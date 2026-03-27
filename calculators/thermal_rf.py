def calculate_rf_thermal(p_out_watts: float, efficiency: float = 0.4) -> dict:
    """
    Calculates heat dissipation for an RF Amplifier.
    
    Args:
        p_out_watts: Output RF power (e.g., 30W).
        efficiency: PAE (Power Added Efficiency), typically 30-50% for AB class.
        
    Returns:
        Dictionary with P_in, P_dissipated (Heat), and recommendations.
    """
    if efficiency <= 0 or efficiency > 1:
        efficiency = 0.4
        
    p_total_in = p_out_watts / efficiency
    p_heat = p_total_in - p_out_watts
    
    return {
        "p_out_watts": p_out_watts,
        "p_total_in_watts": round(p_total_in, 2),
        "p_heat_watts": round(p_heat, 2),
        "efficiency_pct": efficiency * 100,
        "status": "Critical Heat" if p_heat > 10 else "Manageable"
    }

if __name__ == "__main__":
    # 30W Booster, 40% efficiency
    res = calculate_rf_thermal(30, 0.4)
    print(f"Heat to dissipate: {res['p_heat_watts']} Watts")
