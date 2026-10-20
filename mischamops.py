#!/usr/bin/env python3
"""Find vinyl records from a Spotify playlist on medimops.de.

1. Fetch the playlist via the Spotify Web API and collapse tracks into albums.
2. Build an index of all vinyl products from medimops' public product sitemaps
   (search and product pages sit behind a bot challenge; sitemaps do not and
   are allowed by robots.txt).
3. Match albums against the index and write a Markdown report that marks
   offers which are new since the previous run.

Only the standard library is used. Configuration comes from the environment
or a .env file next to this script (see .env.example and README.md).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import difflib
import gzip
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

SITEMAP_INDEX = "https://www.medimops.de/sitemap_index_deu.xml"
USER_AGENT = "mischamops/0.1 (personal weekly vinyl report)"
SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

# Product URL: https://www.medimops.de/<artist>-<title>-<format...>-M<id>.html
PRODUCT_RE = re.compile(r"https://www\.medimops\.de/([a-z0-9-]+)-(M[0-9A-Z]+)\.html")
# Everything from the first format marker on is not part of artist/title.
FORMAT_RE = re.compile(r"-(vinyl|lp-record|single-vinyl|maxi-vinyl)(-|$)")
# Words that differ between Spotify and medimops editions without changing the record.
NOISE_RE = re.compile(
    r"\b(remaster(ed)?|deluxe|edition|expanded|anniversary|version|limited|"
    r"special|bonus|tracks?|reissue|mono|stereo|lp|vinyl|\d{4})\b"
)

MATCH_THRESHOLD = 0.85


# --------------------------------------------------------------------------- utils


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env support: KEY=value lines; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def http_get(url: str, headers: dict[str, str] | None = None, retries: int = 3) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", **(headers or {})}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def slugify(text: str, german: bool = True) -> str:
    """Approximate medimops' URL slugs: ascii, lowercase, dash-separated."""
    text = text.replace("&", " and ")
    if german:
        text = text.translate(UMLAUTS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def slug_variants(text: str) -> set[str]:
    """medimops mostly writes umlauts as ae/oe/ue, but sometimes just drops the dots."""
    return {slugify(text), slugify(text, german=False)}


def clean_title(slug: str) -> str:
    words = NOISE_RE.sub(" ", slug.replace("-", " "))
    return " ".join(words.split())


def similarity(title: str, target: str) -> float:
    if title == target:
        return 1.0
    # medimops titles often carry extras: "wish you were here inkl mp3 download"
    if len(target) >= 6 and title.startswith(target + " "):
        return 0.9
    return difflib.SequenceMatcher(None, title, target).ratio()


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------------- spotify


SPOTIFY_TOKEN_FILE = DATA / "spotify_token.json"
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def spotify_client() -> tuple[str, str]:
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET fehlen – bitte in .env eintragen (siehe README).")
    return cid, secret


def spotify_token_request(form: dict[str, str]) -> dict:
    cid, secret = spotify_client()
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(form).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def spotify_login() -> None:
    """One-time browser login. Since 2026 playlist contents require a user token."""
    import http.server
    import secrets
    import webbrowser

    cid, _ = spotify_client()
    state = secrets.token_urlsafe(16)
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {"client_id": cid, "response_type": "code", "redirect_uri": REDIRECT_URI, "state": state}
    )
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if query.get("state") == state:
                result.update(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Login abgeschlossen – du kannst dieses Fenster schließen.".encode())

        def log_message(self, *args):
            pass

    parsed = urllib.parse.urlparse(REDIRECT_URI)
    server = http.server.HTTPServer((parsed.hostname, parsed.port), Handler)
    print(f"Öffne im Browser (falls nicht automatisch):\n{auth_url}", file=sys.stderr)
    webbrowser.open(auth_url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()
    if "error" in result:
        sys.exit(f"Spotify-Login fehlgeschlagen: {result['error']}")

    tokens = spotify_token_request(
        {"grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT_URI}
    )
    save_json(SPOTIFY_TOKEN_FILE, {"refresh_token": tokens["refresh_token"]})
    print(f"Login gespeichert in {SPOTIFY_TOKEN_FILE}", file=sys.stderr)


def spotify_token() -> str:
    stored = load_json(SPOTIFY_TOKEN_FILE, {})
    if not stored.get("refresh_token"):
        sys.exit("Kein Spotify-Login vorhanden. Einmalig ausführen: python3 mischamops.py --login")
    tokens = spotify_token_request({"grant_type": "refresh_token", "refresh_token": stored["refresh_token"]})
    if tokens.get("refresh_token"):  # Spotify may rotate it
        save_json(SPOTIFY_TOKEN_FILE, {"refresh_token": tokens["refresh_token"]})
    return tokens["access_token"]


def fetch_playlist_albums(playlist_id: str) -> list[dict]:
    token = spotify_token()
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/items?limit=100"
    albums: dict[str, dict] = {}
    tracks = 0
    while url:
        try:
            page = json.loads(http_get(url, {"Authorization": f"Bearer {token}"}))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                sys.exit(
                    "Spotify verweigert den Zugriff auf die Playlist (403). Seit Februar 2026 liefert "
                    "Spotify die Songs nur für Playlists, die dem eingeloggten Account gehören. "
                    "Siehe README → Fehlerbehebung."
                )
            raise
        for item in page["items"]:
            track = item.get("item") or item.get("track") or {}
            album = track.get("album")
            if not album or not album.get("id"):
                continue  # local files, removed tracks
            tracks += 1
            entry = albums.setdefault(
                album["id"],
                {
                    "id": album["id"],
                    "name": album["name"],
                    "artists": [a["name"] for a in album["artists"]],
                    "type": album["album_type"],
                    "year": (album.get("release_date") or "")[:4],
                    "url": album["external_urls"].get("spotify", ""),
                    "tracks": 0,
                },
            )
            entry["tracks"] += 1
        url = page.get("next")
    print(f"Spotify: {tracks} Tracks → {len(albums)} Alben", file=sys.stderr)
    return list(albums.values())


# ------------------------------------------------------------------------ medimops


def sitemap_locs(xml: bytes) -> list[str]:
    return [el.text.strip() for el in ET.fromstring(xml).iter(f"{SM_NS}loc") if el.text]


def vinyl_from_sitemap(url: str) -> list[dict]:
    out = []
    for loc in sitemap_locs(http_get(url)):
        m = PRODUCT_RE.fullmatch(loc)
        if not m:
            continue
        slug, pid = m.groups()
        fm = FORMAT_RE.search(slug)
        # "...-vinyl-audio-cd" and "cd-in-vinyl-optik" are CDs styled like records
        if not fm or slug.endswith("audio-cd") or "cd-in-vinyl-optik" in slug:
            continue
        out.append({"id": pid, "url": loc, "name": slug[: fm.start()], "format": slug[fm.start() + 1 :]})
    return out


def build_vinyl_index(workers: int = 4) -> list[dict]:
    sitemaps = [u for u in sitemap_locs(http_get(SITEMAP_INDEX)) if "sitemap_product_" in u]
    print(f"medimops: lade {len(sitemaps)} Produkt-Sitemaps …", file=sys.stderr)
    items: dict[str, dict] = {}
    with ThreadPoolExecutor(workers) as pool:
        for i, batch in enumerate(pool.map(vinyl_from_sitemap, sitemaps), 1):
            for it in batch:
                items[it["id"]] = it
            if i % 20 == 0:
                print(f"  {i}/{len(sitemaps)} Sitemaps, {len(items)} Vinyl-Artikel", file=sys.stderr)
    print(f"medimops: {len(items)} Vinyl-Artikel im Index", file=sys.stderr)
    return list(items.values())


# ------------------------------------------------------------------------ matching


def artist_keys(name: str) -> set[str]:
    keys = slug_variants(name)
    keys |= {k[4:] for k in keys if k.startswith("the-")}
    return {k for k in keys if k}


def match(albums: list[dict], vinyl: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Return (album matches, other vinyl per playlist artist)."""
    by_first_word: dict[str, list[dict]] = defaultdict(list)
    for v in vinyl:
        by_first_word[v["name"].split("-", 1)[0]].append(v)

    hits: list[dict] = []
    matched_ids: set[str] = set()
    artist_items: dict[str, dict[str, dict]] = defaultdict(dict)

    for album in albums:
        targets = {clean_title(t) for t in slug_variants(album["name"])} - {""}
        for artist in album["artists"]:
            for key in artist_keys(artist):
                for v in by_first_word.get(key.split("-", 1)[0], []):
                    if not (v["name"] == key or v["name"].startswith(key + "-")):
                        continue
                    artist_items[artist][v["id"]] = v
                    title = clean_title(v["name"][len(key) + 1 :])
                    if not targets or not title:
                        continue
                    score = max(similarity(title, t) for t in targets)
                    if score >= MATCH_THRESHOLD and v["id"] not in matched_ids:
                        matched_ids.add(v["id"])
                        hits.append({"album": album, "offer": v, "score": round(score, 2)})

    others = {
        artist: sorted((v for v in items.values() if v["id"] not in matched_ids), key=lambda v: v["name"])
        for artist, items in artist_items.items()
    }
    return hits, {a: vs for a, vs in others.items() if vs}


# -------------------------------------------------------------------------- report


def pretty(slug: str) -> str:
    return slug.replace("-", " ").title()


def write_report(hits: list[dict], others: dict[str, list[dict]], seen: set[str], n_albums: int) -> Path:
    today = dt.date.today().isoformat()
    new_hits = [h for h in hits if h["offer"]["id"] not in seen]
    lines = [
        f"# medimops Vinyl-Report {today}",
        "",
        f"{n_albums} Alben aus der Playlist geprüft · **{len(hits)} Treffer**, davon **{len(new_hits)} neu** seit dem letzten Lauf.",
        "",
        "Preise und Zustand stehen nur auf der Produktseite (Link öffnen).",
        "",
        "## Treffer",
        "",
        "| | Künstler | Album | medimops-Artikel | Format |",
        "|---|---|---|---|---|",
    ]
    for h in sorted(hits, key=lambda h: (h["offer"]["id"] in seen, h["album"]["artists"][0].lower())):
        a, o = h["album"], h["offer"]
        flag = "🆕" if o["id"] not in seen else ""
        unsure = " (?)" if h["score"] < 0.95 else ""
        lines.append(
            f"| {flag} | {', '.join(a['artists'])} | [{a['name']}]({a['url']}) | "
            f"[{pretty(o['name'])}]({o['url']}){unsure} | {o['format']} |"
        )
    if others:
        lines += ["", "## Weitere Vinyl von Künstlern aus der Playlist", ""]
        for artist in sorted(others, key=str.lower):
            items = others[artist]
            links = ", ".join(
                f"[{pretty(v['name'])}]({v['url']}){' 🆕' if v['id'] not in seen else ''}" for v in items
            )
            lines.append(f"- **{artist}** ({len(items)}): {links}")
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"{today}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------- main


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--playlist", help="Spotify-Playlist-URL oder -ID (Standard: SPOTIFY_PLAYLIST aus .env)")
    p.add_argument("--login", action="store_true", help="einmaliger Spotify-Login im Browser")
    p.add_argument("--cached-index", action="store_true", help="medimops-Index nicht neu laden")
    p.add_argument("--cached-playlist", action="store_true", help="Playlist nicht neu laden")
    load_dotenv()
    args = p.parse_args()

    if args.login:
        spotify_login()
        return

    playlist = args.playlist or os.environ.get("SPOTIFY_PLAYLIST")
    if not playlist and not args.cached_playlist:
        sys.exit("Keine Playlist angegeben – SPOTIFY_PLAYLIST in .env setzen oder --playlist verwenden.")
    playlist_id = re.sub(r".*playlist/([A-Za-z0-9]+).*", r"\1", playlist or "")

    albums_path, index_path, seen_path = DATA / "albums.json", DATA / "vinyl_index.json", DATA / "seen.json"

    if args.cached_playlist and albums_path.exists():
        albums = load_json(albums_path, [])
    else:
        albums = fetch_playlist_albums(playlist_id)
        save_json(albums_path, albums)

    if args.cached_index and index_path.exists():
        vinyl = load_json(index_path, [])
    else:
        vinyl = build_vinyl_index()
        save_json(index_path, vinyl)

    hits, others = match(albums, vinyl)
    seen = set(load_json(seen_path, []))
    report = write_report(hits, others, seen, len(albums))

    current = {h["offer"]["id"] for h in hits} | {v["id"] for vs in others.values() for v in vs}
    save_json(seen_path, sorted(current))
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
