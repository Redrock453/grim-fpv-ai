Внутренний event bus на asyncio.Queue.
Модули не знают друг о друге — только о событиях.
"""

import asyncio
import logging
from typing import Callable, Dict, List
from core.data_contracts import SystemEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    Pub/Sub на asyncio.Queue.
    Старт простой — без Redis/NATS, но API совместимо для замены.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._running = False

    def subscribe(self, event_type: str, handler: Callable):
        """Подписаться на тип события."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"[BUS] {handler.__qualname__} subscribed to '{event_type}'")

    async def publish(self, event: SystemEvent):
        """Опубликовать событие (non-blocking)."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"[BUS] Queue full — dropping event '{event.event_type}'")

    async def start(self):
        """Запустить dispatch loop."""
        self._running = True
        logger.info("[BUS] Started")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[BUS] Dispatch error: {e}")

    async def _dispatch(self, event: SystemEvent):
        handlers = self._subscribers.get(event.event_type, [])
        handlers += self._subscribers.get("*", [])  # wildcard подписчики
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[BUS] Handler {handler.__qualname__} error: {e}")

    def stop(self):
        self._running = False
        logger.info("[BUS] Stopped")


# Singleton для удобства импорта
bus = EventBus()
