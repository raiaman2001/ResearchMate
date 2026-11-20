"""F4: Confidence score + auto-generated Limitations. Poora deterministic (LLM nahi)."""
from statistics import mean

from app.i18n import t

VERDICT_WEIGHT = {"supported": 1.0, "partial": 0.5, "unsupported": 0.0, "uncited": 0.2}


def label_for(score):
    return "High" if score >= 0.8 else "Medium" if score >= 0.45 else "Low"


def claim_confidence(verdict, cited_scores, n_sources):
    """Verdict x source credibility. 2+ alag sources ho to thoda bonus."""
    cred = mean(cited_scores) if cited_scores else 0.5
    s = VERDICT_WEIGHT[verdict] * (0.5 + 0.5 * cred)
    if verdict in ("supported", "partial") and n_sources >= 2:
        s += 0.1
    s = round(min(1.0, s), 2)
    return s, label_for(s)


def overall_confidence(checks, n_conflicts=0, n_failed=0):
    """(score, label). Checks nahi hue (verify off) to (None, 'Not verified')."""
    if not checks:
        return None, "Not verified"
    s = mean(c["score"] for c in checks)
    s -= min(0.2, 0.05 * n_conflicts) + min(0.2, 0.1 * n_failed)
    s = round(max(0.0, min(1.0, s)), 2)
    return s, label_for(s)


def summarize_checks(checks):
    n = len(checks)
    counts = {v: sum(1 for c in checks if c["verdict"] == v) for v in VERDICT_WEIGHT}
    bad = counts["unsupported"] + counts["uncited"]
    return {"claims": n, **counts, "unsupported_rate": round(bad / n, 3) if n else 0.0}


def build_limitations(gaps, failed, conflicts, checks, source_scores, dropped_total, lang="hinglish"):
    """'Open Questions / Limitations' ki bullet list (report ki bhasha me)."""
    out = [t(lang, "lim_gap", g=g) for g in gaps]
    out += [t(lang, "lim_failed", q=q) for q in failed]
    if conflicts:
        out.append(t(lang, "lim_conflicts", n=len(conflicts)))
    bad = [c for c in checks if c["verdict"] in ("unsupported", "uncited")]
    if bad:
        out.append(t(lang, "lim_bad", n=len(bad)))
    partial = [c for c in checks if c["verdict"] == "partial"]
    if partial:
        out.append(t(lang, "lim_partial", n=len(partial)))
    single = [c for c in checks if len(c["ids"]) == 1 and c["verdict"] in ("supported", "partial")]
    if single:
        out.append(t(lang, "lim_single", n=len(single)))
    low = [s for s in source_scores if s["label"] == "Low"]
    if low:
        out.append(t(lang, "lim_low", n=len(low)))
    if dropped_total:
        out.append(t(lang, "lim_dropped", n=dropped_total))
    return out
