import pytest
from decimal import Decimal
from fractions import Fraction
from typing import Union
import math
import sys

# Assuming Number is a type alias for numeric types
Number = Union[int, float, complex, Decimal, Fraction]

# Import the function to test
from calculator