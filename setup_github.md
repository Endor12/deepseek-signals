# Setup-Anleitung: DeepSeek Forward Signal auf GitHub

Dieser Ordner (`forward_test/`) ist als eigenständiges Git-Repository gedacht.
GitHub Actions führt jeden Sonntag automatisch einen S&P 500 Scan durch und
committet die Ergebnisse in `forward_signals.json`.

---

## 1. Privates GitHub-Repository anlegen

1. Öffne [github.com](https://github.com) und melde dich an
2. Klicke oben rechts auf **+** → **New repository**
3. Name: z. B. `deepseek-forward-signals`
4. Sichtbarkeit: **Private** (API-Key liegt nur in Secrets, aber zur Sicherheit privat lassen)
5. **Kein** README, .gitignore oder Lizenz hinzufügen (Repo bleibt leer)
6. Klicke **Create repository**

---

## 2. Diesen Ordner als Repo hochladen

Öffne eine Kommandozeile im `forward_test/`-Ordner und führe aus:

```bash
git init
git add .
git commit -m "init: DeepSeek forward signal setup"
git branch -M main
git remote add origin https://github.com/DEIN-USERNAME/deepseek-forward-signals.git
git push -u origin main
```

> Ersetze `DEIN-USERNAME` durch deinen GitHub-Benutzernamen.

---

## 3. DEEPSEEK_API_KEY als Secret hinterlegen

Der API-Key wird **nie** in den Code oder ins Repo geschrieben — nur als verschlüsseltes Secret.

1. Gehe im Repo auf **Settings** → **Secrets and variables** → **Actions**
2. Klicke **New repository secret**
3. Name: `DEEPSEEK_API_KEY`
4. Value: Deinen DeepSeek API-Key (beginnt mit `sk-...`)
5. Klicke **Add secret**

Den Key findest du unter [platform.deepseek.com](https://platform.deepseek.com) → API Keys.

---

## 4. GitHub Actions aktivieren

GitHub Actions ist standardmäßig aktiviert. Prüfe kurz:

1. Gehe auf den Tab **Actions** in deinem Repo
2. Wenn du gefragt wirst, ob du Workflows aktivieren möchtest → **I understand my workflows, go ahead and enable them**
3. Du siehst den Workflow `Weekly S&P 500 Forward Signal` in der Liste

Der Workflow läuft automatisch jeden **Sonntag um 20:00 Uhr** deutscher Sommerzeit (18:00 UTC).

---

## 5. Ersten manuellen Test-Run auslösen

Um sofort zu testen ob alles funktioniert:

1. Gehe auf **Actions** → **Weekly S&P 500 Forward Signal**
2. Klicke rechts auf **Run workflow** → Branch: `main` → **Run workflow**
3. Der Lauf startet innerhalb weniger Sekunden
4. Klicke auf den laufenden Job um das Live-Log zu sehen
5. Nach ca. 5–10 Minuten (Daten laden + API-Call):
   - `forward_signals.json` erscheint im Repo mit dem ersten Signal
   - `forward_log.txt` enthält das Protokoll

---

## 6. Ergebnisse lesen

`forward_signals.json` wächst wöchentlich und enthält alle Signale:

```json
{
  "signals": [
    {
      "date": "2026-07-06",
      "generated_at_utc": "2026-07-06 18:03 UTC",
      "spy_price": 585.20,
      "universe_size": 487,
      "model": "deepseek-v4-flash",
      "confidence": 72,
      "overall_rationale": "Tech momentum remains strong ...",
      "cash_reserve": 20,
      "actions": [
        {"ticker": "NVDA", "action": "BUY", "price": 152.30, "rationale": "..."}
      ],
      "prices_snapshot": {
        "NVDA": 152.30
      }
    }
  ]
}
```

---

## 7. Lokal testen (ohne GitHub)

```bash
# Im forward_test/ Ordner:
pip install openai yfinance pandas numpy

# API-Key setzen (Windows PowerShell):
$env:DEEPSEEK_API_KEY = "sk-..."

# API-Key setzen (Linux/Mac):
export DEEPSEEK_API_KEY="sk-..."

# Skript ausführen:
python forward_signal.py
```

Alternativ: Trage den Key in `../config.json` ein (Feld `"api_key"`).
Das Skript liest automatisch aus `config.json` als Fallback.

---

## Dateistruktur

```
forward_test/               ← wird Git-Repo-Root
├── forward_signal.py       ← Hauptskript
├── forward_signals.json    ← wird automatisch erstellt/erweitert
├── forward_log.txt         ← Protokolldatei
├── setup_github.md         ← diese Anleitung
└── .github/
    └── workflows/
        └── weekly_signal.yml   ← GitHub Actions Workflow
```
