import unittest
from calculators.flight_time_calc import calculate_flight_time

class TestCalculations(unittest.TestCase):
    def test_flight_time(self):
        # 18.87Wh / 150W * 60min * 0.85 = ~6.41min
        result = calculate_flight_time(18.87, 150, 0.85)
        self.assertGreater(result, 6)
        self.assertLess(result, 7)

    def test_zero_power(self):
        self.assertEqual(calculate_flight_time(18.87, 0), 0.0)

if __name__ == "__main__":
    unittest.main()
