"""Language detection (Hindi / Hinglish / English) + Devanagari helpers + Multi-language support."""
import re
import unicodedata

from app import config

DEVA_RE = re.compile(r"[\u0900-\u097F]")
DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

LANGS = (
    "en", "hi", "hinglish",
    # Indian / National Languages
    "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur",
    # International Languages
    "es", "fr", "de", "zh", "ja", "ar", "ru", "pt"
)

LANG_NAME = {
    "en": "English", "hi": "Hindi (हिंदी)", "hinglish": "Hinglish",
    "bn": "Bengali (বাংলা)", "ta": "Tamil (தமிழ்)", "te": "Telugu (తెలుగు)",
    "mr": "Marathi (मराठी)", "gu": "Gujarati (ગુજરાતી)", "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)", "pa": "Punjabi (ਪੰਜਾਬੀ)", "ur": "Urdu (اردو)",
    "es": "Spanish (Español)", "fr": "French (Français)", "de": "German (Deutsch)",
    "zh": "Chinese (中文)", "ja": "Japanese (日本語)", "ar": "Arabic (العربية)",
    "ru": "Russian (Русский)", "pt": "Portuguese (Português)"
}

# Roman-script Hindi ke shabd. STRONG = lagbhag sirf Hindi me aate hain; WEAK = English me bhi aa sakte hain.
HINGLISH_STRONG = set("""kya hai hain kaise kaisa kaisi nahi nahin mujhe batao btao karo kijiye chahiye raha rahi rahe hoga
hogi honge sakte sakta sakti kyun kyu kitna kitne kaun kab wala wali aur bare baare liye mein tum aap mera meri apna
hota hoti hote kaam jaldi abhi bahut zyada kam sabse kar karna karne karta karti karte karen dega degi denge khatam
naukri naukriyan padhai sabhi koi kuch lekin magar isme usme isse usse hum sirf bilkul pehle baad saal sarkar yojana
desh paisa hamesha kabhi kahan kyunki isliye jaise waise toh mujhse unka unki bataiye samjhao samjhaiye dikhao zaroori
behtar sahi galat achha acha kitni kaisi""".split())
# "the" jaan-boojh ke nahi: wo English ka sabse common shabd hai (Hindi "थे" ka Roman form ignore karna theek hai)
HINGLISH_WEAK = set("me ka ke ki ko se par pe bhi ye yeh wo woh iska uska tha thi".split())


def nfc(text):
    return unicodedata.normalize("NFC", text)


def normalize_digits(text):
    """Devanagari ank (४०) -> ASCII (40)."""
    return text.translate(DEVA_DIGITS)


def script_ratio(text):
    """Letters me Devanagari ka hissa (0..1)."""
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if DEVA_RE.match(c)) / len(letters) if letters else 0.0


def hinglish_stats(text):
    words = re.findall(r"[a-z]+", text.lower())
    strong = sum(1 for w in words if w in HINGLISH_STRONG)
    weak = sum(1 for w in words if w in HINGLISH_WEAK)
    return strong, weak, len(words)


def hinglish_ratio(text):
    strong, weak, n = hinglish_stats(text)
    return (strong + weak) / n if n else 0.0


def detect_language(text):
    """'hi' (Devanagari), 'hinglish' (Roman Hindi) ya 'en'. Chhote queries ke liye bana hai."""
    if script_ratio(text) >= 0.3:
        return "hi"
    strong, weak, n = hinglish_stats(text)
    if strong >= 2:                                    # 2+ pakke Hindi shabd: Hinglish
        return "hinglish"
    if strong >= 1 and (strong + weak) >= 2 and (strong + weak) / n >= 0.3:
        return "hinglish"
    return "en"


def resolve_language(option, topic):
    """option: None/'auto'/'en'/'hi'/etc. Galat value par ValueError."""
    option = (option or config.DEFAULT_REPORT_LANGUAGE or "auto").lower()
    if option == "auto":
        return detect_language(topic)
    if option not in LANGS:
        raise ValueError(f"Unknown language: {option}")
    return option


# Writer/Judge ko report ki bhasha ka instruction. Headings ke saath English keyword bracket me
# zaroor rakhte hain taaki verifier (aur code) unhe Limitations/Verdict ke hisaab se pehchan sake.
WRITER_LANG_INSTRUCTION = {
    "en": "\n\nReport language: English.",
    "hinglish": "\n\nReport language: Hinglish (Roman script me Hindi aur English ka mix, jaise user likhta hai).",
    "hi": ("\n\nReport language: शुद्ध हिंदी (देवनागरी)। नाम, संस्थाएँ और technical शब्द English में रह सकते हैं। "
           "Findings अगर English में हैं तो उनका अर्थ बदले बिना हिंदी में अनुवाद करके लिखो। "
           "Citation numbers हमेशा ASCII अंकों में लिखो, जैसे [3] (देवनागरी अंकों में नहीं)। "
           "Section headings हिंदी में लिखो पर उनके साथ English keyword कोष्ठक में ज़रूर रखो, जैसे "
           "`## सारांश (Summary)`, `## मुख्य निष्कर्ष (Key Findings)`, `## सीमाएँ (Limitations)`; "
           "debate में: `## प्रश्न (Question)`, `## पक्ष में (Case For)`, `## विपक्ष में (Case Against)`, "
           "`## साक्ष्यों का मूल्यांकन (Weighing the evidence)`, `## निर्णय (Verdict)`, `## सीमाएँ (Limitations)`."),
    "bn": ("\n\nReport language: Bengali (বাংলা). Write the complete report in natural, fluent Bengali. "
           "Section headings must include English keyword in brackets, e.g. `## সারসংক্ষেপ (Summary)`, "
           "`## মূল ফলাফল (Key Findings)`, `## সীমাবদ্ধতা (Limitations)`. Citations in ASCII e.g. [1]."),
    "ta": ("\n\nReport language: Tamil (தமிழ்). Write the complete report in natural, fluent Tamil. "
           "Section headings must include English keyword in brackets, e.g. `## சுருக்கம் (Summary)`, "
           "`## முக்கிய கண்டுபிடிப்புகள் (Key Findings)`, `## வரம்புகள் (Limitations)`. Citations in ASCII e.g. [1]."),
    "te": ("\n\nReport language: Telugu (తెలుగు). Write the complete report in natural, fluent Telugu. "
           "Section headings must include English keyword in brackets, e.g. `## సారాంశం (Summary)`, "
           "`## ముఖ్య ఫలితాలు (Key Findings)`, `## పరిమితులు (Limitations)`. Citations in ASCII e.g. [1]."),
    "mr": ("\n\nReport language: Marathi (मराठी). Write the complete report in natural, fluent Marathi. "
           "Section headings must include English keyword in brackets, e.g. `## सारांश (Summary)`, "
           "`## मुख्य निष्कर्ष (Key Findings)`, `## मर्यादा (Limitations)`. Citations in ASCII e.g. [1]."),
    "gu": ("\n\nReport language: Gujarati (ગુજરાતી). Write the complete report in natural, fluent Gujarati. "
           "Section headings must include English keyword in brackets, e.g. `## સારાંશ (Summary)`, "
           "`## મુખ્ય તારણો (Key Findings)`, `## મર્યાદાઓ (Limitations)`. Citations in ASCII e.g. [1]."),
    "kn": ("\n\nReport language: Kannada (ಕನ್ನಡ). Write the complete report in natural, fluent Kannada. "
           "Section headings must include English keyword in brackets, e.g. `## ಸಾರಾಂಶ (Summary)`, "
           "`## ಪ್ರಮುಖ ಸಂಶೋಧನೆಗಳು (Key Findings)`, `## ಮಿತಿಗಳು (Limitations)`. Citations in ASCII e.g. [1]."),
    "ml": ("\n\nReport language: Malayalam (മലയാളം). Write the complete report in natural, fluent Malayalam. "
           "Section headings must include English keyword in brackets, e.g. `## സംഗ്രഹം (Summary)`, "
           "`## പ്രധാന കണ്ടെത്തലുകൾ (Key Findings)`, `## പരിമിതികൾ (Limitations)`. Citations in ASCII e.g. [1]."),
    "pa": ("\n\nReport language: Punjabi (ਪੰਜਾਬੀ). Write the complete report in natural, fluent Punjabi. "
           "Section headings must include English keyword in brackets, e.g. `## ਸੰਖੇਪ (Summary)`, "
           "`## ਮੁੱਖ ਨਤੀਜੇ (Key Findings)`, `## ਸੀਮਾਵਾਂ (Limitations)`. Citations in ASCII e.g. [1]."),
    "ur": ("\n\nReport language: Urdu (اردو). Write the complete report in natural, fluent Urdu. "
           "Section headings must include English keyword in brackets, e.g. `## خلاصہ (Summary)`, "
           "`## اہم نتائج (Key Findings)`, `## حدود (Limitations)`. Citations in ASCII e.g. [1]."),
    "es": ("\n\nReport language: Spanish (Español). Write the complete report in natural, fluent Spanish. "
           "Section headings must include English keyword in brackets, e.g. `## Resumen (Summary)`, "
           "`## Hallazgos clave (Key Findings)`, `## Limitaciones (Limitations)`. Citations in ASCII e.g. [1]."),
    "fr": ("\n\nReport language: French (Français). Write the complete report in natural, fluent French. "
           "Section headings must include English keyword in brackets, e.g. `## Résumé (Summary)`, "
           "`## Principales conclusions (Key Findings)`, `## Limites (Limitations)`. Citations in ASCII e.g. [1]."),
    "de": ("\n\nReport language: German (Deutsch). Write the complete report in natural, fluent German. "
           "Section headings must include English keyword in brackets, e.g. `## Zusammenfassung (Summary)`, "
           "`## Wichtigste Erkenntnisse (Key Findings)`, `## Einschränkungen (Limitations)`. Citations in ASCII e.g. [1]."),
    "zh": ("\n\nReport language: Simplified Chinese (简体中文). Write the complete report in natural, fluent Chinese. "
           "Section headings must include English keyword in brackets, e.g. `## 摘要 (Summary)`, "
           "`## 主要发现 (Key Findings)`, `## 局限性 (Limitations)`. Citations in ASCII e.g. [1]."),
    "ja": ("\n\nReport language: Japanese (日本語). Write the complete report in natural, fluent Japanese. "
           "Section headings must include English keyword in brackets, e.g. `## 要約 (Summary)`, "
           "`## 主な調査結果 (Key Findings)`, `## 限界点 (Limitations)`. Citations in ASCII e.g. [1]."),
    "ar": ("\n\nReport language: Arabic (العربية). Write the complete report in natural, fluent Arabic. "
           "Section headings must include English keyword in brackets, e.g. `## ملخص (Summary)`, "
           "`## النتائج الرئيسية (Key Findings)`, `## القيود (Limitations)`. Citations in ASCII e.g. [1]."),
    "ru": ("\n\nReport language: Russian (Русский). Write the complete report in natural, fluent Russian. "
           "Section headings must include English keyword in brackets, e.g. `## Резюме (Summary)`, "
           "`## Ключевые выводы (Key Findings)`, `## Ограничения (Limitations)`. Citations in ASCII e.g. [1]."),
    "pt": ("\n\nReport language: Portuguese (Português). Write the complete report in natural, fluent Portuguese. "
           "Section headings must include English keyword in brackets, e.g. `## Resumo (Summary)`, "
           "`## Principais descobertas (Key Findings)`, `## Limitações (Limitations)`. Citations in ASCII e.g. [1]."),
}

RESEARCH_LANG_NOTE = {
    "en": "",
    "hinglish": ("\n\nUser Hindi/Hinglish me hai: web_search me English aur Hindi dono queries try karo. "
                 "Hindi aur English dono sources valid hain. Claim ko source ki apni bhasha me likho (translate mat karo) "
                 "taaki quote-verify sahi rahe; Writer baad me translate karega."),
}
RESEARCH_LANG_NOTE["hi"] = RESEARCH_LANG_NOTE["hinglish"]

PLAN_LANG_NOTE = {
    "en": "",
    "hinglish": "\nSub-questions Hinglish (Roman script) me likho.",
    "hi": "\nSub-questions हिंदी (देवनागरी) में लिखो (नाम और technical शब्द English में रह सकते हैं).",
}

for l_code, l_label in LANG_NAME.items():
    if l_code not in RESEARCH_LANG_NOTE:
        RESEARCH_LANG_NOTE[l_code] = f"\n\nTarget language is {l_label}. Search both in English and {l_label} to gather best global and local sources."
    if l_code not in PLAN_LANG_NOTE:
        PLAN_LANG_NOTE[l_code] = f"\nSub-questions must be written in {l_label}."
