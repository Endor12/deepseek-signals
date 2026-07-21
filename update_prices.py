"""
update_prices.py — Täglicher Kurs-Refresh für den Portfolio-Forward-Test
==========================================================================
Läuft werktags nach US-Marktschluss (siehe .github/workflows/daily_prices.yml):
  1. Holt aktuelle Kurse für alle offenen Positionen in portfolio_state.json
  2. Berechnet portfolio_value neu (Cash + offene Positionen zu aktuellen Kursen)
  3. Holt den SPY-Kurs und skaliert spy_value hoch
     (gleiche Logik wie first_spy_val in DeepSeekTrader_v5.py:
      initial_capital * aktueller SPY / SPY bei Start)
  4. Hängt einen neuen Eintrag an equity_history an
     (überschreibt einen evtl. bereits vorhandenen Eintrag für denselben Tag,
      z.B. wenn am selben Tag zuvor ein Signal angewendet wurde)

Verwendung (lokal):
  python update_prices.py
"""

import sys
import logging
import warnings
from datetime import datetime

from apply_signals import load_state, save_state

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def fetch_price(ticker):
    import yfinance as yf
    import pandas as pd
    try:
        df = yf.download(ticker, period="5d", progress=False, auto_adjust=True, timeout=15)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        close = df["Close"].dropna()
        if close.empty:
            return None
        return float(close.iloc[-1])
    except Exception as e:
        log.warning(f"  Kurs für {ticker} nicht ladbar: {e}")
        return None


def main():
    state = load_state()
    positions = state.get("positions", {})

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log.info(f"Aktualisiere Kurse für {len(positions)} offene Position(en) — {date_str}")

    # ── Kurse der offenen Positionen holen
    last_prices = state.setdefault("last_prices", {})
    position_value = 0.0
    for tk, pos in positions.items():
        price = fetch_price(tk)
        if price is None:
            log.warning(f"  {tk}: kein aktueller Kurs verfügbar, nutze entry_price als Fallback")
            price = pos["entry_price"]
        else:
            last_prices[tk] = price
        position_value += pos["shares"] * price
        log.info(f"  {tk}: ${price:.2f}  ({pos['shares']:.2f} Stk. = ${pos['shares'] * price:,.2f})")

    state["last_prices_date"] = date_str
    portfolio_value = state["cash"] + position_value

    # ── SPY-Kurs holen und hochrechnen
    spy_price = fetch_price("SPY")
    spy_value = state["initial_capital"]
    if spy_price and state.get("initial_spy_price"):
        spy_value = state["initial_capital"] * spy_price / state["initial_spy_price"]
    elif not state.get("initial_spy_price") and spy_price:
        # Sollte durch apply_signals eigentlich schon gesetzt sein; Fallback falls nicht.
        state["initial_spy_price"] = spy_price

    log.info(f"Portfolio-Wert: ${portfolio_value:,.2f}  |  SPY-Wert (skaliert): ${spy_value:,.2f}")

    # ── equity_history aktualisieren: heutigen Eintrag ersetzen falls vorhanden,
    #    sonst neu anhängen (verhindert Duplikate am Signal-Tag)
    history = state.setdefault("equity_history", [])
    entry = {
        "date": date_str,
        "portfolio_value": round(portfolio_value, 2),
        "spy_value": round(spy_value, 2),
    }
    if history and history[-1]["date"] == date_str:
        history[-1] = entry
        log.info("Heutigen equity_history-Eintrag aktualisiert.")
    else:
        history.append(entry)
        log.info("Neuen equity_history-Eintrag angehängt.")

    save_state(state)
    log.info("Fertig.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"Fehler: {e}")
        sys.exit(1)
