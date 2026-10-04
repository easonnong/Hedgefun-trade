#!/usr/bin/env python3
"""Four bounded, concurrent groups of operator-controlled SBOX test wallets.

Default is an offline plan. The operator alone runs --execute. Group workers own
disjoint wallets and sign independently; only durable JSON writes share a lock.
This is a new 4.5 USDG session, not a replay of the original players-v1 schedule.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import fcntl
import json
import os
from pathlib import Path
import random
import signal
import sys
import threading

import sandbox_wallets as sw
from sbox_players import intent_for

VERSION = 'parallel-v1'
# wallet, action, quantity, randomized seconds BEFORE that action.
GROUPS = {
    'holders': ((1,'buy','0.5',(0,5)),(2,'buy','0.5',(15,30)),(3,'buy','0.5',(15,30))),
    'split': ((4,'buy','0.25',(0,5)),(5,'buy','0.25',(5,10)),(6,'buy','0.25',(5,10)),
              (4,'buy','0.25',(30,60)),(5,'buy','0.25',(5,10)),(6,'buy','0.25',(5,10))),
    'partial': ((7,'buy','0.5',(0,5)),(8,'buy','0.5',(5,10)),
                (7,'sell','5000',(20,45)),(8,'sell','5000',(5,10))),
    'late': ((9,'buy','0.25',(45,90)),(10,'buy','0.25',(5,15)),
             (9,'sell','2500',(20,45)),(10,'sell','2500',(5,15))),
}


def batch(group, index):
    return f'{VERSION}-{group}-{index:02d}'


def check_schedule():
    owned = set()
    total = 0
    for steps in GROUPS.values():
        wallets = {step[0] for step in steps}
        sw.require(not owned & wallets, 'Groups must have disjoint wallets')
        owned |= wallets
        for _, action, amount, delay in steps:
            sw.require(action in ('buy','sell') and 0 <= delay[0] <= delay[1] <= 90, 'Invalid bounded schedule')
            if action == 'buy':
                total += sw.units(amount,6,cap=1)
            else:
                sw.require(0 < int(amount) <= 10000, 'Invalid sale fraction')
    sw.require(owned == set(range(1,11)) and total == 4_500_000, 'Unexpected wallet set or 4.5 USDG session budget')


class GroupJournal(sw.Journal):
    """One worker's operation view; merge only owned keys into canonical state."""
    def __init__(self, state, config, group, wallets, write_lock, stop, steps=None, version=VERSION):
        self.write_lock, self.stop = write_lock, stop
        self.allowed = {}
        for index, step in enumerate(GROUPS[group] if steps is None else steps,1):
            key = f'{version}-{group}-{index:02d}:{step[0]}:{step[1]}'
            for suffix in ('',':approve',':reset'):
                self.allowed[key+suffix] = wallets[step[0]-1]['address']
        with write_lock:
            super().__init__(state,config)
            self.ops = {key:value for key,value in self.ops.items() if key in self.allowed}
            self.data['operations'] = self.ops
            self._check_owned()

    def _check_owned(self):
        for key, op in self.ops.items():
            sw.require(key in self.allowed, 'Group attempted to write another group operation')
            sw.require(op.get('from') == self.allowed[key], 'Operation sender is outside the owning wallet')

    def save(self):
        with self.write_lock:
            self._check_owned()
            canonical = json.loads(sw.safe_file(self.path).read_text())
            sw.require(canonical['config'] == self.data['config'], 'Canonical journal config changed')
            canonical['operations'].update(copy.deepcopy(self.ops))
            sw.write_json(self.path,canonical)

    def done(self, key, intent):
        sw.require(key in self.allowed, 'Group attempted an unowned operation')
        return super().done(key,intent)

    def unblocked(self):
        sw.require(not self.stop.is_set(), 'Another group stopped; no new transactions')
        super().unblocked()

    def admit_send(self):
        # This gate runs before durable prepare. After admission the send drains
        # even if another group stops, so a known-unsent entry is never stranded.
        sw.require(not self.stop.is_set(), 'Another group stopped before send admission')


def action_args(args, group, index, step, password):
    wallet,action,amount,_ = step
    return sw.parser().parse_args([
        '--state',str(args.state),'--config',str(args.config),action,
        '--wallet',str(wallet),'--batch',batch(group,index),
        '--amount' if action=='buy' else '--fraction-bps',amount,
        '--slippage-bps','100','--max-tax-bps','1000','--deadline-seconds','90',
        '--password-file',str(password),'--execute',
    ])


def worker(args, state, group, journal, password, stop):
    rng = random.SystemRandom()
    try:
        for index, step in enumerate(GROUPS[group],1):
            key = f'{batch(group,index)}:{step[0]}:{step[1]}'
            if journal.done(key,intent_for(step)):
                print(f'{key}: already confirmed; skipped',flush=True)
                continue
            if stop.wait(rng.uniform(*step[3])):
                return
            journal.unblocked()
            print(f'[{group}] wallet {step[0]} {step[1]} {step[2]}',flush=True)
            sw.run(action_args(args,group,index,step,password),state,journal=journal)
    except BaseException:
        stop.set()
        raise


def execute(args, state):
    config = json.loads(sw.safe_file(args.config).read_text())
    rpc = sw.Rpc(os.environ.get('RH_RPC',''))
    config = sw.validate(rpc,config)
    wallets = sw.manifest(state)
    canonical = sw.Journal(state,config)
    canonical.refresh(rpc)
    canonical.unblocked()  # A prior unknown submission stops all groups at startup.
    lock, stop = threading.RLock(), threading.Event()
    journals = {group:GroupJournal(state,config,group,wallets,lock,stop) for group in GROUPS}
    unfinished = [group for group, journal in journals.items() if any(
        not journal.done(f'{batch(group,i)}:{s[0]}:{s[1]}',intent_for(s))
        for i,s in enumerate(GROUPS[group],1))]
    if not unfinished:
        print('All parallel-v1 actions confirmed; nothing to unlock or replay.')
        return
    with sw.password_file(state,args.password_file,'Ten wallets') as password:
        pool = ThreadPoolExecutor(max_workers=4,thread_name_prefix='sbox-role')
        failure = None
        try:
            futures = []
            for group in unfinished:
                futures.append(pool.submit(worker,args,state,group,journals[group],password,stop))
            for future in as_completed(futures):
                future.result()
        except BaseException as error:
            failure = error
            stop.set()
        finally:
            # Repeated Ctrl-C must not remove the shared password or release the
            # root state lock while a worker is still submitting/recording a tx.
            interrupted = drain_workers(pool,stop)
            if interrupted and failure is None:
                failure = KeyboardInterrupt()
        if failure is not None:
            raise failure
    print('All four groups finished. Inspect canonical journal and chart for actual fills.')


def drain_workers(pool, stop):
    interrupted = False
    def defer_interrupt(signum, frame):
        nonlocal interrupted
        stop.set()
        interrupted = True
    # Defer SIGINT while joining: repeated interrupts must not unwind Thread.join
    # or the password/lock contexts. The flag is surfaced after all workers drain.
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGINT,defer_interrupt)
    try:
        while True:
            try:
                pool.shutdown(wait=True,cancel_futures=True)
                return interrupted
            except KeyboardInterrupt:
                stop.set()
                interrupted = True
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT,previous)


def show_plan():
    print('CONTROLLED TEST: four independent concurrent groups, ten wallets owned by one operator; not organic market activity.')
    print('New parallel-v1 session: 17 actions, 4.5 USDG total buys, no funding. Prior players-v1 session is separate.')
    print('1% slippage; 10% preflight tax cap; 90-second deadlines. Sell fractions use CURRENT wallet holdings, including earlier sessions.')
    for group,steps in GROUPS.items():
        print(f'[{group}]')
        for index,(wallet,action,amount,delay) in enumerate(steps,1):
            size = amount+' USDG' if action=='buy' else str(int(amount)/100)+'% SBOX'
            print(f'  {batch(group,index)}: wait {delay[0]}-{delay[1]}s, wallet {wallet} {action} {size}')
    print('Groups overlap; each group is sequential. First failure stops new actions; already in-flight submissions finish recording. Stable batches resume without replay.')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,default=sw.DEFAULT_STATE)
    p.add_argument('--config',type=Path,default=sw.REPO/'data/sbox-multiwallet.json')
    p.add_argument('--password-file',type=Path)
    p.add_argument('--execute',action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        check_schedule()
        show_plan()
        if not args.execute:
            print('PLAN ONLY: no network, key unlock, signing or transactions.')
            return 0
        state=args.state.expanduser().absolute()
        sw.require(not any(p.is_symlink() for p in (state,*state.parents)), 'Symlink state paths forbidden')
        sw.require(not state.is_relative_to(sw.REPO) and not any((p/'.git').exists() for p in (state,*state.parents)), 'State and keys must be outside every repository')
        sw.require(state.is_dir() and state.stat().st_uid==os.getuid() and state.stat().st_mode & 0o077==0,'Use the existing funded state directory with mode 0700')
        args.state=state
        os.umask(0o077)
        lock=state/'.lock'
        sw.require(not lock.is_symlink(),'Symlink lock forbidden')
        with lock.open('a') as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise sw.SafetyError('Another process is using this state; wait for it to finish') from None
            execute(args,state)
    except (KeyboardInterrupt,EOFError):
        print('STOP: cancelled after joining workers. Run status before resuming; do not delete the journal.',file=sys.stderr)
        return 130
    except (sw.SafetyError,KeyError,ValueError,OSError) as error:
        print('STOP: '+(str(error) if isinstance(error,sw.SafetyError) else 'Invalid local configuration or file state'),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
