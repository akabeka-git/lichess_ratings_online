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
HIGHLIGHT_PLAYERS = {"tric-k_17", "pion-panique", "panic-pawn", "botfather-slay"}

def load_players():
    seen = set()
    players = []
    for account in HIGHLIGHT_PLAYERS:
        if account.lower() not in seen:
            seen.add(account.lower())
            players.append(account)

    token_map = {
        "tric-k_17":      os.environ.get("LICHESS_TOKEN_TRIC", ""),
        "pion-panique":   os.environ.get("LICHESS_TOKEN_PION", ""),
        "botfather-slay": os.environ.get("LICHESS_TOKEN_BOTFATHER", ""),
        "panic-pawn":     os.environ.get("LICHESS_TOKEN_PANIC", ""),
    }

    for account in HIGHLIGHT_PLAYERS:
        token = token_map.get(account, "")
        if not token:
            print(f"  Kein Token für {account} — überspringe.", file=sys.stderr)
            continue
        url = "https://lichess.org/api/rel/following"
        req = urllib.request.Request(url, headers={
            "Accept": "application/x-ndjson",
            "Authorization": f"Bearer {token}"
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    user = json.loads(line.decode())
                    name = user.get("username", "")
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        players.append(name)
            print(f"  {account}: Following geladen.")
        except Exception as e:
            print(f"  Following-Fehler bei {account}: {e}", file=sys.stderr)
        time.sleep(1)

    # Manuelle Ergänzungsliste
    if os.path.exists(PLAYERS_FILE):
        with open(PLAYERS_FILE, encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name and not name.startswith("#") and name.lower() not in seen:
                    seen.add(name.lower())
                    players.append(name)

    print(f"  {len(players)} Spieler gesamt.")
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

H2H_PLAYERS = ["pion-panique", "botfather-slay", "tric-k_17", "panic-pawn"]

COLOR_STATS_PLAYERS = ["pion-panique", "tric-k_17", "botfather-slay"]
SINCE_2026 = 1767225600000  # 2026-01-01 00:00:00 UTC in ms

def fetch_color_stats():
    total_white, total_black, total_seconds = 0, 0, 0
    total_wins, total_losses, total_draws = 0, 0, 0
    for username in COLOR_STATS_PLAYERS:
        url = (
            f"https://lichess.org/api/games/user/{username}"
            f"?since={SINCE_2026}&moves=false&evals=false&opening=false"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/x-ndjson"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    game = json.loads(line.decode())
                    players = game.get("players", {})
                    white_id = players.get("white", {}).get("user", {}).get("id", "").lower()
                    black_id = players.get("black", {}).get("user", {}).get("id", "").lower()
                    is_white = white_id == username.lower()
                    if is_white:
                        total_white += 1
                    else:
                        total_black += 1
                    winner = game.get("winner")
                    if winner == "white":
                        if is_white: total_wins += 1
                        else: total_losses += 1
                    elif winner == "black":
                        if not is_white: total_wins += 1
                        else: total_losses += 1
                    else:
                        total_draws += 1
                    created = game.get("createdAt", 0)
                    last_move = game.get("lastMoveAt", 0)
                    if created and last_move:
                        total_seconds += (last_move - created) / 1000
        except Exception as e:
            print(f"  Farbstatistik-Fehler bei {username}: {e}", file=sys.stderr)
        time.sleep(2)
    days    = int(total_seconds // 86400)
    hours   = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return total_white, total_black, days, hours, minutes, total_wins, total_draws, total_losses

def fetch_h2h_score(username):
    if username.lower() in [h.lower() for h in H2H_PLAYERS]:
        return None
    total_wins, total_losses, total_draws = 0, 0, 0
    for h2h_player in H2H_PLAYERS:
        url = (
            f"https://lichess.org/api/games/user/{h2h_player}"
            f"?vs={username}&perf=classical&moves=false&evals=false&opening=false&max=300"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/x-ndjson"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    game = json.loads(line.decode())
                    winner = game.get("winner")
                    players = game.get("players", {})
                    white_id = players.get("white", {}).get("user", {}).get("id", "").lower()
                    h2h_is_white = white_id == h2h_player.lower()
                    if winner is None:
                        total_draws += 1
                    elif winner == "white":
                        if h2h_is_white: total_wins += 1
                        else: total_losses += 1
                    elif winner == "black":
                        if not h2h_is_white: total_wins += 1
                        else: total_losses += 1
        except Exception as e:
            print(f"  H2H-Fehler bei {username} vs {h2h_player}: {e}", file=sys.stderr)
        time.sleep(2)
    if total_wins == 0 and total_losses == 0 and total_draws == 0:
        return None
    my_score = total_wins + total_draws * 0.5
    opp_score = total_losses + total_draws * 0.5
    # Format: ganzzahlig wenn .0, sonst mit .5
    def fmt(n):
        return str(int(n)) if n == int(n) else str(n)
    return (fmt(my_score), fmt(opp_score))

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
        rd = classical.get("rd", 0)
        prog = classical.get("prog", 0)
    except Exception as e:
        print(f"  Fehler bei {username}: {e}", file=sys.stderr)
        return {"name": username, "rating": 0, "diff": 0, "error": True}
    try:
        games_today = fetch_todays_classic_games(username)
        diff = calculate_daily_diff(games_today, username)
    except Exception as e:
        print(f"  Tagesspiele nicht abrufbar fuer {username}: {e}", file=sys.stderr)
        diff = 0
    h2h = fetch_h2h_score(username)
    return {"name": username, "rating": rating, "provisional": provisional, "rd": rd, "prog": prog, "diff": diff, "h2h": h2h, "error": False}

def generate_html(players_data, color_stats=None):
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
            base_color = "#a68900" if p.get("provisional") else "#ffd700"
        else:
            base_color = "#a6a6a6" if p.get("provisional") else "#ffffff"

        def dim65(hex_color):
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
            return "#{:02x}{:02x}{:02x}".format(int(r*0.65), int(g*0.65), int(b*0.65))

        text_color   = dim65(base_color) if p.get("provisional") else base_color
        rating_color = text_color

        is_italic = p["name"].lower().startswith("maia")

        name_style   = "font-weight:bold;" if is_highlight else "font-style:italic;" if is_italic else ""
        rating_style = "font-weight:bold;" if is_highlight else "font-style:italic;" if is_italic else ""

        # Differenz: grün / rot / neutral
        if diff > 0:
            raw_diff_color = "#5fdd8a" if is_highlight else "#3dbd6a"
        elif diff < 0:
            raw_diff_color = "#ff6b6b" if is_highlight else "#cc4444"
        else:
            raw_diff_color = base_color
        diff_color = dim65(raw_diff_color) if p.get("provisional") else raw_diff_color

        diff_str = f"{diff_sign}{diff}" if diff != 0 else ""

        current_hundred = p["rating"] // 100
        if prev_hundred is not None and current_hundred < prev_hundred:
            rows += '      <tr><td colspan="4" style="border-top:1px solid #666666;padding:3px 0 0 0;"></td></tr>\n'
        prev_hundred = current_hundred
        row_num += 1

        h2h = p.get("h2h")
        if h2h:
            my_s, opp_s = float(h2h[0]), float(h2h[1])
            if my_s > opp_s:
                h2h_color = "#3d7a52"
            elif my_s < opp_s:
                h2h_color = "#7a3d3d"
            else:
                h2h_color = "#555555"
            h2h_str = f"&nbsp;&nbsp;<span style='color:{h2h_color};font-size:18px;'>{h2h[0]}-{h2h[1]}</span>"
        else:
            h2h_str = ""

        display_name = "schachpinguin" if p['name'].lower() == "schachpinguin3000" else p['name']
        if is_highlight:
            display_name = f"&gt;&gt; {display_name}"

        rd_str = ""
        if is_highlight:
            rd_val = p.get("rd")
            if rd_val:
                rd_rounded = round(rd_val)
                warn = "<svg width='14' height='14' viewBox='0 0 24 24' style='vertical-align:-2px;'><path d='M12 2 L23 21 L1 21 Z' fill='#e8a33d'/><text x='12' y='19' font-size='14' font-weight='bold' fill='#1a1a1a' text-anchor='middle'>!</text></svg>&nbsp;" if 100 <= rd_rounded <= 110 else ""
                rd_str = f"&nbsp;<span style='color:#555555;font-size:18px;font-weight:normal;font-style:normal;'>{warn}{rd_rounded}</span>"

        prog = p.get("prog", 0)
        if prog > 0:
            prog_symbol = "&#9650;"
            sym_size = "20px"
        elif prog < 0:
            prog_symbol = "&#9660;"
            sym_size = "20px"
        else:
            prog_symbol = "&#9679;"
            sym_size = "16px"
        arrow_html = f"&nbsp;<span style='color:#6b6b6b;font-size:{sym_size};font-style:normal;font-weight:normal;display:inline-block;'>{prog_symbol}</span>"

        rows += (
            f"      <tr>\n"
            f"        <td class=\"rownum\" style=\"color:#555555;text-align:right;white-space:nowrap;\">{row_num}</td>\n"
            f"        <td style=\"color:{text_color};white-space:nowrap;\"><a href='https://lichess.org/@/{p['name']}/all' target='_blank' style='color:inherit;text-decoration:none;cursor:pointer;{name_style}'>{display_name}</a>{rd_str}{h2h_str}</td>\n"
            f"        <td style=\"color:{diff_color};text-align:right;{rating_style}white-space:nowrap;\">{diff_str}</td>\n"
            f"        <td style=\"color:{rating_color};text-align:right;{rating_style}white-space:nowrap;\">{'(' + str(p['rating']) + ')' if p.get('provisional') else p['rating']}{arrow_html}</td>\n"
            f"      </tr>\n"
        )

    color_html = ""
    if color_stats:
        w, b, days, hours, minutes, wins, draws, losses = color_stats
        total = w + b
        color_html = f"""  <div style="margin-top:2em;font-size:19px;color:#555555;text-align:center;line-height:1.6;">{total} Partien<br><br>weiss <span style="color:#ffffff;">{w}</span> – schwarz <span style="color:#ffffff;">{b}</span><br>gewonnen {wins} – remis {draws} – verloren {losses}<br><br>Gesamtspielzeit<br>{days} Tage&nbsp;&nbsp;{hours} Std.&nbsp;&nbsp;{minutes} Min.</div>
  <div style="margin-bottom:1.5em;"></div>
"""

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
    align-items: flex-start;
    padding: 4rem 0 1.5rem 0;
  }}
  html, body {{
    overflow-x: hidden;
    max-width: 100%;
    touch-action: pan-y;
  }}
  .wrapper {{
    display: inline-block;
    text-align: left;
    max-width: 100vw;
  }}
  h1 {{
    font-size: 19px;
    font-weight: normal;
    color: #dddddd;
    margin-bottom: 0;
    white-space: nowrap;
  }}
  table {{
    border-collapse: collapse;
  }}
  td {{
    padding: 0.1rem 2.5rem 0.1rem 0;
    font-size: 23px;
    font-weight: normal;
  }}
  .rownum {{
    padding-right: 2rem;
  }}
  .updated {{
    font-size: 16px;
    color: #dddddd;
    white-space: nowrap;
  }}
  @media (max-width: 600px) {{
    body {{
      align-items: flex-start;
      justify-content: center;
      padding: 1.2rem 0.5rem;
    }}
    .wrapper {{
      transform: none;
      max-width: calc(100vw - 1rem);
      overflow-x: hidden;
    }}
    h1 {{
      font-size: 17px;
    }}
    .updated {{
      font-size: 13px;
    }}
    td {{
      font-size: 20px;
      padding: 0.1rem 1rem 0.1rem 0;
    }}
    .rownum {{
      padding-right: 0.8rem !important;
    }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2rem;width:100%;gap:1rem;">
    <h1><span style="color:#ffffff;margin-right:0.4em;">&#9823;</span>lichess classic ratings</h1>
    <div class="updated">{now_str}</div>
  </div>
  <table>
    <tbody>
{rows}    </tbody>
  </table>
{color_html}</div>
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

    print("  Rufe Farbstatistiken ab ...")
    color_stats = fetch_color_stats()

    os.makedirs(PUBLIC_DIR, exist_ok=True)
    html = generate_html(players_data, color_stats)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  HTML gespeichert: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
