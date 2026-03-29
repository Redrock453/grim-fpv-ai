YOLOv8 детектор объектов.
Запускается в отдельном процессе — обход GIL (тяжёлый инференс).
Поддерживает TensorRT (Jetson) и NCNN (Raspberry) через ultralytics backends.

Pipeline:
    Camera frame → YOLOv8 → raw detections → tracker.py
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from multiprocessing import Process, Queue as MPQueue
from typing import List, Optional

from core.data_contracts import BoundingBox, ObjectClass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

@dataclass
class DetectorConfig:
    model_path: str = "yolov8n.pt"          # n=nano, s=small, m=medium
    confidence_threshold: float = 0.5        # предфильтр (финальный порог 0.7 в FSM)
    iou_threshold: float = 0.45             # NMS порог
    input_size: int = 640                   # пиксели (640 стандарт)
    device: str = "auto"                    # "cpu", "cuda", "tensorrt", "ncnn"
    max_detections: int = 20               # лимит объектов за кадр
    target_classes: List[str] = field(default_factory=lambda: [
        "person", "car", "truck", "bus",    # цели
        "tree", "wall", "building"           # препятствия (если есть в модели)
    ])


# ─────────────────────────────────────────────
# RAW DETECTION (до трекера)
# ─────────────────────────────────────────────

@dataclass
class RawDetection:
    """Сырая детекция из YOLO — без track_id (добавит ByteTrack)."""
    class_name: str
    confidence: float
    bbox: BoundingBox
    timestamp: float = field(default_factory=time.time)

    @property
    def object_class(self) -> ObjectClass:
        mapping = {
            "person": ObjectClass.PERSON,
            "car": ObjectClass.VEHICLE,
            "truck": ObjectClass.VEHICLE,
            "bus": ObjectClass.VEHICLE,
            "tree": ObjectClass.OBSTACLE,
            "wall": ObjectClass.OBSTACLE,
            "building": ObjectClass.OBSTACLE,
        }
        return mapping.get(self.class_name, ObjectClass.UNKNOWN)


@dataclass
class DetectionFrame:
    detections: List[RawDetection]
    frame_id: int
    inference_ms: float         # время инференса в мс
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────
# YOLO WORKER PROCESS
# ─────────────────────────────────────────────

def _detector_worker(
    input_queue: MPQueue,
    output_queue: MPQueue,
    config: DetectorConfig
) -> None:
    """
    YOLOv8 в отдельном процессе.
    Ultralytics поддерживает TensorRT и NCNN через export.

    Для Jetson Orin: конвертируем модель один раз:
        yolo export model=yolov8n.pt format=engine device=0
    Для Raspberry + Hailo: format=ncnn
    """
    import logging
    import time
    logger = logging.getLogger("detector_worker")

    # определяем device
    device = _resolve_device(config.device)
    logger.info(f"[YOLO] Loading {config.model_path} on {device}")

    try:
        from ultralytics import YOLO
        model = YOLO(config.model_path)
        logger.info(f"[YOLO] Model loaded. Classes: {len(model.names)}")
    except ImportError:
        logger.warning("[YOLO] ultralytics not installed — running in stub mode")
        model = None
    except Exception as e:
        logger.error(f"[YOLO] Model load error: {e}")
        model = None

    frame_id = 0

    while True:
        try:
            frame_data = input_queue.get(timeout=1.0)
        except Exception:
            continue

        frame_id += 1
        t_start = time.time()

        if model is None:
            # заглушка для разработки без GPU
            detections = _stub_detections(frame_data, config)
        else:
            detections = _run_inference(model, frame_data, config, device)

        inference_ms = (time.time() - t_start) * 1000.0

        result = DetectionFrame(
            detections=detections,
            frame_id=frame_id,
            inference_ms=inference_ms,
            timestamp=time.time()
        )

        if inference_ms > 100:
            logger.warning(f"[YOLO] Slow inference: {inference_ms:.1f}ms")

        try:
            output_queue.put_nowait(result)
        except Exception:
            pass  # трекер не успевает — пропускаем кадр


def _resolve_device(device: str) -> str:
    """Определяем доступное железо."""
    if device != "auto":
        return device
    try:
        import torch
        if torch.cuda.is_available():
            # проверяем TensorRT
            try:
                import tensorrt  # noqa
                return "cuda"  # ultralytics сам выберет TensorRT если .engine файл
            except ImportError:
                return "cuda"
    except ImportError:
        pass
    return "cpu"


def _run_inference(
    model,
    frame_data: dict,
    config: DetectorConfig,
    device: str
) -> List[RawDetection]:
    """Реальный инференс через ultralytics."""
    import numpy as np

    frame = frame_data.get("frame")  # numpy array HxWx3
    if frame is None:
        return []

    try:
        results = model(
            frame,
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
            max_det=config.max_detections,
            device=device,
            verbose=False
        )
    except Exception as e:
        logger.error(f"[YOLO] Inference error: {e}")
        return []

    detections = []
    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names.get(cls_id, "unknown")

            # фильтруем только нужные классы
            if cls_name not in config.target_classes:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append(RawDetection(
                class_name=cls_name,
                confidence=conf,
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
            ))

    return detections


def _stub_detections(
    frame_data: dict,
    config: DetectorConfig
) -> List[RawDetection]:
    """
    Заглушка для разработки без GPU/камеры.
    Генерирует реалистичные детекции для тестирования FSM.
    """
    import random
    import math

    t = time.time()
    detections = []

    # симулируем человека который появляется и двигается
    if math.sin(t * 0.3) > 0:
        detections.append(RawDetection(
            class_name="person",
            confidence=0.75 + 0.2 * abs(math.sin(t)),
            bbox=BoundingBox(
                x1=280 + 50 * math.sin(t * 0.5),
                y1=200,
                x2=380 + 50 * math.sin(t * 0.5),
                y2=400
            )
        ))

    # иногда появляется препятствие
    if random.random() < 0.05:
        detections.append(RawDetection(
            class_name="tree",
            confidence=0.85,
            bbox=BoundingBox(x1=100, y1=150, x2=200, y2=350)
        ))

    return detections


# ─────────────────────────────────────────────
# DETECTOR (async wrapper)
# ─────────────────────────────────────────────

class Detector:
    """
    Async wrapper над YOLO worker process.
    Принимает numpy frames, отдаёт DetectionFrame.
    """

    def __init__(self, config: Optional[DetectorConfig] = None):
        self._config = config or DetectorConfig()
        self._input_queue: MPQueue = MPQueue(maxsize=3)   # малый буфер — свежесть важнее
        self._output_queue: MPQueue = MPQueue(maxsize=5)
        self._worker: Optional[Process] = None
        self._running = False

        # статистика
        self._frames_in = 0
        self._frames_out = 0
        self._total_inference_ms = 0.0

    def start(self) -> None:
        self._worker = Process(
            target=_detector_worker,
            args=(self._input_queue, self._output_queue, self._config),
            daemon=True,
            name="yolo_worker"
        )
        self._worker.start()
        self._running = True
        logger.info(f"[DETECTOR] Started (PID: {self._worker.pid})")

    def stop(self) -> None:
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.terminate()
            self._worker.join(timeout=2.0)
        logger.info(
            f"[DETECTOR] Stopped. "
            f"In: {self._frames_in}, Out: {self._frames_out}, "
            f"Avg inference: {self._avg_inference_ms:.1f}ms"
        )

    async def push_frame(self, frame, frame_id: int = 0) -> None:
        """Отправить кадр на детекцию (non-blocking)."""
        try:
            self._input_queue.put_nowait({
                "frame": frame,
                "frame_id": frame_id,
                "timestamp": time.time()
            })
            self._frames_in += 1
        except Exception:
            pass  # детектор занят — пропускаем кадр (свежесть важнее полноты)

    async def get_detections(self, timeout: float = 0.05) -> Optional[DetectionFrame]:
        """Получить результат детекции (async)."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._output_queue.get(timeout=timeout)
            )
            self._frames_out += 1
            self._total_inference_ms += result.inference_ms
            return result
        except Exception:
            return None

    @property
    def _avg_inference_ms(self) -> float:
        if self._frames_out == 0:
            return 0.0
        return self._total_inference_ms / self._frames_out

    def get_diagnostics(self) -> dict:
        return {
            "worker_alive": self._worker.is_alive() if self._worker else False,
            "frames_in": self._frames_in,
            "frames_out": self._frames_out,
            "avg_inference_ms": self._avg_inference_ms,
            "drop_rate_pct": (
                100.0 * (1.0 - self._frames_out / max(1, self._frames_in))
            ),
            "model": self._config.model_path,
            "device": self._config.device,
            "confidence_threshold": self._config.confidence_threshold,
        }
