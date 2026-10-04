> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Mutations run by the round-4 claims lane

Audited tip: `codex/v2-strategy-engine` @ `5aedceb`. Each mutation was applied to a clean `src/`, the V2 subset
(`forge test --match-path 'test/V2*'`: 28 suites, 184 passed / 17 skipped on the unmutated tip) was run, the
result recorded, and `src/` restored with `git checkout -- src`. The subset is sound for these mutations: the only
test files that import anything under `src/v2/` are `test/V2*.t.sol` and `test/StrategyPolicyAdversarialMocks.t.sol`,
and the latter never touches the mutated contracts (it exercises the mock policies directly). Two mutations were
re-run against the full suite (`forge test`, 104 suites) as a control and gave the same verdicts: `E01-nonce` and
`D01-registerPolicy-owner` both left all 1,474 tests passing (52 skipped), exactly as on the unmutated tip.

The tests that turn the GREEN rows red are in [`AuditClaims4.t.sol`](./AuditClaims4.t.sol) (13 tests, all passing on
the unmutated tip; `./run.sh` stages and runs them). Each test names the mutation it catches.

**GREEN** means every test still passed: the guard is not pinned by any test. **RED** names the tests that caught it.

To replay: `git checkout 5aedceb`, `git apply diffs/<name>.diff` (the same diffs as below, as files), `forge test --match-path 'test/V2*'`, `git checkout -- src`.

| # | mutation | property it breaks | result | tests that caught it |
|---|---|---|---|---|
| 1 | `E01-nonce` | engine checks the current strategy nonce on every execution | **GREEN** | — |
| 2 | `E02-confighash` | engine checks the domain-separated config hash on every execution | **RED (1 failed)** | test_wrongCommitmentAndExcessiveAmountBothFailClosedAtTheCore() |
| 3 | `E03-codehash-exec` | engine re-checks the policy runtime codehash on every execution | **GREEN** | — |
| 4 | `E04-gas` | policy call gas is bounded by the registered maxGas | **GREEN** | — |
| 5 | `E05-retsize` | exact 160-byte returndata size is enforced | **RED (1 failed)** | test_hugePolicyReturndataIsRejectedBeforeCopyOrStateChange() |
| 6 | `E06-health` | execute refuses when health() is not ok | **GREEN** | — |
| 7 | `E07-live` | execute refuses when the stock oracle is not live | **GREEN** | — |
| 8 | `E08-capability` | engine enforces SPOT_BUY / SPOT_SELL capability at execution | **GREEN** | — |
| 9 | `E09-cooldown` | engine enforces the cooldown independently of the policy | **RED (1 failed)** | test_cooldownAndDailyCapUseCumulativeActualTurnover() |
| 10 | `E10-direction` | engine enforces target/deadband direction (sell only above upper band, buy only below lower band) | **GREEN** | — |
| 11 | `E11-percall` | engine caps each action at maxTradeUsdg | **RED (2 failed)** | test_cooldownAndDailyCapUseCumulativeActualTurnover()<br> test_wrongCommitmentAndExcessiveAmountBothFailClosedAtTheCore() |
| 12 | `E12-daily` | engine caps cumulative turnover per UTC epoch at maxDailyTurnoverUsdg | **RED (1 failed)** | test_cooldownAndDailyCapUseCumulativeActualTurnover() |
| 13 | `E13-minlot-actual` | actual turnover below minLotUsdg reverts atomically (dust fill cannot advance nonce/cooldown) | **RED (4 failed)** | [FAIL: invariant_handlerChecksCannotFailSilently replay failure]<br> test_handlerCoversSubMinFailureAndExactBoundarySuccess()<br> test_shortBuyBelowMinLotRollsBackWithoutConsumingStrategyState()<br> test_shortSellBelowMinLotRollsBackWithoutConsumingStrategyState() |
| 14 | `E14-daily-post` | post-fill check that actual turnover does not exceed the remaining daily budget | **GREEN** | — |
| 15 | `E15-options-cap` | spot engine rejects every non-spot capability bit in its constructor | **RED (3 failed)** | test_buybackCapabilityCannotEnterRebalanceEngine()<br> test_futureUnknownCapabilityFailsClosedInsideSpotEngine()<br> test_overBroadKindCannotSmuggleOptionsCapabilityIntoSpotEngine() |
| 16 | `E16-reserved-bits` | engine rejects reserved config bits (words[0] >> 64) | **RED (1 failed)** | test_coreRejectsReservedConfigBitsEvenWhenPolicyWouldIgnoreThem() |
| 17 | `E17-config-bounds` | engine enforces target/deadband/cooldown/maxTrade<=sellChunk/maxDaily>=maxTrade bounds at construction | **GREEN** | — |
| 18 | `E18-action-range` | engine rejects an out-of-range action word before use | **GREEN** | — |
| 19 | `E19-call-not-staticcall` | policy is invoked with STATICCALL (state writes trap) | **RED (1 failed)** | test_staticcallTrapsPolicyStateWrites() |
| 20 | `E20-book-in-execute` | execute books newly arrived stock before observing (donations become part of the next observation) | **GREEN** | — |
| 21 | `E21-preview-minlot` | preview does not claim a below-minimum lot is executable | **RED (1 failed)** | test_previewDoesNotClaimDustBelowTheCoreMinimumIsExecutable() |
| 22 | `E22-preswap-minlot` | pre-swap minimum-lot gate on the offered amount | **GREEN** | — |
| 23 | `E23-inventory-offered` | inventory is debited by the actual fill, not the offered amount | **RED (1 failed)** | testFuzz_shortSellFillUsesOnlyActualInput(uint16) |
| 24 | `E24-enabled-both` | a disabled policy cannot launch a treasury whose salt was configured before the disable (constructor + _code) | **GREEN** | — |
| 25 | `D01-registerPolicy-owner` | only the factory owner may register a policy | **GREEN** | — |
| 26 | `D02-registerEngineKind-owner` | only the factory owner may register an engine kind | **GREEN** | — |
| 27 | `D03-disablePolicy-owner` | only the factory owner may disable a policy | **GREEN** | — |
| 28 | `D04-registerKind-owner` | only the factory owner may register a legacy kind (control: covered by V2StrategyKinds) | **RED (1 failed)** | test_onlyFactoryOwnerRegistersAKindAndKindsAreWriteOnce() |
| 29 | `D05-deploy-onlyFactory` | only the bound factory may deploy a treasury | **GREEN** | — |
| 30 | `D06-deploy-introspection` | deploy verifies the deployed engine's version, policy id and config hash | **GREEN** | — |
| 31 | `D07-registerPolicy-bounds` | registerPolicy enforces maxGas/maxReturnBytes/manifest-hash bounds | **GREEN** | — |
| 32 | `D08-setEngineConfig-capsubset` | setEngineConfig rejects a policy whose capabilities exceed the kind's | **RED (2 failed)** | test_optionsCapabilityCannotEnterTheSpotEngine()<br> test_spotOnlyKindRejectsPolicyContainingAnyOptionsCapabilityAtConfiguration() |
| 33 | `D09-setEngineConfig-codehash` | setEngineConfig rejects a policy whose runtime code changed | **RED (1 failed)** | test_policyCodeReplacementFailsBeforePredictionOrLaunch() |
| 34 | `D10-policy-dup` | policy registrations are append-only (a key cannot be re-registered) | **GREEN** | — |
| 35 | `D11-setStrategyKind-engine` | the legacy setStrategyKind cannot select an engine kind without a config | **RED (1 failed)** | test_engineSelectionRestatesQuoteAndLegacySetterCannotSkipConfig() |
| 36 | `D12-policyMetadata-consistency` | registerPolicy rejects a policy whose metadata is zero | **GREEN** | — |
| 37 | `V01-no-retry` | a refused stock-fee credit is parked and retried; the token burn still completes | **RED (1 failed)** | test_stockCreditFailureParksFeeButStillBurnsTokenFee() |
| 38 | `V02-no-clear` | a delivered stock fee is cleared from the pending ledger (no double credit / stuck retry) | **RED (1 failed)** | testFuzz_threeActorSequencesConserveBeforeAndAfterGraduation(uint256,bool,bool) |
| 39 | `V03-selfcall` | creditPendingStock is self-call only | **RED (1 failed)** | test_callbackCannotBeCalledByOutsider() |
| 40 | `F01-spike` | graduated V2 pools freeze spikeBps = 0 | **RED (6 failed)** | test_buybackNoticeCannotRaiseV2SniperExitTax()<br> test_buybackNoticeLeavesV2SellTaxFlat()<br> test_buybackPacesSpendsBurnsWithoutRearmingSellSpike()<br> test_fourWalletV4SellWaveRemainsFlatAfterBuybackNotice()<br> test_graduatedV2PoolNeverArmsSellSpikeFromFeeFundedBuyback()<br> test_graduationAndBuybackKeepFlatSellTax() |
| 41 | `T01-creditfee-sender` | creditLiquidityFee accepts only the registered vault | **GREEN** | — |

## The diffs

### `E01-nonce` — GREEN

engine checks the current strategy nonce on every execution.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..ae31e89 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -372,7 +372,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
     }
 
     function _basicIntentValid(StrategyIntent memory intent) private view returns (bool) {
-        return intent.configHash == configHash && intent.nonce == strategyNonce
+        return intent.configHash == configHash
             && uint8(intent.action) <= uint8(StrategyAction.BuybackBurn);
     }
```

### `E02-confighash` — RED: test_wrongCommitmentAndExcessiveAmountBothFailClosedAtTheCore()

engine checks the domain-separated config hash on every execution.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..1e56b8f 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -372,7 +372,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
     }
 
     function _basicIntentValid(StrategyIntent memory intent) private view returns (bool) {
-        return intent.configHash == configHash && intent.nonce == strategyNonce
+        return intent.nonce == strategyNonce
             && uint8(intent.action) <= uint8(StrategyAction.BuybackBurn);
     }
```

### `E03-codehash-exec` — GREEN

engine re-checks the policy runtime codehash on every execution.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..f678945 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -391,7 +391,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
 
     function _policyIntent(StrategyContext memory context) private view returns (StrategyIntent memory intent) {
         address implementation = policyImplementation;
-        if (implementation.codehash != policyRuntimeCodeHash) revert PolicyUnavailable();
         bytes memory callData = abi.encodeCall(IStrategyPolicy.decide, (context, _engineConfig, policyState));
         bool success;
         uint256 size;
```

### `E04-gas` — GREEN

policy call gas is bounded by the registered maxGas.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..bd6e169 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -397,7 +397,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 size;
         uint256 gasLimit = policyGasLimit;
         assembly ("memory-safe") {
-            success := staticcall(gasLimit, implementation, add(callData, 0x20), mload(callData), 0, 0)
+            success := staticcall(gas(), implementation, add(callData, 0x20), mload(callData), 0, 0)
             size := returndatasize()
         }
         if (!success) revert PolicyFailure();
```

### `E05-retsize` — RED: test_hugePolicyReturndataIsRejectedBeforeCopyOrStateChange()

exact 160-byte returndata size is enforced.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..435ea9e 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -401,7 +401,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
             size := returndatasize()
         }
         if (!success) revert PolicyFailure();
-        if (size != INTENT_RETURN_BYTES || size > policyReturnLimit) revert BadPolicyReturn();
         bytes memory result = new bytes(size);
         assembly ("memory-safe") { returndatacopy(add(result, 0x20), 0, size) }
         intent = abi.decode(result, (StrategyIntent));
```

### `E06-health` — GREEN

execute refuses when health() is not ok.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..e839abf 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -250,7 +250,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
     function execute() external override nonReentrant returns (Action action, uint256 id) {
         _bookInventory();
         (bool ok, uint256 p) = health();
-        if (!ok) revert Unhealthy();
+        ok;
         (bool live,) = _oracle.tryPrice();
         if (!live) revert Unhealthy();
```

### `E07-live` — GREEN

execute refuses when the stock oracle is not live.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..b2d37f3 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -252,7 +252,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         (bool ok, uint256 p) = health();
         if (!ok) revert Unhealthy();
         (bool live,) = _oracle.tryPrice();
-        if (!live) revert Unhealthy();
+        live;
 
         StrategyContext memory context = _context(p, bookedStock);
         StrategyIntent memory intent = _policyIntent(context);
```

### `E08-capability` — GREEN

engine enforces SPOT_BUY / SPOT_SELL capability at execution.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..13234ee 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -325,7 +325,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         ExecutionLimits memory limits
     ) private returns (ExecutionResult memory result) {
         uint256 upperValue = Math.mulDiv(limits.totalValue, limits.targetBps + limits.deadbandBps, BPS);
-        if (policyCapabilities & StrategyCapabilities.SPOT_SELL == 0 || context.stockValueUsdg <= upperValue) {
+        if (context.stockValueUsdg <= upperValue) {
             revert BadIntent();
         }
         uint256 excessUsdg = context.stockValueUsdg - Math.mulDiv(limits.totalValue, limits.targetBps, BPS);
@@ -345,7 +345,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         ExecutionLimits memory limits
     ) private returns (ExecutionResult memory result) {
         uint256 lowerValue = Math.mulDiv(limits.totalValue, limits.targetBps - limits.deadbandBps, BPS);
-        if (policyCapabilities & StrategyCapabilities.SPOT_BUY == 0 || context.stockValueUsdg >= lowerValue) {
+        if (context.stockValueUsdg >= lowerValue) {
             revert BadIntent();
         }
         uint256 deficitUsdg = Math.mulDiv(limits.totalValue, limits.targetBps, BPS) - context.stockValueUsdg;
```

### `E09-cooldown` — RED: test_cooldownAndDailyCapUseCumulativeActualTurnover()

engine enforces the cooldown independently of the policy.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..9014b0f 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -292,7 +292,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 cooldown;
         uint256 maxDaily;
         (limits.targetBps, limits.deadbandBps, cooldown, limits.maxTrade, maxDaily) = _riskConfig();
-        if (lastStrategyAt != 0 && block.timestamp < lastStrategyAt + cooldown) revert Cooldown();
+        cooldown;
         limits.epoch = uint64(block.timestamp / 1 days);
         limits.used = turnoverEpoch == limits.epoch ? turnoverInEpoch : 0;
         if (limits.used >= maxDaily) revert NotDue();
```

### `E10-direction` — GREEN

engine enforces target/deadband direction (sell only above upper band, buy only below lower band).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..c884efc 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -325,7 +325,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         ExecutionLimits memory limits
     ) private returns (ExecutionResult memory result) {
         uint256 upperValue = Math.mulDiv(limits.totalValue, limits.targetBps + limits.deadbandBps, BPS);
-        if (policyCapabilities & StrategyCapabilities.SPOT_SELL == 0 || context.stockValueUsdg <= upperValue) {
+        if (policyCapabilities & StrategyCapabilities.SPOT_SELL == 0) {
             revert BadIntent();
         }
         uint256 excessUsdg = context.stockValueUsdg - Math.mulDiv(limits.totalValue, limits.targetBps, BPS);
@@ -345,7 +345,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         ExecutionLimits memory limits
     ) private returns (ExecutionResult memory result) {
         uint256 lowerValue = Math.mulDiv(limits.totalValue, limits.targetBps - limits.deadbandBps, BPS);
-        if (policyCapabilities & StrategyCapabilities.SPOT_BUY == 0 || context.stockValueUsdg >= lowerValue) {
+        if (policyCapabilities & StrategyCapabilities.SPOT_BUY == 0) {
             revert BadIntent();
         }
         uint256 deficitUsdg = Math.mulDiv(limits.totalValue, limits.targetBps, BPS) - context.stockValueUsdg;
```

### `E11-percall` — RED: test_cooldownAndDailyCapUseCumulativeActualTurnover(); test_wrongCommitmentAndExcessiveAmountBothFailClosedAtTheCore()

engine caps each action at maxTradeUsdg.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..555515c 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -329,7 +329,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
             revert BadIntent();
         }
         uint256 excessUsdg = context.stockValueUsdg - Math.mulDiv(limits.totalValue, limits.targetBps, BPS);
-        uint256 capUsdg = Math.min(Math.min(limits.maxTrade, limits.remainingDaily), excessUsdg);
+        uint256 capUsdg = Math.min(limits.remainingDaily, excessUsdg);
         uint256 offered = Math.min(requested, Math.min(bookedStock, _ruleStockFor(capUsdg, price)));
         if (offered == 0 || _ruleValue(offered, price) < _params.minLotUsdg) revert NotDue();
         (result.actualInput, result.actualOutput) = _swapStock(false, offered, price);
@@ -349,7 +349,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
             revert BadIntent();
         }
         uint256 deficitUsdg = Math.mulDiv(limits.totalValue, limits.targetBps, BPS) - context.stockValueUsdg;
-        uint256 capUsdg = Math.min(Math.min(limits.maxTrade, limits.remainingDaily), deficitUsdg);
+        uint256 capUsdg = Math.min(limits.remainingDaily, deficitUsdg);
         uint256 offered = Math.min(Math.min(requested, capUsdg), context.usdgInventory);
         if (offered < _params.minLotUsdg) revert NotDue();
         (result.actualInput, result.actualOutput) = _swapStock(true, offered, price);
```

### `E12-daily` — RED: test_cooldownAndDailyCapUseCumulativeActualTurnover()

engine caps cumulative turnover per UTC epoch at maxDailyTurnoverUsdg.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..64c65f4 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -295,8 +295,8 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         if (lastStrategyAt != 0 && block.timestamp < lastStrategyAt + cooldown) revert Cooldown();
         limits.epoch = uint64(block.timestamp / 1 days);
         limits.used = turnoverEpoch == limits.epoch ? turnoverInEpoch : 0;
-        if (limits.used >= maxDaily) revert NotDue();
-        limits.remainingDaily = maxDaily - limits.used;
+        maxDaily;
+        limits.remainingDaily = type(uint256).max;
         if (context.stockValueUsdg > type(uint256).max - context.usdgInventory) revert BadIntent();
         limits.totalValue = context.stockValueUsdg + context.usdgInventory;
         if (limits.totalValue == 0) revert NotDue();
```

### `E13-minlot-actual` — RED: [FAIL: invariant_handlerChecksCannotFailSilently replay failure]; test_handlerCoversSubMinFailureAndExactBoundarySuccess(); test_shortBuyBelowMinLotRollsBackWithoutConsumingStrategyState(); test_shortSellBelowMinLotRollsBackWithoutConsumingStrategyState()

actual turnover below minLotUsdg reverts atomically (dust fill cannot advance nonce/cooldown).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..67f141a 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -268,7 +268,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         // action would let a thin or deliberately positioned venue advance the nonce and renew the cooldown while
         // barely consuming the daily budget. The check must use the actual fill and must happen before any strategy
         // state is committed; reverting here rolls the swap and its transfers back atomically.
-        if (result.turnover < _params.minLotUsdg) revert NotDue();
         if (result.turnover > limits.remainingDaily) revert BadIntent();
         turnoverEpoch = limits.epoch;
         turnoverInEpoch = limits.used + result.turnover;
```

### `E14-daily-post` — GREEN

post-fill check that actual turnover does not exceed the remaining daily budget.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..39d8dbb 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -269,7 +269,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         // barely consuming the daily budget. The check must use the actual fill and must happen before any strategy
         // state is committed; reverting here rolls the swap and its transfers back atomically.
         if (result.turnover < _params.minLotUsdg) revert NotDue();
-        if (result.turnover > limits.remainingDaily) revert BadIntent();
         turnoverEpoch = limits.epoch;
         turnoverInEpoch = limits.used + result.turnover;
         lastStrategyAt = block.timestamp;
```

### `E15-options-cap` — RED: test_buybackCapabilityCannotEnterRebalanceEngine(); test_futureUnknownCapabilityFailsClosedInsideSpotEngine(); test_overBroadKindCannotSmuggleOptionsCapabilityIntoSpotEngine()

spot engine rejects every non-spot capability bit in its constructor.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..db14a50 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -133,7 +133,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
                 || !manifest.enabledForNewLaunches || manifest.implementation == address(0)
                 || actualCodeHash == bytes32(0) || actualCodeHash != manifest.runtimeCodeHash || manifest.maxGas == 0
                 || manifest.maxGas > MAX_POLICY_GAS || manifest.maxReturnBytes != INTENT_RETURN_BYTES
-                || manifest.capabilities & SPOT_CAPABILITIES == 0 || manifest.capabilities & ~SPOT_CAPABILITIES != 0
+                || manifest.capabilities & SPOT_CAPABILITIES == 0
                 || packed >> 64 != 0 || targetBps == 0 || targetBps >= BPS || deadbandBps == 0
                 || deadbandBps >= targetBps || targetBps + deadbandBps >= BPS || cooldown == 0 || maxTradeUsdg == 0
                 || maxTradeUsdg > p.sellChunkUsdg || maxDailyTurnoverUsdg < maxTradeUsdg
```

### `E16-reserved-bits` — RED: test_coreRejectsReservedConfigBitsEvenWhenPolicyWouldIgnoreThem()

engine rejects reserved config bits (words[0] >> 64).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..feddd13 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -134,7 +134,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
                 || actualCodeHash == bytes32(0) || actualCodeHash != manifest.runtimeCodeHash || manifest.maxGas == 0
                 || manifest.maxGas > MAX_POLICY_GAS || manifest.maxReturnBytes != INTENT_RETURN_BYTES
                 || manifest.capabilities & SPOT_CAPABILITIES == 0 || manifest.capabilities & ~SPOT_CAPABILITIES != 0
-                || packed >> 64 != 0 || targetBps == 0 || targetBps >= BPS || deadbandBps == 0
+                || targetBps == 0 || targetBps >= BPS || deadbandBps == 0
                 || deadbandBps >= targetBps || targetBps + deadbandBps >= BPS || cooldown == 0 || maxTradeUsdg == 0
                 || maxTradeUsdg > p.sellChunkUsdg || maxDailyTurnoverUsdg < maxTradeUsdg
         ) revert BadEngineConfig();
```

### `E17-config-bounds` — GREEN

engine enforces target/deadband/cooldown/maxTrade<=sellChunk/maxDaily>=maxTrade bounds at construction.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..1e6405b 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -134,9 +134,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
                 || actualCodeHash == bytes32(0) || actualCodeHash != manifest.runtimeCodeHash || manifest.maxGas == 0
                 || manifest.maxGas > MAX_POLICY_GAS || manifest.maxReturnBytes != INTENT_RETURN_BYTES
                 || manifest.capabilities & SPOT_CAPABILITIES == 0 || manifest.capabilities & ~SPOT_CAPABILITIES != 0
-                || packed >> 64 != 0 || targetBps == 0 || targetBps >= BPS || deadbandBps == 0
-                || deadbandBps >= targetBps || targetBps + deadbandBps >= BPS || cooldown == 0 || maxTradeUsdg == 0
-                || maxTradeUsdg > p.sellChunkUsdg || maxDailyTurnoverUsdg < maxTradeUsdg
+                || packed >> 64 != 0
         ) revert BadEngineConfig();
     }
```

### `E18-action-range` — GREEN

engine rejects an out-of-range action word before use.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..a03f663 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -372,8 +372,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
     }
 
     function _basicIntentValid(StrategyIntent memory intent) private view returns (bool) {
-        return intent.configHash == configHash && intent.nonce == strategyNonce
-            && uint8(intent.action) <= uint8(StrategyAction.BuybackBurn);
+        return intent.configHash == configHash && intent.nonce == strategyNonce;
     }
 
     function _riskConfig()
```

### `E19-call-not-staticcall` — RED: test_staticcallTrapsPolicyStateWrites()

policy is invoked with STATICCALL (state writes trap).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..c8cb41a 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -174,7 +174,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
     }
 
     /// @notice Simulate the immutable policy. `execute()` always recomputes the context and intent on chain.
-    function preview() external view returns (bool due, StrategyAction action, uint256 amountIn) {
+    function preview() external returns (bool due, StrategyAction action, uint256 amountIn) {
         (bool ok, uint256 p) = health();
         (bool live,) = _oracle.tryPrice();
         if (!ok || !live) return (false, StrategyAction.Hold, 0);
@@ -389,7 +389,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         maxDaily = uint256(_engineConfig.words[2]);
     }
 
-    function _policyIntent(StrategyContext memory context) private view returns (StrategyIntent memory intent) {
+    function _policyIntent(StrategyContext memory context) private returns (StrategyIntent memory intent) {
         address implementation = policyImplementation;
         if (implementation.codehash != policyRuntimeCodeHash) revert PolicyUnavailable();
         bytes memory callData = abi.encodeCall(IStrategyPolicy.decide, (context, _engineConfig, policyState));
@@ -397,7 +397,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 size;
         uint256 gasLimit = policyGasLimit;
         assembly ("memory-safe") {
-            success := staticcall(gasLimit, implementation, add(callData, 0x20), mload(callData), 0, 0)
+            success := call(gasLimit, implementation, 0, add(callData, 0x20), mload(callData), 0, 0)
             size := returndatasize()
         }
         if (!success) revert PolicyFailure();
```

### `E20-book-in-execute` — GREEN

execute books newly arrived stock before observing (donations become part of the next observation).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..f61818e 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -248,7 +248,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
 
     /// @notice Execute one bounded policy action. Keepers choose no action, route, lot, price or recipient.
     function execute() external override nonReentrant returns (Action action, uint256 id) {
-        _bookInventory();
         (bool ok, uint256 p) = health();
         if (!ok) revert Unhealthy();
         (bool live,) = _oracle.tryPrice();
```

### `E21-preview-minlot` — RED: test_previewDoesNotClaimDustBelowTheCoreMinimumIsExecutable()

preview does not claim a below-minimum lot is executable.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..535f1b1 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -228,7 +228,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 capUsdg =
             Math.min(Math.min(limits.maxTrade, limits.remainingDaily), context.stockValueUsdg - targetValue);
         offered = Math.min(requested, Math.min(context.stockInventory, _ruleStockFor(capUsdg, price)));
-        if (offered == 0 || _ruleValue(offered, price) < _params.minLotUsdg) return 0;
+        if (offered == 0) return 0;
     }
 
     function _previewBuy(StrategyContext memory context, uint256 requested, ExecutionLimits memory limits)
@@ -243,7 +243,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 capUsdg =
             Math.min(Math.min(limits.maxTrade, limits.remainingDaily), targetValue - context.stockValueUsdg);
         offered = Math.min(Math.min(requested, capUsdg), context.usdgInventory);
-        if (offered < _params.minLotUsdg) return 0;
     }
 
     /// @notice Execute one bounded policy action. Keepers choose no action, route, lot, price or recipient.
```

### `E22-preswap-minlot` — GREEN

pre-swap minimum-lot gate on the offered amount.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..ab9570e 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -331,7 +331,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 excessUsdg = context.stockValueUsdg - Math.mulDiv(limits.totalValue, limits.targetBps, BPS);
         uint256 capUsdg = Math.min(Math.min(limits.maxTrade, limits.remainingDaily), excessUsdg);
         uint256 offered = Math.min(requested, Math.min(bookedStock, _ruleStockFor(capUsdg, price)));
-        if (offered == 0 || _ruleValue(offered, price) < _params.minLotUsdg) revert NotDue();
+        if (offered == 0) revert NotDue();
         (result.actualInput, result.actualOutput) = _swapStock(false, offered, price);
         bookedStock -= result.actualInput;
         result.turnover = _ruleValue(result.actualInput, price);
@@ -351,7 +351,6 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 deficitUsdg = Math.mulDiv(limits.totalValue, limits.targetBps, BPS) - context.stockValueUsdg;
         uint256 capUsdg = Math.min(Math.min(limits.maxTrade, limits.remainingDaily), deficitUsdg);
         uint256 offered = Math.min(Math.min(requested, capUsdg), context.usdgInventory);
-        if (offered < _params.minLotUsdg) revert NotDue();
         (result.actualInput, result.actualOutput) = _swapStock(true, offered, price);
         bookedStock += result.actualOutput;
         result.turnover = result.actualInput;
```

### `E23-inventory-offered` — RED: testFuzz_shortSellFillUsesOnlyActualInput(uint16)

inventory is debited by the actual fill, not the offered amount.

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..39166fd 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -333,7 +333,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         uint256 offered = Math.min(requested, Math.min(bookedStock, _ruleStockFor(capUsdg, price)));
         if (offered == 0 || _ruleValue(offered, price) < _params.minLotUsdg) revert NotDue();
         (result.actualInput, result.actualOutput) = _swapStock(false, offered, price);
-        bookedStock -= result.actualInput;
+        bookedStock -= offered;
         result.turnover = _ruleValue(result.actualInput, price);
         result.action = Action.RebalanceSell;
     }
```

### `E24-enabled-both` — GREEN

a disabled policy cannot launch a treasury whose salt was configured before the disable (constructor + _code).

```diff
diff --git a/src/v2/HedgeFunV2EngineTreasury.sol b/src/v2/HedgeFunV2EngineTreasury.sol
index 555f237..b5b8536 100644
--- a/src/v2/HedgeFunV2EngineTreasury.sol
+++ b/src/v2/HedgeFunV2EngineTreasury.sol
@@ -130,7 +130,7 @@ contract HedgeFunV2EngineTreasury is HedgeFunV2Treasury {
         if (
             c.schema != StrategyCapabilities.CONFIG_SCHEMA_V1 || c.engineVersion != StrategyCapabilities.SPOT_ENGINE_V1
                 || manifest.engineVersion != c.engineVersion || manifest.configSchema != c.schema
-                || !manifest.enabledForNewLaunches || manifest.implementation == address(0)
+                || manifest.implementation == address(0)
                 || actualCodeHash == bytes32(0) || actualCodeHash != manifest.runtimeCodeHash || manifest.maxGas == 0
                 || manifest.maxGas > MAX_POLICY_GAS || manifest.maxReturnBytes != INTENT_RETURN_BYTES
                 || manifest.capabilities & SPOT_CAPABILITIES == 0 || manifest.capabilities & ~SPOT_CAPABILITIES != 0
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..ac00e9b 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -344,7 +344,7 @@ contract V2TreasuryDeployer is BoundDeployer {
             ) revert BadPolicy();
             PolicyManifest storage manifest = _policies[config.policyKey];
             if (
-                manifest.implementation == address(0) || !manifest.enabledForNewLaunches
+                manifest.implementation == address(0)
                     || manifest.implementation.codehash != manifest.runtimeCodeHash
                     || manifest.engineVersion != config.engineVersion || manifest.configSchema != config.schema
                     || manifest.capabilities & ~k.capabilities != 0
```

### `D01-registerPolicy-owner` — GREEN

only the factory owner may register a policy.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..5b0b93e 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -215,7 +215,6 @@ contract V2TreasuryDeployer is BoundDeployer {
         bytes32 dependencyManifestHash,
         bytes32 auditManifestHash
     ) external returns (bytes32 policyKey) {
-        _onlyOwner();
         if (
             implementation.code.length == 0 || maxGas == 0 || maxGas > MAX_POLICY_GAS
                 || maxReturnBytes != POLICY_RETURN_BYTES || dependencyManifestHash == bytes32(0)
```

### `D02-registerEngineKind-owner` — GREEN

only the factory owner may register an engine kind.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..decd350 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -194,7 +194,6 @@ contract V2TreasuryDeployer is BoundDeployer {
         external
         returns (uint8 kind)
     {
-        _onlyOwner();
         if (
             a.code.length == 0 || b.code.length == 0 || engineVersion == 0 || configSchema == 0 || capabilities == 0
                 || _kinds.length == type(uint8).max
```

### `D03-disablePolicy-owner` — GREEN

only the factory owner may disable a policy.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..e06973c 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -278,7 +278,6 @@ contract V2TreasuryDeployer is BoundDeployer {
     }
 
     function disablePolicy(bytes32 policyKey) external {
-        _onlyOwner();
         PolicyManifest storage manifest = _policies[policyKey];
         if (manifest.implementation == address(0) || !manifest.enabledForNewLaunches) revert BadPolicy();
         manifest.enabledForNewLaunches = false;
```

### `D04-registerKind-owner` — RED: test_onlyFactoryOwnerRegistersAKindAndKindsAreWriteOnce()

only the factory owner may register a legacy kind (control: covered by V2StrategyKinds).

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..3492bac 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -181,7 +181,6 @@ contract V2TreasuryDeployer is BoundDeployer {
 
     /// @notice The bound factory's owner adds a strategy kind for FUTURE launches. Existing kinds never change.
     function registerKind(address a, address b) external returns (uint8 kind) {
-        _onlyOwner();
         if (a.code.length == 0 || b.code.length == 0 || _kinds.length == type(uint8).max) revert BadKind();
         kind = uint8(_kinds.length);
         _kinds.push(Kind(a, b, 0, 0, _creationCodeHash(a, b), 0));
```

### `D05-deploy-onlyFactory` — GREEN

only the bound factory may deploy a treasury.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..6fecd2f 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -366,7 +366,6 @@ contract V2TreasuryDeployer is BoundDeployer {
     }
 
     function deploy(bytes32 salt, bytes calldata args) external returns (address a) {
-        _onlyFactory();
         _validate(args);
         bytes memory code = _code(salt, args);
         bytes32 initCodeHash = keccak256(code);
```

### `D06-deploy-introspection` — GREEN

deploy verifies the deployed engine's version, policy id and config hash.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..65f0527 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -381,10 +381,6 @@ contract V2TreasuryDeployer is BoundDeployer {
             EngineConfig storage config = _engineConfigOf[salt];
             IStrategyEngineIntrospection engine = IStrategyEngineIntrospection(a);
             boundConfigHash = engine.configHash();
-            if (
-                engine.engineVersion() != config.engineVersion || engine.strategyId() != config.policyKey
-                    || boundConfigHash == bytes32(0)
-            ) revert TreasuryDeployFailed();
         }
         // `args` starts (usdg, stock, ...): the stock is its second word
         lpBpsOfTreasury[a] = lpBps(address(uint160(uint256(bytes32(args[32:64])))));
```

### `D07-registerPolicy-bounds` — GREEN

registerPolicy enforces maxGas/maxReturnBytes/manifest-hash bounds.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..7edeac2 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -217,9 +217,7 @@ contract V2TreasuryDeployer is BoundDeployer {
     ) external returns (bytes32 policyKey) {
         _onlyOwner();
         if (
-            implementation.code.length == 0 || maxGas == 0 || maxGas > MAX_POLICY_GAS
-                || maxReturnBytes != POLICY_RETURN_BYTES || dependencyManifestHash == bytes32(0)
-                || auditManifestHash == bytes32(0)
+            implementation.code.length == 0
         ) revert BadPolicy();
 
         uint32 engineVersion;
```

### `D08-setEngineConfig-capsubset` — RED: test_optionsCapabilityCannotEnterTheSpotEngine(); test_spotOnlyKindRejectsPolicyContainingAnyOptionsCapabilityAtConfiguration()

setEngineConfig rejects a policy whose capabilities exceed the kind's.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..4e32639 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -309,7 +309,7 @@ contract V2TreasuryDeployer is BoundDeployer {
                 || config.schema != k.engineConfigSchema || manifest.implementation == address(0)
                 || !manifest.enabledForNewLaunches || manifest.implementation.codehash != manifest.runtimeCodeHash
                 || manifest.engineVersion != config.engineVersion || manifest.configSchema != config.schema
-                || manifest.capabilities & ~k.capabilities != 0
+
         ) revert BadPolicy();
         bytes32 salt = keccak256(abi.encode(symbol, msg.sender, nonce));
         strategyKindOf[salt] = kind;
```

### `D09-setEngineConfig-codehash` — RED: test_policyCodeReplacementFailsBeforePredictionOrLaunch()

setEngineConfig rejects a policy whose runtime code changed.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..c6dbe15 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -307,7 +307,7 @@ contract V2TreasuryDeployer is BoundDeployer {
         if (
             k.engineConfigSchema == 0 || config.engineVersion != k.engineVersion
                 || config.schema != k.engineConfigSchema || manifest.implementation == address(0)
-                || !manifest.enabledForNewLaunches || manifest.implementation.codehash != manifest.runtimeCodeHash
+                || !manifest.enabledForNewLaunches
                 || manifest.engineVersion != config.engineVersion || manifest.configSchema != config.schema
                 || manifest.capabilities & ~k.capabilities != 0
         ) revert BadPolicy();
```

### `D10-policy-dup` — GREEN

policy registrations are append-only (a key cannot be re-registered).

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..f29c2d0 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -250,7 +250,6 @@ contract V2TreasuryDeployer is BoundDeployer {
                 auditManifestHash
             )
         );
-        if (_policies[policyKey].implementation != address(0)) revert BadPolicy();
         _policies[policyKey] = PolicyManifest({
             implementation: implementation,
             runtimeCodeHash: runtimeCodeHash,
```

### `D11-setStrategyKind-engine` — RED: test_engineSelectionRestatesQuoteAndLegacySetterCannotSkipConfig()

the legacy setStrategyKind cannot select an engine kind without a config.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..5e75d5b 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -294,7 +294,6 @@ contract V2TreasuryDeployer is BoundDeployer {
     ///         moves the treasury address and the launch reverts `Restated` -- re-quote. Kind 0 needs no call.
     function setStrategyKind(string calldata symbol, uint96 nonce, uint8 kind) external {
         if (kind >= _kinds.length) revert BadKind();
-        if (_kinds[kind].engineConfigSchema != 0) revert BadKind();
         strategyKindOf[keccak256(abi.encode(symbol, msg.sender, nonce))] = kind;
         emit StrategyKindSet(msg.sender, symbol, nonce, kind);
     }
```

### `D12-policyMetadata-consistency` — GREEN

registerPolicy rejects a policy whose metadata is zero.

```diff
diff --git a/src/v2/V2TreasuryDeployer.sol b/src/v2/V2TreasuryDeployer.sol
index 5ce7353..286ac27 100644
--- a/src/v2/V2TreasuryDeployer.sol
+++ b/src/v2/V2TreasuryDeployer.sol
@@ -234,7 +234,6 @@ contract V2TreasuryDeployer is BoundDeployer {
         } catch {
             revert BadPolicy();
         }
-        if (engineVersion == 0 || configSchema == 0 || capabilities == 0) revert BadPolicy();
 
         bytes32 runtimeCodeHash = implementation.codehash;
         policyKey = keccak256(
```

### `V01-no-retry` — RED: test_stockCreditFailureParksFeeButStillBurnsTokenFee()

a refused stock-fee credit is parked and retried; the token burn still completes.

```diff
diff --git a/src/v2/V2LiquidityVault.sol b/src/v2/V2LiquidityVault.sol
index ad496af..29fc435 100644
--- a/src/v2/V2LiquidityVault.sol
+++ b/src/v2/V2LiquidityVault.sol
@@ -105,7 +105,7 @@ contract V2LiquidityVault is IUnlockCallback {
         pendingStockFee += newStockFee;
         // The issuer may reject delivery to the treasury. Keep that fee for a later retry
         // without reverting the independent token burn.
-        try this.creditPendingStock() returns (uint256 delivered) { stockFee = delivered; pendingStockFee = 0; } catch {}
+        stockFee = this.creditPendingStock(); pendingStockFee = 0;
         if (tokenBurned != 0) HedgeFunToken(token).burn(tokenBurned);
         _mode = 0;
         emit FeesCollected(stockFee, tokenBurned);
```

### `V02-no-clear` — RED: testFuzz_threeActorSequencesConserveBeforeAndAfterGraduation(uint256,bool,bool)

a delivered stock fee is cleared from the pending ledger (no double credit / stuck retry).

```diff
diff --git a/src/v2/V2LiquidityVault.sol b/src/v2/V2LiquidityVault.sol
index ad496af..a3f74b5 100644
--- a/src/v2/V2LiquidityVault.sol
+++ b/src/v2/V2LiquidityVault.sol
@@ -105,7 +105,7 @@ contract V2LiquidityVault is IUnlockCallback {
         pendingStockFee += newStockFee;
         // The issuer may reject delivery to the treasury. Keep that fee for a later retry
         // without reverting the independent token burn.
-        try this.creditPendingStock() returns (uint256 delivered) { stockFee = delivered; pendingStockFee = 0; } catch {}
+        try this.creditPendingStock() returns (uint256 delivered) { stockFee = delivered; } catch {}
         if (tokenBurned != 0) HedgeFunToken(token).burn(tokenBurned);
         _mode = 0;
         emit FeesCollected(stockFee, tokenBurned);
```

### `V03-selfcall` — RED: test_callbackCannotBeCalledByOutsider()

creditPendingStock is self-call only.

```diff
diff --git a/src/v2/V2LiquidityVault.sol b/src/v2/V2LiquidityVault.sol
index ad496af..bb6db2a 100644
--- a/src/v2/V2LiquidityVault.sol
+++ b/src/v2/V2LiquidityVault.sol
@@ -113,7 +113,6 @@ contract V2LiquidityVault is IUnlockCallback {
 
     /// @dev Only collectFees can make this self-call. A later collectFees retries any parked stock fee.
     function creditPendingStock() external returns (uint256 amount) {
-        if (msg.sender != address(this)) revert Busy();
         amount = pendingStockFee;
         if (amount == 0) return 0;
         IERC20 asset = IERC20(stock);
```

### `F01-spike` — RED: test_buybackNoticeCannotRaiseV2SniperExitTax(); test_buybackNoticeLeavesV2SellTaxFlat(); test_buybackPacesSpendsBurnsWithoutRearmingSellSpike(); test_fourWalletV4SellWaveRemainsFlatAfterBuybackNotice(); test_graduatedV2PoolNeverArmsSellSpikeFromFeeFundedBuyback(); test_graduationAndBuybackKeepFlatSellTax()

graduated V2 pools freeze spikeBps = 0.

```diff
diff --git a/src/v2/HedgeFunV2Factory.sol b/src/v2/HedgeFunV2Factory.sol
index f5f0387..fa11f99 100644
--- a/src/v2/HedgeFunV2Factory.sol
+++ b/src/v2/HedgeFunV2Factory.sol
@@ -103,7 +103,6 @@ contract HedgeFunV2Factory is HedgeFunFactory {
         rates.snipeSeconds = 0;
         // LP fees can fund permissionless buy-backs without any realised strategy profit.
         // They must not re-arm the sell spike for every new burst of trading volume.
-        rates.spikeBps = 0;
         _frozen[id] = Frozen(key, rates);
         IERC20(token).safeTransfer(curve, d.supply);
         emit CurveLaunched(id, curve, p.saleBps, p.virtualStock);
```

### `T01-creditfee-sender` — GREEN

creditLiquidityFee accepts only the registered vault.

```diff
diff --git a/src/v2/HedgeFunV2Treasury.sol b/src/v2/HedgeFunV2Treasury.sol
index d90f505..5b1915f 100644
--- a/src/v2/HedgeFunV2Treasury.sol
+++ b/src/v2/HedgeFunV2Treasury.sol
@@ -168,7 +168,7 @@ contract HedgeFunV2Treasury is HedgeFunTreasury {
     /// @notice Realized stock-side LP fees enter the buyback budget, never a strategy cost-basis lot.
     /// @dev Pulling under the reentrancy guard prevents token callbacks from booking the fee as principal.
     function creditLiquidityFee(uint256 amount) external nonReentrant {
-        if (msg.sender != liquidityVault || amount == 0) revert NotFactory();
+        if (amount == 0) revert NotFactory();
         _stock.safeTransferFrom(msg.sender, address(this), amount);
         buybackStock += amount;
     }
```
