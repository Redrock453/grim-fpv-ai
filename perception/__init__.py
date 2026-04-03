Perception module — объектное распознавание и отслеживание.

Состоит из:
- `yolo_detector.py` — YOLO модель для детекции
- `byte_track.py` — ByteTrack для отслеживания

Flow:
  Camera → YOLO → DetectedObject (с track_id)
  → ByteTrack → Треки объектов
  → PerceptionFrame → WorldModel
"""

from core.data_contracts import DetectedObject, PerceptionFrame, ObjectClass
from .yolo_detector import YOLODetector
from .byte_track import ByteTracker

__all__ = [
    "DetectedObject",
    "PerceptionFrame",
    "ObjectClass",
    "YOLODetector",
    "ByteTracker",
]
