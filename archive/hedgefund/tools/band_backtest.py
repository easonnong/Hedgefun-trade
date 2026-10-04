#!/usr/bin/env python3
"""What would each `bandBpsPerHour` have done on this pool's own history?

A strategy's V3 treasury prices itself by `HedgeFunTreasury.health()`: Chainlink, pulled by the pool's 600-second
mean inside   band = maxDeviationBps + bandBpsPerHour * feedAgeHours   (capped at 3000 bps) -- on scheduled closures
only; while the market is open it is Chainlink or nothing. The creator picks
`bandBpsPerHour` once, forever. This replays that function over archive state so a buyer can see the trade-off
before buying: how often the rule could act, and how far the pool was allowed to move its price.

  sample   read pool + feeds from an ARCHIVE rpc into a json (the public rpc serves ~83 minutes of history)
             RH_RPC=<archive url> tools/band_backtest.py sample --pool 0x.. --feed 0x.. --days 12 --step 300 out.json
             (or --env-file path/to/.env holding RH_RPC=...; the url is never printed)
  report   replay health() for each band over a sample file; writes <out>.csv and <out>.png
             tools/band_backtest.py report out.json --bands 0,10,25,50,100,200 --label CRCL/USDG

What the chart does NOT show, because history cannot: a pinned pool. After a real gap, whoever holds the pool for
one TWAP window picks the price anywhere inside the band (AUDIT.md TR-1). "worst-case pull" below is that bound --
`bandBpsPerHour * age` -- and it is the number to weigh against pool depth, not the realised one.
"""
import argparse, csv, datetime, json, os, sys, time, urllib.request

USDG = '0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168'
USDG_FEED = '0x61B7e5650328764B076A108EFF5fa7282a1B9aD2'
SEL = dict(slot0='0x3850c7bd', token0='0x0dfe1681', latestRoundData='0xfeaf968c', decimals='0x313ce567')
MAX_BAND_BPS = 3000
# NYSE full-day closures. TradingCalendar.sol computes these by rule; a replay only needs the ones in its window.
HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26',
            '2026-12-25', '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06',
            '2027-11-25', '2027-12-24'}

# ---------------------------------------------------------------------------------------------- rpc
def _url(env_file):
    u = os.environ.get('RH_RPC')
    if not u and env_file:
        for line in open(env_file):
            if line.startswith('RH_RPC='):
                u = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not u: sys.exit('set RH_RPC or pass --env-file')
    return u

class Rpc:
    def __init__(self, url): self.url, self.n = url, 0
    def _post(self, payload, timeout):
        for attempt in range(5):
            try:
                r = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'band-backtest/1'})   # some archive endpoints refuse urllib's default agent
                with urllib.request.urlopen(r, timeout=timeout) as f: return json.load(f)
            except Exception:
                if attempt == 4: raise RuntimeError('rpc failed after 5 attempts') from None   # never echo the url
                time.sleep(1.5 * (attempt + 1))
    def call(self, m, p):
        self.n += 1
        d = self._post({'jsonrpc': '2.0', 'id': self.n, 'method': m, 'params': p}, 40)
        if 'error' in d: raise RuntimeError(d['error'])
        return d['result']
    def batch(self, reqs):
        pl = []
        for m, p in reqs:
            self.n += 1; pl.append({'jsonrpc': '2.0', 'id': self.n, 'method': m, 'params': p})
        return sorted(self._post(pl, 90), key=lambda x: x['id'])

def h2i(x, signed=False, bits=256):
    v = int(x, 16)
    return v - (1 << bits) if signed and v >= 1 << (bits - 1) else v
def words(h): return [h[2:][i:i + 64] for i in range(0, len(h) - 2, 64)]
def observe_data(secs): return '0x883bdbfd' + '%064x' % 32 + '%064x' % len(secs) + ''.join('%064x' % s for s in secs)

def price_at_sqrt(sqrtP, stock_is_token0, scale):
    """PoolTrader._priceAtSqrt, integer for integer. USDG is token1 in 9 of the listed pools; assume an ordering
    and the pool reads as zero with no error."""
    raw = (sqrtP * sqrtP) >> 96
    if raw == 0: return 0
    return (raw * scale) >> 96 if stock_is_token0 else (scale << 96) // raw

def mean_tick(delta, w=600):
    return delta // w                       # python floors, as PoolTrader._meanTick does

# ---------------------------------------------------------------------------------------------- calendar
def _et(ts):
    d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).replace(tzinfo=None)
    def nth_sun(y, m, n):
        x = datetime.datetime(y, m, 1)
        return x + datetime.timedelta(days=(6 - x.weekday()) % 7 + 7 * (n - 1))
    dst = nth_sun(d.year, 3, 2) + datetime.timedelta(hours=7) <= d < nth_sun(d.year, 11, 1) + datetime.timedelta(hours=6)
    return d - datetime.timedelta(hours=4 if dst else 5)

def regime(ts):
    """'weekend' = TradingCalendar.isClosed (session rolls 20:00 ET; weekends and the HOLIDAYS above),
    'cash' = 09:30-16:00 ET on a trading day, 'overnight' = everything else the 24/5 calendar calls open."""
    l = _et(ts); day = l.date() + datetime.timedelta(days=1 if l.hour >= 20 else 0)
    if day.weekday() >= 5 or day.isoformat() in HOLIDAYS: return 'weekend'
    mins = l.hour * 60 + l.minute
    return 'cash' if l.date() == day and 570 <= mins < 960 else 'overnight'

# ---------------------------------------------------------------------------------------------- sample
def sample(a):
    rpc = Rpc(_url(a.env_file))
    head = rpc.call('eth_getBlockByNumber', ['latest', False]); HN, HT = int(head['number'], 16), int(head['timestamp'], 16)
    stock_is_token0 = ('0x' + rpc.call('eth_call', [{'to': a.pool, 'data': SEL['token0']}, 'latest'])[-40:]).lower() != USDG.lower()
    sdec = h2i(rpc.call('eth_call', [{'to': a.feed, 'data': SEL['decimals']}, 'latest']))
    udec = h2i(rpc.call('eth_call', [{'to': USDG_FEED, 'data': SEL['decimals']}, 'latest']))
    scale = 10**18 * 10**a.stock_decimals // 10**6
    cache = {}
    def block_at(ts):
        est = HN - int((HT - ts) * 10)                       # ~0.1 s blocks
        for _ in range(8):
            est = max(1, min(est, HN))
            if est not in cache: cache[est] = int(rpc.call('eth_getBlockByNumber', [hex(est), False])['timestamp'], 16)
            t = cache[est]
            if abs(t - ts) <= 1: break
            est += int((ts - t) * 10)
        return est, t
    targets = list(range(HT - int(a.days * 86400), HT - 5, a.step)); rows = []
    for i in range(0, len(targets), 25):
        blocks = [block_at(t) for t in targets[i:i + 25]]; reqs = []
        for bn, _ in blocks:
            h = hex(bn)
            reqs += [('eth_call', [{'to': a.pool, 'data': SEL['slot0']}, h]), ('eth_call', [{'to': a.feed, 'data': SEL['latestRoundData']}, h]),
                     ('eth_call', [{'to': USDG_FEED, 'data': SEL['latestRoundData']}, h]), ('eth_call', [{'to': a.pool, 'data': observe_data([600, 0])}, h])]
        res = rpc.batch(reqs)
        for j, (bn, bt) in enumerate(blocks):
            r = res[4 * j:4 * j + 4]
            if any('error' in x for x in r[:3]): continue
            s0 = words(r[0]['result']); fw = words(r[1]['result']); uw = words(r[2]['result'])
            sqrtP, tick = int(s0[0], 16), h2i(s0[1], True)
            s, u = h2i(fw[1], True), h2i(uw[1], True)
            if s <= 0 or u <= 0: continue
            feed = s * 10**18 * 10**udec // (u * 10**sdec)       # PriceOracle: stock/usd over usdg/usd, 1e18
            mt = None
            if 'error' not in r[3]:
                tw = words(r[3]['result']); mt = mean_tick(h2i(tw[4], True) - h2i(tw[3], True))
            rows.append(dict(ts=bt, block=bn, tick=tick, mean_tick=mt, feed=feed / 1e18, spot=price_at_sqrt(sqrtP, stock_is_token0, scale) / 1e18,
                             stock_is_token0=stock_is_token0, feed_age=bt - h2i(fw[3]), usdg_age=bt - h2i(uw[3])))
        print('%d/%d' % (min(i + 25, len(targets)), len(targets)), file=sys.stderr)
    json.dump(rows, open(a.out, 'w')); print('wrote', len(rows), 'rows to', a.out)

# ---------------------------------------------------------------------------------------------- replay
def health(row, k, dev_bps, max_stock_age, max_usdg_age):
    """HedgeFunTreasury._priced, in floats. Returns (ok, pull_bps): the signed distance the served price sits from
    the feed."""
    feed, spot, age = row['feed'], row['spot'], row['feed_age']
    shut = regime(row['ts']) == 'weekend'
    if row.get('mean_tick') is not None: drift = abs(row['tick'] - row['mean_tick'])
    else: return False, 0.0                                                     # ring could not serve the window
    # the mean as a price: spot moved back by the tick drift. Sign of a tick depends on the token ordering.
    signed = row['tick'] - row['mean_tick']
    if not row.get('stock_is_token0', False): signed = -signed
    mean = spot / (1.0001 ** signed)
    if row['usdg_age'] > max_usdg_age: return False, 0.0
    # PoolTrader._health first, whatever the band: a band only ever adds to when the rule may act
    if not shut and age <= max_stock_age and abs(spot - feed) * 1e4 <= feed * dev_bps and drift <= dev_bps: return True, 0.0
    if k == 0: return False, 0.0
    if not shut: return False, 0.0                                              # the band exists only on a scheduled closure
    if abs(spot - mean) * 1e4 > mean * dev_bps: return False, 0.0
    band = min(dev_bps + k * age / 3600.0, MAX_BAND_BPS)
    dev = (mean - feed) / feed * 1e4
    if abs(dev) > band: return False, 0.0
    if abs(dev) <= dev_bps: return True, 0.0
    return True, (abs(dev) - dev_bps) * (1 if dev > 0 else -1)

def pct(xs, q):
    if not xs: return 0.0
    xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))]

def report(a):
    rows = json.load(open(a.samples)); bands = [int(x) for x in a.bands.split(',')]
    regs = ['cash', 'overnight', 'weekend']
    n = {g: sum(1 for r in rows if regime(r['ts']) == g) for g in regs}
    out = []
    for k in bands:
        rec = dict(bandBpsPerHour=k)
        pulls, caps = [], []
        okc = {g: 0 for g in regs}
        for r in rows:
            ok, pull = health(r, k, a.max_deviation_bps, a.max_stock_age, a.max_usdg_age)
            if ok:
                okc[regime(r['ts'])] += 1; pulls.append(abs(pull))
                caps.append(min(k * r['feed_age'] / 3600.0, MAX_BAND_BPS - a.max_deviation_bps))
        for g in regs: rec['open_%s_pct' % g] = round(100.0 * okc[g] / n[g], 1) if n[g] else 0.0
        rec['open_all_pct'] = round(100.0 * sum(okc.values()) / len(rows), 1)
        rec['pull_p50_bps'] = round(pct(pulls, .5), 1); rec['pull_p99_bps'] = round(pct(pulls, .99), 1); rec['pull_max_bps'] = round(max(pulls or [0]), 1)
        rec['worstcase_pull_p50_bps'] = round(pct(caps, .5), 1); rec['worstcase_pull_p99_bps'] = round(pct(caps, .99), 1)
        rec['worstcase_fill_vs_feed_p99_bps'] = round(rec['worstcase_pull_p99_bps'] + a.max_slippage_bps, 1)
        out.append(rec)
    base = os.path.splitext(a.out or a.samples)[0]
    with open(base + '.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    days = (rows[-1]['ts'] - rows[0]['ts']) / 86400.0
    print('%s: %d samples over %.1f days  (cash %d / overnight %d / weekend %d)' % (a.label, len(rows), days, n['cash'], n['overnight'], n['weekend']))
    hdr = list(out[0].keys()); print(' | '.join(hdr))
    for rec in out: print(' | '.join(str(rec[h]) for h in hdr))
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib not installed: wrote the csv only'); return
    fig, ax = plt.subplots(3, 1, figsize=(11, 12), gridspec_kw=dict(height_ratios=[1.1, 1, 1]))
    # 1. the history itself, with one band drawn over it
    t = [datetime.datetime.fromtimestamp(r['ts'], datetime.timezone.utc) for r in rows]
    basis = [(r['spot'] - r['feed']) / r['feed'] * 1e4 for r in rows]
    kk = a.draw_band if a.draw_band is not None else bands[len(bands) // 2]
    env = [min(a.max_deviation_bps + kk * r['feed_age'] / 3600.0, MAX_BAND_BPS) for r in rows]
    ax[0].fill_between(t, [-e for e in env], env, color='#2b6cb0', alpha=.15, label='band at %d bps/h' % kk, step='mid')
    ax[0].axhspan(-a.max_deviation_bps, a.max_deviation_bps, color='#2f855a', alpha=.18, label='agreement zone (price = Chainlink)')
    ax[0].plot(t, basis, color='#1a202c', lw=.7, label='pool vs Chainlink, bps')
    lim = max(60, min(max(abs(b) for b in basis) * 1.15, 700)); ax[0].set_ylim(-lim, lim)
    s = t[0]
    for i in range(1, len(rows)):
        if regime(rows[i]['ts']) == 'weekend' and regime(rows[i - 1]['ts']) != 'weekend': s = t[i]
        if regime(rows[i]['ts']) != 'weekend' and regime(rows[i - 1]['ts']) == 'weekend': ax[0].axvspan(s, t[i], color='#a0aec0', alpha=.25, lw=0)
    ax[0].set_title('%s  -  where the pool sat against a feed that goes quiet (grey = market shut)' % a.label); ax[0].set_ylabel('bps'); ax[0].legend(loc='upper left', fontsize=8)
    # 2. availability
    wd = .8 / len(bands)
    for i, rec in enumerate(out):
        ax[1].bar([x + i * wd for x in range(3)], [rec['open_%s_pct' % g] for g in regs], wd, label='%d bps/h' % rec['bandBpsPerHour'])
    ax[1].set_xticks([x + .4 - wd / 2 for x in range(3)]); ax[1].set_xticklabels(['cash session', 'overnight (calendar "open")', 'weekend / holiday'])
    ax[1].set_ylabel('% of time the rule could act'); ax[1].set_ylim(0, 105); ax[1].legend(ncol=len(bands), fontsize=8, loc='upper center'); ax[1].set_title('what a wider band buys')
    # 3. what it costs
    x = range(len(out))
    ax[2].bar([i - .2 for i in x], [r['pull_p99_bps'] for r in out], .4, color='#2b6cb0', label='realised pull off Chainlink, p99 (this history, nobody pinning)')
    ax[2].bar([i + .2 for i in x], [r['worstcase_pull_p99_bps'] for r in out], .4, color='#c53030', label='worst case a pinned pool could pull, p99  (= bps/h x feed age)')
    ax[2].set_xticks(list(x)); ax[2].set_xticklabels(['%d bps/h' % r['bandBpsPerHour'] for r in out]); ax[2].set_ylabel('bps'); ax[2].legend(fontsize=8, loc='upper left')
    ax[2].set_title('what it costs: how far the pool may move the rule\'s price  (every fill is a further %d bps slippage at most)' % a.max_slippage_bps)
    fig.tight_layout(); fig.savefig(base + '.png', dpi=130); print('wrote', base + '.csv', 'and', base + '.png')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sample'); s.add_argument('out'); s.add_argument('--pool', required=True); s.add_argument('--feed', required=True)
    s.add_argument('--days', type=float, default=12); s.add_argument('--step', type=int, default=300); s.add_argument('--stock-decimals', type=int, default=18)
    s.add_argument('--env-file'); s.set_defaults(fn=sample)
    r = sub.add_parser('report'); r.add_argument('samples'); r.add_argument('--bands', default='0,10,25,50,100,200'); r.add_argument('--label', default='pool')
    r.add_argument('--max-deviation-bps', type=float, default=50); r.add_argument('--max-slippage-bps', type=float, default=100)
    r.add_argument('--max-stock-age', type=int, default=26 * 3600); r.add_argument('--max-usdg-age', type=int, default=26 * 3600)
    r.add_argument('--draw-band', type=int); r.add_argument('--out'); r.set_defaults(fn=report)
    a = ap.parse_args(); a.fn(a)
