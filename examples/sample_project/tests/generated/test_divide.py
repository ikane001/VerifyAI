import pytest
from typing import Union
from decimal import Decimal
from fractions import Fraction
import math

# Assuming Number is a type alias for numeric types
Number = Union[int, float, complex, Decimal, Fraction]

# Import the function to test
from calculator import divide


class TestDivide:
    """Test suite for the divide function."""

    def test_divide_positive_integers_returns_float(self):
        """Test division of positive integers returns correct float result."""
        result = divide(10, 2)
        assert result == 5.0
        assert isinstance(result, float)

    def test_divide_negative_integers_returns_float(self):
        """Test division of negative integers returns correct float result."""
        result = divide(-10, 2)
        assert result == -5.0
        assert isinstance(result, float)

    def test_divide_positive_by_negative_returns_negative_float(self):
        """Test division of positive by negative returns negative float."""
        result = divide(10, -2)
        assert result == -5.0
        assert isinstance(result, float)

    def test_divide_negative_by_negative_returns_positive_float(self):
        """Test division of negative by negative returns positive float."""
        result = divide(-10, -2)
        assert result == 5.0
        assert isinstance(result, float)

    def test_divide_floats_returns_correct_result(self):
        """Test division of float numbers returns correct result."""
        result = divide(7.5, 2.5)
        assert result == 3.0
        assert isinstance(result, float)

    def test_divide_with_decimal_precision(self):
        """Test division that results in decimal places."""
        result = divide(1, 3)
        assert abs(result - 0.3333333333333333) < 1e-15
        assert isinstance(result, float)

    def test_divide_large_numbers_returns_correct_result(self):
        """Test division of large numbers."""
        result = divide(1000000, 1000)
        assert result == 1000.0
        assert isinstance(result, float)

    def test_divide_small_numbers_returns_correct_result(self):
        """Test division of very small numbers."""
        result = divide(0.001, 0.1)
        assert abs(result - 0.01) < 1e-15
        assert isinstance(result, float)

    def test_divide_zero_by_nonzero_returns_zero(self):
        """Test division of zero by non-zero number returns zero."""
        result = divide(0, 5)
        assert result == 0.0
        assert isinstance(result, float)

    def test_divide_zero_by_negative_returns_zero(self):
        """Test division of zero by negative number returns zero."""
        result = divide(0, -5)
        assert result == 0.0
        assert isinstance(result, float)

    def test_divide_by_zero_raises_zero_division_error(self):
        """Test division by zero raises ZeroDivisionError with correct message."""
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            divide(10, 0)

    def test_divide_negative_by_zero_raises_zero_division_error(self):
        """Test division of negative number by zero raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            divide(-10, 0)

    def test_divide_zero_by_zero_raises_zero_division_error(self):
        """Test division of zero by zero raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            divide(0, 0)

    def test_divide_float_by_zero_raises_zero_division_error(self):
        """Test division of float by zero raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            divide(3.14, 0)

    def test_divide_by_zero_float_raises_zero_division_error(self):
        """Test division by zero float raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            divide(10, 0.0)

    def test_divide_complex_numbers_returns_complex_result(self):
        """Test division of complex numbers returns correct result."""
        result = divide(4+2j, 2)
        assert result == (2+1j)
        # Note: complex division returns complex, not float

    def test_divide_by_complex_number_returns_complex_result(self):
        """Test division by complex number returns correct result."""
        result = divide(4, 1+1j)
        expected = 4 / (1+1j)
        assert result == expected

    def test_divide_decimal_numbers_returns_float(self):
        """Test division of Decimal numbers returns float result."""
        result = divide(Decimal('10'), Decimal('2'))
        assert result == 5.0
        assert isinstance(result, float)

    def test_divide_fraction_numbers_returns_float(self):
        """Test division of Fraction numbers returns float result."""
        result =