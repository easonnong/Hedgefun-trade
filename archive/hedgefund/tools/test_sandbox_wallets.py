import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sandbox_wallets as sw


def addr(n):
    return '0x' + f'{n:040x}'


class FakeRPC:
    def __init__(self):
        self.url = 'https://example.invalid'
        self.chain = sw.CHAIN
        self.wrong = False
        self.receipt = None
    def request(self, method, params):
        if method == 'eth_chainId': return hex(self.chain)
        if method == 'eth_getCode': return '0x1234'
        if method == 'eth_getTransactionCount': return '0x0'
        if method == 'eth_getTransactionReceipt': return self.receipt
        raise AssertionError(method)
    def call(self, target, sig, *args, **kwargs):
        if sig == 'factory()': return [99 if self.wrong else 1]
        if sig == 'usdg()': return [5]
        if sig == 'poolManager()': return [3]
        if sig == 'strategies(uint256)': return [4,9,10,6,8]
        if sig == 'token0()': return [5]
        if sig == 'token1()': return [6]
        if sig == 'v3Factory()': return [11]
        if sig == 'getPool(address,address,uint24)': return [7]
        if sig == 'fee()': return [3000]
        if sig == 'decimals()': return [6 if target == addr(5) else 18]
        raise AssertionError(sig)


def config():
    return dict(chain_id=4663, factory=addr(1),router=addr(2),pool_manager=addr(3),token=addr(4),quote=addr(5),stock=addr(6),stock_pool=addr(7),operator=addr(8),treasury=addr(9),hook=addr(10),strategy_id=0,router_codehash='0x'+'a'*64)


class SafetyTests(unittest.TestCase):
    def test_existing_funding_account_can_have_an_empty_password(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve()
            with patch.object(sw.getpass, 'getpass', return_value=''):
                with sw.password_file(state, None, 'Funding account', allow_empty=True) as password:
                    self.assertEqual(password.read_text(), '')
                    self.assertEqual(password.stat().st_mode & 0o777, 0o600)
                self.assertFalse(password.exists())
                with self.assertRaisesRegex(sw.SafetyError, 'Empty password refused'):
                    with sw.password_file(state, None, 'Ten wallets'):
                        self.fail('New wallet empty password must still be refused')

    def test_empty_password_file_requires_explicit_existing_account_policy(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve(); source = state/'password'
            source.write_text(''); source.chmod(0o600)
            with sw.password_file(state, source, 'Funding account', allow_empty=True) as password:
                self.assertEqual(password, source)
            with self.assertRaisesRegex(sw.SafetyError, 'Empty password refused'):
                with sw.password_file(state, source, 'New wallet keystore', confirm=True):
                    self.fail('Empty new-wallet password file must be refused')
            self.assertTrue(source.exists(), 'Never delete a user-supplied password file')

    def test_wallet_password_error_is_specific_without_exposing_stderr(self):
        failed = SimpleNamespace(returncode=1, stdout='', stderr='Failed to decrypt: MAC mismatch; secret-value https://secret.invalid')
        with patch.object(sw.subprocess, 'run', return_value=failed):
            with self.assertRaises(sw.SafetyError) as caught:
                sw.signer_address(['--account', 'sandbox-deployer'], Path('/password'))
        self.assertIn('Funding account unlock failed', str(caught.exception))
        self.assertIn('original keystore password', str(caught.exception))
        self.assertNotIn('secret-value', str(caught.exception))
        self.assertNotIn('secret.invalid', str(caught.exception))

    def test_unknown_wallet_open_error_does_not_claim_wrong_password(self):
        failed = SimpleNamespace(returncode=1, stdout='', stderr='cannot find /private/path/account secret-data')
        with patch.object(sw.subprocess, 'run', return_value=failed):
            with self.assertRaises(sw.SafetyError) as caught:
                sw.signer_address(['--account', 'sandbox-deployer'], Path('/password'))
        self.assertIn('Could not open/decrypt', str(caught.exception))
        self.assertNotIn('/private/path', str(caught.exception))
        self.assertNotIn('secret-data', str(caught.exception))

    def test_empty_or_mismatched_init_password_creates_no_wallet_directory(self):
        for answers, message in (([''], 'Empty password'), (['example', 'different'], 'do not match')):
            with self.subTest(answers=len(answers)), tempfile.TemporaryDirectory() as d:
                state = Path(d).resolve()
                args = sw.parser().parse_args(['init', '--execute'])
                with patch.object(sw.getpass, 'getpass', side_effect=answers), patch.object(sw, 'cast') as cast:
                    with self.assertRaisesRegex(sw.SafetyError, message):
                        sw.initialize(args, state)
                    cast.assert_not_called()
                self.assertFalse((state/'keystores').exists())
                self.assertFalse((state/'wallets.json').exists())
                self.assertEqual(list(state.glob('.password-*')), [])

    def test_init_reuses_empty_directory_left_by_old_failed_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve()
            folder = state/'keystores'; folder.mkdir(mode=0o700)
            def generate(args, **kwargs):
                self.assertEqual(args[:2], ['wallet', 'new'])
                for i in range(10):
                    (folder/str(i)).write_text('encrypted test fixture')
                return ''
            with patch.object(sw.getpass, 'getpass', side_effect=['example', 'example']), \
                 patch.object(sw, 'cast', side_effect=generate) as cast, \
                 patch.object(sw, 'signer_address', side_effect=[addr(i+1) for i in range(10)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                sw.initialize(sw.parser().parse_args(['init', '--execute']), state)
            self.assertEqual(cast.call_count, 1)
            self.assertEqual(len(sw.manifest(state)), 10)
            self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in folder.iterdir()))
            with self.assertRaisesRegex(sw.SafetyError, 'never overwrite'):
                sw.initialize(sw.parser().parse_args(['init', '--execute']), state)

    def test_partial_key_generation_is_preserved_even_on_interrupt(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve()
            key = state/'keystores'/'existing-key'
            def interrupted(*args, **kwargs):
                key.write_text('encrypted key must survive')
                raise KeyboardInterrupt()
            with patch.object(sw.getpass, 'getpass', side_effect=['example', 'example']), \
                 patch.object(sw, 'cast', side_effect=interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    sw.initialize(sw.parser().parse_args(['init', '--execute']), state)
            self.assertEqual(key.read_text(), 'encrypted key must survive')
            self.assertFalse((state/'wallets.json').exists())
            self.assertEqual(list(state.glob('.password-*')), [])
            with patch.object(sw, 'cast') as cast, patch.object(sw.getpass, 'getpass') as prompt:
                with self.assertRaisesRegex(sw.SafetyError, 'keep them for recovery'):
                    sw.initialize(sw.parser().parse_args(['init', '--execute']), state)
                cast.assert_not_called(); prompt.assert_not_called()
            self.assertEqual(key.read_text(), 'encrypted key must survive')

    def test_init_generation_failure_without_keys_is_retryable(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve()
            with patch.object(sw.getpass, 'getpass', side_effect=['example', 'example']), \
                 patch.object(sw, 'cast', side_effect=sw.SafetyError('generation failed')):
                with self.assertRaisesRegex(sw.SafetyError, 'generation failed'):
                    sw.initialize(sw.parser().parse_args(['init', '--execute']), state)
            self.assertFalse((state/'keystores').exists())
            self.assertFalse((state/'wallets.json').exists())

    def test_init_rejects_symlink_directory_before_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d).resolve(); target = state/'target'; target.mkdir()
            (state/'keystores').symlink_to(target)
            with patch.object(sw.getpass, 'getpass') as prompt:
                with self.assertRaisesRegex(sw.SafetyError, 'Symlink'):
                    sw.initialize(sw.parser().parse_args(['init', '--execute']), state)
                prompt.assert_not_called()
            self.assertTrue(target.is_dir())

    def test_missing_manifest_fails_before_config_rpc_or_password(self):
        with tempfile.TemporaryDirectory() as d:
            args = sw.parser().parse_args(['--config', 'nonexistent.json', 'fund', '--execute'])
            with patch.object(sw, 'Rpc') as rpc, patch.object(sw.getpass, 'getpass') as prompt:
                with self.assertRaisesRegex(sw.SafetyError, 'not initialized'):
                    sw.run(args, Path(d).resolve())
                rpc.assert_not_called(); prompt.assert_not_called()

    def test_ctrl_c_and_eof_exit_cleanly(self):
        for error in (KeyboardInterrupt, EOFError):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as d:
                state = Path(d).resolve(); state.chmod(0o700)
                args = sw.parser().parse_args(['--state', str(state), 'init', '--execute'])
                stderr = io.StringIO()
                with patch.object(sw.argparse.ArgumentParser, 'parse_args', return_value=args), \
                     patch.object(sw, 'run', side_effect=error), contextlib.redirect_stderr(stderr):
                    self.assertEqual(sw.main(), 130)
                self.assertIn('Cancelled', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())

    def test_amount_precision_cap_nan_and_scientific_notation(self):
        self.assertEqual(sw.units('0.5',6,cap=1),500000)
        self.assertEqual(sw.units('1e-6',6),1)
        for value in ('NaN','Infinity','-1','0','0.0000001','1.000001'):
            with self.assertRaises(sw.SafetyError): sw.units(value,6,cap=1)

    def test_minimum_never_zero_or_excess_slippage(self):
        self.assertEqual(sw.minimum(10001,100),9900)
        for output,bps in ((0,100),(1,100),(10,301),(10,-1)):
            with self.assertRaises(sw.SafetyError): sw.minimum(output,bps)

    @patch.object(sw,'cast',return_value='0x'+'a'*64)
    def test_wiring_chain_and_codehash_fail_closed(self,_):
        rpc=FakeRPC()
        self.assertEqual(sw.validate(rpc,config())['token'],addr(4))
        rpc.chain=1
        with self.assertRaisesRegex(sw.SafetyError,'chain'): sw.validate(rpc,config())
        rpc.chain=4663; rpc.wrong=True
        with self.assertRaisesRegex(sw.SafetyError,'Wiring'): sw.validate(rpc,config())
        rpc.wrong=False
        c=config(); c['router_codehash']='0x'+'b'*64
        with self.assertRaisesRegex(sw.SafetyError,'runtime hash'): sw.validate(rpc,c)
        c=config(); c['token']=addr(12)
        with self.assertRaisesRegex(sw.SafetyError,'strategy'): sw.validate(rpc,c)

    def test_every_mutating_command_defaults_to_plan(self):
        for argv in (['init'],['fund'],['buy','--amount','0.5'],['sell','--fraction-bps','5000']):
            self.assertFalse(sw.parser().parse_args(argv).execute)
        with tempfile.TemporaryDirectory() as d, patch.object(sw,'cast') as cast:
            with contextlib.redirect_stdout(io.StringIO()): sw.initialize(sw.parser().parse_args(['init']),Path(d).resolve())
            cast.assert_not_called()
            self.assertFalse((Path(d).resolve()/'keystores').exists())

    def test_journal_blocks_ambiguous_sends_and_validates_batch(self):
        with tempfile.TemporaryDirectory() as d:
            j=sw.Journal(Path(d).resolve(),config())
            j.ops['buy:1']={'status':'prepared','intent':{'amount':'0.5'}}
            j.save()
            j=sw.Journal(Path(d).resolve(),config())
            with self.assertRaisesRegex(sw.SafetyError,'blocks sending'): j.unblocked()
            j.ops['buy:1']['status']='confirmed'
            self.assertTrue(j.done('buy:1',{'amount':'0.5'}))
            with self.assertRaisesRegex(sw.SafetyError,'arguments changed'): j.done('buy:1',{'amount':'1'})

    def test_send_error_persists_prepared_and_never_retries(self):
        with tempfile.TemporaryDirectory() as d:
            j=sw.Journal(Path(d).resolve(),config())
            with patch.object(sw,'cast',side_effect=sw.SafetyError('timeout')) as call:
                with self.assertRaises(sw.SafetyError):
                    sw.send(FakeRPC(),j,'op',addr(8),addr(7),'0x',100,['--account','x'],Path(d).resolve()/'password',{'kind':'gas'})
                self.assertEqual(call.call_count,1)
                argv = call.call_args[0][0]
                self.assertEqual(argv[:3], ['send', addr(7), '0x'])
                self.assertNotIn('--data', argv)
            self.assertEqual(json.loads(j.path.read_text())['operations']['op']['status'],'prepared')
            with self.assertRaises(sw.SafetyError): j.unblocked()

    def test_receipt_refresh_resolves_only_recorded_hash(self):
        rpc=FakeRPC()
        with tempfile.TemporaryDirectory() as d:
            j=sw.Journal(Path(d).resolve(),config()); j.ops['x']={'status':'submitted','hash':'0x'+'1'*64}
            j.refresh(rpc)
            self.assertEqual(j.ops['x']['status'],'submitted')
            rpc.receipt={'status':'0x1','blockNumber':'0x22'}
            j.refresh(rpc)
            self.assertEqual(j.ops['x']['status'],'confirmed')

    def test_reconcile_rejects_unrelated_hash_and_matches_exact_intent(self):
        with tempfile.TemporaryDirectory() as d:
            j=sw.Journal(Path(d).resolve(),config())
            j.ops['op']={'status':'prepared','intent':{},'from':addr(8),'to':addr(7),'nonce':2,'value':10,'data':'0x1234'}
            args=sw.parser().parse_args(['reconcile','--operation','op','--tx-hash','0x'+'1'*64])
            tx={'from':addr(8),'to':addr(7),'nonce':'0x2','value':'0xb','input':'0x1234','chainId':hex(4663)}
            rpc=FakeRPC()
            with patch.object(rpc,'request',return_value=tx):
                with self.assertRaisesRegex(sw.SafetyError,'exact recorded intent'): sw.reconcile(args,rpc,j)
            self.assertEqual(j.ops['op']['status'],'prepared')
            tx['value']='0xa'
            with patch.object(rpc,'request',side_effect=[tx,{'status':'0x1'}]), contextlib.redirect_stdout(io.StringIO()):
                sw.reconcile(args,rpc,j)
            self.assertEqual(j.ops['op']['status'],'confirmed')

    def test_secret_env_not_inherited(self):
        with patch.dict(sw.os.environ,{'ETH_PRIVATE_KEY':'secret','ETH_FROM':addr(99),'RH_RPC':'secret-url','CAST_PASSWORD':'pw','KEEPER_PK':'secret'}):
            env=sw.clean_env()
            self.assertFalse(set(env)&{'ETH_PRIVATE_KEY','ETH_FROM','RH_RPC','CAST_PASSWORD','KEEPER_PK'})

    def test_symlink_secret_denied(self):
        with tempfile.TemporaryDirectory() as d:
            key=Path(d).resolve()/'key'; key.write_text('encrypted'); key.chmod(0o600)
            link=Path(d).resolve()/'link'; link.symlink_to(key)
            with self.assertRaises(sw.SafetyError): sw.safe_file(link,private=True)

if __name__=='__main__': unittest.main()
