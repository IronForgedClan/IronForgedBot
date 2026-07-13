import asyncio
import functools
import logging

logger = logging.getLogger(__name__)


def retry_on_exception(retries=3):
    """Retries function upon any exception up to retry limit"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            sleep_time = 1
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < retries - 1:
                        logger.warning(
                            f"Fail #{attempt + 1} for {func.__name__}, "
                            f"retrying after {sleep_time}s sleep..."
                        )
                        await asyncio.sleep(sleep_time)
                        sleep_time *= 2
                    else:
                        logger.critical(e)
                        raise e

        return wrapper

    return decorator
