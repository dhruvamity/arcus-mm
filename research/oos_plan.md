# Out-of-sample plan (frozen 2026-09-22)

Configs were chosen on tape through 2026-09-21 23:59 UTC. They are scored, unchanged, on tape
from **2026-09-22 00:00 UTC through 2026-09-28 23:59 UTC**. No parameter may change after the
commit that adds this file; a changed config is a new hypothesis and needs a new window.

Command (run after 2026-09-29 00:00 UTC, once those days are closed):

```bash
.venv/bin/python scripts/deep_quote_backtest.py --markets GLD-USD,NVDA-USD,HYPE-USD,SPY-USD,ETH-USD \
    --depths 2,3,5 --from-day 2026-09-22 --to-day 2026-09-28 --out research/oos_result.md
```

Score only the rows listed below (the grid also prints neighbours, which are not hypotheses).
`--from-day` replays 2026-09-21 to build the book but places no quotes before 2026-09-22 00:00 UTC.

| id | market | depth | role |
|---|---|---:|---|
| C1 | GLD-USD | 2 bps | candidate |
| C2 | GLD-USD | 3 bps | candidate |
| C3 | NVDA-USD | 3 bps | candidate |
| C4 | HYPE-USD | 5 bps | candidate (latency-sensitive) |
| K1 | SPY-USD | 2 bps | breakeven reference |
| K2 | ETH-USD | 2 bps | negative control — must lose |

Fixed params: requote ≥1 bps, $25 clip, $100 max inventory, RTT 200 ms, skew 0, maker fee 0.

**Pass** for a candidate: net PnL > 0 over the week **and** positive on ≥ 5 of 7 days **and**
≥ 150 fills. K2 must come out negative, or the replay is suspect. One passing candidate moves to
testnet order-lifecycle checks (post-only, cancel latency, reconciliation), not to mainnet.
