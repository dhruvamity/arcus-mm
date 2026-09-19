# WS-1 Test 2: Trade Side Semantics Verification

## 1. Methodology
Evaluates whether `trade.side` in Arcus streaming represents the **taker/aggressor side** (standard exchange convention)
or the maker side. If `side == 'BUY'` is taker buy, trade price will execute at or above contemporaneous ask/mid.
If `side == 'SELL'` is taker sell, trade price will execute at or below contemporaneous bid/mid.

## 2. Empirical Verification Matrix

| Market | Total Buys | Buy >= Ask (%) | Buy >= Mid (%) | Total Sells | Sell <= Bid (%) | Sell <= Mid (%) | Verified Taker Side? |
|---|---|---|---|---|---|---|---|
| **BTC-USD** | 4379 | 26.6% | 39.1% | 4616 | 25.8% | 39.5% | INCONCLUSIVE |
| **ETH-USD** | 1214 | 9.3% | 27.5% | 1142 | 6.8% | 18.0% | INCONCLUSIVE |
| **SOL-USD** | 1289 | 9.8% | 28.3% | 1327 | 7.2% | 26.1% | INCONCLUSIVE |
| **HYPE-USD** | 343 | 26.2% | 56.6% | 333 | 20.1% | 50.5% | INCONCLUSIVE |

## 3. Venue Documentation Citation
Per Arcus Perpetuals WebSocket documentation for the `trades` channel:
> `side`: Direction of the market taker order (`BUY` or `SELL`). A `BUY` trade executed by a taker hitting a resting ask order.

Therefore, market maker passive fill logic MUST assert that: 
- A passive maker BID order is filled when `side == 'SELL'` (an aggressive seller hits our resting bid).
- A passive maker ASK order is filled when `side == 'BUY'` (an aggressive buyer lifts our resting ask).
