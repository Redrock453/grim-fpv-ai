Иерархический конечный автомат состояний (HFSM).
SAFETY всегда прерывает NAVIGATION — стандарт робототехники.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
from core.data_contracts import (
    FlightMode, SafetyMode, WorldModel, SafetyStatus,
    SystemEvent, FlightCommand
)
from core.terminal_guidance import (
    TerminalGuidanceController, GuidanceConfig, GuidanceMode
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# АБСТРАКТНЫЙ СТЕЙТ
# ─────────────────────────────────────────────

class State(ABC):
    """Базовый класс для любого состояния."""

    def __init__(self, name: str):
        self.name = name

    async def on_enter(self, world: WorldModel) -> None:
        """Вызывается при входе в состояние."""
        logger.info(f"[STATE] → {self.name}")

    async def on_exit(self, world: WorldModel) -> None:
        """Вызывается при выходе из состояния."""
        pass

    @abstractmethod
    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        """
        Основная логика стейта.
        Возвращает FlightCommand или None.
        """
        pass

    @abstractmethod
    async def evaluate_transition(self, world: WorldModel) -> Optional["State"]:
        """
        Оценивает нужен ли переход в другой стейт.
        Возвращает новый стейт или None (остаёмся).
        """
        pass


# ─────────────────────────────────────────────
# NAVIGATION STATES
# ─────────────────────────────────────────────

class IdleState(State):
    def __init__(self):
        super().__init__("IDLE")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        return None

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        if world.perception.targets:
            return SearchState()
        return None


class SearchState(State):
    def __init__(self):
        super().__init__("SEARCH")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        # TODO: паттерн поиска (spiral / lawnmower)
        return FlightCommand(command_type="search_pattern")

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        targets = world.perception.targets
        if targets:
            best = max(targets, key=lambda t: t.confidence)
            if best.is_reliable:
                return TrackState(target_id=best.track_id)
        return None


class SearchLastKnownState(State):
    """
    GPT: не сбрасываться в IDLE если цель пропала.
    Ищем в последней известной точке с таймаутом.
    """
    TIMEOUT_SEC = 10.0

    def __init__(self):
        super().__init__("SEARCH_LAST_KNOWN")
        self._elapsed = 0.0

    async def on_enter(self, world: WorldModel) -> None:
        await super().on_enter(world)
        self._elapsed = 0.0

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        self._elapsed += 0.1  # шаг цикла
        if world.last_known_target_pose:
            return FlightCommand(
                command_type="set_position",
                target_pose=world.last_known_target_pose
            )
        return None

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        # цель снова появилась
        if world.perception.targets:
            best = max(world.perception.targets, key=lambda t: t.confidence)
            if best.is_reliable:
                return TrackState(target_id=best.track_id)
        # таймаут — уходим домой
        if self._elapsed >= self.TIMEOUT_SEC:
            logger.warning("[FSM] Target lost timeout — returning home")
            return ReturnState()
        return None


class TrackState(State):
    def __init__(self, target_id: int = -1):
        super().__init__("TRACK")
        self.target_id = target_id

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        target = self._find_target(world)
        if target and target.world_position:
            return FlightCommand(
                command_type="set_position",
                target_pose=target.world_position
            )
        return None

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        target = self._find_target(world)
        if not target:
            return SearchLastKnownState()

        # Target in engagement range → switch to TERMINAL_GUIDANCE
        if hasattr(target, 'range_m') and target.range_m:
            guidance_ctrl = TerminalGuidanceController()
            engagement_range = guidance_ctrl._get_engagement_range(
                getattr(target, 'class_id', 0)
            )
            if target.range_m <= engagement_range:
                logger.info(f"[FSM] Target at {target.range_m:.0f}m — ENGAGE")
                return TerminalGuidanceState(target_id=self.target_id)

        return None

    def _find_target(self, world: WorldModel):
        return next(
            (o for o in world.perception.targets if o.track_id == self.target_id),
            None
        )


class PatrolState(State):
    def __init__(self):
        super().__init__("PATROL")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        # TODO: waypoint следование
        return FlightCommand(command_type="next_waypoint")

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        if world.perception.targets:
            best = max(world.perception.targets, key=lambda t: t.confidence)
            if best.is_reliable:
                return TrackState(target_id=best.track_id)
        return None


class ReturnState(State):
    def __init__(self):
        super().__init__("RETURN")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        return FlightCommand(command_type="return_to_home")

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        # TODO: проверка что добрались домой
        return None


# ─────────────────────────────────────────────
# TERMINAL GUIDANCE STATE — Autonomous Target Intercept
# ─────────────────────────────────────────────

class TerminalGuidanceState(State):
    """
    Autonomous terminal guidance — visual-only, GPS-free, EW-resistant.

    Pipeline: ByteTrack → Range/Bearing Estimation → PN/Pursuit/PIP → MAVLink

    Target acquisition:
      Vehicles: 300-400m (bbox > 10x10 px)
      Personnel: 120-200m (bbox > 10x10 px)
    """
    def __init__(self, target_id: int = -1):
        super().__init__("TERMINAL_GUIDANCE")
        self.target_id = target_id
        self._guidance = TerminalGuidanceController(
            GuidanceConfig(mode=GuidanceMode.PROPORTIONAL_NAV)
        )

    async def on_enter(self, world: WorldModel) -> None:
        await super().on_enter(world)
        logger.warning("[FSM] *** TERMINAL GUIDANCE ENGAGED ***")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        target = self._find_target(world)
        if not target:
            return None

        # Build detection dict from tracked target
        detection = {
            'cx': getattr(target, 'bbox_cx', 320),
            'cy': getattr(target, 'bbox_cy', 240),
            'w': getattr(target, 'bbox_w', 20),
            'h': getattr(target, 'bbox_h', 20),
            'confidence': target.confidence,
            'class_id': getattr(target, 'class_id', 0),
            'time': world.timestamp if hasattr(world, 'timestamp') else 0,
            'vx': getattr(target, 'velocity_px_x', 0),
            'vy': getattr(target, 'velocity_px_y', 0),
        }

        cmd = self._guidance.update(detection)

        if cmd.locked:
            return FlightCommand(
                command_type="guidance",
                roll=cmd.roll_cmd,
                pitch=cmd.pitch_cmd,
                throttle=cmd.throttle_cmd,
            )
        return None

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        target = self._find_target(world)

        # Target lost
        if not target:
            logger.warning("[FSM] Target lost during terminal guidance")
            self._guidance.release_lock()
            return SearchLastKnownState()

        # Impact (range < 5m) — mission complete
        if hasattr(target, 'range_m') and target.range_m and target.range_m < 5:
            logger.warning("[FSM] *** IMPACT *** Target neutralized")
            self._guidance.release_lock()
            return EmergencyLandState()  # or self-destruct

        return None

    def _find_target(self, world: WorldModel):
        return next(
            (o for o in world.perception.targets if o.track_id == self.target_id),
            None
        )


# ─────────────────────────────────────────────
# SAFETY STATES (Interrupt — приоритет над Navigation)
# ─────────────────────────────────────────────

class AvoidState(State):
    """
    GLM: AVOID — это Interrupt, не обычный стейт.
    Прерывает Navigation, после разрешения возвращает предыдущий стейт.
    """
    def __init__(self, return_to: State):
        super().__init__("AVOID")
        self.return_to = return_to  # куда вернуться после avoid

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        # TODO: obstacle avoidance алгоритм
        return FlightCommand(command_type="avoid_obstacle")

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        if not world.perception.obstacles:
            logger.info(f"[FSM] Obstacle cleared — returning to {self.return_to.name}")
            return self.return_to
        return None


class EmergencyLandState(State):
    def __init__(self):
        super().__init__("EMERGENCY_LAND")

    async def execute(self, world: WorldModel) -> Optional[FlightCommand]:
        return FlightCommand(command_type="land")

    async def evaluate_transition(self, world: WorldModel) -> Optional[State]:
        return None  # без выхода


# ─────────────────────────────────────────────
# HFSM ОРКЕСТРАТОР
# ─────────────────────────────────────────────

class HierarchicalFSM:
    """
    HFSM: SAFETY > NAVIGATION.
    Safety проверяется первым на каждом цикле — всегда.
    """

    CYCLE_HZ = 10  # частота цикла FSM

    def __init__(self, event_bus=None):
        self._nav_state: State = IdleState()
        self._safety_mode: SafetyMode = SafetyMode.NOMINAL
        self._avoid_active: bool = False
        self._event_bus = event_bus
        self._running = False

    @property
    def current_state(self) -> str:
        if self._avoid_active:
            return "AVOID"
        return self._nav_state.name

    async def start(self, world_model_getter):
        """
        world_model_getter — callable что возвращает актуальный WorldModel.
        Разделение: FSM не знает откуда берётся WorldModel.
        """
        self._running = True
        await self._nav_state.on_enter(await world_model_getter())
        logger.info("[HFSM] Started")

        while self._running:
            try:
                world = await world_model_getter()
                command = await self._tick(world)
                if command and self._event_bus:
                    await self._event_bus.publish(SystemEvent(
                        event_type="flight_command",
                        payload={"command": command},
                        source="hfsm"
                    ))
            except Exception as e:
                logger.error(f"[HFSM] Tick error: {e}")

            await asyncio.sleep(1.0 / self.CYCLE_HZ)

    async def _tick(self, world: WorldModel) -> Optional[FlightCommand]:
        """Один цикл HFSM."""

        # ── SAFETY LAYER (всегда первый) ──────────────────
        safety = self._evaluate_safety(world)

        if safety == SafetyMode.EMERGENCY_LAND:
            if self._safety_mode != SafetyMode.EMERGENCY_LAND:
                logger.critical("[HFSM] EMERGENCY LAND triggered!")
                self._safety_mode = SafetyMode.EMERGENCY_LAND
            return await EmergencyLandState().execute(world)

        if safety == SafetyMode.MANUAL_OVERRIDE:
            self._safety_mode = SafetyMode.MANUAL_OVERRIDE
            return None  # управление у оператора

        # ── AVOID INTERRUPT ───────────────────────────────
        if world.perception.obstacles and not self._avoid_active:
            logger.warning(f"[HFSM] Obstacle detected — interrupting {self._nav_state.name}")
            self._avoid_state = AvoidState(return_to=self._nav_state)
            self._avoid_active = True
            self._safety_mode = SafetyMode.AVOID

        if self._avoid_active:
            next_state = await self._avoid_state.evaluate_transition(world)
            if next_state:
                # вернулись из avoid
                self._avoid_active = False
                self._safety_mode = SafetyMode.NOMINAL
                await self._transition_nav(next_state, world)
            else:
                return await self._avoid_state.execute(world)

        # ── NAVIGATION LAYER ──────────────────────────────
        next_nav = await self._nav_state.evaluate_transition(world)
        if next_nav:
            await self._transition_nav(next_nav, world)

        return await self._nav_state.execute(world)

    async def _transition_nav(self, new_state: State, world: WorldModel):
        await self._nav_state.on_exit(world)
        self._nav_state = new_state
        await self._nav_state.on_enter(world)

    def _evaluate_safety(self, world: WorldModel) -> SafetyMode:
        """Watchdog checks — порядок важен."""
        # TODO: подключить реальный SafetyStatus из watchdog
        return SafetyMode.NOMINAL

    def stop(self):
        self._running = False
        logger.info("[HFSM] Stopped")
