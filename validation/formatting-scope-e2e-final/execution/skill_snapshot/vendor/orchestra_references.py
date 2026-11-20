"""R027: bounded scholarly-metadata retrieval; no model-generated references.

Semantic Scholar remains primary. Crossref and OpenAlex are explicit metadata
provider substitutions after primary failure/rejection. The authors' title-score,
year bonus, cutoff comparison and required-abstract semantics are retained.
"""
from __future__ import annotations

import datetime
import html
import os
import re
import time
from typing import Callable

import requests
from thefuzz import fuzz

S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_URL = "https://api.crossref.org/works"
OPENALEX_URL = "https://api.openalex.org/works"
FIELDS = "title,authors,venue,year,abstract,citationCount,journal,publicationDate"


def plain_text(value):
    """Strip deposited JATS/HTML markup, preserving the deposited wording."""
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def date_allowed(publication_date, year, cutoff):
    """Upstream full-date/year rules, plus explicit month-precision comparison.

    Crossref month-only dates are kept as YYYY-MM, without inventing a day.
    A known publication month must be strictly before the cutoff month; this
    preserves upstream's strict full-date boundary rather than dropping known
    month information into the permissive year-only fallback.
    """
    if not cutoff:
        return True
    try:
        cy, cm = map(int, cutoff.split("-"))
        end = datetime.datetime(cy, cm, 1)
        if publication_date:
            if re.fullmatch(r"\d{4}-\d{2}", publication_date):
                py, pm = map(int, publication_date.split("-"))
                if 1 <= pm <= 12:
                    return (py, pm) < (cy, cm)
            try:
                return datetime.datetime.strptime(publication_date, "%Y-%m-%d") < end
            except ValueError:
                pass
        if year:
            return year < cy or (year == cy and cm > 1)
        return True
    except Exception:
        return True


def from_crossref(item):
    parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])[0]
    year = parts[0] if parts else None
    publication_date = None
    if len(parts) >= 2:
        publication_date = "-".join([str(parts[0]), f"{parts[1]:02d}"]
                                    + ([f"{parts[2]:02d}"] if len(parts) >= 3 else []))
    titles = item.get("title") or []
    journals = item.get("container-title") or []
    journal = journals[0] if journals else ""
    return {"title": plain_text(titles[0]) if titles else "",
            "authors": [{"name": " ".join(filter(None, [a.get("given"), a.get("family")]))
                         or a.get("name", "Unknown")} for a in item.get("author", [])],
            "venue": journal, "year": year, "abstract": plain_text(item.get("abstract")),
            "citationCount": item.get("is-referenced-by-count", 0),
            "journal": {"name": journal, "volume": item.get("volume"), "pages": item.get("page")}
                       if item.get("type") == "journal-article" else None,
            "publicationDate": publication_date,
            "sourceDatePrecision": "day" if len(parts) >= 3 else "month" if len(parts) == 2 else "year",
            "externalIds": {"DOI": item.get("DOI")}, "url": item.get("URL")}


def from_openalex(item):
    positions = {}
    for token, indexes in (item.get("abstract_inverted_index") or {}).items():
        for index in indexes:
            positions[index] = token
    abstract = " ".join(positions[i] for i in sorted(positions))
    source = ((item.get("primary_location") or {}).get("source") or {})
    journal = source.get("display_name", "")
    biblio = item.get("biblio") or {}
    pages = "-".join(str(v) for v in [biblio.get("first_page"), biblio.get("last_page")] if v)
    return {"title": item.get("title", ""),
            "authors": [{"name": (a.get("author") or {}).get("display_name", "Unknown")}
                        for a in item.get("authorships", [])],
            "venue": journal, "year": item.get("publication_year"), "abstract": abstract,
            "citationCount": item.get("cited_by_count", 0),
            "journal": {"name": journal, "volume": biblio.get("volume"), "pages": pages}
                       if source.get("type") == "journal" else None,
            "publicationDate": item.get("publication_date"),
            "externalIds": {"DOI": item.get("doi"), "OpenAlex": item.get("id")},
            "url": item.get("doi") or item.get("id")}


class ReferenceRetriever:
    """One run-scoped retriever; retries/circuit state never changes agent limits.

    recorder(event, **fields) receives response JSON and selection decisions;
    headers and API-key query fields are deliberately never recorded here.
    """
    def __init__(self, recorder: Callable | None = None, *, get=None, sleep=None):
        self.recorder = recorder or (lambda event, **fields: None)
        self.get = get or requests.get
        self.sleep = sleep or time.sleep
        self.disabled = set()
        self.cache = {}

    def _request(self, provider, url, params, headers=None):
        if provider in self.disabled:
            self.recorder("reference_provider_skipped", provider=provider, reason="rate_limit_circuit_open")
            return None
        for attempt in range(1, 3):
            try:
                response = self.get(url, params=params, headers=headers or {}, timeout=10)
                try:
                    body = response.json()
                except ValueError:
                    body = {"unparsed_body": response.text}
                # Persist JSON only; response/request headers can contain secrets.
                self.recorder("reference_response", provider=provider, attempt=attempt,
                              status=response.status_code, response=body)
                if response.status_code == 200:
                    return body
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable:
                    return None
                if attempt == 2:
                    if response.status_code == 429:
                        self.disabled.add(provider)
                    return None
                try:
                    delay = max(0., float(response.headers.get("Retry-After", 1)))
                except ValueError:
                    delay = 1.
                if delay > 2.:
                    self.disabled.add(provider)
                    self.recorder("reference_provider_deferred", provider=provider,
                                  reason="retry_after_exceeds_run_wait_budget", retry_after=delay)
                    return None
                self.sleep(delay)
            except requests.RequestException as exc:
                # Do not log exception strings: requests may include key-bearing URLs.
                self.recorder("reference_request_error", provider=provider, attempt=attempt,
                              error_type=type(exc).__name__)
                if attempt < 2:
                    self.sleep(1.)
        return None

    def _select(self, provider, items, title, year_hint, cutoff):
        best = None
        highest = 0
        for item in items:
            reason = None
            if not item.get("title"):
                reason = "missing_title"
            elif not date_allowed(item.get("publicationDate"), item.get("year"), cutoff):
                reason = "after_cutoff"
            if reason:
                self.recorder("reference_candidate_rejected", provider=provider,
                              title=item.get("title"), reason=reason)
                continue
            ratio = fuzz.ratio(title.lower(), item["title"].lower())
            if year_hint and item.get("year") == year_hint:
                ratio += 10
            if ratio > highest:
                best, highest = item, ratio
        if not best or highest <= 70:
            self.recorder("reference_candidate_rejected", provider=provider,
                          title=title, reason="no_title_match", score=highest)
            return None
        if not best.get("abstract", "").strip():
            self.recorder("reference_candidate_rejected", provider=provider,
                          title=best["title"], reason="missing_abstract", score=highest)
            return None
        self.recorder("reference_selected", provider=provider, query=title,
                      score=highest, record=best)
        return best

    def lookup(self, title_query, year_hint=None, cutoff_date=None):
        cache_key = (title_query.lower().strip(), year_hint, cutoff_date)
        if cache_key in self.cache:
            self.recorder("reference_cache_hit", title=title_query,
                          accepted=self.cache[cache_key] is not None)
            return self.cache[cache_key]
        self.recorder("reference_lookup", title=title_query, year_hint=year_hint, cutoff=cutoff_date)
        key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        body = self._request("semantic-scholar", S2_URL,
                             {"query": title_query, "limit": 3, "fields": FIELDS},
                             {"X-API-KEY": key} if key else {})
        candidates = body.get("data", []) if isinstance(body, dict) else []
        chosen = self._select("semantic-scholar", candidates, title_query, year_hint, cutoff_date)
        if not chosen:
            body = self._request("crossref", CROSSREF_URL, {"query.title": title_query, "rows": 3})
            items = (body.get("message") or {}).get("items", []) if isinstance(body, dict) else []
            chosen = self._select("crossref", [from_crossref(i) for i in items],
                                  title_query, year_hint, cutoff_date)
        if not chosen:
            params = {"search": title_query, "per-page": 3}
            key = os.environ.get("OPENALEX_API_KEY")
            if key:
                params["api_key"] = key
            body = self._request("openalex", OPENALEX_URL, params)
            items = body.get("results", []) if isinstance(body, dict) else []
            chosen = self._select("openalex", [from_openalex(i) for i in items],
                                  title_query, year_hint, cutoff_date)
        self.cache[cache_key] = chosen
        return chosen


_default = ReferenceRetriever()


def lookup(title, year=None, cutoff=None, recorder=None):
    """Compatibility entrypoint; use ReferenceRetriever per run for durable state."""
    if recorder is not None:
        return ReferenceRetriever(recorder).lookup(title, year, cutoff)
    return _default.lookup(title, year, cutoff)
