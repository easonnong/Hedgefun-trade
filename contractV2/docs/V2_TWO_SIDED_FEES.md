# V2双向手续费：基础费收入与销毁分别记账

用户选择的发布配置为基础费3%，费用按协议20%、创作者10%、金库70%分账。
新代码支持这组参数，同时保留已有的、有上限的按launch选费率机制；它不把所有自定义launch硬编码为3%。
发布请求须采用 `taxBps=300`、`creatorBps=1000`，Factory defaults采用 `protocolBps=2000`。
每个launch的参数在创建时冻结；更改未来默认值不能追改已发行的池子。

## 当前改动

| 阶段与交易 | 基础手续费 | 收入如何实现 |
|---|---|---|
| 曲线买入 | 实际股票支付额中扣基础费 | 净本金进入曲线，股票费用即时记入三方可领取账本 |
| 曲线卖出 | 实际毛股票输出中扣基础费 | 三方可领取账本，和买入共用分账函数 |
| V4固定投入金额买入 | 支付的股票中扣基础费，在`beforeSwap`收取 | 股票claims由正常sweep结算到三方，无需兑换 |
| V4固定投入金额卖出 | 实际毛股票输出中扣基础费 | 股票claims由正常sweep结算到三方 |
| V4指定买到数量的买入 | 维持现有股票输入gross-up费 | 股票claims按相同分成结算；不支持指定卖出所得的卖出 |

V2毕业后的 `sweepTipBps=0`，基础费不会先被清算奖励稀释。实际分账对协议和创作者取整，剩余归金库。
曲线买入的开盘附加税仍单独烧策略币，归一化比例为 `(当前总名义税率−基础费率)/(10000−基础费率)`。
普通基础费不再用于买入即销毁。股票侧LP手续费仍属于独立的金库回购预算，策略币侧LP手续费仍销毁。
V4的0.30% LP费是额外费用，不能称整个swap只收3%，也不能计成协议地址收入。

## 买入费直接收股票（hook version 3）

`HedgeFunV2Hook`是独立的新hook，沿用真实PoolManager的交易结算与每池税收账本。
旧 `HedgeFunHook` 的买入销毁行为保留；基础类只开放继承所需的可覆盖函数和共享重入锁。
Factory只接受 `version()==3` 的hook。

V4的`afterSwap`只能从未指定数量的一侧取费；固定投入买入时那一侧是策略币。version 2因此先收策略币，
再由Factory owner调用`convertFees`换成股票，主网上每个池子每次兑换都是一次Safe操作。
version 3改为在`beforeSwap`从买家支付的股票里直接扣 `floor(支付额×taxBps/10000)`，
费用从产生起就是该池的股票claims：没有策略币费用库存，没有兑换卖单，也没有owner环节。
`convertFees`与`pendingTokenFees`已删除；任何人调用`sweep`即可把买入、卖出两侧费用一起分给三方。

`beforeSwap`在池价移动前按请求金额收费，所以触及价格限制而提前停止的固定投入买入会被拒绝
（`PartialFillRefused`），而不是多收未成交部分的费用。买家用最低到账量限定价格，`HedgeFunV2TradeRouter`即如此。
卖出仍在`afterSwap`按实际成交收费，可以部分成交；金库自己的交易不收费，也不受此限制。
毕业池没有开盘窗口，买入费率恒为基础费率。只有扣费后的支付额进入池子，与指定买到数量的买入一致：
同样的策略币，两种买法的总支付和费用相同（差额在取整范围内）。
hook地址低14位为`0x28CC`（原`0x2844`加`BEFORE_SWAP`与`BEFORE_SWAP_RETURNS_DELTA`）。

已部署的version 2核心不可变，仍按旧流程运行；脚本和fork测试通过
[`ILegacyV2FeeConversion`](../script/testnet/ILegacyV2FeeConversion.sol)访问它们的兑换接口。

## 前端、部署与旧证据

曲线 `quoteBuy` / `quoteBuyFor` ABI保持不变，但第三个返回值现在只表示开盘附加销毁。
基础股票手续费为 `floor(实际stockSpent×taxBps/10000)`。报价、费用展示必须分别显示基础费和附加销毁。
超出毕业cap的退款不收手续费；毕业迁移的股票金额仅为真实净本金，不包含三方未领取债务。

新版的curve、hook和Factory需重新部署，只应用于新launch。不能把新ABI或新收入模型套到已部署旧池。
部署脚本采用新hook的creationCode重新找地址并readback `version()==3`，地址簿标记新fee featureVersion。
本次不签名或广播任何链上交易，也不迁移旧池。

旧资本/持仓/供应模拟保持其旧规则的历史含义。由于基础买入销毁变成收费分账、曲线本金扣费和
V4费用兑换都会改变储备与供应，旧金额不能作为新版测量结果。
这次只验证收入、资产负债、退款、部分成交、隔离和交易边界，不测算协调拉盘或退出收益。

## 参考与验证

[pump.fun官方费用](https://pump.fun/docs/fees)分别列出creator、protocol和LP费用；
[Pons官方V2源码](https://github.com/ponsdotdev/pons-labs)采用曲线quote收费，以及V4策略币费用批量换quote后分配。
本实现的参数、启动税与金库策略独立，不声称复制两者的经济模型。

实现：[`HedgeFunBondingCurve`](../src/v2/HedgeFunBondingCurve.sol)、
[`HedgeFunV2Hook`](../src/hooks/HedgeFunV2Hook.sol)、[`HedgeFunV2Factory`](../src/v2/HedgeFunV2Factory.sol)。
验证覆盖实际PoolManager下买卖收入、买入费的股票计价与部分成交拒绝、claims到股票到账的分账、币种排序、封顶退款与费用负债，
并回归旧V1销毁及股票受阻的独立领取路径。最终检查与审查结论记录在PR中。
