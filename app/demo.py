"""DEMO MODE: bina API key / internet ke poora UI chalane ke liye sample data wala fake LLM + fake web.

Sab content ILLUSTRATIVE hai (nakli hostnames: *.demo.gov.in, *.demo.ac.in ...): asli research nahi.
`streamlit run demo_ui.py` se chalta hai; UI par "DEMO MODE" badge dikhta hai.
"""
import asyncio
import re
import types

PAGES = {
    "https://ev-policy.demo.gov.in/scheme-review": (
        "Sample policy review", "2026-03-12", True,
        ["The sample purchase-incentive scheme supports electric two-wheelers and three-wheelers.",
         "Charging stations installed under the scheme roughly doubled between the two review periods.",
         "Several state governments announced additional road-tax waivers for electric vehicles."]),
    "https://mobility.demo.ac.in/ev-registrations-study": (
        "Sample registrations study", "2026-01-20", True,
        ["Electric two-wheeler registrations grew by more than forty percent in the latest fiscal year of the sample dataset.",
         "Battery pack prices have fallen steadily over the last five years.",
         "Charging access remains uneven between metro cities and rural districts."]),
    "https://www.business-daily.example.com/ev-outlook": (
        "Sample market outlook", "2025-11-02", True,
        ["Analysts expect electric vehicle sales to keep growing, with forecasts of fifteen to twenty percent annual growth.",
         "Several manufacturers announced new electric models aimed at first-time buyers.",
         "Dependence on imported battery cells is a supply-chain risk."]),
    "https://sample-blog.medium.com/why-the-ev-boom-is-overhyped": (
        "Sample opinion post", "2023-06-09", False,
        ["The growth narrative is overhyped, and a realistic estimate is closer to five percent annual growth.",
         "High upfront costs and limited financing for buyers slow down adoption."]),
    "https://stats.demo.org.in/charging-points": (
        "Sample charging statistics", "2026-02-15", True,
        ["Public charging points are concentrated in a handful of cities and highway coverage is thin.",
         "Fast chargers make up less than ten percent of the installed public points."]),
}
PAGE_KEYS = list(PAGES)
PRO_PAGES, CON_PAGES = [0, 1, 2], [3, 4, 1]
Q_PAGES = {"market": [1, 2, 3], "polic": [0], "barrier": [4, 1, 2]}          # sub-question keyword -> pages

HI = {
    "The sample purchase-incentive scheme supports electric two-wheelers and three-wheelers.": "नमूना प्रोत्साहन योजना इलेक्ट्रिक दोपहिया और तिपहिया वाहनों को सहारा देती है",
    "Charging stations installed under the scheme roughly doubled between the two review periods.": "योजना के तहत लगे चार्जिंग स्टेशनों की संख्या दो समीक्षा अवधियों के बीच लगभग दोगुनी हो गई",
    "Several state governments announced additional road-tax waivers for electric vehicles.": "कई राज्य सरकारों ने इलेक्ट्रिक वाहनों के लिए अतिरिक्त रोड-टैक्स छूट की घोषणा की",
    "Electric two-wheeler registrations grew by more than forty percent in the latest fiscal year of the sample dataset.": "नमूना डेटा के अनुसार पिछले वित्त वर्ष में इलेक्ट्रिक दोपहिया पंजीकरण चालीस प्रतिशत से अधिक बढ़े",
    "Battery pack prices have fallen steadily over the last five years.": "पिछले पाँच वर्षों में बैटरी पैक की कीमतें लगातार घटी हैं",
    "Charging access remains uneven between metro cities and rural districts.": "महानगरों और ग्रामीण ज़िलों के बीच चार्जिंग की पहुँच असमान बनी हुई है",
    "Analysts expect electric vehicle sales to keep growing, with forecasts of fifteen to twenty percent annual growth.": "विश्लेषकों के अनुसार बिक्री बढ़ती रहेगी और वार्षिक वृद्धि का अनुमान पंद्रह से बीस प्रतिशत है",
    "Several manufacturers announced new electric models aimed at first-time buyers.": "कई निर्माताओं ने पहली बार खरीदने वालों के लिए नए इलेक्ट्रिक मॉडल घोषित किए",
    "Dependence on imported battery cells is a supply-chain risk.": "आयातित बैटरी सेल पर निर्भरता आपूर्ति-श्रृंखला का जोखिम है",
    "The growth narrative is overhyped, and a realistic estimate is closer to five percent annual growth.": "वृद्धि की कहानी बढ़ा-चढ़ाकर पेश की गई है और यथार्थवादी अनुमान लगभग पाँच प्रतिशत वार्षिक है",
    "High upfront costs and limited financing for buyers slow down adoption.": "ऊँची शुरुआती लागत और खरीदारों के लिए सीमित वित्तपोषण अपनाने की गति धीमी करते हैं",
    "Public charging points are concentrated in a handful of cities and highway coverage is thin.": "सार्वजनिक चार्जिंग पॉइंट कुछ ही शहरों में केंद्रित हैं और हाईवे पर कवरेज कम है",
    "Fast chargers make up less than ten percent of the installed public points.": "फास्ट चार्जर कुल सार्वजनिक पॉइंट का दस प्रतिशत से कम हैं",
}


class _Resp:
    status_code = 200

    def __init__(self, url):
        title, date, author, sentences = PAGES[url]
        meta = f'<meta property="article:published_time" content="{date}">' + ('<meta name="author" content="Demo Author">' if author else "")
        self.text = f"<html><head><title>{title}</title>{meta}</head><body><article><p>{' '.join(sentences)}</p></article></body></html>"
        self.content = self.text.encode("utf-8")

    def raise_for_status(self):
        pass


def install_demo_web():
    import requests

    def get(url, **kw):
        if url in PAGES:
            return _Resp(url)
        resp = types.SimpleNamespace(status_code=404, text="", content=b"")

        def fail():
            raise requests.HTTPError("404 (demo mode: sirf sample pages hain)")
        resp.raise_for_status = fail
        return resp
    requests.get = get


def _ns(**k):
    return types.SimpleNamespace(**k)


def _tool(name, inp, n=[0]):
    n[0] += 1
    return _ns(stop_reason="tool_use", usage=_ns(input_tokens=1800, output_tokens=260),
               content=[_ns(type="tool_use", id=f"d{n[0]}", name=name, input=inp)])


class DemoClient:
    """Anthropic AsyncClient jaisa interface: client.messages.create(...)"""

    def __init__(self, delay=0.12):
        self.delay, self.messages = delay, self

    async def create(self, **kw):
        await asyncio.sleep(self.delay)
        system, tools = kw.get("system", ""), {t["name"] for t in (kw.get("tools") or [])}
        user = kw["messages"][0]["content"]
        if "read_webpage" in tools:
            return self._researcher(kw, system, user)
        if "submit" in tools:
            if "fact-consistency" in system:
                return self._conflicts(user)
            if "fact-checker" in system:
                return self._verifier(user)
            if "knowledge-graph" in system:
                return self._triples(user)
            if "debate planner" in system:
                return _tool("submit", {"pro": ["Evidence that EV adoption is accelerating", "Policy and cost advantages"],
                                        "con": ["Barriers: charging access and upfront cost", "Supply-chain and growth-estimate risks"]})
            return _tool("submit", {"sub_questions": ["How large is the EV market and how fast is it growing?",
                                                      "Which government policies support adoption?",
                                                      "What are the main barriers such as charging and costs?"]})
        text = self._writer(system, user)
        return _ns(stop_reason="end_turn", usage=_ns(input_tokens=2600, output_tokens=540),
                   content=[_ns(type="text", text=text)])

    # ---- researcher: 2-3 sample pages padho, unke sentences findings banao ----
    def _researcher(self, kw, system, user):
        q = user.replace("Sub-question: ", "").lower()
        if "SAMARTHAN" in system:
            idxs = PRO_PAGES
        elif "VIRODH" in system:
            idxs = CON_PAGES
        else:
            idxs = next((v for k, v in Q_PAGES.items() if k in q), [abs(hash(q)) % len(PAGE_KEYS)])
        urls = [PAGE_KEYS[i] for i in idxs]
        if sum(1 for m in kw["messages"] if m["role"] == "assistant") == 0:
            return _ns(stop_reason="tool_use", usage=_ns(input_tokens=1500, output_tokens=120),
                       content=[_ns(type="tool_use", id=f"r{i}", name="read_webpage", input={"url": u}) for i, u in enumerate(urls)])
        findings = [{"claim": s, "source_url": u} for u in urls for s in PAGES[u][3][:2]][:5]
        return _tool("submit_findings", {"findings": findings, "gaps": ""})

    def _lines(self, user, pattern):
        return [m.groups() for m in re.finditer(pattern, user, flags=re.M)]

    def _conflicts(self, user):
        rows = self._lines(user, r"^F(\d+) \[source (\d+)\] (.+)$")
        growth = [(int(i), s, c) for i, s, c in rows if "annual growth" in c]
        pair = None
        for a in growth:
            for b in growth:
                if a[1] != b[1] and a[0] < b[0]:
                    pair = (a, b)
        if not pair:
            return _tool("submit", {"conflicts": []})
        return _tool("submit", {"conflicts": [{"topic": "Annual EV growth estimate", "claim_ids_a": [pair[0][0]],
                                               "claim_ids_b": [pair[1][0]],
                                               "explanation": "One source forecasts fifteen to twenty percent a year, another about five percent."}]})

    def _verifier(self, user):
        claim = user.split("CLAIM: ", 1)[1].split("\n\nSOURCES:", 1)[0]
        text = " ".join(re.findall(r"<source[^>]*>(.*?)</source>", user, flags=re.S))
        cwords = set(re.findall(r"[a-z]{4,}", claim.lower()))
        sents = re.split(r"(?<=[.])\s+", text)
        best = max(sents, key=lambda s: len(cwords & set(re.findall(r"[a-z]{4,}", s.lower()))), default="").strip()
        verdict = "partial" if "more than doubled" in claim.lower() else "supported"
        reason = "Source reports a smaller increase than the claim states." if verdict == "partial" else "Matches the cited source."
        return _tool("submit", {"verdict": verdict, "evidence_quote": best, "reason": reason})

    def _triples(self, user):
        rules = [("scheme", ("Purchase incentive scheme", "supports", "Electric two-wheelers")),
                 ("charging points", ("Public charging network", "concentrated in", "Metro cities")),
                 ("battery pack", ("Battery pack prices", "declined over", "Five years")),
                 ("analysts", ("Analysts", "forecast", "Annual EV growth"))]
        out = []
        for i, claim in self._lines(user, r"^F(\d+): (.+)$"):
            for key, (s, r, o) in rules:
                if key in claim.lower() and len(out) < 4 and all(t["subject"] != s for t in out):
                    out.append({"subject": s, "subject_type": "organisation", "relation": r, "object": o,
                                "object_type": "topic", "finding_id": int(i)})
        return _tool("submit", {"triples": out})

    # ---- writer / judge ----
    def _writer(self, system, user):
        rows = self._lines(user, r"^\[(\d+)\](?: \[(PRO|CON)\])? \(credibility: \w+\)(?: \(purani research, [^)]*\))? (.+)$")
        hindi = "शुद्ध हिंदी" in user
        tr = (lambda c: HI.get(c, c).rstrip(".") + "।") if hindi else (lambda c: c)
        seen, items = set(), []
        for n, stance, claim in rows:
            if claim not in seen:
                seen.add(claim)
                items.append((int(n), stance, claim))
        cite = lambda n: f"[{n}]"
        if "nishpaksh judge" in system:
            pro = [f"- {tr(c)} {cite(n)}" for n, s, c in items if s == "PRO"][:4]
            con = [f"- {tr(c)} {cite(n)}" for n, s, c in items if s == "CON"][:4]
            first = lambda s: next((n for n, st, _ in items if st == s), 1)
            if hindi:
                return ("## प्रश्न (Question)\nक्या भारत में EV अपनाना फ़ायदेमंद है?\n\n## पक्ष में (Case For)\n" + "\n".join(pro) +
                        "\n\n## विपक्ष में (Case Against)\n" + "\n".join(con) + f"\n\n## साक्ष्यों का मूल्यांकन (Weighing the evidence)\n"
                        f"नीति-समर्थन वाले स्रोत अधिक विश्वसनीय हैं {cite(first('PRO'))}।\n\n## निर्णय (Verdict)\nसाक्ष्य सावधानी के साथ अपनाने की ओर झुके हैं।\n\n"
                        "## सीमाएँ (Limitations)\nसभी स्रोत नमूना डेटा हैं।")
            return ("## Question\nIs EV adoption beneficial for India?\n\n## Case For\n" + "\n".join(pro) + "\n\n## Case Against\n" + "\n".join(con) +
                    f"\n\n## Weighing the evidence\nThe policy-backed sources carry more weight than the opinion post {cite(first('PRO'))}.\n\n"
                    "## Verdict\nThe evidence leans towards adoption being beneficial, with real caveats on charging access and growth estimates.\n\n"
                    "## Limitations\nAll sources are sample data and differ in methodology.")
        bullets = [f"- {tr(c)} {cite(n)}" for n, _, c in items][:7]
        extra = [(n, c) for n, _, c in items if "forty percent" in c]
        if extra:
            bullets.insert(2, (f"- {'दोपहिया EV बिक्री दोगुनी से भी अधिक हो गई' if hindi else 'Two-wheeler EV sales have more than doubled in recent years'}"
                               f"{'।' if hindi else ''} {cite(extra[0][0])}").replace("।.", "।"))
        a, b = (items[0][0], items[-1][0]) if items else (1, 1)
        if hindi:
            return (f"## सारांश (Summary)\nस्रोत तेज़ वृद्धि की ओर इशारा करते हैं, जिसे नीति-प्रोत्साहन और घटती बैटरी कीमतों का सहारा है {cite(a)}। "
                    f"फिर भी वृद्धि के अनुमान स्रोतों के बीच काफ़ी अलग हैं {cite(b)}।\n\n## मुख्य निष्कर्ष (Key Findings)\n" + "\n".join(bullets) +
                    "\n\n## सीमाएँ (Limitations)\nसभी स्रोत नमूना डेटा हैं और उनकी कार्यप्रणाली अलग है।")
        return (f"## Summary\nThe sources point to fast growth backed by policy incentives and falling battery prices {cite(a)}. "
                f"Growth estimates differ widely between sources, so headline numbers should be read with caution {cite(b)}.\n\n"
                "## Key Findings\n" + "\n".join(bullets) + "\n\n## Limitations\nAll sources are sample data and differ in methodology.")
