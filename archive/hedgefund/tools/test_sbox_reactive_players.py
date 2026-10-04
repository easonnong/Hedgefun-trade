import contextlib
from fractions import Fraction
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import sandbox_wallets as sw
import sbox_reactive_players as reactive


def wallets():return [{'address':f'0x{i:040x}','keystore':f'wallet{i}.json'} for i in range(1,11)]
def sample(block,ppm=0,timestamp=1000):
    return {'block':block,'timestamp':timestamp,'block_hash':'0x'+f'{block:064x}','price':Fraction(1_000_000+ppm,1_000_000)}
def initial_state():
    return {'last':reactive.pack_sample(sample(1)),'streak':0,'peak':reactive.pack_price(Fraction(1)),'armed':False}


class ReactiveTests(unittest.TestCase):
    @contextlib.contextmanager
    def environment(self):
        with tempfile.TemporaryDirectory() as raw,patch.object(reactive.time,'time',return_value=1000):
            state=Path(raw).resolve();lock=threading.RLock();stop=threading.Event()
            sw.Journal(state,{}).save()
            session=reactive.Session(state,{},wallets(),180,lock,sample(1))
            yield state,lock,stop,session

    def test_schedule_budget_and_default_offline(self):
        reactive.check_schedule()
        self.assertEqual(sum(1 for steps in reactive.GROUPS.values() for s in steps if s[1]=='buy'),8)
        with patch.object(reactive,'spot_sample') as spot,patch.object(sw,'password_file') as password,patch.object(reactive,'execute') as execute,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(reactive.main([]),0)
        spot.assert_not_called();password.assert_not_called();execute.assert_not_called()

    def test_up_flat_up_triggers_chase_and_third_rise_hesitant(self):
        state=initial_state()
        for value in (sample(2,5),sample(3,5),sample(4,10)):
            state=reactive.observe(state,value,Fraction(1),1000)
        self.assertEqual(state['streak'],2)
        self.assertIsNotNone(reactive.signal_for('chase',state,Fraction(1)))
        self.assertIsNone(reactive.signal_for('hesitant',state,Fraction(1)))
        state=reactive.observe(state,sample(5,30),Fraction(1),1000)
        self.assertIsNotNone(reactive.signal_for('hesitant',state,Fraction(1)))
        state=reactive.observe(state,sample(6,29),Fraction(1),1000)
        self.assertEqual(state['streak'],0)

    def test_duplicates_do_not_count_and_reorg_stale_future_fail_closed(self):
        state=reactive.observe(initial_state(),sample(2,5),Fraction(1),1000)
        self.assertIsNone(reactive.observe(state,sample(2,5),Fraction(1),1000))
        self.assertEqual(state['streak'],1)
        for bad in ({**sample(2,5),'block_hash':'0x'+'f'*64},sample(1),sample(3,timestamp=960),sample(3,timestamp=1010)):
            with self.assertRaises(sw.SafetyError):reactive.observe(state,bad,Fraction(1),1000)

    def test_exit_requires_rise_or_armed_drawdown_not_just_falling_price(self):
        state=reactive.observe(initial_state(),sample(2,-100),Fraction(1),1000)
        self.assertIsNone(reactive.signal_for('exit',state,Fraction(1)))
        state=reactive.observe(state,sample(3,40),Fraction(1),1000)
        self.assertTrue(state['armed'])
        self.assertIsNone(reactive.signal_for('exit',state,Fraction(1)))
        state=reactive.observe(state,sample(4,20),Fraction(1),1000)
        self.assertIn('retraced',reactive.signal_for('exit',state,Fraction(1)))
        state=reactive.observe(initial_state(),sample(2,60),Fraction(1),1000)
        self.assertIn('60 ppm',reactive.signal_for('exit',state,Fraction(1)))

    def test_persisted_deadline_baseline_streak_decision_survive_resume(self):
        with self.environment() as (state,lock,stop,session),contextlib.redirect_stdout(io.StringIO()):
            session.update_observation('chase',sample(2,5))
            session.decide('reactive-v1-seed-01:1:buy','seed',None)
            with patch.object(reactive.time,'time',return_value=1100):
                resumed=reactive.Session(state,{},wallets(),180,lock,sample(99,500,timestamp=1100))
            self.assertEqual(resumed.data['deadline'],1180)
            self.assertEqual(resumed.baseline,Fraction(1))
            self.assertEqual(resumed.data['groups']['chase']['streak'],1)
            self.assertEqual(resumed.decision('reactive-v1-seed-01:1:buy')['status'],'decided')
            with self.assertRaises(sw.SafetyError):reactive.Session(state,{},wallets(),300,lock)

    def test_flat_market_expiry_persists_noops_and_discards_queued_decision(self):
        with self.environment() as (state,lock,stop,session),contextlib.redirect_stdout(io.StringIO()):
            for block in (2,3,4):
                updated=session.update_observation('chase',sample(block))
                self.assertIsNone(reactive.signal_for('chase',updated,Fraction(1)))
            session.decide('reactive-v1-seed-01:1:buy','queued seed',None)
            with patch.object(reactive.time,'time',return_value=1181):
                session.finalize_expiry({})
                self.assertFalse(session.decide('reactive-v1-seed-01:1:buy','retry',None))
            data=json.loads(session.path.read_text())
            self.assertEqual(len(data['decisions']),10)
            self.assertTrue(all(d['status']=='noop' for d in data['decisions'].values()))

    def test_expired_send_gate_creates_no_prepared_transaction(self):
        class Rpc:
            url='https://invalid.example'
            def request(self,method,params):return '0x0'
        with self.environment() as (state,lock,stop,session):
            journal=reactive.ReactiveJournal(state,{},'seed',wallets(),lock,stop,session)
            with patch.object(reactive.time,'time',return_value=1181),patch.object(sw,'cast') as cast:
                with self.assertRaisesRegex(sw.SafetyError,'expired before send admission'):
                    sw.send(Rpc(),journal,'reactive-v1-seed-01:1:buy',wallets()[0]['address'],'0x'+'f'*40,'0x',0,[],state/'password',{})
            cast.assert_not_called()
            self.assertEqual(json.loads((state/'journal.json').read_text())['operations'],{})

    def test_worker_persists_decision_before_delegated_action_and_sends_once(self):
        with self.environment() as (state,lock,stop,session):
            journal=reactive.ReactiveJournal(state,{},'chase',wallets(),lock,stop,session)
            args=reactive.parser().parse_args(['--state',str(state),'--execute'])
            class Feed:
                values=iter((sample(2,5),sample(3,10)))
                def after(self,cursor):return next(self.values)
            def run(parsed,*a,**kw):
                self.assertEqual(parsed.amount,'0.1')
                self.assertEqual(session.decision('reactive-v1-chase-01:3:buy')['status'],'decided')
                stop.set()
            with patch.object(sw,'run',side_effect=run) as action,contextlib.redirect_stdout(io.StringIO()):
                reactive.worker(args,state,'chase',journal,session,state/'password',stop,Feed())
            self.assertEqual(action.call_count,1)
            self.assertEqual(session.decision('reactive-v1-chase-01:3:buy')['status'],'confirmed')

    def test_flat_worker_expires_without_forced_trade(self):
        with self.environment() as (state,lock,stop,session):
            journal=reactive.ReactiveJournal(state,{},'chase',wallets(),lock,stop,session)
            args=reactive.parser().parse_args(['--state',str(state),'--execute'])
            class Feed:
                block=1
                def after(self,cursor):
                    self.block+=1
                    if self.block==5:
                        session.monotonic_deadline=0
                        return None
                    return sample(self.block)
            with patch.object(sw,'run') as action:
                reactive.worker(args,state,'chase',journal,session,state/'password',stop,Feed())
            action.assert_not_called()
            session.finalize_expiry({})
            self.assertEqual(session.decision('reactive-v1-chase-01:3:buy')['status'],'noop')

    def test_exit_worker_armed_drawdown_sells_existing_tenth_once(self):
        with self.environment() as (state,lock,stop,session):
            journal=reactive.ReactiveJournal(state,{},'exit',wallets(),lock,stop,session)
            args=reactive.parser().parse_args(['--state',str(state),'--execute'])
            class Feed:
                values=iter((sample(2,40),sample(3,20)))
                def after(self,cursor):return next(self.values)
            def run(parsed,*a,**kw):
                self.assertEqual((parsed.command,parsed.wallet,parsed.fraction_bps),('sell',9,1000))
                self.assertIn('retraced',session.decision('reactive-v1-exit-01:9:sell')['reason'])
                stop.set()
            with patch.object(sw,'run',side_effect=run) as action,contextlib.redirect_stdout(io.StringIO()):
                reactive.worker(args,state,'exit',journal,session,state/'password',stop,Feed())
            self.assertEqual(action.call_count,1)

    def test_feed_rejects_orphaned_persisted_cursor_even_with_newer_canonical_sample(self):
        with self.environment() as (state,lock,stop,session):
            session.update_observation('chase',sample(2,5))
            class Rpc:
                def request(self,method,params):
                    number=int(params[0],16)
                    return {'hash':'0x'+'f'*64 if number==2 else sample(number)['block_hash']}
            feed=reactive.SpotFeed(Rpc(),{},session,stop)
            with self.assertRaisesRegex(sw.SafetyError,'reorganized'):
                feed.check_canonical_history(sample(3,10))
            feed.latest=sample(3,10)
            with self.assertRaisesRegex(sw.SafetyError,'reorganized'):
                feed.check_canonical_history(sample(4,20))

    def test_missing_metadata_with_recorded_reactive_tx_cannot_restart_deadline(self):
        with self.environment() as (state,lock,stop,session):
            session.path.unlink()
            config=state/'config.json';config.write_text('{}')
            journal=sw.Journal(state,{})
            journal.ops['reactive-v1-seed-01:1:buy']={'status':'confirmed'};journal.save()
            args=reactive.parser().parse_args(['--state',str(state),'--config',str(config),'--execute'])
            with patch.object(sw,'Rpc'),patch.object(sw,'validate',return_value={}),patch.object(sw,'manifest',return_value=wallets()),patch.object(sw,'password_file') as password:
                with self.assertRaisesRegex(sw.SafetyError,'metadata is missing'):
                    reactive.execute(args,state)
            password.assert_not_called()
            self.assertFalse(session.path.exists())

    def test_wrong_password_does_not_start_session_clock(self):
        with self.environment() as (state,lock,stop,session):
            session.path.unlink()
            config=state/'config.json';config.write_text('{}')
            args=reactive.parser().parse_args(['--state',str(state),'--config',str(config),'--execute'])
            with patch.object(sw,'Rpc'),patch.object(sw,'validate',return_value={}),patch.object(sw,'manifest',return_value=wallets()),patch.object(sw,'password_file',return_value=contextlib.nullcontext(state/'password')),patch.object(sw,'signer_address',side_effect=sw.SafetyError('wrong password')),patch.object(reactive,'spot_sample') as sample_call:
                with self.assertRaisesRegex(sw.SafetyError,'wrong password'):
                    reactive.execute(args,state)
            sample_call.assert_not_called()
            self.assertFalse(session.path.exists())

    def test_monotonic_clock_bounds_session_if_wall_clock_moves_back(self):
        with self.environment() as (state,lock,stop,session):
            with patch.object(reactive.time,'time',return_value=900),patch.object(reactive.time,'monotonic',return_value=session.monotonic_deadline+1):
                self.assertTrue(session.expired())


if __name__=='__main__':unittest.main()
