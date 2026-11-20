"""Compare accepted LaTeX with a formatting candidate before compiling it."""

from pathlib import Path
import re


FORMAT_REVIEW_RULE = (
    "[FORMATTING SCOPE] Limit suggested edits to figure/table float placement "
    "and figure width. Report length or other issues requiring content edits "
    "as unresolved. Do not recommend shortening scientific prose, removing "
    "citations, editing bibliography records, or changing figure sources."
)
FORMAT_EDITOR_RULE = (
    "[FORMATTING SCOPE] This rule overrides any feedback or guideline that "
    "asks for content changes. Preserve the full source exactly except for "
    "float placement (h, t, b, p, !) on standalone standard figure/table "
    "openings and width on a standalone includegraphics command inside a "
    "top-level figure. For width use 0.5 to 1 times linewidth or columnwidth. "
    "Keep image paths, prose, math, tables, captions, citations and bibliography "
    "commands exactly as supplied. Keep line breaks and indentation. "
    "Return the source unchanged if the feedback requires other edits."
)

_FLOAT = re.compile(r"([ \t]*\\begin\{(?:figure|table)\*?\})(?:\[!?[htbp]+!?\])?([ \t]*)")
_IMAGE = re.compile(
    r"([ \t]*\\includegraphics)"
    r"(?:\[width=(?:0?\.[5-9][0-9]*|1(?:\.0+)?)?\\(?:line|column)width\])?"
    r"(\{[^{}\\%\r\n]+\}[ \t]*)"
)
_TOKEN = re.compile(
    r"\\verb\*?(?P<delimiter>[^a-zA-Z*\s]).*?(?P=delimiter)"
    r"|\\(?P<direction>begin|end)\{(?P<environment>[a-zA-Z*]+)\}"
    r"|\\[a-zA-Z@]+|\\.|[{}%]"
)
_LITERAL = {"comment", "verbatim", "verbatim*", "Verbatim", "Verbatim*",
            "lstlisting", "minted", "filecontents", "filecontents*"}


class FormattingScopeError(ValueError):
    """The formatter changed source outside the supported layout edits."""


def _layout_signature(source):
    """Remove only the approved option values from recognizable LaTeX lines."""
    environments = []
    groups = 0
    signature = []
    for line in source.strip().split("\n"):
        current = environments[-1] if environments else None
        if current in _LITERAL:
            if line.strip() == rf"\end{{{current}}}":
                environments.pop()
            signature.append(line)
            continue

        option = None
        if groups == 0:
            if environments == ["document"]:
                option = _FLOAT.fullmatch(line)
            elif environments in (["document", "figure"], ["document", "figure*"]):
                option = _IMAGE.fullmatch(line)
        # A tuple cannot collide with literal source containing the same text.
        signature.append(option.groups() if option else line)
        for token in _TOKEN.finditer(line):
            value = token[0]
            if value == "%":
                break
            if value in {"{", r"\begingroup", r"\bgroup", r"\(", r"\["}:
                groups += 1
            elif value in {"}", r"\endgroup", r"\egroup", r"\)", r"\]"}:
                groups -= 1
            elif groups == 0 and token["direction"] == "begin":
                environments.append(token["environment"])
                if token["environment"] in _LITERAL:
                    break
            elif groups == 0 and token["direction"] == "end":
                if not environments or environments[-1] != token["environment"]:
                    raise FormattingScopeError("Could not identify LaTeX environment boundaries")
                environments.pop()
    if environments or groups:
        raise FormattingScopeError("Could not identify LaTeX group boundaries")
    return signature


def validate_formatting(workdir, candidate):
    """Keep scientific source and all citation uses from the accepted draft."""
    baseline = Path(workdir) / "format_candidate_v0.tex"
    try:
        before = baseline.read_text(encoding="utf-8")
        after = Path(candidate).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FormattingScopeError("Could not read the formatting input and candidate") from exc
    if before.strip() == after.strip():
        return
    if _layout_signature(before) != _layout_signature(after):
        raise FormattingScopeError(
            "Source changed outside allowed float placement or figure width edits"
        )
