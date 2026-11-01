import unittest
from fco.calculators.tax import calculate_tax, format_bp


class TaxTests(unittest.TestCase):
    def test_reference_image(self):
        result = calculate_tax(7600000000000, "svip", 30)
        self.assertEqual(result.net_bp, 6384000000000)
        self.assertEqual(result.tax_bp, 1216000000000)
        self.assertEqual(result.saved_bp, 1824000000000)
        self.assertEqual(result.tax_basis_points, 1600)

    def test_members_are_mutually_exclusive(self):
        for member, expected in [("none", 600000000), ("vip", 640000000), ("svip", 720000000)]:
            self.assertEqual(calculate_tax(10**9, member).net_bp, expected)

    def test_pc_optional_and_coupon_on_tax_not_price(self):
        self.assertEqual(calculate_tax(10**9, coupon_percent=30).net_bp, 720000000)
        self.assertEqual(calculate_tax(10**9, "svip", 30, True).net_bp, 960000000)
        self.assertEqual(calculate_tax(7600000000000, "svip", 30, True).net_bp, 7296000000000)

    def test_discounts_capped_and_large_integer_precision(self):
        huge = 99999999999999999999
        self.assertEqual(calculate_tax(huge, "svip", 100, True).net_bp, huge)
        self.assertEqual(calculate_tax(huge, "svip", 100, True).tax_bp, 0)
        self.assertEqual(calculate_tax(huge).net_bp, huge * 60 // 100)

    def test_rounding_and_balanced_breakdown(self):
        for price in (0, 1, 7, 101, 99999999999999999999):
            for coupon in (0, 10, 20, 30, 35, 40, 100):
                result = calculate_tax(price, "svip", coupon, True)
                self.assertEqual(result.net_bp + result.tax_bp, price)
                self.assertEqual(result.tax_bp + result.saved_bp, result.base_tax_bp)
                self.assertLessEqual(result.net_bp, price)
                self.assertGreaterEqual(result.tax_bp, 0)

    def test_invalid_inputs_and_vietnamese_format(self):
        for args in [
            (-1,),
            (1.5,),
            (True,),
            (1, "vvip"),
            (1, "none", 101),
            (1, "none", -1),
            (1, "none", 30.5),
            (1, "none", 30, "yes"),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                calculate_tax(*args)
        self.assertEqual(format_bp(6384000000000), "6.384.000.000.000")


if __name__ == "__main__":
    unittest.main()
