#!/usr/bin/env python3
"""
Tiny server for the filme app on OSMC / Kodi.

- Serves the static React/Next build from ./out
- POST /api/play  {"filename": "Some.Movie.2019.mkv"}  -> tells Kodi to play it

Stdlib only, so nothing to pip install on the Pi.

Config via environment variables:
  PORT         port to listen on                      (default 3000)
  STATIC_DIR   folder with the built app              (default ./out next to this file)
  KODI_URL     Kodi JSON-RPC endpoint                 (default http://localhost:8080/jsonrpc)
  KODI_USER    Kodi web server username               (default osmc)
  KODI_PASS    Kodi web server password               (default osmc)
  MOVIES_DIR   fallback folder if a file isn't in the Kodi library,
               e.g. /media/usb/Movies                 (default: none)
"""
import base64
import json
import os
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

PORT = int(os.environ.get("PORT", "3000"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parent / "out"))
KODI_URL = os.environ.get("KODI_URL", "http://localhost:8080/jsonrpc")
KODI_USER = os.environ.get("KODI_USER", "osmc")
KODI_PASS = os.environ.get("KODI_PASS", "osmc")
MOVIES_DIR = os.environ.get("MOVIES_DIR", "")


def kodi(method, params=None):
    """Call a Kodi JSON-RPC method and return its result."""
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    ).encode()
    req = urllib.request.Request(
        KODI_URL, payload, {"Content-Type": "application/json"}
    )
    token = base64.b64encode(f"{KODI_USER}:{KODI_PASS}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Kodi error"))
    return data.get("result")


def base_name(path):
    return path.replace("\\", "/").rstrip("/").split("/")[-1].lower()


def find_in_library(filename):
    """Match a filename against the movies in Kodi's library."""
    result = kodi("VideoLibrary.GetMovies", {"properties": ["file"]}) or {}
    target = base_name(filename)
    for movie in result.get("movies", []):
        if base_name(movie.get("file", "")) == target:
            return movie
    return None


def play(filename):
    movie = find_in_library(filename)
    if movie:
        # Playing by movieid keeps resume points / watched status working
        item = {"movieid": movie["movieid"]}
    elif MOVIES_DIR:
        if ".." in PurePosixPath(filename).parts:
            raise LookupError("Invalid filename")
        item = {"file": str(PurePosixPath(MOVIES_DIR) / filename)}
    else:
        raise LookupError(
            f"'{filename}' not found in Kodi library (and MOVIES_DIR is not set)"
        )
    kodi("Player.Open", {"item": item})


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def send_json(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path != "/api/play":
            return self.send_json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            filename = str(body.get("filename", "")).strip()
            if not filename:
                return self.send_json(400, {"error": "filename is required"})
            play(filename)
            self.send_json(200, {"ok": True})
        except LookupError as e:
            self.send_json(404, {"error": str(e)})
        except Exception as e:  # Kodi unreachable, bad credentials, etc.
            self.send_json(502, {"error": f"Kodi request failed: {e}"})


if __name__ == "__main__":
    if not STATIC_DIR.is_dir():
        raise SystemExit(f"Static folder not found: {STATIC_DIR}")
    print(f"Serving {STATIC_DIR} on http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()