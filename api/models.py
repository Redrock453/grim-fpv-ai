from pydantic import BaseModel
from typing import Optional, List

class FlightTimeRequest(BaseModel):
    battery_wh: float
    avg_power_watts: float
    sag_factor: Optional[float] = 0.85

class MultiAIRequest(BaseModel):
    prompt: str
    engines: Optional[List[str]] = ["grok", "gemini", "claude"]
