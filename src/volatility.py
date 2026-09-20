from __future__ import annotations

"""Deterministic Realized Volatility Estimator for Arcus Perpetuals Market Making.

- Deterministic volatility estimator from historical/live BBO or mid data.
- 1-second sampling grid for log-returns.
- EWMA variance filter with configurable half-life (default 300s).
- Outlier/jump clipping at configurable threshold (default 500 bps).
- Annualization convention using seconds-per-year (365.25 * 86,400).
- Zero look-ahead bias.
"""

import math
from typing import Optional, Dict, Any


class RealizedVolatilityEstimator:
    """Estimates continuous realized volatility dynamically from streaming mid prices."""

    SECONDS_PER_YEAR = 365.25 * 86_400.0

    def __init__(
        self,
        sampling_interval_sec: float = 1.0,
        half_life_sec: float = 300.0,
        max_jump_bps: float = 500.0,
        min_volatility: float = 0.05,  # 5% annual floor
        default_initial_vol: float = 0.30,  # 30% initial prior
    ):
        self.sampling_interval_sec = sampling_interval_sec
        self.sampling_interval_ns = int(sampling_interval_sec * 1e9)
        self.half_life_sec = half_life_sec
        self.decay_factor_per_sec = math.log(2.0) / half_life_sec
        self.max_jump_bps = max_jump_bps
        self.min_volatility = min_volatility
        self.default_initial_vol = default_initial_vol

        # State
        self.last_sample_ts_ns: Optional[int] = None
        self.last_sample_mid: Optional[float] = None
        # Convert initial vol to per-interval variance prior
        var_per_sec = (default_initial_vol ** 2) / self.SECONDS_PER_YEAR
        self.ewma_var_per_sec: float = var_per_sec
        self.samples_count: int = 0
        self.outliers_clipped: int = 0

    def reset(self) -> None:
        """Resets the volatility estimator state."""
        self.last_sample_ts_ns = None
        self.last_sample_mid = None
        var_per_sec = (self.default_initial_vol ** 2) / self.SECONDS_PER_YEAR
        self.ewma_var_per_sec = var_per_sec
        self.samples_count = 0
        self.outliers_clipped = 0

    def update(self, ts_ns: int, mid_price: float) -> float:
        """Processes an incoming mid price observation and updates EWMA volatility."""
        if mid_price <= 0:
            return self.get_annualized_volatility()

        if self.last_sample_ts_ns is None:
            self.last_sample_ts_ns = ts_ns
            self.last_sample_mid = mid_price
            return self.get_annualized_volatility()

        delta_ns = ts_ns - self.last_sample_ts_ns
        if delta_ns < self.sampling_interval_ns:
            # Sub-interval event: do not over-sample, return current estimate
            return self.get_annualized_volatility()

        delta_sec = delta_ns / 1e9
        prev_mid = self.last_sample_mid
        self.last_sample_ts_ns = ts_ns
        self.last_sample_mid = mid_price

        if prev_mid is None or prev_mid <= 0:
            return self.get_annualized_volatility()

        # Compute log return
        try:
            log_ret = math.log(mid_price / prev_mid)
        except (ValueError, ZeroDivisionError):
            return self.get_annualized_volatility()

        # Outlier / jump handling
        ret_bps = abs(log_ret) * 10_000.0
        if ret_bps > self.max_jump_bps:
            self.outliers_clipped += 1
            # Clip return to max allowable jump
            log_ret = math.copysign((self.max_jump_bps / 10_000.0), log_ret)

        # Instantaneous variance rate per second
        inst_var_per_sec = (log_ret ** 2) / delta_sec

        # EWMA decay
        decay = math.exp(-self.decay_factor_per_sec * delta_sec)
        self.ewma_var_per_sec = decay * self.ewma_var_per_sec + (1.0 - decay) * inst_var_per_sec
        self.samples_count += 1

        return self.get_annualized_volatility()

    def get_annualized_volatility(self) -> float:
        """Returns annualized volatility estimate (sigma)."""
        ann_var = max(0.0, self.ewma_var_per_sec * self.SECONDS_PER_YEAR)
        vol = math.sqrt(ann_var)
        return max(self.min_volatility, vol)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annualized_volatility": round(self.get_annualized_volatility(), 4),
            "samples_count": self.samples_count,
            "outliers_clipped": self.outliers_clipped,
            "half_life_sec": self.half_life_sec,
            "sampling_interval_sec": self.sampling_interval_sec,
        }
