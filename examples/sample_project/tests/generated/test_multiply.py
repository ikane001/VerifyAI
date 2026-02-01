import pytest
from typing import Union
from decimal import Decimal
import math
import sys

# Assuming Number is a type alias for numeric types
Number = Union[int, float, complex, Decimal]

# Import the function to test
from calculator import multiply


class TestMultiply:
    """Test suite for the multiply function."""

    def test_multiply_positive_integers_returns_correct_product(self):
        """Test multiplication of two positive integers."""
        result = multiply(3, 4)
        assert result == 12
        assert isinstance(result, int)

    def test_multiply_negative_integers_returns_correct_product(self):
        """Test multiplication of two negative integers."""
        result = multiply(-3, -4)
        assert result == 12
        assert isinstance(result, int)

    def test_multiply_positive_and_negative_integer_returns_negative_product(self):
        """Test multiplication of positive and negative integer."""
        result = multiply(3, -4)
        assert result == -12
        assert isinstance(