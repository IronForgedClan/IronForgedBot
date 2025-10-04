import asyncio
import logging
import time
import zlib
import pickle

from ironforgedbot.common.helpers import deep_getsizeof
from ironforgedbot.models.score import ScoreBreakdown


logger = logging.getLogger(__name__)


class ScoreCache:
    def __init__(self, ttl: int = 600):
        self.cache = {}
        self.ttl = ttl
        self.lock = asyncio.Lock()

    async def get(self, player_name: str) -> ScoreBreakdown | None:
        async with self.lock:
            if player_name in self.cache:
                data, expires = self.cache[player_name]
                if time.time() < expires:
                    return pickle.loads(zlib.decompress(data))
                else:
                    del self.cache[player_name]
            return None

    async def set(self, player_name: str, data: ScoreBreakdown) -> None:
        async with self.lock:
            compressed_data = zlib.compress(pickle.dumps(data))
            self.cache[player_name] = (compressed_data, time.time() + self.ttl)

    async def clean(self) -> str | None:
        async with self.lock:
            now = time.time()
            expired_entries = [
                k for k, (_, expires) in self.cache.items() if now >= expires
            ]
            if len(expired_entries) > 0:
                logger.debug(
                    f"Clearing {len(expired_entries)} expired item(s) from cache"
                )
                initial_size = deep_getsizeof(self.cache)

                for k in expired_entries:
                    del self.cache[k]

                cleaned_size = deep_getsizeof(self.cache)
                diff = initial_size - cleaned_size
                percent = (diff / initial_size * 100) if initial_size else 0

                return (
                    f"Deleted **{diff / 2024:.2f} KB** of expired data. "
                    f"Reduced cache size by **~{percent:.2f}%**. Cache entries: "
                    f"**{len(self.cache)}**. Cache size: "
                    f"**{cleaned_size / 2024:.2f} KB**."
                )
            return None


SCORE_CACHE = ScoreCache(600)
