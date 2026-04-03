Data contracts — всё что летает между модулями.
Единый источник правды для типов данных.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple
import time


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class FlightMode(Enum):
    IDLE            = auto()
    SEARCH          = auto()
    SEARCH_LAST_KNOWN = auto()  # GPT: не сбрасываться в IDLE если цель пропала
    TRACK           = auto()
    PATROL          = auto()
    RETURN          = auto()
    LOITER          = auto()


class SafetyMode(Enum):
    NOMINAL         = auto()
    AVOID           = auto()    # GLM: Interrupt, не стейт — прерывает Navigation
    EMERGENCY_LAND  = auto()
    MANUAL_OVERRIDE = auto()


class SystemHealth(Enum):
    OK              = auto()
    DEGRADED        = auto()
    CRITICAL        = auto()


class ObjectClass(Enum):
    PERSON          = "person"
    VEHICLE         = "vehicle"
    OBSTACLE        = "obstacle"
    LANDING_ZONE    = "landing_zone"
    UNKNOWN         = "unknown"


# ─────────────────────────────────────────────
# SLAM / POSITION
# ─────────────────────────────────────────────

@dataclass
class Pose3D:
    """Позиция и ориентация в локальной системе координат (SLAM)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0     # 0.0 — SLAM потерян, 1.0 — надёжно


@dataclass
class Velocity3D:
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SlamState:
    pose: Pose3D = field(default_factory=Pose3D)
    velocity: Velocity3D = field(default_factory=Velocity3D)
    is_tracking: bool = False
    drift_estimate: float = 0.0     # метры — насколько карта "уплыла"
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────
# PERCEPTION
# ─────────────────────────────────────────────

@dataclass
class BoundingBox:
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    @property
    def area(self) -> float:
        """GLM: площадь бокса в пикселях — прокси для дистанции до объекта."""
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class DetectedObject:
    track_id: int                           # ByteTrack ID — постоянный между кадрами
    object_class: ObjectClass = ObjectClass.UNKNOWN
    confidence: float = 0.0                 # порог >0.7 для перехода стейтов
    bbox: BoundingBox = field(default_factory=BoundingBox)
    world_position: Optional[Pose3D] = None # позиция в системе координат SLAM
    timestamp: float = field(default_factory=time.time)

    @property
    def is_obstacle(self) -> bool:
        """Препятствие всегда приоритетнее цели."""
        return self.object_class == ObjectClass.OBSTACLE

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class PerceptionFrame:
    objects: List[DetectedObject] = field(default_factory=list)
    frame_id: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def obstacles(self) -> List[DetectedObject]:
        return [o for o in self.objects if o.is_obstacle and o.is_reliable]

    @property
    def targets(self) -> List[DetectedObject]:
        return [o for o in self.objects if not o.is_obstacle and o.is_reliable]


# ─────────────────────────────────────────────
# WORLD MODEL
# ─────────────────────────────────────────────

@dataclass
class WorldModel:
    """
    Единая система координат — фундамент всей системы.
    SLAM pose + tracked objects + obstacle map в одном месте.
    """
    slam: SlamState = field(default_factory=SlamState)
    perception: PerceptionFrame = field(default_factory=PerceptionFrame)
    active_target: Optional[DetectedObject] = None
    last_known_target_pose: Optional[Pose3D] = None  # для SEARCH_LAST_KNOWN
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────
# TELEMETRY / EVENTS
# ─────────────────────────────────────────────

@dataclass
class TelemetryPacket:
    """Что летит на WebSocket клиенту."""
    flight_mode: FlightMode = FlightMode.IDLE
    safety_mode: SafetyMode = SafetyMode.NOMINAL
    pose: Pose3D = field(default_factory=Pose3D)
    battery_pct: float = 100.0
    slam_confidence: float = 1.0
    active_target_id: Optional[int] = None
    object_count: int = 0
    system_health: SystemHealth = SystemHealth.OK
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemEvent:
    """Event bus — что летит между модулями внутри системы."""
    event_type: str = ""
    payload: dict = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────
# WATCHDOG / SAFETY
# ─────────────────────────────────────────────

@dataclass
class SafetyStatus:
    battery_pct: float = 100.0
    link_lost: bool = False
    slam_lost: bool = False
    manual_override: bool = False
    low_battery_threshold: float = 20.0
    critical_battery_threshold: float = 10.0
    timestamp: float = field(default_factory=time.time)

    @property
    def requires_return(self) -> bool:
        return (
            self.link_lost or
            self.battery_pct < self.low_battery_threshold
        )

    @property
    def requires_emergency_land(self) -> bool:
        return self.battery_pct < self.critical_battery_threshold

    @property
    def requires_hover(self) -> bool:
        return self.slam_lost and not self.requires_return


# ─────────────────────────────────────────────
# MAVLINK COMMANDS
# ─────────────────────────────────────────────

@dataclass
class FlightCommand:
    """Команда в MAVLink transport layer."""
    command_type: str = ""          # "takeoff", "land", "set_position", "set_velocity"
    target_pose: Optional[Pose3D] = None
    target_velocity: Optional[Velocity3D] = None
    altitude: float = 0.0
    timestamp: float = field(default_factory=time.time)
