# Lichess Classic Ratings Tracker

Stündlich aktualisierte Rating-Tabelle, gehostet auf Netlify, gebaut via GitHub Actions.

---

## Repo-Struktur

```
/
├── .github/
│   └── workflows/
│       └── update.yml       ← GitHub Actions (läuft stündlich)
├── public/
│   └── index.html           ← generierte HTML (wird auto-committed)
├── lichess_tracker.py       ← Haupt-Script
├── spieler.txt              ← ein Lichess-Name pro Zeile
├── werte.json               ← persistenter Diff-Cache
├── netlify.toml             ← Netlify-Konfiguration
└── .gitignore
```

---

## Setup (einmalig)

### 1. GitHub Repo erstellen

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/DEIN-USER/DEIN-REPO.git
git push -u origin main
```

### 2. GitHub Actions Schreibrecht geben

Repo → **Settings → Actions → General → Workflow permissions**  
→ **Read and write permissions** aktivieren → Save

### 3. Netlify verbinden

1. [netlify.com](https://netlify.com) → „Add new site" → „Import an existing project"
2. GitHub-Repo auswählen
3. Build-Einstellungen:
   - **Build command:** *(leer lassen)*
   - **Publish directory:** `public`
4. Deploy! Netlify gibt dir eine URL wie `https://xyz.netlify.app`

### 4. Spieler anpassen

`spieler.txt` bearbeiten — ein Lichess-Username pro Zeile.  
Zeilen mit `#` werden ignoriert.

---

## Wie es funktioniert

```
GitHub Actions (cron: stündlich)
  └─ python lichess_tracker.py
       └─ ruft Lichess API ab
       └─ schreibt public/index.html + werte.json
  └─ git commit & push
       └─ Netlify erkennt neuen Commit
       └─ deployed public/index.html automatisch
```

Der `werte.json`-Cache wird direkt ins Repo committed → Diff-Werte bleiben auch zwischen Runs erhalten.

---

## Lokal testen

```bash
python lichess_tracker.py
# → public/index.html wird erstellt
open public/index.html
```
