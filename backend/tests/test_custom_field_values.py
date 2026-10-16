"""Custom field value validation — pure, no database."""

import unittest
from types import SimpleNamespace as F

try:
    from app.core.exceptions import ValidationFailedError
    from app.modules.customfields.validation import check_values
except ImportError:  # pragma: no cover - fastapi missing
    check_values = None


def field(key, field_type, **kw):
    return F(key=key, label=kw.pop("label", key.title()), field_type=field_type, options=kw.pop("options", None),
             required=kw.pop("required", False), is_active=kw.pop("is_active", True))


DEFS = [
    field("size", "select", options=["Small", "Large"]),
    field("colours", "multiselect", options=["Red", "Green", "Blue"]),
    field("budget", "number"),
    field("birthday", "date"),
    field("vip", "checkbox"),
    field("site", "url"),
    field("billing", "email"),
    field("nickname", "text"),
    field("old", "text", is_active=False),
    field("account", "text", required=True, label="Account no."),
]


@unittest.skipIf(check_values is None, "fastapi not installed")
class CheckValuesTests(unittest.TestCase):
    def ok(self, incoming, existing=None):
        return check_values(DEFS, {"account": "A1", **incoming}, existing)

    def bad(self, incoming, existing=None, contains=""):
        with self.assertRaises(ValidationFailedError) as ctx:
            check_values(DEFS, incoming, existing)
        self.assertIn(contains, ctx.exception.message)

    def test_normalises_values(self):
        out = self.ok({"size": "Large", "colours": ["Blue", "Red", "Blue"], "budget": "12.50", "birthday": "1990-05-04T00:00",
                       "vip": "true", "site": "https://x.example", "billing": " Ann@Example.COM ", "nickname": "  Annie "})
        self.assertEqual(out["colours"], ["Red", "Blue"])
        self.assertEqual(out["budget"], 12.5)
        self.assertEqual(self.ok({"budget": "40"})["budget"], 40)
        self.assertEqual(out["birthday"], "1990-05-04")
        self.assertIs(out["vip"], True)
        self.assertEqual(out["billing"], "ann@example.com")
        self.assertEqual(out["nickname"], "Annie")

    def test_rejects_bad_values_and_lists_all_problems(self):
        self.bad({"account": "A", "size": "Huge", "budget": "lots", "site": "x.example"}, contains="Size must be one of")
        with self.assertRaises(ValidationFailedError) as ctx:
            check_values(DEFS, {"account": "A", "size": "Huge", "budget": "lots"}, None)
        self.assertIn("Budget must be a number", ctx.exception.message)
        self.bad({"account": "A", "vip": "maybe"}, contains="Vip must be yes or no")
        self.bad({"account": "A", "budget": True}, contains="Budget must be a number")
        self.bad({"account": "A", "budget": "nan"}, contains="Budget must be a number")
        self.bad({"account": "A", "colours": "Red"}, contains="list of options")
        self.bad({"account": "A", "billing": "nope"}, contains="email address")
        self.bad({"account": "A", "nickname": "x" * 256}, contains="at most 255")

    def test_unknown_and_inactive_fields(self):
        self.bad({"account": "A", "shoe": "9"}, contains="shoe: unknown field")
        self.bad({"account": "A", "old": "new"}, existing={"old": "kept"}, contains="no longer in use")
        self.assertEqual(self.ok({"old": "kept"}, existing={"old": "kept"})["old"], "kept")

    def test_required_and_clearing(self):
        self.bad({}, contains="Account no. is required")
        self.bad({"account": ""}, existing={"account": "A1"}, contains="Account no. is required")
        self.assertEqual(check_values(DEFS, {}, {"account": "A1"}), {"account": "A1"})  # partial update keeps it
        out = self.ok({"nickname": ""}, existing={"nickname": "Annie", "account": "A1"})
        self.assertNotIn("nickname", out)

    def test_required_field_with_bad_value_reports_once(self):
        with self.assertRaises(ValidationFailedError) as ctx:
            check_values([field("n", "number", required=True)], {"n": "x"}, None)
        self.assertEqual(ctx.exception.message, "N must be a number")


if __name__ == "__main__":
    unittest.main()
