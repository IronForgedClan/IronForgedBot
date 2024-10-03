import asyncio
import logging

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event_name, callback):
        """Subscribe to an event with a callback."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(callback)

    async def emit(self, event_name, *args, **kwargs):
        """Emit an event and call all listeners for that event."""
        if event_name in self.listeners:
            tasks = []
            for callback in self.listeners[event_name]:
                tasks.append(callback(*args, **kwargs))
            await asyncio.gather(*tasks)


event_emitter = EventEmitter()
