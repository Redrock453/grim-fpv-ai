# Hover Current Calculation for GRIM-5

def calculate_hover_current(weight_g: float, thrust_kg: float, max_current_a: float) -> float:
    """
    Estimates hover current based on weight and thrust-to-weight ratio.
    
    Args:
        weight_g: Total weight of the drone in grams.
        thrust_kg: Total max thrust of the drone in kg.
        max_current_a: Total max current at max thrust in Amps.
        
    Returns:
        Estimated hover current in Amps.
    """
    if thrust_kg <= 0:
        return 0.0
    
    # Thrust needed for hover = weight (converted to kg)
    hover_thrust_kg = weight_g / 1000.0
    
    # Linear estimation of current (simplistic)
    # Current = (Hover Thrust / Max Thrust) * Max Current
    hover_current_a = (hover_thrust_kg / thrust_kg) * max_current_a
    
    return round(hover_current_a, 2)

if __name__ == "__main__":
    # GRIM-5: 865g, 4.2kg thrust, 4*45A = 180A max
    w = 865
    t = 4.2
    m = 180
    print(f"Estimated hover current: {calculate_hover_current(w, t, m)} A")
