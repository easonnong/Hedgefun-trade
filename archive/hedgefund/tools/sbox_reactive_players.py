#!/usr/bin/env python3
"""A finite, price-reactive rehearsal: at most 0.8 USDG new buys.

Default: offline plan. The human operator alone supplies --execute and the wallet
password. Eight wallets can buy 0.1 each; two can sell 10% of existing holdings.
Signals refer to spot movement, not profit after tax. Untriggered actions expire.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from fractions import Fraction
import fcntl
import json
import os
from pathlib import Path
import random
import sys
import threading
import time

import sandbox_wallets as sw
from sbox_parallel_players import GroupJournal, drain_workers
from sbox_players import intent_for

VERSION='reactive-v1'
GROUPS={
    'seed': ((1,'buy','0.1',(5,15)),(2,'buy','0.1',(5,15))),
    'chase': tuple((w,'buy','0.1',(2,4)) for w in (3,4,5)),
    'hesitant': tuple((w,'buy','0.1',(2,4)) for w in (6,7,8)),
    'exit': tuple((w,'sell','1000',(2,4)) for w in (9,10)),
}


def check_schedule():
    seen=set();total=0
    for steps in GROUPS.values():
        for wallet,kind,amount,delay in steps:
            sw.require(len(delay)==2 and all(type(v) is int for v in delay) and 0<=delay[0]<=delay[1]<=90,'Invalid bounded observation delay')
            sw.require(wallet not in seen,'Reactive wallets must be disjoint with one action each')
            seen.add(wallet)
            sw.require((1<=wallet<=8 and kind=='buy' and amount=='0.1') or
                       (wallet in (9,10) and kind=='sell' and amount=='1000'),'Unexpected reactive action')
            if kind=='buy':total+=sw.units(amount,6)
    sw.require(seen==set(range(1,11)) and total==800_000,'Reactive buy budget must be exactly 0.8 USDG maximum')


def batch(group,index):
    return f'{VERSION}-{group}-{index:02d}'


def key_for(group,index,step):
    return f'{batch(group,index)}:{step[0]}:{step[1]}'


def pack_price(price):
    return {'n':str(price.numerator),'d':str(price.denominator)}


def unpack_price(price):
    return Fraction(int(price['n']),int(price['d']))


def pack_sample(value):
    return {**value,'price':pack_price(value['price'])}


def validate_sample(value, now):
    sw.require(type(value['block']) is int and type(value['timestamp']) is int,'Invalid observation block or timestamp')
    sw.require(sw.HASH.fullmatch(value['block_hash']),'Invalid observation hash')
    sw.require(isinstance(value['price'],Fraction) and value['price']>0,'Positive rational spot price required')
    sw.require(now-30 <= value['timestamp'] <= now+5,'Spot observation is stale or future-dated')


def observe(previous, observation, baseline, now):
    """Return persisted observation state; duplicate blocks never add momentum."""
    validate_sample(observation,now)
    last=previous['last']
    if observation['block']==last['block']:
        sw.require(observation['block_hash']==last['block_hash'],'Same-height reorg; stop rather than reuse momentum')
        return None
    sw.require(observation['block']>last['block'],'Regressing block; stop rather than reuse momentum')
    sw.require(observation['timestamp']>=last['timestamp'],'Regressing chain timestamp')
    price=observation['price']
    prior=unpack_price(last['price'])
    # Flat observations neither add nor erase a run of positive price changes.
    streak=previous['streak']+1 if price>prior else (previous['streak'] if price==prior else 0)
    peak=max(unpack_price(previous['peak']),price)
    armed=previous['armed'] or price/baseline-1>=Fraction(30,1_000_000)
    return {'last':pack_sample(observation),'streak':streak,'peak':pack_price(peak),'armed':armed}


def signal_for(group,state,baseline):
    price=unpack_price(state['last']['price'])
    rise=price/baseline-1
    if group=='chase' and state['streak']>=2 and rise>=Fraction(10,1_000_000):
        return 'two positive price changes without a drop and spot rise >= 10 ppm'
    if group=='hesitant' and state['streak']>=3 and rise>=Fraction(30,1_000_000):
        return 'three positive price changes without a drop and spot rise >= 30 ppm'
    if group=='exit':
        if rise>=Fraction(60,1_000_000):
            return 'spot rise >= 60 ppm (not after-tax profit)'
        peak=unpack_price(state['peak'])
        if state['armed'] and 1-price/peak>=Fraction(15,1_000_000):
            return 'armed at +30 ppm; retraced >= 15 ppm from observed peak'
    return None


class Session:
    def __init__(self,state,config,wallets,duration,lock,initial=None):
        self.path=state/(VERSION+'.json')
        self.lock=lock
        with lock:
            if self.path.exists():
                self.data=json.loads(sw.safe_file(self.path).read_text())
                sw.require(self.data['version']==VERSION and self.data['config']==config and
                           self.data['wallets']==[w['address'] for w in wallets] and self.data['duration']==duration,
                           'Reactive session pins changed; baseline and deadline may not be reset')
            else:
                sw.require(initial is not None,'Initial spot observation required')
                now=int(time.time());validate_sample(initial,now)
                packed=pack_sample(initial)
                self.data={'version':VERSION,'config':config,'wallets':[w['address'] for w in wallets],
                           'duration':duration,'started_at':now,'deadline':now+duration,'chain_deadline':initial['timestamp']+duration,'baseline':packed,
                           'groups':{g:{'last':copy.deepcopy(packed),'streak':0,'peak':pack_price(initial['price']),'armed':False} for g in GROUPS},'decisions':{}}
                self.save()
        sw.require(self.data['deadline']==self.data['started_at']+duration and
                   self.data['chain_deadline']==self.data['baseline']['timestamp']+duration,'Corrupt persisted deadline')
        self.baseline=unpack_price(self.data['baseline']['price'])
        self.monotonic_deadline=time.monotonic()+min(duration,max(0,self.data['deadline']-time.time()))

    def save(self):
        # Every caller holds the shared RLock; canonical journal uses the same lock.
        sw.write_json(self.path,self.data)

    def expired(self):
        return (time.time()>=self.data['deadline'] or time.monotonic()>=self.monotonic_deadline or
                any(g['last']['timestamp']>=self.data['chain_deadline'] for g in self.data['groups'].values()))

    def decision(self,key):
        with self.lock:
            return copy.deepcopy(self.data['decisions'].get(key))

    def update_observation(self,group,value):
        with self.lock:
            updated=observe(self.data['groups'][group],value,self.baseline,time.time())
            if updated is None:
                return None
            self.data['groups'][group]=updated
            self.save()
            return copy.deepcopy(updated)

    def decide(self,key,reason,observation):
        with self.lock:
            if self.expired():
                return False
            if key not in self.data['decisions']:
                self.data['decisions'][key]={'status':'decided','reason':reason,'decided_at':int(time.time()),'observation':copy.deepcopy(observation)}
                self.save()  # Durable decision before the shared signing path.
                print(f'SIGNAL {key}: {reason}',flush=True)
            return self.data['decisions'][key]['status']=='decided'

    def confirmed(self,key):
        with self.lock:
            decision=self.data['decisions'].setdefault(key,{})
            decision['status']='confirmed';self.save()

    def finalize_expiry(self,operations):
        with self.lock:
            if not self.expired():
                return
            for group,steps in GROUPS.items():
                for index,step in enumerate(steps,1):
                    key=key_for(group,index,step)
                    op=operations.get(key)
                    status=op['status'] if op else None
                    if status=='confirmed':
                        self.data['decisions'].setdefault(key,{})['status']='confirmed'
                    elif status in ('prepared','submitted','reverted'):
                        self.data['decisions'].setdefault(key,{})['status']='unresolved' if status!='reverted' else 'reverted'
                    else:
                        entry=self.data['decisions'].setdefault(key,{})
                        entry.update(status='noop',reason='session expired before trade admission')
            self.save()


class ReactiveJournal(GroupJournal):
    def __init__(self,state,config,group,wallets,lock,stop,session):
        self.session=session
        super().__init__(state,config,group,wallets,lock,stop,steps=GROUPS[group],version=VERSION)

    def admit_send(self):
        super().admit_send()
        sw.require(not self.session.expired(),'Reactive session expired before send admission')


def action_args(args,group,index,step,password):
    wallet,kind,amount,_=step
    return sw.parser().parse_args(['--state',str(args.state),'--config',str(args.config),kind,
        '--wallet',str(wallet),'--batch',batch(group,index),'--amount' if kind=='buy' else '--fraction-bps',amount,
        '--slippage-bps','100','--max-tax-bps','1000','--deadline-seconds','90','--password-file',str(password),'--execute'])


def spot_sample(rpc,config):
    from sbox_spot import sample
    return sample(rpc,config)


def worker(args,state,group,journal,session,password,stop,feed):
    rng=random.SystemRandom()
    try:
        for index,step in enumerate(GROUPS[group],1):
            key=key_for(group,index,step)
            if journal.done(key,intent_for(step)):
                session.confirmed(key);continue
            while not stop.is_set() and not session.expired():
                decision=session.decision(key)
                if decision and decision['status']=='noop':
                    break
                if decision and decision['status']=='decided':
                    sw.run(action_args(args,group,index,step,password),state,journal=journal)
                    session.confirmed(key)
                    break
                if group=='seed':
                    remaining=max(0,session.data['deadline']-time.time())
                    if stop.wait(min(rng.uniform(*step[3]),remaining)) or session.expired():
                        return
                    # Seed actions are the only unconditional small buys.
                    session.decide(key,'bounded seed buy after stagger',None)
                else:
                    with session.lock:
                        cursor=copy.deepcopy(session.data['groups'][group]['last'])
                    value=feed.after(cursor)
                    if value is None:
                        return
                    updated=session.update_observation(group,value)
                    if updated is not None:
                        reason=signal_for(group,updated,session.baseline)
                        if reason:
                            session.decide(key,reason,updated)
    except BaseException:
        stop.set();raise


class SpotFeed:
    """One canonical sampler fans each observation out to independent workers."""
    def __init__(self,rpc,config,session,stop):
        self.rpc,self.config,self.session,self.stop=rpc,config,session,stop
        self.condition=threading.Condition()
        self.latest=None
        self.failure=None

    def check_canonical_history(self,observation):
        history=[self.session.data['baseline']]
        if self.latest is not None:
            history.append(self.latest)
        with self.session.lock:
            history.extend(copy.deepcopy(g['last']) for g in self.session.data['groups'].values())
        history.append(observation)
        checked=set()
        for item in history:
            pair=(item['block'],item['block_hash'])
            if pair in checked:continue
            checked.add(pair)
            header=self.rpc.request('eth_getBlockByNumber',[hex(item['block']),False])
            sw.require(header and header['hash']==item['block_hash'],'Observed price history was reorganized; stop before using momentum')

    def poll(self):
        rng=random.SystemRandom()
        try:
            while not self.stop.is_set() and not self.session.expired():
                if self.stop.wait(rng.uniform(2,4)): return
                if self.session.expired(): return
                observation=spot_sample(self.rpc,self.config)
                validate_sample(observation,time.time())
                self.check_canonical_history(observation)
                with self.condition:
                    self.latest=observation
                    self.condition.notify_all()
        except BaseException as error:
            self.failure=error;self.stop.set()
            with self.condition:self.condition.notify_all()
            raise
        finally:
            with self.condition:self.condition.notify_all()

    def after(self,cursor):
        with self.condition:
            while not self.session.expired():
                if self.failure is not None:raise self.failure
                if self.stop.is_set():return None
                if self.latest is not None:
                    sw.require(self.latest['block']>=cursor['block'],'Sampler block regressed')
                    if self.latest['block']>cursor['block'] or self.latest['block_hash']!=cursor['block_hash']:
                        return copy.deepcopy(self.latest)
                self.condition.wait(timeout=1)
        return None


def session_journals(state,config,wallets,lock,stop,session):
    journals={g:ReactiveJournal(state,config,g,wallets,lock,stop,session) for g in GROUPS}
    unfinished=[g for g in GROUPS if any(not journals[g].done(key_for(g,i,s),intent_for(s)) and
                (session.decision(key_for(g,i,s)) or {}).get('status')!='noop' for i,s in enumerate(GROUPS[g],1))]
    return journals,unfinished


def execute(args,state):
    config=json.loads(sw.safe_file(args.config).read_text())
    rpc=sw.Rpc(os.environ.get('RH_RPC',''));config=sw.validate(rpc,config)
    wallets=sw.manifest(state)
    canonical=sw.Journal(state,config);canonical.refresh(rpc);canonical.unblocked()
    lock,stop=threading.RLock(),threading.Event()
    session=None
    if (state/(VERSION+'.json')).exists():
        session=Session(state,config,wallets,args.duration,lock)
        # Verify every persisted cursor before a queued decision can resume.
        SpotFeed(rpc,config,session,stop).check_canonical_history(session.data['baseline'])
        if session.expired():
            session.finalize_expiry(canonical.ops)
            print('Persisted deadline passed; queued or untriggered actions are no-ops. No unlock or new deadline.')
            return
        journals,unfinished=session_journals(state,config,wallets,lock,stop,session)
        if not unfinished:
            print('Reactive actions completed; nothing to unlock or replay.');return
    if session is None:
        sw.require(not any(key.startswith(VERSION+'-') for key in canonical.ops),
                   'Reactive transactions exist but session metadata is missing; restore metadata instead of resetting deadline')
    failure=None
    with sw.password_file(state,args.password_file,'Ten wallets') as password:
        if session is None:
            # Verify decryption before creating the immutable clock: a mistyped
            # password must not consume this one-shot session's observation window.
            for wallet in wallets:
                signer=['--keystore',str(state/'keystores'/wallet['keystore'])]
                sw.require(sw.signer_address(signer,password)==wallet['address'],'Wallet/keystore mismatch before session start')
            session=Session(state,config,wallets,args.duration,lock,spot_sample(rpc,config))
            journals,unfinished=session_journals(state,config,wallets,lock,stop,session)
        print(f'Reactive deadline: {session.data["deadline"]} Unix seconds; baseline block {session.data["baseline"]["block"]}.',flush=True)
        feed=SpotFeed(rpc,config,session,stop)
        pool=ThreadPoolExecutor(max_workers=5,thread_name_prefix='sbox-reactive')
        try:
            sampler=pool.submit(feed.poll)
            futures=[]
            for group in unfinished:
                futures.append(pool.submit(worker,args,state,group,journals[group],session,password,stop,feed))
            for future in as_completed(futures):future.result()
            stop.set()
            sampler.result()
        except BaseException as error:
            failure=error;stop.set()
        finally:
            interrupted=drain_workers(pool,stop)
            if interrupted and failure is None:failure=KeyboardInterrupt()
            final=sw.Journal(state,config)
            session.finalize_expiry(final.ops)
        if failure is not None:raise failure
    counts={status:sum(d['status']==status for d in session.data['decisions'].values()) for status in ('confirmed','noop','unresolved')}
    print(f'Reactive session finished: {counts}. Details in reactive-v1.json and canonical transaction journal.')


def show_plan(duration):
    print('CONTROLLED PRICE-REACTIVE TEST: one operator owns all ten wallets; no promise of FOMO, organic demand or profit.')
    print(f'reactive-v1: persisted {duration}-second deadline; maximum new buys 0.8 USDG, one buy per wallet 1-8 at 0.1 each.')
    print('Seed1-2: buy0.1 each, stagger5-15s. Chase3-5: 2 positive price changes without a drop and +10ppm vs baseline.')
    print('Hesitant6-8: 3 positive price changes without a drop and +30ppm. Exit9-10: sell10% EXISTING holdings at +60ppm, or arm+30ppm then retrace15ppm from peak.')
    print('One shared sampler observes every2-4s on distinct canonical blocks; flat prices preserve but do not increment momentum. Spot thresholds are not after-tax profits. 1% slippage,10% tax precheck,90s transaction deadlines.')
    print('No trigger => no trade; expiry discards queued unsent decisions. Resume preserves baseline/deadline and fixed batches. Admitted transactions still drain.')


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,default=sw.DEFAULT_STATE)
    p.add_argument('--config',type=Path,default=sw.REPO/'data/sbox-multiwallet.json')
    p.add_argument('--duration',type=int,default=180)
    p.add_argument('--password-file',type=Path)
    p.add_argument('--execute',action='store_true')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        check_schedule()
        sw.require(1<=args.duration<=300,'Session duration must be 1..300 seconds')
        show_plan(args.duration)
        if not args.execute:
            print('PLAN ONLY: no RPC, keys or transactions.');return 0
        state=args.state.expanduser().absolute()
        sw.require(not any(p.is_symlink() for p in (state,*state.parents)),'Symlink state paths forbidden')
        sw.require(not state.is_relative_to(sw.REPO) and not any((p/'.git').exists() for p in (state,*state.parents)),'State must be outside every repository')
        sw.require(state.is_dir() and state.stat().st_uid==os.getuid() and state.stat().st_mode&0o077==0,'Use existing funded state directory mode0700')
        args.state=state;os.umask(0o077)
        lock=state/'.lock';sw.require(not lock.is_symlink(),'Symlink lock forbidden')
        with lock.open('a') as handle:
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise sw.SafetyError('Another process is using this state') from None
            execute(args,state)
    except (KeyboardInterrupt,EOFError):
        print('STOP: cancelled after draining workers. Preserve journal and session metadata before resuming.',file=sys.stderr);return 130
    except (sw.SafetyError,KeyError,ValueError,OSError) as error:
        print('STOP: '+(str(error) if isinstance(error,sw.SafetyError) else 'Invalid local state or configuration'),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
