#!/usr/bin/env python3
"""One bounded, versioned SBOX rehearsal with ten operator-controlled wallets.

Default: print the complete plan offline. --execute is exclusively for the human
operator: unlock once, then run seventeen sequential actions using the audited
wallet CLI. Stable journal batches make resuming idempotent. No funding or retry.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time

import sandbox_wallets as sw

VERSION = 'players-v1'
# These are controlled test roles; late arrivals are time-based, not a dip signal.
# wallet, action, buy USDG or fraction in basis points, role
SCHEDULE = (
    (1, 'buy', '0.5', 'hold'),
    (4, 'buy', '0.25', 'split entry'),
    (7, 'buy', '0.5', 'partial exit'),
    (2, 'buy', '0.5', 'hold'),
    (5, 'buy', '0.25', 'split entry'),
    (8, 'buy', '0.5', 'partial exit'),
    (3, 'buy', '0.5', 'hold'),
    (6, 'buy', '0.25', 'split entry'),
    (4, 'buy', '0.25', 'split entry'),
    (7, 'sell', '5000', 'partial exit'),
    (5, 'buy', '0.25', 'split entry'),
    (9, 'buy', '0.25', 'late arrival'),
    (8, 'sell', '5000', 'partial exit'),
    (6, 'buy', '0.25', 'split entry'),
    (10, 'buy', '0.25', 'late arrival'),
    (9, 'sell', '2500', 'late arrival'),
    (10, 'sell', '2500', 'late arrival'),
)


def step_args(args, index, step, password):
    wallet, action, amount, _ = step
    return sw.parser().parse_args([
        '--state', str(args.state), '--config', str(args.config), action,
        '--wallet', str(wallet), '--batch', f'{VERSION}-{index:02d}',
        '--amount' if action == 'buy' else '--fraction-bps', amount,
        '--slippage-bps', '100', '--max-tax-bps', '1000',
        '--deadline-seconds', '90', '--password-file', str(password), '--execute',
    ])


def intent_for(step):
    _, action, amount, _ = step
    return {'kind': action, 'amount': amount if action == 'buy' else None,
            'fraction_bps': int(amount) if action == 'sell' else None,
            'slippage_bps': 100, 'max_tax_bps': 1000}


def show_plan(args):
    print('CONTROLLED TEST: these ten wallets have one operator; this is not organic trading activity.')
    print(f'{VERSION}: 17 actions; 4.5 USDG total buy input; no extra funding.')
    print('Wallets 1-3: buy 0.5 and hold; 4-6: two buys of 0.25; 7-8: buy 0.5 then sell 50%; 9-10: arrive later, buy 0.25 then sell 25%.')
    print(f'Interval after successful actions: {args.interval}s; slippage 1%; preflight tax cap 10%; transaction deadline 90s.')
    print('Tax cap is a preflight check; on-chain minOut protects the quoted net output. Sales are fractions of the current wallet token balance.')
    for index, (wallet, action, amount, role) in enumerate(SCHEDULE, 1):
        size = amount + ' USDG' if action == 'buy' else f'{int(amount)/100:g}% of current SBOX'
        print(f'{index:02d}. wallet {wallet:02d}: {action} {size} ({role}); batch {VERSION}-{index:02d}')
    if not args.execute:
        print('PLAN ONLY: no RPC, key unlock, signature or transaction. Add --execute locally to run once or resume the same journal.')


def execute_schedule(args, state):
    # Verify the complete target before requesting a password or trusting receipts.
    config = json.loads(sw.safe_file(args.config).read_text())
    rpc = sw.Rpc(os.environ.get('RH_RPC', ''))
    config = sw.validate(rpc, config)
    sw.manifest(state)
    journal = sw.Journal(state, config)
    journal.refresh(rpc)
    journal.unblocked()
    todo = []
    for index, step in enumerate(SCHEDULE, 1):
        key = f'{VERSION}-{index:02d}:{step[0]}:{step[1]}'
        if journal.done(key, intent_for(step)):
            print(f'{key}: already confirmed; skipped')
        else:
            todo.append((index, step))
    if not todo:
        print('All 17 actions are already confirmed. Nothing to sign or replay.')
        return
    with sw.password_file(state, args.password_file, 'Ten wallets') as password:
        for pending_index, (index, step) in enumerate(todo):
            print(f'Running step {index:02d}/17: wallet {step[0]}, {step[1]}', flush=True)
            # The shared implementation independently validates each step, checks
            # exact intent/batch identity and persists before signing. No retries.
            sw.run(step_args(args, index, step, password), state)
            if pending_index + 1 < len(todo) and args.interval:
                time.sleep(args.interval)
    print('Rehearsal complete. Use the read-only chart tool to inspect confirmed fills.')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=sw.DEFAULT_STATE)
    p.add_argument('--config', type=Path, default=sw.REPO / 'data/sbox-multiwallet.json')
    p.add_argument('--interval', type=int, default=15, help='Seconds between successful actions, 0..60')
    p.add_argument('--password-file', type=Path)
    p.add_argument('--execute', action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        sw.require(0 <= args.interval <= 60, '--interval must be 0..60 seconds')
        show_plan(args)
        if not args.execute:
            return 0
        state = args.state.expanduser().absolute()
        sw.require(not any(p.is_symlink() for p in (state, *state.parents)), 'Symlink state paths forbidden')
        sw.require(not state.is_relative_to(sw.REPO) and not any((p/'.git').exists() for p in (state,*state.parents)), 'State and keys must be outside every repository')
        sw.require(state.is_dir(), 'Use the existing funded wallet state directory')
        sw.require(state.stat().st_uid == os.getuid() and state.stat().st_mode & 0o077 == 0, 'State directory must belong to you and have mode 0700')
        args.state = state
        os.umask(0o077)
        lock = state / '.lock'
        sw.require(not lock.is_symlink(), 'Symlink lock forbidden')
        with lock.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise sw.SafetyError('Another process is using this state directory') from None
            execute_schedule(args, state)
    except (KeyboardInterrupt, EOFError):
        print('STOP: Cancelled. Run wallet status before resuming; never delete the journal.', file=sys.stderr)
        return 130
    except (sw.SafetyError, KeyError, ValueError, OSError) as error:
        print('STOP: '+(str(error) if isinstance(error,sw.SafetyError) else 'Invalid local configuration or file state')+'. No later steps were attempted.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
