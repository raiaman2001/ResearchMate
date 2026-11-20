"""Process-wide singletons (Streamlit reruns ke beech state bachane ke liye: MemorySaver, Chroma, KG)."""
from app.graph import Orchestrator

_orchestrator = None
DEMO = False


def enable_demo():
    """Sample-data mode: fake LLM + fake web + alag temp storage (asli data/history ko nahi chhuta)."""
    global _orchestrator, DEMO
    import tempfile
    from pathlib import Path
    from app import config
    from app.demo import DemoClient, install_demo_web
    tmp = Path(tempfile.mkdtemp(prefix="researchmate_demo_"))
    config.DB_PATH, config.CHROMA_DIR, config.KG_PATH = tmp / "demo.db", tmp / "chroma", tmp / "kg.json"
    config.REPORTS_DIR = tmp / "reports"           # demo reports project folder me nahi likhi jati
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    install_demo_web()
    _orchestrator, DEMO = Orchestrator(client_factory=lambda: DemoClient()), True
    return _orchestrator


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def set_orchestrator(o):
    """Tests ke liye (fake LLM wala orchestrator inject karne ko)."""
    global _orchestrator
    _orchestrator = o
