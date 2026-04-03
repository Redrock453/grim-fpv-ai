"""
Fresnel Zone Calculator
========================
Calculates Fresnel zone clearance for RF link reliability.

Key formula:
  r_n = sqrt(n * lambda * d1 * d2 / (d1 + d2))

Where:
  r_n    = radius of n-th Fresnel zone at point between TX and RX
  lambda = wavelength (c / f)
  d1, d2 = distances from TX and RX to the point

60% of first Fresnel zone must be clear for acceptable signal quality.
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

SPEED_OF_LIGHT = 299_792_458  # m/s


@dataclass
class FresnelResult:
    """Fresnel zone calculation result."""
    frequency_mhz: float
    total_distance_km: float
    wavelength_m: float

    # First Fresnel zone radius at midpoint (maximum)
    r1_max_m: float

    # 60% clearance radius
    r1_60_percent_m: float

    # Recommended minimum antenna heights
    min_height_operators_m: float   # with operator antenna height
    min_height_drone_m: float       # recommended drone flight height

    # At specific point along path
    r1_at_point_m: float

    # Whether link is viable
    link_viable: bool
    warnings: list


def calc_fresnel_zone(
    frequency_mhz: float,
    distance_km: float,
    operator_antenna_height_m: float = 4.0,
    drone_height_m: float = 60.0,
    terrain_obstacle_height_m: float = 0.0,
    point_distance_km: Optional[float] = None,
) -> FresnelResult:
    """
    Calculate Fresnel zone parameters for RF link.

    Args:
        frequency_mhz: Link frequency in MHz (e.g. 720, 5800)
        distance_km: Total link distance in km
        operator_antenna_height_m: Height of ground antenna
        drone_height_m: Planned drone flight height
        terrain_obstacle_height_m: Height of terrain/obstacles along path
        point_distance_km: Distance from TX to calculate radius at specific point
    """
    warnings = []

    # Wavelength
    wavelength_m = SPEED_OF_LIGHT / (frequency_mhz * 1e6)

    # Distance in meters
    d_total = distance_km * 1000

    # First Fresnel zone at midpoint (maximum radius)
    # r1 = sqrt(lambda * d / 2) at midpoint where d1 = d2 = d/2
    # Simplifies to: r1_max = sqrt(lambda * d_total / 2)
    # Wait, actually: r1 = sqrt(lambda * d1 * d2 / d_total) at midpoint d1=d2=d/2
    # r1_max = sqrt(lambda * (d/2) * (d/2) / d) = sqrt(lambda * d / 4)
    r1_max = math.sqrt(wavelength_m * d_total / 4)

    # 60% clearance
    r1_60 = r1_max * 0.6

    # Radius at specific point
    if point_distance_km is None:
        point_distance_km = distance_km / 2  # midpoint by default

    d1 = point_distance_km * 1000
    d2 = d_total - d1
    r1_at_point = math.sqrt(wavelength_m * d1 * d2 / d_total) if d2 > 0 else r1_max

    # Minimum required heights
    # The first Fresnel zone must clear terrain
    min_clearance = r1_60 + terrain_obstacle_height_m

    # Required drone height for LOS + Fresnel clearance
    # Accounting for Earth curvature: h_curve = d1*d2 / (2*R_earth) where R=6371km
    earth_curvature_m = (d1 * d2) / (2 * 6_371_000)
    min_drone_height = min_clearance + earth_curvature_m - operator_antenna_height_m
    min_drone_height = max(min_drone_height, r1_60 + terrain_obstacle_height_m)

    # Check if planned drone height is sufficient
    link_viable = drone_height_m >= (r1_60 + terrain_obstacle_height_m)

    if not link_viable:
        warnings.append(
            f"Drone height {drone_height_m}m below required "
            f"{r1_60 + terrain_obstacle_height_m:.0f}m for 60% Fresnel clearance"
        )

    # High frequency warning
    if frequency_mhz >= 5000:
        warnings.append(
            f"High frequency ({frequency_mhz}MHz) — especially vulnerable to "
            f"Fresnel zone obstruction. Consider lower frequency for long range."
        )

    # Long distance warning
    if distance_km > 10:
        warnings.append(
            f"Long range ({distance_km}km) — Earth curvature effect: "
            f"{earth_curvature_m:.1f}m. Plan altitude accordingly."
        )

    return FresnelResult(
        frequency_mhz=frequency_mhz,
        total_distance_km=distance_km,
        wavelength_m=wavelength_m,
        r1_max_m=round(r1_max, 2),
        r1_60_percent_m=round(r1_60, 2),
        min_height_operators_m=round(operator_antenna_height_m, 1),
        min_height_drone_m=round(min_drone_height, 1),
        r1_at_point_m=round(r1_at_point, 2),
        link_viable=link_viable,
        warnings=warnings,
    )


@dataclass
class HarmonicCheck:
    """Harmonic overlap analysis result."""
    video_freq_mhz: float
    control_freq_mhz: float
    video_harmonics: list      # [fundamental, 2nd, 3rd, ...]
    control_harmonics: list
    overlaps: list             # overlapping frequencies
    compatible: bool
    recommendation: str


def check_harmonic_overlap(
    video_freq_mhz: float,
    control_freq_mhz: float,
    video_bandwidth_mhz: float = 20.0,
    control_bandwidth_mhz: float = 2.0,
    num_harmonics: int = 5,
) -> HarmonicCheck:
    """
    Check for harmonic interference between video and control frequencies.

    When harmonics of one frequency overlap with another,
    interference occurs even with good frequency separation.
    """
    # Generate harmonics (n * f)
    video_harmonics = [video_freq_mhz * n for n in range(1, num_harmonics + 1)]
    control_harmonics = [control_freq_mhz * n for n in range(1, num_harmonics + 1)]

    overlaps = []
    for i, v_harm in enumerate(video_harmonics):
        for j, c_harm in enumerate(control_harmonics):
            # Check if within bandwidth of each other
            gap = abs(v_harm - c_harm)
            threshold = (video_bandwidth_mhz + control_bandwidth_mhz) / 2
            if gap < threshold:
                overlaps.append({
                    'video_harmonic': i + 1,
                    'video_freq': round(v_harm, 1),
                    'control_harmonic': j + 1,
                    'control_freq': round(c_harm, 1),
                    'gap_mhz': round(gap, 1),
                })

    compatible = len(overlaps) == 0

    if compatible:
        recommendation = (
            f"No harmonic overlap between {video_freq_mhz}MHz video "
            f"and {control_freq_mhz}MHz control. Safe to operate."
        )
    else:
        recommendation = (
            f"WARNING: {len(overlaps)} harmonic overlap(s) detected. "
            f"Consider changing video or control frequency."
        )

    return HarmonicCheck(
        video_freq_mhz=video_freq_mhz,
        control_freq_mhz=control_freq_mhz,
        video_harmonics=[round(h, 1) for h in video_harmonics],
        control_harmonics=[round(h, 1) for h in control_harmonics],
        overlaps=overlaps,
        compatible=compatible,
        recommendation=recommendation,
    )


@dataclass
class FrameRFImpact:
    """Frame material impact on RF performance."""

    material: str
    conductivity: str          # conductive / dielectric / mixed
    shielding_effect: str      # high / medium / low
    antenna_detune_pct: float  # % frequency shift
    swr_impact: str            # low / medium / high / critical
    gain_loss_db: float        # estimated gain loss
    recommendation: str


def analyze_frame_rf_impact(
    material: str,
    antenna_distance_mm: float = 20.0,
    frequency_ghz: float = 5.8,
) -> FrameRFImpact:
    """
    Analyze how frame material affects antenna performance.

    Materials:
      - carbon: conductive, creates parasitic currents, shields signal
      - aluminum: metal, full shielding, reflects
      - plastic/ABS: dielectric, shifts resonance
      - nylon: low dielectric, minimal impact
    """
    material = material.lower().strip()

    material_db = {
        'carbon': {
            'conductivity': 'conductive',
            'shielding': 'high',
            'detune_pct': 3.0,
            'swr': 'high',
            'gain_loss_db': 3.0,
            'detail': (
                'Carbon is conductive — creates parasitic currents, '
                'partially shields antenna. Antennas inside frame lose '
                'efficiency significantly. Always mount antennas OUTSIDE frame.'
            ),
        },
        'aluminum': {
            'conductivity': 'conductive',
            'shielding': 'high',
            'detune_pct': 1.5,
            'swr': 'medium',
            'gain_loss_db': 2.0,
            'detail': (
                'Aluminum fully shields and reflects. Good for EMI from ESC/motors '
                'but blocks antenna signal if too close. Minimum 30mm clearance recommended.'
            ),
        },
        'plastic': {
            'conductivity': 'dielectric',
            'shielding': 'low',
            'detune_pct': 2.0,
            'swr': 'medium',
            'gain_loss_db': 0.5,
            'detail': (
                'Plastic shifts antenna resonance due to dielectric permittivity. '
                'At 2.4-5.8GHz even few mm of plastic can detune antenna. '
                'Less shielding but more frequency drift.'
            ),
        },
        'abs': {
            'conductivity': 'dielectric',
            'shielding': 'low',
            'detune_pct': 2.0,
            'swr': 'medium',
            'gain_loss_db': 0.5,
            'detail': 'Same as plastic — dielectric, shifts resonance.',
        },
        'nylon': {
            'conductivity': 'dielectric',
            'shielding': 'low',
            'detune_pct': 0.5,
            'swr': 'low',
            'gain_loss_db': 0.2,
            'detail': (
                'Nylon has low dielectric constant — minimal RF impact. '
                'Best non-conductive frame material for antenna performance.'
            ),
        },
        'g10': {
            'conductivity': 'dielectric',
            'shielding': 'low',
            'detune_pct': 1.0,
            'swr': 'low',
            'gain_loss_db': 0.3,
            'detail': 'FR-4/G10 fiberglass — moderate dielectric, acceptable RF performance.',
        },
    }

    if material not in material_db:
        return FrameRFImpact(
            material=material,
            conductivity='unknown',
            shielding_effect='unknown',
            antenna_detune_pct=0.0,
            swr_impact='unknown',
            gain_loss_db=0.0,
            recommendation=f'Unknown material: {material}. Test antenna performance empirically.',
        )

    data = material_db[material]

    # Adjust based on antenna distance and frequency
    # Closer antenna = more impact
    distance_factor = max(0.5, min(2.0, 20.0 / max(antenna_distance_mm, 1.0)))
    # Higher frequency = more sensitive
    freq_factor = max(0.8, min(2.0, frequency_ghz / 2.4))

    adjusted_gain_loss = data['gain_loss_db'] * distance_factor * freq_factor
    adjusted_detune = data['detune_pct'] * distance_factor * freq_factor

    recommendation = data['detail']
    if antenna_distance_mm < 15 and data['conductivity'] == 'conductive':
        recommendation += (
            f'\nCRITICAL: Antenna only {antenna_distance_mm}mm from {material} — '
            f'MUST move antenna outside frame!'
        )

    return FrameRFImpact(
        material=material,
        conductivity=data['conductivity'],
        shielding_effect=data['shielding'],
        antenna_detune_pct=round(adjusted_detune, 1),
        swr_impact=data['swr'],
        gain_loss_db=round(adjusted_gain_loss, 1),
        recommendation=recommendation,
    )


@dataclass
class FiberOpticLink:
    """Fiber optic link analysis (alternative to RF)."""
    wavelength_nm: int          # 1310 or 1550
    distance_km: float
    signal_loss_db: float       # total link loss
    link_margin_db: float       # margin above sensitivity
    bandwidth_mbps: float
    viable: bool
    advantage: str


def analyze_fiber_optic_link(
    wavelength_nm: int = 1310,
    distance_km: float = 20.0,
    fiber_loss_db_per_km: float = 0.35,
    connector_loss_db: float = 1.0,
    splice_loss_db: float = 0.1,
    num_splices: int = 2,
    tx_power_dbm: float = -5.0,
    rx_sensitivity_dbm: float = -25.0,
) -> FiberOpticLink:
    """
    Analyze fiber optic link for FPV drone tethering.

    Advantage over RF:
      - No RF interference, EW-immune
      - No Fresnel zone concerns
      - No frequency coordination needed
      - Unlimited bandwidth for video + control

    Reference: BEASTFPV ground module (FPGA-based)
    """
    # Total fiber loss
    fiber_loss = fiber_loss_db_per_km * distance_km
    total_loss = fiber_loss + connector_loss_db + (splice_loss_db * num_splices)

    # Link budget
    received_power = tx_power_dbm - total_loss
    link_margin = received_power - rx_sensitivity_dbm

    viable = link_margin > 3.0  # 3dB minimum margin

    if viable:
        advantage = (
            f'Fiber optic link viable: {distance_km}km, '
            f'margin {link_margin:.1f}dB. '
            f'EW-immune, no RF interference, no Fresnel zone. '
            f'Video + control + telemetry over single fiber.'
        )
    else:
        advantage = (
            f'Fiber optic link marginal: {distance_km}km, '
            f'margin only {link_margin:.1f}dB. '
            f'Consider: higher TX power, lower loss fiber, or shorter distance.'
        )

    return FiberOpticLink(
        wavelength_nm=wavelength_nm,
        distance_km=distance_km,
        signal_loss_db=round(total_loss, 1),
        link_margin_db=round(link_margin, 1),
        bandwidth_mbps=1000,  # typical single-mode
        viable=viable,
        advantage=advantage,
    )


# --- Demo ---

def demo():
    print("=" * 60)
    print("FPV RF ENGINEERING CALCULATOR")
    print("=" * 60)

    # 1. Fresnel Zone (BEASTFPV example: 720MHz, 18km)
    print("\n1. FRESNEL ZONE — 720MHz control, 18km range")
    print("-" * 50)
    fresnel = calc_fresnel_zone(
        frequency_mhz=720,
        distance_km=18,
        operator_antenna_height_m=4,
        drone_height_m=80,
    )
    print(f"  Wavelength: {fresnel.wavelength_m:.3f}m")
    print(f"  R1 max (midpoint): {fresnel.r1_max_m:.1f}m")
    print(f"  60% clearance: {fresnel.r1_60_percent_m:.1f}m")
    print(f"  Min drone height: {fresnel.min_height_drone_m:.0f}m")
    print(f"  Link viable: {'YES' if fresnel.link_viable else 'NO'}")
    for w in fresnel.warnings:
        print(f"  Warning: {w}")

    # 2. Fresnel Zone — 5.8GHz video
    print("\n2. FRESNEL ZONE — 5.8GHz video, 18km range")
    print("-" * 50)
    fresnel_video = calc_fresnel_zone(
        frequency_mhz=5800,
        distance_km=18,
        operator_antenna_height_m=4,
        drone_height_m=80,
    )
    print(f"  R1 max: {fresnel_video.r1_max_m:.1f}m")
    print(f"  60% clearance: {fresnel_video.r1_60_percent_m:.1f}m")
    print(f"  Link viable: {'YES' if fresnel_video.link_viable else 'NO'}")

    # 3. Harmonic overlap
    print("\n3. HARMONIC OVERLAP — Video 5830MHz + Control 720MHz")
    print("-" * 50)
    harmonics = check_harmonic_overlap(5830, 720)
    print(f"  Video harmonics: {harmonics.video_harmonics}")
    print(f"  Control harmonics: {harmonics.control_harmonics}")
    print(f"  Overlaps: {len(harmonics.overlaps)}")
    print(f"  Compatible: {'YES' if harmonics.compatible else 'NO'}")
    print(f"  {harmonics.recommendation}")

    # 4. Frame RF impact
    print("\n4. FRAME RF IMPACT")
    print("-" * 50)
    for mat in ['carbon', 'aluminum', 'plastic', 'nylon']:
        impact = analyze_frame_rf_impact(mat, antenna_distance_mm=15, frequency_ghz=5.8)
        print(f"  {mat:10s}: gain_loss={impact.gain_loss_db:.1f}dB, "
              f"detune={impact.antenna_detune_pct:.1f}%, "
              f"SWR={impact.swr_impact}")

    # 5. Fiber optic
    print("\n5. FIBER OPTIC LINK — 20km, 1310nm")
    print("-" * 50)
    fiber = analyze_fiber_optic_link(distance_km=20)
    print(f"  Loss: {fiber.signal_loss_db:.1f}dB")
    print(f"  Margin: {fiber.link_margin_db:.1f}dB")
    print(f"  Viable: {'YES' if fiber.viable else 'NO'}")
    print(f"  {fiber.advantage}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    demo()
