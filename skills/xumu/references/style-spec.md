# 风格规范与合规检查

模型差异靠规范压：规范越是写成机器可读的参数和可运行的模板，模型只负责填空，出来的片子差异越小。但全锁死会出一千个一样的片子，所以**锁语法，放词汇**：时序、可读性、确定性渲染和风格标志动作锁住；色板、字体、插画、开场、人像、音乐方向放给频道档案，每个频道有自己那一份。

## 1. 规范文件

每种风格一个目录 `library/styles/<key>/`，`style.json` 随 Skill 发布；代表帧、样片和用户的参考片媒体在工作区 `library-media/`（见 [风格参考片库](style-library.md)，P5 第二步）。

`style.json` 由 `style_tools.py sync-catalog` 从 [风格目录](style-catalog.md) 生成，描述性字段（名称、大类、观感、标志动作、适合内容、实现、模板、参考片、组件）跟着目录走，再同步时自动更新；`spec`、`gallery`、`verified_in` 是人填的，同步不碰。

| 字段 | 说明 | 谁填 |
|---|---|---|
| `template` | `assets/templates/<key>` 存在时自动填；有模板 = L0 可用 | 自动 |
| `reference` | 目录里的 `mg15:` 编号；有参考片源码 = L1 可用 | 自动 |
| `needs_assets` | 目录标了"需素材" | 自动 |
| `spec.palette` | 十六进制色板，空 = 待定，首次成片后从通过验收的帧里取 | 人 |
| `spec.palette_status` | `verified`（来自成片或模板）/ `draft`（按观感猜的，待校准） | 人 |
| `spec.fonts` | 标题 / 正文 / 手写字体名，许可按 [素材来源](asset-sources.md) | 人 |
| `spec.strength_max` | 动作档位上限：克制 / 中 / 强；默认按大类（平面流派、复古、科技、三维为强，其余为中） | 默认 + 人 |
| `spec.max_chars_per_s` | 屏幕文字阅读速度上限，默认 4 字/秒；大字排版用 3 | 默认 + 人 |
| `spec.min_dwell_s` | 带文字的镜头最短停留，默认 1.2 秒 | 默认 + 人 |
| `spec.signature_moves` | 标志动作，从目录拆出；整片自检"风格一致"按它逐条核对 | 自动 + 人 |
| `spec.forbidden` | 这种风格里不该出现的东西（词），和栏目 `avoid`、品牌 `forbidden` 合并后检查 | 人 |
| `gallery.frame / sample / frame_kind` | 代表帧与样片路径；`frame_kind` 为 `render`（真渲染）或 `concept`（生图示意） | P5 第二步 |
| `verified_in` | 在哪些项目里实际跑通过 | 人 |

```text
python <skill>/scripts/style_tools.py sync-catalog              # 目录改了之后补齐 / 更新描述
python <skill>/scripts/style_tools.py list | show <key>
python <skill>/scripts/style_tools.py set <key> --set 'spec.palette=["#ffffff","#2b2b2b"]' --set spec.palette_status=verified
```

某个风格第一次在项目里通过验收后，把色板、字体、动作档位写回规范（`palette_status=verified`），把项目名记进 `verified_in`，再按 [风格模板的沉淀](style-stack.md#9-风格模板的沉淀) 整理模板。

## 2. 自由度

决策书第 9 格的 `freedom`（栏目层可固定）决定模型有多大发挥空间：

| 档 | 允许 | 检查器怎么判 |
|---|---|---|
| L0 填空 | 真实素材、Shotcraft 镜头、**有模板**的风格做 MG / 插画 | `mg` / `illustration` 镜头的风格没有 `template` → 不通过；`three` / `external` → 不通过 |
| L1 调参 | L0 之外，还允许有参考片源码的风格；可改色板、字体、动作档位、开场变体 | 既无模板也无参考片的 `mg`、以及 `three` / `external` → 不通过 |
| L2 混合 | 定制镜头不超过两成 | 定制镜头数 > ⌈镜头数 × 0.2⌉ → 不通过 |
| L3 自由 | 规范只做参考 | 只查风格一致、禁用项、可读性 |

"定制"指没有模板也没有参考片源码的 `mg` / `illustration`，以及 `three`、`external`。弱模型默认 L0，中等 L1，强模型 L2，L3 要用户点名。

## 3. 合规检查

```text
python <skill>/scripts/style_tools.py check --edit <edit> [--frames <edit>/verify/frames] [--strict]
python <skill>/scripts/style_tools.py check --plan <visual-plan.json> --freedom L1 --style whiteboard-world [--assist …] [--forbid 竞品]
```

`--edit` 时自由度与主风格从 `director.json` 第 9、6 格读，辅助风格、避开清单、品牌禁区从频道档案读；报告写 `verify/style-check.json` 与 `.md`。

| 项 | 不通过 | 提醒 |
|---|---|---|
| 自由度 | 见第 2 节 | |
| 风格一致 | 非 overlay 镜头的 `style` 不是主风格或辅助风格 | |
| 禁用项 | 镜头的 purpose / screen_text / quote / props 里出现规范、栏目、品牌任一禁用词 | |
| 可读性 | | 屏幕文字字数 ÷ 秒数 > `max_chars_per_s`；带文字镜头短于 `min_dwell_s` |
| 动作档位 | | 镜头 `props.strength`（或 `motion`）高于 `strength_max` |
| 静帧色板 | | `--frames` 目录里的静帧，离色板任一色 60 以内的有色像素少于 60%（近白近黑不计）；色板为空或 `draft` 时只提醒 |

不通过就不进合成：在流程 5 的 `plan_tools.py check --ready` 之前跑；`--strict` 把提醒也当不通过（专业模式、或交付前最后一遍）。提醒要逐条看过，确认是有意为之的写进 `project.md`。

## 4. 镜头里怎么写

- `style`：主风格或辅助风格 key；叠在人物画面上的花字、贴纸这类 `role=overlay` 镜头可以用别的风格（如 `variety-caption`）。
- `props.strength`：克制 / 中 / 强，定制 MG 的 brief 里按 [口播适配](mg-prompt-patterns.md#2-口播适配原提示词要翻译不能照搬) 降档后写进来。
- `screen_text`：实际出现在画面上的字，按它算阅读速度；逐句字幕由字幕层管，不写在这里。

## 5. 边界

- 规范没填色板时静帧比对跳过，不假装通过。
- 检查只看计划和静帧，判断"像不像这种风格"仍靠看帧和 `signature_moves` 逐条核对（原则 5）。
- 用户点名的风格或镜头与规范冲突时按原则 3：照用户的做，差距在 `project.md` 记一句，检查器的提醒随报告交付。
