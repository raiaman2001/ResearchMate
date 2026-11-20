import os
import sys
import time
import webbrowser
import threading
import uvicorn

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

def main():
    print("=" * 60)
    print("  Starting ResearchMate — 3D Research Command Deck")
    print("=" * 60)
    print("  Server URL : http://localhost:8000")
    print("  Demo Mode  : http://localhost:8000/?demo=1")
    print("=" * 60)
    print("  Opening browser in a few seconds...")
    print("  Press Ctrl+C in terminal to stop server.\n")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run uvicorn server
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()

