import asyncio
import time


class ScoreCache:
    def __init__(self, ttl: int = 600):
        self.cache = {}
        self.ttl = ttl
        self.lock = asyncio.Lock()

    async def get(self, player_name: str):
        async with self.lock:
            if player_name in self.cache:
                data, expires = self.cache[player_name]
                if time.time() < expires:
                    return data
                else:
                    del self.cache[player_name]
            return None

    async def set(self, player_name: str, data) -> None:
        async with self.lock:
            self.cache[player_name] = (data, time.time() + self.ttl)
