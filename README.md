# mischamops 🎶

Findet die Alben aus deiner Spotify-Playlist als **Schallplatte bei [medimops.de](https://www.medimops.de)** und schreibt einen übersichtlichen Bericht – auf Wunsch automatisch jede Woche.

Ein Bericht sieht so aus:

```markdown
# medimops Vinyl-Report 2026-10-07

277 Alben aus der Playlist geprüft · **12 Treffer**, davon **12 neu** seit dem letzten Lauf.

## Treffer

|    | Künstler    | Album                 | medimops-Artikel                  | Format         |
|----|-------------|-----------------------|-----------------------------------|----------------|
| 🆕 | Bob Dylan   | Highway 61 Revisited  | Bob Dylan Highway 61 Revisited    | vinyl-lp-vinyl |
| 🆕 | Sylvan Esso | Free Love             | Sylvan Esso Free Love             | vinyl-lp-vinyl |
…

## Weitere Vinyl von Künstlern aus der Playlist

- **Iggy Pop** (6): Brick By Brick, Instinct, Lust For Life, …
```

Alle Einträge sind Links – zum Album auf Spotify und zum Angebot bei medimops.

---

## Inhalt

1. [Voraussetzungen](#1-voraussetzungen)
2. [Installation](#2-installation)
3. [Spotify-App anlegen](#3-spotify-app-anlegen)
4. [Konfiguration (.env)](#4-konfiguration-env)
5. [Einmalig bei Spotify anmelden](#5-einmalig-bei-spotify-anmelden)
6. [Bericht erstellen](#6-bericht-erstellen)
7. [Jede Woche automatisch](#7-jede-woche-automatisch)
8. [So funktioniert es](#8-so-funktioniert-es)
9. [Fehlerbehebung](#9-fehlerbehebung)

---

## 1. Voraussetzungen

| Was | Warum |
|---|---|
| **Python 3.9 oder neuer** | Das Skript ist ein einzelnes Python-Programm, ohne weitere Pakete. |
| **Spotify Premium** | Spotify erlaubt eigene Entwickler-Apps seit Februar 2026 nur noch mit Premium. |
| **Die Playlist muss dir gehören** | Spotify gibt die Songs einer Playlist nur an ihren Besitzer heraus – auch bei öffentlichen Playlists (siehe [Fehlerbehebung](#spotify-verweigert-den-zugriff-auf-die-playlist-403)). |
| macOS, Linux oder Windows | Getestet auf macOS. |

Prüfen, ob Python da ist – im Terminal:

```bash
python3 --version
```

Kommt eine Versionsnummer ≥ 3.9, passt alles. Auf dem Mac fragt macOS sonst ggf., ob die „Developer Tools“ installiert werden sollen – einfach bestätigen. Alternativ: [python.org/downloads](https://www.python.org/downloads/).

> **Windows:** Statt `python3` heißt der Befehl meist `python` oder `py`.

## 2. Installation

```bash
git clone https://github.com/lemoony/mischamops.git
cd mischamops
```

Mehr ist nicht nötig – es gibt keine Abhängigkeiten zu installieren.

## 3. Spotify-App anlegen

Das Skript braucht eine (kostenlose) „App“ bei Spotify, um deine Playlist lesen zu dürfen. Das geht am besten am Computer, nicht am Handy (dort fehlt der Button).

1. Öffne <https://developer.spotify.com/dashboard> und melde dich mit deinem Spotify-Account an. Beim ersten Mal musst du die Nutzungsbedingungen akzeptieren und ggf. deine E-Mail bestätigen.
2. Klicke **Create app** und fülle aus:
   - **App name:** `mischamops` (beliebig)
   - **App description:** `Persönlicher Vinyl-Report` (beliebig)
   - **Website:** leer lassen
   - **Redirect URIs:** genau `http://127.0.0.1:8888/callback` eintragen und auf **Add** klicken
   - **Which API/SDKs are you planning to use?** → **Web API** ankreuzen
   - Bedingungen akzeptieren → **Save**
3. In der App auf **Settings** gehen. Dort findest du die **Client ID** und – hinter **View client secret** – das **Client Secret**. Beides brauchst du im nächsten Schritt.

> Das Client Secret ist wie ein Passwort: nicht teilen, nicht ins Repository committen. Falls es doch mal in falsche Hände gerät: in den Settings **Rotate client secret** klicken und den neuen Wert in `.env` eintragen.

## 4. Konfiguration (.env)

Kopiere die Vorlage und öffne sie in einem Texteditor:

```bash
cp .env.example .env
open -e .env        # macOS; sonst mit einem beliebigen Editor öffnen
```

Trage ein:

```ini
SPOTIFY_CLIENT_ID=deine-client-id
SPOTIFY_CLIENT_SECRET=dein-client-secret
SPOTIFY_PLAYLIST=https://open.spotify.com/playlist/...
```

Den Playlist-Link bekommst du in Spotify über **⋯ → Teilen → Link zur Playlist kopieren**. Der Teil nach `?si=…` darf dranbleiben.

`.env` steht in `.gitignore` und landet nie im Repository.

## 5. Einmalig bei Spotify anmelden

```bash
python3 mischamops.py --login
```

Es öffnet sich dein Browser mit der Spotify-Anmeldung. Melde dich an (mit dem Account, dem die Playlist gehört) und bestätige den Zugriff. Danach steht im Browser „Login abgeschlossen“ und das Skript beendet sich.

Die Anmeldung wird in `data/spotify_token.json` gespeichert und automatisch erneuert – du musst das nur **ein einziges Mal** machen (oder wieder, falls du den Zugriff in deinem Spotify-Konto entziehst).

> Öffnet sich kein Browser, kopiere den Link aus dem Terminal in deinen Browser – auf **demselben Computer**, denn Spotify schickt die Antwort an `127.0.0.1` (= diesen Rechner).

## 6. Bericht erstellen

```bash
python3 mischamops.py
```

Das dauert ca. 1–2 Minuten:

```
Spotify: 286 Tracks → 277 Alben
medimops: lade 162 Produkt-Sitemaps …
  20/162 Sitemaps, 36 Vinyl-Artikel
  …
medimops: 8479 Vinyl-Artikel im Index
Report: …/reports/2026-10-07.md
```

Den Bericht findest du im Ordner `reports/` – eine Markdown-Datei pro Tag. Öffnen z. B. mit VS Code, [Obsidian](https://obsidian.md), [MacDown](https://macdown.uranusjr.com) oder direkt als Text.

**So liest du ihn:**

- **Treffer** – Alben aus deiner Playlist, die es gerade als Platte gibt.
- **🆕** – neu seit dem letzten Lauf. Ab dem zweiten Lauf siehst du so sofort, was sich getan hat.
- **(?)** – unsicherer Treffer: der Titel ist ähnlich, aber nicht gleich (z. B. eine andere Edition). Kurz prüfen.
- **Weitere Vinyl von Künstlern aus der Playlist** – andere Platten deiner Künstler, die gerade da sind.
- **Preis und Zustand** stehen nur auf der medimops-Seite → Link öffnen.

### Optionen

| Befehl | Wirkung |
|---|---|
| `python3 mischamops.py` | Normaler Lauf mit der Playlist aus `.env` |
| `python3 mischamops.py --playlist <Link>` | Andere (eigene) Playlist verwenden |
| `python3 mischamops.py --login` | Spotify-Anmeldung (einmalig) |
| `python3 mischamops.py --cached-index` | medimops nicht neu laden, letzten Stand nehmen (schnell, zum Ausprobieren) |
| `python3 mischamops.py --cached-playlist` | Playlist nicht neu laden |

## 7. Jede Woche automatisch

### macOS (launchd)

launchd holt einen verpassten Termin nach, wenn der Mac zu dem Zeitpunkt geschlafen hat – besser als cron.

1. Pfade herausfinden:

   ```bash
   which python3      # z. B. /usr/bin/python3
   pwd                # im mischamops-Ordner, z. B. /Users/du/mischamops
   ```

2. Datei `~/Library/LaunchAgents/de.mischamops.weekly.plist` anlegen und die beiden Pfade (`/usr/bin/python3` und `/Users/du/mischamops`) ersetzen. Dieses Beispiel läuft **montags um 8:00 Uhr**:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key>
     <string>de.mischamops.weekly</string>
     <key>ProgramArguments</key>
     <array>
       <string>/usr/bin/python3</string>
       <string>/Users/du/mischamops/mischamops.py</string>
     </array>
     <key>WorkingDirectory</key>
     <string>/Users/du/mischamops</string>
     <key>StartCalendarInterval</key>
     <dict>
       <key>Weekday</key><integer>1</integer>   <!-- 1 = Montag … 7 = Sonntag -->
       <key>Hour</key><integer>8</integer>
       <key>Minute</key><integer>0</integer>
     </dict>
     <key>StandardOutPath</key>
     <string>/Users/du/mischamops/data/launchd.log</string>
     <key>StandardErrorPath</key>
     <string>/Users/du/mischamops/data/launchd.log</string>
   </dict>
   </plist>
   ```

3. Aktivieren und einmal testweise sofort starten:

   ```bash
   launchctl load ~/Library/LaunchAgents/de.mischamops.weekly.plist
   launchctl start de.mischamops.weekly
   ```

   Nach 1–2 Minuten sollte ein neuer Bericht in `reports/` liegen. Falls nicht: `data/launchd.log` ansehen.

4. Wieder abschalten:

   ```bash
   launchctl unload ~/Library/LaunchAgents/de.mischamops.weekly.plist
   ```

> Liegt der Ordner unter *Dokumente*, *Schreibtisch* oder *Downloads*, kann macOS dem Hintergrundjob den Zugriff verweigern („Operation not permitted“ im Log). Dann den Ordner z. B. nach `~/mischamops` verschieben.

### Linux (cron)

`crontab -e` und diese Zeile ergänzen (Montag 8:00, Pfad anpassen):

```cron
0 8 * * 1 cd /home/du/mischamops && /usr/bin/python3 mischamops.py >> data/cron.log 2>&1
```

### Windows (Aufgabenplanung)

Aufgabenplanung → **Einfache Aufgabe erstellen** → Wöchentlich → Aktion „Programm starten“:
- Programm: `py`
- Argumente: `mischamops.py`
- Starten in: dein `mischamops`-Ordner

## 8. So funktioniert es

```
Spotify-Playlist ──► Alben ──┐
                             ├──► Abgleich ──► reports/JJJJ-MM-TT.md
medimops-Sitemaps ─► Vinyl ──┘
```

1. **Spotify:** Das Skript lädt alle Songs der Playlist über die offizielle Spotify Web API und fasst sie zu Alben zusammen (aus 300 Songs werden so z. B. 280 Alben, aus 3000 vielleicht 1500). Jedes Album wird nur einmal gesucht.

2. **medimops:** medimops hat keine öffentliche Schnittstelle. Die Suche und die Produktseiten sind durch eine Bot-Sperre (Cloudflare) geschützt und die Suche ist laut `robots.txt` für Programme tabu – beides umgeht das Skript **nicht**. Stattdessen nutzt es die **öffentlichen Sitemaps**: Listen aller Produktadressen, die medimops für Suchmaschinen bereitstellt und die laut `robots.txt` ausdrücklich erlaubt sind. Es sind ~160 Dateien (~270 MB komprimiert). Die Produktadressen enthalten Künstler, Titel und Format, z. B.

   ```
   https://www.medimops.de/david-bowie-aladdin-sane-vinyl-lp-lp-record-M0B00004WP9Y.html
   ```

   Daraus filtert das Skript alle Schallplatten heraus (aktuell ca. 8.500 von mehreren Millionen Artikeln) und speichert sie in `data/vinyl_index.json`. CDs „in Vinyl-Optik“ werden aussortiert.

3. **Abgleich:** Künstler müssen übereinstimmen, Titel werden unscharf verglichen. Zusätze wie „Remastered“, „Deluxe Edition“ oder Jahreszahlen werden ignoriert, Umlaute in beiden Schreibweisen berücksichtigt („Ärzte“ = „aerzte“ = „arzte“).

4. **Gedächtnis:** `data/seen.json` merkt sich, was beim letzten Mal gefunden wurde – daher die 🆕-Markierung.

### Grenzen

- **Kein Preis, kein Zustand:** Die stehen nur auf der Produktseite. Der Bericht verlinkt dorthin.
- **„Verfügbar“ ist eine Annahme:** Stichproben zeigen, dass medimops nur Artikel auf Lager in die Sitemap aufnimmt. Sie wird täglich erneuert – ein Artikel kann aber zwischendurch verkauft werden.
- **Treffer sind nicht perfekt:** Andere Schreibweisen können Treffer verhindern, ähnliche Titel falsche erzeugen (dann mit **(?)** markiert).
- **Singles** gibt es selten als Platte – die meisten Treffer kommen von Alben.
- Ändert medimops den Aufbau seiner Adressen oder Sitemaps, muss das Skript angepasst werden.

### Dateien

| Pfad | Inhalt | Im Git? |
|---|---|---|
| `mischamops.py` | das Programm | ✅ |
| `.env.example` | Vorlage für die Konfiguration | ✅ |
| `.env` | deine Zugangsdaten | ❌ |
| `data/spotify_token.json` | deine Spotify-Anmeldung | ❌ |
| `data/albums.json`, `data/vinyl_index.json` | Zwischenstände | ❌ |
| `data/seen.json` | Treffer vom letzten Lauf (für 🆕) | ❌ |
| `reports/` | deine Berichte | ❌ |

## 9. Fehlerbehebung

### `SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET fehlen`
Es gibt keine `.env` oder die Werte fehlen → [Schritt 4](#4-konfiguration-env). Die Datei muss im selben Ordner wie `mischamops.py` liegen und genau `.env` heißen.

### `Kein Spotify-Login vorhanden`
→ `python3 mischamops.py --login` ([Schritt 5](#5-einmalig-bei-spotify-anmelden)).

### Spotify meldet „INVALID_CLIENT: Invalid redirect URI“
Die Redirect-URI in der Spotify-App stimmt nicht. Im Dashboard unter **Settings → Redirect URIs** muss **exakt** `http://127.0.0.1:8888/callback` stehen (kein `localhost`, kein `/` am Ende). Speichern und `--login` erneut ausführen.

### `Address already in use` beim Login
Port 8888 ist belegt. Im Dashboard eine zweite Redirect-URI wie `http://127.0.0.1:8899/callback` ergänzen und in `.env` setzen:
`SPOTIFY_REDIRECT_URI=http://127.0.0.1:8899/callback`

### Spotify verweigert den Zugriff auf die Playlist (403)
Seit Februar 2026 liefert Spotify für Entwickler-Apps **nur die Songs von Playlists, die dem angemeldeten Account gehören** – öffentliche Playlists anderer Leute geben nur Name und Cover heraus ([Spotify-Changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)). Lösungen:
- Mit dem Account anmelden, dem die Playlist gehört (`--login` erneut ausführen).
- Oder die Playlist in den eigenen Account kopieren: in der Spotify-Desktop-App Playlist öffnen, mit **Cmd/Strg + A** alle Songs markieren, Rechtsklick → **Zur Playlist hinzufügen → Neue Playlist**. Nachteil: Die Kopie wächst nicht mit dem Original mit.

### Spotify: 403 oder „user may not be registered“ direkt beim Login
Der Account hat kein Premium, oder du meldest dich mit einem anderen Account an als dem, mit dem die App erstellt wurde. Andere Accounts muss man im Dashboard unter **User Management** freischalten (max. 5).

### Keine oder sehr wenige Treffer
Das kann einfach stimmen – medimops verkauft gebrauchte Platten, das Angebot wechselt. Den medimops-Teil kannst du prüfen: `data/vinyl_index.json` sollte einige Tausend Einträge enthalten. Sind es 0, hat medimops vermutlich seine Sitemaps umgebaut.

### Der Hintergrundjob läuft nicht (macOS)
`data/launchd.log` ansehen. Häufigste Ursachen: falscher Pfad zu `python3` in der plist, oder der Ordner liegt unter *Dokumente/Schreibtisch* (siehe Hinweis in [Schritt 7](#macos-launchd)).
