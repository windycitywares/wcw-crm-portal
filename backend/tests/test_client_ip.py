"""Which address the rate limits count a request under: a caller must not be able to choose it."""

import unittest

from app.core.client_ip import is_internal, pick_ip

OWN = frozenset({"192.0.2.10"})  # this server's public address


class PickIpTests(unittest.TestCase):
    def test_a_visitor_cannot_choose_their_address(self):
        # Connects from the internet and claims to be someone else: counted under where it connected from.
        self.assertEqual(pick_ip("198.51.100.7", "203.0.113.77", OWN), "198.51.100.7")
        self.assertEqual(pick_ip("198.51.100.7", "203.0.113.1, 203.0.113.2", OWN), "198.51.100.7")
        self.assertEqual(pick_ip("198.51.100.7", None, OWN), "198.51.100.7")

    def test_our_own_server_may_say_who_it_acts_for(self):
        # The main site's server calls the API for a visitor, from this machine.
        self.assertEqual(pick_ip("192.0.2.10", "203.0.113.5", OWN), "203.0.113.5")
        self.assertEqual(pick_ip("127.0.0.1", "203.0.113.5", OWN), "203.0.113.5")
        self.assertEqual(pick_ip("::1", "203.0.113.5", OWN), "203.0.113.5")

    def test_behind_a_local_proxy_the_right_most_outside_address_wins(self):
        # A proxy appends the real address; whatever the caller wrote comes before it.
        self.assertEqual(pick_ip("127.0.0.1", "6.6.6.6, 203.0.113.5", OWN), "203.0.113.5")
        self.assertEqual(pick_ip("127.0.0.1", "203.0.113.5, 192.0.2.10, 10.0.0.3", OWN), "203.0.113.5")

    def test_nothing_usable_falls_back_to_the_peer(self):
        self.assertEqual(pick_ip("127.0.0.1", None, OWN), "127.0.0.1")
        self.assertEqual(pick_ip("127.0.0.1", "not-an-address, ", OWN), "127.0.0.1")
        self.assertEqual(pick_ip(None, None, OWN), "unknown")

    def test_a_local_transport_is_not_a_visitor(self):
        self.assertEqual(pick_ip("testclient", "203.0.113.9", OWN), "203.0.113.9")

    def test_internal_addresses(self):
        for a in ("127.0.0.1", "10.1.2.3", "192.168.1.1", "::1", "169.254.1.1"):
            self.assertTrue(is_internal(a), a)
        for a in ("203.0.113.5", "8.8.8.8", "nonsense", ""):
            self.assertFalse(is_internal(a), a)


if __name__ == "__main__":
    unittest.main()
