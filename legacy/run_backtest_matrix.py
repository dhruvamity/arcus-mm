"""LEGACY SCRIPT - DEPRECATED.
DO NOT USE FOR FORMAL BACKTESTING OR RESEARCH.
Superseded by SimEngine (src/sim/engine.py) and scripts/run_phase_14_backtest.py.
Preserved for archival purposes only.

CLI runner executing the complete Phase 7 & 8 Backtest Evaluation Matrix.
"""

import argparse
import datetime
import json
import logging
from pathlib import Path
import pandas as pd

from src.backtester import ArcusEventBacktester
from src.models.fill import FillModelType
from src.models.latency import LatencyConfig
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.strategies.avellaneda_stoikov import AvellanedaStoikovStrategy
from src.strategies.volatility_clock import VolatilityClockStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("legacy_backtest_cli")

MARKET_SPECS = {
    "HYPE-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0},
    "ZEC-USD": {"tick_size": 0.001, "step_size": 0.00001, "min_notional": 5.0},
    "NEAR-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0},
    "SPCX-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0},
    "LIT-USD": {"tick_size": 0.0001, "step_size": 0.001, "min_notional": 5.0},
    "UNI-USD": {"tick_size": 0.001, "step_size": 0.001, "min_notional": 5.0},
    "SLV-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0},
}


def main():
    logger.warning("run_backtest_matrix.py is DEPRECATED. Use SimEngine and scripts/run_phase_14_backtest.py.")


if __name__ == "__main__":
    main()
