# 组织仓库运维入口

当前开发、审查和运维文档以 `0xHedgeHood/Hedgefun-trade` 默认分支 `codex/contract-v1` 为准。V1、V2 分别在 `contractV1/`、`contractV2/` 构建。新部署推荐 **1% 基础交易费（`taxBps=100`）**；创建者仍在工厂允许范围内选择，LP 费另计。已发行策略使用其冻结条款。完整权限和发布边界见 [合约范围](CONTRACT_SCOPE.md)。

## 先确认部署身份

操作或展示策略前，记录 `chainId + factory + strategyId`，从经核验地址簿和实时链上读数确认 factory、hook、router、treasury kind、owner、calendar 和 implementation。通过 factory 的策略登记验证身份；源码已合并不等于对应合约已部署或 kind 已注册。

[2026-10-03 测试网交接](../contractV2/docs/TESTNET_LAUNCH_HANDOFF_2026-10-03.md)和[地址簿](../contractV2/deploy/testnet-v2-fresh-creator.json)描述已有 stock/tUSDG 部署。该历史部署尚未启用 Native ETH，也不代表新版可升级默认金库、NAV Engine 或 Cycle 已注册。旧收据、费用和地址保持原版本。

## 当前 V2 工作路径

| 工作 | 文档与工具 |
|---|---|
| 新核心部署、收据与角色核验 | [V2 测试网](../contractV2/docs/TESTNET_V2.md)、[独立部署验证器](../contractV2/tools/verify_testnet_deployment.py)、[creator 核心验证器](../contractV2/tools/verify_fresh_creator_deployment.py) |
| 上架前检查股票价格、池深、毕业和执行 gates | [部署演练](../contractV2/docs/V2_DEPLOYMENT_REHEARSAL.md)、[上市检查工具](../contractV2/tools/v2_launch_check.py) |
| ETH 市场、桥接和原生币发射 | [ETH 市场](../contractV2/docs/TESTNET_V2_ETH_MARKET.md)、[桥接](../contractV2/docs/TESTNET_V2_ETH_BRIDGE.md)、[原生币发射](../contractV2/docs/V2_NATIVE_LAUNCH.md) |
| 基础费转换、分账、LP 收入和回购 | [双向手续费](../contractV2/docs/V2_TWO_SIDED_FEES.md)、[keeper 奖励](../contractV2/docs/TESTNET_V2_KEEPER_REWARD.md) |
| 普通策略执行与当前触发下限 | [AllIn runbook](../contractV2/docs/V2_ALL_IN_TESTNET_RUNBOOK.md)、[触发下限](../contractV2/docs/V2_ALL_IN_TRIGGER_FLOOR.md) |
| 新注册 Cycle 种类 | [Cycle 集成审查](../contractV2/docs/V2_CYCLE_INTEGRATION_REVIEW.md)、[keeper preflight](../contractV2/tools/v2_cycle_keeper.py) |
| 新默认金库升级 | [升级设计](../contractV2/docs/V2_BONDING_CURVE.md#treasury-upgrades-and-lp-isolation)、[controller 源码](../contractV2/src/v2/V2TreasuryUpgradeController.sol) |

只读检查从 `contractV2/` 执行，使用 Python 3.11 或更新版本和 Foundry。上市判断使用实际创建者的 `saleBps`、已部署配置与当时池深，不能把历史测量当作当前深度：

```sh
cd contractV2
python3 tools/read_testnet_readiness.py --book deploy/testnet-v2-fresh-creator.json --output /tmp/hedgefun-readiness.json
python3 tools/v2_launch_check.py --testnet --book deploy/testnet-v2-fresh-creator.json
```

这些命令读取链状态，不发送交易。发布仍按对应 runbook 核验收据、ABI、代码、链 ID、角色和 listings；历史测试中的跳过或 RPC 错误不算通过。

## 故障与权限

先按具体部署核对可用 owner 入口和实际影响。停止公开发射或禁用某只股票的 listing 影响新发射，不会暂停既有曲线或取回 LP 本金。calendar 的停市覆盖影响依赖它的策略定价与执行，不能当作 token 交易暂停；真实市场下跌时也要考虑停市会阻止止损。曲线未毕业的 treasury 健康状态与已毕业策略分开判断。

新默认 kind 0 的代理金库由独立 controller 管理。owner 排期后至少等待 48 小时，执行核对 implementation、配置、迁移数据和 factory 所有权轮次。待执行的升级可以通过 controller 的 `cancel` 取消；这不是即时资金救援机制。旧不可升级实例和其它种类不会自动获得升级能力。锁定 LP vault 没有提取本金或升级路径。

既有 V1 的 [Safe 应急工具与决策表](../archive/hedgefund/emergency/README.md)完整保存在组织仓库，配置仍针对原始 V1 部署。按[历史工具使用说明](../archive/hedgefund/README.md#using-historical-tools)复现；当前 V2 不能直接套用其中的地址簿或“所有 treasury 不可升级”结论。历史工具只构造 Safe batch；操作员仍需核对实时目标、owner 和 calldata。

## 审计和历史运维资料

[审计索引](../audit/README.md)连接当前 V2 审查与历史轮次。[历史运维说明](../archive/hedgefund/docs/OPERATIONS.md)、[部署记录](../archive/hedgefund/docs/DEPLOYMENT.md)、[股票发行方权限](../archive/hedgefund/docs/STOCK_TOKEN_ASSESSMENT.md)、[监控和上市工具](../archive/hedgefund/tools/)以及[公共 Safe 批次](../archive/hedgefund/deploy/safe/)均保留原版本。新工作在组织仓库提交，历史文件的出处和哈希见 [迁移清单](../archive/hedgefund/MANIFEST.json)。
