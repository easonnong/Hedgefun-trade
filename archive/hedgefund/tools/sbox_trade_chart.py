#!/usr/bin/env python3
"""Read-only receipt report for the controlled SBOX multiwallet test (stdlib only)."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import html
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.request

CHAIN_ID = 4663
ROUTER = '0x9937bf2edf733f7f960e7fe78904045ad81d33cd'
TOKEN = '0xed9288aab3c09f8ec899ca5f10a69b7c407df831'
STOCK = '0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec'
USDG = '0x5fc5360d0400a0fd4f2af552add042d716f1d168'
MANAGER = '0x8366a39cc670b4001a1121b8f6a443a643e40951'
HOOK = '0x45783cf9f91aa3661e4d9156d9b3313e702de844'
TREASURY = '0x86b6dc8f21a5c65a9441613e8aceb2e018f01960'
BOUGHT = '0xaf6c8baebc55f540953b129965caf1e3f48010ed731c2cea5ed61e71ebc57153'
SOLD = '0x47c2f180f415c943169b11c4bd61c71dbd5f15ed83b496b3a65a47a3a21d63b4'
SWAP = '0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f'
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', value):
        raise ValueError('Invalid address in test state or receipt')
    return value.lower()


def words(data, count):
    if not isinstance(data, str) or not re.fullmatch('0x[0-9a-fA-F]{%d}' % (64 * count), data):
        raise ValueError('Malformed event data')
    return [int(data[2 + i * 64:2 + (i + 1) * 64], 16) for i in range(count)]


def topic_address(topic):
    value = words(topic, 1)[0]
    if value >= 1 << 160:
        raise ValueError('Noncanonical indexed address')
    return f'0x{value:040x}'


def signed(value, bits):
    result = value - (1 << 256) if value >> 255 else value
    if not -(1 << (bits - 1)) <= result < 1 << (bits - 1):
        raise ValueError('Noncanonical signed event field')
    return result


def stock_per_token(sqrt_price, token=TOKEN, stock=STOCK, token_decimals=18, stock_decimals=18):
    if not 0 < sqrt_price < 1 << 160:
        raise ValueError('Invalid square-root price')
    with localcontext() as context:
        context.prec = 70
        ratio = Decimal(sqrt_price) ** 2 / Decimal(1 << 192)
        price = ratio if int(address(token), 16) < int(address(stock), 16) else 1 / ratio
        return price * Decimal(10) ** (token_decimals - stock_decimals)


def net_transfer(logs, asset, wallet):
    net = 0
    for log in logs:
        topics = log.get('topics', [])
        if log.get('address', '').lower() != asset or not topics or topics[0].lower() != TRANSFER:
            continue
        if len(topics) != 3:
            raise ValueError('Malformed Transfer event')
        amount = words(log['data'], 1)[0]
        if topic_address(topics[1]) == wallet:
            net -= amount
        if topic_address(topics[2]) == wallet:
            net += amount
    return net


def decode_receipt(receipt, wallet, kind, pool_id):
    """Reject unrelated/failed receipts; preserve every matching pool Swap in log order."""
    wallet = address(wallet)
    if kind not in ('buy', 'sell') or int(receipt.get('status', '0x0'), 16) != 1:
        raise ValueError('Trade receipt is unsuccessful or has an invalid kind')
    if address(receipt['from']) != wallet or address(receipt['to']) != ROUTER:
        raise ValueError('Receipt sender/router does not match the test trade')
    logs = receipt['logs']
    expected_topic = BOUGHT if kind == 'buy' else SOLD
    events = [log for log in logs if log.get('address', '').lower() == ROUTER
              and log.get('topics') and log['topics'][0].lower() == expected_topic]
    if len(events) != 1:
        raise ValueError('Expected exactly one matching router trade event')
    event = events[0]
    if len(event['topics']) != 3 or words(event['topics'][1], 1)[0] != 0 or topic_address(event['topics'][2]) != wallet:
        raise ValueError('Router event does not match strategy 0 and the test wallet')
    event_amounts = words(event['data'], 3)
    token_delta = net_transfer(logs, TOKEN, wallet)
    quote_delta = net_transfer(logs, USDG, wallet)
    if kind == 'buy':
        valid = token_delta > 0 and quote_delta < 0 and -quote_delta == event_amounts[0] and token_delta == event_amounts[2]
    else:
        valid = token_delta < 0 and quote_delta > 0 and -token_delta <= event_amounts[0] and quote_delta == event_amounts[2]
    if not valid:
        raise ValueError('Router amounts and net wallet transfers disagree')
    with localcontext() as context:
        context.prec = 70
        effective = Decimal(abs(quote_delta)) / Decimal(abs(token_delta)) * Decimal(10) ** 12
    base = dict(block=int(receipt['blockNumber'], 16), transaction_index=int(receipt['transactionIndex'], 16),
                tx_hash=receipt['transactionHash'].lower(), wallet=wallet, kind=kind,
                net_usdg=str(Decimal(quote_delta) / 10 ** 6), net_sbox=str(Decimal(token_delta) / 10 ** 18),
                effective_usdg_per_sbox=str(effective))
    rows = []
    for log in logs:
        topics = log.get('topics', [])
        if log.get('address', '').lower() != MANAGER or len(topics) != 3 or topics[0].lower() != SWAP or topics[1].lower() != pool_id.lower():
            continue
        values = words(log['data'], 6)
        amount0, amount1 = signed(values[0], 128), signed(values[1], 128)
        sqrt_price, liquidity, tick, fee = values[2], values[3], signed(values[4], 24), values[5]
        if liquidity >= 1 << 128 or fee >= 1 << 24:
            raise ValueError('Noncanonical Swap event')
        rows.append(dict(base, log_index=int(log['logIndex'], 16), sqrt_price_x96=str(sqrt_price),
                         spot_nvda_per_sbox=str(stock_per_token(sqrt_price)), tick=tick,
                         amount0=str(amount0), amount1=str(amount1)))
    # Hook-handled trades can lack a Swap event: show execution, never invent a spot.
    if not rows:
        rows.append(dict(base, log_index=int(event['logIndex'], 16), sqrt_price_x96='',
                         spot_nvda_per_sbox='', tick='', amount0='', amount1=''))
    return sorted(rows, key=sort_key)


def sort_key(row):
    return row['block'], row['transaction_index'], row['log_index']


class RPC:
    def __init__(self, url):
        if not url.startswith(('https://', 'http://')):
            raise ValueError('RH_RPC must be an HTTP(S) URL')
        self.url = url

    def call(self, method, params):
        request = urllib.request.Request(self.url, json.dumps(dict(jsonrpc='2.0', id=1, method=method, params=params)).encode(),
                                         {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except Exception:
            raise ValueError(f'RPC request failed for {method}; endpoint omitted') from None
        if 'error' in payload or 'result' not in payload:
            raise ValueError(f'RPC returned an error for {method}; endpoint omitted')
        return payload['result']


def chart_svg(rows, field, title):
    samples = [(i, Decimal(row[field]), row) for i, row in enumerate(rows) if row.get(field)]
    if not samples:
        return f'<h2>{html.escape(title)}</h2><p>No confirmed price observations.</p>'
    low, high = min(x[1] for x in samples), max(x[1] for x in samples)
    span = high - low
    margin = span / 10 if span else (abs(high) / 100 or Decimal(1))
    low, high = low - margin, high + margin
    def xy(index, value):
        return 105 + 720 * index / max(1, len(rows) - 1), 240 - float((value - low) / (high - low)) * 200
    marks, points = [], []
    for index, value, row in samples:
        x, y = xy(index, value)
        points.append(f'{x:.3f},{y:.3f}')
        label = html.escape(f"{row['kind']} · block {row['block']} · {value} · {row['tx_hash']}")
        color = '#19745c' if row['kind'] == 'buy' else '#b75332'
        marks.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="{color}"><title>{label}</title></circle>')
    return (f'<h2>{html.escape(title)}</h2><svg viewBox="0 0 860 290" role="img" aria-label="{html.escape(title)}">'
            '<path d="M105 30V240H830" stroke="#98a5ae" fill="none"/>'
            f'<text x="2" y="45">{high:.6g}</text><text x="2" y="240">{low:.6g}</text>'
            f'<polyline points="{" ".join(points)}" fill="none" stroke="#536a86" stroke-width="2"/>'
            + ''.join(marks) + '<text x="105" y="275">Recorded test observations in chain order · green buy / orange sell</text></svg>')


def render_report(rows):
    rows = sorted(rows, key=sort_key)
    # There may be several pool swaps in a receipt; execution is one observation per trade.
    trades = list({row['tx_hash']: row for row in rows}.values())
    table = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(row.get(key, "")))}</td>' for key in
                    ('block', 'kind', 'wallet', 'net_usdg', 'net_sbox', 'effective_usdg_per_sbox', 'spot_nvda_per_sbox', 'tx_hash'))
                    + '</tr>' for row in trades)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Controlled SBOX trade test</title><style>body{font:16px system-ui;color:#233342;background:#fafaf6;max-width:1100px;margin:36px auto;padding:0 20px}h1{font-size:30px}svg{width:100%;background:white;border:1px solid #ddd;border-radius:10px}svg text{font-size:12px}table{border-collapse:collapse;font-size:12px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}td{max-width:240px;overflow-wrap:anywhere}.table{overflow:auto}.note{background:#fff0ce;padding:16px}</style>'
            '<h1>SBOX controlled wallet test</h1><p class="note">Controlled 10-wallet test, not organic market activity. '
            'Only confirmed trades from this test journal are included. Unrelated swaps between these snapshots are omitted. '
            'These lines are observations, not a complete market chart or investment performance.</p>'
            f'<p>{len(trades)} confirmed trades · chain {CHAIN_ID} · strategy 0 · {TOKEN}</p>'
            + ('<p>No confirmed test trades yet. Run the report again after trading; no price data has been fabricated.</p>' if not rows else '')
            + chart_svg(rows, 'spot_nvda_per_sbox', 'Pool spot after swap · NVDA per SBOX')
            + '<p>Pool spot comes from the V4 Swap event square-root price; no USD conversion is applied. Missing Swap events have no spot point.</p>'
            + chart_svg(trades, 'effective_usdg_per_sbox', 'Net execution price · USDG per SBOX')
            + '<p>Execution price uses actual net wallet token transfers, including the effect of trading taxes, fees and any token refund. '
            'Buy and sell prices are different quantities from the pool spot. Gas is excluded. CSV rows are swap observations: repeated trade totals must be counted only once per transaction hash.</p>'
            + '<h2>Actual receipts</h2><div class="table"><table><thead><tr><th>Block</th><th>Side</th><th>Wallet</th><th>Net USDG</th><th>Net SBOX</th><th>Execution USDG/SBOX</th><th>Last spot NVDA/SBOX</th><th>Transaction</th></tr></thead><tbody>'
            + table + '</tbody></table></div></html>')


def write_reports(rows, output_dir):
    output = Path(output_dir).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if output == repo or repo in output.parents:
        raise ValueError('Report output must be outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    fields = ['block', 'transaction_index', 'log_index', 'timestamp_utc', 'tx_hash', 'wallet', 'kind',
              'net_usdg', 'net_sbox', 'effective_usdg_per_sbox', 'spot_nvda_per_sbox', 'sqrt_price_x96', 'tick', 'amount0', 'amount1']
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(sorted(rows, key=sort_key))
    for filename, contents in [('sbox-trades.csv', buffer.getvalue()), ('sbox-trades.html', render_report(rows))]:
        path = output / filename
        if path.is_symlink():
            raise ValueError('Refusing to overwrite a symlink')
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output, delete=False) as handle:
            handle.write(contents)
            temp = handle.name
        os.replace(temp, path)
    return output / 'sbox-trades.html'


def load_trades(state_dir):
    state = Path(state_dir).expanduser().resolve()
    manifest = json.loads((state / 'wallets.json').read_text())
    if manifest.get('version') != 1:
        raise ValueError('Unsupported wallet manifest version')
    wallets = [address(item['address']) for item in manifest['wallets']]
    if len(wallets) != 10 or len(set(wallets)) != 10:
        raise ValueError('Expected ten distinct test wallets')
    journal_path = state / 'journal.json'
    if not journal_path.exists():
        return []
    journal = json.loads(journal_path.read_text())
    if journal.get('version') != 1:
        raise ValueError('Unsupported trade journal version')
    config = journal['config']
    if config.get('chain_id') != CHAIN_ID or config.get('strategy_id') != 0:
        raise ValueError('Journal is not for the pinned SBOX strategy and chain')
    for key, expected in dict(router=ROUTER, token=TOKEN, stock=STOCK, quote=USDG,
                              pool_manager=MANAGER, hook=HOOK, treasury=TREASURY).items():
        if address(config[key]) != expected:
            raise ValueError(f'Journal {key} does not match the pinned deployment')
    selected = {}
    for operation in journal['operations'].values():
        kind = operation.get('intent', {}).get('kind')
        if operation.get('status') != 'confirmed' or kind not in ('buy', 'sell'):
            continue
        wallet = address(operation['from'])
        tx_hash = operation['hash'].lower()
        if wallet not in wallets or address(operation['to']) != ROUTER:
            raise ValueError('Confirmed trade is outside the test wallet manifest/router')
        if not re.fullmatch(r'0x[0-9a-f]{64}', tx_hash):
            raise ValueError('Invalid transaction hash')
        trade = (tx_hash, wallet, kind)
        if tx_hash in selected and selected[tx_hash] != trade:
            raise ValueError('Conflicting trade journal entries')
        selected[tx_hash] = trade
    return list(selected.values())


def collect_rows(trades, rpc):
    if int(rpc.call('eth_chainId', []), 16) != CHAIN_ID:
        raise ValueError('RPC chain is not 4663')
    pool_id = rpc.call('eth_call', [dict(to=HOOK, data='0x4e46e4c9' + TREASURY[2:].zfill(64)), 'latest'])
    if words(pool_id, 1)[0] == 0:
        raise ValueError('Treasury has no registered V4 pool')
    blocks, rows = {}, []
    for tx_hash, wallet, kind in trades:
        receipt = rpc.call('eth_getTransactionReceipt', [tx_hash])
        if not receipt or receipt.get('transactionHash', '').lower() != tx_hash:
            raise ValueError('A journal trade has no matching on-chain receipt')
        number = receipt['blockNumber']
        if number not in blocks:
            blocks[number] = rpc.call('eth_getBlockByNumber', [number, False])
        block = blocks[number]
        if not block or block['hash'].lower() != receipt['blockHash'].lower():
            raise ValueError('Receipt block is no longer canonical; rerun after confirmation')
        timestamp = datetime.fromtimestamp(int(block['timestamp'], 16), timezone.utc).isoformat()
        decoded = decode_receipt(receipt, wallet, kind, pool_id)
        rows.extend(dict(row, timestamp_utc=timestamp) for row in decoded)
    return sorted(rows, key=sort_key)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path, help='External wallet state directory; no keystores are opened')
    parser.add_argument('--output-dir', type=Path, help='External report directory (default: STATE/reports)')
    args = parser.parse_args(argv)
    try:
        trades = load_trades(args.state)
        rows = collect_rows(trades, RPC(os.environ.get('RH_RPC', ''))) if trades else []
        path = write_reports(rows, args.output_dir or args.state / 'reports')
    except (ValueError, KeyError, TypeError, OSError, OverflowError):
        # Never echo local journal content, credential-bearing RPC URL, or raw HTTP errors.
        print('STOP: could not verify report inputs/receipts. Check the manifest, journal, RH_RPC and output path.', file=sys.stderr)
        return 1
    print(f'{len(trades)} confirmed test trades; report: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
