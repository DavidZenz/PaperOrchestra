"""User-approved bibliography readiness checks (adaptation; not upstream logic)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata


class BibliographyError(RuntimeError):
    """A library or compiled manuscript lacks a usable, resolved bibliography."""


def _read(path):
    path = Path(path)
    if not path.is_file():
        raise BibliographyError(f"Missing bibliography artifact: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _keys(text):
    # The vendored generator writes ordinary BibTeX, one record per line.
    keys = re.findall(r"(?mi)^\s*@(?!(?:comment|string|preamble)\b)\w+\s*[{(]\s*([^,\s]+)\s*,", text)
    if len(keys) != len(set(keys)):
        raise BibliographyError("Duplicate BibTeX citation keys")
    return set(keys)


def escape_bibtex_fields(text):
    """Escape literal metadata reserved characters in upstream field lines."""
    def field(match):
        value = re.sub(r"(?<!\\)([&%#_])", r"\\\1", match[2])
        return match[1] + value + match[3]
    return re.sub(r"(?m)^(  (?:title|author|journal|booktitle|volume|pages)=\{)(.*)(\},?)$", field, text)


def validate_library(directory):
    """Reject zero records or a key mismatch before section writing."""
    directory = Path(directory)
    bib = directory / "references.bib"
    mapping_path = directory / "citation_map.json"
    try:
        mapping = json.loads(_read(mapping_path))
    except ValueError as exc:
        raise BibliographyError(f"Invalid citation map: {exc}") from exc
    if not isinstance(mapping, dict) or not mapping:
        raise BibliographyError("Empty bibliography: no verified references in citation_map.json")
    keys = _keys(_read(bib))
    if not keys:
        raise BibliographyError("Empty bibliography: references.bib has no entries")
    if keys != set(mapping):
        raise BibliographyError("Bibliography/citation-map keys differ")
    for key, record in mapping.items():
        if not isinstance(record, dict) or not record.get("title") or not record.get("abstract"):
            raise BibliographyError(f"Incomplete verified citation record: {key}")
    return {"valid": True, "reference_count": len(keys), "keys": sorted(keys),
            "bibliography_sha256": _hash(bib), "citation_map_sha256": _hash(mapping_path)}


def _normal(text):
    text = re.sub(r"\\[A-Za-z]+", "", text)
    return "".join(c.lower() for c in unicodedata.normalize("NFKD", text) if c.isalnum())


def validate_manuscript(cwd, basename, citation_map_path, pdf_path=None):
    """Check actual BibTeX output and resolved citations after compilation.

    Does not rewrite TeX, insert citations or repair a failed candidate. The caller
    decides whether a failed candidate consumes an original compile/revision try.
    """
    directory = Path(cwd)
    mapping = (citation_map_path if isinstance(citation_map_path, dict)
               else json.loads(_read(citation_map_path)))
    if not mapping:
        raise BibliographyError("Empty bibliography: permitted citation map is empty")
    requested_basename = basename
    pdf = Path(pdf_path) if pdf_path else directory / f"{basename}.pdf"
    if not (directory / f"{basename}.aux").is_file():
        # Upstream copies the accepted TeX/PDF to final_refined_paper, but does
        # not copy its compilation sidecars. Bind those to a byte-identical
        # retained candidate instead of accepting an unrelated successful .bbl.
        source = directory / f"{basename}.tex"
        matches = []
        if source.is_file() and pdf.is_file():
            for candidate in sorted(directory.glob("*.aux")):
                candidate_tex = candidate.with_suffix(".tex")
                candidate_pdf = candidate.with_suffix(".pdf")
                if (candidate_tex.is_file() and candidate_pdf.is_file()
                        and candidate_tex.read_bytes() == source.read_bytes()
                        and candidate_pdf.read_bytes() == pdf.read_bytes()):
                    matches.append(candidate.stem)
        if not matches:
            raise BibliographyError("No byte-identical compiled candidate for final manuscript")
        basename = matches[0]
    aux = _read(directory / f"{basename}.aux")
    citations = set()
    for group in re.findall(r"\\citation\{([^}]+)\}", aux):
        citations.update(k.strip() for k in group.split(",") if k.strip())
    if "*" in citations:
        citations = (citations - {"*"}) | set(mapping)
    if not citations:
        raise BibliographyError("Empty bibliography: manuscript has no compiled citations")
    unknown = citations - set(mapping)
    if unknown:
        raise BibliographyError("Unapproved citation keys: " + ", ".join(sorted(unknown)))
    databases = re.findall(r"\\bibdata\{([^}]+)\}", aux)
    if not databases or not re.search(r"\\bibstyle\{[^}]+\}", aux):
        raise BibliographyError("Missing bibliography database/style commands")
    database_keys = set()
    for group in databases:
        for name in group.split(","):
            path = directory / name.strip()
            if path.suffix.lower() != ".bib":
                path = path.with_suffix(".bib")
            database_keys |= _keys(_read(path))
    if citations - database_keys:
        raise BibliographyError("Cited keys missing from bibliography database")
    bbl_path = directory / f"{basename}.bbl"
    bbl = _read(bbl_path)
    items = set(re.findall(r"\\bibitem(?:\[[\s\S]*?\])?\s*\{([^{}]+)\}", bbl))
    resolved = set(re.findall(r"\\bibcite\{([^}]+)\}", aux))
    if not items or citations - items or citations - resolved:
        raise BibliographyError("Empty or unresolved bibliography: missing compiled bibitems/bibcite keys")
    if items - set(mapping) or items - database_keys:
        raise BibliographyError("Compiled bibliography contains unapproved or unknown entries")
    blg = _read(directory / f"{basename}.blg")
    if re.search(r"error message|I couldn't open|I found no |I was expecting|Illegal,|Repeated entry|Warning--I didn't find", blg, re.I):
        raise BibliographyError("BibTeX reported a bibliography error")
    log = _read(directory / f"{basename}.log")
    if re.search(r"Citation[^\n]*(?:\n[^\n]*)?undefined|undefined citations|There were undefined references", log, re.I):
        raise BibliographyError("LaTeX reported unresolved citations/references")
    if not pdf.is_file():
        raise BibliographyError("Missing compiled manuscript PDF")
    import pymupdf
    try:
        with pymupdf.open(pdf) as document:
            pages = [page.get_text() for page in document]
    except Exception as exc:
        raise BibliographyError(f"Unreadable manuscript PDF: {exc}") from exc
    text = _normal(" ".join(pages))
    visible_titles = [key for key in sorted(citations)
                      if _normal(mapping[key].get("title", ""))
                      and _normal(mapping[key]["title"]) in text]
    # A .bbl file alone can exist even if it was never included in the PDF.
    # Resolved aux keys plus visible reference metadata prove actual inclusion.
    if not visible_titles:
        raise BibliographyError("No cited reference title is visible in the compiled PDF")
    return {"valid": True, "requested_basename": requested_basename, "compiled_candidate": basename,
            "cited_keys": sorted(citations), "bibitem_keys": sorted(items),
            "resolved_keys": sorted(resolved), "visible_title_keys": visible_titles,
            "reference_count": len(items), "pdf_pages": len(pages), "pdf_sha256": _hash(pdf),
            "bbl_sha256": _hash(bbl_path), "aux_sha256": _hash(directory / f"{basename}.aux")}
