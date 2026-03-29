from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.flight_time_calc import calculate_flight_time
from calculators.hover_current import calculate_hover_current
from calculators.rf_link_budget import calculate_path_loss, calculate_link_budget, watts_to_dbm
from calculators.thermal_rf import calculate_rf_thermal

app = FastAPI(title="GRIM-5 FPV & RF Engineering API (Victoria)")

class FlightTimeRequest(BaseModel):
    battery_wh: float
    avg_power_watts: float
    sag_factor: float = 0.85

class HoverCurrentRequest(BaseModel):
    weight_g: float
    thrust_kg: float
    max_current_a: float

class RFLinkRequest(BaseModel):
    freq_mhz: float
    distance_km: float
    tx_power_watts: float
    tx_gain_dbi: float = 4.0
    rx_gain_dbi: float = 2.0
    fade_margin_db: float = 10.0

class RFThermalRequest(BaseModel):
    p_out_watts: float
    efficiency: float = 0.4

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": "grim-fpv-ai", "lead": "Victoria"}

@app.post("/calculate/flight-time")
async def get_flight_time(req: FlightTimeRequest):
    try:
        minutes = calculate_flight_time(req.battery_wh, req.avg_power_watts, req.sag_factor)
        return {
            "flight_time_min": minutes,
            "params": {
                "wh": req.battery_wh,
                "watts": req.avg_power_watts,
                "sag": req.sag_factor
            }
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

@app.post("/calculate/hover-current")
async def get_hover_current(req: HoverCurrentRequest):
    try:
        current_a = calculate_hover_current(req.weight_g, req.thrust_kg, req.max_current_a)
        return {
            "hover_current_a": current_a,
            "params": {
                "weight": req.weight_g,
                "thrust": req.thrust_kg,
                "max_current": req.max_current_a
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calculate/multi-ai")
async def multi_ai_check():
    return {
        "status": "simulation",
        "engines": ["grok", "gemini", "claude"],
        "message": "AI Engines will be integrated in the next update"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
