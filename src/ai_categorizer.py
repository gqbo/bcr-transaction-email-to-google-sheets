"""
AI-powered merchant categorization using Google Gemini.

This module uses Gemini 2.0 Flash to categorize merchants
into predefined spending categories.
"""

import os
import logging
import time
from typing import Optional

import google.generativeai as genai

from config.categories import (
    VALID_CATEGORIES,
    validate_category,
    get_category_by_keyword,
    build_categorization_prompt
)

logger = logging.getLogger(__name__)

# Gemini model configuration
MODEL_NAME = "models/gemini-2.5-flash-lite"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Module-level model instance (initialized lazily)
_model: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    """
    Get or initialize the Gemini model.

    Returns:
        Configured GenerativeModel instance

    Raises:
        ValueError: If GEMINI_API_KEY is not set
    """
    global _model

    if _model is None:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"Initialized Gemini model: {MODEL_NAME}")

    return _model


def categorize_merchant(merchant: str) -> str:
    """
    Categorize a merchant using Gemini AI.

    First attempts keyword-based categorization for common merchants,
    then falls back to AI categorization.

    Args:
        merchant: Merchant name to categorize

    Returns:
        Category name from VALID_CATEGORIES, or "Uncategorized" if
        categorization fails
    """
    if not merchant:
        logger.warning("Empty merchant name provided")
        return "Uncategorized"

    # Try keyword-based categorization first (faster, no API call)
    keyword_category = get_category_by_keyword(merchant)
    if keyword_category:
        logger.info(f"Categorized '{merchant}' via keyword: {keyword_category}")
        return keyword_category

    # Fall back to AI categorization
    return _categorize_with_ai(merchant)


def _categorize_with_ai(merchant: str) -> str:
    """
    Categorize merchant using Gemini AI with retry logic.

    Args:
        merchant: Merchant name to categorize

    Returns:
        Category name or "Uncategorized" on failure
    """
    prompt = build_categorization_prompt(merchant)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            model = _get_model()

            # Generate with temperature=0 for deterministic results
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    max_output_tokens=50
                )
            )

            category = response.text.strip()

            # Validate the returned category
            if validate_category(category):
                logger.info(f"AI categorized '{merchant}' as: {category}")
                return category
            else:
                logger.warning(
                    f"AI returned invalid category '{category}' for '{merchant}'"
                )
                # Try to find closest match
                closest = _find_closest_category(category)
                if closest:
                    logger.info(f"Using closest match: {closest}")
                    return closest
                return "Uncategorized"

        except Exception as e:
            logger.error(
                f"Attempt {attempt}/{MAX_RETRIES} failed for '{merchant}': {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)  # Exponential backoff
            continue

    logger.error(f"All attempts failed to categorize '{merchant}'")
    return "Uncategorized"


def _find_closest_category(category: str) -> Optional[str]:
    """
    Find the closest matching valid category.

    Useful when AI returns a slightly different category name.

    Args:
        category: Category name to match

    Returns:
        Closest matching category or None
    """
    category_lower = category.lower().strip()

    for valid_cat in VALID_CATEGORIES:
        if valid_cat.lower() == category_lower:
            return valid_cat
        # Check if the category is contained in a valid category
        if category_lower in valid_cat.lower():
            return valid_cat
        if valid_cat.lower() in category_lower:
            return valid_cat

    return None


def batch_categorize(merchants: list[str]) -> dict[str, str]:
    """
    Categorize multiple merchants.

    Args:
        merchants: List of merchant names

    Returns:
        Dictionary mapping merchant names to categories
    """
    results = {}
    for merchant in merchants:
        results[merchant] = categorize_merchant(merchant)
    return results
