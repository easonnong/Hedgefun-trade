# Broker vault TVL adapter draft

This is a tested builder, not a published adapter or assurance of listing. No production addresses have been supplied.

After a verified mainnet deployment, a submission wrapper can export `buildAdapter([verifiedVaultAddress])`. Copy the builder into the DefiLlama project directory, add the actual start block/time, and run their adapter harness against real balances. Never use the repository's valueless Robinhood testnet assets as production TVL.

Candidate TVL is `managedBalances()`:

- NVDA: active capital + queued deposits + reserved, unclaimed withdrawals.
- USDG: confirmed rewards that users have not claimed.
- Excluded: broker cash/margin, bank balances, pending report prefunding, unsolicited donations, and bNVDA shares (their backing is already counted).

This is gross on-chain custody. Open option liabilities are off-chain; TVL is not net asset value or proof of solvency. Eligibility of this hybrid RWA model, pending balances and underlying token prices needs DefiLlama review. If a token lacks their price mapping, resolve that mapping; do not hardcode a stock price. Existing protocols' receipt tokens also require their double-counting methodology.

Net option PnL, fees, user yield and broker trading volume are separate datasets. This TVL adapter does not submit any of them. Report hashes do not prove broker activity.

```sh
node --test integrations/defillama/adapter.test.cjs
```

Sources checked during implementation:

- [What to include as TVL](https://docs.llama.fi/list-your-project/what-to-include-as-tvl)
- [SDK adapters](https://docs.llama.fi/list-your-project/how-to-write-an-sdk-adapter)
- [Submission and review](https://docs.llama.fi/list-your-project/submit-a-project)
- [Data definitions](https://docs.llama.fi/analysts/data-definitions)
- [Existing Robinhood chain adapter](https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/projects/panoptic-v2/index.js)
