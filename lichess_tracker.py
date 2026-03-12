#!/usr/bin/env python3
"""
Lichess Classic Ratings Tracker — Multi-Spieler
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, date
import os
import sys
import time

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PLAYERS_FILE = os.path.join(SCRIPT_DIR, "spieler.txt")
PUBLIC_DIR   = os.path.join(SCRIPT_DIR, "docs")
OUTPUT_FILE  = os.path.join(PUBLIC_DIR, "index.html")
CACHE_FILE   = os.path.join(SCRIPT_DIR, "werte.json")

# Diese Spieler: 100% weiss + 100% gelb fuer Aenderungen
HIGHLIGHT_PLAYERS = {"tric-k_17", "pion-panique", "panic-pawn"}

def load_players():
    if not os.path.exists(PLAYERS_FILE):
        print(f"FEHLER: {PLAYERS_FILE} nicht gefunden!", file=sys.stderr)
        sys.exit(1)
    players = []
    with open(PLAYERS_FILE, encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name and not name.startswith("#"):
                players.append(name)
    return players

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)

def is_online():
    try:
        urllib.request.urlopen("https://lichess.org", timeout=5)
        return True
    except:
        return False

def fetch_user_info(username):
    url = f"https://lichess.org/api/user/{username}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def fetch_todays_classic_games(username):
    url = (
        f"https://lichess.org/api/games/user/{username}"
        f"?max=100&moves=false&evals=false&opening=false"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/x-ndjson"})
    games = []
    with urllib.request.urlopen(req, timeout=20) as resp:
        for line in resp:
            line = line.strip()
            if line:
                game = json.loads(line.decode())
                ts = game.get("lastMoveAt", game.get("createdAt", 0)) / 1000
                is_today = datetime.fromtimestamp(ts).date() == date.today()
                is_classical = game.get("perf") == "classical"
                if is_today and is_classical:
                    games.append(game)
    return games

def calculate_daily_diff(games, username):
    username_lower = username.lower()
    total_diff = 0
    for g in games:
        players = g.get("players", {})
        white = players.get("white", {})
        black = players.get("black", {})
        if white.get("user", {}).get("id", "").lower() == username_lower:
            total_diff += white.get("ratingDiff", 0) or 0
        elif black.get("user", {}).get("id", "").lower() == username_lower:
            total_diff += black.get("ratingDiff", 0) or 0
    return total_diff

def fetch_player_data(username):
    try:
        user_info = fetch_user_info(username)
        classical = user_info.get("perfs", {}).get("classical", {})
        rating = classical.get("rating", 0)
        provisional = classical.get("prov", False)
    except Exception as e:
        print(f"  Fehler bei {username}: {e}", file=sys.stderr)
        return {"name": username, "rating": 0, "diff": 0, "error": True}
    try:
        games_today = fetch_todays_classic_games(username)
        diff = calculate_daily_diff(games_today, username)
    except Exception as e:
        print(f"  Tagesspiele nicht abrufbar fuer {username}: {e}", file=sys.stderr)
        diff = 0
    return {"name": username, "rating": rating, "provisional": provisional, "diff": diff, "error": False}

def generate_html(players_data):
    months = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]
    import zoneinfo
    now = datetime.now(zoneinfo.ZoneInfo("Europe/Berlin"))
    now_str = f"{now.day}. {months[now.month-1]} {now.hour}:{now.minute:02d} Uhr"

    rows = ""
    prev_hundred = None
    row_num = 0
    for p in players_data:
        if p["error"]:
            continue
        diff = p["diff"]
        diff_sign = "+" if diff >= 0 else ""
        is_highlight = p["name"].lower() in {h.lower() for h in HIGHLIGHT_PLAYERS}

        # Gelb wenn in letzten 7 Tagen gespielt
        from datetime import timedelta
        cache = load_cache()
        key = p["name"].lower()
        played_recently = False
        if key in cache:
            entry = cache[key]
            last_played = entry["last_played"] if isinstance(entry, dict) else None
            if last_played:
                days_ago = (date.today() - date.fromisoformat(last_played)).days
                played_recently = days_ago < 7

        if played_recently:
            text_color = "#ffd700" if is_highlight else "#a68900"
        else:
            text_color = "#ffffff" if is_highlight else "#a6a6a6"

        # Differenz: grün / rot / neutral
        if diff > 0:
            diff_color = "#5fdd8a" if is_highlight else "#3dbd6a"
        elif diff < 0:
            diff_color = "#ff6b6b" if is_highlight else "#cc4444"
        else:
            diff_color = text_color

        diff_str = f"{diff_sign}{diff}" if diff != 0 else ""

        current_hundred = p["rating"] // 100
        if prev_hundred is not None and current_hundred < prev_hundred:
            rows += '      <tr><td colspan="4" style="border-top:1px solid #333333;padding:3px 0 0 0;"></td></tr>\n'
        prev_hundred = current_hundred
        row_num += 1

        rows += (
            f"      <tr>\n"
            f"        <td style=\"color:#555555;text-align:right;padding-right:2rem\">{row_num}</td>\n"
            f"        <td style=\"color:{text_color}\"><a href='https://lichess.org/@/{p['name']}/all' target='_blank' style='color:inherit;text-decoration:none;cursor:pointer;'>{p['name']}</a></td>\n"
            f"        <td style=\"color:{diff_color};text-align:right\">{diff_str}</td>\n"
            f"        <td style=\"color:{'#a68900' if p.get('provisional') and played_recently else '#a6a6a6' if p.get('provisional') else text_color};text-align:right\">{'(' + str(p['rating']) + ')' if p.get('provisional') else p['rating']}</td>\n"
            f"      </tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>lichess classic ratings</title>
<meta http-equiv="refresh" content="300">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1a1a1a;
    font-family: Arial, sans-serif;
    font-weight: normal;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 4rem 0;
  }}
  .wrapper {{
    display: inline-block;
    text-align: left;
  }}
  h1 {{
    font-size: 16px;
    font-weight: normal;
    color: #dddddd;
    margin-bottom: 2rem;
  }}
  .pawn {{
    color: #ffffff;
    margin-right: 0.4em;
  }}
  table {{
    border-collapse: collapse;
  }}
  td {{
    padding: 0.1rem 2.5rem 0.1rem 0;
    font-size: 23px;
    font-weight: normal;
  }}
  .updated {{
    margin-top: 1rem;
    font-size: 11px;
    color: #dddddd;
  }}
  @media (max-width: 600px) {{
    body {{
      align-items: center;
      justify-content: center;
      padding: 2rem 0;
    }}
    .wrapper {{
      transform: scale(0.8);
      transform-origin: top center;
    }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <h1><span class="pawn">&#9823;</span>lichess classic ratings</h1>
  <table>
    <tbody>
{rows}    </tbody>
  </table>
  <br>
  <div class="updated">{now_str}</div>
</div>
</body>
</html>"""
    return html

def main():
    if not is_online():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Kein Internet — Script wird beendet.")
        sys.exit(0)

    PLAYERS = load_players()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starte Lichess-Abruf fuer {len(PLAYERS)} Spieler ...")
    players_data = []
    for username in PLAYERS:
        print(f"  -> {username} ...", end=" ", flush=True)
        data = fetch_player_data(username)
        players_data.append(data)
        print(f"Rating: {data['rating']}, Heute: {'+' if data['diff']>=0 else ''}{data['diff']}")
        time.sleep(3)

    # Cache laden und Werte mergen
    cache = load_cache()
    today_str = date.today().isoformat()
    for p in players_data:
        if not p["error"]:
            key = p["name"].lower()
            if p["diff"] != 0:
                cache[key] = {"diff": p["diff"], "last_played": today_str}
            elif key in cache:
                p["diff"] = cache[key]["diff"] if isinstance(cache[key], dict) else cache[key]
    save_cache(cache)

    players_data.sort(key=lambda p: p["rating"], reverse=True)

    os.makedirs(PUBLIC_DIR, exist_ok=True)
    html = generate_html(players_data)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  HTML gespeichert: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
