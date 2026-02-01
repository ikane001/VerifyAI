import pytest
from typing import Union
from decimal import Decimal
import math

# Assuming Number is a type alias for numeric types
Number = Union[int, float, complex, Decimal]

# Import the function to test
from calculator import subtract


class TestSubtract:
    """Test suite for the subtract function."""

    def test_subtract_positive_integers_returns_correct_difference(self):
        """Test subtraction of two positive integers."""
        result = subtract(10, 3)
        assert result == 7
        assert isinstance(result, int)

    def test_subtract_negative_integers_returns_correct_difference(self):
        """Test subtraction of two negative integers."""
        result = subtract(-5, -3)
        assert result == -2
        assert isinstance(result, int)

    def test_subtract_mixed_sign_integers_returns_correct_difference(self):
        """Test subtraction with mixed positive and negative integers."""
        result = subtract(5, -3)
        assert result == 8
        assert isinstance(result, int)

    def test_subtract_negative_from_positive_returns_correct_difference(self):
        """Test subtracting negative from positive integer."""
        result = subtract(-5, 3)
        assert result == -8
        assert isinstance(result, int)

    def test_subtract_zero_from_number_returns_same_number(self):
        """Test subtracting zero from a number returns the same number."""
        result = subtract(42, 0)
        assert result == 42
        assert isinstance(result, int)

    def test_subtract_number_from_zero_returns_negative(self):
        """Test subtracting a number from zero returns negative of that number."""
        result = subtract(0, 15)
        assert result == -15
        assert isinstance(result, int)

    def test_subtract_same_numbers_returns_zero(self):
        """Test subtracting a number from itself returns zero."""
        result = subtract(7, 7)
        assert result == 0
        assert isinstance(result, int)

    def test_subtract_floats_returns_correct_difference(self):
        """Test subtraction of two float numbers."""
        result = subtract(10.5, 3.2)
        assert abs(result - 7.3) < 1e-10  # Account for floating point precision
        assert isinstance(result, float)

    def test_subtract_float_from_integer_returns_float(self):
        """Test subtracting float from integer returns float."""
        result = subtract(10, 3.5)
        assert abs(result - 6.5) < 1e-10
        assert isinstance(result, float)

    def test_subtract_integer_from_float_returns_float(self):
        """Test subtracting integer from float returns float."""
        result = subtract(10.5, 3)
        assert abs(result - 7.5) < 1e-10
        assert isinstance(result, float)

    def test_subtract_very_large_numbers_returns_correct_difference(self):
        """Test subtraction with very large numbers."""
        large_num1 = 10**15
        large_num2 = 10**14
        result = subtract(large_num1, large_num2)
        expected = 9 * (10**14)
        assert result == expected

    def test_subtract_very_small_numbers_returns_correct_difference(self):
        """Test subtraction with very small numbers."""
        small_num1 = 1e-10
        small_num2 = 1e-11
        result = subtract(small_num1, small_num2)
        expected = 9e-11
        assert abs(result - expected) < 1e-20

    def test_subtract_decimal_numbers_returns_correct_difference(self):
        """Test subtraction with Decimal numbers for precise arithmetic."""
        a = Decimal('10.50')
        b = Decimal('3.25')
        result = subtract(a, b)
        expected = Decimal('7.25')
        assert result == expected
        assert isinstance(result, Decimal)

    def test_subtract_complex_numbers_returns_correct_difference(self):
        """Test subtraction of complex numbers."""
        a = complex(5, 3)
        b = complex(2, 1)
        result = subtract(a, b)
        expected = complex(3, 2)
        assert result == expected
        assert isinstance(result, complex)

    def test_subtract_complex_with_real_returns_complex(self):
        """Test subtracting real number from complex number."""
        a = complex(5, 3)
        b = 2
        result = subtract(a, b)
        expected = complex(3, 3)
        assert result == expected
        assert isinstance(result, complex)

    def test_subtract_real_from_complex_returns_complex(self):
        """Test subtracting complex number from real number."""
        a = 5
        b = complex(2, 1)
        result = subtract(a, b)
        expected = complex(3, -1)
        assert result == expected
        assert isinstance(result, complex)

    def test_subtract_infinity_values_handles_correctly(self):
        """Test subtraction with infinity values."""
        result = subtract(float('inf'), 100)
        assert result == float('inf')
        
        result = subtract(100, float('inf'))
        assert result == float('-inf')

    def test_subtract_negative_infinity_handles_correctly(self):
        """Test subtraction with negative infinity."""
        result = subtract(float('-inf'), 100)
        assert result == float('-inf')
        
        result = subtract(100, float('-inf'))
        assert result == float('inf')

    def test_subtract_nan_returns_nan(self):
        """Test subtraction with NaN values."""
        result = subtract(float('nan'), 5)
        assert math.isnan(result)
        
        result = subtract(5, float('nan'))
        assert math.isnan(result)

    def test_subtract_infinity_from_infinity_returns_nan(self):
        """Test subtracting infinity from infinity returns NaN."""
        result = subtract(float('inf'), float('inf'))
        assert math.isnan(result)

    def test_subtract_negative_infinity_from_negative_infinity_returns_nan(self):
        """Test subtracting negative infinity from negative infinity returns NaN."""
        result = subtract(float('-inf'), float('-inf'))
        assert math.isnan(result)

    def test_subtract_preserves_type_hierarchy(self):
        """Test that subtraction preserves Python's numeric type hierarchy."""
        # int - int = int
        assert isinstance(subtract(5, 3), int)
        
        # float - int = float
        assert isinstance(subtract(5.0, 3), float)
        
        # int - float = float
        assert isinstance(subtract(5, 3.0), float)
        
        # complex - int = complex
        assert isinstance(subtract(complex(5, 0), 3), complex)

    @pytest.mark.parametrize("a,b,expected", [
        (0, 0, 0),
        (1, 1, 0),
        (-1, -1, 0),
        (100, 50, 50),
        (-100, -50, -50),
        (0.5, 0.3, 0.2),
        (-0.5, -0.3, -0.2),
    ])
    def test_subtract_parametrized_cases_return_expected_results(self, a, b, expected):
        """Test various subtraction cases using parametrized testing."""
        result = subtract(a, b)
        if isinstance(expected, float):
            assert abs(result - expected) < 1e-10
        else:
            assert result == expected

    def test_subtract_boolean_values_treated_as_integers(self):
        """Test that boolean values are treated as integers (True=1, False=0)."""
        assert subtract(True, False) == 1
        assert subtract(False, True) == -1
        assert subtract(True, True) == 0
        assert subtract(False, False) == 0

    def test_subtract_mixed_boolean_and_numeric_types(self):
        """Test subtraction with mixed boolean and numeric types."""
        assert subtract(5, True) == 4  # 5 - 1
        assert subtract(True, 5) == -4  # 1 - 5
        assert subtract(3.5, True) == 2.5  # 3.5 - 1
        assert subtract(False, 2.5) == -2.5  # 0 - 2.5