"""Synthetic fixtures only; these modules never measure vocal features."""
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def mock_implementation(function: F) -> F:
    """Optional runtime marker to reject known mocks before running real mode."""
    setattr(function, "suara_mode", "mock")
    return function
