# PaperOrchestra validation evidence

The latest update adds [dated model recommendations](MODEL-RECOMMENDATIONS-REPORT.md)
for OpenAI, Anthropic, Gemini/Antigravity and Mistral, plus an optional Codex
profile. Only the Codex worker backend is implemented and validated; the other
providers are explicitly advisory. No new paper or provider comparison was run.

[Invocation-time model selection](MODEL-PROFILES-REPORT.md) provides:
183 passing tests, per-type/per-role profiles, zero-call preview and the requested
setup question. No new paper was generated for this configuration update.

[Exact manuscript provenance](MANUSCRIPT-PROVENANCE-REPORT.md) records the prior
frozen 57-session full workflow, successful reversion/stopping, seven identical
figure replays and the corrected manuscript's exact R/TikZ sources. Its source
archive remains available as a distinct release; those completed-run claims are
not reassigned to the new model-configuration build.

The [earlier R/TikZ](INSTALLED-CODE-REPORT.md) and [supplied-figure](SUPPLIED-FIGURE-REPORT.md)
reports remain historical. Interrupted diagnostics remain excluded from success claims.
