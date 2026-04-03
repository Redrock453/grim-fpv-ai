from pydantic import BaseModel
from typing import Optional, List, Dict


class FlightTimeRequest(BaseModel):
    battery_wh: float
    avg_power_watts: float
    sag_factor: Optional[float] = 0.85


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
