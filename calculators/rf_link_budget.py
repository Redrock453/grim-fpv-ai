import math

def calculate_path_loss(freq_mhz: float, distance_km: float) -> float:
    """
    Free Space Path Loss (FSPL) calculation.
    Formula: FSPL (dB) = 20log10(d) + 20log10(f) + 32.44
    """
    if distance_km <= 0: return 0.0
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44

def calculate_link_budget(tx_power_dbm: float, tx_gain_dbi: float, rx_gain_dbi: float, path_loss_db: float, fade_margin_db: float = 10.0) -> float:
    """
    Calculates received signal strength (RSSI) in dBm.
    """
    return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - path_loss_db - fade_margin_db

def watts_to_dbm(watts: float) -> float:
    if watts <= 0: return -999.0
    return 10 * math.log10(watts * 1000)

if __name__ == "__main__":
    # Test for 30W Booster
    p_watts = 30.0
    p_dbm = watts_to_dbm(p_watts)
    freq = 433.0
    dist = 50.0 # 50km
    
    loss = calculate_path_loss(freq, dist)
    rssi = calculate_link_budget(p_dbm, 4.0, 2.0, loss)
    
    print(f"30W is {p_dbm:.2f} dBm")
    print(f"Path Loss at {dist}km ({freq}MHz): {loss:.2f} dB")
    print(f"Estimated RSSI: {rssi:.2f} dBm")
