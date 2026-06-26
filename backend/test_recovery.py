import unittest

from app.recovery import (
    RecoveryTracker,
    apply_recovery,
    build_retry_hint,
    empty_result_note,
    is_empty_result,
)


class RecoveryTrackerTests(unittest.TestCase):
    def test_first_attempt_is_one(self):
        tracker = RecoveryTracker()
        self.assertEqual(tracker.attempt_number("sql_analytics"), 1)

    def test_error_then_retry_attempt_numbers(self):
        tracker = RecoveryTracker()
        self.assertEqual(tracker.record_error("sql_analytics"), 1)
        # Next call to the same tool is attempt 2 (the one retry).
        self.assertEqual(tracker.attempt_number("sql_analytics"), 2)

    def test_success_after_error_reports_recovered_and_resets(self):
        tracker = RecoveryTracker()
        tracker.record_error("sql_analytics")
        self.assertTrue(tracker.record_success("sql_analytics"))
        # After recovery the tool is clean again.
        self.assertEqual(tracker.attempt_number("sql_analytics"), 1)

    def test_success_without_prior_error_is_not_recovery(self):
        tracker = RecoveryTracker()
        self.assertFalse(tracker.record_success("sql_analytics"))

    def test_budget_exhausted_after_one_retry(self):
        tracker = RecoveryTracker(max_retries=1)
        tracker.record_error("sql_analytics")          # first failure -> retry allowed
        self.assertFalse(tracker.budget_exhausted("sql_analytics"))
        tracker.record_error("sql_analytics")          # second failure -> exhausted
        self.assertTrue(tracker.budget_exhausted("sql_analytics"))

    def test_tools_tracked_independently(self):
        tracker = RecoveryTracker()
        tracker.record_error("sql_analytics")
        self.assertEqual(tracker.attempt_number("odoo_query"), 1)
        self.assertFalse(tracker.budget_exhausted("odoo_query"))


class EmptyResultTests(unittest.TestCase):
    def test_sql_analytics_zero_rows_is_empty(self):
        self.assertTrue(is_empty_result("sql_analytics", {"row_count": 0, "rows": []}))

    def test_sql_analytics_with_rows_is_not_empty(self):
        self.assertFalse(is_empty_result("sql_analytics", {"row_count": 5, "rows": [{}]}))

    def test_odoo_query_zero_count_is_empty(self):
        self.assertTrue(is_empty_result("odoo_query", {"count": 0, "records": []}))

    def test_error_output_is_never_empty_result(self):
        self.assertFalse(is_empty_result("sql_analytics", {"error": "boom", "row_count": 0}))

    def test_other_tools_are_never_empty_result(self):
        self.assertFalse(is_empty_result("forecast_demand", {"forecast": []}))

    def test_empty_note_mentions_zero_rows_and_recheck(self):
        note = empty_result_note("sql_analytics").lower()
        self.assertIn("0 rows", note)
        self.assertTrue("filter" in note or "narrow" in note)


class RetryHintTests(unittest.TestCase):
    def test_sql_hint_points_at_schema_and_one_retry(self):
        hint = build_retry_hint("sql_analytics", "column foo does not exist", exhausted=False).lower()
        self.assertIn("schema", hint)
        self.assertIn("once", hint)

    def test_generic_hint_for_other_tools(self):
        hint = build_retry_hint("forecast_demand", "bad category", exhausted=False).lower()
        self.assertIn("once", hint)

    def test_exhausted_hint_tells_model_to_stop(self):
        hint = build_retry_hint("sql_analytics", "still broken", exhausted=True).lower()
        self.assertIn("do not", hint)
        self.assertTrue("explain" in hint or "limitation" in hint)


class ApplyRecoveryTests(unittest.TestCase):
    def test_error_adds_retry_guidance_and_returns_attempt(self):
        tracker = RecoveryTracker()
        output = {"error": "column bad does not exist"}
        attempt, recovered = apply_recovery(tracker, "sql_analytics", output)
        self.assertEqual(attempt, 1)
        self.assertFalse(recovered)
        self.assertIn("retry_guidance", output)

    def test_success_after_error_returns_recovered(self):
        tracker = RecoveryTracker()
        apply_recovery(tracker, "sql_analytics", {"error": "boom"})
        attempt, recovered = apply_recovery(
            tracker, "sql_analytics", {"row_count": 3, "rows": [{}]}
        )
        self.assertEqual(attempt, 2)
        self.assertTrue(recovered)

    def test_empty_result_adds_note_but_no_guidance(self):
        tracker = RecoveryTracker()
        output = {"row_count": 0, "rows": []}
        apply_recovery(tracker, "sql_analytics", output)
        self.assertIn("note", output)
        self.assertNotIn("retry_guidance", output)

    def test_successful_nonempty_result_is_untouched(self):
        tracker = RecoveryTracker()
        output = {"row_count": 2, "rows": [{}, {}]}
        attempt, recovered = apply_recovery(tracker, "sql_analytics", output)
        self.assertEqual(attempt, 1)
        self.assertFalse(recovered)
        self.assertNotIn("note", output)
        self.assertNotIn("retry_guidance", output)


if __name__ == "__main__":
    unittest.main()
