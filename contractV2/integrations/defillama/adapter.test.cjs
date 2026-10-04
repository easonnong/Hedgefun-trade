const { test } = require('node:test');
const assert = require('node:assert/strict');
const { buildAdapter } = require('./adapter.cjs');
const vault = '0x1111111111111111111111111111111111111111';
test('reject missing and duplicate production addresses', () => {
  for (const config of [[], ['0x' + '0'.repeat(40)], [vault, vault]])
    assert.throws(() => buildAdapter(config));
});
test('count stock and USDG once, retaining raw integer precision', async () => {
  const amounts = [], stock = '0x2222222222222222222222222222222222222222';
  const usdg = '0x3333333333333333333333333333333333333333';
  await buildAdapter([vault]).robinhood.tvl({
    multiCall: async ({ abi, calls }) => {
      assert.deepEqual(calls, [{target: vault}]);
      return abi.includes('managedBalances') ? [['123456789012345678901234', '7000001']] : abi === 'address:stock' ? [stock] : [usdg];
    }, add: (token, amount) => amounts.push([token, amount])
  });
  assert.deepEqual(amounts, [[stock, '123456789012345678901234'], [usdg, '7000001']]);
});
