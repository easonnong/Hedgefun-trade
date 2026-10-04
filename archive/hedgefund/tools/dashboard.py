#!/usr/bin/env python3
"""A read-only page for a deployed launchpad: what each treasury holds, what it has done, and how it is doing.

  FACTORY=0x... tools/dashboard.py out.html            # one snapshot
  FACTORY=0x... tools/dashboard.py out.html --every 60  # rewrite it every minute; open the file in a browser

Reads the chain with eth_call and eth_getLogs only. It holds no key and sends nothing. RPC defaults to the chain's
public endpoint; set RH_RPC for an archive node if the event log should reach further back than the public one serves.

The score is (stock held + stock spent on buy-backs + the reserve THE RULE EARNED, at the rule's price) / stock received,
shown as a percentage against doing nothing: +0.00% is "sat on the tax", +2.78% means the rule has earned 2.78% more
stock than that, negative means it gave some away. It is computed from the treasury's events, not its USDG balance, because
anyone can donate USDG to a treasury and the on-chain `stockEquivalentHeld()` would count it. It is NOT a per-token value -- nothing here is redeemable -- and
the page does not show one.
"""
import html, json, os, subprocess, sys, time, urllib.request

RPC = os.environ.get('RH_RPC') or 'https://rpc.mainnet.chain.robinhood.com'
_sel, _id = {}, [0]

def sel(sig):
    if sig not in _sel: _sel[sig] = subprocess.check_output(['cast', 'sig', sig]).decode().strip()
    return _sel[sig]
def topic(sig): 
    k = 'E:' + sig
    if k not in _sel: _sel[k] = subprocess.check_output(['cast', 'keccak', sig]).decode().strip()
    return _sel[k]

def rpc(method, params):
    _id[0] += 1
    req = urllib.request.Request(RPC, data=json.dumps({'jsonrpc': '2.0', 'id': _id[0], 'method': method, 'params': params}).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=40) as f: d = json.load(f)
    except Exception: return None                                    # never echo the url: it may carry a key
    return d.get('result')

def call(to, sig, *args):
    data = sel(sig) + ''.join(('%064x' % a) if isinstance(a, int) else a[2:].rjust(64, '0') for a in args)
    r = rpc('eth_call', [{'to': to, 'data': data}, 'latest'])
    return [r[2:][i:i + 64] for i in range(0, len(r) - 2, 64)] if r and r != '0x' else None
u = lambda w: int(w, 16)
addr = lambda w: '0x' + w[24:]
def string(words):
    try: b = bytes.fromhex(''.join(words)); n = int.from_bytes(b[32:64], 'big'); return b[64:64 + n].decode(errors='replace')
    except Exception: return '?'

EVENTS = {'LotBooked(uint256,uint256,uint256,bool)': 'book', 'ProfitTaken(uint256,uint256,uint256,uint256,uint256)': 'takeProfit',
          'Stopped(uint256,uint256,uint256)': 'stopLoss', 'Buyback(uint256,uint256)': 'buyback', 'Swept(bytes32,uint256,uint256,uint256,uint256)': 'sweep'}

def strategy(f, i, head):
    w = call(f, 'strategies(uint256)', i); tok, tr, hk, stock = addr(w[0]), addr(w[1]), addr(w[2]), addr(w[3])
    s = dict(id=i, token=tok, treasury=tr, hook=hk, symbol=string(call(tok, 'symbol()')), stockSym=string(call(stock, 'symbol()')))
    s['supply'] = u(call(tok, 'totalSupply()')[0]) / 1e18
    h = call(tr, 'health()'); s['healthy'], s['price'] = bool(u(h[0])), u(h[1]) / 1e18
    for k, sig in dict(booked='bookedStock()', buyback='buybackStock()', received='totalStockReceived()', spent='totalStockSpentOnBuybacks()', unbooked='unbookedStock()').items():
        s[k] = u(call(tr, sig)[0]) / 1e18
    s['reserve'] = u(call(tr, 'reserveUsdg()')[0]) / 1e6; s['lastSale'] = u(call(tr, 'lastSalePrice()')[0]) / 1e18
    pid = '0x' + call(hk, 'poolOfTreasury(address)', tr)[0]                       # ONE hook serves every strategy: everything on it is by pool id
    s['poolId'] = pid
    s['sellRate'] = u(call(hk, 'sellRateBps(bytes32)', pid)[0]) / 100
    m = call(stock, 'uiMultiplier()'); s['mult'] = (u(m[0]) / 1e18) if m else 1.0   # shares = raw amount x multiplier
    info = call(tok, 'description()'); s['desc'] = string(info) if info else ''
    s['locked'] = bool(u(call(tok, 'locked()')[0])); s['updatedAt'] = u(call(tok, 'updatedAt()')[0])
    s['lots'] = []
    for j in range(u(call(tr, 'lotCount()')[0])):
        L = call(tr, 'lots(uint256)', j); s['lots'].append(dict(qty=u(L[0]) / 1e18, cost=u(L[1]) / 1e18, half=bool(u(L[2]))))
    p = s['price'] or s['lastSale']
    # THE SCORE IS COMPUTED FROM EVENTS, NOT FROM THE USDG BALANCE. Anyone can send USDG to any treasury (and a launch
    # may seed some), and `stockEquivalentHeld()` counts the whole balance -- so a score read off the balance can be
    # bought with a donation. What the RULE earned is: USDG its take-profits and stops brought in, less what its dip
    # buys spent (bounties included). Anything in the balance beyond that is seed / donation: shown, never scored.
    # It needs the treasury's whole history, so an RPC that cannot serve it gets no score rather than a wrong one.
    # (Donated STOCK cannot be told from tax stock on chain -- both are `LotBooked(fromTax = true)`.)
    hist = rpc('eth_getLogs', [{'address': tr, 'fromBlock': '0x0', 'toBlock': 'latest'}])
    s['multiple'] = None; s['external'] = None
    if hist is not None:
        tp, st, lb = topic('ProfitTaken(uint256,uint256,uint256,uint256,uint256)'), topic('Stopped(uint256,uint256,uint256)'), topic('LotBooked(uint256,uint256,uint256,bool)')
        earned = spent_on_dips = 0.0
        for l in hist:
            d = [u(l['data'][2:][k:k + 64]) for k in range(0, len(l['data']) - 2, 64)]
            if l['topics'][0] == tp: earned += d[3] / 1e6
            elif l['topics'][0] == st: earned += d[0] * d[2] / 1e36 * 0.995                 # qty x price, less the stop's bounty; an upper bound (slippage)
            elif l['topics'][0] == lb and d[2] == 0: spent_on_dips += d[0] * d[1] / 1e36 * 1.005   # a dip buy: qty x cost, plus its bounty
        ruled = max(0.0, min(s['reserve'], earned - spent_on_dips))
        s['external'] = max(0.0, s['reserve'] - ruled)
        if s['received'] and p: s['multiple'] = (s['booked'] + s['buyback'] + s['spent'] + ruled / p) / s['received']
    s['events'] = []
    day = 864000                                                   # ~0.1 s blocks
    def _logs(frm):                                                 # the treasury's own events, plus the shared hook's events FOR THIS POOL
        a = rpc('eth_getLogs', [{'address': tr, 'fromBlock': hex(frm), 'toBlock': 'latest'}])
        b = rpc('eth_getLogs', [{'address': hk, 'fromBlock': hex(frm), 'toBlock': 'latest', 'topics': [None, pid]}])
        return None if a is None or b is None else sorted(a + b, key=lambda l: (u(l['blockNumber'][2:].rjust(64, '0')), u(l['logIndex'][2:].rjust(64, '0'))))
    logs = _logs(max(0, head - day))
    s['windowH'] = 24.0
    if logs is None:                                               # the public RPC refuses a range that long
        logs = _logs(max(0, head - 14000)) or []
        s['windowH'] = 14000 / 36000.0
    taxed = topic('Taxed(bytes32,bool,bool,uint256,uint256,uint256)'); s['taxStock'] = 0.0
    for l in logs:
        if l['topics'][0] == taxed and u(l['topics'][2]) == 1:     # a SELL: the tax is in the stock. data = inToken, moved, tax, rate
            s['taxStock'] += u(l['data'][2:][128:192]) / 1e18
    names = {topic(k): v for k, v in EVENTS.items()}
    for l in logs[-40:]:
        n = names.get(l['topics'][0])
        if n: s['events'].append((u(l['blockNumber'][2:].rjust(64, '0')), n, l['transactionHash'], [u(x) for x in [l['data'][2:][k:k + 64] for k in range(0, len(l['data']) - 2, 64)]]))
    return s

def fmt_event(n, d, stockSym):
    if n == 'book': return 'booked %.4f %s at %.2f' % (d[0] / 1e18, stockSym, d[1] / 1e18)
    if n == 'takeProfit': return 'sold %.4f at %.2f (cost %.2f): +%.2f USDG to reserve, %.4f %s kept for buy-back' % (d[0] / 1e18, d[2] / 1e18, d[1] / 1e18, d[3] / 1e6, d[4] / 1e18, stockSym)
    if n == 'stopLoss': return 'stopped %.4f at %.2f (cost %.2f)' % (d[0] / 1e18, d[2] / 1e18, d[1] / 1e18)
    if n == 'buyback': return 'spent %.4f %s, burned %.0f tokens' % (d[0] / 1e18, stockSym, d[1] / 1e18)
    return 'burned %.0f tokens; %.5f %s to treasury, %.5f protocol, %.5f creator' % (d[0] / 1e18, d[1] / 1e18, stockSym, d[2] / 1e18, d[3] / 1e18)   # Swept: the pool id is a topic, not data

def page(f):
    head = u(rpc('eth_blockNumber', [])[2:].rjust(64, '0')); n = u(call(f, 'strategyCount()')[0])
    S = [strategy(f, i, head) for i in range(n)]; e = html.escape
    o = ['<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=60><title>Launchpad test run</title><style>body{font:14px/1.5 -apple-system,system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#131820;background:#f6f7f9}'
         'h2{margin:28px 0 6px}table{border-collapse:collapse;width:100%;background:#fff}td,th{padding:6px 10px;border-bottom:1px solid #dce2ea;text-align:right}td:first-child,th:first-child{text-align:left}'
         '.k{color:#7a8698;font-size:12px}.ok{color:#0d857c}.no{color:#a8262c}code{font:12px ui-monospace,Menlo,monospace}.card{background:#fff;border:1px solid #dce2ea;border-radius:10px;padding:14px 16px;margin:10px 0;overflow-x:auto}</style>',
         '<h1>Launchpad test run</h1><p class=k>factory <code>%s</code> · block %d · %s UTC · read-only, refreshes every minute · nothing here is redeemable, so no per-token value is shown</p>' % (e(f), head, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())),
         '<div class=card><table><tr><th>token<th>treasury holds (shares)<th>worth, USDG<th>burned<th>bought back (all time)<th>sell tax, last %s<th>gate<th>sell tax rate</tr>' % ('24h' if S and S[0]['windowH'] >= 24 else '%.0f min' % (S[0]['windowH'] * 60 if S else 0))]
    for s in S:
        held = s['booked'] + s['buyback'] + s['unbooked']; p = s['price'] or s['lastSale']
        o.append('<tr><td><b>%s</b><td>%.4f %s<td>%.2f<td>%.3f%%<td>%.4f %s<td>%.5f %s<td class=%s>%s<td>%.1f%%</tr>' % (
            e(s['symbol']), held * s['mult'], e(s['stockSym']), held * p + s['reserve'], 100 * (1 - s['supply'] / 1e9), s['spent'], e(s['stockSym']),
            s['taxStock'], e(s['stockSym']), 'ok' if s['healthy'] else 'no', 'open' if s['healthy'] else 'shut', s['sellRate']))
    o.append('</table></div>')
    for s in S:
        o.append('<h2>%s</h2><p class=k>token <code>%s</code> · treasury <code>%s</code> · hook <code>%s</code></p>' % (e(s['symbol']), s['token'], s['treasury'], s['hook']))
        o.append('<p class=k>page: %s%s</p>' % (e(s['desc'][:200]) or '<i>empty</i>', ' · locked' if s['locked'] else ''))
        o.append('<p class=k>%s price %.2f · USDG reserve %.2f%s · waiting to be booked at the next open %.5f · dip reference %.2f · received all time %.5f · rule vs simply holding the tax: <b class=%s>%s</b></p>' % (
            e(s['stockSym']), s['price'], s['reserve'], (' (of which %.2f seeded or donated, not scored)' % s['external']) if s['external'] else '', s['unbooked'], s['lastSale'], s['received'], 'k' if not s['multiple'] else ('ok' if s['multiple'] >= 1 else 'no'),
            ('%+.2f%%' % ((s['multiple'] - 1) * 100)) if s['multiple'] else ('needs an archive RPC' if s['external'] is None else '—')))
        o.append('<div class=card><b>Lots</b> (open positions)<table><tr><th>#<th>qty<th>cost<th>now<th>unrealised<th>tp1 taken</tr>')
        for j, L in enumerate(s['lots']):
            pnl = (s['price'] / L['cost'] - 1) * 100 if s['price'] and L['cost'] else 0
            o.append('<tr><td>%d<td>%.5f<td>%.2f<td>%.2f<td class=%s>%+.2f%%<td>%s</tr>' % (j, L['qty'], L['cost'], s['price'], 'ok' if pnl >= 0 else 'no', pnl, 'yes' if L['half'] else ''))
        if not s['lots']: o.append('<tr><td colspan=6 class=k>none yet</td></tr>')
        o.append('</table></div><div class=card><b>Operations</b> (as far back as the RPC serves; set RH_RPC to an archive node for a full day)<table><tr><th>block<th>what<th style="text-align:left">detail<th>tx</tr>')
        for b, n_, tx, d in reversed(s['events']):
            o.append('<tr><td>%d<td>%s<td style="text-align:left">%s<td><code>%s…</code></tr>' % (b, n_, e(fmt_event(n_, d, s['stockSym'])), tx[:12]))
        if not s['events']: o.append('<tr><td colspan=4 class=k>nothing in the window</td></tr>')
        o.append('</table></div>')
    return '\n'.join(o)

if __name__ == '__main__':
    f = os.environ.get('FACTORY') or sys.exit('set FACTORY=0x...')
    out = sys.argv[1] if len(sys.argv) > 1 else 'dashboard.html'
    every = int(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 0
    while True:
        open(out, 'w').write(page(f)); print('wrote', out, time.strftime('%H:%M:%S'))
        if not every: break
        time.sleep(every)
