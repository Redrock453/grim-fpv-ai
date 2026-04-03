from fastapi import FastAPI, HTTPException
import uvicorn
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.flight_time_calc import calculate_flight_time
from calculators.hover_current import calculate_hover_current
from calculators.rf_link_budget import calculate_path_loss, calculate_link_budget, watts_to_dbm
from calculators.thermal_rf import calculate_rf_thermal
from api.models import (
    FlightTimeRequest, HoverCurrentRequest, RFLinkRequest,
    RFThermalRequest, ThermalRequest, RangeRequest, PIDRequest, MultiAIRequest
)

app = FastAPI(title="GRIM-5 FPV AI Engineering API", version="2.0")


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
