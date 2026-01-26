"""
Category definitions for merchant classification.

This module loads categories and keyword rules from categories.yaml
for easy configuration without code changes.
"""

import json
import logging
from pathlib import Path
from typing import Set, Dict, List

import yaml

logger = logging.getLogger(__name__)

def _get_config_file() -> Path:
    """
    Determine which categories config file to use.

    Priority:
    1. categories.yaml (user's custom config, gitignored)
    2. categories.yaml.example (template/fallback)

    Returns:
        Path to the config file to use

    Raises:
        FileNotFoundError: If no config file exists
    """
    config_dir = Path(__file__).parent

    # Priority 1: User's custom categories.yaml
    custom_config = config_dir / "categories.yaml"
    if custom_config.exists():
        return custom_config

    # Priority 2: Example file (template/fallback)
    example_config = config_dir / "categories.yaml.example"
    if example_config.exists():
        logger.warning(
            "Using categories.yaml.example - copy it to categories.yaml and customize your categories"
        )
        return example_config

    raise FileNotFoundError(
        "No categories configuration found.\n"
        "Please copy config/categories.yaml.example to config/categories.yaml"
    )


# Determine which config file to use
_CONFIG_FILE = _get_config_file()


def _load_config() -> dict:
    """
    Load categories configuration from YAML file.

    Returns:
        Dictionary with 'categories' and 'keyword_rules' keys

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded {len(config.get('categories', []))} categories from {_CONFIG_FILE.name}")
    return config


# Load configuration at module import time
_config = _load_config()

# Public variables (same interface as before)
KEYWORD_RULES: Dict[str, List[str]] = _config.get('keyword_rules', {})
VALID_CATEGORIES: Set[str] = set(_config.get('categories', []))


def validate_category(category: str) -> bool:
    """
    Validate that a category exists in the valid categories list.

    Args:
        category: The category name to validate

    Returns:
        True if category is valid, False otherwise
    """
    return category.strip() in VALID_CATEGORIES


def get_category_by_keyword(merchant: str) -> str | None:
    """
    Try to match a merchant to a category using keyword rules.

    Args:
        merchant: The merchant name to match

    Returns:
        Category name if a keyword match is found, None otherwise
    """
    merchant_upper = merchant.upper()

    for category, keywords in KEYWORD_RULES.items():
        for keyword in keywords:
            if keyword in merchant_upper:
                return category

    return None


def build_batch_categorization_prompt(merchants: list[str]) -> str:
    """
    Build the AI categorization prompt for multiple merchants.

    Args:
        merchants: List of merchant names to categorize

    Returns:
        Complete prompt string for Gemini API requesting JSON output
    """
    categories_list = "\n".join(f"- {cat}" for cat in sorted(VALID_CATEGORIES))
    merchants_json = json.dumps(merchants, ensure_ascii=False)

    return f"""You are an expert at categorizing Costa Rican business transactions.

TASK: For each item below, identify what type of expense it represents, then assign the best category.
Items may be merchant names (e.g., "MAS X MENOS") or transaction descriptions/motivos (e.g., "Pago alquiler").

ITEMS TO CATEGORIZE:
{merchants_json}

VALID CATEGORIES:
{categories_list}

CATEGORIZATION RULES:
- Bars, pubs, cantinas, discotecas, restaurants, sodas, cafeterias → "Domicilios/restaurantes"
- Supermarkets, grocery stores, mini-supers, pulperías → "Mercado (alimentos, aseo hogar)"
- Gas stations, gasolineras → "Combustible"
- Pharmacies, farmacias → "Medicamentos"
- Clothing stores, shoe stores, fashion → "Vestuario (ropa/zapato/accesorios)"
- Electronics stores, tech shops → "Diversión" (unless clearly a necessity)
- Entertainment venues, clubs, cinemas → "Diversión"
- Hair salons, barberías → "Peluquería"
- Auto shops, talleres, repuestos → "Mantenimiento vehículo"
- Hardware stores, ferreterías, home repair → "Mantenimiento hogar"
- Medical clinics, doctors, hospitals → "Consultas médicas"

CONFIDENCE REQUIREMENT:
- Only assign a category if you are 80% or more confident it is correct
- If the description is vague, ambiguous, or you cannot determine the category with high confidence, use "Uncategorized"
- Examples of items that should be "Uncategorized": random words, abbreviations without context, names only, gibberish

THINK STEP BY STEP:
1. Look at each item (merchant name or description)
2. Identify what kind of expense it likely represents
3. If you're 80%+ confident, assign the best category; otherwise use "Uncategorized"

OUTPUT: Return ONLY a valid JSON object mapping each item to its category.
Format: {{"Item": "Category"}}

JSON RESPONSE:"""
