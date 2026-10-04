// Draft builder, NOT a submitted/listed DefiLlama adapter.
// Put the verified production vault addresses in a thin index.js wrapper.
const address = /^0x[0-9a-fA-F]{40}$/;
function buildAdapter(vaults) {
  if (!Array.isArray(vaults) || !vaults.length || vaults.some(v => !address.test(v) || /^0x0{40}$/i.test(v)))
    throw new Error('Configure verified, deployed mainnet vault addresses. Testnet and empty addresses are not TVL.');
  if (new Set(vaults.map(v => v.toLowerCase())).size !== vaults.length)
    throw new Error('Duplicate vault would double count backing.');
  const calls = vaults.map(target => ({ target }));
  return {
    methodology: 'Counts managed on-chain stock (active, pending and reserved withdrawals) plus confirmed, unclaimed USDG. Excludes provisional report funding, donations, broker margin and receipt shares. Gross custody, not live strategy NAV.',
    robinhood: {
      tvl: async api => {
        const [balances, stocks, usdgs] = await Promise.all([
          api.multiCall({ abi: 'function managedBalances() view returns (uint256 stockAmount, uint256 usdgAmount)', calls }),
          api.multiCall({ abi: 'address:stock', calls }),
          api.multiCall({ abi: 'address:usdg', calls })
        ]);
        vaults.forEach((_, i) => {
          // Return raw amounts. SDK prices assets using chain + token address.
          api.add(stocks[i], balances[i][0]);
          api.add(usdgs[i], balances[i][1]);
        });
      }
    }
  };
}
module.exports = { buildAdapter };
