"""Prompt injection se bachav: web page ka text DATA hai, command nahi."""
import re

SUSPICIOUS = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|prompts)"
    r"|disregard (the |all )?(previous|above|system)"
    r"|पिछले (सभी )?निर्देश|निर्देशों को (अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल)|सिस्टम प्रॉम्प्ट"
    r"|you are now |new instructions:|system prompt|reveal your (prompt|instructions))",
    re.IGNORECASE,
)


def looks_injected(text):
    return bool(SUSPICIOUS.search(text))


def wrap_source(url, text):
    """Text ko <source> tag me band karo; andar ka closing tag tod do taaki bahar na nikle."""
    safe = text.replace("</source", "<\\/source")
    return f'<source url="{url}">\n{safe}\n</source>'
