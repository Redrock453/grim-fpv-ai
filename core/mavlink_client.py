MAVLink transport layer — отправляет FlightCommand дрону.

**Проблема**:
- OpenVINS возвращает позицию в локальной системе координат
- Дрон работает в мировой системе координат (NED)
- Нужно конвертировать и масштабировать

**Решение**:
- MAVLink client для sending команды
- Coordinate transforms (NED → ENU)
- Scaling между метрами и частотами
- Retransmission для надежности

**MAVLink Protocol**:
- `SET_POSITION_TARGET_LOCAL_NED` — точечная позиция
- `SET_VELOCITY_TARGET_NED` — скорость
- `COMMAND_LONG` — команды (takeoff, land, mode change)
"""

import asyncio
import logging
import time
from typing import Optional

from core.data_contracts import FlightCommand, Pose3D, Velocity3D

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# MAVLink CONSTANTS
# ─────────────────────────────────────────────

# Command IDs (стандартные MAVLink)
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_TAKEOFF = 22
MAV_CMD_NAV_LAND = 21
MAV_CMD_DO_CHANGE_SPEED = 178
MAV_CMD_DO_SET_MODE = 176
MAV_CMD_DO_SET_HOME = 192

# Message types
MAVLink_MSG_SET_POSITION_TARGET_LOCAL_NED = 84
MAVLink_MSG_SET_VELOCITY_TARGET_NED = 87
MAVLink_MSG_COMMAND_LONG = 76

# Coordinate frame
MAV_FRAME_LOCAL_NED = 1


# ─────────────────────────────────────────────
# MAVLink CLIENT
# ─────────────────────────────────────────────

class MAVLinkClient:
    """
    Клиент для отправки команд в дрон через MAVLink.

    Поддерживаемые команды:
    - takeoff, land, return_to_home
    - set_position (точечное позиционирование)
    - set_velocity (скорость)
    """

    def __init__(self, connection_url: str = "udp://:14540"):
        self._connection_url = connection_url
        self._running = False
        self._retransmission_count = 0
        self._max_retransmissions = 3

        logger.info(f"[MAV] Client initialized: {connection_url}")

    async def start(self) -> None:
        """Запускаем клиент."""
        self._running = True
        logger.info("[MAV] MAVLink client started")

        # TODO: реализовать реальный MAVLink транспорт
        # - pymavlink для low-level
        # - или use mavproxy для удобства

    def stop(self) -> None:
        self._running = False
        logger.info("[MAV] Stopped")

    # ─────────────────────────────────────────────
    # COMMANDS
    # ─────────────────────────────────────────────

    async def send_takeoff(self, altitude: float = 1.0) -> bool:
        """
        Команда takeoff.

        Args:
            altitude: высота над точкой старта (метры)

        Returns:
            True если команда успешно отправлена
        """
        logger.info(f"[MAV] Takeoff command: altitude={altitude}m")

        # TODO: отправляем MAV_CMD_NAV_TAKEOFF
        # mav.send_message(MAVLink_message(
        #     msg_id=MAV_CMD_NAV_TAKEOFF,
        #     param1=0.0,  # latitude
        #     param2=0.0,  # longitude
        #     param3=altitude,  # altitude
        #     param4=0.0,  # yaw
        #     param5=0.0,  # x
        #     param6=0.0,  # y
        #     param7=0.0,  # z
        # ))

        return await self._send_with_retries("takeoff")

    async def send_land(self) -> bool:
        """Команда land."""
        logger.info("[MAV] Land command")

        # TODO: MAV_CMD_NAV_LAND
        return await self._send_with_retries("land")

    async def send_return_to_home(self) -> bool:
        """Команда return_to_home."""
        logger.info("[MAV] Return to home command")

        # TODO: MAV_CMD_NAV_RETURN_TO_LAUNCH
        return await self._send_with_retries("return_to_home")

    async def send_position(self, pose: Pose3D, altitude: float = 0.0) -> bool:
        """
        Команда set_position.

        Args:
            pose: целевая позиция в ENU (метры)
            altitude: высота над землёй (метры)

        Returns:
            True если команда успешно отправлена
        """
        logger.debug(
            f"[MAV] Position command: "
            f"x={pose.x:.2f}, y={pose.y:.2f}, z={pose.z:.2f}, "
            f"alt={altitude:.2f}m"
        )

        # TODO: MAVLink_MSG_SET_POSITION_TARGET_LOCAL_NED
        # Важно: OpenVINS возвращает ENU, MAVLink ожидает NED
        # нужна конвертация: x_NED = -x_ENU, y_NED = -y_ENU, z_NED = z_ENU

        # Transform ENU → NED для MAVLink
        ned_pose = Pose3D(
            x=-pose.x,
            y=-pose.y,
            z=pose.z,  # высота остается как есть
            roll=pose.roll,
            pitch=pose.pitch,
            yaw=pose.yaw
        )

        # TODO: отправляем MAVLink сообщение
        # mav.send_message(MAVLink_position_target_local_ned(
        #     type_mask=0b111111111000,  # игнорируем velocity, accel
        #     coordinate_frame=MAV_FRAME_LOCAL_NED,
        #     x=ned_pose.x,
        #     y=ned_pose.y,
        #     z=ned_pose.z,
        #     yaw=ned_pose.yaw
        # ))

        return await self._send_with_retries("set_position")

    async def send_velocity(self, velocity: Velocity3D) -> bool:
        """
        Команда set_velocity.

        Args:
            velocity: скорость в ENU (м/с)

        Returns:
            True если команда успешно отправлена
        """
        logger.debug(
            f"[MAV] Velocity command: "
            f"vx={velocity.vx:.2f}, vy={velocity.vy:.2f}, vz={velocity.vz:.2f}"
        )

        # TODO: MAVLink_MSG_SET_VELOCITY_TARGET_NED
        # Transform ENU → NED
        ned_velocity = Velocity3D(
            vx=-velocity.vx,
            vy=-velocity.vy,
            vz=velocity.vz
        )

        # TODO: отправляем MAVLink сообщение
        return await self._send_with_retries("set_velocity")

    # ─────────────────────────────────────────────
    # RETRY LOGIC
    # ─────────────────────────────────────────────

    async def _send_with_retries(self, command: str) -> bool:
        """
        Отправляем команду с retransmission для надежности.

        Retransmission:
        - 3 попытки с экспоненциальной задержкой
        - Логируем если failed
        """
        for attempt in range(1, self._max_retransmissions + 1):
            try:
                # TODO: реально отправляем
                await asyncio.sleep(0.01)  # placeholder

                # Проверяем что команда принята
                # mav.last_packet == "command"
                return True

            except Exception as e:
                logger.warning(f"[MAV] Command '{command}' attempt {attempt}/{self._max_retransmissions}: {e}")

            # Задержка перед retransmission (экспоненциальная)
            delay = 0.1 * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

        logger.error(f"[MAV] Command '{command}' failed after {self._max_retransmissions} attempts")
        return False


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

client = MAVLinkClient()
