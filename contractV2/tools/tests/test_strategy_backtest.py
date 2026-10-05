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

# HedgeFunV2CycleTreasury itself (take-profit 5% / 10%, dip and recovery 5%, 20% of cash, 20 USDG chunk) in the
# repository's V2CycleBase fixture, against its real concentrated-liquidity venue: one stock at 100, then these
# prices, execute() until nothing was due. Per step: price, actions, lots, stock, cash, buy-back stock, and the
# sale price a recovery buy is armed at.
CYCLE = [
    (105.5, 3, 1, 0.5, 49.849757, 0.025936019, 105.5),
    (111.0, 3, 0, 0.0, 99.69952, 0.075237821, 111.0),
    (117.0, 1, 1, 0.169065366, 79.760114, 0.075237821, 0.0),
    (110.0, 1, 2, 0.312925558, 63.808491, 0.075237821, 0.0),
    (116.0, 1, 2, 0.240995462, 71.720807, 0.078735418, 116.0),
    (104.0, 1, 3, 0.377818569, 57.377004, 0.078735418, 0.0),
    (98.0, 1, 4, 0.493979334, 45.901891, 0.078735418, 0.0),
    (104.0, 1, 4, 0.435898951, 51.593772, 0.081905529, 104.0),
    (110.0, 2, 3, 0.309407016, 64.400452, 0.091574043, 110.0),
    (116.0, 1, 2, 0.240995462, 71.515259, 0.098431992, 116.0),
    (109.0, 1, 3, 0.371168138, 57.212566, 0.098431992, 0.0),
    (103.0, 1, 4, 0.481373306, 45.770339, 0.098431992, 0.0),
    (109.0, 1, 4, 0.426270722, 51.445908, 0.101294043, 109.0),
    (115.0, 2, 3, 0.3060818, 64.215885, 0.110061356, 115.0),
    (118.0, 0, 3, 0.3060818, 64.215885, 0.110061356, 115.0),
    (112.0, 0, 3, 0.3060818, 64.215885, 0.110061356, 115.0)]

# The percentage rebalance treasury with realised-net-income accounting (target 70%, band 5%, 25% per action,
# 100% of the pinned basis per direction a day, half of a net gain to the buy-back), in the repository's
# V2TradablePercentEngineFixture: 95.831319478 stock booked at 100, a flat venue with a 0.3% fee, then one new
# trading day per step. Per step: price, actions, stock, cash, buy-back stock, unrecovered loss.
REBALANCE = [
    (100.0, 2, 66.948011338506524893, 2865.267492, 0.0, 23.063322),
    (100.0, 0, 66.948011338506524893, 2865.267492, 0.0, 23.063322),
    (130.0, 1, 62.410835910644420443, 3396.436565, 0.418370826086956521, 0.0),
    (130.0, 0, 62.410835910644420443, 3396.436565, 0.418370826086956521, 0.0),
    (90.0, 1, 70.042881544755531554, 2704.023539, 0.418370826086956521, 0.0),
    (90.0, 0, 70.042881544755531554, 2704.023539, 0.418370826086956521, 0.0),
    (70.0, 1, 76.022123900755531554, 2282.107575, 0.418370826086956521, 0.0),
    (70.0, 0, 76.022123900755531554, 2282.107575, 0.418370826086956521, 0.0),
    (110.0, 1, 67.771063883712863297, 3131.656544, 0.884092466319206558, 0.0),
    (150.0, 1, 62.076966737963731730, 3831.359918, 1.875953094461112723, 0.0),
    (150.0, 0, 62.076966737963731730, 3831.359918, 1.875953094461112723, 0.0),
    (120.0, 0, 62.076966737963731730, 3831.359918, 1.875953094461112723, 0.0),
    (80.0, 1, 73.954362071776231730, 2873.519939, 1.875953094461112723, 0.0),
    (140.0, 1, 66.166869338020853162, 3781.649231, 3.124595308108225785, 0.0),
]


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

    def test_the_cycle_treasury_matches_step_by_step(self):
        t = TOOL.Treasury(0.05, 0.10, 0.05, 0.20, TOOL.Costs(sell_chunk=20.0, slippage=0.0), cycle=True)
        t.lots.append(TOOL.Lot(1.0, 100.0))
        t.last_sale = 100.0
        for price, actions, lots, stock, cash, bought_back, armed in CYCLE:
            n = 0
            while n < 30 and t.execute(price):
                n += 1
            with self.subTest(price=price):
                self.assertEqual((n, len(t.lots)), (actions, lots))
                self.assertAlmostEqual(t.armed, armed, places=9)
                self.assertAlmostEqual(sum(lot.qty for lot in t.lots), stock, delta=stock * 1e-4 + 1e-9)
                self.assertAlmostEqual(t.usdg, cash, delta=cash * 1e-4)
                self.assertAlmostEqual(t.buyback_stock, bought_back, delta=bought_back * 1e-4)
        self.assertGreater(t.recovery_buys, 0, "the path exercises a recovery buy")

    def test_the_rebalance_treasury_matches_step_by_step(self):
        r = TOOL.Rebalance(0.70, 0.05, 0.5, TOOL.Costs(slippage=0.0), stock=95.831319478008699857, avg_cost=100.0)
        for day, (price, actions, stock, cash, bought_back, loss) in enumerate(REBALANCE):
            n = 0
            while n < 6 and r.execute(price, day):
                n += 1
            with self.subTest(day=day, price=price):
                self.assertEqual(n, actions)
                self.assertAlmostEqual(r.stock, stock, delta=stock * 1e-6)
                self.assertAlmostEqual(r.cash, cash, delta=cash * 1e-6)
                self.assertAlmostEqual(r.buyback_stock, bought_back, delta=bought_back * 1e-6 + 1e-12)
                self.assertAlmostEqual(r.loss, loss, delta=loss * 1e-6 + 1e-9)


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

    def test_the_shipped_price_files_load(self):
        self.assertGreater(len(TOOL.load()), 10_000)
        for source in ("hourly", "feed"):
            for ticker in TOOL.TICKERS:
                with self.subTest(source=source, ticker=ticker):
                    series = TOOL.series_of(ticker, source)
                    self.assertGreater(len(series), 1_000)
                    # a feed can print twice in one second; never backwards
                    self.assertTrue(all(b[0] >= a[0] and b[1] > 0 for a, b in zip(series, series[1:])))
                    # no print is on another scale: nothing moves a hundredfold between two prints
                    self.assertTrue(all(0.5 < b[1] / a[1] < 2 for a, b in zip(series, series[1:])))

    def test_a_rebalance_sale_under_cost_reserves_nothing_and_carries_the_loss(self):
        r = TOOL.Rebalance(0.5, 0.01, 1.0, TOOL.Costs(), stock=100.0, avg_cost=100.0)
        self.assertTrue(r.execute(90.0, 0))
        self.assertEqual(r.buyback_stock, 0.0)
        self.assertGreater(r.loss, 0.0)


if __name__ == "__main__":
    unittest.main()
