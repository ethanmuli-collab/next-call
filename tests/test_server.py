"""Web app API: read endpoints return real run data, and bad input is rejected before it touches disk."""
import io
import unittest

import server


class ServerApiTest(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_pages_and_overview(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)
        data = self.client.get("/api/overview").get_json()
        self.assertIn(data["mode"], {"llm", "offline"})
        self.assertIn("weekly", [s["key"] for s in data["sources"]])

    def test_committed_run_is_readable(self):
        detail = self.client.get("/api/runs/leads_weekly_export_v2").get_json()
        self.assertEqual(detail["summary"]["status"], "gate_failed")
        self.assertEqual([s["state"] for s in detail["stages"]], ["ok", "fail", "blocked", "blocked"])
        report = self.client.get("/api/runs/leads_weekly_export_v2/file/gate_report.json").get_json()
        self.assertEqual(report["kind"], "text")

    def test_outcomes_export_is_csv(self):
        res = self.client.get("/api/outcomes.csv")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_data(as_text=True).lstrip("\ufeff").startswith("lead_id,outcome,note,marked_at"))

    def test_unknown_run_or_file_is_404(self):
        self.assertEqual(self.client.get("/api/runs/..%2F..").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/no_such_run").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/leads_weekly_export_v2/file/config.py").status_code, 404)

    def test_bad_input_is_rejected(self):
        self.assertEqual(self.client.post("/api/run", json={"source": "nope"}).status_code, 404)
        self.assertEqual(self.client.post("/api/outcome", json={"lead_id": "L1", "outcome": "won"}).status_code, 400)
        self.assertEqual(self.client.post("/api/outcome", json={"lead_id": "x; DROP", "outcome": "enrolled"}).status_code, 400)
        res = self.client.post("/api/upload", data={"file": (io.BytesIO(b"x"), "notes.txt")})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
