import asyncio
import threading
from typing import Dict
from typing import Callable, Awaitable, List


class MeshEventPublisher:
    """
    Observer Pattern: Subject class.
    Manages subscribers (WebSockets or Callbacks) and broadcasts mesh update events.
    """
    def __init__(self):
        self._subscribers: List[Callable[[str, dict], Awaitable[None]]] = []
        self._subscriber_loops: Dict[Callable[[str, dict], Awaitable[None]], asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[str, dict], Awaitable[None]]):
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                self._subscriber_loops[callback] = loop

    def unsubscribe(self, callback: Callable[[str, dict], Awaitable[None]]):
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
            self._subscriber_loops.pop(callback, None)

    def notify_sync(self, event_name: str, payload: dict):
        """Broadcast events from sync contexts to each subscriber's event loop."""
        with self._lock:
            subscribers = list(self._subscribers)
            subscriber_loops = dict(self._subscriber_loops)

        for callback in subscribers:
            target_loop = subscriber_loops.get(callback)
            if target_loop is not None and target_loop.is_running():
                try:
                    target_loop.call_soon_threadsafe(
                        self._schedule_in_loop,
                        target_loop,
                        callback,
                        event_name,
                        payload,
                    )
                except RuntimeError:
                    # Stale loop, fallback to a new temporary loop.
                    self._run_in_background_loop(callback, event_name, payload)
                continue

            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(callback(event_name, payload))
            except RuntimeError:
                self._run_in_background_loop(callback, event_name, payload)

    @staticmethod
    def _schedule_in_loop(
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[str, dict], Awaitable[None]],
        event_name: str,
        payload: dict,
    ) -> None:
        loop.create_task(callback(event_name, payload))

    @staticmethod
    def _run_in_background_loop(
        callback: Callable[[str, dict], Awaitable[None]],
        event_name: str,
        payload: dict,
    ) -> None:
        def runner() -> None:
            asyncio.run(callback(event_name, payload))

        threading.Thread(target=runner, daemon=True).start()

# Global Singleton for Observer
mesh_events = MeshEventPublisher()
