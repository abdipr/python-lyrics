import re
import sys
import time
import argparse
import json

try:
    import requests  # type: ignore
    def url_get(url):
        return requests.get(url, timeout=10).text
except ImportError:
    from urllib import request as _request
    def url_get(url):
        with _request.urlopen(url) as r:
            return r.read().decode('utf-8')

ANSI_CLEAR = "\x1b[2J\x1b[H"
ANSI_BOLD = "\x1b[1m"
ANSI_DIM = "\x1b[2m"
ANSI_RESET = "\x1b[0m"
ANSI_CYAN = "\x1b[36m"
ANSI_BLINK = "\x1b[5m"
ANSI_HIDE_CURSOR = "\x1b[?25l"
ANSI_SHOW_CURSOR = "\x1b[?25h"

TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)")

def parse_synced(raw):
    lines = raw.strip().splitlines()
    out = []
    for ln in lines:
        m = TIMESTAMP_RE.match(ln)
        if m:
            mm, ss = int(m.group(1)), int(m.group(2))
            frac = m.group(3)
            ms = int(frac.ljust(3, "0")) / 1000 if frac else 0.0
            out.append((mm * 60 + ss + ms, m.group(4)))
    return sorted(out, key=lambda x: x[0])

def fetch_first_result(track, artist=None):
    q = track.replace(" ", "+")
    url = f"https://lrclib.net/api/search?track_name={q}"
    if artist:
        url += f"&artist_name={artist.replace(' ', '+')}"
    txt = url_get(url)
    data = json.loads(txt)
    if not data:
        raise RuntimeError("No result found.")
    for item in data:
        synced = item.get("syncedLyrics") or item.get("synced_lyrics")
        if synced and synced.strip():
            return item
    print("⚠️  No synced lyrics found. Falling back to plain lyrics.", file=sys.stderr)
    return data[0]

def secs_from_str(s):
    if ":" in s:
        mm, ss = s.split(":")
        return int(mm)*60 + float(ss)
    return float(s)

def clear():
    sys.stdout.write(ANSI_CLEAR)
    sys.stdout.flush()

def move_cursor_bottom():
    sys.stdout.write("\x1b[999B")

def type_line(line, per_char=0.05):
    sys.stdout.write(ANSI_BOLD + ANSI_CYAN)
    for ch in line:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(per_char)
    sys.stdout.write(ANSI_RESET)
    sys.stdout.flush()

def play_lyrics(lyrics, start=0.0, speed=1.0):
    clear()
    prev_lines = []
    idx = 0
    while idx < len(lyrics) and lyrics[idx][0] < start:
        idx += 1
    if idx > 0:
        prev_lines.append(lyrics[idx - 1][1])

    base_time = time.time()
    sys.stdout.write(ANSI_HIDE_CURSOR)
    try:
        for i in range(idx, len(lyrics)):
            t, line = lyrics[i]
            wait_until = (t - start) / speed

            while (time.time() - base_time) < wait_until:
                time.sleep(0.01)

            clear()
            print()
            for old in prev_lines[-3:]:
                print(ANSI_DIM + old + ANSI_RESET)
            print()

            type_line(line, per_char=0.05)
            prev_lines.append(line)

        move_cursor_bottom()
        sys.stdout.flush()
    finally:
        sys.stdout.write(ANSI_SHOW_CURSOR)
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description="Display synced lyrics from lrclib.net in console.")
    parser.add_argument("--track", required=True, help="Track name (e.g. 'ILYSB')")
    parser.add_argument("--artist", help="Artist name (optional)")
    parser.add_argument("--start", default="0", help="Start time (mm:ss or seconds)")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    args = parser.parse_args()

    start = secs_from_str(args.start)
    print("Searching...", file=sys.stderr)
    try:
        res = fetch_first_result(args.track, args.artist)
    except Exception as e:
        print("Failed to fetch:", e, file=sys.stderr)
        sys.exit(1)

    synced = res.get("syncedLyrics") or ""
    if not synced.strip():
        print("No synced lyrics found.", file=sys.stderr)
        sys.exit(1)

    lyrics = parse_synced(synced)
    print(f"{ANSI_CYAN}Now playing:{ANSI_RESET} {res.get('artistName')} — {res.get('trackName')}")
    print(f"Start offset: {start:.2f}s | Speed: x{args.speed}")
    time.sleep(0.8)
    play_lyrics(lyrics, start=start, speed=args.speed)
    print("\nDone.")

if __name__ == "__main__":
    main()