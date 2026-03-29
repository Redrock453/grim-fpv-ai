# FPV Drone Calculations for GRIM-5

def calculate_flight_time(battery_wh: float, power_watts: float, sag_factor: float = 0.85) -> float:
    """
    Calculates estimated flight time in minutes.
    
    Args:
        battery_wh: Battery energy in Watt-hours.
        power_watts: Average power consumption in Watts.
        sag_factor: Factor to account for voltage sag and safety margin (0.0 to 1.0).
        
    Returns:
        Flight time in minutes.
    """
    if power_watts <= 0:
        return 0.0
    
    # (Wh / Watts) * 60 minutes * efficiency factor
    flight_time_min = (battery_wh / power_watts) * 60 * sag_factor
    return round(flight_time_min, 2)

if __name__ == "__main__":
    # Test with GRIM-5 specs
    wh = 18.87
    # Assuming average power consumption for hover/light flight is ~150W for 5" racer
    avg_power = 150 
    print(f"Estimated flight time: {calculate_flight_time(wh, avg_power)} minutes")
