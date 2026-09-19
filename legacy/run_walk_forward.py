"""LEGACY SCRIPT - DEPRECATED.
DO NOT USE FOR FORMAL BACKTESTING OR RESEARCH.
Superseded by SimEngine (src/sim/engine.py) and Pre-registration Protocol v3 (research/prereg_backtest.md).
Preserved for archival purposes only.

CLI runner for Phase 10 Walk-Forward & Multiple-Testing Control.
"""

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legacy.run_backtest_matrix import MARKET_SPECS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("legacy_wf_cli")


def main():
    logger.warning("run_walk_forward.py is DEPRECATED. Refer to research/prereg_backtest.md for Protocol v3.")


if __name__ == "__main__":
    main()
