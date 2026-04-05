import unittest
import math
from calculators.flight_time_calc import calculate_flight_time
from calculators.hover_current import calculate_hover_current
from calculators.rf_link_budget import calculate_path_loss, calculate_link_budget, watts_to_dbm
from calculators.thermal_rf import calculate_rf_thermal
from calculators.thermal_analysis import calculate_thermal
from calculators.pid_tuning import recommend_pid
from calculators.range_calc import calculate_range, mw_to_dbm, fspl_db, calculate_range_table
from calculators.fresnel_zone import calc_fresnel_zone, check_harmonic_overlap, analyze_frame_rf_impact


class TestFlightTime(unittest.TestCase):
    def test_flight_time_normal(self):
        result = calculate_flight_time(18.87, 150, 0.85)
        self.assertGreater(result, 6)
        self.assertLess(result, 7)

    def test_zero_power(self):
        self.assertEqual(calculate_flight_time(18.87, 0), 0.0)

    def test_negative_power(self):
        self.assertEqual(calculate_flight_time(18.87, -10), 0.0)

    def test_high_capacity_battery(self):
        result = calculate_flight_time(50.0, 100, 0.9)
        self.assertAlmostEqual(result, 27.0, places=1)


class TestHoverCurrent(unittest.TestCase):
    def test_grim5_hover(self):
        result = calculate_hover_current(865, 4.2, 180)
        self.assertGreater(result, 0)
        self.assertLess(result, 180)

    def test_zero_thrust(self):
        self.assertEqual(calculate_hover_current(500, 0, 100), 0.0)

    def test_light_drone(self):
        result = calculate_hover_current(300, 2.0, 80)
        self.assertAlmostEqual(result, 12.0, places=1)

    def test_hover_less_than_max(self):
        result = calculate_hover_current(500, 5.0, 200)
        self.assertLess(result, 200)


class TestRfLinkBudget(unittest.TestCase):
    def test_fspl_24ghz_1km(self):
        loss = calculate_path_loss(2400, 1.0)
        self.assertAlmostEqual(loss, 100.0, places=1)

    def test_fspl_433mhz_50km(self):
        loss = calculate_path_loss(433, 50.0)
        self.assertGreater(loss, 100)

    def test_fspl_zero_distance(self):
        self.assertEqual(calculate_path_loss(2400, 0), 0.0)

    def test_fspl_negative_distance(self):
        self.assertEqual(calculate_path_loss(2400, -1), 0.0)

    def test_link_budget_strong_signal(self):
        rssi = calculate_link_budget(27, 3, 3, 100, 10)
        self.assertAlmostEqual(rssi, -77.0, places=1)

    def test_watts_to_dbm_1w(self):
        self.assertAlmostEqual(watts_to_dbm(1.0), 30.0, places=1)

    def test_watts_to_dbm_30w(self):
        self.assertAlmostEqual(watts_to_dbm(30.0), 44.77, places=2)

    def test_watts_to_dbm_zero(self):
        self.assertEqual(watts_to_dbm(0), -999.0)

    def test_watts_to_dbm_negative(self):
        self.assertEqual(watts_to_dbm(-1), -999.0)


class TestThermalRf(unittest.TestCase):
    def test_30w_amplifier(self):
        result = calculate_rf_thermal(30, 0.4)
        self.assertEqual(result["p_out_watts"], 30)
        self.assertGreater(result["p_heat_watts"], 10)
        self.assertEqual(result["status"], "Critical Heat")

    def test_low_power(self):
        result = calculate_rf_thermal(1, 0.5)
        self.assertEqual(result["status"], "Manageable")

    def test_invalid_efficiency(self):
        result = calculate_rf_thermal(10, 0)
        self.assertEqual(result["efficiency_pct"], 40)

    def test_invalid_efficiency_high(self):
        result = calculate_rf_thermal(10, 1.5)
        self.assertEqual(result["efficiency_pct"], 40)

    def test_efficiency_100(self):
        result = calculate_rf_thermal(10, 1.0)
        self.assertAlmostEqual(result["p_heat_watts"], 0.0, places=2)


class TestThermalAnalysis(unittest.TestCase):
    def test_normal_current(self):
        result = calculate_thermal(15.0, 25.0)
        self.assertGreater(result["esc_temp_c"], 25)
        self.assertGreater(result["motor_temp_c"], 25)

    def test_esc_overheat(self):
        result = calculate_thermal(30.0, 25.0)
        self.assertNotEqual(result["warning"], "OK")
        esc_temp = result["esc_temp_c"]
        motor_temp = result["motor_temp_c"]
        self.assertTrue(esc_temp > 85 or motor_temp > 95)

    def test_motor_overheat(self):
        result = calculate_thermal(25.0, 25.0)
        self.assertIn("Мотор", result["warning"])

    def test_ok_at_low_current(self):
        result = calculate_thermal(5.0, 25.0)
        self.assertEqual(result["warning"], "OK")

    def test_cold_ambient(self):
        result = calculate_thermal(15.0, -10.0)
        self.assertGreater(result["esc_temp_c"], -10)


class TestPidTuning(unittest.TestCase):
    def test_default_2000kv(self):
        result = recommend_pid(2000, "5045", 865)
        self.assertEqual(result["roll"]["P"], 45)
        self.assertEqual(result["roll"]["I"], 35)
        self.assertEqual(result["roll"]["D"], 22)

    def test_high_kv(self):
        result = recommend_pid(2400, "5045", 865)
        self.assertGreater(result["roll"]["P"], 45)

    def test_pitch_higher_than_roll(self):
        result = recommend_pid(2000, "5045", 865)
        self.assertGreater(result["pitch"]["P"], result["roll"]["P"])

    def test_yaw_values(self):
        result = recommend_pid(2000, "5045", 865)
        self.assertEqual(result["yaw"]["P"], 30)
        self.assertEqual(result["yaw"]["I"], 25)
        self.assertEqual(result["yaw"]["D"], 0)


class TestRangeCalc(unittest.TestCase):
    def test_expresslrs_500mw(self):
        result = calculate_range(tx_power_mw=500, frequency_mhz=2400)
        self.assertGreater(result["range_km"], 0)
        self.assertGreater(result["realistic_range_km"], 0)
        self.assertLessEqual(result["realistic_range_km"], result["range_km"])

    def test_900mhz_longer_range(self):
        result_900 = calculate_range(tx_power_mw=500, frequency_mhz=900)
        result_2400 = calculate_range(tx_power_mw=500, frequency_mhz=2400)
        self.assertGreater(result_900["range_km"], result_2400["range_km"])

    def test_higher_power_more_range(self):
        result_1w = calculate_range(tx_power_mw=1000)
        result_500mw = calculate_range(tx_power_mw=500)
        self.assertGreater(result_1w["range_km"], result_500mw["range_km"])

    def test_zero_power(self):
        result = calculate_range(tx_power_mw=0)
        self.assertEqual(result["range_km"], 0.0)

    def test_tx_power_dbm_conversion(self):
        result = calculate_range(tx_power_mw=500)
        self.assertAlmostEqual(result["tx_power_dbm"], 27.0, places=1)

    def test_fspl_24ghz_1km(self):
        loss = fspl_db(1.0, 2400)
        self.assertAlmostEqual(loss, 100.0, places=1)

    def test_fspl_formula_inversion(self):
        loss = fspl_db(10.0, 2400)
        expected = 20 * math.log10(10) + 20 * math.log10(2400) + 32.44
        self.assertAlmostEqual(loss, expected, places=2)

    def test_mw_to_dbm_500mw(self):
        self.assertAlmostEqual(mw_to_dbm(500), 27.0, places=1)

    def test_mw_to_dbm_1mw(self):
        self.assertAlmostEqual(mw_to_dbm(1), 0.0, places=1)

    def test_mw_to_dbm_zero(self):
        self.assertEqual(mw_to_dbm(0), -999.0)

    def test_range_table(self):
        table = calculate_range_table(tx_power_mw=500, frequency_mhz=2400)
        self.assertGreater(len(table), 0)
        self.assertEqual(table[0]["distance_km"], 0.1)
        self.assertIn("rssi_dbm", table[0])
        self.assertIn("signal", table[0])

    def test_range_table_signal_degrades(self):
        table = calculate_range_table(tx_power_mw=500, frequency_mhz=2400)
        first_rssi = table[0]["rssi_dbm"]
        last_rssi = table[-1]["rssi_dbm"]
        self.assertGreater(first_rssi, last_rssi)


class TestFresnelZone(unittest.TestCase):
    def test_720mhz_18km(self):
        result = calc_fresnel_zone(frequency_mhz=720, distance_km=18, drone_height_m=80)
        self.assertGreater(result.r1_max_m, 0)
        self.assertGreater(result.r1_60_percent_m, 0)

    def test_high_frequency_smaller_zone(self):
        r1_720 = calc_fresnel_zone(frequency_mhz=720, distance_km=10)
        r1_5800 = calc_fresnel_zone(frequency_mhz=5800, distance_km=10)
        self.assertGreater(r1_720.r1_max_m, r1_5800.r1_max_m)

    def test_long_distance_warning(self):
        result = calc_fresnel_zone(frequency_mhz=720, distance_km=15)
        self.assertTrue(any("Earth curvature" in w for w in result.warnings))

    def test_high_freq_warning(self):
        result = calc_fresnel_zone(frequency_mhz=5800, distance_km=5)
        self.assertTrue(any("High frequency" in w for w in result.warnings))


class TestHarmonicOverlap(unittest.TestCase):
    def test_no_overlap_wide_separation(self):
        result = check_harmonic_overlap(5800, 720)
        self.assertTrue(result.compatible)

    def test_overlap_close_frequencies(self):
        result = check_harmonic_overlap(1200, 600)
        self.assertFalse(result.compatible)


class TestFrameRfImpact(unittest.TestCase):
    def test_carbon_frame(self):
        result = analyze_frame_rf_impact("carbon")
        self.assertEqual(result.conductivity, "conductive")
        self.assertGreater(result.gain_loss_db, 0)

    def test_nylon_frame(self):
        result = analyze_frame_rf_impact("nylon")
        self.assertLess(result.gain_loss_db, 1.0)

    def test_unknown_material(self):
        result = analyze_frame_rf_impact("titanium")
        self.assertEqual(result.conductivity, "unknown")

    def test_close_antenna_warning(self):
        result = analyze_frame_rf_impact("carbon", antenna_distance_mm=5)
        self.assertIn("CRITICAL", result.recommendation)


if __name__ == "__main__":
    unittest.main()
