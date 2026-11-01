import unittest
from fco.pricing import parse_bp, parse_label, Quote, permits, may_qualify, ChangeDetector


class PricingTests(unittest.TestCase):
    def test_integer_precision_and_display_resolution(self):
        self.assertEqual(parse_bp("9.999.999.999.999.999"), 9999999999999999)
        self.assertEqual(parse_label("7.8B").value, 7800000000)
        self.assertEqual(parse_label("7.8B").quantum, 100000000)
        self.assertEqual(parse_label("471M").value, 471000000)
        for text in ("O.8B", "7 8B", "1.5T", "-1"):
            with self.assertRaises(ValueError):
                parse_bp(text)

    def test_compact_quote_is_only_precheck_full_price_enforces_cap(self):
        label = parse_label("9.3B")
        self.assertTrue(may_qualify("buy", label, 9250000000))
        self.assertFalse(permits("buy", 9300000000, 9250000000))
        self.assertFalse(permits("sell", 7800000000, 7900000000))
        self.assertFalse(label.contains(7800000000))

    def test_stable_baseline_and_change(self):
        old = Quote(parse_label("7.8B"), parse_label("9.3B"))
        new = Quote(parse_label("7.9B"), parse_label("9.4B"))
        detector = ChangeDetector()
        self.assertFalse(detector.observe(old))
        self.assertFalse(detector.observe(old))
        self.assertFalse(detector.observe(new))
        detector.invalidate()
        self.assertFalse(detector.observe(new))
        self.assertTrue(detector.observe(new))
        self.assertFalse(detector.observe(new))
