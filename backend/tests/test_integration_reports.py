"""Reports: cross-module overview and grouped customer, ticket, and supplier counts."""

import unittest

from app.modules.reports.schemas import ReportBucket
from tests.support import API, World, reset_limits, run, skip_unless_db


class ReportSchemaTests(unittest.TestCase):
    def test_bucket_has_a_stable_label_and_count(self):
        bucket = ReportBucket.model_validate({"label": "Not set", "count": 3})
        self.assertEqual((bucket.label, bucket.count), ("Not set", 3))


@skip_unless_db
class ReportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.modules.lookups.service import LookupService

        cls.w = World()
        reset_limits()
        run(lambda session: LookupService(session).seed())
        cls.manager, cls.manager_h = cls.w.user_with_token("manager")
        cls.read_only, cls.read_only_h = cls.w.user_with_token("read_only")
        cls.sales, cls.sales_h = cls.w.user_with_token("sales")
        cls.customer_type = run(lambda session: LookupService(session).values("customer_type"))[0].key
        cls.lead_source = run(lambda session: LookupService(session).values("lead_source"))[0].key
        cls.ticket_type = run(lambda session: LookupService(session).values("ticket_type"))[0].key
        cls.ticket_priority = run(lambda session: LookupService(session).values("ticket_priority"))[0].key
        cls.supplier_type = run(lambda session: LookupService(session).values("supplier_type"))[0].key

    def setUp(self):
        reset_limits()

    def test_breakdowns_and_overview_include_real_records(self):
        customer = self.w.client.post(f"{API}/customers", headers=self.manager_h, json={
            "first_name": "Report", "last_name": "Customer", "email": self.w.email("report-customer"),
            "customer_type": self.customer_type, "source": self.lead_source,
        })
        self.assertEqual(customer.status_code, 201, customer.text)
        ticket = self.w.client.post(f"{API}/tickets", headers=self.manager_h, json={
            "subject": "Report ticket", "ticket_type": self.ticket_type, "priority": self.ticket_priority,
        })
        self.assertEqual(ticket.status_code, 201, ticket.text)
        supplier = self.w.client.post(f"{API}/suppliers", headers=self.manager_h, json={
            "name": self.w.email("report-supplier"), "supplier_type": self.supplier_type,
        })
        self.assertEqual(supplier.status_code, 201, supplier.text)

        customers = self.w.client.get(f"{API}/reports/customers", headers=self.read_only_h)
        self.assertEqual(customers.status_code, 200, customers.text)
        customer_report = customers.json()
        self.assertGreaterEqual(customer_report["total"], 1)
        self.assertIn(self.customer_type, [item["label"] for item in customer_report["by_type"]])
        self.assertIn(self.lead_source, [item["label"] for item in customer_report["by_source"]])

        tickets = self.w.client.get(f"{API}/reports/tickets", headers=self.manager_h)
        self.assertEqual(tickets.status_code, 200, tickets.text)
        ticket_report = tickets.json()
        self.assertGreaterEqual(ticket_report["total"], 1)
        self.assertIn(self.ticket_type, [item["label"] for item in ticket_report["by_type"]])
        self.assertIn(self.ticket_priority, [item["label"] for item in ticket_report["by_priority"]])

        suppliers = self.w.client.get(f"{API}/reports/suppliers", headers=self.manager_h)
        self.assertEqual(suppliers.status_code, 200, suppliers.text)
        self.assertIn(self.supplier_type, [item["label"] for item in suppliers.json()["by_type"]])

        overview = self.w.client.get(f"{API}/reports/overview", headers=self.read_only_h,
                                     params={"campaign_days": 14})
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["campaigns"]["days"], 14)
        self.assertGreaterEqual(overview.json()["active_customers"], 1)
        self.assertGreaterEqual(overview.json()["active_suppliers"], 1)

    def test_reports_require_reports_permission(self):
        response = self.w.client.get(f"{API}/reports/customers", headers=self.sales_h)
        self.assertEqual(response.status_code, 403)