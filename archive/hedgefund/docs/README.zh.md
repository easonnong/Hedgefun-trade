> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

<!-- translation-of: README.md @ 437e9b0e690dbe81e60796e5f7f20197e67da000 -->
# 文档

Robinhood Chain 上"策略代币 launchpad"的开发文档。这里全部是带相对链接的纯 Markdown，在 GitLab、GitHub 或本地打开看到的都一样。图用 [Mermaid](https://mermaid.js.org/) 画，两个平台都能直接渲染。

> 这是中文版。**英文版是唯一的权威版本**：合约、审计和紧急预案以英文文档为准，中文版落后时以英文为准（站点会在构建时提示哪些译文已经过期）。还没有翻译的页面会自动显示英文原文。

## 从这里开始

| 如果你想… | 看 |
|---|---|
| 弄懂这是什么、各部分怎么拼在一起 | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| 编译、跑测试、安全地改代码 | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| 知道信任了什么、防住了什么、哪些是明知而未解决的 | [SECURITY.md](./SECURITY.md) |
| 查一个函数、selector、错误或常量 | [REFERENCE.md](./REFERENCE.md) *（自动生成，不要手改）* |
| 彩排或执行一次部署 | [DEPLOYMENT.md](./DEPLOYMENT.md) |
| 上架一只股票、做日常巡检、看懂一条告警 | [OPERATIONS.md](./OPERATIONS.md) |
| 看哪些先上线、哪些留给 v2，以及为什么 | [ROADMAP.md](./ROADMAP.md) |
| 写网站、公告或发币表单 | [LAUNCH_KIT.md](./LAUNCH_KIT.md) |
| 处理一次事故 | [`../emergency/README.md`](../emergency/README.md) |

**想要一个网站而不是一个文件夹？** `pip install mkdocs-material mkdocs-static-i18n jieba`，然后 `tools/docs_site.py serve`：在 http://127.0.0.1:8000 得到搜索、侧边栏、渲染好的 Mermaid 和中英文切换，全部由这些文件现拼出来（没有为它另写任何内容，仓库始终是唯一的源头）。只限内部使用：里面有 SECURITY、AUDIT 和紧急预案。

**第一次来？** 按 ARCHITECTURE → DEVELOPMENT → SECURITY 的顺序读，大约四十分钟，足够去审一个 PR。

## 必须记住的一件事

**发出去的东西全部不可更改。** 一个代币、它的金库、以及所有策略的池子共用的那一个 `HedgeFunHook`，都没有升级路径，也没有任何可以修改的参数：

- 代币没有 owner；
- 金库的 owner 只能指定它所持股票的投票委托对象（`setVoteDelegate`，目前只是预留，链上还没有可投的票）；
- hook 的 owner（同一个，也就是工厂的 owner）只能改每个池子的两个收款地址，其中创建者的收款地址要先公开等待 14 天，创建者一次调用就能否决，除此之外什么也做不了。

代币或金库里的一个 bug 会永远留在所有在它存在期间发出的策略里；hook 里的一个 bug 会**同时影响所有策略**。所以审计的修复都赶在第一次发币之前合入，每个修复都有一个"去掉修复就会失败"的回归测试，[SECURITY.md](./SECURITY.md#rules-for-changing-the-code) 里写的是改代码的规则，而不是建议。

## 证据和分析

这些是已完成工作的记录，不是活文档：它们写的是成文当时的事实，并带有日期。

| 文档 | 内容 |
|---|---|
| [`../AUDIT.md`](../AUDIT.md) | 安全审计记录：多轮对抗性审计、Foundry 复现、go/no-go 结论，以及每个发现所依据的链上实测数据 |
| [STOCK_TOKEN_ASSESSMENT.md](./STOCK_TOKEN_ASSESSMENT.md) | 真实的 Robinhood 股票代币能对持有人做什么：beacon 代理、升级权、黑名单、暂停、`adminBurn`，逐项标注"已验证"或"推断" |
| [`../LISTING_CANDIDATES.md`](../LISTING_CANDIDATES.md) | 哪些股票能上架（194 → 35 → 25）、首批的决定、喂价在周末到底怎么表现 |
| [rule-backtest/](./rule-backtest/README.md) | 创建者的止盈、抄底、止损参数在历史上会得到什么：正放和倒放都跑。讲的是**规则的经济性**，不是合约安全 |
| [`../POOL_SELECTION.md`](../POOL_SELECTION.md) | *另一个*产品：用 Lighter 永续对冲的 delta 中性 LP。共用同一份池子普查 |
| [robinhood-chain/](./robinhood-chain/README.md) | 三页 Robinhood Chain 官方文档的镜像，每页都和链上实际行为核对过 |

## 让文档保持真实

- **[REFERENCE.md](./REFERENCE.md) 是生成的**：由 `tools/gen_reference.py` 从编译器的 ABI 输出和源码的 NatSpec 生成。要改就改 NatSpec，不要改 Markdown，然后重新生成。
- **`python3 tools/check_docs.py`** 会在任何相对链接或标题锚点失效、或参考文档过期时失败。重命名文件、标题或函数之前先跑它。
- **改行为的 PR，在同一个 PR 里改描述它的文档。** 怎么运作写进 ARCHITECTURE，防住或接受了什么写进 SECURITY，运维会因此改变的做法写进 OPERATIONS 和 `emergency/`。
- **数字会过期。** 分析文档里的池子深度、TVL、喂价年龄和测试数量都是带日期的测量值。要用就重新跑工具，不要引用旧数字。
- 保持可移植：只用相对链接，不用平台专属的 Markdown 扩展，代码块都带语言标签。
- **译文**放在原文旁边，文件名加 `.zh.md`，第一行记录它译自原文的哪个版本；原文变了，构建站点时会列出过期的译文。
