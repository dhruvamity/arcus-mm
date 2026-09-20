from __future__ import annotations

"""Latency Pipeline Model for Arcus Market Making.

- Feed latency (WS market data arrival)
- Decision latency (strategy compute time)
- Send latency (network transit to gateway)
- Exchange ACK latency (matching engine process & confirmation)
- Cancel latency
- Modify latency

Supports testing at baseline, +100ms, +500ms, +1s, +5s.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CANONICAL_LATENCY_CONFIG_PATH = REPO_ROOT / "configs/latency_model.yaml"


def load_canonical_latency_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads single canonical latency configuration from configs/latency_model.yaml.
    All values are labeled PROVISIONAL until authenticated testnet RTT is benchmarked.
    """
    p = config_path or CANONICAL_LATENCY_CONFIG_PATH
    if not p.exists():
        return {
            "status": "PROVISIONAL",
            "sensitivity_grid_ms": [25.0, 60.0, 150.0, 300.0, 700.0],
            "empirical_rtt": {"status": "PROVISIONAL", "p50_rtt_ms": 173.99},
            "one_way_wire_transit": {"status": "PROVISIONAL_PING_ONLY", "p50_ms": 77.86},
        }
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_pre_declared_latency_grid(config_path: Optional[Path] = None) -> List[float]:
    """Returns pre-declared sensitivity grid [25.0, 60.0, 150.0, 300.0, 700.0] ms per WS-A."""
    cfg = load_canonical_latency_config(config_path)
    grid = cfg.get("sensitivity_grid_ms") or [25.0, 60.0, 150.0, 300.0, 700.0]
    return [float(x) for x in grid]


class LatencyConfig:
    """Latency parameters in milliseconds."""

    @classmethod
    def from_canonical_yaml(cls, config_path: Optional[Path] = None) -> LatencyConfig:
        """Constructs LatencyConfig from the single canonical configs/latency_model.yaml."""
        cfg = load_canonical_latency_config(config_path)
        base = cfg.get("baseline_pipeline_ms", {})
        return cls(
            feed_latency_ms=float(base.get("feed_latency_ms", 20.0)),
            decision_latency_ms=float(base.get("decision_latency_ms", 5.0)),
            send_latency_ms=float(base.get("send_latency_ms", 25.0)),
            ack_latency_ms=float(base.get("ack_latency_ms", 10.0)),
            cancel_latency_ms=float(base.get("cancel_latency_ms", 25.0)),
            modify_latency_ms=float(base.get("modify_latency_ms", 30.0)),
            additional_stress_latency_ms=float(base.get("additional_stress_latency_ms", 0.0)),
        )

    def __init__(
        self,
        feed_latency_ms: float = 20.0,
        decision_latency_ms: float = 5.0,
        send_latency_ms: float = 25.0,
        ack_latency_ms: float = 10.0,
        cancel_latency_ms: float = 25.0,
        modify_latency_ms: float = 30.0,
        additional_stress_latency_ms: float = 0.0,
        order_entry_latency_ms: Optional[float] = None,
        **kwargs: Any,
    ):
        if order_entry_latency_ms is not None:
            self.send_latency_ms = float(order_entry_latency_ms)
            self.feed_latency_ms = 0.0
            self.decision_latency_ms = 0.0
            self.ack_latency_ms = 0.0
        else:
            self.send_latency_ms = float(send_latency_ms)
            self.feed_latency_ms = float(feed_latency_ms)
            self.decision_latency_ms = float(decision_latency_ms)
            self.ack_latency_ms = float(ack_latency_ms)
        self.cancel_latency_ms = float(cancel_latency_ms)
        self.modify_latency_ms = float(modify_latency_ms)
        self.additional_stress_latency_ms = float(additional_stress_latency_ms)

    @property
    def order_entry_latency_ms(self) -> float:
        return self.total_place_latency_ms

    @property
    def total_place_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.send_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    @property
    def total_cancel_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.cancel_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    @property
    def total_modify_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.modify_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_latency_ms": self.feed_latency_ms,
            "decision_latency_ms": self.decision_latency_ms,
            "send_latency_ms": self.send_latency_ms,
            "ack_latency_ms": self.ack_latency_ms,
            "cancel_latency_ms": self.cancel_latency_ms,
            "modify_latency_ms": self.modify_latency_ms,
            "additional_stress_latency_ms": self.additional_stress_latency_ms,
            "total_place_latency_ms": self.total_place_latency_ms,
            "total_cancel_latency_ms": self.total_cancel_latency_ms,
        }


class LatencyModel:
    """Abstract base class for order transit and feed latency models."""

    def sample_ms(self, action: str, rng: Optional[Any] = None) -> float:
        raise NotImplementedError

    def sample_ns(self, action: str, rng: Optional[Any] = None) -> int:
        return int(self.sample_ms(action, rng) * 1_000_000)


class ConstantLatencyModel(LatencyModel):
    """Constant latency model with optional bounded uniform jitter."""

    def __init__(self, config: Optional[LatencyConfig] = None, jitter_fraction: float = 0.1):
        self.config = config or LatencyConfig()
        self.jitter_fraction = jitter_fraction

    def sample_ms(self, action: str, rng: Optional[Any] = None) -> float:
        if action == "place":
            base = self.config.total_place_latency_ms
        elif action == "cancel":
            base = self.config.total_cancel_latency_ms
        elif action == "modify":
            base = self.config.total_modify_latency_ms
        elif action == "feed":
            base = self.config.feed_latency_ms
        else:
            base = 25.0

        if rng and self.jitter_fraction > 0:
            jitter = rng.uniform(-self.jitter_fraction, self.jitter_fraction) * base
            return max(0.1, base + jitter)
        return max(0.1, base)


class EmpiricalLatencyModel(LatencyModel):
    """Samples latency empirically with replacement from recorded benchmark distributions."""

    def __init__(self, samples_file: Any, fallback_config: Optional[LatencyConfig] = None):
        from pathlib import Path
        self.samples_file = Path(samples_file)
        self.fallback = ConstantLatencyModel(fallback_config)
        self.samples: list[float] = []
        self._load_samples()

    def _load_samples(self) -> None:
        import json
        if not self.samples_file.exists():
            return
        if self.samples_file.suffix == ".jsonl":
            try:
                with open(self.samples_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        if "rtt_ms" in rec and rec.get("status") == "ok":
                            self.samples.append(float(rec["rtt_ms"]))
            except Exception:
                pass
            return

        if self.samples_file.suffix in (".yaml", ".yml"):
            try:
                with open(self.samples_file, "r", encoding="utf-8") as f:
                    ydata = yaml.safe_load(f)
                rtt = ydata.get("empirical_rtt") or ydata.get("empirical_latency") or {}
                if "p50_rtt_ms" in rtt:
                    p50 = float(rtt["p50_rtt_ms"])
                    p95 = float(rtt.get("p95_rtt_ms", p50 * 1.5))
                    p99 = float(rtt.get("p99_rtt_ms", p95 * 1.3))
                    p_min = float(rtt.get("min_rtt_ms", p50 * 0.7))
                    self.samples = [p_min, p50, p95, p99]
            except Exception:
                pass
            return

        try:
            with open(self.samples_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                rtt = data.get("rest_rtt_ms", {})
                if "p50" in rtt:
                    p50 = float(rtt.get("p50", 25.0))
                    p95 = float(rtt.get("p95", p50 * 1.5))
                    p_min = float(rtt.get("min", p50 * 0.8))
                    p_mean = float(rtt.get("mean", p50))
                    p_max = float(rtt.get("max", p95 * 1.2))
                    self.samples = [p_min, p50, p_mean, p95, p_max]
            elif isinstance(data, list):
                self.samples = [float(x) for x in data if isinstance(x, (int, float))]
        except Exception:
            pass

    def sample_ms(self, action: str, rng: Optional[Any] = None) -> float:
        import random
        if self.samples:
            chooser = rng.choice if rng else random.choice
            val = float(chooser(self.samples))
            if action == "cancel":
                return max(0.1, val * 0.8)
            return max(0.1, val)
        return self.fallback.sample_ms(action, rng)
