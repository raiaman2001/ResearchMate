"""Final markdown report banana (report ki bhasha: en / hi / hinglish)."""
from app.i18n import domain, label, t


def compose(r):
    """r: dict. keys: topic, body, plan, cited, scores_by_url, origin (url->saved_at ya None), other_read, failed,
    conflicts, summary, conf_label, conf_score, retries, limitations, verified, mode, debate_stats, language"""
    lang = r.get("language", "hinglish")
    L = [f"# {r['topic']}", ""]
    if r["mode"] == "debate":
        L += [t(lang, "mode_debate"), ""]
    L += [r["body"].strip(), ""]

    if r["conflicts"]:
        L += ["---", t(lang, "conflicts_h")]
        for c in r["conflicts"]:
            L += [f"**{c['topic']}**: {c['explanation']}"]
            L += [f"- {t(lang, 'side_a')}: {x['claim']} [{x['src']}]" for x in c["side_a"]]
            L += [f"- {t(lang, 'side_b')}: {x['claim']} [{x['src']}]" for x in c["side_b"]]
            L += [""]

    L += ["---", t(lang, "verif_h")]
    if r["verified"]:
        sm = r["summary"]
        score_txt = t(lang, "score", score=r["conf_score"]) if r["conf_score"] is not None else ""
        L += [t(lang, "overall", label=label(lang, r["conf_label"]), score=score_txt),
              t(lang, "checked", n=sm["claims"], s=sm["supported"], p=sm["partial"], u=sm["unsupported"],
                c=sm["uncited"], r=r["retries"])]
    else:
        L += [t(lang, "verify_off")]
    if r["mode"] == "debate" and r["debate_stats"]:
        d = r["debate_stats"]
        L += [t(lang, "debate_balance", pro_n=d["pro"]["findings"], pro_c=d["pro"]["avg_credibility"],
                con_n=d["con"]["findings"], con_c=d["con"]["avg_credibility"])]

    L += ["", t(lang, "limits_h")]
    L += [f"- {x}" for x in r["limitations"]] or [t(lang, "no_limits")]

    L += ["", t(lang, "sources_h")]
    for i, u in enumerate(r["cited"], 1):
        s = r["scores_by_url"][u]
        extra = f"{label(lang, s['label'])} ({s['score']}), {domain(lang, s['domain_type'])}" + (f", {s['year']}" if s["year"] else "")
        if r["origin"].get(u):
            extra += f", {t(lang, 'past')} ({r['origin'][u][:10]})"
        L.append(f"{i}. {u} — {extra}")
    if r["other_read"]:
        L += ["", t(lang, "other_read")] + [f"- {u}" for u in r["other_read"]]

    L += ["", t(lang, "plan_h")] + [f"{i}. {q}" for i, q in enumerate(r["plan"], 1)]
    if r["failed"]:
        L += ["", t(lang, "failed_h")] + [f"- {q}" for q in r["failed"]]
    return "\n".join(L) + "\n"
