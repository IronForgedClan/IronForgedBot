"""Discord-coupled logging decorators. Pure decorators live in ironforgedcore.common.logging_utils."""

import functools
import logging
import time
from typing import Callable, Optional


def log_command_execution(
    logger: Optional[logging.Logger] = None, interaction_position: int = 0
):
    """Decorator to log Discord command execution.

    Args:
        logger: Logger instance to use. If None, creates one from the function module.
        interaction_position: Position of the interaction parameter in the function signature (0-indexed).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import discord

            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()

            if len(args) > interaction_position:
                interaction = args[interaction_position]
                if isinstance(interaction, discord.Interaction):
                    user_info = f"{interaction.user} (ID: {interaction.user.id})"
                    actual_logger.info(
                        f"Command {func.__name__} started by {user_info}"
                    )
                else:
                    actual_logger.info(
                        f"Command {func.__name__} started (no interaction)"
                    )
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
        async def wrapper(self, interaction, *args, **kwargs):
            import discord

            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            start_time = time.time()
            if isinstance(interaction, discord.Interaction):
                user_info = f"{interaction.user} (ID: {interaction.user.id})"
            else:
                user_info = str(interaction)
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
    """Decorator to log task/job execution."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            actual_logger = (
                logger if logger is not None else logging.getLogger(func.__module__)
            )
            actual_logger.info(f"Task {func.__name__} started")

            try:
                result = await func(*args, **kwargs)
                actual_logger.info(f"Task {func.__name__} completed successfully")
                return result
            except Exception as e:
                actual_logger.error(f"Task {func.__name__} failed: {e}", exc_info=True)
                raise

        return wrapper

    return decorator
