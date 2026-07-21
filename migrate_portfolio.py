"""
migrate_portfolio.py — Einmalige Migration
============================================
Rechnet die bisherige Signal-Historie aus forward_signals.json rückwirkend
durch apply_signals.apply_signal() und erzeugt daraus ein initiales
portfolio_state.json. Nur einmal ausführen (bricht ab, falls die Datei
bereits existiert — Löschen/Umbenennen erzwingt eine Neuberechnung).

Verwendung:
  python migrate_portfolio.py [--force]
"""

import sys
import logging

from apply_signals import (
    default_state, save_state, load_signals, apply_signal, STATE_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def main():
    if STATE_FILE.exists() and "--force" not in sys.argv:
        log.error(
            f"{STATE_FILE.name} existiert bereits. "
            "Dies ist eine einmalige Migration — mit --force erneut ausführen "
            "(überschreibt die aktuelle Datei komplett)."
        )
        sys.exit(1)

    signals = load_signals()
    if not signals:
        log.error("forward_signals.json ist leer oder fehlt — nichts zu migrieren.")
        sys.exit(1)

    log.info(f"Migriere {len(signals)} Signal-Eintrag/Einträge aus forward_signals.json …")

    state = default_state()
    for signal in signals:
        log.info(f"\n[{signal['date']}] verarbeite …")
        apply_signal(state, signal, log_cb=log.info)

    save_state(state)
    log.info(f"\nFertig -> {STATE_FILE.name} geschrieben.")
    log.info(f"Cash: ${state['cash']:,.2f} | Offene Positionen: {len(state['positions'])} "
              f"| Geschlossene Trades: {len(state['closed_trades'])}")


if __name__ == "__main__":
    main()
