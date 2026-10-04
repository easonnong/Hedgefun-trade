import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import sandbox_wallets as sw
import sbox_parallel_players as parallel
from sbox_players import intent_for


def wallets():
    return [{'address':f'0x{i:040x}'} for i in range(1,11)]


class FakeRpc:
    url='https://example.invalid'
    def request(self,method,params):
        if method=='eth_getTransactionCount': return '0x0'
        if method=='eth_getTransactionReceipt': return {'status':'0x1'}
        raise AssertionError(method)


class ParallelTests(unittest.TestCase):
    @contextlib.contextmanager
    def environment(self):
        with tempfile.TemporaryDirectory() as raw:
            state=Path(raw).resolve()
            sw.Journal(state,{}).save()
            lock,stop=threading.RLock(),threading.Event()
            journals={g:parallel.GroupJournal(state,{},g,wallets(),lock,stop) for g in parallel.GROUPS}
            yield state,journals,stop

    def test_fixed_disjoint_budget_and_default_offline(self):
        parallel.check_schedule()
        self.assertEqual(sum(len(s) for s in parallel.GROUPS.values()),17)
        with patch.object(sw,'Rpc') as rpc,patch.object(sw,'password_file') as password,patch.object(parallel,'execute') as execute,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(parallel.main([]),0)
        rpc.assert_not_called();password.assert_not_called();execute.assert_not_called()
        self.assertIn('CURRENT wallet holdings',output.getvalue())
        bad=dict(parallel.GROUPS);bad['late']=((1,'buy','0.25',(0,0)),)
        with patch.object(parallel,'GROUPS',bad),self.assertRaisesRegex(sw.SafetyError,'disjoint'):
            parallel.check_schedule()

    def test_real_send_paths_overlap_and_atomic_merges_lose_no_records(self):
        # Barrier inside cast send proves independent groups reach actual send
        # concurrently, rather than merely dispatching serialized worker threads.
        with self.environment() as (state,journals,stop):
            barrier=threading.Barrier(4,timeout=5)
            def fake_cast(args,**kwargs):
                self.assertEqual(args[0],'send')
                sender=args[args.index('--from')+1]
                barrier.wait()
                return '0x'+f'{int(sender,16):064x}'
            def submit(group):
                step=parallel.GROUPS[group][0]
                sender=wallets()[step[0]-1]['address']
                sw.send(FakeRpc(),journals[group],f'{parallel.batch(group,1)}:{step[0]}:{step[1]}',sender,'0x'+'f'*40,'0x',0,[],state/'password',intent_for(step))
            with patch.object(sw,'cast',side_effect=fake_cast),contextlib.redirect_stdout(io.StringIO()),ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(submit,journals))
            canonical=json.loads((state/'journal.json').read_text())
            self.assertEqual(len(canonical['operations']),4)
            self.assertTrue(all(v['status']=='confirmed' for v in canonical['operations'].values()))
            self.assertEqual(canonical['config'],{})
            self.assertEqual(canonical['version'],1)

    def test_group_cannot_write_foreign_key_or_sender(self):
        with self.environment() as (state,journals,stop):
            j=journals['holders']
            with self.assertRaisesRegex(sw.SafetyError,'unowned'): j.done('parallel-v1-split-01:4:buy',{})
            j.ops['parallel-v1-split-01:4:buy']={'from':wallets()[3]['address']}
            with self.assertRaisesRegex(sw.SafetyError,'another group'): j.save()
            j.ops.clear();j.ops['parallel-v1-holders-01:1:buy']={'from':wallets()[3]['address']}
            with self.assertRaisesRegex(sw.SafetyError,'sender'): j.save()
            self.assertEqual(json.loads((state/'journal.json').read_text())['operations'],{})

    def test_stop_blocks_new_broadcast_but_preserves_inflight_receipt(self):
        with self.environment() as (state,journals,stop):
            j=journals['holders'];sender=wallets()[0]['address']
            def fake_cast(args,**kwargs):
                stop.set()  # Another group fails after this transaction started.
                return '0x'+'a'*64
            with patch.object(sw,'cast',side_effect=fake_cast) as cast,contextlib.redirect_stdout(io.StringIO()):
                sw.send(FakeRpc(),j,'parallel-v1-holders-01:1:buy',sender,'0x'+'f'*40,'0x',0,[],state/'password',{})
                with self.assertRaisesRegex(sw.SafetyError,'stopped'):
                    sw.send(FakeRpc(),journals['split'],'parallel-v1-split-01:4:buy',wallets()[3]['address'],'0x'+'f'*40,'0x',0,[],state/'password',{})
                self.assertEqual(cast.call_count,1)
            self.assertEqual(json.loads((state/'journal.json').read_text())['operations']['parallel-v1-holders-01:1:buy']['status'],'confirmed')

    def test_stop_before_admission_creates_no_prepared_record(self):
        with self.environment() as (state,journals,stop):
            rpc=FakeRpc()
            def nonce_and_stop(method,params):
                if params[-1]=='pending': stop.set()
                return '0x0'
            with patch.object(rpc,'request',side_effect=nonce_and_stop),patch.object(sw,'cast') as cast:
                with self.assertRaisesRegex(sw.SafetyError,'before send admission'):
                    sw.send(rpc,journals['holders'],'parallel-v1-holders-01:1:buy',wallets()[0]['address'],'0x'+'f'*40,'0x',0,[],state/'password',{})
            cast.assert_not_called()
            self.assertEqual(json.loads((state/'journal.json').read_text())['operations'],{})

    def test_stop_after_admission_drains_prepared_send_to_receipt(self):
        with self.environment() as (state,journals,stop):
            j=journals['holders'];original=j.save
            def save_and_stop():
                original();stop.set()
            with patch.object(j,'save',side_effect=save_and_stop),patch.object(sw,'cast',return_value='0x'+'b'*64) as cast,contextlib.redirect_stdout(io.StringIO()):
                sw.send(FakeRpc(),j,'parallel-v1-holders-01:1:buy',wallets()[0]['address'],'0x'+'f'*40,'0x',0,[],state/'password',{})
            self.assertEqual(cast.call_count,1)
            self.assertEqual(json.loads((state/'journal.json').read_text())['operations']['parallel-v1-holders-01:1:buy']['status'],'confirmed')

    def test_resume_worker_skips_confirmed_and_failure_cancels_future_steps(self):
        with self.environment() as (state,journals,stop):
            j=journals['holders'];step=parallel.GROUPS['holders'][0]
            j.ops['parallel-v1-holders-01:1:buy']={'from':wallets()[0]['address'],'intent':intent_for(step),'status':'confirmed'};j.save()
            args=parallel.parser().parse_args(['--state',str(state),'--execute'])
            with patch.object(parallel.random.SystemRandom,'uniform',return_value=0),patch.object(sw,'run',side_effect=sw.SafetyError('failed')) as run,contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(sw.SafetyError,'failed'):
                    parallel.worker(args,state,'holders',j,state/'password',stop)
                self.assertEqual(run.call_count,1)
                self.assertEqual(run.call_args.args[0].wallet,2)
                self.assertEqual(run.call_args.args[0].batch,'parallel-v1-holders-02')
            self.assertTrue(stop.is_set())

    def test_own_pending_blocks_but_other_group_inflight_does_not(self):
        with self.environment() as (state,journals,stop):
            j=journals['holders']
            j.ops['parallel-v1-holders-01:1:buy']={'from':wallets()[0]['address'],'status':'submitted'};j.save()
            with self.assertRaises(sw.SafetyError): j.unblocked()
            journals['split'].unblocked()
            journals['split'].save()
            self.assertIn('parallel-v1-holders-01:1:buy',json.loads((state/'journal.json').read_text())['operations'])

    def test_repeated_interrupts_keep_draining_before_cleanup(self):
        pool=Mock()
        pool.shutdown.side_effect=[KeyboardInterrupt(),KeyboardInterrupt(),None]
        stop=threading.Event()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(parallel.drain_workers(pool,stop))
        self.assertTrue(stop.is_set())
        self.assertEqual(pool.shutdown.call_count,3)
        self.assertEqual(pool.shutdown.call_args.kwargs,{'wait':True,'cancel_futures':True})

    def test_same_root_flock_blocks_before_worker_creation(self):
        with tempfile.TemporaryDirectory() as raw:
            state=Path(raw).resolve()
            with (state/'.lock').open('a') as handle:
                parallel.fcntl.flock(handle,parallel.fcntl.LOCK_EX | parallel.fcntl.LOCK_NB)
                with patch.object(parallel,'execute') as execute,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(parallel.main(['--state',str(state),'--execute']),1)
                execute.assert_not_called()


if __name__=='__main__':unittest.main()
