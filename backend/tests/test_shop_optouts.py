"""Which audit rows mean "this address left the list" (pure rule, no database)."""

import unittest
from types import SimpleNamespace as NS

from app.integrations.shop.optouts import opt_out_email


def row(action, **changes):
    return NS(action=action, changes=changes or None)


def contact(email="Ana@Example.com", subscribed=True, types=("subscriber",)):
    return NS(email=email, subscribed_at=object() if subscribed else None, types=list(types))


class OptOutRuleTests(unittest.TestCase):
    def test_suppressions_and_staff_unsubscribes_count(self):
        self.assertEqual(opt_out_email(row("suppression.create", email="X@Example.com"), None), "x@example.com")
        self.assertEqual(opt_out_email(row("contact.update", via="unsubscribe"), contact()), "ana@example.com")
        self.assertEqual(opt_out_email(row("contact.update", via="remove"), contact()), "ana@example.com")

    def test_the_shop_s_own_changes_and_other_edits_do_not(self):
        self.assertIsNone(opt_out_email(row("contact.update", via="shop", newsletter=["subscribed", "unsubscribed"]), contact()))
        self.assertIsNone(opt_out_email(row("contact.update", via="pause"), contact()))
        self.assertIsNone(opt_out_email(row("contact.update", phone=["1", "2"]), contact()))

    def test_deleting_only_counts_for_someone_on_the_list(self):
        self.assertEqual(opt_out_email(row("contact.delete"), contact()), "ana@example.com")
        self.assertIsNone(opt_out_email(row("contact.delete"), contact(subscribed=False, types=("customer",))))
        self.assertIsNone(opt_out_email(row("contact.delete"), contact(email=None)))
        self.assertIsNone(opt_out_email(row("contact.delete"), None))

    def test_staff_taking_back_a_customer_s_consent_counts(self):
        cust = NS(email="Bo@Example.com")
        self.assertEqual(opt_out_email(row("customer.update", marketing_consent=[True, False]), cust), "bo@example.com")
        self.assertIsNone(opt_out_email(row("customer.update", marketing_consent=[False, True]), cust))
        self.assertIsNone(opt_out_email(row("customer.update", phone=["1", "2"]), cust))


if __name__ == "__main__":
    unittest.main()
