"""
apply_signals.py — Portfolio-Simulation für den Forward-Test
==============================================================
Wendet Signale aus forward_signals.json auf portfolio_state.json an,
genau wie run_backtest_engine() in DeepSeekTrader_v5.py:
  - BUY: Position eröffnen mit position_size_percent vom Portfoliowert
         (Wert VOR den Trades dieses Tages, wie im Backtest-Engine)
  - SELL: Position schließen, P&L verbuchen
  - Slippage 0.2% auf beide Richtungen
  - Sektor-Limit 25% hart durchgesetzt (CURATED_SECTORS aus forward_signal.py)
  - Max 8 offene Positionen gleichzeitig

Wird von forward_signal.py am Ende jedes wöchentlichen Laufs automatisch
aufgerufen (apply_latest_signal()). Für die einmalige Rekonstruktion der
bisherigen Historie siehe migrate_portfolio.py.
"""

import json
import logging
from pathlib import Path

from forward_signal import CURATED_SECTORS

SCRIPT_DIR   = Path(__file__).parent
STATE_FILE   = SCRIPT_DIR / "portfolio_state.json"
SIGNALS_FILE = SCRIPT_DIR / "forward_signals.json"

# ── Konstanten (identisch mit DeepSeekTrader_v5.py)
INITIAL_CAPITAL = 100_000
SLIPPAGE        = 0.002   # 0.2%
MAX_POSITIONS   = 8
MAX_SECTOR_PCT  = 0.25    # 25%

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# State laden/speichern
# ══════════════════════════════════════════════════════════════════════════════

def default_state():
    return {
        "initial_capital":          INITIAL_CAPITAL,
        "cash":                     INITIAL_CAPITAL,
        "initial_spy_price":        None,
        "last_applied_signal_date": None,
        "positions":                {},
        "closed_trades":            [],
        "equity_history":           [],
        "last_prices":              {},
        "last_prices_date":         None,
    }


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return default_state()


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_signals():
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE, encoding="utf-8") as f:
            return json.load(f).get("signals", [])
    return []


# ══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def gather_prices(signal):
    """Kurse für dieses Signal: prices_snapshot + per-action price als Fallback."""
    prices = dict(signal.get("prices_snapshot", {}))
    for a in signal.get("actions", []):
        tk = a.get("ticker")
        if tk and a.get("price") is not None:
            prices.setdefault(tk, float(a["price"]))
    return prices


def resolve_price(tk, pos, prices, last_prices):
    """Kurs-Fallback-Kette: aktuelles Signal -> zuletzt bekannter Kurs -> Einstiegskurs.
    Wichtig für Ticker, die in dieser Woche nicht im Signal-Snapshot auftauchen
    (z.B. weil sie aus den Top/Bottom-60 herausgefallen sind) — sonst würde ihre
    Bewertung fälschlich auf den Einstiegskurs zurückfallen und P&L verschwinden."""
    if tk in prices:
        return prices[tk]
    if last_prices and tk in last_prices:
        return last_prices[tk]
    return pos["entry_price"]


def position_value(positions, prices, last_prices=None):
    return sum(
        pos["shares"] * resolve_price(tk, pos, prices, last_prices)
        for tk, pos in positions.items()
    )


def sector_value(positions, prices, sector, sector_map, last_prices=None):
    return sum(
        pos["shares"] * resolve_price(tk, pos, prices, last_prices)
        for tk, pos in positions.items()
        if sector_map.get(tk, "Unknown") == sector
    )


# ══════════════════════════════════════════════════════════════════════════════
# Kern: ein Signal auf den State anwenden
# ══════════════════════════════════════════════════════════════════════════════

def apply_signal(state, signal, sector_map=CURATED_SECTORS, log_cb=None):
    """Wendet ein einzelnes Signal (ein Wochen-Eintrag aus forward_signals.json)
    auf den Portfolio-State an. Mutiert und gibt `state` zurück."""
    def emit(msg):
        (log_cb or log.info)(msg)

    date_str    = signal["date"]
    prices      = gather_prices(signal)
    spy_price   = signal.get("spy_price")
    # Kurse aus früheren Wochen/Tagen — Fallback für Positionen, die in diesem
    # Signal nicht auftauchen (z.B. aus den Top/Bottom-60 herausgefallen),
    # damit sie nicht fälschlich auf ihren Einstiegskurs zurückfallen.
    last_prices = dict(state.get("last_prices", {}))

    if not state.get("initial_spy_price") and spy_price:
        state["initial_spy_price"] = spy_price

    positions = state["positions"]
    cash      = state["cash"]
    actions   = signal.get("actions", [])

    # Portfoliowert VOR den Trades dieses Tages — wird für die Positionsgröße
    # aller BUYs dieses Tages verwendet (identisch mit v5: port_val wird nicht
    # nach jedem Trade neu berechnet).
    port_val_pre = cash + position_value(positions, prices, last_prices)

    # ── SELLs zuerst
    for a in actions:
        if a.get("action") != "SELL":
            continue
        tk = a.get("ticker")
        if tk not in positions:
            continue
        px = prices.get(tk)
        if px is None:
            emit(f"  SKIP SELL {tk}: kein Kurs")
            continue
        pos      = positions[tk]
        sell_px  = px * (1 - SLIPPAGE)
        revenue  = pos["shares"] * sell_px
        entry_v  = pos["shares"] * pos["entry_price"]
        pnl_pct  = (revenue - entry_v) / entry_v * 100 if entry_v else 0.0
        cash    += revenue

        state["closed_trades"].append({
            "ticker":               tk,
            "entry_date":           pos["entry_date"],
            "entry_price":          round(pos["entry_price"], 4),
            "position_pct_at_entry": pos.get("position_pct_at_entry"),
            "exit_date":            date_str,
            "exit_price":           round(sell_px, 4),
            "shares":               pos["shares"],
            "pnl_pct":              round(pnl_pct, 2),
            "pnl_value":            round(revenue - entry_v, 2),
            "rationale":            a.get("rationale", ""),
        })
        emit(f"  SELL {tk} @ ${sell_px:.2f} | P&L {pnl_pct:+.1f}%")
        del positions[tk]

    # ── BUYs
    for a in actions:
        if a.get("action") != "BUY":
            continue
        tk = a.get("ticker")
        if not tk or tk in positions:
            continue
        px = prices.get(tk)
        if px is None:
            emit(f"  SKIP BUY {tk}: kein Kurs")
            continue
        if len(positions) >= MAX_POSITIONS:
            emit(f"  SKIP BUY {tk}: Max Positionen ({MAX_POSITIONS})")
            continue

        pct    = max(5.0, min(25.0, float(a.get("position_size_percent", 10))))
        invest = port_val_pre * pct / 100.0
        if invest <= 0 or invest > cash:
            emit(f"  SKIP BUY {tk}: nicht genug Cash (${cash:,.0f} verfügbar)")
            continue

        # ── Sektor-Limit hart durchsetzen (unabhängig vom LLM)
        sector = sector_map.get(tk, "Unknown")
        if sector != "Unknown" and port_val_pre > 0:
            sec_val = sector_value(positions, prices, sector, sector_map, last_prices)
            if (sec_val + invest) / port_val_pre > MAX_SECTOR_PCT:
                emit(
                    f"  SKIP BUY {tk}: Sektor-Limit "
                    f"({sector} würde {((sec_val + invest) / port_val_pre) * 100:.0f}% "
                    f"> {MAX_SECTOR_PCT * 100:.0f}%)"
                )
                continue

        buy_px = px * (1 + SLIPPAGE)
        shares = invest / buy_px
        cash  -= invest
        positions[tk] = {
            "shares":               shares,
            "entry_price":          buy_px,
            "entry_date":           date_str,
            "position_pct_at_entry": pct,
        }
        emit(f"  BUY  {tk} {pct:.0f}% (${invest:,.0f}) @ ${buy_px:.2f}")

    state["cash"] = cash

    # ── Equity-Eintrag für diesen Signal-Tag
    port_val  = cash + position_value(positions, prices, last_prices)
    spy_value = state["initial_capital"]
    if state.get("initial_spy_price") and spy_price:
        spy_value = state["initial_capital"] * spy_price / state["initial_spy_price"]

    state["equity_history"].append({
        "date":            date_str,
        "portfolio_value": round(port_val, 2),
        "spy_value":       round(spy_value, 2),
    })
    state["last_applied_signal_date"] = date_str

    # ── Aktuelle Kurse persistieren, damit das Dashboard sie ohne Live-Fetch
    #    anzeigen kann (CORS blockiert Yahoo Finance im Browser).
    last_prices = state.setdefault("last_prices", {})
    last_prices.update({tk: px for tk, px in prices.items() if px is not None})
    state["last_prices_date"] = date_str

    return state


# ══════════════════════════════════════════════════════════════════════════════
# Einstiegspunkt für den wöchentlichen Lauf
# ══════════════════════════════════════════════════════════════════════════════

def apply_latest_signal():
    """Wendet nur das neueste Signal aus forward_signals.json an — idempotent,
    überspringt falls dieses Datum bereits verarbeitet wurde."""
    signals = load_signals()
    if not signals:
        log.warning("Keine Signale in forward_signals.json — nichts zu tun.")
        return None

    latest = signals[-1]
    state  = load_state()

    if state.get("last_applied_signal_date") == latest["date"]:
        log.info(f"Signal vom {latest['date']} wurde bereits angewendet — überspringe.")
        return state

    log.info(f"Wende Signal vom {latest['date']} auf portfolio_state.json an …")
    apply_signal(state, latest, log_cb=log.info)
    save_state(state)
    log.info(
        f"Portfolio aktualisiert -> Cash ${state['cash']:,.0f} | "
        f"{len(state['positions'])} offene Position(en) | "
        f"{len(state['closed_trades'])} geschlossene Trades gesamt"
    )
    return state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
    apply_latest_signal()
