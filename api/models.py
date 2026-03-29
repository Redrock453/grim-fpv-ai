from pydantic import BaseModel
from typing import Dict, Optional

class FlightTimeRequest(BaseModel):
    battery_wh: float = 18.87
    c_rating: int = 75
    drone_weight_g: float = 865
    target_current_a: float = 15.0

class ThermalRequest(BaseModel):
    current_a_per_motor: float = 15.0
    ambient_temp_c: float = 25.0

class RangeRequest(BaseModel):
    tx_power_mw: int = 500
    antenna_gain_db: float = 3.0

class PIDRequest(BaseModel):
    kv: int = 2000
    prop_size: str = "5045"
    weight_g: float = 865

class MultiAIRequest(BaseModel):
    calculation_type: str
    params: Dict
