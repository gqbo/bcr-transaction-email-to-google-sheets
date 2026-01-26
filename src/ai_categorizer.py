"""
AI-powered transaction categorization using Google Gemini.

This module uses Gemini 2.5 Flash to categorize transactions
into predefined spending categories based on:
- Merchant names (for card transactions)
- Motivo/reason (for SINPE transactions)

Architecture:
- AICategorizer class uses dependency injection for testability
- Backward-compatible functions wrap the class for existing code
- Factory function creates instances with real Gemini model
"""

import os
import logging
import json
import re
from dataclasses import dataclass
from typing import Optional, Protocol, Any

import google.generativeai as genai

from config.categories import (
    VALID_CATEGORIES,
    validate_category,
    get_category_by_keyword,
    build_batch_categorization_prompt
)

logger = logging.getLogger(__name__)

# Gemini model configuration
MODEL_NAME = "models/gemini-2.5-flash-lite"


# ============================================================
# Protocol (Interface) for Generative Model
# ============================================================

class GenerativeModelProtocol(Protocol):
    """
    Protocol defining what we need from a generative model.

    Why use a Protocol?
    ------------------
    A Protocol is like an interface - it defines what methods a class
    must have, without specifying how they work. This lets us:
    1. Use the real Gemini model in production
    2. Use a fake model in tests (that returns predictable results)

    The actual model just needs to have a generate_content method
    that matches this signature.
    """

    def generate_content(
        self,
        prompt: str,
        generation_config: Any = None
    ) -> Any:
        """Generate content from a prompt."""
        ...


# ============================================================
# Main AICategorizer Class (Dependency Injection)
# ============================================================

@dataclass
class AICategorizer:
    """
    AI-powered transaction categorizer with injectable dependencies.

    Why use Dependency Injection?
    -----------------------------
    Instead of creating the Gemini model inside this class (hidden dependency),
    we accept it as a parameter (explicit dependency). This means:

    1. **Testable**: We can inject a fake model that returns predictable results
    2. **Explicit**: Reading the code shows exactly what dependencies are needed
    3. **Flexible**: Different models can be used without changing this class

    Example (Production):
        >>> model = genai.GenerativeModel("models/gemini-2.5-flash-lite")
        >>> categorizer = AICategorizer(model=model)
        >>> result = categorizer.categorize_merchant("UBER")

    Example (Testing):
        >>> fake_model = FakeModel(returns='{"UBER": "Transporte UBER"}')
        >>> categorizer = AICategorizer(model=fake_model)  # No API call!
        >>> result = categorizer.categorize_merchant("UBER")

    Attributes:
        model: A generative model that implements generate_content()
    """

    model: GenerativeModelProtocol

    def categorize_merchant(self, merchant: str) -> str:
        """
        Categorize a single merchant.

        This is a convenience wrapper around batch_categorize for single merchants.

        Args:
            merchant: Merchant name to categorize

        Returns:
            Category name from VALID_CATEGORIES, or "Uncategorized" if
            categorization fails
        """
        if not merchant:
            logger.warning("Empty merchant name provided")
            return "Uncategorized"

        results = self.batch_categorize([merchant])
        return results.get(merchant, "Uncategorized")

    def batch_categorize(self, concepto_sources: list[str]) -> dict[str, str]:
        """
        Categorize multiple transactions efficiently.

        First applies keyword matching (no API call), then batches remaining
        items into a single AI API call.

        Args:
            concepto_sources: List of categorization sources:
                - Merchant names (for card transactions)
                - Motivo/reason (for SINPE transactions)

        Returns:
            Dictionary mapping source strings to categories.
            Empty or whitespace-only strings return "Uncategorized".
        """
        results = {}
        needs_ai = []

        # Phrases that indicate no meaningful description
        uncategorizable_phrases = [
            "sin descripcion",
            "sin descripción",
            "no descripcion",
            "no descripción",
            "n/a",
            "na",
        ]

        # First pass: keyword matching (free, no API call)
        for source in concepto_sources:
            # Handle empty or whitespace-only strings
            if not source or not source.strip():
                results[source] = "Uncategorized"
                continue

            # Handle "Sin Descripcion" and similar phrases
            source_lower = source.strip().lower()
            if source_lower in uncategorizable_phrases:
                logger.info(f"Skipping categorization for '{source}' (no meaningful description)")
                results[source] = "Uncategorized"
                continue

            keyword_category = get_category_by_keyword(source)
            if keyword_category:
                logger.info(f"Categorized '{source}' via keyword: {keyword_category}")
                results[source] = keyword_category
            else:
                needs_ai.append(source)

        # Second pass: batch AI call for remaining items
        if needs_ai:
            logger.info(f"Batch categorizing {len(needs_ai)} items via AI")
            ai_results = self._batch_categorize_with_ai(needs_ai)
            results.update(ai_results)

        return results

    def _batch_categorize_with_ai(self, merchants: list[str]) -> dict[str, str]:
        """
        Categorize multiple merchants in a single API call.

        Args:
            merchants: List of merchant names to categorize

        Returns:
            Dictionary mapping merchant names to categories.
            On failure, all merchants are mapped to "Uncategorized".
        """
        if not merchants:
            return {}

        prompt = build_batch_categorization_prompt(merchants)

        try:
            # Use higher token limit for batch responses
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    max_output_tokens=10000
                )
            )

            # Handle multi-part responses properly
            if response.candidates and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text.strip()
            else:
                raise ValueError("Empty or blocked response from Gemini")

            # Parse JSON response
            logger.debug(f"Raw Gemini response: {response_text}")

            # Remove markdown code block if present
            if "```" in response_text:
                # Extract content between ``` markers
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    response_text = json_match.group(1).strip()
                else:
                    # Try removing just the opening ```
                    response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                    response_text = re.sub(r'\s*```$', '', response_text)

            # Clean up common JSON issues
            response_text = response_text.strip()

            try:
                categories_map = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed, attempting partial recovery: {response_text[:200]}")
                # Try to extract valid key-value pairs from truncated JSON
                categories_map = self._extract_partial_json(response_text)
                if not categories_map:
                    logger.error("Could not recover any data from response")
                    raise ValueError(f"Invalid JSON from Gemini: {e}")

            # Validate and build results
            results = {}
            for merchant in merchants:
                category = categories_map.get(merchant, "Uncategorized")
                if validate_category(category):
                    results[merchant] = category
                    logger.info(f"Batch AI categorized '{merchant}' as: {category}")
                else:
                    # Try to find closest match
                    closest = self._find_closest_category(category)
                    if closest:
                        results[merchant] = closest
                        logger.info(f"Batch AI: '{merchant}' -> closest match: {closest}")
                    else:
                        results[merchant] = "Uncategorized"
                        logger.warning(f"Batch AI: invalid category '{category}' for '{merchant}'")

            return results

        except Exception as e:
            logger.error(f"Batch categorization failed: {e}")
            # Return all as Uncategorized on failure
            return {merchant: "Uncategorized" for merchant in merchants}

    def _find_closest_category(self, category: str) -> Optional[str]:
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

    def _extract_partial_json(self, text: str) -> dict[str, str]:
        """
        Extract valid key-value pairs from a potentially truncated JSON response.

        Args:
            text: Potentially malformed JSON string

        Returns:
            Dictionary of successfully extracted merchant->category pairs
        """
        results = {}
        # Pattern to match complete "key": "value" pairs
        pattern = r'"([^"]+)"\s*:\s*"([^"]+)"'
        matches = re.findall(pattern, text)

        for merchant, category in matches:
            if validate_category(category):
                results[merchant] = category
                logger.info(f"Recovered from partial JSON: '{merchant}' -> '{category}'")
            else:
                closest = self._find_closest_category(category)
                if closest:
                    results[merchant] = closest
                    logger.info(f"Recovered with closest match: '{merchant}' -> '{closest}'")

        return results


# ============================================================
# Factory Function (Creates Real Instances)
# ============================================================

def create_categorizer(api_key: Optional[str] = None) -> AICategorizer:
    """
    Create an AICategorizer with a real Gemini model.

    This is the "factory" function that creates properly configured
    instances for production use.

    Why a factory function?
    -----------------------
    - Encapsulates the complexity of setting up the real Gemini model
    - Keeps the AICategorizer class focused on business logic
    - Easy to swap out for testing (just create AICategorizer directly with a fake)

    Args:
        api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.

    Returns:
        Configured AICategorizer instance ready for use

    Raises:
        ValueError: If API key is not provided or found in environment
    """
    key = api_key or os.environ.get('GEMINI_API_KEY')
    if not key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    genai.configure(api_key=key)
    model = genai.GenerativeModel(MODEL_NAME)
    logger.info(f"Created AICategorizer with model: {MODEL_NAME}")

    return AICategorizer(model=model)


# ============================================================
# Backward-Compatible Module-Level Functions
# ============================================================

# These functions maintain backward compatibility with existing code
# that calls categorize_merchant() and batch_categorize() directly.
# They lazily initialize a default categorizer instance.

_default_categorizer: Optional[AICategorizer] = None


def _get_default_categorizer() -> AICategorizer:
    """
    Get or create the default categorizer instance.

    Uses lazy initialization - only creates the Gemini model
    when first needed.
    """
    global _default_categorizer
    if _default_categorizer is None:
        _default_categorizer = create_categorizer()
    return _default_categorizer


def categorize_merchant(merchant: str) -> str:
    """
    Categorize a single merchant (backward-compatible function).

    This function maintains compatibility with existing code.
    For new code, consider using AICategorizer directly for better testability.

    Args:
        merchant: Merchant name to categorize

    Returns:
        Category name from VALID_CATEGORIES, or "Uncategorized"
    """
    return _get_default_categorizer().categorize_merchant(merchant)


def batch_categorize(concepto_sources: list[str]) -> dict[str, str]:
    """
    Categorize multiple transactions efficiently (backward-compatible function).

    This function maintains compatibility with existing code.
    For new code, consider using AICategorizer directly for better testability.

    Args:
        concepto_sources: List of merchant names or motivos to categorize

    Returns:
        Dictionary mapping source strings to categories
    """
    return _get_default_categorizer().batch_categorize(concepto_sources)
