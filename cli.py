"""Terminal: python cli.py   (flags: --no-verify, --no-conflicts, --sequential, --lang hi|en|hinglish|auto,
--export pdf|docx|md)"""
import sys

from app.pipeline import run_research

def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default


if __name__ == "__main__":
    topic = input("Research topic: ").strip()
    if topic:
        res = run_research(topic, on_event=print, verify="--no-verify" not in sys.argv,
                           detect_conflicts="--no-conflicts" not in sys.argv,
                           parallel="--sequential" not in sys.argv, language=_arg("--lang", "auto"))
        print("\n" + "=" * 60)
        if not res.ok:
            print("Error:", res.error)
        else:
            print(res.report)
            for w in res.warnings:
                print("⚠️", w)
            print(f"\nSaved: {res.file_path}  (language: {res.language})")
            fmt = _arg("--export")
            if fmt:
                from app.export import ExportError, download_filename, export_report
                try:
                    data, _, ext = export_report(res.report, fmt, topic)
                    name = download_filename(topic, ext)[2]
                    open(name, "wb").write(data)
                    print(f"Exported: {name}")
                except ExportError as e:
                    print("Export fail:", e)
            print(f"Confidence: {res.confidence_label} | Time: {res.elapsed}s | "
                  f"Tokens: {res.input_tokens}+{res.output_tokens} | Est. cost: ${res.cost_usd:.4f}")
