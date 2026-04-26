import asyncio
from typing import Callable, Awaitable, List

class MeshEventPublisher:
    """
    Observer Pattern: Subject class.
    Manages subscribers (WebSockets or Callbacks) and broadcasts mesh update events.
    """
    def __init__(self):
        self._subscribers: List[Callable[[str, dict], Awaitable[None]]] = []

    def subscribe(self, callback: Callable[[str, dict], Awaitable[None]]):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str, dict], Awaitable[None]]):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def notify_sync(self, event_name: str, payload: dict):
        """Broadcasts event from synchronous code using the active event loop."""
        try:
            loop = asyncio.get_running_loop()
            for callback in self._subscribers:
                loop.create_task(callback(event_name, payload))
        except RuntimeError:
            # If no running loop, just skip (e.g. during some unit tests)
            pass

# Global Singleton for Observer
mesh_events = MeshEventPublisher()

