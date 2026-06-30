"""
forward_signal.py — S&P 500 Forward Signal Logger
==================================================
Berechnet wöchentlich Indikatoren für den S&P 500 und loggt
DeepSeek-Signale ohne Portfolio-Simulation.

Verwendung (lokal):
  python forward_signal.py

API-Key Priorität:
  1. Umgebungsvariable DEEPSEEK_API_KEY
  2. Fallback: ../config.json → "api_key"
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# ── Pfade
SCRIPT_DIR   = Path(__file__).parent
SIGNALS_FILE = SCRIPT_DIR / "forward_signals.json"
LOG_FILE     = SCRIPT_DIR / "forward_log.txt"
CONFIG_FILE  = SCRIPT_DIR.parent / "config.json"

MODEL       = "deepseek-v4-flash"
DATA_PERIOD = "4mo"   # ~85 Handelstage — genug für EMA50 (span=50) und RSI (span=14)
MIN_VALID   = 20

# ── Logging (Datei + Konsole)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Ticker-Universum (identisch mit DeepSeekTrader_v5.py)
# TTD + VRT entfernt (forward_looking_bias), 9 Ticker ergänzt (survivorship_bias)
SP500_TICKERS = [
    "A","AAL","AAPL","ABBV","ABNB","ABT","ACGL","ACN","ADBE","ADI",
    "ADM","ADP","ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG",
    "AKAM","ALB","ALGN","ALL","ALLE","AMAT","AMCR","AMD","AME","AMGN",
    "AMP","AMT","AMZN","ANET","AON","AOS","APA","APD","APH",
    "APTV","ARE","ATO","AVB","AVGO","AVY","AWK","AXON","AXP","AZO",
    "BA","BAC","BALL","BAX","BBY","BDX","BEN","BF-B","BG","BIIB",
    "BK","BKNG","BKR","BLDR","BLK","BMY","BR","BRK-B","BRO","BSX",
    "BXP","C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE","CCI",
    "CCL","CDNS","CDW","CE","CEG","CF","CFG","CHD","CHRW","CHTR",
    "CI","CINF","CL","CLX","CMCSA","CME","CMG","CMI",
    "CMS","CNC","CNP","COF","COO","COP","COR","COST","CPAY","CPB",
    "CPRT","CPT","CRL","CRM","CRWD","CSCO","CSGP","CSX","CTAS",
    "CTRA","CTSH","CTVA","CVS","CVX","D","DAL","DD","DE",
    "DECK","DELL","DG","DGX","DHI","DHR","DIS","DLR","DLTR",
    "DOC","DOV","DOW","DPZ","DRI","DTE","DUK","DVA","DVN","DXCM",
    "EA","EBAY","ECL","ED","EFX","EG","EIX","EL","ELV","EMN",
    "EMR","ENPH","EOG","EPAM","EQIX","EQR","EQT","ES","ESS","ETN",
    "ETR","EVRG","EW","EXC","EXPD","EXPE","EXR","F","FANG","FAST",
    "FCX","FDS","FDX","FE","FFIV","FICO","FIS","FITB","FMC",
    "FOX","FOXA","FRT","FSLR","FTNT","FTV","GD","GDDY","GE","GEHC",
    "GEN","GEV","GILD","GIS","GL","GLW","GM","GNRC","GOOG","GOOGL",
    "GPC","GPN","GRMN","GS","GWW","HAL","HAS","HBAN","HCA","HD",
    "HIG","HII","HLT","HOLX","HON","HPE","HPQ","HRL","HSIC",
    "HST","HSY","HUBB","HUM","HWM","IBM","ICE","IDXX","IEX","IFF",
    "INCY","INTC","INTU","INVH","IP","IQV","IR","IRM","ISRG",
    "IT","ITW","IVZ","J","JBL","JCI","JKHY","JNJ","JPM","KDP",
    "KEY","KEYS","KHC","KIM","KKR","KLAC","KMB","KMI","KMX",
    "KO","KR","KVUE","L","LDOS","LEN","LH","LHX","LIN","LKQ",
    "LLY","LMT","LNT","LOW","LRCX","LULU","LUV","LVS","LW","LYB",
    "LYV","MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ",
    "MDT","MET","META","MGM","MKC","MLM","MMM","MNST","MO",
    "MOH","MOS","MPC","MPWR","MRK","MRNA","MS","MSCI","MSFT","MSI",
    "MTB","MTCH","MTD","MU","NDAQ","NDSN","NEE","NEM","NFLX","NI",
    "NKE","NOC","NOW","NRG","NSC","NTAP","NTRS","NUE","NVDA","NVR",
    "NWSA","NXPI","O","ODFL","OKE","OMC","ON","ORCL","ORLY","OTIS",
    "OXY","PANW","PARA","PAYC","PAYX","PCAR","PCG","PEG","PEP","PFE",
    "PFG","PG","PGR","PH","PHM","PKG","PLD","PLTR","PM","PNC",
    "PNR","PNW","PODD","POOL","PPG","PPL","PRU","PSA","PSX","PTC",
    "PWR","PYPL","QCOM","RCL","REG","REGN","RF","RJF","RL",
    "RMD","ROK","ROL","ROP","ROST","RSG","RTX","SBAC","SBUX",
    "SCHW","SHW","SJM","SLB","SMCI","SNA","SNPS","SO","SPG",
    "SPGI","SRE","STE","STLD","STT","STX","STZ","SW","SWK",
    "SYF","SYK","SYY","T","TAP","TDG","TDY","TECH","TEL","TER",
    "TFC","TGT","TJX","TMO","TMUS","TPR","TRGP","TRMB","TROW",
    "TRV","TSCO","TSLA","TSN","TT","TTWO","TXN","TXT","TYL",
    "UAL","UBER","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB",
    "V","VICI","VLO","VLTO","VMC","VRSK","VRSN","VRTX","VST",
    "VTR","VTRS","VZ","WAB","WAT","WBD","WDC","WEC","WELL","WFC",
    "WHR","WM","WMB","WMT","WRB","WST","WTW","WY","WYNN","XEL",
    "XYL","YUM","ZBH","ZBRA","ZION","ZTS",
    # survivorship_bias_missing (waren am 2025-06-01 im S&P 500)
    "JNPR","ANSS","HES","WBA","CZR","MKTX","K","MHK","DAY",
]

# Deduplizieren
SP500_TICKERS = list(dict.fromkeys(
    t.replace(".", "-").strip() for t in SP500_TICKERS if t.strip()
))

# ── Sektor-Mapping (aus DeepSeekTrader_v5.py, für Prompt-Kontext)
CURATED_SECTORS = {
    "WDC": "Memory_Storage", "STX": "Memory_Storage",
    "NTAP": "Memory_Storage", "MU": "Memory_Storage",
    "NVDA": "Semis", "AMD": "Semis", "AVGO": "Semis", "INTC": "Semis",
    "QCOM": "Semis", "TXN": "Semis", "ADI": "Semis", "MCHP": "Semis",
    "NXPI": "Semis", "ON": "Semis", "MPWR": "Semis", "SWKS": "Semis",
    "QRVO": "Semis", "TER": "Semis", "LRCX": "Semis", "AMAT": "Semis",
    "KLAC": "Semis", "SMCI": "Semis", "GFS": "Semis", "FSLR": "Semis",
    "MSFT": "Software", "ORCL": "Software", "CRM": "Software", "ADBE": "Software",
    "NOW": "Software", "INTU": "Software", "PANW": "Software", "SNPS": "Software",
    "CDNS": "Software", "FTNT": "Software", "CRWD": "Software", "ADSK": "Software",
    "WDAY": "Software", "ANSS": "Software", "ROP": "Software", "MSI": "Software",
    "GOOGL": "Internet", "GOOG": "Internet", "META": "Internet", "AMZN": "Internet",
    "NFLX": "Internet", "UBER": "Internet", "BKNG": "Internet",
    "ANET": "Networking", "CSCO": "Networking", "GLW": "Networking",
    "JNPR": "Networking", "FFIV": "Networking",
    "AAPL": "ConsumerTech", "DELL": "ConsumerTech", "HPQ": "ConsumerTech",
    "HPE": "ConsumerTech",
    "DHI": "Homebuilders", "LEN": "Homebuilders", "PHM": "Homebuilders",
    "NVR": "Homebuilders",
    "JPM": "Banks", "BAC": "Banks", "WFC": "Banks", "C": "Banks",
    "GS": "Banks", "MS": "Banks", "USB": "Banks", "PNC": "Banks",
    "V": "Payments", "MA": "Payments", "AXP": "Payments", "PYPL": "Payments",
    "FI": "Payments", "GPN": "Payments",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
    "SLB": "Energy", "PSX": "Energy", "MPC": "Energy", "VLO": "Energy",
    "HES": "Energy",
    "JNJ": "Pharma", "LLY": "Pharma", "PFE": "Pharma", "MRK": "Pharma",
    "ABBV": "Pharma", "BMY": "Pharma", "AMGN": "Pharma", "GILD": "Pharma",
    "GNRC": "Industrials", "ETN": "Industrials", "EMR": "Industrials",
    "PWR": "Industrials", "GE": "Industrials", "HON": "Industrials",
    "CAT": "Industrials", "DE": "Industrials",
    "ALB": "Materials", "LIN": "Materials", "FCX": "Materials",
    "NEM": "Materials", "SHW": "Materials", "APD": "Materials",
    "EBAY": "Retail", "WMT": "Retail", "COST": "Retail", "HD": "Retail",
    "LOW": "Retail", "TGT": "Retail", "NKE": "Retail",
    "WBA": "Pharmacy_Retail", "CZR": "Gaming", "MKTX": "FinTech",
    "K": "Food_Beverage", "MHK": "HomeGoods", "DAY": "HCM_Software",
}

# ── Playbook (Momentum-Strategie, kompakt für Signal-Modus)
PLAYBOOK = """\
# YOUR IDENTITY
You are a disciplined momentum investor.

# YOUR GOAL
Identify the strongest S&P 500 momentum opportunities for the coming week.
Generate actionable BUY/SELL/HOLD signals. No portfolio is active — this is a fresh scan.

# ENTRY CRITERIA (BUY)
- Chg20d > +5%  (strong 20-day momentum)
- EMA50dist > 0  (price above 50-day EMA)
- RSI between 40 and 72  (not overbought)

# EXIT CRITERIA (SELL signal for watchlist tracking)
- Chg20d turns negative
- EMA50dist < -2%
- RSI < 35

# OUTPUT FORMAT — valid JSON only:
{
  "actions": [
    {"ticker": "NVDA", "action": "BUY",  "position_size_percent": 15, "rationale": "Brief reason"},
    {"ticker": "AAPL", "action": "SELL", "position_size_percent": 0,  "rationale": "Brief reason"},
    {"ticker": "MSFT", "action": "HOLD", "position_size_percent": 10, "rationale": "Brief reason"}
  ],
  "cash_reserve": 20,
  "confidence": 75,
  "overall_rationale": "One sentence market summary"
}"""


# ══════════════════════════════════════════════════════════════════════════════

def load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        log.info("API-Key aus Umgebungsvariable DEEPSEEK_API_KEY geladen.")
        return key
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            key = cfg.get("api_key", "").strip()
            if key and not key.startswith("sk-DEIN"):
                log.info("API-Key aus ../config.json geladen.")
                return key
        except Exception as e:
            log.warning(f"Fehler beim Lesen von config.json: {e}")
    log.error(
        "Kein gültiger API-Key. "
        "Setze DEEPSEEK_API_KEY als Umgebungsvariable oder trage den Key in ../config.json ein."
    )
    sys.exit(1)


def load_prices():
    import yfinance as yf
    import pandas as pd
    import time
    import warnings
    warnings.filterwarnings("ignore")

    log.info(f"Lade Kursdaten für {len(SP500_TICKERS)} Ticker (Periode: {DATA_PERIOD}) …")

    prices = {}
    CHUNK = 25
    total_chunks = (len(SP500_TICKERS) + CHUNK - 1) // CHUNK

    for i in range(0, len(SP500_TICKERS), CHUNK):
        chunk = SP500_TICKERS[i:i + CHUNK]
        cn = i // CHUNK + 1
        for ticker in chunk:
            try:
                df = yf.download(
                    ticker, period=DATA_PERIOD,
                    progress=False, auto_adjust=True, timeout=15
                )
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                if "Close" not in df.columns or len(df) < MIN_VALID:
                    continue
                close = df["Close"].dropna()
                if len(close) < MIN_VALID or float(close.std()) == 0:
                    continue
                prices[ticker] = close
            except Exception:
                pass
        log.info(f"  Chunk {cn}/{total_chunks} → {len(prices)} valide Aktien bisher")
        if i + CHUNK < len(SP500_TICKERS):
            time.sleep(1)

    log.info(f"Kursdaten vollständig: {len(prices)} Aktien valide.")
    return pd.DataFrame(prices)


def compute_snapshot(prices_df):
    import numpy as np

    if len(prices_df) < MIN_VALID:
        return prices_df.__class__()

    cur = prices_df.iloc[-1]
    n   = len(prices_df)
    p5  = prices_df.iloc[max(0, n - 6)]
    p20 = prices_df.iloc[max(0, n - 21)]

    c5  = (cur / p5  - 1) * 100
    c20 = (cur / p20 - 1) * 100

    ema50     = prices_df.ewm(span=50, adjust=False).mean().iloc[-1]
    ema50dist = (cur / ema50 - 1) * 100

    delta = prices_df.diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = (-delta).where(delta < 0, 0.0)
    ag    = gain.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    al    = loss.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    rs    = ag / al.replace(0, float("nan"))
    rsi   = (100 - 100 / (1 + rs)).clip(0, 100)

    vol = prices_df.iloc[-20:].pct_change().std() * (252 ** 0.5) * 100

    import pandas as pd
    snap = pd.DataFrame({
        "Price":  cur,
        "Chg5d":  c5,
        "Chg20d": c20,
        "EMA50d": ema50dist,
        "RSI":    rsi,
        "Vol":    vol,
    }).round(2).replace([float("inf"), float("-inf")], float("nan")).dropna()

    return snap


def build_prompt(snap, spy_price, date_str):
    by_mom = snap.sort_values("Chg20d", ascending=False)

    rows = ["Ticker,Sector,Price,Chg5d%,Chg20d%,EMA50dist%,RSI,Vol%"]
    for tk, r in by_mom.head(60).iterrows():
        rows.append(
            f"{tk},{CURATED_SECTORS.get(tk, 'Unknown')},{r['Price']:.2f},"
            f"{r['Chg5d']:+.1f},{r['Chg20d']:+.1f},"
            f"{r['EMA50d']:+.1f},{r['RSI']:.0f},{r['Vol']:.1f}"
        )
    rows.append("\n--- Weakest 20 ---")
    for tk, r in by_mom.tail(20).iterrows():
        rows.append(
            f"{tk},{CURATED_SECTORS.get(tk, 'Unknown')},{r['Price']:.2f},"
            f"{r['Chg5d']:+.1f},{r['Chg20d']:+.1f},"
            f"{r['EMA50d']:+.1f},{r['RSI']:.0f},{r['Vol']:.1f}"
        )

    return (
        f"{PLAYBOOK}\n\n---\n\n"
        f"# MARKET DATA — {date_str}\n"
        f"SPY: ${spy_price:.2f}\n"
        f"Universe: {len(snap)} stocks\n\n"
        + "\n".join(rows)
        + "\n\nNo active portfolio — generate fresh signals only.\n"
        "Output ONLY valid JSON."
    )


def call_api(prompt, api_key):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
            timeout=60,
        )
        text  = resp.choices[0].message.content
        start = text.find("{")
        end   = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception as e:
        log.error(f"API-Fehler ({MODEL}): {e}")
        return None


def load_signals():
    if SIGNALS_FILE.exists():
        try:
            with open(SIGNALS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"signals": []}


def save_signals(data):
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Signal gespeichert → {SIGNALS_FILE.name} (gesamt: {len(data['signals'])} Einträge)")


# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info(f"Forward Signal Logger  |  Modell: {MODEL}")
    log.info("=" * 60)

    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        from openai import OpenAI
    except ImportError as e:
        log.error(f"Fehlende Bibliothek: {e}")
        log.error("Installiere mit: pip install openai yfinance pandas numpy")
        sys.exit(1)

    api_key  = load_api_key()
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    ts_utc   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    prices_df = load_prices()
    if prices_df.empty or len(prices_df) < MIN_VALID:
        log.error("Zu wenige Kursdaten geladen. Abbruch.")
        sys.exit(1)

    # SPY laden
    spy_price = 0.0
    try:
        spy_raw = yf.download("SPY", period=DATA_PERIOD, progress=False, auto_adjust=True)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = [col[0] for col in spy_raw.columns]
        spy_price = float(spy_raw["Close"].dropna().iloc[-1])
    except Exception as e:
        log.warning(f"SPY konnte nicht geladen werden: {e}. Nutze 0.")

    snap = compute_snapshot(prices_df)
    if snap.empty:
        log.error("Snapshot leer. Abbruch.")
        sys.exit(1)

    log.info(f"Snapshot: {len(snap)} Aktien | SPY: ${spy_price:.2f}")

    prompt   = build_prompt(snap, spy_price, date_str)
    log.info(f"API-Call → {MODEL} …")
    response = call_api(prompt, api_key)

    if response is None:
        log.error("Kein API-Response. Abbruch.")
        sys.exit(1)

    actions   = response.get("actions", [])
    rationale = response.get("overall_rationale", "")
    conf      = response.get("confidence", "?")
    log.info(f"Signale: {len(actions)} Aktionen | Konfidenz: {conf}% | {rationale[:120]}")

    # Kurse der empfohlenen Ticker aus Snapshot
    prices_snapshot = {}
    enriched_actions = []
    for a in actions:
        ea = dict(a)
        tk = a.get("ticker", "")
        if tk in snap.index:
            price = float(snap.loc[tk, "Price"])
            ea["price"] = price
            if a.get("action") in ("BUY", "SELL"):
                prices_snapshot[tk] = price
        enriched_actions.append(ea)
        log.info(
            f"  {a.get('action','?'):4s}  {tk:6s}"
            f"  ${ea.get('price', 0):.2f}"
            f"  — {a.get('rationale', '')[:80]}"
        )

    signal_entry = {
        "date":              date_str,
        "generated_at_utc":  ts_utc,
        "spy_price":         spy_price,
        "universe_size":     len(snap),
        "model":             MODEL,
        "confidence":        conf,
        "overall_rationale": rationale,
        "cash_reserve":      response.get("cash_reserve"),
        "actions":           enriched_actions,
        "prices_snapshot":   prices_snapshot,
    }

    data = load_signals()
    data["signals"].append(signal_entry)
    save_signals(data)
    log.info("Fertig.\n")


if __name__ == "__main__":
    main()
