"""
Category definitions for merchant classification.

This module contains all valid categories and keyword rules
used by the AI categorizer to classify BCR transactions.
"""

from typing import Set, Dict, List

# Keyword rules for quick categorization (case-insensitive)
KEYWORD_RULES: Dict[str, List[str]] = {
    "Mercado (alimentos, aseo hogar)": [
        "MXM", "SUPER", "MAS X MENOS", "PRICE SMART", "FRESK MARKET"
    ],
    "Combustible": [
        "SERVICENTRO", "ESTACION"
    ],
    "Domicilios/restaurantes": [
        "SODA", "RESTAURANT", "SUBWAY", "CAFE", "COFEE", "PIZZA"
    ],
    "Agua": [
        "AGUA"
    ],
    "Electricidad": [
        "ELECTRICIDAD", "ICE"
    ],
    "Internet": [
        "INTERNET", "CABLE"
    ],
    "Transporte UBER": [
        "UBER"
    ],
    "YouTube Premium": [
        "YOUTUBE"
    ],
    "Chat GPT": [
        "GPT", "CHATGPT"
    ],
    "Plan funerario": [
        "FUNERARIO"
    ],
    "Hipoteca Casa": [
        "HIPOTECA", "VIVIENDA"
    ],
    "Plan celular": [
        "CELULAR", "KOLBI", "PLAN"
    ],
}

# Complete list of all valid categories
VALID_CATEGORIES: Set[str] = {
    "Agua",
    "Agua Desamparados",
    "Chat GPT",
    "Combustible",
    "Consultas médicas",
    "Diversión",
    "Domicilios/restaurantes",
    "Educación",
    "Electricidad",
    "Fruta/Snacks/Café",
    "Hipoteca Casa",
    "Internet",
    "Mantenimiento vehículo",
    "Mantenimiento hogar",
    "Medicamentos",
    "Mercado (alimentos, aseo hogar)",
    "Mesada Gabriel",
    "Mesada Oscar",
    "Peluquería",
    "Plan celular",
    "Plan funerario",
    "Transporte UBER",
    "Vacaciones",
    "Vestuario (ropa/zapato/accesorios)",
    "YouTube Premium",
}


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


def build_categorization_prompt(merchant: str) -> str:
    """
    Build the AI categorization prompt for a merchant.

    Args:
        merchant: The merchant name to categorize

    Returns:
        Complete prompt string for Gemini API
    """
    categories_list = "\n".join(f"- {cat}" for cat in sorted(VALID_CATEGORIES))

    return f"""Classify this merchant into ONE category. Reply with ONLY the category name, nothing else.

Merchant: {merchant}

## CLASSIFICATION RULES (apply these first by searching keywords, case-insensitive):

🛒 Mercado (alimentos, aseo hogar)
Keywords: MXM, SUPER, MAS X MENOS, PRICE SMART, FRESK MARKET

⛽ Combustible
Keywords: SERVICENTRO, ESTACION

🍽️ Domicilios/restaurantes
Keywords: SODA, RESTAURANT, SUBWAY, CAFE, COFEE, PIZZA

💧 Agua
Keywords: AGUA

⚡ Electricidad
Keywords: ELECTRICIDAD, ICE

🌐 Internet
Keywords: INTERNET, CABLE

🚗 Transporte UBER
Keywords: UBER

📺 YouTube Premium
Keywords: YOUTUBE

🤖 Chat GPT
Keywords: GPT, CHATGPT

⚰️ Plan funerario
Keywords: FUNERARIO

🏠 Hipoteca Casa
Keywords: HIPOTECA, VIVIENDA

📱 Plan celular
Keywords: CELULAR, KOLBI, PLAN

## ALL VALID CATEGORIES (use if no keyword rule matches):
{categories_list}

Reply with ONLY the exact category name."""
