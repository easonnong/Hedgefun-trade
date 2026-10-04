#!/usr/bin/env python3
"""Bounded, operator-run SBOX rehearsal. No transaction is signed without --execute.

Needs Foundry cast on PATH; Python standard library only. Secrets and mutable state
live outside the repository. Each batch is resumable; never reuse a batch name for
an intentionally new trade. Uncertain submissions block every subsequent send.
"""
import argparse
import contextlib
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from decimal import Decimal, InvalidOperation

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path.home() / '.local/share/hedgefund-sandbox/sbox-ten'
CHAIN = 4663


class SafetyError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def address(value):
    require(isinstance(value, str) and ADDRESS.fullmatch(value), 'Invalid address')
    require(int(value, 16) != 0, 'Zero address is forbidden')
    return value.lower()


def units(value, decimals, cap=None, allow_zero=False):
    try:
        n = Decimal(str(value))
        require(n.is_finite() and (n >= 0 if allow_zero else n > 0), 'Amount must be finite and positive')
        require(n.as_tuple().exponent >= -decimals, 'Amount has excess decimal precision')
        require(cap is None or n <= Decimal(str(cap)), f'Amount exceeds rehearsal cap {cap}')
        return int(n * 10 ** decimals)
    except (InvalidOperation, ValueError):
        raise SafetyError('Invalid decimal amount') from None


def minimum(output, slippage):
    require(0 <= slippage <= 300, 'Slippage must be 0..300 basis points')
    result = output * (10000 - slippage) // 10000
    require(result > 0, 'Quote is zero or too small for a nonzero minimum')
    return result


def clean_env():
    # No ambient signer, mnemonic, RPC, chain, or account may override our pins.
    return {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'LANG') if k in os.environ}


def cast(args, env=None, timeout=90):
    try:
        p = subprocess.run(['cast', *map(str, args)], env=env or clean_env(),
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise SafetyError('cast failed or timed out; secret-bearing output suppressed') from None
    if p.returncode != 0:
        # Classify only known wallet-decryption errors; never echo raw stderr,
        # which may contain paths, credentials, RPC URLs or input material.
        if list(args[:2]) == ['wallet', 'address']:
            reason = p.stderr.lower()
            if any(marker in reason for marker in ('mac mismatch', 'macmismatch', 'incorrect password', 'invalid password')):
                raise SafetyError('Keystore password did not unlock this account. Use its original keystore password, not a private key.')
            raise SafetyError('Could not open/decrypt the selected keystore. Check the account name and its original password locally with cast wallet address.')
        raise SafetyError('cast failed; secret-bearing output suppressed (check RPC, balance, password and contract gates)')
    return p.stdout.strip()


def safe_file(path, private=False):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink paths are forbidden')
    require(path.is_file(), f'Missing file: {path.name}')
    if private:
        st = path.stat()
        require(st.st_uid == os.getuid() and st.st_mode & 0o077 == 0, 'Secret file must belong to you and have mode 0600')
    return path


def write_json(path, data):
    require(not path.is_symlink(), 'Refusing symlink state file')
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Rpc:
    def __init__(self, url):
        require(url.startswith(('http://', 'https://')), 'Set RH_RPC to an HTTP(S) endpoint')
        self.url = url

    def request(self, method, params):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
        try:
            req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=40) as response:
                result = json.load(response)
            require('error' not in result and 'result' in result, f'{method} rejected; RPC details suppressed')
            return result['result']
        except SafetyError:
            raise
        except Exception:
            raise SafetyError(f'{method} unavailable; endpoint details suppressed') from None

    def call(self, target, signature, *args, sender=None):
        tx = {'to': target, 'data': calldata(signature, *args)}
        if sender:
            tx['from'] = sender
        data = self.request('eth_call', [tx, 'latest'])
        require(data.startswith('0x') and len(data[2:]) % 64 == 0, 'Invalid ABI response')
        return [int(data[i:i+64], 16) for i in range(2, len(data), 64)]

    def balance(self, owner, token=None):
        return (self.call(token, 'balanceOf(address)', owner)[0] if token else
                int(self.request('eth_getBalance', [owner, 'latest']), 16))


def calldata(signature, *args):
    return cast(['calldata', signature, *args])


def word_address(word):
    require(0 < word < 2**160, 'Invalid address ABI word')
    return f'0x{word:040x}'


def validate(rpc, config):
    require(config.get('chain_id') == CHAIN, 'Config must pin chain 4663')
    require(int(rpc.request('eth_chainId', []), 16) == CHAIN, 'Wrong RPC chain')
    for key in ('factory', 'router', 'pool_manager', 'token', 'quote', 'stock', 'stock_pool', 'treasury', 'hook', 'operator'):
        config[key] = address(config[key])
        if key != 'operator':
            require(rpc.request('eth_getCode', [config[key], 'latest']) not in ('0x', '0x0'), f'{key} has no code')
    require(HASH.fullmatch(config.get('router_codehash', '')), 'Pin the independently verified router runtime hash')
    code = rpc.request('eth_getCode', [config['router'], 'latest'])
    require(cast(['keccak', code]).lower() == config['router_codehash'].lower(), 'Router runtime hash mismatch; approvals forbidden')
    require(type(config['strategy_id']) is int and config['strategy_id'] >= 0, 'Invalid strategy id')
    def a(target, sig, *args):
        return word_address(rpc.call(target, sig, *args)[0])
    f, r = config['factory'], config['router']
    for target, sig, expected in ((r, 'factory()', f), (r, 'usdg()', config['quote']),
            (r, 'poolManager()', config['pool_manager']), (f, 'usdg()', config['quote']),
            (f, 'poolManager()', config['pool_manager'])):
        require(a(target, sig) == expected, f'Wiring mismatch: {sig}')
    strategy = rpc.call(f, 'strategies(uint256)', config['strategy_id'])
    require(len(strategy) == 5, 'Wrong strategy ABI')
    require(word_address(strategy[0]) == config['token'] and word_address(strategy[3]) == config['stock'], 'Wrong strategy token or stock')
    require(word_address(strategy[1]) == config['treasury'] and word_address(strategy[2]) == config['hook'], 'Wrong treasury or hook')
    pool = config['stock_pool']
    require({a(pool, 'token0()'), a(pool, 'token1()')} == {config['quote'], config['stock']}, 'Wrong V3 pair')
    v3 = a(f, 'v3Factory()')
    require(a(v3, 'getPool(address,address,uint24)', config['quote'], config['stock'], rpc.call(pool, 'fee()')[0]) == pool, 'Noncanonical V3 pool')
    require(rpc.call(config['quote'], 'decimals()')[0] == 6, 'Quote must use 6 decimals')
    require(rpc.call(config['token'], 'decimals()')[0] == 18, 'Strategy token must use 18 decimals')
    return config


@contextlib.contextmanager
def password_file(state, supplied, label, confirm=False, allow_empty=False):
    if supplied:
        path = safe_file(supplied, private=True)
        require(allow_empty or bool(path.read_text().rstrip('\r\n')), 'Empty password refused')
        yield path
        return
    hint = '; press Enter if this existing account has no password' if allow_empty else ''
    password = getpass.getpass(label + ' password (hidden' + hint + '): ')
    require(allow_empty or bool(password), 'Empty password refused')
    if confirm:
        repeated = getpass.getpass('Repeat new wallet password (hidden): ')
        require(password == repeated, 'Passwords do not match; no wallets created')
        del repeated
    fd, name = tempfile.mkstemp(prefix='.password-', dir=state)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(password)
        del password
        yield Path(name)
    finally:
        os.unlink(name)


def signer_address(signer, password):
    try:
        result = cast(['wallet', 'address', *signer, '--password-file', str(password)])
    except SafetyError as error:
        label = 'Funding account unlock' if '--account' in signer else 'Test-wallet unlock'
        raise SafetyError(label + ' failed: ' + str(error)) from None
    return address(result)


def manifest(state):
    data = json.loads(safe_file(state / 'wallets.json').read_text())
    require(data['version'] == 1 and len(data['wallets']) == 10, 'Expected manifest of exactly 10 generated wallets')
    seen = set()
    for wallet in data['wallets']:
        wallet['address'] = address(wallet['address'])
        require(wallet['address'] not in seen, 'Duplicate wallet')
        seen.add(wallet['address'])
        name = wallet['keystore']
        require(isinstance(name, str) and Path(name).name == name, 'Invalid keystore name')
        safe_file(state / 'keystores' / name, private=True)
    return data['wallets']


def initialize(args, state):
    manifest_path = state / 'wallets.json'
    folder = state / 'keystores'
    require(not manifest_path.exists() and not manifest_path.is_symlink(), 'Wallets already exist; never overwrite keys')
    require(not folder.is_symlink(), 'Symlink keystore directory forbidden')
    # An old failed prompt could leave an empty directory. Reuse only that case;
    # even one file is preserved and requires explicit recovery, never replacement.
    require(not folder.exists() or (folder.is_dir() and not any(folder.iterdir())),
            'Existing keystore files found without a wallet manifest; keep them for recovery, never overwrite keys')
    if not args.execute:
        print('PLAN: generate 10 random encrypted wallets outside the repo; add --execute locally to create.')
        return
    with password_file(state, args.password_file, 'New wallet keystore', confirm=True) as password:
        env = clean_env()
        env['CAST_PASSWORD'] = password.read_text().rstrip('\r\n')
        require(bool(env['CAST_PASSWORD']), 'Empty keystore password refused')
        folder.mkdir(mode=0o700, exist_ok=True)
        require(folder.stat().st_uid == os.getuid() and folder.stat().st_mode & 0o077 == 0,
                'Keystore directory must belong to you and have mode 0700')
        try:
            # stdout may include sensitive material in future Foundry versions: never emit it.
            cast(['wallet', 'new', str(folder), '--number', '10'], env=env)
        finally:
            del env['CAST_PASSWORD']
            # rmdir cannot remove a nonempty directory: partial keys always survive.
            try:
                folder.rmdir()
            except OSError:
                pass
        require(folder.is_dir(), 'No wallets generated; rerun init to try again')
        files = sorted(folder.iterdir())
        require(len(files) == 10, 'Incomplete wallet generation; keep keystore directory for recovery')
        wallets = []
        for key in files:
            os.chmod(key, 0o600)
            safe_file(key, private=True)
            wallets.append({'address': signer_address(['--keystore', str(key)], password), 'keystore': key.name})
        require(len({w['address'] for w in wallets}) == 10, 'Duplicate generated addresses')
        write_json(state / 'wallets.json', {'version': 1, 'wallets': wallets})
    print(json.dumps({'manifest': str(state / 'wallets.json'), 'addresses': [w['address'] for w in wallets]}, indent=2))


class Journal:
    def __init__(self, state, config):
        self.path = state / 'journal.json'
        self.data = json.loads(safe_file(self.path).read_text()) if self.path.exists() else {'version': 1, 'config': config, 'operations': {}}
        require(self.data['config'] == config, 'Config changed since journal creation; use a separate state directory')
        self.ops = self.data['operations']

    def save(self):
        write_json(self.path, self.data)

    def unblocked(self):
        blocked = [k for k, v in self.ops.items() if v['status'] in ('prepared', 'submitted')]
        require(not blocked, 'Uncertain/pending operation blocks sending: ' + ', '.join(blocked) + '. Run status or reconcile; do not resend.')

    def admit_send(self):
        """Optional cancellation gate before prepare; admitted sends must drain."""

    def done(self, key, intent):
        if key not in self.ops:
            return False
        require(self.ops[key]['intent'] == intent, 'Batch arguments changed; inspect journal and use a new --batch only for an intentional new operation')
        require(self.ops[key]['status'] == 'confirmed', 'Previous operation not confirmed; inspect status/reconcile')
        return True

    def refresh(self, rpc):
        for item in self.ops.values():
            if item['status'] == 'submitted':
                receipt = rpc.request('eth_getTransactionReceipt', [item['hash']])
                if receipt:
                    item['status'] = 'confirmed' if int(receipt['status'], 16) == 1 else 'reverted'
                    item['receipt'] = receipt
        self.save()


def send(rpc, journal, key, sender, to, data, value, signer, password, intent):
    if journal.done(key, intent):
        print(f'{key}: already confirmed; skipped')
        return
    journal.unblocked()
    latest = int(rpc.request('eth_getTransactionCount', [sender, 'latest']), 16)
    pending = int(rpc.request('eth_getTransactionCount', [sender, 'pending']), 16)
    require(latest == pending, 'Signer has pending transactions; wait and inspect before sending')
    journal.admit_send()  # Passing the gate admits this send; later cancellation cannot revoke it.
    operation = {'status': 'prepared', 'intent': intent, 'from': sender, 'to': to,
                 'data': data, 'value': value, 'nonce': pending, 'created_at': int(time.time())}
    journal.ops[key] = operation
    journal.save()  # Durable BEFORE signing; any error from now is ambiguous.
    env = clean_env()
    env['ETH_RPC_URL'] = rpc.url
    result = cast(['send', to, data, '--value', str(value), '--chain', CHAIN,
                   '--nonce', pending, '--from', sender, *signer, '--password-file', str(password), '--async'], env=env)
    require(HASH.fullmatch(result), f'Uncertain send for {key}; inspect transaction history and reconcile')
    operation.update(status='submitted', hash=result)
    journal.save()
    print(f'{key}: {result}', flush=True)
    for _ in range(60):
        receipt = rpc.request('eth_getTransactionReceipt', [result])
        if receipt:
            operation.update(status='confirmed' if int(receipt['status'], 16) == 1 else 'reverted', receipt=receipt)
            journal.save()
            require(operation['status'] == 'confirmed', f'{key} reverted; stopping batch')
            return
        time.sleep(1)
    raise SafetyError('Receipt pending; batch stopped. Run status before continuing.')


def reconcile(args, rpc, journal):
    require(args.operation in journal.ops, 'Unknown operation')
    item = journal.ops[args.operation]
    require(item['status'] == 'prepared', 'Only uncertain prepared operations need reconciliation')
    require(HASH.fullmatch(args.tx_hash), 'Invalid transaction hash')
    tx = rpc.request('eth_getTransactionByHash', [args.tx_hash])
    require(tx is not None, 'Transaction not found; no state changed')
    require(tx['from'].lower() == item['from'] and (tx.get('to') or '').lower() == item['to'] and
            int(tx['nonce'], 16) == item['nonce'] and int(tx['value'], 16) == item['value'] and
            tx['input'].lower() == item['data'].lower() and int(tx.get('chainId', hex(CHAIN)), 16) == CHAIN,
            'Transaction does not match exact recorded intent')
    item.update(status='submitted', hash=args.tx_hash)
    journal.save()
    journal.refresh(rpc)
    print(f"Reconciled {args.operation}: {item['status']}")


def tax_rates(rpc, config, owner):
    pool_id = rpc.call(config['hook'], 'poolOfTreasury(address)', config['treasury'])[0]
    require(pool_id != 0, 'Treasury has no registered token pool')
    encoded = f'0x{pool_id:064x}'
    return {kind: rpc.call(config['hook'], kind+'RateBps(bytes32)', encoded, sender=owner)[0] for kind in ('buy', 'sell')}


def selected(args, wallets):
    if args.wallet is None:
        return list(enumerate(wallets, 1))
    require(1 <= args.wallet <= 10, '--wallet must be 1..10')
    return [(args.wallet, wallets[args.wallet - 1])]


def run(args, state, journal=None):
    if args.command == 'init':
        return initialize(args, state)
    require(args.config, '--config is required')
    require((state / 'wallets.json').is_file(),
            'Wallets are not initialized. Run init --execute by itself and finish both password prompts first.')
    wallets = manifest(state)
    config = json.loads(safe_file(args.config).read_text())
    rpc = Rpc(os.environ.get('RH_RPC', ''))
    config = validate(rpc, config)
    journal = Journal(state, config) if journal is None else journal
    require(journal.path == state / 'journal.json' and journal.data['config'] == config, 'Injected journal target mismatch')
    if args.command == 'reconcile':
        return reconcile(args, rpc, journal)
    if args.command in ('status', 'inspect', 'plan'):
        journal.refresh(rpc)
        print(json.dumps({'operator': config['operator'], 'operations': {k: {'status': v['status'], 'hash': v.get('hash')} for k,v in journal.ops.items()},
            'wallets': [{'index': i, 'address': w['address'], 'gas_wei': rpc.balance(w['address']), 'quote_units': rpc.balance(w['address'], config['quote']), 'token_units': rpc.balance(w['address'], config['token'])} for i,w in enumerate(wallets, 1)]}, indent=2))
        return
    require(re.fullmatch(r'[a-zA-Z0-9_-]{1,48}', args.batch), 'Invalid batch name')
    journal.refresh(rpc)
    journal.unblocked()
    selection = selected(args, wallets)
    if args.command == 'fund':
        quote_target, gas_target = units(args.quote, 6, cap=1), units(args.gas, 18, cap='0.001')
        plans = [(i, w, max(0, quote_target-rpc.balance(w['address'], config['quote'])), max(0, gas_target-rpc.balance(w['address']))) for i,w in selection]
        funded = sum(int(op['data'][-64:], 16) for op in journal.ops.values() if op['intent'].get('kind') == 'quote' and op['status'] != 'reverted')
        new_funding = sum(q for i,w,q,g in plans if f'{args.batch}:{i}:quote' not in journal.ops)
        require(funded + new_funding <= 20_000_000, 'Cumulative quote funding exceeds hard 20 USDG rehearsal budget')
        print(json.dumps({'mode': 'EXECUTE' if args.execute else 'PLAN', 'topups': [{'index':i,'address':w['address'],'quote_units':q,'gas_wei':g} for i,w,q,g in plans]}, indent=2), flush=True)
        if not args.execute:
            return
        require(rpc.balance(config['operator'], config['quote']) >= sum(p[2] for p in plans), 'Operator lacks quote funding balance')
        require(rpc.balance(config['operator']) > sum(p[3] for p in plans), 'Operator lacks native balance plus transaction fees')
        # Verify every destination against the decrypted keystore before funding any.
        with password_file(state, args.wallet_password_file, 'Ten wallets') as wallet_password:
            for _, wallet in selection:
                require(signer_address(['--keystore', str(state/'keystores'/wallet['keystore'])], wallet_password) == wallet['address'], 'Destination keystore/address mismatch')
        with password_file(state, args.password_file, 'Funding account', allow_empty=True) as password:
            signer = ['--account', args.account]
            require(signer_address(signer, password) == config['operator'], 'Funding account does not match pinned operator')
            for i,w,q,g in plans:
                for kind, amount, to, data, value, target in (
                        ('quote', q, config['quote'], calldata('transfer(address,uint256)', w['address'], q), 0, quote_target),
                        ('gas', g, w['address'], '0x', g, gas_target)):
                    key = f'{args.batch}:{i}:{kind}'
                    intent = {'kind':kind,'target':target,'recipient':w['address']}
                    if key in journal.ops:
                        journal.done(key, intent)
                        continue
                    if amount:
                        send(rpc,journal,key,config['operator'],to,data,value,signer,password,intent)
                        require(rpc.balance(w['address'], config['quote'] if kind == 'quote' else None) >= target, 'Funding balance postcheck failed; stop and inspect receipt')
        return
    require(0 <= args.max_tax_bps <= 1500, 'Tax cap must be 0..1500 basis points')
    require(0 <= args.slippage_bps <= 300 and 1 <= args.deadline_seconds <= 120, 'Invalid slippage or deadline')
    if args.command == 'buy':
        fixed = units(args.amount, 6, cap=1)
    else:
        require(1 <= args.fraction_bps <= 10000, 'Sell fraction must be 1..10000 basis points')
    rates = tax_rates(rpc, config, selection[0][1]['address'])
    print(json.dumps({'current_tax_bps': rates, 'maximum_tax_bps': args.max_tax_bps}), flush=True)
    require(rates[args.command] <= args.max_tax_bps, 'Current trade tax exceeds explicit cap')
    print(f'{"EXECUTE" if args.execute else "PLAN"}: {args.command}, {len(selection)} wallets, slippage={args.slippage_bps}bps, batch={args.batch}', flush=True)
    if not args.execute:
        print('Execution will decrypt/verify each wallet, approve exact input, quote eth_call, and send one bounded trade per wallet sequentially.')
        return
    with password_file(state, args.password_file, 'Ten wallets') as password:
        for i,w in selection:
            owner = w['address']
            signer = ['--keystore', str(state/'keystores'/w['keystore'])]
            require(signer_address(signer,password) == owner, 'Wallet/keystore mismatch')
            key = f'{args.batch}:{i}:{args.command}'
            intent = {'kind':args.command,'amount':args.amount if args.command == 'buy' else None,
                      'fraction_bps':args.fraction_bps if args.command == 'sell' else None,'slippage_bps':args.slippage_bps,'max_tax_bps':args.max_tax_bps}
            if journal.done(key,intent):
                print(f'{key}: already confirmed; skipped')
                continue
            rates = tax_rates(rpc, config, owner)
            require(rates[args.command] <= args.max_tax_bps, 'Current trade tax exceeds explicit cap')
            print(json.dumps({'wallet': i, 'current_tax_bps': rates}), flush=True)
            input_token = config['quote'] if args.command == 'buy' else config['token']
            amount = fixed if args.command == 'buy' else rpc.balance(owner,input_token)*args.fraction_bps//10000
            require(amount > 0 and rpc.balance(owner,input_token) >= amount, 'Wallet has insufficient trade balance')
            allowance = rpc.call(input_token,'allowance(address,address)',owner,config['router'])[0]
            # Reset any old allowance, then set exactly this input. Both steps journaled.
            if allowance != amount:
                if allowance:
                    send(rpc,journal,key+':reset',owner,input_token,calldata('approve(address,uint256)',config['router'],0),0,signer,password,{'amount':0})
                send(rpc,journal,key+':approve',owner,input_token,calldata('approve(address,uint256)',config['router'],amount),0,signer,password,{'amount':amount})
                require(rpc.call(input_token,'allowance(address,address)',owner,config['router'])[0] == amount, 'Exact allowance verification failed')
            require(tax_rates(rpc, config, owner)[args.command] <= args.max_tax_bps, 'Tax changed above cap after approval; stop before trade')
            deadline = int(rpc.request('eth_getBlockByNumber',['latest',False])['timestamp'],16) + args.deadline_seconds
            sig = f'{args.command}(uint256,address,uint256,uint256,uint256)'
            quote = rpc.call(config['router'],sig,config['strategy_id'],config['stock_pool'],amount,0,deadline,sender=owner)[0]
            min_out = minimum(quote,args.slippage_bps)
            print(json.dumps({'wallet':i,'input_units':amount,'quoted_output_units':quote,'min_output_units':min_out,'deadline':deadline}),flush=True)
            send(rpc,journal,key,owner,config['router'],calldata(sig,config['strategy_id'],config['stock_pool'],amount,min_out,deadline),0,signer,password,intent)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=DEFAULT_STATE)
    p.add_argument('--config', type=Path)
    commands = p.add_subparsers(dest='command', required=True)
    for name in ('init','fund','buy','sell','status','inspect','plan','reconcile'):
        sub = commands.add_parser(name)
        if name in ('init','fund','buy','sell'):
            sub.add_argument('--execute',action='store_true',help='Explicitly authorize local key creation or transaction signing/broadcast')
            sub.add_argument('--password-file',type=Path)
        if name in ('fund','buy','sell'):
            sub.add_argument('--batch',default=name+'-1')
            sub.add_argument('--wallet',type=int,help='Only this wallet, 1..10; otherwise all ten sequentially')
        if name == 'fund':
            sub.add_argument('--account',default='sandbox-deployer')
            sub.add_argument('--wallet-password-file',type=Path)
            sub.add_argument('--quote',default='1')
            sub.add_argument('--gas',default='0.0002')
        if name in ('buy','sell'):
            sub.add_argument('--max-tax-bps',type=int,default=1000)
            sub.add_argument('--slippage-bps',type=int,default=100)
            sub.add_argument('--deadline-seconds',type=int,default=90)
        if name == 'buy':
            sub.add_argument('--amount',required=True)
        if name == 'sell':
            sub.add_argument('--fraction-bps',type=int,required=True)
        if name == 'reconcile':
            sub.add_argument('--operation',required=True)
            sub.add_argument('--tx-hash',required=True)
    return p


def main():
    args = parser().parse_args()
    try:
        state = args.state.expanduser().absolute()
        require(not any(p.is_symlink() for p in (state,*state.parents)), 'Symlink state paths forbidden')
        require(not state.is_relative_to(REPO) and not any((p/'.git').exists() for p in (state,*state.parents)), 'State and keys must be outside every repository')
        os.umask(0o077)
        state.mkdir(parents=True,exist_ok=True,mode=0o700)
        require(state.stat().st_uid == os.getuid() and state.stat().st_mode & 0o077 == 0, 'State directory must belong to you and have mode 0700')
        lock = state/'.lock'
        require(not lock.is_symlink(),'Symlink lock forbidden')
        with lock.open('a') as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SafetyError('Another process is using this state directory') from None
            run(args,state)
    except (KeyboardInterrupt, EOFError):
        print('STOP: Cancelled. For a transaction command, run status before retrying; do not delete the journal.', file=sys.stderr)
        return 130
    except (SafetyError, KeyError, ValueError, OSError) as error:
        # Never emit subprocess stderr or URL-bearing transport exception details.
        print('STOP: '+(str(error) if isinstance(error,SafetyError) else 'Invalid local configuration or file state'),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
