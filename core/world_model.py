Вершина пирамиды — объединяет SLAM, Perception и команды полёта в единое состояние.

Flow:
  OpenVINSBridge → WorldModel.slam
  Perception → WorldModel.perception
  HFSM → FlightCommand → WorldModel (через event_bus)

**Критично**: это единственное место где все данные изолированы от друг друга.
Остальные модули знают только про data_contracts.
"""

import asyncio
import logging
import time
from typing import Optional
from dataclasses import dataclass, field

from core.data_contracts import (
    WorldModel, FlightMode, SafetyMode, FlightCommand,
    Pose3D, SystemEvent, ObjectClass
)
from slam.openvins_bridge import OpenVINSBridge

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# WORLD MODEL MANAGER
# ─────────────────────────────────────────────

class WorldModelManager:
    """
    Управляет WorldModel и связывает все компоненты.

    Lifecycle:
    1. Инициализация
    2. Запуск SLAM (OpenVINSBridge)
    3. Запуск Perception
    4. Запуск HFSM
    5. Объединение всех в единый WorldModel
    """

    def __init__(self, config: Optional[dict] = None):
        self._config = config or {}
        self._world_model: Optional[WorldModel] = None
        self._openvins_bridge: Optional[OpenVINSBridge] = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        logger.info("[WM] WorldModelManager initialized")

    def get_world_model(self) -> WorldModel:
        """Получаем текущий WorldModel (thread-safe?)."""
        return self._world_model or WorldModel()

    # ─────────────────────────────────────────────
    # COMPONENTS SETUP
    # ─────────────────────────────────────────────

    def setup_openvins(self):
        """Инициализируем OpenVINS bridge."""
        self._openvins_bridge = OpenVINSBridge()
        logger.info("[WM] OpenVINS bridge configured")

    # ─────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────

    async def start(self) -> None:
        """Запускаем главный цикл объединения данных."""
        self._running = True
        logger.info("[WM] Starting main loop")

        # инициализируем WorldModel
        self._world_model = WorldModel()

        # запускаем OpenVINS bridge в фоне
        if self._openvins_bridge:
            await self._openvins_bridge.start()

        # главный цикл — обновляем WorldModel
        self._loop_task = asyncio.create_task(self._update_loop())

    def stop(self) -> None:
        """Останавливаем менеджер."""
        self._running = False

        if self._loop_task:
            self._loop_task.cancel()

        if self._openvins_bridge:
            self._openvins_bridge.stop()

        logger.info("[WM] Stopped")

    async def _update_loop(self) -> None:
        """
        Главный цикл — собирает данные из всех источников.

        В реальности это может быть:
        - Быстрая очередь (10Hz) — для перцепции
        - Медленная очередь (1Hz) — для SLAM
        """
        while self._running:
            try:
                await self._sync_from_openvins()
                await self._sync_perception()  # TODO: когда perception готов
                await self._sync_commands()    # TODO: когда HFSM готов
                await asyncio.sleep(0.1)  # 10Hz

            except Exception as e:
                logger.error(f"[WM] Update loop error: {e}")

    async def _sync_from_openvins(self) -> None:
        """Синхронизируем SLAM позицию от OpenVINS."""
        if not self._openvins_bridge or not self._world_model:
            return

        pose = await self._openvins_bridge.get_position()

        if pose:
            # TODO: конвертируем pose из OpenVINS в Pose3D
            # Сейчас просто логируем
            logger.debug(
                f"[WM] SLAM pose: "
                f"x={pose.get('x', 0):.3f}, "
                f"y={pose.get('y', 0):.3f}, "
                f"z={pose.get('z', 0):.3f}"
            )

            # TODO: обновляем self._world_model.slam.pose
            # self._world_model.slam.pose = Pose3D(...)
        else:
            # OpenVINS ещё не выдал позицию
            logger.debug("[WM] SLAM position not ready yet")

    async def _sync_perception(self) -> None:
        """
        Синхронизируем перцепцию.

        TODO: когда perception готов, здесь будет:
        - await perception.get_frame()
        - world_model.perception = perception_frame
        """
        pass

    async def _sync_commands(self) -> None:
        """
        Синхронизируем команды полёта.

        TODO: когда HFSM готов, здесь будет:
        - command = await hfsm.get_command()
        - world_model.command = command
        """
        pass


# ─────────────────────────────────────────────
# SINGLETON для удобства
# ─────────────────────────────────────────────

manager = WorldModelManager()
