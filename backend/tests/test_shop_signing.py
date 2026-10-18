"""Webhook signature scheme shared with the shop (no database needed)."""

import unittest

from app.integrations import signing

SECRET = "s" * 40


class SigningTests(unittest.TestCase):
    def test_round_trip(self):
        body = b'{"id":"evt-1"}'
        sig = signing.sign(SECRET, 1_000_000, body)
        self.assertTrue(sig.startswith("sha256="))
        self.assertIsNone(signing.verify(SECRET, "1000000", sig, body, now=1_000_010))

    def test_rejections(self):
        body = b"{}"
        sig = signing.sign(SECRET, 1_000_000, body)
        self.assertEqual(signing.verify("", "1000000", sig, body, now=1_000_000), "not configured")
        self.assertEqual(signing.verify(SECRET, None, sig, body, now=1_000_000), "missing signature headers")
        self.assertEqual(signing.verify(SECRET, "abc", sig, body, now=1_000_000), "bad timestamp")
        self.assertEqual(signing.verify(SECRET, "1000000", sig, body, now=1_000_301), "timestamp too old or in the future")
        self.assertEqual(signing.verify(SECRET, "1000000", sig, b"{ }", now=1_000_000), "signature mismatch")
        self.assertEqual(signing.verify("t" * 40, "1000000", sig, body, now=1_000_000), "signature mismatch")


if __name__ == "__main__":
    unittest.main()
