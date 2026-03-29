ByteTrack трекер — присваивает постоянный track_id объектам между кадрами.

Проблема без трекера:
    frame1: person detected (no id)
    frame2: person detected (no id) ← FSM думает новая цель
    frame3: person detected (no id) ← FSM думает новая цель

С ByteTrack:
    frame1: person → track_id=1
    frame2: person → track_id=1  ← та же цель
    frame3: person → track_id=1  ← та же цель

Pipeline:
    DetectionFrame → ByteTrack → List[DetectedObject] (с track_id)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.data_contracts import BoundingBox, DetectedObject, ObjectClass, PerceptionFrame
from ai.detector import DetectionFrame, RawDetection

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TRACK STATE
# ─────────────────────────────────────────────

class TrackState:
    TENTATIVE = "tentative"     # только появился — ещё не подтверждён
    CONFIRMED = "confirmed"     # подтверждён (n_hits >= min_hits)
    LOST = "lost"               # не видно — ищем
    DELETED = "deleted"         # удалён из трекера


@dataclass
class Track:
    """Один tracked объект."""
    track_id: int
    detection: RawDetection
    state: str = TrackState.TENTATIVE

    # счётчики
    n_hits: int = 1             # сколько раз подтверждён
    n_misses: int = 0           # сколько кадров не виден
    age: int = 1                # сколько кадров существует

    # история bbox для предсказания (упрощённый Kalman)
    bbox_history: List[BoundingBox] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)

    def predict(self) -> BoundingBox:
        """
        Предсказываем где будет объект в следующем кадре.
        Упрощение: линейная экстраполяция по последним 2 bbox.
        В полной реализации — Kalman filter.
        """
        if len(self.bbox_history) < 2:
            return self.detection.bbox

        prev = self.bbox_history[-2]
        curr = self.bbox_history[-1]

        dx1 = curr.x1 - prev.x1
        dy1 = curr.y1 - prev.y1
        dx2 = curr.x2 - prev.x2
        dy2 = curr.y2 - prev.y2

        return BoundingBox(
            x1=curr.x1 + dx1,
            y1=curr.y1 + dy1,
            x2=curr.x2 + dx2,
            y2=curr.y2 + dy2
        )

    def update(self, detection: RawDetection) -> None:
        """Обновляем трек новой детекцией."""
        self.detection = detection
        self.n_hits += 1
        self.n_misses = 0
        self.age += 1
        self.last_seen = time.time()
        self.bbox_history.append(detection.bbox)
        if len(self.bbox_history) > 10:
            self.bbox_history.pop(0)

    def mark_missed(self) -> None:
        """Объект не найден в этом кадре."""
        self.n_misses += 1
        self.age += 1

    @property
    def is_valid(self) -> bool:
        return self.state in (TrackState.CONFIRMED, TrackState.TENTATIVE)


# ─────────────────────────────────────────────
# IOU UTILS
# ─────────────────────────────────────────────

def compute_iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection over Union для двух bbox."""
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = a.area + b.area - intersection

    return intersection / max(union, 1e-6)


def iou_matrix(
    tracks: List[Track],
    detections: List[RawDetection]
) -> List[List[float]]:
    """IoU матрица tracks × detections."""
    matrix = []
    for track in tracks:
        predicted_bbox = track.predict()
        row = [compute_iou(predicted_bbox, det.bbox) for det in detections]
        matrix.append(row)
    return matrix


# ─────────────────────────────────────────────
# HUNGARIAN ASSIGNMENT (упрощённый greedy)
# ─────────────────────────────────────────────

def greedy_assignment(
    iou_mat: List[List[float]],
    threshold: float = 0.3
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """
    Жадное назначение tracks → detections по IoU.

    В полном ByteTrack используется Hungarian algorithm (scipy.linear_sum_assignment).
    Для MVP — жадный алгоритм достаточен при малом числе объектов (<20).

    Returns:
        matched: список (track_idx, det_idx)
        unmatched_tracks: треки без пары
        unmatched_dets: детекции без пары
    """
    if not iou_mat or not iou_mat[0]:
        return [], list(range(len(iou_mat))), []

    n_tracks = len(iou_mat)
    n_dets = len(iou_mat[0])

    matched = []
    used_tracks = set()
    used_dets = set()

    # собираем все пары (iou, track_idx, det_idx) и сортируем по убыванию IoU
    pairs = []
    for t_idx in range(n_tracks):
        for d_idx in range(n_dets):
            iou = iou_mat[t_idx][d_idx]
            if iou >= threshold:
                pairs.append((iou, t_idx, d_idx))

    pairs.sort(reverse=True)

    for iou, t_idx, d_idx in pairs:
        if t_idx in used_tracks or d_idx in used_dets:
            continue
        matched.append((t_idx, d_idx))
        used_tracks.add(t_idx)
        used_dets.add(d_idx)

    unmatched_tracks = [i for i in range(n_tracks) if i not in used_tracks]
    unmatched_dets = [i for i in range(n_dets) if i not in used_dets]

    return matched, unmatched_tracks, unmatched_dets


# ─────────────────────────────────────────────
# BYTE TRACKER
# ─────────────────────────────────────────────

class ByteTracker:
    """
    Упрощённый ByteTrack трекер.

    ByteTrack оригинал: https://github.com/ifzhang/ByteTrack
    Ключевая идея: используем ВСЕ детекции (не только high confidence)
    для matching, но подтверждаем только high confidence.

    Наша реализация: упрощённый вариант с IoU matching.
    Для production — использовать оригинальный ByteTrack через pip.
    """

    def __init__(
        self,
        min_hits: int = 3,              # кадров для подтверждения трека
        max_misses: int = 10,           # кадров потери до удаления
        iou_threshold: float = 0.3,     # минимальный IoU для matching
        min_confidence: float = 0.5,    # минимальная уверенность для нового трека
    ):
        self._min_hits = min_hits
        self._max_misses = max_misses
        self._iou_threshold = iou_threshold
        self._min_confidence = min_confidence

        self._tracks: Dict[int, Track] = {}
        self._next_id = 1
        self._frame_count = 0

        logger.info(
            f"[TRACKER] ByteTracker initialized "
            f"(min_hits={min_hits}, max_misses={max_misses})"
        )

    def update(self, detection_frame: DetectionFrame) -> PerceptionFrame:
        """
        Основной метод — обновляет треки новыми детекциями.

        Returns: PerceptionFrame с DetectedObject (с track_id)
        """
        self._frame_count += 1
        detections = detection_frame.detections

        active_tracks = [t for t in self._tracks.values() if t.is_valid]

        # ── MATCHING ──────────────────────────────────
        if active_tracks and detections:
            iou_mat = iou_matrix(active_tracks, detections)
            matched, unmatched_tracks, unmatched_dets = greedy_assignment(
                iou_mat, self._iou_threshold
            )
        else:
            matched = []
            unmatched_tracks = list(range(len(active_tracks)))
            unmatched_dets = list(range(len(detections)))

        # ── UPDATE MATCHED TRACKS ─────────────────────
        for t_idx, d_idx in matched:
            track = active_tracks[t_idx]
            track.update(detections[d_idx])
            if (track.state == TrackState.TENTATIVE
                    and track.n_hits >= self._min_hits):
                track.state = TrackState.CONFIRMED
                logger.debug(f"[TRACKER] Track {track.track_id} confirmed")

        # ── MARK MISSED TRACKS ────────────────────────
        for t_idx in unmatched_tracks:
            track = active_tracks[t_idx]
            track.mark_missed()

            if track.n_misses >= self._max_misses:
                track.state = TrackState.DELETED
                logger.debug(
                    f"[TRACKER] Track {track.track_id} deleted "
                    f"(missed {track.n_misses} frames)"
                )
            elif track.state == TrackState.CONFIRMED:
                track.state = TrackState.LOST
                logger.debug(f"[TRACKER] Track {track.track_id} lost")

        # ── CREATE NEW TRACKS ─────────────────────────
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            if det.confidence >= self._min_confidence:
                new_track = Track(
                    track_id=self._next_id,
                    detection=det,
                    bbox_history=[det.bbox]
                )
                self._tracks[self._next_id] = new_track
                logger.debug(
                    f"[TRACKER] New track {self._next_id}: "
                    f"{det.class_name} ({det.confidence:.2f})"
                )
                self._next_id += 1

        # ── CLEANUP DELETED ───────────────────────────
        self._tracks = {
            tid: t for tid, t in self._tracks.items()
            if t.state != TrackState.DELETED
        }

        # ── BUILD OUTPUT ──────────────────────────────
        return self._build_perception_frame(detection_frame)

    def _build_perception_frame(
        self,
        source_frame: DetectionFrame
    ) -> PerceptionFrame:
        """Конвертим треки в PerceptionFrame для WorldModel."""
        objects = []

        for track in self._tracks.values():
            if not track.is_valid:
                continue

            obj = DetectedObject(
                track_id=track.track_id,
                object_class=track.detection.object_class,
                confidence=track.detection.confidence,
                bbox=track.detection.bbox,
                world_position=None,    # заполнит WorldModel через SLAM fusion
                timestamp=track.last_seen
            )
            objects.append(obj)

        return PerceptionFrame(
            objects=objects,
            frame_id=source_frame.frame_id,
            timestamp=source_frame.timestamp
        )

    def get_diagnostics(self) -> dict:
        confirmed = sum(
            1 for t in self._tracks.values()
            if t.state == TrackState.CONFIRMED
        )
        tentative = sum(
            1 for t in self._tracks.values()
            if t.state == TrackState.TENTATIVE
        )
        lost = sum(
            1 for t in self._tracks.values()
            if t.state == TrackState.LOST
        )
        return {
            "frame_count": self._frame_count,
            "total_tracks": len(self._tracks),
            "confirmed": confirmed,
            "tentative": tentative,
            "lost": lost,
            "next_id": self._next_id,
        }
