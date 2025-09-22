"""Error handling utilities and decorators"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from ..exceptions import AnkiVocabError

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


def handle_errors(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    reraise_on: type[Exception] | tuple[type[Exception], ...] | None = None,
    operation_name: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for handling errors with customizable behavior.

    Args:
        default_return: Value to return when an error occurs
        log_level: Logging level for error messages
        reraise_on: Exception type(s) to reraise instead of handling
        operation_name: Custom operation name for logging (defaults to function name)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            logger = logging.getLogger(func.__module__)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check if we should reraise certain exceptions
                if reraise_on and isinstance(e, reraise_on):
                    raise

                # Log the error with appropriate context
                if isinstance(e, AnkiVocabError):
                    logger.log(log_level, f"Application error in {op_name}: {e}")
                    if e.details:
                        logger.debug(f"Error details for {op_name}: {e.details}")
                else:
                    logger.log(
                        log_level, f"Unexpected error in {op_name}: {e}", exc_info=True
                    )

                return cast(T, default_return)

        return wrapper

    return decorator


def handle_errors_async(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    reraise_on: type[Exception] | tuple[type[Exception], ...] | None = None,
    operation_name: str | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Async version of the error handling decorator.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            logger = logging.getLogger(func.__module__)

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Check if we should reraise certain exceptions
                if reraise_on and isinstance(e, reraise_on):
                    raise

                # Log the error with appropriate context
                if isinstance(e, AnkiVocabError):
                    logger.log(log_level, f"Application error in {op_name}: {e}")
                    if e.details:
                        logger.debug(f"Error details for {op_name}: {e.details}")
                else:
                    logger.log(
                        log_level, f"Unexpected error in {op_name}: {e}", exc_info=True
                    )

                return cast(T, default_return)

        return wrapper

    return decorator


class ErrorCollector:
    """Utility class for collecting and reporting multiple errors"""

    def __init__(self) -> None:
        self.errors: list[Exception] = []
        self.warnings: list[str] = []

    def add_error(self, error: Exception) -> None:
        """Add an error to the collection"""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the collection"""
        self.warnings.append(warning)

    def has_errors(self) -> bool:
        """Check if any errors were collected"""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were collected"""
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """Get a summary of all collected errors and warnings"""
        summary_parts = []

        if self.errors:
            summary_parts.append(f"{len(self.errors)} errors:")
            for i, error in enumerate(self.errors, 1):
                summary_parts.append(f"  {i}. {error}")

        if self.warnings:
            summary_parts.append(f"{len(self.warnings)} warnings:")
            for i, warning in enumerate(self.warnings, 1):
                summary_parts.append(f"  {i}. {warning}")

        return "\n".join(summary_parts) if summary_parts else "No errors or warnings"

    def log_all(self, logger: logging.Logger) -> None:
        """Log all collected errors and warnings"""
        for error in self.errors:
            if isinstance(error, AnkiVocabError):
                logger.error(f"Application error: {error}")
            else:
                logger.error(f"Unexpected error: {error}", exc_info=False)

        for warning in self.warnings:
            logger.warning(warning)

    def clear(self) -> None:
        """Clear all collected errors and warnings"""
        self.errors.clear()
        self.warnings.clear()


def safe_execute(
    func: Callable[P, R],
    default_return: R | None = None,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R | None:
    """
    Safely execute a function and return default value on error.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        default_return: Value to return on error
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Safe execution failed for {func.__name__}: {e}")
        return default_return


def validate_and_execute(
    func: Callable[P, R],
    validators: list[Callable[P, Any]] | None = None,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """
    Execute a function with pre-validation.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        validators: List of validation functions to run before execution
        **kwargs: Keyword arguments for the function

    Returns:
        Function result

    Raises:
        ValidationError: If any validator fails
    """
    # Run validators if provided
    if validators:
        for validator in validators:
            validator(*args, **kwargs)

    return func(*args, **kwargs)
