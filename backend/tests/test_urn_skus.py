"""Pure tests: the SKU template and reading sizes from Etsy variation names."""

import unittest

try:
    from app.modules.urns import reading, skus
except (ImportError, RuntimeError):
    reading = skus = None

SIZES = [] if reading is None else [reading.Size("10", ("large", "adult")), reading.Size("3", ("keepsake", "keepsakes", "mini"))]


@unittest.skipIf(skus is None, "backend not installed")
class SkuTemplateTests(unittest.TestCase):
    def test_default_format_renders_and_reads_back(self):
        f = skus.SkuFormat()
        self.assertEqual(skus.check(f, size_codes=["10", "3"]), [])
        sku = skus.render(f, supplier_id=7, urn_id=345, sizes=[("10", 1), ("3", 3)])
        self.assertEqual(sku, "WCW-007-0345-10x1-3x3")
        self.assertEqual(skus.read(f, sku, ["10", "3"]), {"supplier": 7, "urn": 345, "sizes": {"10": 1, "3": 3}, "option": None})
        self.assertEqual(skus.render(f, supplier_id=7, urn_id=345, sizes=[("10", 0), ("3", 4)]), "WCW-007-0345-3x4")
        with_option = skus.render(f, supplier_id=7, urn_id=345, sizes=[("10", 1)], option="BLU")
        self.assertEqual(skus.read(f, with_option, ["10", "3"])["option"], "BLU")
        self.assertIsNone(skus.read(f, "SOMETHING-ELSE", ["10", "3"]))

    def test_template_rules(self):
        self.assertTrue(skus.check(skus.SkuFormat(template="WCW-{urn:4}"), size_codes=["10"]))
        self.assertTrue(skus.check(skus.SkuFormat(template="WCW-{supplier}-{urn:4}-{sizes}"), size_codes=["10"]))
        self.assertTrue(skus.check(skus.SkuFormat(template="WCW {supplier:3}-{urn:4}-{sizes}"), size_codes=["10"]))
        self.assertTrue(skus.check(skus.SkuFormat(size_format="{code}{qty}"), size_codes=["10"]))
        problems = skus.check(skus.SkuFormat(), size_codes=["10", "3"], max_supplier=1234)
        self.assertIn("raise {supplier:3}", problems[0])
        long = skus.SkuFormat(template="WINDYCITYWARES-{supplier:5}-{urn:6}-{sizes}{-option}")
        self.assertTrue(any("Etsy allows 32" in p for p in skus.check(long, size_codes=["10", "3"])))
        custom = skus.SkuFormat(template="U{urn:3}.S{supplier:2}.{sizes}", size_format="{qty}at{code}", separator="_")
        sku = skus.render(custom, supplier_id=4, urn_id=12, sizes=[("10", 1), ("3", 2)])
        self.assertEqual(sku, "U012.S04.1at10_2at3")
        self.assertEqual(skus.read(custom, sku, ["10", "3"])["sizes"], {"10": 1, "3": 2})


@unittest.skipIf(reading is None, "backend not installed")
class ReadingTests(unittest.TestCase):
    def test_names(self):
        cases = {
            "10 inch Large": {"10": 1},
            "3 inch Keepsake": {"3": 1},
            "Set of 2 Keepsakes (3 inch)": {"3": 2},
            "Set of 4 Keepsakes (3 inch)": {"3": 4},
            "10 inch + 2 Keepsakes": {"10": 1, "3": 2},
            "Large 10\" Urn & Set of 4 3\" Keepsakes": {"10": 1, "3": 4},
            "Two Keepsakes": {"3": 2},
            "1 Large 2 keepsake": {"10": 1, "3": 2},
            "1 Large 4 Keepsake": {"10": 1, "3": 4},
            "3 inch set of 4": {"3": 4},
        }
        for text, want in cases.items():
            got = reading.read(text, SIZES)
            self.assertEqual(got.quantities, want, text)
            self.assertTrue(got.clear, text)

    def test_unclear_is_never_guessed(self):
        self.assertFalse(reading.read("Blue", SIZES).clear)
        self.assertFalse(reading.read("7 inch", SIZES).clear)
        twelve = reading.read("12 Inch Extra Large", SIZES)  # "large" must not make a 12 inch a 10 inch
        self.assertEqual((twelve.quantities, twelve.clear), ({}, False))
        self.assertIn("12 inch", twelve.note)
        self.assertFalse(reading.read("", SIZES).clear)

    def test_keys_and_names(self):
        self.assertEqual(reading.options_key({"Size": "10 inch", "Color": "Blue"}),
                         reading.options_key([{"name": "Color", "value": "blue"}, {"name": "size", "value": "10 Inch"}]))
        self.assertEqual(reading.options_key({}), "")
        self.assertEqual(reading.short_name("Sea Turtle Urn - Hand painted | Keepsake"), "Sea Turtle Urn")
