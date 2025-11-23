"""
Tests for utility functions.
"""

import pytest
import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.utils import (
    parse_decimal,
    mask_api_key,
    validate_symbol,
    validate_side,
    validate_order_type,
    format_price,
    format_size,
)


class TestParseDecimal:
    """Tests for decimal parsing."""

    def test_parse_string(self):
        """Should parse string to Decimal."""
        assert parse_decimal("123.456") == Decimal("123.456")

    def test_parse_int(self):
        """Should parse int to Decimal."""
        assert parse_decimal(100) == Decimal("100")

    def test_parse_float(self):
        """Should parse float to Decimal."""
        result = parse_decimal(1.5)
        assert result == Decimal("1.5")

    def test_parse_decimal(self):
        """Should return Decimal unchanged."""
        d = Decimal("99.99")
        assert parse_decimal(d) == d

    def test_parse_invalid(self):
        """Should raise ValueError for invalid input."""
        with pytest.raises(ValueError):
            parse_decimal("not a number")


class TestMaskApiKey:
    """Tests for API key masking."""

    def test_mask_normal_key(self):
        """Should mask middle of key."""
        assert mask_api_key("abcd1234efgh5678") == "abcd****5678"

    def test_mask_short_key(self):
        """Should return *** for short keys."""
        assert mask_api_key("short") == "***"
        assert mask_api_key("") == "***"

    def test_mask_none(self):
        """Should handle None."""
        assert mask_api_key(None) == "***"


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_symbols(self):
        """Should accept valid symbol formats."""
        assert validate_symbol("BTC-USDT") is True
        assert validate_symbol("ETH-USDT") is True
        assert validate_symbol("SOL-USDC") is True

    def test_invalid_symbols(self):
        """Should reject invalid symbol formats."""
        assert validate_symbol("BTCUSDT") is False  # No dash
        assert validate_symbol("BTC-") is False  # Empty quote
        assert validate_symbol("-USDT") is False  # Empty base
        assert validate_symbol("") is False
        assert validate_symbol(None) is False


class TestValidateSide:
    """Tests for side validation."""

    def test_valid_sides(self):
        """Should accept BUY and SELL."""
        assert validate_side("BUY") is True
        assert validate_side("SELL") is True
        assert validate_side("buy") is True  # Case insensitive
        assert validate_side("sell") is True

    def test_invalid_sides(self):
        """Should reject invalid sides."""
        assert validate_side("LONG") is False
        assert validate_side("SHORT") is False
        assert validate_side("") is False


class TestValidateOrderType:
    """Tests for order type validation."""

    def test_valid_types(self):
        """Should accept MARKET and LIMIT."""
        assert validate_order_type("MARKET") is True
        assert validate_order_type("LIMIT") is True
        assert validate_order_type("market") is True
        assert validate_order_type("limit") is True

    def test_invalid_types(self):
        """Should reject invalid order types."""
        assert validate_order_type("STOP") is False
        assert validate_order_type("") is False


class TestFormatters:
    """Tests for formatting functions."""

    def test_format_price(self):
        """Should format prices correctly."""
        assert format_price(Decimal("12345.67")) == "12,345.67"
        assert format_price(Decimal("100"), decimals=0) == "100"

    def test_format_size(self):
        """Should format sizes correctly."""
        assert format_size(Decimal("0.001234")) == "0.001234"
        assert format_size(Decimal("1.5"), decimals=2) == "1.50"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
