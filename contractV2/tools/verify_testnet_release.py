#!/usr/bin/env python3
"""Verify a testnet release core and promote its candidate address book, with read-only RPC.

The release is six broadcasts by the deployer, in order: DeployV2ReleaseTestnet (40), RegisterV2TradablePercent (5),
RegisterV2PercentBuyback (3), RegisterV2UpgradeableCycle (3), SetV2KeeperReward (1), CalibrateV2Listings (16).
Every transaction is checked against its canonical receipt, the live state is read back at one pinned block and
compared with the build of the recorded commit, and only then is `deploy/testnet-v2-release.json` written. Nothing
here signs or sends. Needs Foundry `cast` and a build of the recorded commit in `out/`.

  python3 tools/verify_testnet_release.py            # reads the candidate and the six run-latest.json logs
"""
import argparse
import datetime
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOYER = '0x36437b878415eda1a24186cf79afffbc9eced298'
VENUE_OWNER = '0x75cee941b0ef3a83fea0397bbf903c12c1d7e96d'
FEATURE = 'v2-release-candidate-v2'
SCRIPTS = [('DeployV2ReleaseTestnet', 40), ('RegisterV2TradablePercent', 5), ('RegisterV2PercentBuyback', 3),
           ('RegisterV2UpgradeableCycle', 3), ('SetV2KeeperReward', 1), ('CalibrateV2Listings', 16)]
CORE = {'treasuryDeployer': ('V2TreasuryDeployer', 'V2TreasuryDeployer'), 'tokenDeployer': ('HedgeFunDeployers', 'TokenDeployer'),
        'curveDeployer': ('CurveDeployer', 'CurveDeployer'), 'hook': ('HedgeFunV2Hook', 'HedgeFunV2Hook'),
        'factory': ('HedgeFunV2Factory', 'HedgeFunV2Factory'), 'tradeRouter': ('HedgeFunV2TradeRouter', 'HedgeFunV2TradeRouter'),
        'nativeRouter': ('HedgeFunV2NativeRouter', 'HedgeFunV2NativeRouter'), 'rebalancePolicy': ('strategy/V2RebalancePolicy', 'V2RebalancePolicy'),
        'tradablePercentPolicy': ('strategy/V2TradablePercentRebalancePolicy', 'V2TradablePercentRebalancePolicy')}
KINDS = [('HedgeFunV2UpgradeableTreasury', 'ordinary strategy (default)', 0, 0, 0),
         ('HedgeFunV2UpgradeableBuybackTreasury', 'buy-back', 0, 0, 0),
         ('HedgeFunV2UpgradeableEngineTreasury', 'spot engine', 1, 1, 3),
         ('HedgeFunV2TradablePercentEngineTreasury', 'rebalance (schema 3)', 1, 3, 3),
         ('HedgeFunV2PercentBuybackTreasury', 'percentage buy-back', 0, 0, 0),
         ('HedgeFunV2UpgradeableCycleTreasury', 'cycle', 0, 0, 0)]
# Defaults the deployment sets on top of the base venue's, then SetV2KeeperReward: index into the Defaults tuple.
RELEASE_DEFAULTS = {1: 2000, 5: 3000, 6: 1000, 9: 0, 12: 10, 16: 10, 20: 1, 21: 500000000000000}
SALE_BPS, LP_BPS, TARGET_FDV_USD = 7931, 7000, 50_000


def reference_open_price_e18(price_e18):
    remaining = 10_000 - SALE_BPS
    opening_fdv = TARGET_FDV_USD * 10**18 * remaining * remaining // (10_000 * 10_000)
    return opening_fdv * 10**18 // (price_e18 * 1_000_000_000)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, default=ROOT / 'deploy/testnet-v2-release.candidate.json')
    p.add_argument('--broadcasts', type=Path, default=ROOT / 'broadcast')
    p.add_argument('--out', type=Path, default=ROOT / 'deploy/testnet-v2-release.json')
    p.add_argument('--rpc', default='https://rpc.testnet.chain.robinhood.com')
    p.add_argument('--cast', default='cast')
    p.add_argument('--confirmations', type=int, default=2)
    p.add_argument('--venue', type=Path, help='the deployer venue file written by RelistV2TestnetStocks: its stocks are expected to be listed on it')
    a = p.parse_args()
    book = json.loads(a.candidate.read_text())

    def rpc(method, params):
        assert method in {'eth_chainId', 'eth_getBlockByNumber', 'eth_getTransactionReceipt', 'eth_getTransactionByHash',
                          'eth_getCode', 'eth_call'}
        payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
        r = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--max-time', '30', '-H', 'Content-Type: application/json',
                            '--data-binary', '@-', a.rpc], input=payload, text=True, capture_output=True, check=True)
        result = json.loads(r.stdout)
        assert 'error' not in result, result
        return result['result']

    def cast(*args):
        return subprocess.check_output([a.cast, *map(str, args)], text=True).strip()

    def creation(file, name):
        return json.loads((ROOT / 'out' / (file.split('/')[-1] + '.sol') / (name + '.json')).read_text())['bytecode']['object']

    # --- the candidate and the source
    assert int(rpc('eth_chainId', []), 16) == book['chainId'] == 46630
    assert book['featureVersion'] == FEATURE and book['broadcast'] is False and book['broadcastRequested'] is True
    assert book['operator'].lower() == book['owner'].lower() == DEPLOYER
    assert book['protocol'].lower() == book['venueOperator'].lower() == VENUE_OWNER
    subprocess.run(['git', 'diff', '--exit-code', book['commit'], '--', 'src'], cwd=ROOT, check=True, capture_output=True)
    venue = json.loads(a.venue.read_text()) if a.venue else None
    if venue:
        assert venue['schema'] == 'v2-testnet-deployer-venue-v1' and venue['chainId'] == 46630 and venue['factory'].lower() == book['factory'].lower()
        assert venue['owner'].lower() == DEPLOYER and venue['broadcastRequested'] is True
    head = rpc('eth_getBlockByNumber', ['latest', False])
    tag = hex(int(head['number'], 16) - a.confirmations)
    block = rpc('eth_getBlockByNumber', [tag, False])

    # --- every transaction of every script, against its canonical receipt
    runs, nonces, creates, hook_rows, records = [], [], {}, [], []
    for script, count in SCRIPTS:
        run = json.loads((a.broadcasts / f'{script}.s.sol/46630/run-latest.json').read_text())
        assert run['chain'] == 46630 and len(run['transactions']) == count, (script, len(run['transactions']))
        hashes = []
        for row in run['transactions']:
            h, expected = row['hash'], row['transaction']
            tx, receipt = rpc('eth_getTransactionByHash', [h]), rpc('eth_getTransactionReceipt', [h])
            assert receipt and int(receipt['status'], 16) == 1, (script, h)
            assert receipt['transactionHash'].lower() == h.lower() and tx['from'].lower() == receipt['from'].lower() == DEPLOYER
            assert int(tx['chainId'], 16) == 46630 and int(tx['value'], 16) == 0
            assert tx['input'].lower() == expected['input'].lower()
            assert (tx.get('to') or '').lower() == (expected.get('to') or '').lower()
            mined = rpc('eth_getBlockByNumber', [receipt['blockNumber'], False])
            assert mined['hash'] == receipt['blockHash'] and h.lower() in [v.lower() for v in mined['transactions']]
            assert int(tag, 16) >= int(receipt['blockNumber'], 16)
            nonces.append(int(tx['nonce'], 16))
            if row['transactionType'] == 'CREATE' and row.get('contractName'):
                creates[row['contractName']] = (receipt['contractAddress'], tx['input'])
            if row['transactionType'] == 'CREATE2' and row.get('contractName') == 'HedgeFunV2Hook':
                hook_rows.append((row['contractAddress'], tx['input']))
            hashes.append(h)
        runs.append(run)
        records.append({'script': script, 'transactionHashes': hashes})
    assert len(set(nonces)) == len(nonces) == sum(c for _, c in SCRIPTS) and nonces == list(range(nonces[0], nonces[0] + len(nonces)))
    for key, (file, name) in CORE.items():
        if key == 'hook':
            continue
        target, init = creates[name]
        if key == 'tradablePercentPolicy':
            book[key] = target
        assert target.lower() == book[key].lower() and init.startswith(creation(file, name)), key
    assert len(hook_rows) == 1 and hook_rows[0][0].lower() == book['hook'].lower()
    assert hook_rows[0][1][2:66].lower() == book['hookSalt'][2:].lower() and ('0x' + hook_rows[0][1][66:]).startswith(creation('HedgeFunV2Hook', 'HedgeFunV2Hook'))
    assert int(book['hook'], 16) & 0x3fff == 0x28cc

    # --- the live state at the pinned block
    def read(target, sig, *args):
        raw = rpc('eth_call', [{'to': target, 'data': cast('calldata', sig, *args)}, tag])
        assert len(raw) > 2 and (len(raw) - 2) % 64 == 0, (target, sig)
        return [int(raw[i:i + 64], 16) for i in range(2, len(raw), 64)]

    def eq(target, sig, expected, *args):
        wanted = [int(x, 16) if isinstance(x, str) and x.startswith('0x') else int(x) for x in expected]
        assert read(target, sig, *args) == wanted, (sig, target, args)

    def addr(word):
        return f'0x{word:040x}'

    for sig, key in [('owner()', 'owner'), ('protocol()', 'protocol'), ('poolManager()', 'poolManager'), ('v3Factory()', 'v3Factory'),
                     ('usdg()', 'usdg'), ('hook()', 'hook'), ('treasuryDeployer()', 'treasuryDeployer'), ('tokenDeployer()', 'tokenDeployer'),
                     ('curveDeployer()', 'curveDeployer')]:
        eq(book['factory'], sig, [book[key]])
    eq(book['factory'], 'pendingOwner()', [0]); eq(book['factory'], 'publicLaunch()', [1])
    book['strategyCount'] = read(book['factory'], 'strategyCount()')[0]   # 0 at the release; launches since are recorded, not refused
    for key in ('treasuryDeployer', 'tokenDeployer', 'curveDeployer', 'hook', 'tradeRouter'):
        eq(book[key], 'factory()', [book['factory']])
    eq(book['nativeRouter'], 'router()', [book['tradeRouter']]); eq(book['nativeRouter'], 'wrappedNative()', [book['weth']])
    eq(book['hook'], 'version()', [3]); eq(book['treasuryDeployer'], 'version()', [2])
    eq(book['curveDeployer'], 'DEFAULT_SALE_BPS()', [SALE_BPS]); eq(book['treasuryDeployer'], 'DEFAULT_LP_BPS()', [LP_BPS])
    registry = book['treasuryDeployer']
    eq(registry, 'kindCount()', [len(KINDS)])
    kinds = []
    for i, (name, label, engine_version, schema, capabilities) in enumerate(KINDS):
        code = creation(name, name)
        manifest = read(registry, 'kindManifest(uint8)', i)
        assert manifest == [engine_version, schema, int(cast('keccak', code), 16), capabilities], (i, name)
        chunks = read(registry, 'kinds(uint8)', i)
        assert '0x' + ''.join(rpc('eth_getCode', [addr(x), tag])[2:] for x in chunks) == code, (i, name)
        kinds.append({'kind': i, 'name': label, 'contract': name, 'chunkA': cast('to-check-sum-address', addr(chunks[0])),
                      'chunkB': cast('to-check-sum-address', addr(chunks[1])), 'creationCodeHash': cast('keccak', code),
                      'engineVersion': engine_version, 'configSchema': schema, 'capabilities': capabilities, 'upgradeable': True})
    eq(registry, 'allInTriggerCodeHash()', [cast('keccak', creation('HedgeFunV2UpgradeableTreasury', 'HedgeFunV2UpgradeableTreasury'))])
    controller = addr(read(registry, 'upgradeController()')[0])
    eq(controller, 'owner()', [book['owner']]); eq(controller, 'UPGRADE_DELAY()', [172800])
    # policies: schema 1 (spot engine) from the deployment, schema 3 (rebalance) from RegisterV2TradablePercent
    tradable = runs[1]
    registered = [t for t in tradable['transactions'] if (t.get('function') or '').startswith('registerPolicy')]
    assert len(registered) == 1
    policy_args = registered[0]['arguments']
    assert policy_args[0].lower() == book['tradablePercentPolicy'].lower()
    # the key the registration returned, as the registry derives it (see V2TreasuryDeployer.registerPolicy)
    kind3, key3, policy3 = re.match(r'\((\d+), (0x[0-9a-fA-F]{64}), (0x[0-9a-fA-F]{40})\)', tradable['returns']['r']['value']).groups()
    assert kind3 == '3' and policy3.lower() == book['tradablePercentPolicy'].lower()
    for key, policy, expected in [(book['rebalancePolicyKey'], book['rebalancePolicy'], [1, 1, 150000, 160, 3, 1]),
                                  (key3, book['tradablePercentPolicy'], [1, 3, int(policy_args[1]), int(policy_args[2]), 3, 1])]:
        manifest = read(registry, 'policy(bytes32)', key)
        assert manifest[0] == int(policy, 16) and manifest[1] == int(cast('keccak', rpc('eth_getCode', [policy, tag])), 16)
        assert manifest[2:] == expected, (key, manifest)
    book['tradablePercentPolicyKey'] = key3
    book['tradablePercentManifests'] = {'dependency': policy_args[3], 'audit': policy_args[4]}
    # defaults: the base venue's, with the release choices
    defaults, base = read(book['factory'], 'getDefaults()'), read(book['baseFactory'], 'getDefaults()')
    for i, v in RELEASE_DEFAULTS.items():
        base[i] = v
    assert defaults == base, [(i, d, b) for i, (d, b) in enumerate(zip(defaults, base)) if d != b]
    book['expectedDefaults'] = '0x' + ''.join(f'{x:064x}' for x in defaults)
    book['defaultsHash'] = cast('keccak', book['expectedDefaults'])
    # the venue is untouched and still the venue owner's
    for key in ('market', 'calendar', 'usdg', 'usdgFeed', 'baseFactory'):
        eq(book[key], 'owner()', [VENUE_OWNER])
    # listings: the base venue's oracle and pool, the reference opening price, the release LP share
    assert set(book['stocks']) == {'AAPL', 'GME', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'GOOGL', 'META'}
    for symbol, stock in book['stocks'].items():
        token, oracle, pool = stock['token'], stock['oracle'], stock['pool']
        eq(book['baseFactory'], 'listings(address)', [oracle, pool, stock['openPriceE18'], 1], token)
        ok, price_e18, _ = read(oracle, 'lastPriceAt()')
        assert ok == 1 and price_e18 == int(stock['priceE18']), (symbol, price_e18)
        open_price = reference_open_price_e18(price_e18)
        relisted = venue['stocks'].get(symbol) if venue else None
        if relisted:
            # the deployer venue's feed, oracle and pool; the price is whatever the deployer last set
            assert relisted['token'].lower() == token.lower() and relisted['decimals'] == 18
            for k in ('feed', 'oracle', 'pool', 'fee', 'tickLower', 'tickUpper', 'maxDeviationBps', 'maxSlippageBps', 'sellChunkUsdg'):
                stock[k] = relisted[k]
            oracle, pool = stock['oracle'], stock['pool']
            ok, price_e18, _ = read(oracle, 'lastPriceAt()')
            assert ok == 1 and price_e18 > 0, (symbol, 'venue oracle')
            stock['priceE18'] = str(price_e18)
            stock['liquidity'] = str(read(pool, 'liquidity()')[0])
            eq(venue['market'], 'lines(address)', [token, stock['feed'], int(token, 16) < int(book['usdg'], 16), 10**30, stock['tickLower'], stock['tickUpper'], int(stock['liquidity'])], pool)
            eq(stock['feed'], 'owner()', [DEPLOYER]); eq(stock['feed'], 'operators(address)', [1], venue['market'])
        eq(book['factory'], 'listings(address)', [oracle, pool, open_price, 1], token)
        eq(book['factory'], 'listingGates(address)', [stock['maxDeviationBps'], stock['maxSlippageBps'], stock['sellChunkUsdg']], token)
        eq(registry, 'lpBps(address)', [LP_BPS], token)
        eq(oracle, 'stock()', [token]); eq(oracle, 'stockFeed()', [stock['feed']])
        eq(oracle, 'usdgFeed()', [book['usdgFeed']]); eq(oracle, 'calendar()', [book['calendar']])
        eq(book['v3Factory'], 'getPool(address,address,uint24)', [pool], token, book['usdg'], stock['fee'])
        stock['openPriceE18'] = str(open_price)
        stock['lpBps'] = LP_BPS
    if venue:
        eq(venue['market'], 'owner()', [DEPLOYER]); eq(venue['market'], 'usdg()', [book['usdg']])
        book['venue'] = {'schema': venue['schema'], 'market': venue['market'], 'stocks': sorted(venue['stocks']),
                         'codeHash': cast('keccak', rpc('eth_getCode', [venue['market'], tag]))}
    # runtime code of every component, as deployed
    book['codeHashes'] = {k: cast('keccak', rpc('eth_getCode', [book[k], tag])) for k in CORE}
    book['codeHashes']['upgradeController'] = cast('keccak', rpc('eth_getCode', [controller, tag]))

    book.update({'broadcast': True, 'kinds': kinds, 'upgradeController': cast('to-check-sum-address', controller),
                 'tradablePercentKind': 3, 'percentBuybackKind': 4, 'cycleKind': 5, 'keeperRewardBps': 10,
                 'verification': {
                     'blockNumber': int(tag, 16), 'blockHash': block['hash'], 'transactionCount': len(nonces),
                     'firstNonce': nonces[0], 'transactions': records,
                     'listingParameters': {'saleBps': SALE_BPS, 'lpBps': LP_BPS, 'targetGraduationFdvUsd': TARGET_FDV_USD,
                                           'openingFdvUsd': '2140.3805', 'graduationRaiseUsd': 'about 8,205'},
                     'checks': f'{len(nonces)} transactions of six scripts against canonical receipts (status, sender, chain, input, '
                               'nonce sequence, block membership); creation code of the nine core contracts and the six kinds against '
                               'the build of the recorded commit; roles, versions, both policies, the release defaults against the base '
                               "venue's, and the eight listings at the reference opening price with a 7000 LP share"
                               + (f"; {', '.join(sorted(venue['stocks']))} re-listed on the deployer venue {venue['market']}" if venue else '') + '; read at one block.',
                     'verifiedAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}})
    a.out.write_text(json.dumps(book, indent=1, sort_keys=True) + '\n')
    print(f'verified at block {int(tag, 16)}; wrote {a.out}')


if __name__ == '__main__':
    main()
