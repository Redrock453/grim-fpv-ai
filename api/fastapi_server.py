from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sys
import logging
import asyncio
import time
import random
import math
from typing import Dict, List, Optional
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.flight_time_calc import calculate_flight_time
from calculators.hover_current import calculate_hover_current
from calculators.rf_link_budget import calculate_path_loss, calculate_link_budget, watts_to_dbm
from calculators.thermal_rf import calculate_rf_thermal
from api.models import (
    FlightTimeRequest, HoverCurrentRequest, RFLinkRequest,
    RFThermalRequest, ThermalRequest, RangeRequest, PIDRequest, MultiAIRequest
)

try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False

from flight_simulator import generate_mission, BASE_LAT, BASE_LON

logger = logging.getLogger(__name__)

app = FastAPI(title="GRIM-5 FPV AI Engineering API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/dashboard", StaticFiles(directory=_static_dir, html=True), name="static")

# ─────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────

latest_telemetry: Dict = {
    "timestamp": "",
    "lat": BASE_LAT,
    "lon": BASE_LON,
    "alt_m": 0.0,
    "speed_ms": 0.0,
    "heading_deg": 0.0,
    "battery_pct": 100.0,
    "voltage": 25.2,
    "current_a": 0.0,
    "rssi_dbm": -55.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "throttle_pct": 0.0,
    "mode": "STANDBY",
}

sitl_connected: bool = False
sitl_master = None
active_mission: Optional[Dict] = None
websocket_clients: List[WebSocket] = []

# ─────────────────────────────────────────────
# MAVLink TELEMETRY BACKGROUND TASK
# ─────────────────────────────────────────────

def _parse_telemetry_from_msg(msg) -> Dict:
    msg_type = msg.get_type()
    ts = datetime.utcnow().isoformat()

    if msg_type == "GLOBAL_POSITION_INT":
        latest_telemetry.update({
            "timestamp": ts,
            "lat": msg.lat / 1e7,
            "lon": msg.lon / 1e7,
            "alt_m": msg.alt / 1e3,
            "speed_ms": math.sqrt(msg.vx**2 + msg.vy**2) / 100.0,
            "heading_deg": (msg.hdg / 100.0) % 360,
        })
    elif msg_type == "SYS_STATUS":
        latest_telemetry.update({
            "timestamp": ts,
            "battery_pct": msg.battery_remaining,
            "voltage": msg.voltage_battery / 1e3,
            "current_a": msg.current_battery / 100.0,
        })
    elif msg_type == "ATTITUDE":
        latest_telemetry.update({
            "timestamp": ts,
            "roll": math.degrees(msg.roll),
            "pitch": math.degrees(msg.pitch),
            "yaw": (math.degrees(msg.yaw) % 360),
        })
    elif msg_type == "VFR_HUD":
        latest_telemetry.update({
            "timestamp": ts,
            "alt_m": msg.alt,
            "speed_ms": msg.groundspeed,
            "throttle_pct": msg.throttle,
        })
    elif msg_type == "HEARTBEAT":
        latest_telemetry["timestamp"] = ts
        mode_mapping = {
            0: "MANUAL", 4: "GUIDED", 5: "AUTO", 6: "RTL",
            9: "LAND", 10: "DRIFT", 15: "STABILIZE", 16: "LOITER",
        }
        latest_telemetry["mode"] = mode_mapping.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
    elif msg_type == "GPS_RAW_INT":
        latest_telemetry.update({
            "timestamp": ts,
            "lat": msg.lat / 1e7,
            "lon": msg.lon / 1e7,
            "alt_m": msg.alt / 1e3,
        })
    elif msg_type == "SCALED_IMU2":
        latest_telemetry["timestamp"] = ts
    elif msg_type == "RADIO_STATUS":
        latest_telemetry.update({
            "timestamp": ts,
            "rssi_dbm": msg.rssi,
        })

    return latest_telemetry


async def mavlink_telemetry_loop():
    global sitl_connected, sitl_master

    if not PYMAVLINK_AVAILABLE:
        logger.warning("[MAV] pymavlink not installed, falling back to simulation")
        return

    while True:
        try:
            if not sitl_connected:
                mavlink_url = os.getenv("MAVLINK_URL", "tcp:localhost:5760")
                logger.info(f"[MAV] Connecting to SITL on {mavlink_url}")
                sitl_master = mavutil.mavlink_connection(mavlink_url)
                await asyncio.sleep(1)

                msg = sitl_master.recv_match(type="HEARTBEAT", blocking=True, timeout=5)
                if msg:
                    sitl_connected = True
                    logger.info("[MAV] Connected to SITL")
                    _parse_telemetry_from_msg(msg)
                else:
                    raise ConnectionError("No heartbeat received")

            while sitl_connected:
                msg = sitl_master.recv_match(blocking=True, timeout=1)
                if msg:
                    _parse_telemetry_from_msg(msg)
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.warning(f"[MAV] Connection lost: {e}")
            sitl_connected = False
            sitl_master = None
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(mavlink_telemetry_loop())
    logger.info("[API] GRIM-5 FPV AI Engineering API started")


@app.on_event("shutdown")
async def shutdown_event():
    global sitl_connected, sitl_master
    sitl_connected = False
    if sitl_master:
        try:
            sitl_master.close()
        except Exception:
            pass
    sitl_master = None
    logger.info("[API] Shutting down")


# ─────────────────────────────────────────────
# SIMULATED TELEMETRY GENERATOR
# ─────────────────────────────────────────────

_sim_state = {
    "lat": BASE_LAT,
    "lon": BASE_LON,
    "alt_m": 0.0,
    "speed_ms": 0.0,
    "heading_deg": 0.0,
    "battery_pct": 100.0,
    "voltage": 25.2,
    "current_a": 0.0,
    "rssi_dbm": -55.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "throttle_pct": 0.0,
    "mode": "STANDBY",
    "phase": "idle",
    "mission_start": None,
    "mission_duration": 0,
}


def _generate_sim_telemetry() -> Dict:
    global _sim_state

    now = datetime.utcnow()
    ts = now.isoformat()

    if _sim_state["phase"] == "idle":
        return {
            "timestamp": ts,
            "lat": BASE_LAT,
            "lon": BASE_LON,
            "alt_m": 0.0,
            "speed_ms": 0.0,
            "heading_deg": 0.0,
            "battery_pct": 100.0,
            "voltage": 25.2,
            "current_a": 0.0,
            "rssi_dbm": -55.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "throttle_pct": 0.0,
            "mode": "STANDBY",
        }

    if _sim_state["phase"] == "takeoff":
        _sim_state["alt_m"] = min(_sim_state["alt_m"] + 2.0, 30.0)
        _sim_state["throttle_pct"] = 70.0
        _sim_state["mode"] = "GUIDED"
        if _sim_state["alt_m"] >= 30.0:
            _sim_state["phase"] = "mission"
            _sim_state["mission_start"] = time.time()
    elif _sim_state["phase"] == "mission":
        elapsed = time.time() - _sim_state["mission_start"]
        _sim_state["heading_deg"] = (_sim_state["heading_deg"] + random.uniform(-5, 5)) % 360
        speed = 15.0 + 5.0 * math.sin(elapsed / 10)
        _sim_state["speed_ms"] = max(0, speed)
        _sim_state["alt_m"] = 30.0 + 10.0 * math.sin(elapsed / 20)
        _sim_state["throttle_pct"] = 50.0 + 10.0 * math.sin(elapsed / 15)
        _sim_state["battery_pct"] = max(5.0, _sim_state["battery_pct"] - 0.02)
        _sim_state["mode"] = "AUTO"

        heading_rad = math.radians(_sim_state["heading_deg"])
        _sim_state["lat"] += speed * math.cos(heading_rad) * 0.000001
        _sim_state["lon"] += speed * math.sin(heading_rad) * 0.000001

        if _sim_state["battery_pct"] <= 10.0:
            _sim_state["phase"] = "rtl"
    elif _sim_state["phase"] == "rtl":
        _sim_state["mode"] = "RTL"
        _sim_state["throttle_pct"] = 40.0
        _sim_state["alt_m"] = max(10.0, _sim_state["alt_m"] - 1.0)
        _sim_state["speed_ms"] = max(0, _sim_state["speed_ms"] - 0.5)
        if _sim_state["alt_m"] <= 10.0:
            _sim_state["phase"] = "land"
    elif _sim_state["phase"] == "land":
        _sim_state["mode"] = "LAND"
        _sim_state["alt_m"] = max(0, _sim_state["alt_m"] - 0.5)
        _sim_state["throttle_pct"] = 20.0
        _sim_state["speed_ms"] = max(0, _sim_state["speed_ms"] - 0.3)
        if _sim_state["alt_m"] <= 0:
            _sim_state["phase"] = "idle"
            _sim_state["lat"] = BASE_LAT
            _sim_state["lon"] = BASE_LON

    _sim_state["roll"] = 10.0 * math.sin(time.time() / 3) + random.uniform(-2, 2)
    _sim_state["pitch"] = 5.0 * math.sin(time.time() / 5) + random.uniform(-1, 1)
    _sim_state["yaw"] = _sim_state["heading_deg"] + random.uniform(-3, 3)
    _sim_state["voltage"] = 21.0 + (25.2 - 21.0) * (_sim_state["battery_pct"] / 100.0)
    _sim_state["current_a"] = 12.0 * (_sim_state["throttle_pct"] / 50.0)
    _sim_state["rssi_dbm"] = -55.0 - 20.0 * math.log10(max(0.1, random.uniform(0.5, 2.0))) + random.uniform(-2, 2)

    return {
        "timestamp": ts,
        "lat": round(_sim_state["lat"], 6),
        "lon": round(_sim_state["lon"], 6),
        "alt_m": round(_sim_state["alt_m"], 1),
        "speed_ms": round(_sim_state["speed_ms"], 1),
        "heading_deg": round(_sim_state["heading_deg"], 1),
        "battery_pct": round(_sim_state["battery_pct"], 1),
        "voltage": round(_sim_state["voltage"], 2),
        "current_a": round(_sim_state["current_a"], 1),
        "rssi_dbm": round(_sim_state["rssi_dbm"], 1),
        "roll": round(_sim_state["roll"], 1),
        "pitch": round(_sim_state["pitch"], 1),
        "yaw": round(_sim_state["yaw"], 1),
        "throttle_pct": round(_sim_state["throttle_pct"], 1),
        "mode": _sim_state["mode"],
    }


# ─────────────────────────────────────────────
# EXISTING ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": "grim-fpv-ai", "drone": "ГРІМ-5", "version": "2.0"}


@app.post("/calculate/flight-time")
async def get_flight_time(req: FlightTimeRequest):
    try:
        minutes = calculate_flight_time(req.battery_wh, req.avg_power_watts, req.sag_factor)
        return {
            "flight_time_min": round(minutes, 2),
            "params": {"wh": req.battery_wh, "watts": req.avg_power_watts, "sag": req.sag_factor}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/hover-current")
async def get_hover_current(req: HoverCurrentRequest):
    try:
        current_a = calculate_hover_current(req.weight_g, req.thrust_kg, req.max_current_a)
        return {
            "hover_current_a": round(current_a, 2),
            "params": {"weight": req.weight_g, "thrust": req.thrust_kg, "max_current": req.max_current_a}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/rf-link")
async def get_rf_link(req: RFLinkRequest):
    try:
        p_dbm = watts_to_dbm(req.tx_power_watts)
        loss = calculate_path_loss(req.freq_mhz, req.distance_km)
        rssi = calculate_link_budget(p_dbm, req.tx_gain_dbi, req.rx_gain_dbi, loss, req.fade_margin_db)
        return {
            "tx_power_dbm": round(p_dbm, 2),
            "path_loss_db": round(loss, 2),
            "rssi_dbm": round(rssi, 2),
            "status": "Strong" if rssi > -90 else "Weak"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/rf-thermal")
async def get_rf_thermal(req: RFThermalRequest):
    try:
        return calculate_rf_thermal(req.p_out_watts, req.efficiency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/thermal")
async def get_thermal(req: ThermalRequest):
    try:
        from calculators.thermal_analysis import calculate_thermal
        return calculate_thermal(req.current_a_per_motor, req.ambient_temp_c)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/range")
async def get_range(req: RangeRequest):
    try:
        from calculators.range_calc import calculate_range
        return calculate_range(req.tx_power_mw, req.antenna_gain_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/pid")
async def get_pid(req: PIDRequest):
    try:
        from calculators.pid_tuning import recommend_pid
        return recommend_pid(req.kv, req.prop_size, req.weight_g)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calculate/multi-ai")
async def multi_ai(req: MultiAIRequest):
    import asyncio
    prompt = f"Расчёт для ГРІМ-5: {req.calculation_type} с параметрами {req.params}"
    try:
        from ai_engines.gemini_engine import gemini_calculate
        from ai_engines.glm_engine import glm_calculate
        from ai_engines.groq_engine import groq_calculate
        results = await asyncio.gather(
            gemini_calculate(prompt),
            glm_calculate(prompt),
            groq_calculate(prompt),
            return_exceptions=True
        )
        return {"multi_ai_results": [r if not isinstance(r, Exception) else {"error": str(r)} for r in results]}
    except Exception as e:
        return {"status": "partial", "message": "Some AI engines unavailable", "error": str(e)}


@app.get("/missions/portfolio")
async def get_portfolio_missions():
    from flight_simulator import generate_portfolio_missions
    from dataclasses import asdict
    missions = generate_portfolio_missions()
    return {
        "total": len(missions),
        "missions": [
            {
                "mission_id": m.mission_id,
                "type": m.mission_type,
                "callsign": m.callsign,
                "duration_sec": m.duration_sec,
                "distance_m": m.distance_m,
                "max_alt_m": m.max_alt_m,
                "max_speed_ms": m.max_speed_ms,
                "battery_start": m.battery_start_pct,
                "battery_end": m.battery_end_pct,
                "status": m.status,
                "notes": m.notes,
            }
            for m in missions
        ]
    }


@app.get("/missions/{mission_type}/simulate")
async def simulate_mission(mission_type: str, duration: int = 180, wind: float = 5.0):
    from flight_simulator import generate_mission
    from dataclasses import asdict
    valid_types = ["recon", "intercept", "loiter", "strike", "delivery"]
    if mission_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Use: {valid_types}")
    mission = generate_mission(mission_type, duration, wind)
    return asdict(mission)


# ─────────────────────────────────────────────
# NEW ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/simulate/mission")
async def simulate_mission_get(type: str = "recon", duration: int = 180, wind: float = 5.0):
    from dataclasses import asdict
    valid_types = ["recon", "intercept", "loiter", "strike", "delivery"]
    if type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Use: {valid_types}")
    mission = generate_mission(type, duration, wind)
    return asdict(mission)


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info(f"[WS] Client connected. Total clients: {len(websocket_clients)}")

    try:
        while True:
            if sitl_connected and latest_telemetry["timestamp"]:
                data = dict(latest_telemetry)
            else:
                data = _generate_sim_telemetry()

            await websocket.send_json(data)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected")
    except Exception as e:
        logger.warning(f"[WS] Error: {e}")
    finally:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
        logger.info(f"[WS] Client removed. Total clients: {len(websocket_clients)}")


@app.post("/mission/start")
async def mission_start(body: Dict = None):
    global active_mission, _sim_state

    if body is None:
        body = {}

    mission_type = body.get("mission_type", "recon")
    valid_types = ["recon", "intercept", "loiter", "strike", "delivery"]
    if mission_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Use: {valid_types}")

    if sitl_connected and sitl_master:
        try:
            sitl_master.mav.command_long_send(
                sitl_master.target_system,
                sitl_master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,
                1,
                4,
                0, 0, 0, 0, 0
            )
            await asyncio.sleep(0.5)

            sitl_master.mav.command_long_send(
                sitl_master.target_system,
                sitl_master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1, 0, 0, 0, 0, 0, 0
            )
            await asyncio.sleep(0.5)

            sitl_master.mav.command_long_send(
                sitl_master.target_system,
                sitl_master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0, 0, 0, 0, 0, 0, 10.0
            )

            active_mission = {
                "mission_type": mission_type,
                "status": "running",
                "source": "sitl",
                "started_at": datetime.utcnow().isoformat(),
            }
            return {"status": "success", "message": f"Mission {mission_type} started via SITL", "mission": active_mission}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MAVLink command failed: {str(e)}")

    else:
        _sim_state["phase"] = "takeoff"
        _sim_state["lat"] = BASE_LAT
        _sim_state["lon"] = BASE_LON
        _sim_state["alt_m"] = 0.0
        _sim_state["speed_ms"] = 0.0
        _sim_state["heading_deg"] = random.uniform(0, 360)
        _sim_state["battery_pct"] = 100.0
        _sim_state["mode"] = "GUIDED"

        mission = generate_mission(mission_type, 180, 5.0)
        active_mission = {
            "mission_type": mission_type,
            "status": "running",
            "source": "simulator",
            "started_at": datetime.utcnow().isoformat(),
            "mission_id": mission.mission_id,
            "callsign": mission.callsign,
        }
        return {"status": "success", "message": f"Mission {mission_type} started in simulation", "mission": active_mission}


@app.post("/mission/stop")
async def mission_stop():
    global active_mission, _sim_state

    if not active_mission:
        raise HTTPException(status_code=400, detail="No active mission to stop")

    if active_mission.get("source") == "sitl" and sitl_connected and sitl_master:
        try:
            sitl_master.mav.command_long_send(
                sitl_master.target_system,
                sitl_master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,
                0, 0, 0, 0, 0, 0, 0
            )
            active_mission["status"] = "rtl"
            return {"status": "success", "message": "RTL command sent via MAVLink", "mission": active_mission}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MAVLink RTL failed: {str(e)}")
    else:
        _sim_state["phase"] = "rtl"
        _sim_state["mode"] = "RTL"
        active_mission["status"] = "rtl"
        return {"status": "success", "message": "Mission stopped, returning to launch (simulated)", "mission": active_mission}


@app.get("/telemetry/latest")
async def get_latest_telemetry():
    if sitl_connected and latest_telemetry["timestamp"]:
        return {"source": "sitl", "connected": True, "telemetry": dict(latest_telemetry)}
    else:
        return {"source": "simulator", "connected": False, "telemetry": _generate_sim_telemetry()}


@app.get("/mission/status")
async def get_mission_status():
    if active_mission:
        return {"active": True, "mission": active_mission}
    return {"active": False, "message": "No active mission"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
