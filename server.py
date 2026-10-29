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
import urllib.parse
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

PORT = int(os.environ.get("PORT", "3000"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parent / "out"))
KODI_URL = os.environ.get("KODI_URL", "http://localhost:8080/jsonrpc")
KODI_USER = "osmc"
KODI_PASS = "osmc"
MOVIES_DIR = os.environ.get("MOVIES_DIR", "")
TMDB_TOKEN = os.environ.get("TMDB_READ_ACCESS_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJlODI0YmE2ODhlMWQwN2ZmYzdmNjE5NGE1MWZiZTc0MSIsIm5iZiI6MTY5MTU3NTY1Ni44MzEsInN1YiI6IjY0ZDM2NTY4YjZjMjY0MTE1Njk5YTUyYSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.3lx7QW1oSrMqlnAJL1LX8J9gJp54o4no2BJdE3zyMSI")
METADATA_DIR = Path(__file__).resolve().parent / "public" / "metadata"


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


def get_tmdb_metadata(title, year=None):
    """Fetch and cache movie metadata and poster from TMDB."""
    safe_title = title.replace(" ", "_").lower()
    meta_file = METADATA_DIR / f"{safe_title}.json"
    
    if meta_file.exists():
        print(f"Cache hit: {meta_file}")
        with open(meta_file, "r") as f:
            return json.load(f)

    if not TMDB_TOKEN:
        print("TMDB_TOKEN not set")
        return None

    # Clean title: remove " - HBO", " (2025)", " 1080p", etc.
    clean_title = re.sub(r'\s*-\s*HBO$', '', title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\s*\(\d{4}\)', '', clean_title)
    clean_title = re.sub(r'\s*\d{4}$', '', clean_title)
    clean_title = re.sub(r'\s*(1080p|720p|BluRay|WEB-DL|WEBRip|x264|x265|HEVC|DTS|AAC).*', '', clean_title, flags=re.IGNORECASE)
    clean_title = clean_title.strip()

    try:
        # Attempt 1: Specific title and year
        print(f"Fetching TMDB data for {clean_title} ({year if year else 'any year'})...")
        url = f"https://api.themoviedb.org/3/search/movie?query={urllib.parse.quote(clean_title)}"
        if year:
            url += f"&year={year}"
        
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {TMDB_TOKEN}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        
        results = data.get("results", [])
        if results:
            movie = results[0]
            # TMDB search results usually don't include genres in the base search.
            # To get genres/cast, we'd need another call to /movie/{id}.
            # For now, let's fetch the full movie details to get genres and cast.
            try:
                details_url = f"https://api.themoviedb.org/3/movie/{movie['id']}?append_to_response=credits"
                det_req = urllib.request.Request(details_url)
                det_req.add_header("Authorization", f"Bearer {TMDB_TOKEN}")
                with urllib.request.urlopen(det_req, timeout=10) as det_resp:
                    details = json.load(det_resp)
                
                # Map genre IDs to names using a simple map or TMDB's genre list
                # For simplicity, we can just take the first genre name if available
                genres_list = details.get("genres", [])
                genre_name = genres_list[0].get("name") if genres_list else None
                
                cast_list = details.get("credits", {}).get("cast", [])
                cast = [c.get("name") for c in cast_list[:3]] # Top 3 actors
                
                meta = {
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path"),
                    "release_date": movie.get("release_date"),
                    "genre": genre_name,
                    "cast": cast,
                }
            except Exception as e:
                print(f"Error fetching details for {movie['id']}: {e}")
                meta = {
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path"),
                    "release_date": movie.get("release_date"),
                    "genre": None,
                    "cast": [],
                }
            
            METADATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(meta_file, "w") as f:
                json.dump(meta, f)
                
            if meta["poster_path"]:
                poster_url = f"https://image.tmdb.org/t/p/w500{meta['poster_path']}"
                poster_path = METADATA_DIR / f"{safe_title}.jpg"
                with urllib.request.urlopen(poster_url, timeout=10) as p_resp:
                    with open(poster_path, "wb") as p_file:
                        p_file.write(p_resp.read())
                meta["poster_path"] = f"/public/metadata/{safe_title}.jpg"
                
            return meta


        # Attempt 2: Broader search (ignore year)
        if year:
            print(f"No match for {clean_title} in {year}. Trying broader search...")
            url = f"https://api.themoviedb.org/3/search/movie?query={urllib.parse.quote(clean_title)}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {TMDB_TOKEN}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            
            results = data.get("results", [])
            if results:
                movie = results[0]
                meta = {
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path"),
                    "release_date": movie.get("release_date"),
                }
                METADATA_DIR.mkdir(parents=True, exist_ok=True)
                with open(meta_file, "w") as f:
                    json.dump(meta, f)
                if meta["poster_path"]:
                    poster_url = f"https://image.tmdb.org/t/p/w500{meta['poster_path']}"
                    poster_path = METADATA_DIR / f"{safe_title}.jpg"
                    with urllib.request.urlopen(poster_url, timeout=10) as p_resp:
                        with open(poster_path, "wb") as p_file:
                            p_file.write(p_resp.read())
                    meta["poster_path"] = f"/public/metadata/{safe_title}.jpg"
                print(f"DEBUG: Set local path {meta['poster_path']} for {title}")
                return meta

        print(f"Movie not found for {clean_title}")
        # Negative cache: save a marker so we don't ask TMDB again
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(meta_file, "w") as f:
            json.dump({"not_found": True}, f)
        return None
    except Exception as e:
        print(f"Error fetching TMDB metadata for {clean_title}: {e}")
        return None


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

    def do_GET(self):
        # Serve files from public folder first
        if self.path.startswith("/public/"):
            rel_path = self.path.replace("/public/", "", 1)
            full_path = Path(__file__).resolve().parent / "public" / rel_path
            if full_path.exists() and full_path.is_file():
                self.send_response(200)
                # Use simple mime type detection
                content_type = "image/jpeg" if full_path.suffix.lower() == ".jpg" else "application/octet-stream"
                self.send_header("Content-type", content_type)
                self.end_headers()
                with open(full_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        if self.path.startswith("/api/metadata"):
            # /api/metadata?title=...&year=...
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            title = params.get("title", [None])[0]
            year = params.get("year", [None])[0]
            if not title:
                return self.send_json(400, {"error": "title required"})
            meta = get_tmdb_metadata(title, year)
            return self.send_json(200, meta or {"error": "not found"})
        
        super().do_GET()

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
    print(f"Metadata directory: {METADATA_DIR.absolute()}")
    print(f"Serving {STATIC_DIR} on http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
