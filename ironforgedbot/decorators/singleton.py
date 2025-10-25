import asyncio


def singleton(cls):
    """A threadsafe singleton implementation"""
    instances = {}
    lock = asyncio.Lock()

    async def get_instance(*args, **kwargs):
        async with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
            return instances[cls]

    async def async_new(*args, **kwargs):
        return await get_instance(*args, **kwargs)

    class Wrapper:
        def __new__(cls, *args, **kwargs):
            return async_new(*args, **kwargs)

    return Wrapper
