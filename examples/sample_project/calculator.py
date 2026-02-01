"""A simple calculator module for demonstration."""

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Subtract b from a.

    Args:
        a: First number
        b: Second number

    Returns:
        Difference of a and b
    """
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b


def divide(a: Number, b: Number) -> float:
    """Divide a by b.

    Args:
        a: Dividend
        b: Divisor

    Returns:
        Quotient of a / b

    Raises:
        ZeroDivisionError: If b is zero
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


class Calculator:
    """A calculator class with memory."""

    def __init__(self, initial_value: Number = 0):
        """Initialize calculator with optional initial value.

        Args:
            initial_value: Starting value for memory
        """
        self.memory = initial_value

    def add(self, value: Number) -> Number:
        """Add value to memory.

        Args:
            value: Value to add

        Returns:
            New memory value
        """
        self.memory = add(self.memory, value)
        return self.memory

    def subtract(self, value: Number) -> Number:
        """Subtract value from memory.

        Args:
            value: Value to subtract

        Returns:
            New memory value
        """
        self.memory = subtract(self.memory, value)
        return self.memory

    def multiply(self, value: Number) -> Number:
        """Multiply memory by value.

        Args:
            value: Value to multiply by

        Returns:
            New memory value
        """
        self.memory = multiply(self.memory, value)
        return self.memory

    def divide(self, value: Number) -> float:
        """Divide memory by value.

        Args:
            value: Value to divide by

        Returns:
            New memory value

        Raises:
            ZeroDivisionError: If value is zero
        """
        self.memory = divide(self.memory, value)
        return self.memory

    def clear(self) -> None:
        """Reset memory to zero."""
        self.memory = 0

    def get_memory(self) -> Number:
        """Get current memory value.

        Returns:
            Current memory value
        """
        return self.memory
