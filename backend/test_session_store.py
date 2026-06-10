import unittest
from datetime import datetime, timezone

from app.session_store import _json_dumps, summarize_tool_result


class SessionStoreTests(unittest.TestCase):
    def test_summarizes_forecast_tool_result(self):
        summary = summarize_tool_result(
            "forecast_demand",
            {"category": "Outerwear"},
            {
                "category": "Outerwear",
                "history": [{"month": "2026-05-01", "units": 19}],
                "forecast": [{"month": "2026-06-01", "units": 18.3}],
            },
        )

        self.assertIn("forecast_demand for Outerwear", summary)
        self.assertIn("1 history rows", summary)
        self.assertIn("2026-06-01", summary)
        self.assertIn("18.3 units", summary)

    def test_summarizes_tool_error(self):
        summary = summarize_tool_result(
            "forecast_demand",
            {"category": "Outerwear"},
            {"error": "not enough history"},
        )

        self.assertIn("failed with error", summary)
        self.assertIn("not enough history", summary)

    def test_json_dumps_handles_datetime_tool_events(self):
        encoded = _json_dumps(
            [{"evidence": {"top_rows": [{"created_at": datetime(2026, 6, 9, tzinfo=timezone.utc)}]}}]
        )

        self.assertIn("2026-06-09", encoded)


if __name__ == "__main__":
    unittest.main()
