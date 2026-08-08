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
STABIL_FILE  = os.path.join(PUBLIC_DIR, "stabil.html")
NOBOTS_FILE  = os.path.join(PUBLIC_DIR, "nobots.html")
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

def fetch_color_stats(cache):
    cs = cache.get("_color_stats", {})
    since = cs.get("since_ms", SINCE_2026)

    total_white   = cs.get("total_white", 0)
    total_black   = cs.get("total_black", 0)
    total_wins    = cs.get("total_wins", 0)
    total_draws   = cs.get("total_draws", 0)
    total_losses  = cs.get("total_losses", 0)
    white_wins    = cs.get("white_wins", 0)
    black_wins    = cs.get("black_wins", 0)
    total_seconds = cs.get("total_seconds", 0)

    max_created = since
    new_games_found = 0

    for username in COLOR_STATS_PLAYERS:
        url = (
            f"https://lichess.org/api/games/user/{username}"
            f"?since={since}&moves=false&evals=false&opening=false"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/x-ndjson"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    game = json.loads(line.decode())
                    created = game.get("createdAt", 0)
                    # Bereits verarbeitete Partien überspringen (since ist inklusiv)
                    if created <= since:
                        continue
                    new_games_found += 1
                    if created > max_created:
                        max_created = created
                    players = game.get("players", {})
                    white_id = players.get("white", {}).get("user", {}).get("id", "").lower()
                    is_white = white_id == username.lower()
                    if is_white:
                        total_white += 1
                    else:
                        total_black += 1
                    winner = game.get("winner")
                    if winner == "white":
                        if is_white:
                            total_wins += 1
                            white_wins += 1
                        else:
                            total_losses += 1
                    elif winner == "black":
                        if not is_white:
                            total_wins += 1
                            black_wins += 1
                        else:
                            total_losses += 1
                    else:
                        total_draws += 1
                    last_move = game.get("lastMoveAt", 0)
                    if created and last_move:
                        total_seconds += (last_move - created) / 1000
        except Exception as e:
            print(f"  Farbstatistik-Fehler bei {username}: {e}", file=sys.stderr)
        time.sleep(2)

    print(f"  Farbstatistik: {new_games_found} neue Partie(n) seit letztem Run.")

    cache["_color_stats"] = {
        "since_ms": max_created + 1 if new_games_found else since,
        "total_white": total_white,
        "total_black": total_black,
        "total_wins": total_wins,
        "total_draws": total_draws,
        "total_losses": total_losses,
        "white_wins": white_wins,
        "black_wins": black_wins,
        "total_seconds": total_seconds,
    }

    days    = int(total_seconds // 86400)
    hours   = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    white_pct = round(white_wins / total_white * 100) if total_white else 0
    black_pct = round(black_wins / total_black * 100) if total_black else 0
    return total_white, total_black, days, hours, minutes, total_wins, total_draws, total_losses, white_pct, black_pct

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
    import zoneinfo
    berlin = zoneinfo.ZoneInfo("Europe/Berlin")
    today_berlin = datetime.now(berlin).date()

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
                is_today = datetime.fromtimestamp(ts, tz=berlin).date() == today_berlin
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

def generate_html(players_data, color_stats=None, page_variant="alle", cache=None):
    if cache is None:
        cache = {}
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
        key = p["name"].lower()
        played_recently = False
        if key in cache:
            entry = cache[key]
            last_played = entry["last_played"] if isinstance(entry, dict) else None
            if last_played:
                import zoneinfo as _zi
                today_berlin_date = datetime.now(_zi.ZoneInfo("Europe/Berlin")).date()
                days_ago = (today_berlin_date - date.fromisoformat(last_played)).days
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
            h2h_str = f"&nbsp;&nbsp;<span style='color:{h2h_color};font-size:0.78em;'>{h2h[0]}-{h2h[1]}</span>"
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
                rd_str = f"&nbsp;<span style='color:#555555;font-size:0.78em;font-weight:normal;font-style:normal;'>{warn}{rd_rounded}</span>"

        prog = p.get("prog", 0)
        if prog > 0:
            prog_symbol = "&#9650;"
            sym_class = "sym-tri"
            sym_color = "#287b45"
        elif prog < 0:
            prog_symbol = "&#9660;"
            sym_class = "sym-tri"
            sym_color = "#852c2c"
        else:
            prog_symbol = "&#9679;"
            sym_class = "sym-dot"
            sym_color = "#464646"
        arrow_html = f"<span class='{sym_class}' style='color:{sym_color};font-style:normal;font-weight:normal;display:inline-block;'>{prog_symbol}</span>&nbsp;"

        player_key = p["name"].lower()

        rows += (
            f"      <tr>\n"
            f"        <td class=\"rownum\" style=\"color:#555555;text-align:right;white-space:nowrap;\">{row_num}</td>\n"
            f"        <td style=\"color:{text_color};white-space:nowrap;\"><a href='https://lichess.org/@/{p['name']}/all' target='_blank' style='color:inherit;text-decoration:none;cursor:pointer;{name_style}'>{display_name}</a>{rd_str}{h2h_str}</td>\n"
            f"        <td style=\"color:{diff_color};text-align:right;{rating_style}white-space:nowrap;\">{diff_str}</td>\n"
            f"        <td style=\"color:{rating_color};{rating_style}white-space:nowrap;padding-top:0;padding-bottom:0;overflow:visible;\">"
            f"<span style='display:flex;align-items:baseline;width:100%;'>"
            f"<span style='flex:1;text-align:center;font-variant-numeric:tabular-nums;'>{arrow_html}{p['rating']}</span>"
            f"<span class='poschg pcbox' data-name='{player_key}' style='text-align:right;flex-shrink:0;'></span>"
            f"</span></td>\n"
            f"      </tr>\n"
        )

    color_html = ""
    if color_stats:
        w, b, days, hours, minutes, wins, draws, losses, white_pct, black_pct = color_stats
        total = w + b
        color_html = f"""  <div style="margin-top:2em;font-size:17px;color:#555555;text-align:center;line-height:1.6;">{total} Partien<br>weiss <span style="color:#a6a6a6;">{w}</span> <span style="color:#555555;font-size:0.85em;">({white_pct}%)</span> – schwarz <span style="color:#a6a6a6;">{b}</span> <span style="color:#555555;font-size:0.85em;">({black_pct}%)</span><br>gewonnen {wins} – remis {draws} – verloren {losses}<br>Gesamtspielzeit<br>{days} Tage&nbsp;&nbsp;{hours} Std.&nbsp;&nbsp;{minutes} Min.</div>
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
    width: 700px;
  }}
  h1 {{
    font-size: 19px;
    font-weight: normal;
    color: #dddddd;
    margin-bottom: 0;
    white-space: nowrap;
  }}
  @media (min-width: 601px) {{
    .wrapper {{
      padding-left: 1em;
      padding-right: 1em;
    }}
  }}
  table {{
    border-collapse: collapse;
    table-layout: fixed;
    width: 100%;
  }}
  td {{
    padding: 0.1rem 1rem 0.1rem 0;
    font-size: 23px;
    font-weight: normal;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .rownum {{
    padding-right: 1.1rem;
  }}
  .sym-tri {{
    font-size: 20px;
    vertical-align: -1px;
  }}
  .sym-dot {{
    font-size: 19px;
    vertical-align: 1px;
  }}
  .pcbox {{
    width: 2.4em;
    overflow: visible;
  }}
  .pcval {{
    color: #6b6b6b;
    font-size: 0.78em;
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
      width: calc(100vw - 1rem);
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
      padding-right: 0.9rem !important;
    }}
    .sym-tri {{
      font-size: 17px;
    }}
    .sym-dot {{
      font-size: 13.6px;
    }}
    .pcbox {{
      width: 0.9em;
    }}
    .pcval {{
      font-size: 0.5em;
    }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2rem;width:100%;gap:1rem;">
    <h1><a href="https://github.com/akabeka-git/lichess_ratings_online/actions/workflows/update.yml" target="_blank" style="color:inherit;text-decoration:none;"><span style="color:#ffffff;margin-right:0.4em;">&#9823;</span>lichess classic ratings</a></h1>
    <div style="text-align:right;">
      <div class="updated">{now_str}</div>
      <div style="font-size:12px;margin-top:2px;">
        <a href="index.html" style="color:{'#dddddd' if page_variant=='alle' else '#555555'};text-decoration:none;">alle</a>
        <span style="color:#555555;"> · </span>
        <a href="stabil.html" style="color:{'#dddddd' if page_variant=='stabil' else '#555555'};text-decoration:none;">stabil</a>
        <span style="color:#555555;"> · </span>
        <a href="nobots.html" style="color:{'#dddddd' if page_variant=='nobots' else '#555555'};text-decoration:none;">nobots</a>
      </div>
    </div>
  </div>
  <table>
    <colgroup>
      <col style="width:8%">
      <col style="width:52%">
      <col style="width:15%">
      <col style="width:25%">
    </colgroup>
    <tbody>
{rows}    </tbody>
  </table>
{color_html}</div>
<script>
(function() {{
  var storageKey = "lichess_pos_{page_variant}";
  var highlightPlayers = {sorted([h.lower() for h in HIGHLIGHT_PLAYERS])};
  var threeDaysMs = 3 * 24 * 60 * 60 * 1000;
  var now = Date.now();
  var spans = document.querySelectorAll('.poschg');
  var currentPositions = {{}};
  spans.forEach(function(el, idx) {{
    currentPositions[el.dataset.name] = idx + 1;
  }});
  var storedRaw = null;
  try {{ storedRaw = localStorage.getItem(storageKey); }} catch (e) {{}}
  var stored = storedRaw ? JSON.parse(storedRaw) : {{}};
  var isFirstRun = Object.keys(stored).length === 0;
  var updated = {{}};
  spans.forEach(function(el) {{
    var name = el.dataset.name;
    var newPos = currentPositions[name];
    var raw = stored[name];
    // Migration: altes Format war eine reine Zahl statt {{pos, delta}}
    var entry = (raw && typeof raw === "object" && "pos" in raw) ? raw : null;
    if (entry && (typeof entry.pos !== "number" || isNaN(entry.pos) || entry.delta === "NaN")) {{
      entry = null; // kaputter Wert aus fehlerhaftem Zwischenstand -> verwerfen
    }}
    var oldFlatPos = (typeof raw === "number") ? raw : null;
    var displayDelta;
    if (isFirstRun) {{
      // Allererster Aufruf: Basiswert nur still anlegen, nichts anzeigen
      displayDelta = null;
      updated[name] = {{ pos: newPos, delta: "", ts: now }};
    }} else if (!entry && oldFlatPos === null) {{
      // Echter Neuzugang in der Liste
      displayDelta = "neu";
      updated[name] = {{ pos: newPos, delta: "neu", ts: now }};
    }} else if (!entry && oldFlatPos !== null) {{
      // Migration von altem Format: einmalig vergleichen, dann neues Format anlegen
      if (oldFlatPos !== newPos) {{
        var mdelta = oldFlatPos - newPos;
        displayDelta = mdelta > 0 ? ("+" + mdelta) : String(mdelta);
      }} else {{
        displayDelta = null;
      }}
      updated[name] = {{ pos: newPos, delta: displayDelta || "", ts: now }};
    }} else if (entry.pos !== newPos) {{
      // Position hat sich seit dem letzten Mal veraendert -> neuer Wert
      var delta = entry.pos - newPos;
      displayDelta = delta > 0 ? ("+" + delta) : String(delta);
      updated[name] = {{ pos: newPos, delta: displayDelta, ts: now }};
    }} else {{
      // Keine Veraenderung -> pruefen ob abgelaufen (ausser highlight-spieler)
      var entryTs = entry.ts || now;
      var isHighlight = highlightPlayers.indexOf(name) !== -1;
      if (!isHighlight && (now - entryTs) > threeDaysMs) {{
        displayDelta = null;
        updated[name] = {{ pos: newPos, delta: "", ts: entryTs }};
      }} else {{
        displayDelta = entry.delta;
        updated[name] = {{ pos: newPos, delta: entry.delta, ts: entryTs }};
      }}
    }}
    if (displayDelta) {{
      var color = "#6b6b6b";
      if (displayDelta.charAt(0) === "+") {{ color = "#3dbd6a"; }}
      else if (displayDelta.charAt(0) === "-") {{ color = "#cc4444"; }}
      el.innerHTML = "<span class='pcval' style='color:" + color + ";'>" + displayDelta + "</span>";
    }}
  }});
  try {{ localStorage.setItem(storageKey, JSON.stringify(updated)); }} catch (e) {{}}
}})();
</script>
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
    import zoneinfo
    today_str = datetime.now(zoneinfo.ZoneInfo("Europe/Berlin")).date().isoformat()
    for p in players_data:
        if not p["error"]:
            key = p["name"].lower()
            if p["diff"] != 0:
                cache[key] = {"diff": p["diff"], "last_played": today_str}
            elif key in cache:
                p["diff"] = cache[key]["diff"] if isinstance(cache[key], dict) else cache[key]

    players_data.sort(key=lambda p: p["rating"], reverse=True)

    print("  Rufe Farbstatistiken ab ...")
    color_stats = fetch_color_stats(cache)
    save_cache(cache)

    os.makedirs(PUBLIC_DIR, exist_ok=True)

    html_alle = generate_html(players_data, color_stats, page_variant="alle", cache=cache)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_alle)
    print(f"\n  HTML gespeichert: {OUTPUT_FILE}")

    stable_players = [p for p in players_data if p["error"] or not p.get("provisional")]
    html_stabil = generate_html(stable_players, color_stats, page_variant="stabil", cache=cache)
    with open(STABIL_FILE, "w", encoding="utf-8") as f:
        f.write(html_stabil)
    print(f"  HTML gespeichert: {STABIL_FILE}")

    nobots_players = [p for p in stable_players if p["error"] or not p["name"].lower().startswith("maia")]
    html_nobots = generate_html(nobots_players, color_stats, page_variant="nobots", cache=cache)
    with open(NOBOTS_FILE, "w", encoding="utf-8") as f:
        f.write(html_nobots)
    print(f"  HTML gespeichert: {NOBOTS_FILE}")


if __name__ == "__main__":
    main()
