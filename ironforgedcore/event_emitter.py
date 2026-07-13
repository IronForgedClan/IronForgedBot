import asyncio
import logging

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event_name, callback, priority=0):
        """Subscribe to a given event with a callback and priority."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []

        self.listeners[event_name].append((callback, priority))

    async def emit(self, event_name, *args, **kwargs):
        """Emit an event and call all listeners for that event, sorted by priority."""
        if event_name in self.listeners:
            sorted_listeners = sorted(
                self.listeners[event_name], key=lambda x: x[1], reverse=True
            )
            for callback, _ in sorted_listeners:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)

    def remove_listener(self, event_name, callback):
        """Remove a specific listener from an event."""
        if event_name in self.listeners:
            self.listeners[event_name] = [
                (cb, prio) for cb, prio in self.listeners[event_name] if cb != callback
            ]


event_emitter = EventEmitter()
