"""Common logging utilities and decorators."""

import functools
import logging
import time
from typing import Callable, Any, Optional

import discord


def log_command_execution(logger: Optional[logging.Logger] = None, interaction_position: int = 0):
    """Decorator to log Discord command execution.

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
        interaction_position: Position of the interaction parameter in the function signature (0-indexed).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            
            # Get interaction from the specified position
            if len(args) > interaction_position:
                interaction = args[interaction_position]
                if isinstance(interaction, discord.Interaction):
                    user_info = f"{interaction.user} (ID: {interaction.user.id})"
                    actual_logger.info(f"Command {func.__name__} started by {user_info}")
                else:
                    actual_logger.info(f"Command {func.__name__} started (no interaction)")
            else:
                actual_logger.info(f"Command {func.__name__} started (no interaction)")

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                actual_logger.info(
                    f"Command {func.__name__} completed successfully in {elapsed:.2f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                actual_logger.error(
                    f"Command {func.__name__} failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_method_execution(logger: Optional[logging.Logger] = None):
    """Decorator to log Discord method execution (e.g., modal on_submit, view callbacks).

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            user_info = f"{interaction.user} (ID: {interaction.user.id})"

            actual_logger.info(f"Method {func.__name__} started by {user_info}")

            try:
                result = await func(self, interaction, *args, **kwargs)
                elapsed = time.time() - start_time
                actual_logger.info(
                    f"Method {func.__name__} completed successfully in {elapsed:.2f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                actual_logger.error(
                    f"Method {func.__name__} failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_task_execution(logger: Optional[logging.Logger] = None):
    """Decorator to log task/job execution.

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            actual_logger.info(f"Task {func.__name__} started")

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                actual_logger.info(
                    f"Task {func.__name__} completed successfully in {elapsed:.2f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                actual_logger.error(
                    f"Task {func.__name__} failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_database_operation(logger: Optional[logging.Logger] = None):
    """Decorator to log database operations.

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            actual_logger.debug(f"Database operation {func.__name__} started")

            try:
                result = await func(*args, **kwargs)
                actual_logger.debug(f"Database operation {func.__name__} completed")
                return result
            except Exception as e:
                actual_logger.error(
                    f"Database operation {func.__name__} failed: {e}", exc_info=True
                )
                raise

        return wrapper

    return decorator


def log_service_execution(logger: Optional[logging.Logger] = None):
    """Decorator to log service method execution.

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            actual_logger.debug(f"Service method {func.__name__} started")

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                actual_logger.debug(
                    f"Service method {func.__name__} completed in {elapsed:.2f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                actual_logger.error(
                    f"Service method {func.__name__} failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_api_call(service_name: str, logger: Optional[logging.Logger] = None):
    """Decorator to log external API calls.

    Args:
        service_name: Name of the external service being called
        logger: Logger instance to use. If None, creates one from the function module.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger inside wrapper to avoid None issues
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            actual_logger.debug(
                f"API call to {service_name} via {func.__name__} started"
            )

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                actual_logger.debug(
                    f"API call to {service_name} completed in {elapsed:.2f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                actual_logger.error(
                    f"API call to {service_name} failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


class LogContext:
    """Context manager for structured logging with context."""

    def __init__(self, logger: logging.Logger, operation: str, **context):
        """Initialize log context.

        Args:
            logger: Logger instance to use
            operation: Name of the operation being performed
            **context: Additional context to include in logs
        """
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[float] = None

    def __enter__(self):
        """Enter the context."""
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation}", extra={"context": self.context})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
        else:
            elapsed = 0.0

        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation} in {elapsed:.2f}s",
                extra={"context": self.context},
            )
        else:
            self.logger.error(
                f"Failed {self.operation} after {elapsed:.2f}s: {exc_val}",
                extra={"context": self.context},
                exc_info=(exc_type, exc_val, exc_tb),
            )
        return False  # Don't suppress exceptions
