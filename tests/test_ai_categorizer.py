"""
Unit tests for the AI categorizer module.

Run with: pytest tests/test_ai_categorizer.py -v

These tests demonstrate the power of Dependency Injection:
- ALL tests run WITHOUT any real Gemini API calls
- Tests use fake models that return predictable results
- Tests are fast, reliable, and free (no API costs)

Compare this to testing without DI:
- Would require real GEMINI_API_KEY
- Would make real API calls (slow, flaky, costs money)
- Would be hard to test error handling
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai_categorizer import AICategorizer


# ============================================================
# Fake Model Classes for Testing
# ============================================================

class FakeResponse:
    """
    Fake Gemini response object.

    Mimics the structure of a real Gemini response so the
    AICategorizer can process it normally.
    """

    def __init__(self, text: str):
        self.candidates = [FakeCandidate(text)]


class FakeCandidate:
    """Fake candidate containing content."""

    def __init__(self, text: str):
        self.content = FakeContent(text)


class FakeContent:
    """Fake content containing parts."""

    def __init__(self, text: str):
        self.parts = [FakePart(text)]


class FakePart:
    """Fake part containing text."""

    def __init__(self, text: str):
        self.text = text


class FakeModel:
    """
    Fake generative model for testing.

    This class demonstrates the power of Dependency Injection:
    - Returns predictable responses (no network calls)
    - Can track what prompts were sent
    - Can simulate different behaviors (errors, empty responses)

    Example:
        >>> fake = FakeModel('{"UBER": "Transporte UBER"}')
        >>> categorizer = AICategorizer(model=fake)
        >>> result = categorizer.categorize_merchant("UBER")
        >>> assert result == "Transporte UBER"
        >>> assert len(fake.calls) == 1  # Verify API was called
    """

    def __init__(self, response_text: str):
        """
        Initialize fake model with predetermined response.

        Args:
            response_text: The JSON text the model should return
        """
        self.response_text = response_text
        self.calls = []  # Track all calls for verification

    def generate_content(self, prompt: str, generation_config=None):
        """
        Return fake response (no API call).

        Records the call for later verification.
        """
        self.calls.append({
            "prompt": prompt,
            "config": generation_config
        })
        return FakeResponse(self.response_text)


class ErrorModel:
    """Fake model that raises an exception."""

    def __init__(self, error: Exception):
        self.error = error

    def generate_content(self, prompt: str, generation_config=None):
        raise self.error


class EmptyResponseModel:
    """Fake model that returns empty/blocked response."""

    def generate_content(self, prompt: str, generation_config=None):
        response = FakeResponse("")
        response.candidates = []  # No candidates (blocked)
        return response


# ============================================================
# Tests for AICategorizer
# ============================================================

class TestAICategorizerBasic:
    """Basic tests for AICategorizer functionality."""

    def test_empty_merchant_returns_uncategorized(self):
        """Test that empty merchant name returns Uncategorized without API call."""
        fake = FakeModel('{"test": "category"}')
        categorizer = AICategorizer(model=fake)

        result = categorizer.categorize_merchant("")

        assert result == "Uncategorized"
        assert len(fake.calls) == 0  # No API call made

    def test_whitespace_merchant_returns_uncategorized(self):
        """Test that whitespace-only merchant returns Uncategorized."""
        fake = FakeModel('{"test": "category"}')
        categorizer = AICategorizer(model=fake)

        result = categorizer.categorize_merchant("   ")

        assert result == "Uncategorized"
        assert len(fake.calls) == 0


class TestAICategorizerKeywordMatching:
    """Tests for keyword-based categorization (no API call)."""

    def test_uber_categorized_by_keyword(self):
        """Test that UBER is categorized by keyword without AI."""
        fake = FakeModel('{}')  # Won't be used
        categorizer = AICategorizer(model=fake)

        result = categorizer.categorize_merchant("UBER COSTA RICA")

        assert result == "Transporte UBER"
        assert len(fake.calls) == 0  # No AI call needed

    def test_mas_x_menos_categorized_by_keyword(self):
        """Test that MAS X MENOS is categorized by keyword."""
        fake = FakeModel('{}')
        categorizer = AICategorizer(model=fake)

        result = categorizer.categorize_merchant("MAS X MENOS SAN JOSE")

        assert result == "Mercado (alimentos, aseo hogar)"
        assert len(fake.calls) == 0


class TestAICategorizerBatchWithFakeModel:
    """Tests for batch categorization using fake model."""

    def test_batch_categorize_with_valid_json_response(self):
        """Test batch categorization with valid JSON from fake model."""
        fake = FakeModel('{"Store A": "Mercado (alimentos, aseo hogar)", "Restaurant B": "Domicilios/restaurantes"}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Store A", "Restaurant B"])

        assert results["Store A"] == "Mercado (alimentos, aseo hogar)"
        assert results["Restaurant B"] == "Domicilios/restaurantes"
        assert len(fake.calls) == 1  # Single batch API call

    def test_batch_categorize_with_markdown_json(self):
        """Test handling of markdown-wrapped JSON response."""
        fake = FakeModel('```json\n{"Store": "Mercado (alimentos, aseo hogar)"}\n```')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Store"])

        assert results["Store"] == "Mercado (alimentos, aseo hogar)"

    def test_batch_categorize_mixed_keyword_and_ai(self):
        """Test that keywords are matched first, then AI is called for rest."""
        fake = FakeModel('{"Unknown Store": "Diversión"}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["UBER", "Unknown Store"])

        # UBER should be categorized by keyword (no AI call)
        assert results["UBER"] == "Transporte UBER"
        # Unknown Store should be categorized by AI
        assert results["Unknown Store"] == "Diversión"
        # Only one AI call (for "Unknown Store", not "UBER")
        assert len(fake.calls) == 1

    def test_batch_categorize_all_keywords_no_ai_call(self):
        """Test that if all items match keywords, no AI call is made."""
        fake = FakeModel('{}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["UBER", "MAS X MENOS"])

        assert results["UBER"] == "Transporte UBER"
        assert results["MAS X MENOS"] == "Mercado (alimentos, aseo hogar)"
        assert len(fake.calls) == 0  # No AI calls!


class TestAICategorizerErrorHandling:
    """Tests for error handling in categorization."""

    def test_api_error_returns_uncategorized(self):
        """Test that API errors result in Uncategorized."""
        error_model = ErrorModel(Exception("API connection failed"))
        categorizer = AICategorizer(model=error_model)

        results = categorizer.batch_categorize(["Some Store"])

        assert results["Some Store"] == "Uncategorized"

    def test_empty_response_returns_uncategorized(self):
        """Test that empty/blocked response results in Uncategorized."""
        empty_model = EmptyResponseModel()
        categorizer = AICategorizer(model=empty_model)

        results = categorizer.batch_categorize(["Some Store"])

        assert results["Some Store"] == "Uncategorized"

    def test_invalid_json_attempts_partial_recovery(self):
        """Test that invalid JSON attempts partial recovery."""
        # Truncated JSON - only first pair is complete
        fake = FakeModel('{"Complete Store": "Mercado (alimentos, aseo hogar)", "Incomplete')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Complete Store", "Incomplete"])

        # Should recover "Complete Store"
        assert results["Complete Store"] == "Mercado (alimentos, aseo hogar)"
        # "Incomplete" should be Uncategorized (not in recovered JSON)
        assert results["Incomplete"] == "Uncategorized"

    def test_invalid_category_finds_closest_match(self):
        """Test that invalid category names are matched to closest valid one."""
        # Return slightly wrong category name
        fake = FakeModel('{"Store": "mercado"}')  # lowercase, partial
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Store"])

        # Should match to "Mercado (alimentos, aseo hogar)"
        assert "Mercado" in results["Store"]

    def test_completely_invalid_category_returns_uncategorized(self):
        """Test that completely invalid category returns Uncategorized."""
        fake = FakeModel('{"Store": "NonExistentCategory123"}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Store"])

        assert results["Store"] == "Uncategorized"


class TestAICategorizerUncategorizablePhrases:
    """Tests for handling of uncategorizable phrases."""

    def test_sin_descripcion_returns_uncategorized(self):
        """Test that 'Sin Descripcion' returns Uncategorized without AI call."""
        fake = FakeModel('{}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["Sin Descripcion"])

        assert results["Sin Descripcion"] == "Uncategorized"
        assert len(fake.calls) == 0

    def test_na_returns_uncategorized(self):
        """Test that 'N/A' returns Uncategorized without AI call."""
        fake = FakeModel('{}')
        categorizer = AICategorizer(model=fake)

        results = categorizer.batch_categorize(["N/A"])

        assert results["N/A"] == "Uncategorized"
        assert len(fake.calls) == 0


class TestAICategorizerPromptVerification:
    """Tests that verify the correct prompt is sent to the model."""

    def test_prompt_contains_merchants(self):
        """Test that the prompt includes the merchants to categorize."""
        fake = FakeModel('{"Test Store": "Diversión"}')
        categorizer = AICategorizer(model=fake)

        categorizer.batch_categorize(["Test Store"])

        assert len(fake.calls) == 1
        prompt = fake.calls[0]["prompt"]
        assert "Test Store" in prompt

    def test_prompt_contains_valid_categories(self):
        """Test that the prompt includes valid category options."""
        fake = FakeModel('{"Test Store": "Diversión"}')
        categorizer = AICategorizer(model=fake)

        categorizer.batch_categorize(["Test Store"])

        prompt = fake.calls[0]["prompt"]
        # Should contain some valid categories
        assert "Mercado" in prompt or "Domicilios" in prompt or "Combustible" in prompt
