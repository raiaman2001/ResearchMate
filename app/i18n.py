"""Report ke static text (headings, limitations, summary lines) : en / hi / hinglish.
'hinglish' = purana (Stage 4/5) text, tests aur Hinglish users ke liye same rakha hai."""

T = {
    "hinglish": {
        "mode_debate": "*Mode: Debate (PRO vs CON, Judge ka nateeja)*",
        "conflicts_h": "## ⚖️ Conflicting information", "side_a": "Side A", "side_b": "Side B",
        "verif_h": "## 🔍 Verification & confidence",
        "overall": "**Overall confidence: {label}**{score}", "score": " (score {score})",
        "checked": "- Claims checked: {n} | ✅ {s} | ⚠️ {p} | ❌ {u} | uncited {c} | verifier retries: {r}",
        "verify_off": "Verification band thi (verify=False): claims check nahi hue.",
        "debate_balance": "- Debate balance: PRO {pro_n} findings (avg credibility {pro_c}) | CON {con_n} findings (avg credibility {con_c})",
        "limits_h": "## ❓ Open questions & limitations", "no_limits": "- (koi bada limitation nahi mila)",
        "sources_h": "## Sources", "other_read": "Padhe gaye par cite nahi hue:",
        "plan_h": "## Research plan", "failed_h": "Fail hui sub-questions:", "past": "purani research",
        "lim_gap": "Nahi mila: {g}", "lim_failed": "Research fail hui: {q}",
        "lim_conflicts": "{n} jagah sources aapas me contradict karte hain (upar dekhein).",
        "lim_bad": "{n} claim(s) verify nahi ho paye (❌): inhe sach maan kar use mat karo.",
        "lim_partial": "{n} claim(s) sirf partially supported hain (⚠️).",
        "lim_single": "{n} claim(s) sirf ek source par tike hain.",
        "lim_low": "{n} source(s) ki credibility kam hai (social/blog ya naya/anjaan source).",
        "lim_dropped": "{n} unverified finding(s) research stage me hata di gayi.",
        "lim_memory": ("{n} finding(s) purani research se reuse hui: unka source archive se dobara verify hua, "
                       "par web par update ho chuka ho sakta hai."),
        "labels": {}, "domains": {},
    },
    "en": {
        "mode_debate": "*Mode: Debate (PRO vs CON, verdict by the judge)*",
        "conflicts_h": "## ⚖️ Conflicting information", "side_a": "Side A", "side_b": "Side B",
        "verif_h": "## 🔍 Verification & confidence",
        "overall": "**Overall confidence: {label}**{score}", "score": " (score {score})",
        "checked": "- Claims checked: {n} | ✅ {s} | ⚠️ {p} | ❌ {u} | uncited {c} | verifier retries: {r}",
        "verify_off": "Verification was turned off (verify=False): claims were not checked.",
        "debate_balance": "- Debate balance: PRO {pro_n} findings (avg credibility {pro_c}) | CON {con_n} findings (avg credibility {con_c})",
        "limits_h": "## ❓ Open questions & limitations", "no_limits": "- (no major limitations found)",
        "sources_h": "## Sources", "other_read": "Read but not cited:",
        "plan_h": "## Research plan", "failed_h": "Failed sub-questions:", "past": "past research",
        "lim_gap": "Not found: {g}", "lim_failed": "Research failed: {q}",
        "lim_conflicts": "Sources contradict each other on {n} point(s) (see above).",
        "lim_bad": "{n} claim(s) could not be verified (❌): do not rely on them.",
        "lim_partial": "{n} claim(s) are only partially supported (⚠️).",
        "lim_single": "{n} claim(s) rest on a single source.",
        "lim_low": "{n} source(s) have low credibility (social/blog, or new/unknown source).",
        "lim_dropped": "{n} unverified finding(s) were dropped during research.",
        "lim_memory": ("{n} finding(s) were reused from past research: their sources were re-verified from the "
                       "archive, but the web may have changed since."),
        "labels": {}, "domains": {},
    },
    "hi": {
        "mode_debate": "*मोड: डिबेट (पक्ष बनाम विपक्ष, जज का निष्कर्ष)*",
        "conflicts_h": "## ⚖️ परस्पर विरोधी जानकारी", "side_a": "पक्ष A", "side_b": "पक्ष B",
        "verif_h": "## 🔍 सत्यापन और विश्वसनीयता",
        "overall": "**कुल विश्वसनीयता: {label}**{score}", "score": " (स्कोर {score})",
        "checked": "- जाँचे गए दावे: {n} | ✅ {s} | ⚠️ {p} | ❌ {u} | बिना सन्दर्भ {c} | सत्यापन पुनः प्रयास: {r}",
        "verify_off": "सत्यापन बंद था (verify=False): दावों की जाँच नहीं हुई।",
        "debate_balance": "- डिबेट संतुलन: पक्ष {pro_n} निष्कर्ष (औसत विश्वसनीयता {pro_c}) | विपक्ष {con_n} निष्कर्ष (औसत विश्वसनीयता {con_c})",
        "limits_h": "## ❓ अनुत्तरित प्रश्न और सीमाएँ", "no_limits": "- (कोई बड़ी सीमा नहीं मिली)",
        "sources_h": "## स्रोत", "other_read": "पढ़े गए पर उद्धृत नहीं किए गए:",
        "plan_h": "## शोध योजना", "failed_h": "विफल उप-प्रश्न:", "past": "पुरानी रिसर्च",
        "lim_gap": "नहीं मिला: {g}", "lim_failed": "शोध विफल रहा: {q}",
        "lim_conflicts": "{n} जगह स्रोत आपस में विरोधाभासी हैं (ऊपर देखें)।",
        "lim_bad": "{n} दावे सत्यापित नहीं हो पाए (❌): इन्हें सही मानकर उपयोग न करें।",
        "lim_partial": "{n} दावे केवल आंशिक रूप से समर्थित हैं (⚠️)।",
        "lim_single": "{n} दावे केवल एक स्रोत पर आधारित हैं।",
        "lim_low": "{n} स्रोतों की विश्वसनीयता कम है (सोशल/ब्लॉग या नया/अज्ञात स्रोत)।",
        "lim_dropped": "{n} असत्यापित निष्कर्ष शोध चरण में हटा दिए गए।",
        "lim_memory": ("{n} निष्कर्ष पुरानी रिसर्च से दोबारा उपयोग हुए: उनके स्रोत को संग्रह से फिर सत्यापित किया गया, "
                       "पर वेब पर जानकारी बदल चुकी हो सकती है।"),
        "labels": {"High": "उच्च", "Medium": "मध्यम", "Low": "निम्न", "Not verified": "सत्यापित नहीं"},
        "domains": {"government/academic/institution": "सरकारी/शैक्षणिक/संस्थागत", "major news": "प्रमुख समाचार",
                    "reference": "संदर्भ", "social/blog": "सोशल/ब्लॉग", "other": "अन्य",
                    "local document": "स्थानीय दस्तावेज़"},
    },
}


def t(lang, key, **kw):
    """Text lo (lang me na ho to hinglish). **kw se format."""
    s = T.get(lang, T["hinglish"]).get(key, T["hinglish"][key])
    return s.format(**kw) if kw else s


def label(lang, value):
    """High/Medium/Low/Not verified ka display naam (internal value English hi rehti hai)."""
    return T.get(lang, {}).get("labels", {}).get(value, value)


def domain(lang, value):
    return T.get(lang, {}).get("domains", {}).get(value, value)
