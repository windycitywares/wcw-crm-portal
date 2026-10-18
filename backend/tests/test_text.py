"""Tests for shared text helpers."""

import unittest

try:
    from app.shared.text import phone_digits, slugify
except (ImportError, RuntimeError):
    phone_digits = slugify = None


@unittest.skipIf(phone_digits is None, "backend not installed")
class TextTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Marketplace (Etsy/Amazon)"), "marketplace_etsy_amazon")
        self.assertEqual(slugify("UPPER case"), "upper_case")
        self.assertEqual(slugify("  spaced  "), "spaced")
        self.assertEqual(slugify("🎉 emoji"), "emoji")
        self.assertEqual(slugify("a" * 100), "a" * 60)

    def test_phone_digits_basic(self):
        self.assertEqual(phone_digits("(312) 555-0142"), "3125550142")
        self.assertEqual(phone_digits("312-555-0142"), "3125550142")
        self.assertEqual(phone_digits("+1 312 555 0142"), "3125550142")
        self.assertEqual(phone_digits("13125550142"), "3125550142")  # E.164 with leading 1 dropped

    def test_phone_digits_not_nanp(self):
        self.assertEqual(phone_digits("+44 20 7946 0958"), "442079460958")  # UK, 1 not dropped
        self.assertEqual(phone_digits("+33 1 23 45 67 89"), "33123456789")  # France

    def test_phone_digits_edge_cases(self):
        self.assertEqual(phone_digits(""), "")
        self.assertEqual(phone_digits(None), "")
        self.assertEqual(phone_digits("   "), "")
        self.assertEqual(phone_digits("123"), "123")  # too short to be NANP
        self.assertEqual(phone_digits("1" * 11), "1" * 10)  # eleven 1s → drop first
        self.assertEqual(phone_digits("1" * 10), "1" * 10)  # ten 1s → keep all

    def test_phone_forms(self):
        from app.modules.customers.repository import phone_forms

        self.assertEqual(set(phone_forms("(312) 555-0142")), {"3125550142", "13125550142"})
        self.assertEqual(set(phone_forms("+13125550142")), {"3125550142", "13125550142"})
        self.assertEqual(set(phone_forms("+44 20 7946 0958")), {"442079460958"})
        self.assertEqual(phone_forms(""), [])


if __name__ == "__main__":
    unittest.main()