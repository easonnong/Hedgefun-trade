"""Read a canonical, block-pinned SBOX/NVDA V4 spot observation; never sign."""
from fractions import Fraction

import sandbox_wallets as sw


def spot_price(sqrt_price, token, stock):
    sw.require(0 < sqrt_price < 2**160, 'Uninitialized or invalid V4 price')
    token, stock = sw.address(token), sw.address(stock)
    sw.require(token != stock, 'Pool currencies must differ')
    # sample() checks both currencies have 18 decimals. Currency0/1 are
    # address-sorted; square in integers before taking the exact rational ratio.
    ratio = Fraction(sqrt_price * sqrt_price, 2**192)
    return ratio if int(token,16) < int(stock,16) else 1 / ratio


def sample(rpc, config):
    """Caller first validates config. Return NVDA per SBOX, not USDG or PnL.

    Layout follows vendored v4-core StateLibrary: pools mapping is slot 6,
    Pool.State.slot0 stores sqrtPriceX96 in its low 160 bits.
    """
    header = rpc.request('eth_getBlockByNumber', ['latest', False])
    sw.require(isinstance(header,dict) and sw.HASH.fullmatch(header.get('hash','')),
               'Invalid price observation block')
    number = int(header['number'],16)
    timestamp = int(header['timestamp'],16)
    sw.require(number > 0 and timestamp > 0, 'Invalid price observation time')
    block = hex(number)

    def word(target, signature, *args):
        data = rpc.request('eth_call', [{'to':target, 'data':sw.calldata(signature,*args)}, block])
        sw.require(isinstance(data,str) and len(data)==66 and data.startswith('0x'),
                   'Invalid price observation ABI word')
        return int(data,16)

    pool_id = word(config['hook'],'poolOfTreasury(address)',config['treasury'])
    sw.require(pool_id != 0, 'Treasury has no V4 pool')
    sw.require(word(config['token'],'decimals()') == 18 and
               word(config['stock'],'decimals()') == 18,
               'Spot sampler requires two 18-decimal currencies')
    state_slot = sw.cast(['keccak',f'0x{pool_id:064x}{6:064x}'])
    sw.require(sw.HASH.fullmatch(state_slot) is not None, 'Invalid V4 state slot')
    packed = word(config['pool_manager'],'extsload(bytes32)',state_slot)
    sqrt_price = packed & (2**160-1)
    price = spot_price(sqrt_price,config['token'],config['stock'])
    canonical = rpc.request('eth_getBlockByNumber',[block,False])
    sw.require(isinstance(canonical,dict) and canonical.get('hash')==header['hash'],
               'Price observation block was reorganized; stop and inspect')
    return {'block':number,'timestamp':timestamp,'price':price,
            'block_hash':header['hash'], 'sqrt_price_x96':sqrt_price}
