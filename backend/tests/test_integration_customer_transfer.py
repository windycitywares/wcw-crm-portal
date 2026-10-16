"""Customer export (CSV/Excel) and import (CSV/Excel, dry run, skip/update, row errors)."""

import csv
import io
import unittest

from tests.support import API, World, reset_limits, run, skip_unless_db


@skip_unless_db
class CustomerTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda s: LookupService(s).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager", full_name=f"Mona Manager {cls.w.sfx}")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")

    def setUp(self):
        reset_limits()

    def upload(self, text, *, mode="skip", dry_run=True, name="people.csv", headers=None):
        return self.w.client.post(f"{API}/customers/import", headers=headers or self.manager_h,
                                  files={"file": (name, text.encode() if isinstance(text, str) else text)},
                                  data={"mode": mode, "dry_run": str(dry_run).lower()})

    def find(self, email):
        return self.w.client.get(f"{API}/customers/check-email", headers=self.manager_h, params={"email": email}).json()["customer_id"]

    def get(self, cid):
        return self.w.client.get(f"{API}/customers/{cid}", headers=self.manager_h).json()

    def test_permissions(self):
        self.assertEqual(self.w.client.get(f"{API}/customers/export", headers=self.sales_h).status_code, 403)
        self.assertEqual(self.upload("email\nx@example.com", headers=self.sales_h).status_code, 403)

    def test_import_dry_run_then_real_with_errors_and_tags(self):
        a, b, c = self.w.email("imp-a"), self.w.email("imp-b"), self.w.email("imp-c")
        text = (
            "Name,E-mail address,Company,Customer type,Lead source,Tags,City,Zip,Owner\n"
            f"Ada Lovelace,{a},Engines Ltd,VIP,Etsy,\"gift; wholesale\",Chicago,60601,{self.manager['email']}\n"
            f"Bob Bad,{b},,Not a type,,,,,\n"
            f",not-an-email,,,,,,,\n"
            f"Cy Twice,{c},,,,,,,\n"
            f"Cy Again,{c.upper()},,,,,,,\n"
        )
        dry = self.upload(text)
        self.assertEqual(dry.status_code, 200, dry.text)
        d = dry.json()
        self.assertEqual((d["dry_run"], d["rows"], d["created"], d["skipped"]), (True, 5, 2, 3))
        self.assertEqual([e["row"] for e in d["errors"]], [3, 4, 6])
        self.assertIn("Unknown customer type", d["errors"][0]["error"])
        self.assertEqual(d["columns"]["E-mail address"], "email")
        self.assertIsNone(self.find(a))  # nothing saved

        real = self.upload(text, dry_run=False).json()
        self.assertEqual((real["created"], real["skipped"]), (2, 3))
        ada = self.get(self.find(a))
        self.assertEqual((ada["first_name"], ada["last_name"], ada["company"], ada["customer_type"], ada["source"]),
                         ("Ada", "Lovelace", "Engines Ltd", "vip", "etsy"))
        self.assertEqual(ada["address"], {"city": "Chicago", "postal_code": "60601"})
        self.assertEqual(ada["owner_id"], self.manager["id"])
        self.assertEqual(sorted(t["name"] for t in ada["tags"]), ["gift", "wholesale"])
        self.assertFalse(ada["marketing_consent"])  # a file can't grant consent

        # again: existing emails are skipped; in update mode values are filled in and tags added
        again = self.upload(text, dry_run=False).json()
        self.assertEqual(again["created"], 0)
        upd = self.upload(f"email,phone,tags,city\n{a},312-555-0199,vip-list,Evanston\n", mode="update", dry_run=False).json()
        self.assertEqual(upd["updated"], 1)
        ada = self.get(ada["id"])
        self.assertEqual(ada["phone"], "312-555-0199")
        self.assertEqual(ada["address"]["city"], "Evanston")
        self.assertEqual(ada["address"]["postal_code"], "60601")
        self.assertEqual(sorted(t["name"] for t in ada["tags"]), ["gift", "vip-list", "wholesale"])

    def test_bad_files(self):
        self.assertEqual(self.upload("").status_code, 422)
        self.assertEqual(self.upload("favourite colour\nblue\n").status_code, 422)
        self.assertEqual(self.upload(b"not excel", name="x.xlsx").status_code, 422)

    def test_export_csv_and_xlsx_with_filters_and_excel_import(self):
        email = self.w.email("exp")
        made = self.w.client.post(f"{API}/customers", headers=self.manager_h, json={
            "first_name": "=HYPERLINK(1)", "last_name": f"Export{self.w.sfx}", "email": email, "customer_type": "wholesale"}).json()
        res = self.w.client.get(f"{API}/customers/export", headers=self.manager_h, params={"q": f"Export{self.w.sfx}"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("attachment", res.headers["content-disposition"])
        rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], str(made["id"]))
        self.assertEqual(rows[0]["first_name"], "'=HYPERLINK(1)")  # formula neutralised
        self.assertEqual(rows[0]["type"], "Wholesale")
        self.assertEqual(rows[0]["owner"], self.manager["email"])

        xlsx = self.w.client.get(f"{API}/customers/export", headers=self.manager_h,
                                 params={"q": f"Export{self.w.sfx}", "format": "xlsx"})
        self.assertEqual(xlsx.status_code, 200)
        self.assertTrue(xlsx.content.startswith(b"PK"))

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        new_email = self.w.email("xl")
        ws.append(["First name", "Last name", "Email"])
        ws.append(["Excel", "Person", new_email])
        buf = io.BytesIO()
        wb.save(buf)
        res = self.upload(buf.getvalue(), name="people.xlsx", dry_run=False)
        self.assertEqual(res.json()["created"], 1, res.text)
        self.assertIsNotNone(self.find(new_email))

        template = self.w.client.get(f"{API}/customers/import/template", headers=self.manager_h)
        self.assertTrue(template.content.decode("utf-8-sig").startswith("first_name,last_name,company,email"))


if __name__ == "__main__":
    unittest.main()
