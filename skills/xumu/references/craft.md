# 组合配方与表达指导

两份"怎么讲清楚"的参考，来自 [chaojifeng-video-design](https://github.com/mileson/chaojifeng-video-design)（MIT），随包在 `library/craft/`：

| | 是什么 | 谁在什么时候用 |
|---|---|---|
| **组合配方**（18 类，`recipes.json`） | 一种整片或整段的组织方式：需要什么输入，分 4–8 步，每步的镜头目的、画面动作、声音职责和检查；带用到的表达、基础动效和适合的风格 | 编剧排决策书第 4 格"故事线"时 |
| **表达指导**（64 项，`expressions.json`） | 一个局部手法：目的、怎么变换、输入、参数、约束、退路、检查问题；分叙事、镜头、转场、视觉、动画、文字、声音、交互、风格统一、制作组织、知识表达 11 层 | 导演设计镜头、写镜头 brief 时 |

它们和序幕已有的几层不重叠：[解说语法](explainer-grammar.md) 管"这句话在做什么 → 画面怎么组织"；[Shotcraft](shotcraft-direction.md) 管具体镜头卡；手法卡（`library_tools.py`）是从用户发来的视频里学的；`gn:` / `hf:` 是现成动效与组件。配方在它们之上管整片结构，表达在镜头之内管局部手法的检查。

都是指导，不是执行器：用了某个配方不代表能做出来，也不代表效果已验证，本片照常实测。

## 配方：编剧页第 4 格

```text
python <skill>/scripts/craft.py recipes [词…]                 # 列出 / 搜索
python <skill>/scripts/craft.py suggest --edit <edit> [--query "补一句"]   # 按第 3 格一句话、第 1 格素材摘要推荐 3 个
python <skill>/scripts/craft.py show <配方 id>                 # 全文：输入、分步、检查、变体
python <skill>/scripts/craft.py apply <配方 id> --edit <edit> [--force]
```

- 先有一句话（第 3 格）和素材清点（第 1 格），再 `suggest`；对不上就不用配方，照常写故事线。
- `apply` 把配方记进第 4 格 `recipe`；故事线还空时按配方步骤起一版草稿（`goal` 取镜头目的，`beat` 粗分为铺垫 / 证据 / 转折 / 高点 / 落点，`recipe_step` 记对应第几步），`source_refs` 与时长由编剧按素材补。故事线已有就只记配方，不覆盖（`--force` 重起）。
- 配方的 `inputs` 是做这种片子必须有的东西，缺的写进第 1 格 `gaps`；步骤里的 `checks` 和 `questions` 在整片自检时逐条过。
- 有 `variants` 的配方（如"用真实任务证明产品价值""发布片情绪弧"）列出了短版与跳步版，片长或观众熟悉度不同时用。
- 配方里的 `styles` 只是常配的风格，风格仍由第 6 格按栏目和推荐定。以音乐为主线的四类配方（音乐事件成为可见动作、产品音乐叙事、概念知识科普、嘻哈知识科普）需要先定曲子，配乐走 [声音后端](backends.md)。

## 表达：导演页与镜头 brief

```text
python <skill>/scripts/craft.py search <词…> [--layer 转场]    # 例：search 对比；search --layer 声音
python <skill>/scripts/craft.py show transition.match-cut sound.attention-mix
```

- 一个镜头要用某种局部手法时（例如共享形体过渡、先读后动、把注意留给主要声音），`show` 它，把 `params` 里要定的参数写进镜头 brief，`constraints` 当这镜的禁区，`questions` 当验收问题。
- `composition` 写了常与哪些表达搭配；配方的 `expressions` 列出这类片子常用的几条，可以从那里进。
- `fallback` 是做不出来时的退路，按它降级，不要硬做。
