"""The backtest model against what the contracts did on a fork, and a few properties of the rule."""
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("strategy_backtest", Path(__file__).resolve().parents[1] / "strategy_backtest.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

# A kind-0 treasury (take-profit 5% / 10%, dip 5%, 20% of cash per buy) on a fork of chain 46630, launched and
# graduated through the factory, then walked through these TSLA prices with one keeper visit each: execute()
# until nothing was due, then buyback() until the budget was spent. Recorded 2026-10-04.
FORK = {
    "prices": [
        358.647358,
        376.5,
        395,
        374,
        393.5,
        355,
        373.5,
        392.5,
        340,
        357.5
    ],
    "executes": [
        0,
        12,
        1,
        0,
        1,
        0,
        2,
        1,
        0
    ],
    "startStock": 50.79059932334461,
    "endStock": 18.095467,
    "endCash": 11602.83,
    "buybackStockSpent": 5.400567
}

# The percentage buy-back kind with the recommended rule (1% / 2% / 1%, half the cash per buy) and a 0.1% keeper
# reward, the same way. Its 86 buy-backs spent what kind 0's fixed chunk would have spent in a handful.
FORK_ONE_PERCENT = {
    "prices": [
        358.530601,
        362.5,
        366.3,
        362.4,
        366.2,
        369.9,
        365.9,
        369.7,
        373.5,
        369.5,
        365.5,
        369.3,
        373.2
    ],
    "executes": [
        5,
        5,
        1,
        0,
        3,
        1,
        0,
        5,
        1,
        1,
        0,
        1
    ],
    "startStock": 50.79059932334461,
    "endStock": 34.076819,
    "endCash": 5506.58,
    "buybackStockSpent": 1.612127,
    "buybacks": 86
}


class ModelAgainstTheContracts(unittest.TestCase):
    def replay(self, slippage, fork=None, rule=(0.05, 0.10, 0.05, 0.20), keeper=0.005):
        FORK = fork or globals()["FORK"]
        costs = TOOL.Costs(slippage=slippage, keeper=keeper)
        t = TOOL.Treasury(*rule, costs)
        first = FORK["prices"][0]
        t.lots.append(TOOL.Lot(FORK["startStock"], first))
        t.last_sale = first
        executes, bought_back = [], 0.0
        for p in FORK["prices"][1:]:
            n = 0
            while n < 40 and t.execute(p):
                n += 1
            executes.append(n)
            bought_back += t.buyback_stock
            t.buyback_stock = 0.0
        return t, executes, bought_back

    def test_every_visit_takes_the_same_number_of_actions(self):
        for slippage in (0.0, 0.0005, 0.002):
            with self.subTest(slippage=slippage):
                self.assertEqual(self.replay(slippage)[1], FORK["executes"])

    def test_balances_end_within_a_tenth_of_a_percent(self):
        t, _, bought_back = self.replay(0.0)
        stock = sum(lot.qty for lot in t.lots)
        self.assertAlmostEqual(stock / FORK["endStock"], 1, delta=0.001)
        self.assertAlmostEqual(t.usdg / FORK["endCash"], 1, delta=0.001)
        self.assertAlmostEqual(bought_back / FORK["buybackStockSpent"], 1, delta=0.001)

    def test_the_one_percent_rule_matches_too(self):
        f = FORK_ONE_PERCENT
        t, executes, bought_back = self.replay(0.0, f, (0.01, 0.02, 0.01, 0.50), 0.001)
        self.assertEqual(executes, f["executes"])
        self.assertAlmostEqual(sum(lot.qty for lot in t.lots) / f["endStock"], 1, delta=0.001)
        self.assertAlmostEqual(t.usdg / f["endCash"], 1, delta=0.001)
        self.assertAlmostEqual(bought_back / f["buybackStockSpent"], 1, delta=0.003)


class RuleProperties(unittest.TestCase):
    def series(self, prices):
        return [(i * 3600, p) for i, p in enumerate(prices)]

    def test_nothing_is_sold_below_the_first_take_profit(self):
        x = TOOL.run(self.series([100, 104.9, 96, 104.9]), 10_000, 0.05, 0.10, 0.05, 0.5)
        self.assertEqual((x["sells"], x["buybacks"]), (0, 0))
        self.assertEqual(x["dip_buys"], 0, "there is no cash to buy a dip with before a sale")

    def test_a_sale_keeps_only_its_profit_for_the_buyback(self):
        x = TOOL.run(self.series([100, 111]), 1_000, 0.05, 0.10, 0.05, 0.5, costs=TOOL.Costs(keeper=0, pool_fee=0, slippage=0))
        self.assertAlmostEqual(x["buyback_usd"], 110, places=6)          # the 11% gain on 1,000
        self.assertAlmostEqual(x["treasury"].usdg, 1_000, places=6)      # the principal came back as cash

    def test_percentage_sizing_spends_the_same_budget_in_more_calls(self):
        prices = self.series([100, 111] + [111] * 30)
        fixed = TOOL.run(prices, 50_000, 0.05, 0.10, 0.05, 0.5)
        share = TOOL.run(prices, 50_000, 0.05, 0.10, 0.05, 0.5, costs=TOOL.Costs(buyback_bps=1000))
        self.assertAlmostEqual(fixed["buyback_usd"], share["buyback_usd"], places=6)
        self.assertGreater(share["buybacks"], 3 * fixed["buybacks"])

    def test_the_shipped_price_file_loads(self):
        series = TOOL.load()
        self.assertGreater(len(series), 10_000)
        self.assertTrue(all(b[0] > a[0] and b[1] > 0 for a, b in zip(series, series[1:])))


if __name__ == "__main__":
    unittest.main()
