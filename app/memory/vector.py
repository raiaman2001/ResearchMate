"""Chroma wrapper. Embeddings hum khud dete hain (Chroma ka default embedder internet se model download karta hai)."""
import chromadb
from chromadb.config import Settings

from app import config
from app.memory.embedder import get_embedder

_clients = {}


def _client(path):
    key = str(path)
    client = _clients.get(key)
    # Check if client was previously stopped or corrupted
    if client is not None:
        try:
            server = getattr(client, "_server", None)
            if server is not None and not hasattr(server, "bindings"):
                client = None
        except Exception:
            client = None

    if client is None:
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=key, settings=Settings(anonymized_telemetry=False))
        _clients[key] = client
    return client


class VectorStore:
    def __init__(self, name, embedder=None, path=None):
        self.path = path or config.CHROMA_DIR
        self.name = name
        self.embedder = embedder or get_embedder()
        self._col = None

    @property
    def col(self):
        try:
            if self._col is not None:
                # verify collection is healthy
                _ = self._col.count()
                return self._col
        except Exception:
            self._col = None

        client = _client(self.path)
        self._col = client.get_or_create_collection(
            self.name, embedding_function=None, metadata={"hnsw:space": "cosine"}
        )
        return self._col

    def add(self, ids, docs, metas):
        if not ids:
            return
        try:
            self.col.upsert(ids=list(ids), documents=list(docs), metadatas=list(metas),
                            embeddings=self.embedder.embed(docs))
        except Exception as e:
            if "bindings" in str(e).lower():
                _clients.clear()
                self._col = None
                self.col.upsert(ids=list(ids), documents=list(docs), metadatas=list(metas),
                                embeddings=self.embedder.embed(docs))
            else:
                raise

    def query(self, text, k=5, where=None):
        try:
            n = self.col.count()
            if n == 0:
                return []
            r = self.col.query(query_embeddings=self.embedder.embed([text]), n_results=min(k, n), where=where,
                               include=["documents", "metadatas", "distances"])
            return [{"id": i, "doc": d, "meta": m, "sim": round(1 - dist, 4)}
                    for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]
        except Exception as e:
            if "bindings" in str(e).lower():
                _clients.clear()
                self._col = None
                n = self.col.count()
                if n == 0:
                    return []
                r = self.col.query(query_embeddings=self.embedder.embed([text]), n_results=min(k, n), where=where,
                                   include=["documents", "metadatas", "distances"])
                return [{"id": i, "doc": d, "meta": m, "sim": round(1 - dist, 4)}
                        for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]
            raise

    def get(self, where=None):
        try:
            r = self.col.get(where=where, include=["documents", "metadatas"])
            return [{"id": i, "doc": d, "meta": m} for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])]
        except Exception as e:
            if "bindings" in str(e).lower():
                _clients.clear()
                self._col = None
                r = self.col.get(where=where, include=["documents", "metadatas"])
                return [{"id": i, "doc": d, "meta": m} for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])]
            raise

    def delete(self, where):
        try:
            self.col.delete(where=where)
        except Exception as e:
            if "bindings" in str(e).lower():
                _clients.clear()
                self._col = None
                self.col.delete(where=where)
            else:
                raise

    def count(self):
        try:
            return self.col.count()
        except Exception as e:
            if "bindings" in str(e).lower():
                _clients.clear()
                self._col = None
                return self.col.count()
            raise
