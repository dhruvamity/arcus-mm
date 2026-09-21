"""src/sweeps.py: sweep depth must not depend on row order within a taker order."""

import unittest

import numpy as np

from src import sweeps

S = 1_000_000


def tape(rows):
    a = np.array(rows, dtype=float)
    return a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3].astype(bool), a[:, 4].astype(np.int64)


# quotes 99.9/100.1 set by two small prints, then a taker buy sweeps 100.1 -> 100.3,
# then prints within 30 s put the mid back at 100.0
BASE = [(0, 99.9, 1, 0, 1), (1, 100.1, 1, 1, 2)]
SWEEP = [(10 * S, 100.1, 1, 1, 3), (10 * S, 100.2, 1, 1, 3), (10 * S, 100.3, 1, 1, 3)]
AFTER = [(20 * S, 99.9, 1, 0, 4), (21 * S, 100.1, 1, 1, 5), (60 * S, 100.0, 1, 1, 6)]


class TestSweeps(unittest.TestCase):
    def check(self, sweep_rows):
        ts, dep, rs, _ = sweeps.sweep_table(*tape(BASE + sweep_rows + AFTER))
        s = ts == 10 * S
        self.assertEqual(sorted(np.round(dep[s], 1)), [0.0, 10.0, 20.0])  # bps beyond the sweep's first print
        # maker who sold at 100.3 earns 30 bps vs the 100.0 mid 30 s later
        self.assertAlmostEqual(float(rs[s][np.argmax(dep[s])]), 30.0, places=1)

    def test_match_order(self):
        self.check(SWEEP)

    def test_newest_first_order(self):
        self.check(SWEEP[::-1])


if __name__ == "__main__":
    unittest.main()
