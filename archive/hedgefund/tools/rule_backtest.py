#!/usr/bin/env python3
"""What would a creator's RULE have done on a stock's own price history?

Replays `HedgeFunTreasuryBase` -- book / takeProfit / buyDip / stopLoss -- bar by bar over hourly closes, for a grid
of (tp1, dip, stop, lot), and scores each the way the contract scores itself:

    multiple = ( stock still held + stock spent on buy-backs + USDG reserve at the last price ) / stock received

1.00 is "did nothing": the treasury would have had exactly that much by sitting on the tax. Above 1.00 the rule
earned stock; below, it gave some away. The token is priced in the stock, so the stock is the only honest ruler.

Model, and where it is kind or unkind to the rule:
  - the sell tax arrives as a constant USD value per trading day (--inflow), booked at that bar's close
  - the rule is evaluated once per bar AT THE BAR'S CLOSE. A real bot fires nearer the trigger, so fills here are
    sometimes better than real (the bar ran past the trigger) and sometimes missed entirely (it touched and came back)
  - every swap loses --cost-bps (pool fee + slippage; 35 = the 0.30% tier + a little) and every call pays --bounty-bps
  - the overnight and weekend gap shows up as the jump between bars; nothing trades inside it (a band-0 treasury)
  - tp2 = 2 x tp1: half the lot at tp1, the rest at tp2, as the contract does
  - NOT modelled: the token's own market, buy-back price impact, a pinned pool, minLotUsdg

  tools/rule_backtest.py hourly.csv --tickers MSTR,GME,CRCL --out out/rule
  (csv: first column a timestamp, one column of prices per ticker; e.g. from yfinance, interval=1h)

READ THE REVERSED RUN. Three years in which every ticker here rose 2x-37x measure the trend, not the rule. `--reverse`
replays each path backwards -- same volatility, opposite drift -- and a rule is only worth launching if it survives both.
"""
import argparse, csv, itertools, math, os, sys

def load(path, tickers):
    rows = list(csv.reader(open(path))); hdr = rows[0][1:]
    cols = {t: hdr.index(t) + 1 for t in (tickers or hdr)}
    out = {t: [] for t in cols}
    for r in rows[1:]:
        for t, i in cols.items():
            if i < len(r) and r[i] not in ('', 'nan'): out[t].append((r[0], float(r[i])))
    return out

class Ledger:
    """The treasury's books, and the rule applied to them one bar at a time. `replay` below drives it over a price
    history; `lab/trend.py` drives the same object over synthetic paths with V2's inflows, so the two cannot disagree
    about what the rule does. All bps arguments are fractions. A lot is `[qty, cost, half]`."""
    def __init__(self):
        self.lots = []; self.reserve = self.buyback = self.received = self.last_sale = 0.0
        self.n_tp = self.n_dip = self.n_stop = 0

    def book(self, qty, p):
        """a lot at price `p`; the first one is also where a dip is first measured from, as in the contract"""
        self.lots.append([qty, p, False]); self.received += qty
        if not self.last_sale: self.last_sale = p

    def held(self): return sum(L[0] for L in self.lots)

    def value(self, p):
        """stock held + stock set aside for buy-backs + the reserve at `p`: the contract's own scorecard numerator"""
        return self.held() + self.buyback + self.reserve / p

    def step(self, p, tp1, dip, stop, lot, cost, bounty, min_lot=0.0, max_lots=None):
        """one bar at price `p`: every due stop, then every due take-profit, then at most one dip. `min_lot` is the
        contract's `minLotUsdg`: a dip whose spend is under it is not due (0 = not modelled, the historical default);
        `max_lots` is V2's `MAX_STRATEGY_LOTS`, at which a dip buy pauses (None = unlimited, as V1)."""
        lots = self.lots
        # stopLoss first: it is the one that cannot wait
        if stop:
            for L in lots:
                if L[0] and p <= L[1] * (1 - stop):
                    self.reserve += L[0] * p * (1 - cost) * (1 - bounty); L[0] = 0.0; self.last_sale = p; self.n_stop += 1
        for L in lots:
            if not L[0]: continue
            if not L[2]:
                if p < L[1] * (1 + tp1): continue
                q = L[0] / 2; L[2] = True
            else:
                if p < L[1] * (1 + 2 * tp1): continue
                q = L[0]
            principal = q * L[1] / p                                  # sold for USDG: the next dip's ammunition
            self.reserve += principal * p * (1 - cost)
            self.buyback += (q - principal) * (1 - bounty)            # the profit stays stock, and buys the token back
            L[0] -= q; self.last_sale = p; self.n_tp += 1
        self.lots = lots = [L for L in lots if L[0] > 0]
        if self.last_sale and p <= self.last_sale * (1 - dip) and self.reserve * lot > 1e-9:
            spend = self.reserve * lot
            if spend >= min_lot and (max_lots is None or len(lots) < max_lots):
                self.reserve -= spend
                got = spend * (1 - bounty) * (1 - cost) / p
                lots.append([got, spend * (1 - bounty) / got, False]); self.last_sale = p; self.n_dip += 1

def replay(series, tp1, dip, stop, lot, cost, bounty, inflow):
    """returns dict of the scorecard. All bps args are fractions here."""
    L = Ledger(); worst = 1.0; day = None
    for ts, p in series:
        d = ts[:10]
        if d != day: day = d; L.book(inflow / p, p)                   # one booking per trading day
        L.step(p, tp1, dip, stop, lot, cost, bounty)
        if L.received: worst = min(worst, L.value(p) / L.received)
    p = series[-1][1]
    return dict(multiple=L.value(p) / L.received, worst=worst, burned_share=L.buyback / L.received,
                cash_share=(L.reserve / p) / L.received, n_tp=L.n_tp, n_dip=L.n_dip, n_stop=L.n_stop)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('prices'); ap.add_argument('--tickers', default=''); ap.add_argument('--out', default='rule_backtest')
    ap.add_argument('--tp1', default='3,5,10,20,40'); ap.add_argument('--dip', default='3,5,10,20,40')
    ap.add_argument('--stop', default='0,15'); ap.add_argument('--lot', default='20,50')
    ap.add_argument('--cost-bps', type=float, default=35); ap.add_argument('--bounty-bps', type=float, default=50)
    ap.add_argument('--inflow', type=float, default=100.0); ap.add_argument('--reverse', action='store_true')
    a = ap.parse_args()
    data = load(a.prices, [t for t in a.tickers.split(',') if t])
    grid = list(itertools.product(*[[float(x) / 100 for x in s.split(',')] for s in (a.tp1, a.dip, a.stop, a.lot)]))
    out = []
    for t, s in data.items():
        if a.reverse: s = [(s[i][0], s[len(s) - 1 - i][1]) for i in range(len(s))]     # same dates, the path backwards
        r = [math.log(s[i][1] / s[i - 1][1]) for i in range(1, len(s))]
        vol = (sum(x * x for x in r) / len(r)) ** .5 * (7 * 252) ** .5
        for tp1, dip, stop, lot in grid:
            out.append(dict(ticker=t, ann_vol=round(vol, 2), path_x=round(s[-1][1] / s[0][1], 2), tp1=tp1, dip=dip, stop=stop, lot=lot,
                            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in replay(s, tp1, dip, stop, lot, a.cost_bps / 1e4, a.bounty_bps / 1e4, a.inflow).items()}))
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out + '.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print('wrote', a.out + '.csv', len(out), 'rows')

if __name__ == '__main__': main()
