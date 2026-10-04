import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sandbox_wallets as sw
import sbox_players as players


class PlayerTests(unittest.TestCase):
    def test_fixed_schedule_budget_roles_and_batches(self):
        self.assertEqual(len(players.SCHEDULE),17)
        self.assertEqual(sum(sw.units(amount,6) for _,kind,amount,_ in players.SCHEDULE if kind=='buy'),4_500_000)
        for wallet in range(1,11):
            actions=[(kind,amount) for w,kind,amount,_ in players.SCHEDULE if w==wallet]
            expected=([('buy','0.5')] if wallet<=3 else [('buy','0.25'),('buy','0.25')] if wallet<=6 else [('buy','0.5'),('sell','5000')] if wallet<=8 else [('buy','0.25'),('sell','2500')])
            self.assertEqual(actions,expected)
        args=players.parser().parse_args([])
        batches=[players.step_args(args,i,s,Path('/fake/password')).batch for i,s in enumerate(players.SCHEDULE,1)]
        self.assertEqual(len(set(batches)),17)
        self.assertEqual(batches[0],'players-v1-01')
        self.assertEqual(batches[-1],'players-v1-17')

    def test_default_plan_has_no_network_unlock_or_send(self):
        with patch.object(sw,'Rpc') as rpc,patch.object(sw,'password_file') as password,patch.object(sw,'run') as run,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(players.main([]),0)
        rpc.assert_not_called(); password.assert_not_called(); run.assert_not_called()
        self.assertIn('4.5 USDG',out.getvalue())
        self.assertIn('17. wallet 10: sell 25%',out.getvalue())

    @contextlib.contextmanager
    def environment(self):
        with tempfile.TemporaryDirectory() as raw:
            state=Path(raw).resolve()
            config=state/'config.json'; config.write_text('{}')
            args=players.parser().parse_args(['--state',str(state),'--config',str(config),'--interval','0','--execute'])
            with patch.object(sw,'Rpc') as rpc,patch.object(sw,'validate',return_value={}),patch.object(sw,'manifest'),patch.object(sw.Journal,'refresh'),patch.object(sw,'password_file',return_value=contextlib.nullcontext(state/'password')) as password,contextlib.redirect_stdout(io.StringIO()):
                yield args,state,password

    def test_execution_prompts_once_and_stops_first_failure(self):
        with self.environment() as (args,state,password),patch.object(sw,'run',side_effect=[None,sw.SafetyError('failed')]) as run:
            with self.assertRaisesRegex(sw.SafetyError,'failed'):
                players.execute_schedule(args,state)
            self.assertEqual(password.call_count,1)
            self.assertEqual(run.call_count,2)
            first=run.call_args_list[0].args[0]
            self.assertTrue(first.execute)
            self.assertEqual((first.wallet,first.batch,first.amount),(1,'players-v1-01','0.5'))

    def test_resume_skips_confirmed_steps_and_does_not_replay(self):
        with self.environment() as (args,state,password):
            journal=sw.Journal(state,{})
            for index,step in enumerate(players.SCHEDULE[:4],1):
                journal.ops[f'players-v1-{index:02d}:{step[0]}:{step[1]}']={'status':'confirmed','intent':players.intent_for(step)}
            journal.save()
            with patch.object(sw,'run') as run:
                players.execute_schedule(args,state)
                self.assertEqual(run.call_count,13)
                self.assertEqual(run.call_args_list[0].args[0].batch,'players-v1-05')
            self.assertEqual(password.call_count,1)

    def test_complete_journal_needs_no_password(self):
        with self.environment() as (args,state,password):
            journal=sw.Journal(state,{})
            for index,step in enumerate(players.SCHEDULE,1):
                journal.ops[f'players-v1-{index:02d}:{step[0]}:{step[1]}']={'status':'confirmed','intent':players.intent_for(step)}
            journal.save()
            with patch.object(sw,'run') as run:
                players.execute_schedule(args,state)
            password.assert_not_called(); run.assert_not_called()

    def test_uncertain_previous_send_blocks_before_unlock(self):
        with self.environment() as (args,state,password):
            journal=sw.Journal(state,{})
            journal.ops['previous']={'status':'prepared','intent':{}}
            journal.save()
            with self.assertRaisesRegex(sw.SafetyError,'blocks sending'):
                players.execute_schedule(args,state)
            password.assert_not_called()

    def test_same_state_lock_blocks_concurrent_runner_before_unlock(self):
        with tempfile.TemporaryDirectory() as raw:
            state=Path(raw).resolve()
            with (state/'.lock').open('a') as held:
                players.fcntl.flock(held,players.fcntl.LOCK_EX | players.fcntl.LOCK_NB)
                with patch.object(players,'execute_schedule') as execute,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(players.main(['--state',str(state),'--execute']),1)
                execute.assert_not_called()

    def test_interval_is_bounded_before_side_effects(self):
        for interval in ('-1','61'):
            with patch.object(players,'execute_schedule') as execute,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(players.main(['--interval',interval,'--execute']),1)
            execute.assert_not_called()


if __name__=='__main__': unittest.main()
