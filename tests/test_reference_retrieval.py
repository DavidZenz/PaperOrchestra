"""R025 retrieval behavior with controlled HTTP; no live models or services."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper-orchestra/vendor"))
from orchestra_references import ReferenceRetriever, date_allowed, from_openalex, from_crossref


TITLE = "Regression through the Origin"


def response(status=200, body=None, retry_after="0"):
    class Response:
        status_code = status
        headers = {"Retry-After": retry_after}
        text = "response text"
        def json(self):
            return body
    return Response()


def crossref_item(**override):
    return {"title": [TITLE], "author": [{"given": "A", "family": "Researcher"}],
            "published": {"date-parts": [[1985, 4, 1]]},
            "container-title": ["A Journal"], "type": "journal-article",
            "abstract": "<jats:p>A deposited abstract.</jats:p>",
            "DOI": "10.fixture/one", **override}


class ReferenceRetrievalTests(unittest.TestCase):
    def retriever(self, responses):
        from unittest.mock import Mock
        self.get = Mock(side_effect=responses)
        self.sleep = Mock()
        self.events = []
        return ReferenceRetriever(lambda event, **fields: self.events.append({"event": event, **fields}),
                                  get=self.get, sleep=self.sleep)

    def test_s2_remains_primary_and_success_does_not_query_fallbacks(self):
        record = {"title": TITLE, "year": 1985, "abstract": "A real record abstract.",
                  "authors": [{"name": "A Researcher"}]}
        r = self.retriever([response(body={"data": [record]})])
        self.assertEqual(r.lookup(TITLE, 1985, "2026-01"), record)
        self.assertEqual(self.get.call_count, 1)
        self.assertEqual(self.events[-1]["provider"], "semantic-scholar")

    def test_429_retries_twice_opens_circuit_and_uses_deposited_crossref_abstract(self):
        r = self.retriever([response(429, {}, "1"), response(429, {}),
                            response(body={"message": {"items": [crossref_item()]}}),
                            response(body={"message": {"items": [crossref_item(title=["Other title"])]}}),
                            response(body={"results": []})])
        result = r.lookup(TITLE, 1985, "2026-01")
        self.assertEqual(result["abstract"], "A deposited abstract.")
        self.assertEqual(result["authors"], [{"name": "A Researcher"}])
        self.assertEqual(result["publicationDate"], "1985-04-01")
        self.assertEqual(result["externalIds"]["DOI"], "10.fixture/one")
        self.sleep.assert_called_once_with(1.)
        r.lookup("Unrelated paper", None, "2026-01")
        self.assertEqual(sum("semanticscholar" in c.args[0] for c in self.get.call_args_list), 2)
        self.assertTrue(any(e["event"] == "reference_provider_skipped" for e in self.events))

    def test_long_retry_after_defers_provider_without_retrying_early(self):
        r = self.retriever([response(429, {}, "600"),
                            response(body={"message": {"items": [crossref_item()]}})])
        self.assertIsNotNone(r.lookup(TITLE, 1985, "2026-01"))
        self.assertEqual(self.get.call_count, 2)
        self.sleep.assert_not_called()
        self.assertIn("semantic-scholar", r.disabled)
        self.assertTrue(any(e["event"] == "reference_provider_deferred" for e in self.events))

    def test_openalex_reconstructs_actual_indexed_abstract_after_no_crossref_abstract(self):
        item = {"title": TITLE, "publication_year": 1985, "publication_date": "1985-04-01",
                "authorships": [{"author": {"display_name": "A Researcher"}}],
                "abstract_inverted_index": {"Observed": [0], "residuals": [1, 3], "and": [2]},
                "primary_location": {"source": {"display_name": "A Journal", "type": "journal"}}}
        r = self.retriever([response(body={"data": []}),
                            response(body={"message": {"items": [crossref_item(abstract="")]}}),
                            response(body={"results": [item]})])
        result = r.lookup(TITLE, 1985, "2026-01")
        self.assertEqual(result["abstract"], "Observed residuals and residuals")
        self.assertEqual(self.events[-1]["provider"], "openalex")
        self.assertTrue(any(e.get("reason") == "missing_abstract" for e in self.events))

    def test_no_abstract_no_record_and_bad_title_is_rejected(self):
        r = self.retriever([response(body={"data": []}),
                            response(body={"message": {"items": [crossref_item(abstract="")]}}),
                            response(body={"results": [{"title": "Unrelated", "abstract_inverted_index": {"X": [0]}}]})])
        self.assertIsNone(r.lookup(TITLE, 1985, "2026-01"))
        self.assertTrue(any(e.get("reason") == "no_title_match" for e in self.events))

    def test_future_record_rejected_and_fallback_past_record_selected(self):
        r = self.retriever([response(body={"data": [{"title": TITLE, "year": 2027,
                                                    "publicationDate": "2027-01-01", "abstract": "Future"}]}),
                            response(body={"message": {"items": [crossref_item()]}})])
        self.assertEqual(r.lookup(TITLE, None, "2026-11")["year"], 1985)
        self.assertTrue(any(e.get("reason") == "after_cutoff" for e in self.events))

    def test_cache_deduplicates_lookup_and_is_cutoff_specific(self):
        r = self.retriever([response(body={"data": []}), response(body={"message": {"items": []}}),
                            response(body={"results": []})])
        self.assertIsNone(r.lookup(TITLE, 1985, "2026-01"))
        self.assertIsNone(r.lookup(TITLE, 1985, "2026-01"))
        self.assertEqual(self.get.call_count, 3)
        self.assertEqual(self.events[-1]["event"], "reference_cache_hit")

    def test_recording_retains_response_and_does_not_include_authentication(self):
        r = self.retriever([response(body={"data": []}), response(body={"message": {"items": []}}),
                            response(body={"results": []})])
        with patch.dict(os.environ, {"SEMANTIC_SCHOLAR_API_KEY": "secret-s2", "OPENALEX_API_KEY": "secret-oa"}):
            r.lookup(TITLE, 1985, "2026-01")
        self.assertNotIn("secret-", str(self.events))
        self.assertEqual(len([e for e in self.events if e["event"] == "reference_response"]), 3)

    def test_transient_server_failure_retries_once_then_accepts_primary(self):
        record = {"title": TITLE, "year": 1985, "abstract": "Deposited abstract."}
        r = self.retriever([response(503, {}), response(body={"data": [record]})])
        self.assertEqual(r.lookup(TITLE, 1985, "2026-01"), record)
        self.assertEqual(self.get.call_count, 2)
        self.sleep.assert_called_once_with(0.)

    def test_network_failures_are_bounded_and_do_not_leak_urls(self):
        import requests
        r = self.retriever([requests.Timeout("https://api.example/?api_key=secret"),
                            requests.Timeout("https://api.example/?api_key=secret"),
                            response(body={"message": {"items": [crossref_item()]}})])
        self.assertIsNotNone(r.lookup(TITLE, 1985, "2026-01"))
        self.assertEqual(self.get.call_count, 3)
        self.assertNotIn("secret", str(self.events))
        self.assertEqual(len([e for e in self.events if e["event"] == "reference_request_error"]), 2)

    def test_upstream_cutoff_strict_month_boundary_and_year_fallback(self):
        self.assertFalse(date_allowed("2026-11-01", 2026, "2026-11"))
        self.assertTrue(date_allowed("2026-10-31", 2026, "2026-11"))
        self.assertTrue(date_allowed(None, 2026, "2026-11"))
        self.assertFalse(date_allowed(None, 2026, "2026-01"))

    def test_crossref_month_precision_preserved_without_fabricated_day(self):
        record = from_crossref(crossref_item(published={"date-parts": [[2026, 12]]}))
        self.assertEqual(record["publicationDate"], "2026-12")
        self.assertEqual(record["sourceDatePrecision"], "month")
        self.assertFalse(date_allowed(record["publicationDate"], record["year"], "2026-11"))
        self.assertFalse(date_allowed("2026-11", 2026, "2026-11"))
        self.assertTrue(date_allowed("2026-10", 2026, "2026-11"))

    def test_original_second_cutoff_gate_receives_known_crossref_month(self):
        from methods.agents.literature_review_agent import HybridLiteratureAgent
        future = from_crossref(crossref_item(published={"date-parts": [[2026, 12]]}))
        past = from_crossref(crossref_item(published={"date-parts": [[2026, 10]]}))
        self.assertFalse(HybridLiteratureAgent._is_paper_allowed(None, future, "2026-11"))
        self.assertTrue(HybridLiteratureAgent._is_paper_allowed(None, past, "2026-11"))

    def test_month_precision_rejection_falls_back_without_accepting_future_record(self):
        r = self.retriever([response(body={"data": []}),
                            response(body={"message": {"items": [crossref_item(
                                published={"date-parts": [[2026, 12]]})]}}),
                            response(body={"results": []})])
        self.assertIsNone(r.lookup(TITLE, 2026, "2026-11"))
        self.assertTrue(any(e.get("reason") == "after_cutoff" and e.get("provider") == "crossref"
                            for e in self.events))


if __name__ == "__main__":
    unittest.main()
