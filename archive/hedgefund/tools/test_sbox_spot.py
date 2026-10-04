from fractions import Fraction
import unittest
from unittest.mock import patch

import sandbox_wallets as sw
import sbox_spot as spot


LOW='0x'+'1'*40
HIGH='0x'+'2'*40


class SpotTests(unittest.TestCase):
    def test_ordering_and_integer_precision(self):
        self.assertEqual(spot.spot_price(2**97,LOW,HIGH),4)
        self.assertEqual(spot.spot_price(2**97,HIGH,LOW),Fraction(1,4))
        self.assertEqual(spot.spot_price(2**96+1,LOW,HIGH),Fraction((2**96+1)**2,2**192))
        for value in (0,2**160):
            with self.assertRaises(sw.SafetyError):spot.spot_price(value,LOW,HIGH)

    def test_pinned_block_and_low160_only(self):
        class Rpc:
            def __init__(self):self.calls=[]
            def request(self,method,params):
                self.calls.append((method,params))
                if method=='eth_getBlockByNumber':
                    return {'number':'0x20','timestamp':'0x100','hash':'0x'+'a'*64}
                self_outer.assertEqual(params[1],'0x20')
                if params[0]['data']=='decimals()':return f'0x{18:064x}'
                value=99 if params[0]['to']==LOW else (12345<<160)|2**97
                return f'0x{value:064x}'
        self_outer=self
        rpc=Rpc()
        with patch.object(sw,'calldata',side_effect=lambda sig,*args:sig),patch.object(sw,'cast',return_value='0x'+'b'*64) as cast:
            result=spot.sample(rpc,{'hook':LOW,'treasury':HIGH,'pool_manager':HIGH,'token':LOW,'stock':HIGH})
        self.assertEqual(result['price'],4)
        self.assertEqual(result['block'],32)
        self.assertEqual(cast.call_args.args[0],['keccak',f'0x{99:064x}{6:064x}'])
        self.assertEqual(rpc.calls[-1],('eth_getBlockByNumber',['0x20',False]))

    def test_reorg_invalid_abi_and_uninitialized_rejected(self):
        header={'number':'0x20','timestamp':'0x100','hash':'0x'+'a'*64}
        config={'hook':LOW,'treasury':HIGH,'pool_manager':HIGH,'token':LOW,'stock':HIGH}
        cases=[(f'0x{1:064x}',f'0x{2**96:064x}',dict(header,hash='0x'+'b'*64)),
               ('0x12',None,None),(f'0x{0:064x}',None,None),
               (f'0x{1:064x}',f'0x{0:064x}',None)]
        for pool,packed,end in cases:
            with patch.object(sw,'calldata',return_value='0x1234'),patch.object(sw,'cast',return_value='0x'+'b'*64):
                from unittest.mock import Mock
                rpc=Mock();rpc.request.side_effect=[header,pool,f'0x{18:064x}',f'0x{18:064x}',packed,end]
                with self.assertRaises(sw.SafetyError):spot.sample(rpc,config)

    def test_wrong_currency_decimals_rejected(self):
        from unittest.mock import Mock
        rpc=Mock();rpc.request.side_effect=[{'number':'0x20','timestamp':'0x100','hash':'0x'+'a'*64},f'0x{1:064x}',f'0x{18:064x}',f'0x{6:064x}']
        with patch.object(sw,'calldata',return_value='0x1234'),patch.object(sw,'cast') as cast:
            with self.assertRaisesRegex(sw.SafetyError,'18-decimal'):
                spot.sample(rpc,{'hook':LOW,'treasury':HIGH,'pool_manager':HIGH,'token':LOW,'stock':HIGH})
        cast.assert_not_called()


if __name__=='__main__':unittest.main()
