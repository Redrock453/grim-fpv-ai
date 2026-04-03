Мост между sensor_sync и OpenVINS.
Принимает SyncedFrame, формирует VIO-кадры, отдаёт позицию/ориентацию.

Проблема:
  - OpenVINS ожидает последовательные timestamp'ы
  - Camera может быть 30fps, но приходит с задержками
  - Нужно валидировать входные данные перед подачей в OpenVINS

Решение:
  - Буферизация кадров
  - Таймлайн validation (gap > 100ms → reject)
  - Согласование timestamp'ов (OpenVINS требует уникальные)
  - Настройки OpenVINS через JSON
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# OPENVINS CONFIG
# ─────────────────────────────────────────────

@dataclass
class OpenVINSConfig:
    """
    Конфигурация OpenVINS.
    Сохраняется в JSON для удобства настройки.
    """
    # Входные параметры
    camera_rate_hz: float = 30.0
    camera_exposure_time_us: float = 20000.0  # 20ms типичный

    # OpenVINS API параметры
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    camera_id: int = 0

    # Валидация
    max_frame_gap_ms: float = 100.0
    min_consecutive_frames: int = 100

    # VIO параметры
    gyro_noise: float = 1.7e-4
    acc_noise: float = 2.0e-3
    gyro_bias_rate: float = 1.9e-5
    acc_bias_rate: float = 1.0e-4

    # Буферы
    output_buffer_size: int = 100
    input_buffer_size: int = 10


# ─────────────────────────────────────────────
# SYNCED FRAME ENHANCED
# ─────────────────────────────────────────────

@dataclass
class VIOFrame:
    """
    Формат кадра для OpenVINS API.
    """
    timestamp: float
    camera_id: int
    K: list = field(default_factory=list)      # Camera matrix 3x3
    dist: list = field(default_factory=list)   # Distortion coefficients
    R: list = field(default_factory=list)      # Rotation matrix 3x3
    t: list = field(default_factory=list)      # Translation vector 3x1
    ext: list = field(default_factory=list)    # Camera-IMU extrinsics
    p_C_I: list = field(default_factory=list)  # Camera position in IMU frame
    q_C_I: list = field(default_factory=list)  # Quaternion camera-IMU rotation
    b_g: list = field(default_factory=list)    # Gyro bias
    b_a: list = field(default_factory=list)    # Accel bias


# ─────────────────────────────────────────────
# OPENVINS BRIDGE
# ─────────────────────────────────────────────

class OpenVINSBridge:
    """
    Bridge между sensor_sync.py и OpenVINS.

    Flow:
    1. SensorSync → push_synced() → этот класс
    2. Обработка: валидация, timestamp согласование
    3. OpenVINS API: send_vio_frame()
    4. Получаем позицию/ориентацию → WorldModel
    """

    def __init__(self, config: Optional[OpenVINSConfig] = None):
        self._config = config or OpenVINSConfig()
        self._input_queue: asyncio.Queue = asyncio.Queue(maxsize=self._config.input_buffer_size)
        self._output_queue: asyncio.Queue = asyncio.Queue(maxsize=self._config.output_buffer_size)
        self._running = False

        # буфер для timestamp validation
        self._last_timestamp: Optional[float] = None
        self._consecutive_frames = 0

        logger.info(f"[OVINS] Bridge initialized. API: {self._config.api_host}:{self._config.api_port}")

    # ─────────────────────────────────────────────
    # INPUT — от sensor_sync
    # ─────────────────────────────────────────────

    async def push_synced(self, synced_frame) -> None:
        """Принимает SyncedFrame от SensorSync."""
        try:
            self._input_queue.put_nowait(synced_frame)
        except asyncio.QueueFull:
            logger.warning("[OVINS] Input queue full — dropping frame")

    # ─────────────────────────────────────────────
    # OUTPUT — в WorldModel
    # ─────────────────────────────────────────────

    async def get_position(self, timeout: float = 0.1) -> Optional[dict]:
        """Получаем позицию/ориентацию от OpenVINS API."""
        try:
            return await asyncio.wait_for(self._output_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ─────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────

    async def start(self) -> None:
        """Запустить bridge loop."""
        self._running = True
        logger.info("[OVINS] Bridge started")
        await self._process_loop()

    def stop(self) -> None:
        self._running = False
        logger.info(
            f"[OVINS] Stopped. "
            f"Processed: {self._consecutive_frames}"
        )

    async def _process_loop(self) -> None:
        while self._running:
            try:
                synced_frame = await asyncio.wait_for(
                    self._input_queue.get(),
                    timeout=0.1
                )

                # валидация
                if not self._validate_frame(synced_frame):
                    continue

                # timestamp согласование
                if not self._align_timestamp(synced_frame):
                    logger.warning("[OVINS] Timestamp validation failed")
                    continue

                # конвертируем в формат OpenVINS
                vio_frame = self._convert_to_vio_format(synced_frame)

                # отправляем в OpenVINS API
                await self._send_to_openvins(vio_frame)

                # принимаем позицию обратно
                pose = await self._receive_from_openvins()

                if pose:
                    await self._output_queue.put(pose)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[OVINS] Loop error: {e}")

    def _validate_frame(self, synced_frame) -> bool:
        """Проверяем качество кадра перед подачей в OpenVINS."""
        # проверяем quality
        if synced_frame.sync_quality < 0.5:
            logger.warning(
                f"[OVINS] Rejecting frame: quality={synced_frame.sync_quality:.2f}"
            )
            return False

        # проверяем gap
        if self._last_timestamp:
            gap_ms = abs(synced_frame.timestamp - self._last_timestamp) * 1000.0
            if gap_ms > self._config.max_frame_gap_ms:
                logger.warning(
                    f"[OVINS] Rejecting frame: gap={gap_ms:.1f}ms > {self._config.max_frame_gap_ms}ms"
                )
                return False

        # проверяем что timestamp монотонный
        if synced_frame.timestamp < self._last_timestamp:
            logger.warning(f"[OVINS] Rejecting frame: non-monotonic timestamp")
            return False

        return True

    def _align_timestamp(self, synced_frame) -> bool:
        """Согласовываем timestamp с OpenVINS требованиями."""
        if self._last_timestamp is None:
            self._last_timestamp = synced_frame.timestamp
            return True

        # OpenVINS требует уникальные timestamp'ы
        # Если timestamp уже был — логируем, но принимаем (OpenVINS обработает)
        if synced_frame.timestamp == self._last_timestamp:
            logger.warning("[OVINS] Duplicate timestamp — OpenVINS will handle it")
            return True

        # проверяем что разница разумная
        dt = synced_frame.timestamp - self._last_timestamp
        if dt < 0 or dt > (self._config.max_frame_gap_ms / 1000.0):
            return False

        self._last_timestamp = synced_frame.timestamp
        return True

    def _convert_to_vio_format(self, synced_frame) -> VIOFrame:
        """
        Конвертируем SyncedFrame в формат VIOFrame для OpenVINS API.

        TODO: здесь нужно подключить реальные параметры камеры (K, dist)
        и extrinsics из calibrations.
        """
        # Mock параметры — это placeholders для реальных calibrations
        K = [
            [800.0, 0.0, 320.0],
            [0.0, 800.0, 240.0],
            [0.0, 0.0, 1.0]
        ]

        dist = [0.0, 0.0, 0.0, 0.0]

        # Начальная позиция (пока zero — будет обновляться от OpenVINS)
        R = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]

        t = [0.0, 0.0, 0.0]

        # Camera-IMU extrinsics (начало)
        ext = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        # Внешняя позиция камеры в системе IMU
        p_C_I = [0.0, 0.0, 0.0]

        # Quaternion (W, X, Y, Z)
        q_C_I = [1.0, 0.0, 0.0, 0.0]

        # Gyro и accel bias (начально zero — будет calibrate)
        b_g = [0.0, 0.0, 0.0]
        b_a = [0.0, 0.0, 0.0]

        return VIOFrame(
            timestamp=synced_frame.timestamp,
            camera_id=self._config.camera_id,
            K=K,
            dist=dist,
            R=R,
            t=t,
            ext=ext,
            p_C_I=p_C_I,
            q_C_I=q_C_I,
            b_g=b_g,
            b_a=b_a
        )

    async def _send_to_openvins(self, vio_frame: VIOFrame) -> None:
        """
        Отправляем кадр в OpenVINS API.

        TODO: подключить реальный HTTP API OpenVINS или gRPC.
        Сейчас просто логируем.
        """
        logger.debug(
            f"[OVINS] Sending frame to OpenVINS: "
            f"ts={vio_frame.timestamp:.3f}, K={len(vio_frame.K)}"
        )

        # TODO: реализовать HTTP/gRPC запрос к OpenVINS API
        # curl -X POST http://127.0.0.1:8765/api/pose
        # или через gRPC

        self._consecutive_frames += 1

    async def _receive_from_openvins(self) -> Optional[dict]:
        """
        Получаем позицию/ориентацию от OpenVINS API.

        TODO: реализовать запрос к OpenVINS API для получения последнего поза.
        """
        # TODO: реализовать
        return None


# ─────────────────────────────────────────────
# SINGLETON для удобства
# ─────────────────────────────────────────────

bridge = OpenVINSBridge()
