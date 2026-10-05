# Hedgefun 合约范围与发布状态（内部文档）

更新于 **2026-10-04**。代码基线是本仓库默认分支 `main`（2026-10-05 由 `codex/contract-v1` 改名），已合并
[Cycle 集成 #12](https://github.com/0xHedgeHood/Hedgefun-trade/pull/12) 和
[测试网及股票策略回放 #20](https://github.com/0xHedgeHood/Hedgefun-trade/pull/20)。
本页同时更新为 [#25](https://github.com/0xHedgeHood/Hedgefun-trade/pull/25) 的独立集成版本，
不包含草稿 #21 的实验性分红、期权和 Earn。接口细节以对应源码和 ABI 为准。

**已合并源码、历史部署和计划中的发布是三个不同状态。** 合并代码不会升级已发射的合约，
测试或 ABI 的存在也不代表某个策略已在链上注册。接入时使用经核验的地址簿和实时链上读数。

## 产品与资金边界

Hedgefun 是股票策略型代币 launchpad。每个发射绑定自己的 FUN 代币、股票资产、treasury 和 V4 池。
V2 先通过股票计价的 bonding curve 募集真实资产，再毕业建立永久锁定的 LP，并把另一部分股票送入 treasury。
策略、手续费领取和回购都需要交易触发；permissionless 表示任何人可按合约规则调用，不表示会自动执行。

- [V1](../contractV1/README.md) 与 [V2](../contractV2/README.md) 是独立合约项目。V2 的新代码不修改 V1 已部署实例。
- FUN 的发行供应量在创建时确定，没有后续增发入口；实际总供应量仍会受适用版本的销毁逻辑影响。
- 当前 V2 LP vault 只提供手续费收集路径，不提供提取 LP 本金的入口。永久锁定 LP 内的股票不能当作可赎回现金。
- FUN 市价、市值、treasury 资产、包含锁定 LP 的总外部资产分别统计；自己的 FUN 不重复计为外部资产。
- 代币不承诺股票赎回、保本或跑赢持有股票。止损可能实现亏损；回购和缩减供应不等于创造等值外部财富。
- 股票发行方的暂停、冻结、代币升级等外部权限不因 launchpad 的规则而消失。

## 当前 V2：发射、交易和毕业

### 发射配置与报价承诺

创建者选择已上架的股票、名称、符号、费用和支持的策略参数；策略类型通过 treasury registry 选择。
股票的 oracle、交易池和执行 gates 来自 listing。种类、曲线配置和开盘豁免都应在最终 `predict` 前设置；
影响承诺的配置变化会改变预计地址或 `terms`，旧报价应拒绝并重新读取。

下表描述 **包含 #25 的当前源码**；新部署仍待执行，不能套用到历史合约：

| 项目 | 当前源码 | 历史部署及边界 |
|---|---|---|
| 未指定时的曲线出售比例 | `CurveDeployer.DEFAULT_SALE_BPS = 7931`，即 79.31% | 已有测试网旧核心仍默认 44% |
| 创建者可选出售比例 | 1000..9000 bps，即 10%..90% | 79.31% 是默认值，不是硬上限 |
| 开盘附加费窗口 | 创建者可选 0..180 秒；未指定时读工厂默认 | 按发布配置及链上读数展示 |
| 附加豁免地址 | 最多 40 个，creator 自动豁免且不占名额 | 已有旧核心仍为 32 个 |
| 基础交易费 | 新部署推荐 100 bps（1%），创建者仍按工厂限额选择 | 历史测试样例用 300 bps（3%）；不追改旧实例，也未强制固定为 1% |
| LP 分配比例与 LP 费 | 按 listing/registry 配置冻结在 launch 中 | 发布前实测池深；不能把 LP 费算成已包含在基础费里 |

配置依据：[CurveDeployer](../contractV2/src/v2/CurveDeployer.sol)、
[开盘豁免说明](../contractV2/docs/V2_OPENING_TAX_WHITELIST.md)、
[creator 参数](../contractV2/src/v2/strategy/V2CreatorParams.sol)。豁免只免曲线买入的开盘附加部分，
仍付基础费、不改变卖出费，也不延续到毕业后的 V4 池。报价按真实代币接收者计算，不能套用 creator 的豁免给普通买家。
开盘费是交易摩擦，不能保证阻止多钱包或控制筹码。

### 手续费账本

当前 V2 已采用[双向手续费收入模型](../contractV2/docs/V2_TWO_SIDED_FEES.md)：

| 路径 | 收费与入账 |
|---|---|
| 曲线买入/卖出 | 基础费以股票记入三方可领取账本；买入的开盘附加部分另行销毁 FUN |
| V4 固定投入买入 | 股票基础费在 `beforeSwap` 从支付额中收取，经 `sweep` 结算到协议、创建者和 treasury |
| V4 固定投入卖出 | 股票基础费经 `sweep` 结算到协议、创建者和 treasury |
| V4 指定买到数量 | 按股票输入 gross-up 收基础费；不支持指定卖出所得的卖出 |
| LP 手续费 | 股票侧进入 treasury 回购预算，FUN 侧销毁；不等于提取 LP 本金 |

普通基础买入费已经不是 V1 的“全部立即烧掉”。hook version 3 在 `beforeSwap` 直接从买家支付的股票里收取，
任何人 `sweep` 即可分账，没有待转换的 FUN 库存，也没有 owner 环节；触及价格限制而提前停止的固定投入买入会被拒绝。
已部署的 version 2 核心仍是旧流程：`pendingTokenFees` 是待转换的 FUN claims，`convertFees` 需要 factory owner。
曲线 `claimFees`、hook `sweep`、LP 领取、策略 `execute` 和 `buyback` 各有自己的条件。

### 毕业：保留项目币供应，区分本金与收入

达到终点的最后一笔曲线买入触发原子毕业：初始化 V4、注入 LP、绑定 treasury；任何一步失败回滚该笔买入。
毕业资本仅包括真实净储备，不包括虚拟储备或尚欠三方的手续费。多资产支付的超额部分可能以股票退款，
前端必须说明退款币种、partial fill 和最终最低到账保护。

历史版本会烧掉未用于全区间 LP 的 FUN，并把纯回购种类收到的毕业股票记入回购预算。
当前 [Factory](../contractV2/src/v2/HedgeFunV2Factory.sol) 与
[纯回购 treasury](../contractV2/src/v2/HedgeFunV2BuybackTreasury.sol) 已按 #25 修正，新发射遵循：

- 毕业剩余 FUN 进入永久锁定的 LP/余量托管，不在毕业时销毁项目币。
- 毕业本金与收入分开，不把纯回购种类的毕业本金当作回购预算；回购使用允许的收入预算。
- LP 本金仍锁定；销毁 LP 凭证或锁定仓位，与销毁项目 FUN 是不同概念。
- 手续费及盈利后的正常回购/销毁另行保留，不能把“取消毕业烧币”解释成“所有烧币全部取消”。

## 策略种类与执行限制

| 种类 | 负责什么 | 接入边界 |
|---|---|---|
| 当前默认 AllIn / lot 策略 | 按批次成本执行止盈、止损和抄底 | 先处理到期卖出，再考虑买入；不能承诺所有交易都盈利 |
| 纯回购 | 不开股票 lot，按节奏与冲击限制买 FUN 并销毁 | 精确保护毕业本金，费用与后续收入单独进入回购预算 |
| 固定金额 Spot Engine | policy 提出股票目标再平衡动作，treasury 校验并成交 | schema 1；池、资产、收款人由执行核心约束 |
| 资产百分比 Engine | 根据本基金总外部资产确定单笔/日换手上限 | schema 2；锁定 LP 可进入限额分母，不能当作可交易库存 |
| Cycle（#12） | 在原 lot 规则上增加一次有条件的恢复买入 | 独立注册、创建者主动选择；不会替换旧 kind 或旧 treasury |

除特定部署地址簿明确列出的 ID 外，新增 kind 的 ID 取决于注册顺序，不能按表格顺序写死。
策略引擎的 policy 只能提出允许的买/卖/等待意图，执行核心重新核对代码身份、配置、oracle、日历、冷却、
交易规模、日换手和实际成交。详见[固定金额引擎](../contractV2/docs/STRATEGY_ENGINE.md)与
[百分比引擎](../contractV2/docs/V2_ASSET_PERCENT_ENGINE.md)。

Cycle 的恢复买入要经过价格、至少 600 秒等待和更新报价等条件，并受现金、单笔股票交易额及 lot 容量限制。
只有真实成交才建立相应的止损观察；无成交的 dust 清理不应重置恢复门槛或领取卖出奖励。
具体规则和 128-lot 行为见 [Cycle 说明](../contractV2/docs/V2_SIMPLE_CYCLE.md)及
[#12 集成审查记录](../contractV2/docs/V2_CYCLE_INTEGRATION_REVIEW.md)。它可能改善重新参与上涨的机会，
也可能在反复止损/恢复中扩大损失，不是所有行情都更优。

## 金库升级与分红的发布顺序

历史旧 treasury 没有就地升级入口。当前源码已实现新发射的可升级默认 treasury；
首发方案是 **可升级默认 treasury + ETH 支付**，仍需要新核心部署、ETH bridge、激活和地址簿验证。

#25 为新发射的默认 kind 0 引入代理和独立升级控制器：由 factory owner 排期，至少等待 48 小时，
执行时校验实现代码、配置、迁移数据和所有权轮次。所有权转移再转回也不能恢复旧的升级提案。
其他策略种类不会自动获得这条升级路径；既有不可升级实例也不会因新代码合并而变为可升级。

升级治理是新增的信任边界。延迟和校验限制升级流程，但管理员批准的新实现可以改变 treasury 行为，
所以未来不能继续对该代理笼统承诺“任何时候都无人能改变规则或资金权限”。LP vault 本金锁定与 treasury 升级权限分别说明。

分红属于第二阶段：[#22](https://github.com/0xHedgeHood/Hedgefun-trade/pull/22) 提供按种类选择的股票收益分配与质押池，
仍为草稿；是否通过升级已有默认 treasury，或注册新的分红种类接入，需要后续集成确认。
[#21](https://github.com/0xHedgeHood/Hedgefun-trade/pull/21) 的全策略/质押实验也是草稿，
包含 Cycle、期权和 Earn 的源码快照，实验通过不等于这些功能已批准注册或对外提供。

## 测试网与回放证据

#20 归档了 2026-10-03 的 creator 核心部署、股票/tUSDG 发射到毕业流程、费用转换及分账验证。
采用[测试网交接说明](../contractV2/docs/TESTNET_LAUNCH_HANDOFF_2026-10-03.md)和
[核验地址簿](../contractV2/deploy/testnet-v2-fresh-creator.json)，以 `chainId + factory + strategyId` 标识策略。
该历史部署的 Factory 是 `0x2363B102D37BBa1dc3f9aBEdC4d6121C8e90B9cF`，chain ID 为 46630。

该地址簿注册的是 kind 0 AllIn、1 Buyback、2 schema-1 SpotEngine。这份证据没有启用 Native ETH 发射/交易，
也没有把 NAV Engine 或 Cycle 注册进去。不能因为新分支已有相关代码就为这个部署打开入口。
ETH 接入另见[桥接说明](../contractV2/docs/TESTNET_V2_ETH_BRIDGE.md)和
[原生币发射说明](../contractV2/docs/V2_NATIVE_LAUNCH.md)。

#20 的 [2025 股票参数与费用回放](../contractV2/docs/EQUITY_PARAMETER_FEES_2025_2026-10-03.md)
包含 TSLA、NVDA、META 的 39 组情景、9,750 个日快照，以及 LP 领取开/关和同流量基准比较。
行情路径是历史 Close，FUN 订单流、开市条件和部分流动性设置是模拟假设；不是历史用户需求重建，也不是未来收益预测。
FUN 边际标价收益不等于可退出收益，LP 费用转到 treasury 再用于回购不能重复算成新资产。

## 合并与发布检查

1. #12、#20 和内部范围文档 #2 已合并。#25 的三笔功能/修复提交已独立集成到该基线，重新验证构建和回归。
2. 此集成不引入 #21 的实验性分红、期权和 Earn；新部署与前端必须使用最终提交生成的 ABI 和核验地址簿。
3. 每次生产代码或编译器变化重跑 runtime/initcode 体积检查，使用真实上限。#12 的固定记录中 Cycle runtime
   为 24,514 字节，距离 EIP-170 仅 62 字节；这个数是该提交的证据，不是以后版本的保证。
4. 在最终发布提交上执行离线回归及明确启用的 fork 场景。跳过的 opt-in fork 不能算作实链验证；
   RPC 限流或归档读失败要记录并补跑，不应删除断言换取绿灯。
5. 复核 ABI、creation code、kind 注册、链 ID、地址簿和最终部署 readback；逐只股票检查 oracle、日历、交易池深度和毕业可行性。
6. 前端验收包含账户/网络切换、真实接收者报价、过期 terms、partial fill、退款币种、毕业事件、PoolId 切换，
   以及休市时“待入账”状态。新部署配置不覆盖旧实例的历史事实。

本页更新不触发链上签名、部署、注册或参数变更。历史报告保留原日期和条件；最新发布状态由对应 PR、最终提交和核验地址簿共同确定。
