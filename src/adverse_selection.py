"""Adverse Selection & Toxicity Markout Engine for Arcus Perpetuals.

Fulfills Section 4.1, 4.4, and 6.5 of prompt.md:
- Strict un-clamped markout horizons: [100ms, 500ms, 1s, 5s, 10s, 30s, 60s].
- Fills whose target timestamp (t + h) exceeds recorded data are DROPPED, never clamped.
- Reports N (sample size) and confidence intervals per horizon.
- Supports both trade-tape markouts and simulated passive fill markouts.
- Fixed dollar size buckets ($0-$15, $15-$50, >$50) to evaluate sweep asymmetry.
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

HORIZONS_SEC = [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
MAX_TOLERANCE_WINDOW_SEC = 5.0  # Max acceptable gap between target_ts and found BBO mid


def compute_markouts(
    fill_timestamps_ns: np.ndarray,
    fill_prices: np.ndarray,
    fill_sides: np.ndarray,      # "BUY" or "SELL" (passive maker side)
    fill_notionals: np.ndarray,
    bbo_timestamps_ns: np.ndarray,
    bbo_mids: np.ndarray,
    horizons_sec: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Computes forward markouts across horizons with strict dropping of unresolvable fills."""
    horizons = horizons_sec or HORIZONS_SEC
    n_fills = len(fill_timestamps_ns)
    if n_fills == 0 or len(bbo_timestamps_ns) == 0:
        return {
            "total_fills": 0,
            "horizons": {f"{h}s": {"N": 0, "mean_bps": 0.0, "median_bps": 0.0, "p5_bps": 0.0, "p95_bps": 0.0} for h in horizons},
            "by_side": {"BUY": {}, "SELL": {}},
            "by_size_bucket_5s": {},
        }

    # Ensure sorted BBO
    sort_idx = np.argsort(bbo_timestamps_ns)
    bbo_ts = bbo_timestamps_ns[sort_idx]
    bbo_m = bbo_mids[sort_idx]
    max_bbo_ts = bbo_ts[-1]

    markouts_by_horizon: Dict[str, List[float]] = {f"{h}s": [] for h in horizons}
    drifts_by_horizon: Dict[str, List[float]] = {f"{h}s": [] for h in horizons}
    spread_caps_by_horizon: Dict[str, List[float]] = {f"{h}s": [] for h in horizons}
    markouts_buy: Dict[str, List[float]] = {f"{h}s": [] for h in horizons}
    markouts_sell: Dict[str, List[float]] = {f"{h}s": [] for h in horizons}
    dollar_buckets = {"small_under_15": [], "medium_15_to_50": [], "large_over_50": []}

    for i in range(n_fills):
        t_fill = fill_timestamps_ns[i]
        p_fill = fill_prices[i]
        side = fill_sides[i]
        notional = fill_notionals[i]

        # Contemporaneous mid at fill time (as-of join: last BBO <= t_fill)
        idx_fill = int(np.searchsorted(bbo_ts, t_fill, side="right")) - 1
        mid_fill = bbo_m[idx_fill] if idx_fill >= 0 else p_fill
        ref_p = mid_fill if mid_fill > 0 else p_fill
        side_sign = 1.0 if side == "BUY" else -1.0

        for h in horizons:
            target_ts = t_fill + int(h * 1e9)
            # If target exceeds the end of the recording, DROP (never clamp)
            if target_ts > max_bbo_ts:
                continue

            # As-of join per R-09: last BBO <= target_ts
            idx = int(np.searchsorted(bbo_ts, target_ts, side="right")) - 1
            if idx < 0 or idx >= len(bbo_ts):
                continue

            # Verify that found mid is within acceptable staleness tolerance
            staleness_sec = (target_ts - bbo_ts[idx]) / 1e9
            max_staleness = min(1.0, 0.5 * h)
            if staleness_sec > max_staleness:
                continue

            future_mid = bbo_m[idx]
            if p_fill <= 0 or ref_p <= 0:
                continue

            # 3-Component Decomposition per R-09:
            # 1. spread_capture = side_sign * (mid_fill - p_fill) / ref_p
            # 2. drift = side_sign * (future_mid - mid_fill) / ref_p
            # 3. total = side_sign * (future_mid - p_fill) / ref_p
            # 4. adverse_selection = - drift
            spread_cap_bps = side_sign * ((mid_fill - p_fill) / ref_p) * 10_000.0
            drift_bps = side_sign * ((future_mid - mid_fill) / ref_p) * 10_000.0
            as_bps = - drift_bps

            h_key = f"{h}s"
            markouts_by_horizon[h_key].append(as_bps)
            drifts_by_horizon[h_key].append(drift_bps)
            spread_caps_by_horizon[h_key].append(spread_cap_bps)

            if side == "BUY":
                markouts_buy[h_key].append(as_bps)
            else:
                markouts_sell[h_key].append(as_bps)

            if h == 5.0:  # 5s benchmark horizon for size analysis
                if notional < 15.0:
                    dollar_buckets["small_under_15"].append(as_bps)
                elif notional <= 50.0:
                    dollar_buckets["medium_15_to_50"].append(as_bps)
                else:
                    dollar_buckets["large_over_50"].append(as_bps)

    def _calc_stats(arr: List[float], drift_arr: Optional[List[float]] = None, sc_arr: Optional[List[float]] = None) -> Dict[str, Any]:
        n_obs = len(arr)
        if n_obs == 0:
            return {
                "N": 0,
                "mean_bps": 0.0,
                "median_bps": 0.0,
                "p25_bps": 0.0,
                "p75_bps": 0.0,
                "p5_bps": 0.0,
                "p95_bps": 0.0,
                "std_bps": 0.0,
                "ci_90_lower_bps": 0.0,
                "ci_90_upper_bps": 0.0,
                "drift_mean_bps": 0.0,
                "spread_capture_mean_bps": 0.0,
                "total_return_mean_bps": 0.0,
            }
        a = np.array(arr)
        mean_val = float(np.mean(a))
        std_val = float(np.std(a))
        se = std_val / math.sqrt(n_obs) if n_obs > 1 else 0.0
        d_mean = float(np.mean(drift_arr)) if drift_arr else 0.0
        sc_mean = float(np.mean(sc_arr)) if sc_arr else 0.0
        tot_mean = sc_mean + d_mean
        return {
            "N": n_obs,
            "mean_bps": round(mean_val, 2),
            "median_bps": round(float(np.median(a)), 2),
            "p25_bps": round(float(np.percentile(a, 25)), 2),
            "p75_bps": round(float(np.percentile(a, 75)), 2),
            "p5_bps": round(float(np.percentile(a, 5)), 2),
            "p95_bps": round(float(np.percentile(a, 95)), 2),
            "std_bps": round(std_val, 2),
            "ci_90_lower_bps": round(mean_val - 1.645 * se, 2),
            "ci_90_upper_bps": round(mean_val + 1.645 * se, 2),
            "drift_mean_bps": round(d_mean, 2),
            "spread_capture_mean_bps": round(sc_mean, 2),
            "total_return_mean_bps": round(tot_mean, 2),
        }

    # Compute statistics per horizon
    horizon_stats = {
        f"{h}s": _calc_stats(
            markouts_by_horizon[f"{h}s"],
            drifts_by_horizon[f"{h}s"],
            spread_caps_by_horizon[f"{h}s"],
        )
        for h in horizons
    }
    buy_stats = {f"{h}s": _calc_stats(markouts_buy[f"{h}s"]) for h in horizons}
    sell_stats = {f"{h}s": _calc_stats(markouts_sell[f"{h}s"]) for h in horizons}

    # Size bucket stats at 5s
    size_stats = {}
    for b_name, vals in dollar_buckets.items():
        if vals:
            v_arr = np.array(vals)
            size_stats[b_name] = {
                "N": len(vals),
                "mean_bps": round(float(np.mean(v_arr)), 2),
                "median_bps": round(float(np.median(v_arr)), 2),
            }
        else:
            size_stats[b_name] = {"N": 0, "mean_bps": 0.0, "median_bps": 0.0}

    return {
        "total_fills": n_fills,
        "horizons": horizon_stats,
        "by_side": {
            "BUY": buy_stats,
            "SELL": sell_stats,
        },
        "by_size_bucket_5s": size_stats,
    }


class AdverseSelectionStudy:
    """Evaluates adverse selection on historical trade tape and passive fills."""

    def __init__(self, horizons_sec: Optional[List[float]] = None):
        self.horizons_sec = horizons_sec or HORIZONS_SEC

    def evaluate_tape_trades(self, df_trades: pd.DataFrame, df_bbo: pd.DataFrame) -> Dict[str, Any]:
        """Evaluates forward markouts assuming passive counterparty on every tape trade."""
        if df_trades.empty or df_bbo.empty:
            return {"error": "Empty dataset"}

        # Tape trade side is taker side:
        # Taker BUY => maker SELL
        # Taker SELL => maker BUY
        maker_sides = np.where(df_trades["side"].values == "BUY", "SELL", "BUY")

        return compute_markouts(
            fill_timestamps_ns=df_trades["recv_ts_ns"].values,
            fill_prices=df_trades["price"].values,
            fill_sides=maker_sides,
            fill_notionals=df_trades["notional"].values,
            bbo_timestamps_ns=df_bbo["recv_ts_ns"].values,
            bbo_mids=df_bbo["mid_price"].values,
            horizons_sec=self.horizons_sec,
        )
