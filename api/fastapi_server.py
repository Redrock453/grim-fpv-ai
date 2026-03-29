from fastapi import FastAPI
import uvicorn
from calculators.flight_time_calc import calculate_flight_time
from calculators.thermal_analysis import calculate_thermal
from calculators.range_calc import calculate_range
from calculators.pid_tuning import recommend_pid
from api.models import FlightTimeRequest, ThermalRequest, RangeRequest, PIDRequest, MultiAIRequest
from ai_engines/gemini_engine import gemini_calculate
from ai_engines/glm_engine import glm_calculate
from ai_engines/groq_engine import groq_calculate
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

app = FastAPI(title="ГРІМ-5 FPV AI Engine", version="2.0")

@app.get("/health")
async def health():
    return {"status": "✅ OK", "drone": "ГРІМ-5", "ai_engines": "gemini + glm + groq"}

@app.post("/calculate/flight-time")
async def flight_time(request: FlightTimeRequest):
    return calculate_flight_time(**request.model_dump())

@app.post("/calculate/thermal")
async def thermal(request: ThermalRequest):
    return calculate_thermal(**request.model_dump())

@app.post("/calculate/range")
async def range_calc(request: RangeRequest):
    return calculate_range(**request.model_dump())

@app.post("/calculate/pid")
async def pid(request: PIDRequest):
    return recommend_pid(**request.model_dump())

@app.post("/calculate/multi-ai")
async def multi_ai(request: MultiAIRequest):
    prompt = f"Расчёт для ГРІМ-5: {request.calculation_type} с параметрами {request.params}"
    results = await asyncio.gather(
        gemini_calculate(prompt),
        glm_calculate(prompt),
        groq_calculate(prompt)
    )
    return {"multi_ai_results": results}

if __name__ == "__main__":
    uvicorn.run("api/fastapi_server:app", host="0.0.0.0", port=8000, reload=True)
