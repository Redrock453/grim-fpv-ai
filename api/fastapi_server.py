from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.flight_time_calc import calculate_flight_time

app = FastAPI(title="GRIM-5 FPV AI Engineering API")

class FlightTimeRequest(BaseModel):
    battery_wh: float
    avg_power_watts: float
    sag_factor: float = 0.85

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": "grim-fpv-ai"}

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
