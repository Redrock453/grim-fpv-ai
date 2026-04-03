"""
Terminal Guidance Module — Autonomous Target Intercept
========================================================
Pure visual terminal guidance for FPV drone. No GPS required — EW resistant.

Algorithms:
  - Proportional Navigation (PN): a_cmd = N * V_c * d(LOS)/dt
  - Pure Pursuit: always point at target
  - Predicted Intercept Point (PIP): aim where target WILL be

Target acquisition:
  - Vehicles: 300-400m (bounding box > 10x10 px)
  - Personnel: 120-200m (bounding box > 10x10 px)
  - Works on analog video feed (no digital link required)

Integration:
  - HFSM state: TERMINAL_GUIDANCE (between TRACK and impact)
  - Input: ByteTrack bounding boxes + velocity estimates
  - Output: roll/pitch/yaw/throttle commands via MAVLink

Reference: grim-fpv-ai/core/terminal_guidance.py
"""

import math
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

log = logging.getLogger('terminal_guidance')


class GuidanceMode(Enum):
    PURE_PURSUIT = "pure_pursuit"
    PROPORTIONAL_NAV = "proportional_nav"
    PREDICTED_INTERCEPT = "predicted_intercept"


@dataclass
class TargetState:
    """Estimated target state from tracker."""
    cx: float          # bounding box center X (pixels)
    cy: float          # bounding box center Y (pixels)
    width: float       # bounding box width (pixels)
    height: float      # bounding box height (pixels)
    confidence: float  # detection confidence [0..1]
    class_id: int      # class (0=person, 1=car, 2=truck, etc.)
    frame_time: float  # timestamp

    # Estimated (from bounding box + known sizes)
    range_m: float = 0.0           # estimated distance (meters)
    bearing_deg: float = 0.0       # azimuth relative to drone heading
    elevation_deg: float = 0.0     # elevation angle
    velocity_px_s: Tuple[float, float] = (0.0, 0.0)  # velocity in pixels/sec


@dataclass
class GuidanceCommand:
    """Output guidance command for flight controller."""
    roll_cmd: float = 0.0      # [-1, 1] normalized
    pitch_cmd: float = 0.0     # [-1, 1] normalized
    yaw_cmd: float = 0.0       # [-1, 1] normalized
    throttle_cmd: float = 0.0  # [0, 1] normalized
    intercept_time_s: float = 0.0  # estimated time to target
    mode: GuidanceMode = GuidanceMode.PROPORTIONAL_NAV
    locked: bool = False


@dataclass
class GuidanceConfig:
    """Configuration for terminal guidance."""
    mode: GuidanceMode = GuidanceMode.PROPORTIONAL_NAV

    # Proportional Navigation constant (typically 3-5)
    pn_nav_constant: float = 4.0

    # Drone speed (m/s)
    drone_speed: float = 25.0

    # Camera FOV (degrees)
    fov_horizontal: float = 90.0
    fov_vertical: float = 60.0

    # Camera resolution
    img_width: int = 640
    img_height: int = 480

    # Target acquisition thresholds (pixels)
    min_bbox_size: int = 10     # minimum bounding box dimension
    min_confidence: float = 0.6 # minimum detection confidence

    # Engagement ranges (meters) — depends on target type
    engagement_range_vehicle: float = 350.0
    engagement_range_person: float = 180.0

    # Known target sizes for range estimation (meters)
    target_sizes: dict = field(default_factory=lambda: {
        0: 0.5,   # person width ~0.5m
        1: 2.0,   # car width ~2.0m
        2: 2.5,   # truck width ~2.5m
        3: 2.5,   # bus width ~2.5m
        5: 3.0,   # building face ~3.0m
    })

    # Control limits
    max_roll_rate: float = 300.0   # deg/s
    max_pitch_rate: float = 200.0  # deg/s
    max_throttle: float = 1.0


class RangeEstimator:
    """Estimate distance to target from bounding box size."""

    def __init__(self, config: GuidanceConfig):
        self.config = config

    def estimate(self, target: TargetState) -> float:
        """Estimate range from known target size and apparent pixel size."""
        known_width = self.config.target_sizes.get(target.class_id, 1.0)

        # Focal length in pixels: f = (img_width / 2) / tan(FOV_h / 2)
        focal_length = (self.config.img_width / 2) / math.tan(
            math.radians(self.config.fov_horizontal / 2)
        )

        # Range = (known_width * focal_length) / apparent_width_px
        if target.width > 0:
            range_m = (known_width * focal_length) / target.width
            return max(0.0, range_m)
        return 0.0


class BearingEstimator:
    """Estimate bearing and elevation from pixel position."""

    def __init__(self, config: GuidanceConfig):
        self.config = config

    def estimate(self, target: TargetState) -> Tuple[float, float]:
        """Returns (bearing_deg, elevation_deg) relative to camera center."""
        # Offset from image center (normalized to [-1, 1])
        dx = (target.cx - self.config.img_width / 2) / (self.config.img_width / 2)
        dy = (target.cy - self.config.img_height / 2) / (self.config.img_height / 2)

        # Convert to angles
        bearing = math.degrees(math.atan(dx * math.tan(
            math.radians(self.config.fov_horizontal / 2)
        )))
        elevation = -math.degrees(math.atan(dy * math.tan(
            math.radians(self.config.fov_vertical / 2)
        )))

        return bearing, elevation


class ProportionalNavigation:
    """
    Proportional Navigation guidance law.

    a_cmd = N * V_c * d(lambda)/dt

    Where:
      N     = navigation constant (3-5)
      V_c   = closing velocity
      lambda = line-of-sight angle
    """

    def __init__(self, config: GuidanceConfig):
        self.config = config
        self.prev_los_angle: Optional[float] = None
        self.prev_time: Optional[float] = None
        self.los_rate_history: list[float] = []

    def compute(self, target: TargetState) -> GuidanceCommand:
        """Compute guidance command using PN law."""
        now = target.frame_time

        # Line-of-sight angle from bearing
        los_angle = math.radians(target.bearing_deg)

        cmd = GuidanceCommand(mode=GuidanceMode.PROPORTIONAL_NAV)

        if self.prev_los_angle is not None and self.prev_time is not None:
            dt = now - self.prev_time
            if dt > 0:
                # LOS rate (rad/s)
                los_rate = (los_angle - self.prev_los_angle) / dt

                # Smooth LOS rate (low-pass filter)
                self.los_rate_history.append(los_rate)
                if len(self.los_rate_history) > 5:
                    self.los_rate_history.pop(0)
                smooth_los_rate = sum(self.los_rate_history) / len(self.los_rate_history)

                # Closing velocity (assume target moving away slowly)
                # In practice estimated from range rate
                v_closing = self.config.drone_speed * 0.8

                # PN acceleration command
                a_cmd = self.config.pn_nav_constant * v_closing * smooth_los_rate

                # Convert to roll command (lateral acceleration → roll)
                roll = a_cmd / (self.config.max_roll_rate * 0.1)
                roll = max(-1.0, min(1.0, roll))

                # Pitch: aim for target elevation
                pitch = target.elevation_deg / 30.0
                pitch = max(-1.0, min(1.0, pitch))

                cmd.roll_cmd = roll
                cmd.pitch_cmd = pitch
                cmd.throttle_cmd = self.config.max_throttle

                # Estimate intercept time
                if target.range_m > 0:
                    cmd.intercept_time_s = target.range_m / self.config.drone_speed

                cmd.locked = True

        self.prev_los_angle = los_angle
        self.prev_time = now
        return cmd

    def reset(self):
        self.prev_los_angle = None
        self.prev_time = None
        self.los_rate_history.clear()


class PurePursuit:
    """
    Pure Pursuit — always aim directly at target.
    Simpler than PN but less efficient for maneuvering targets.
    """

    def __init__(self, config: GuidanceConfig):
        self.config = config

    def compute(self, target: TargetState) -> GuidanceCommand:
        cmd = GuidanceCommand(mode=GuidanceMode.PURE_PURSUIT)

        # Roll: proportional to bearing offset
        bearing_norm = target.bearing_deg / (self.config.fov_horizontal / 2)
        cmd.roll_cmd = max(-1.0, min(1.0, bearing_norm * 2.0))

        # Pitch: proportional to elevation offset (dive towards target)
        elevation_norm = target.elevation_deg / (self.config.fov_vertical / 2)
        cmd.pitch_cmd = max(-1.0, min(1.0, -elevation_norm * 2.0))

        # Full throttle during terminal phase
        cmd.throttle_cmd = self.config.max_throttle

        # Intercept time estimate
        if target.range_m > 0:
            cmd.intercept_time_s = target.range_m / self.config.drone_speed

        cmd.locked = True
        return cmd


class PredictedInterceptPoint:
    """
    Predicted Intercept Point guidance.
    Aim at where the target WILL be, not where it IS.
    Requires velocity estimate from tracker.
    """

    def __init__(self, config: GuidanceConfig):
        self.config = config

    def compute(self, target: TargetState) -> GuidanceCommand:
        cmd = GuidanceCommand(mode=GuidanceMode.PREDICTED_INTERCEPT)

        if target.range_m <= 0:
            return cmd

        # Time to intercept (assuming constant speed)
        t_intercept = target.range_m / self.config.drone_speed

        # Predict target position at intercept time
        vx, vy = target.velocity_px_s
        predicted_cx = target.cx + vx * t_intercept
        predicted_cy = target.cy + vy * t_intercept

        # Clamp to image bounds
        predicted_cx = max(0, min(self.config.img_width, predicted_cx))
        predicted_cy = max(0, min(self.config.img_height, predicted_cy))

        # Compute commands to aim at predicted position
        dx = (predicted_cx - self.config.img_width / 2) / (self.config.img_width / 2)
        dy = (predicted_cy - self.config.img_height / 2) / (self.config.img_height / 2)

        cmd.roll_cmd = max(-1.0, min(1.0, dx * 2.0))
        cmd.pitch_cmd = max(-1.0, min(1.0, -dy * 2.0))
        cmd.throttle_cmd = self.config.max_throttle
        cmd.intercept_time_s = t_intercept
        cmd.locked = True
        return cmd


class TerminalGuidanceController:
    """
    Main terminal guidance controller.

    Pipeline:
      ByteTrack output → Target State Estimation → Guidance Law → MAVLink Commands

    This is the autonomous targeting module that works:
      - On analog video (no digital link needed)
      - Without GPS (EW resistant)
      - At range: vehicles 300-400m, personnel 120-200m
      - With targets as small as 10x10 pixels
    """

    def __init__(self, config: Optional[GuidanceConfig] = None):
        self.config = config or GuidanceConfig()
        self.range_est = RangeEstimator(self.config)
        self.bearing_est = BearingEstimator(self.config)

        # Select guidance algorithm
        if self.config.mode == GuidanceMode.PROPORTIONAL_NAV:
            self.guidance = ProportionalNavigation(self.config)
        elif self.config.mode == GuidanceMode.PURE_PURSUIT:
            self.guidance = PurePursuit(self.config)
        else:
            self.guidance = PredictedInterceptPoint(self.config)

        self.target_locked = False
        self.engagement_active = False
        self.lock_start_time: Optional[float] = None

    def update(self, detection: dict) -> GuidanceCommand:
        """
        Process a single detection from ByteTrack tracker.

        Input: dict with keys: cx, cy, w, h, confidence, class_id, time, vx, vy
        Output: GuidanceCommand for flight controller
        """
        # Build target state
        target = TargetState(
            cx=detection['cx'],
            cy=detection['cy'],
            width=detection['w'],
            height=detection['h'],
            confidence=detection.get('confidence', 0.0),
            class_id=detection.get('class_id', 0),
            frame_time=detection.get('time', time.time()),
            velocity_px_s=(detection.get('vx', 0.0), detection.get('vy', 0.0)),
        )

        # Check acquisition criteria
        if not self._check_acquisition(target):
            self.target_locked = False
            return GuidanceCommand(locked=False)

        # Estimate range and bearing
        target.range_m = self.range_est.estimate(target)
        target.bearing_deg, target.elevation_deg = self.bearing_est.estimate(target)

        # Check engagement range
        engagement_range = self._get_engagement_range(target.class_id)
        if target.range_m > engagement_range:
            log.debug(f'Target at {target.range_m:.0f}m > engagement range {engagement_range:.0f}m')
            self.target_locked = False
            return GuidanceCommand(locked=False)

        # Lock target
        if not self.target_locked:
            self.target_locked = True
            self.lock_start_time = time.time()
            log.info(f'TARGET LOCKED: class={target.class_id}, range={target.range_m:.0f}m, '
                     f'bearing={target.bearing_deg:.1f}°')
            self.guidance.reset()

        # Compute guidance command
        cmd = self.guidance.compute(target)
        self.engagement_active = cmd.locked

        # Log
        log.debug(f'Guidance: roll={cmd.roll_cmd:.2f}, pitch={cmd.pitch_cmd:.2f}, '
                  f'throttle={cmd.throttle_cmd:.2f}, TTI={cmd.intercept_time_s:.1f}s')

        return cmd

    def _check_acquisition(self, target: TargetState) -> bool:
        """Check if target meets acquisition criteria."""
        if target.width < self.config.min_bbox_size:
            return False
        if target.height < self.config.min_bbox_size:
            return False
        if target.confidence < self.config.min_confidence:
            return False
        return True

    def _get_engagement_range(self, class_id: int) -> float:
        """Get engagement range for target type."""
        person_classes = {0}  # COCO person
        vehicle_classes = {1, 2, 3, 5, 7}  # car, truck, bus, building, truck

        if class_id in person_classes:
            return self.config.engagement_range_person
        elif class_id in vehicle_classes:
            return self.config.engagement_range_vehicle
        else:
            return 200.0  # default

    def release_lock(self):
        """Release target lock."""
        self.target_locked = False
        self.engagement_active = False
        self.lock_start_time = None
        self.guidance.reset()
        log.info('Target lock released')

    def get_status(self) -> dict:
        """Get current guidance status."""
        return {
            'locked': self.target_locked,
            'engaged': self.engagement_active,
            'mode': self.config.mode.value,
            'lock_duration_s': (
                time.time() - self.lock_start_time
                if self.lock_start_time else 0.0
            ),
        }


# --- Demo / Test ---

def simulate_terminal_guidance():
    """Simulate terminal guidance engagement."""
    print("=" * 60)
    print("TERMINAL GUIDANCE SIMULATION")
    print("=" * 60)

    config = GuidanceConfig(
        mode=GuidanceMode.PROPORTIONAL_NAV,
        drone_speed=25.0,
        pn_nav_constant=4.0,
    )

    controller = TerminalGuidanceController(config)

    # Simulate target approaching: starts at 300m, offset 15°
    sim_time = 0.0
    target_range = 300.0
    target_bearing = 15.0  # degrees offset
    target_speed = 3.0     # m/s target moving away

    print(f"\nMode: {config.mode.value}")
    print(f"Drone speed: {config.drone_speed} m/s")
    print(f"Nav constant: {config.pn_nav_constant}")
    print(f"\n{'Time':>6s} {'Range':>8s} {'Bearing':>8s} {'Roll':>7s} "
          f"{'Pitch':>7s} {'Throttle':>9s} {'TTI':>6s} {'Locked':>7s}")
    print("-" * 70)

    while target_range > 5 and sim_time < 30:
        dt = 0.1
        sim_time += dt

        # Simulate bounding box (shrinking range = growing bbox)
        focal = (config.img_width / 2) / math.tan(math.radians(config.fov_horizontal / 2))
        bbox_w = (2.0 * focal) / max(target_range, 1.0)  # 2m car width
        bbox_h = bbox_w * 0.7

        # Target center offset (from bearing)
        cx_offset = (config.img_width / 2) + math.tan(math.radians(target_bearing)) * focal
        cy_offset = config.img_height / 2 + 30  # slightly below center

        detection = {
            'cx': cx_offset,
            'cy': cy_offset,
            'w': bbox_w,
            'h': bbox_h,
            'confidence': 0.85,
            'class_id': 1,  # car
            'time': sim_time,
            'vx': 5.0,  # pixels/sec
            'vy': 1.0,
        }

        cmd = controller.update(detection)

        print(f"{sim_time:6.1f} {target_range:8.1f} {target_bearing:8.1f} "
              f"{cmd.roll_cmd:7.3f} {cmd.pitch_cmd:7.3f} "
              f"{cmd.throttle_cmd:9.3f} {cmd.intercept_time_s:6.1f} "
              f"{'YES' if cmd.locked else 'NO':>7s}")

        # Update simulation
        closing_speed = config.drone_speed - target_speed
        target_range -= closing_speed * dt
        target_bearing *= 0.95  # bearing decreases as we approach

        if not cmd.locked:
            continue

    print("-" * 70)
    print(f"\nSimulation ended: range={target_range:.1f}m, time={sim_time:.1f}s")
    status = controller.get_status()
    print(f"Status: {status}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    simulate_terminal_guidance()
