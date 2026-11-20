"""Embeddings. Default: HashingEmbedder (offline, koi download nahi, deterministic).

Dhyan do: hashing embedder LEXICAL hai (shabd overlap), semantic nahi: "EV" aur "electric vehicle"
ko wo same nahi samajhta. Behtar quality ke liye .env me EMBEDDER=sbert (sentence-transformers) lagao
aur MEMORY_MIN_SIM / DOC_MIN_SIM ko tune karo.
"""
import hashlib
import math
import re

from app import config
from app.lang import nfc, normalize_digits

STOP = set("""the and for that with this from are was were has have had will would can could not but its their
there which about into more than also been being over under between while such only other some what when where
who whom how why does did you your our they them these those then very just said says per via
का की के है हैं में और से को पर यह वह था थी थे एक भी तो ही कि जो इस उस लिए साथ द्वारा""".split())


def tokenize(text):
    text = normalize_digits(nfc(text)).lower()
    return [w for w in re.findall(r"[a-z0-9\u0900-\u097f]+", text) if len(w) > 1 and w not in STOP]


class HashingEmbedder:
    name = "hashing-512"

    def __init__(self, dim=512):
        self.dim = dim

    def _one(self, text):
        toks = tokenize(text)
        feats = [(t, 1.0) for t in toks] + [(f"{a}_{b}", 0.5) for a, b in zip(toks, toks[1:])]
        vec = [0.0] * self.dim
        for f, w in feats:
            h = int(hashlib.md5(f.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += w if (h >> 40) & 1 else -w         # signed hashing: collisions kam hurt karte hain
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts):
        return [self._one(t) for t in texts]


class SentenceTransformerEmbedder:
    """Optional: pip install sentence-transformers. (Sandbox me test nahi hua: model download chahiye.)"""
    name = "sbert-minilm"

    def __init__(self, model=None):
        model = model or config.SBERT_MODEL
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)

    def embed(self, texts):
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()


_cached = {}


def get_embedder():
    kind = config.EMBEDDER
    if kind not in _cached:
        _cached[kind] = SentenceTransformerEmbedder() if kind == "sbert" else HashingEmbedder()
    return _cached[kind]
