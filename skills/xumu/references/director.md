# 创作板块：编剧页与导演页

把素材或想法剪成成片，序幕替代三个人：编剧（讲什么、怎么讲）、导演（什么画面、什么风格、什么节奏）、剪辑师（怎么切、怎么接、怎么合）。三个角色是总控在不同阶段的身份，不是三个子 agent。本文件管前两个角色的产物：频道档案与创作决策书。剪辑师从流程 2 开始，按 [制作路线与合成](production.md) 执行。

文件工具是 `scripts/director.py`，只管结构、校验、渲染与合并；脊梁、故事线、风格方向这些判断由总控写进 JSON。

## 1. 三层档案

下层继承上层，同名字段下层覆盖上层。品牌层保证"还是同一个人的片子"，栏目层保证"这类内容有固定做法"，单片层只记本期特例。

| 层 | 文件 | 记什么 | 改动频率 |
|---|---|---|---|
| 品牌 | `channel/brand.json` | 人像方式、平台、语言、品牌色、字体、旁白声音、片头片尾、禁区、喜欢的参考 | 几乎不改 |
| 栏目 | `channel/series/<key>.json` | 一类内容的做法：描述、脊梁、受众、主风格与避开清单、剪辑尺度、时长、画面比例、声音、自由度、预设 | 偶尔新建或调整 |
| 本片 | `<edit>/director.json` | 创作决策书：只记与栏目不同的部分和本期特有内容 | 每片 |
| 日志 | `channel/changelog.md` | 品牌层与栏目层的每次改动：日期、字段、从什么改成什么、原因 | 随改动 |

`channel/` 是频道的记忆，固定放当前工作区根目录（用户指定则按指定），不放 Skill 目录，插件更新不覆盖。同一台机器多个频道各自一个工作区；决策书记录 `channel_path`。栏目 key 由序幕起名（从内容描述取两三个词的拼音或英文），用户可改。

**没有档案时**：先问三件事，一次问完：做什么内容、发哪里、喜欢谁的片子（链接、名字或"没有"）。有参考就进 [学习模式](learning.md) 拆出色板、字体类型、动效强度、人像方式填草稿；没参考就从素材推断内容，品牌色与字体给两组候选。以一页"频道档案草稿"给用户确认后再写入：

```text
python <skill>/scripts/director.py init --workspace <工作区> --name <频道名> --platform 抖音 --platform B站 [--from 答案.json]
python <skill>/scripts/director.py series add --channel <工作区>/channel --key ai-tutorial --title "AI 工具教程" --spine narration --style whiteboard-world [--from 栏目.json]
python <skill>/scripts/director.py series list --channel <工作区>/channel
```

用户说"只做这一期、不建档"也可以：品牌层与栏目层留空，全部写进本片层，下次再问要不要存档。

**旧项目**（只有 `project.md`，没有 `director.json`）：不自动迁移。用户回到旧项目时提示一句"这个项目还没有频道档案，要从它的制作定位建一份吗"：

```text
python <skill>/scripts/director.py migrate --edit <edit> --channel <工作区>/channel [--series <栏目>]   # 点是
python <skill>/scripts/director.py migrate --edit <edit> --skip                                       # 说不用
```

`migrate` 把 `project.md` 里"制作定位"一节的原文和能拆出的"键：值"行存进 `director.json` 的 `migrated`，各格按栏目默认起草、全部标 `proposed`，模式 `semi`；总控按原文填各格（`update --from`），再给用户确认一次。没有频道档案就先 `init`；栏目没定就先 `classify` 或 `series add`。`--skip` 在 `project.md` 顶部写一个标记，之后不再问；用户改主意时 `migrate --force`。

## 2. 创作决策书

每部片一份，`<edit>/director.json` 是唯一事实源，`创作决策书.md` 由它渲染。归属格在最前，然后编剧页五格、导演页四格。每格带 `status`：`proposed` 建议 / `confirmed` 用户确认 / `edited` 用户改过。

### 归属格

| 格 | 字段 | 写什么 | 用户 |
|---|---|---|---|
| 0 归属 | `series` `series_confidence` `series_action`（reuse / new / one-off） | "这期归【AI 工具教程】，沿用白板"；或"看起来是新类型，建议新建栏目" | 点"对"或改 |

### 编剧页

| 格 | 字段 | 编剧写什么 | 用户 |
|---|---|---|---|
| 1 有什么 | `inputs[]`（path、kind、duration_s、has_audio、summary 一句话）、`gaps[]` | 清点素材与想法；缺什么（要补拍、要找、要生成） | 看一眼，补缺项 |
| 2 脊梁 | `spine.kind` `spine.source` `spine.reason` | 这部片锚在什么上，为什么 | 认可 |
| 3 一句话 | `promise` | 观众看完要记住的一件事 | 认可或改 |
| 4 故事线 | `storyline[]`（id、goal、source_refs[]、beat、est_duration）、可选 `recipe`（id、name） | 讲什么、什么顺序、每段达成什么、哪里是高点；beat 取 铺垫 / 证据 / 转折 / 高点 / 落点；套用了 [组合配方](craft.md) 时记下是哪一类 | 认可或调顺序 |
| 5 删留 | `must_keep[]` `cut_candidates[]` `opener` `closer` `target_duration` | 旁白片：删什么话、开场用哪段；素材片：选哪些段、弃哪些段 | 认可 |

**脊梁**是整条时间线锚定的那条东西，按"用户有什么"判断，不预设片型：

| 用户有什么 | 编剧的工作 | 脊梁通常是 |
|---|---|---|
| 有旁白（录好的，或文案要合成） | 提炼、删改，故事线大体已在旁白里 | `narration` |
| 有素材没旁白 | 从素材里找故事线，或按用户想法组织素材 | `storyline` / `music` / `order`（用户给的顺序） |
| 有想法没素材 | 写故事线；导演标出每段要生成、要找、要用户补拍 | `script` |
| 有剧本和按剧本拍的素材 | 对剧本挑条、定顺序 | `script` |
| 混合（最常见） | 先判断以哪个为脊梁，其余围绕它排 | 由编剧定 |

脊梁决定时间引用的锚点类型：[时间线契约](timeline.md#时间引用) 的"哪句 / 哪段 + 偏移"扩成"锚点 + 偏移"，锚点可以是句、段、素材片段（`clip`）或音乐节拍（`beat`）；后两种由 [剪素材链](footage-cut.md) 的 `edl_footage.json` 与 `beats.json` 提供。

编剧页的分析对象随输入变：有旁白读转录，有素材看画面（时长、场景、人脸、运动、可用度），只有想法则写文案。`propose --inputs` 或 `inventory` 用 ffprobe 清点时长与音视频轨（`--speech` 再用 ffmpeg 的静音检测估每条前两分钟的非静音比例 `speech_ratio`：只是"有没有声音在响"，有配乐或环境声时会偏高，真要分辨讲话还得听或转录），按"讲话 / 无声画面 / 照片 / 文字"的构成给出脊梁建议写进第 2 格；`summary` 和 `spine.source` 要总控看过素材后自己填，填了 `source` 之后 `inventory` 不再覆盖脊梁。

### 导演页

| 格 | 字段 | 导演写什么 | 用户 |
|---|---|---|---|
| 6 风格方向 | `style_options[]`（key、frame、sample、diff 一句话差别）、`style_choice` | 同栏目只有一项"沿用"；新栏目或用户要换时给 3 个拉开差别的方向，各配代表帧与样片；有参考时直接写参考 | 点一个 |
| 7 画面与节奏 | `visual_ratio` `strong_motion_slots[]` `evidence_segments[]` `rhythm` `avatar` | 人物 / 真实素材 / 动画各占多少，强动效只放哪几处，哪些段必须看到真实画面，整片节奏曲线；要不要数字人出镜（见下） | 看一眼 |
| 8 声音 | `narration` `music_direction` `sfx_level` `live_sound` | 旁白方式、音乐方向、音效强度、是否保留现场声 | 看一眼 |
| 9 预算与自由度 | `paid_items[]`（item、quote）、`render_estimate_min` `freedom` `mode` | 付费项报价、预计渲染时长、自由度档位、托管模式 | 默认即可 |

第 6 格的来源按优先级：用户给的参考（`director.py reference`，或 `style_tools.py learn` 进库）> 栏目已定风格 > `style_tools.py recommend --edit <edit> --apply`（按内容、栏目描述、语气打分，不同大类各一个，见 [风格参考片库](style-library.md)）。代表帧来自画廊（真帧 / 生图示意 / 参考片关键帧）；没有的，用本片真实内容的一句或一段现场渲染一张当"效果草稿"（每个方向约 1～3 分钟），文件名带"草稿"，不进成片，格内注明"无样片"。

`reasons[]` 记每个建议的一句理由，全托模式下代替逐段确认（对应 SKILL.md "用记录理由代替逐段确认"）。

### 命令

```text
python <skill>/scripts/director.py propose --edit <edit> --channel <工作区>/channel [--series <key>] [--inputs <素材…>] [--first-time] [--mode full-auto|semi|pro]
python <skill>/scripts/director.py inventory --edit <edit> --inputs <素材…> [--speech]   # 重新清点第 1 格 + 脊梁建议
python <skill>/scripts/director.py classify --edit <edit> [--describe "用户这期的一句话"] [--apply]   # 栏目打分；--apply 写第 0 格
python <skill>/scripts/director.py reference --edit <edit> --ref <链接或文件> [--style-key <key>] [--notes …]   # "照着这个做"
python <skill>/scripts/director.py change --edit <edit> --scope one-off|series|new-series|brand --set 字段=值 … [--new-key k --title t] [--reason "用户原话"]
python <skill>/scripts/director.py update  --edit <edit> --from <总控写的内容.json>     # 按 grids 深合并，版本 +1，重渲 md
python <skill>/scripts/director.py render  --edit <edit>
python <skill>/scripts/director.py check   --edit <edit> [--ready]                    # --ready：全部确认且必填齐
python <skill>/scripts/director.py confirm --edit <edit> (--all | --grids 0,4,6) [--edited] [--mode …] [--series-action reuse|new|one-off]
python <skill>/scripts/director.py merge   --edit <edit> [--draft]                    # 三层合并 → project.md 的"制作定位"
python <skill>/scripts/craft.py suggest --edit <edit> | apply <配方id> --edit <edit>   # 第 4 格：对照 18 类组合配方，故事线空时按配方起草
```

`propose` 生成的草稿已经继承了栏目与品牌的默认值并清点了素材；总控把编剧页与导演页的判断写成一个只含要改字段的 JSON，用 `update --from` 合进去。`merge` 写进 `project.md` 的表每项标注来自本片 / 栏目 / 品牌和确认状态，后续流程读这张表，不再另写制作定位。

## 3. 每部片的流程

```
素材 + 想法 ──► 清点"有什么" ──► 判断脊梁 ──► 与栏目比对
                                              │
        ┌─────────────────────────────────────┼──────────────────────┐
        ▼                                     ▼                      ▼
  匹配且把握大                          匹配但把握小               无匹配
  第 0 格：沿用栏目                     第 0 格：两个候选栏目      第 0 格：建议新建栏目
  第 6 格：一项"沿用"                   让用户点一个               第 6 格：3 个方向配图
        └─────────────────────────────────────┴──────────────────────┘
                                              ▼
                      编剧页：一句话、故事线、删留（分析素材或转录）
                                              ▼
                      导演页：画面与节奏、声音、预算与自由度（栏目默认 + 本期调整）
                                              ▼
                      渲染决策书 ──► 用户确认 / 修改 ──► merge
                                              ▼
                      剪辑师从流程 2 开始（剪话链或剪素材链）
```

**栏目识别**：`classify` 按两条打分：素材构成推出的脊梁与栏目 `spine.kind` 是否一致（+2），用户这期的一句话描述与栏目标题、描述、提示值的字词命中（每个 +1，最多 5）。把握 `high`（最高分 ≥3 且领先 ≥2）直接沿用；`medium` 沿用但在第 0 格注明让用户看一眼；`low` 建议新建。分数和理由都打印出来，总控可以不采纳，用 `confirm --series-action` 改。

**什么时候才问用户**：第一次出现新类型、脊梁判断把握不大（既有讲话又有大量空镜）、栏目识别把握不大、用户主动说"这期换个做法"、第 1 格有缺项要用户补、第 9 格有付费项或预计渲染超过约 30 分钟。其余情况整份默认通过，用户一句"开工"即可。

## 4. 托管模式

| 模式 | 决策书 | 后续流程 |
|---|---|---|
| `full-auto` 全托 | 只需确认第 0、4、6 格；其余记理由 | 参考片门（前 60～90 秒）一次确认，之后自主推进 |
| `semi` 半托 | 两页都展示，默认通过，用户可改 | 现有流程的三次确认（剪辑策略、画面方案、参考片门） |
| `pro` 专业 | 两页都展示，不默认通过 | 现有流程全部确认点 |

首次建档的新手默认 `full-auto`（`propose --first-time`），已有档案的用户沿用上一次的模式；用户说"你看着办 / 全部交给你"切 `full-auto`，说"每步都问我"切 `pro`。

**模式必须可见**：决策书顶部固定一行写当前模式、会在哪几处停下来问、怎么切换（`render` 自动写）；开工时的第一句回复也复述一次。用户不理解自己处在哪种模式，比多问一次更糟。

**决策书之后的确认点**由模式决定哪些必过，`gates` 列出，每过一个记一笔：

| 确认点 | 所在流程 | 全托 | 半托 | 专业 |
|---|---|---|---|---|
| `edit-strategy` 剪辑与旁白策略 | 1 | 不停，按第 5 格做并记理由 | 必过 | 必过 |
| `listen` 剪点试听合集 | 2 | 不停 | 不停（总控自己能听时） | 必过 |
| `visual-plan` 画面方案 | 3 | 不停，按第 6、7 格做 | 必过 | 必过 |
| `reference-clip` 参考片门 | 4 | **必过，唯一一次整片确认** | 必过 | 必过 |
| `delivery` 整片验收 | 5 | 不停（交付门禁照跑） | 不停 | 必过 |

```text
python <skill>/scripts/director.py gates --edit <edit>                       # 本片要过哪些、过了哪些
python <skill>/scripts/director.py gate pass reference-clip --edit <edit> [--note "用户确认了镜头力度偏克制"]
python <skill>/scripts/director.py gate skip reference-clip --edit <edit> --note "沿用上期已确认风格的续作"   # 跳过必须给理由
```

"不停"只是不等用户点头，付费、超时渲染、缺素材、叙事含义或主风格要变时仍然要问（原则 6）。`merge` 写进 `project.md` 的确认点一行反映当前状态，交付前应没有必过项还是 ○。

## 5. 改动范围

用户在任何阶段要求改风格、剪辑尺度、人像方式、脊梁等栏目级字段时，先问清范围，默认第一项：

| 范围 | `change --scope` | 写到哪 | 日志 |
|---|---|---|---|
| 只这一期 | `one-off` | 本片 `director.json` 的 `overrides`，对应的格标 `edited`；合并表里标"本片 · 已改" | 不记 |
| 以后这个栏目都这样 | `series` | 栏目层，并同步本片的格 | `changelog.md` 记一行：字段、旧值 → 新值、`--reason` 原话、哪部片触发 |
| 新开一个栏目 | `new-series --new-key k --title t` | 复制当前栏目为新 key 再改字段，本片指向新栏目，第 0 格 `series_action=new` | 记一行 |

字段用 `--set 字段=值`，值能当 JSON 读的就当 JSON（`duration.target_s=[60,90]`、`sound.live_sound=true`），否则是字符串。栏目字段与决策书格的对应（`style.main` ↔ 第 6 格、`spine.kind` ↔ 第 2 格、`duration.target_s` ↔ 第 5 格、`visual_ratio` ↔ 第 7 格、`sound.*` ↔ 第 8 格、`freedom` ↔ 第 9 格）由脚本维护；没有对应格的字段（如 `edit_policy.cut`）只改档案或 `overrides`。

品牌层字段（人像、品牌色、字体、声音、禁区）只有两个范围：`one-off`（`--layer brand`）和 `brand`。改 `brand` 前先复述影响范围（"以后所有栏目的片子都会用这组色"）再执行。栏目层与品牌层冲突时栏目优先，第 7 格注明。推荐风格前读 `changelog.md` 最近的改动，不把刚改掉的风格再推回来。

**"照着这个做"**：用户贴链接或发文件时不走推荐，`reference --ref` 把该参考写成第 6 格唯一方向并记进 `assets.json` 的来源；进学习模式拆出风格与节奏特征，与风格目录比对，最接近的 key 用 `--style-key` 给出，差异写 `--notes`（存为 `style_notes`）；参考片的结构同时给编剧页做故事线参考。确认后问是否存为本栏目默认（`change --scope series --set style.main=…`）。只学画面语言、结构与节奏参数，不复制对方素材、字体与音乐。

## 6. 与下游的对接

| 下游 | 从决策书拿什么 |
|---|---|
| `project.md` 制作定位 | `merge` 写入的表：每项来自本片 / 栏目 / 品牌与状态；故事线与缺口 |
| 剪话链 `voice_edit.py` | 脊梁为 `narration` 时，第 5 格的删留作为锚点保留表的输入 |
| [剪素材链](footage-cut.md) `footage.py` | 脊梁为 `storyline / music / order` 时：第 4 格每段的 `est_duration` 是要填的秒数，`source_refs` 点名镜头 id 或文件名限定候选；第 7 格 `rhythm` 决定 `--max-shot` 与段内顺序；`scan` 的缩略图墙是第 1 格 `summary` 的依据 |
| [内容到画面](directing.md)、流程 3 | 第 6 格 `style_choice` 作主风格，栏目 `avoid` 作避开清单；第 7 格 `evidence_segments` 是"必须真实素材"的段落，`strong_motion_slots` 限制强动效位置；第 4 格每段 `goal` 对接 [解说语法](explainer-grammar.md) 的句子作用 |
| 声音后端 | 品牌层 `voice` 与第 8 格作为 `audio_cloud.py` 的默认音色与音乐需求 |
| 自由度 → [风格规范与合规检查](style-spec.md) | 第 9 格 `freedom` 与第 6 格 `style_choice` 由 `style_tools.py check --edit` 读取：L0 只用有模板的风格与现成组件；L1 可改色板、字体、动作档位、开场变体；L2 不超过两成镜头做定制 MG；L3 规范只做参考。栏目 `avoid` 与品牌 `forbidden` 作为禁用项一起检查。锁住的始终是时序、可读性、确定性渲染与风格标志动作 |
| [参考片门](qa.md#参考片门) | 全托模式下这是唯一一次整片确认 |
| [本地看板](board.md) `board.py serve` | 读 `channel/`、`director.json`、`footage/scan.html`、风格画廊、`visual-plan.json`、`verify/` 渲染五个页；只做点风格、确认格、过确认点三种写操作，全部转调本文件的命令 |

## 7. 边界

- 清点失败（文件损坏、格式不支持）：第 1 格列出不可用项，不阻塞其余。
- 脊梁判断不了：第 2 格给两个方案（以讲话为脊梁 / 以画面为脊梁配后期旁白）让用户选。
- 只有想法没素材且用户不接受生成：第 1 格 `gaps[]` 变成补拍 / 找素材清单交付，流程停在这里，档案与决策书保留，补齐后续作。
- **数字人只在两种情况下用**：用户自己说要（`avatar.source = user_asked`），或总控认为这条片子适合（`suggested`），例如用户没有出镜素材、栏目要人脸建立信任、手上有本人的口播照片。建议时第 7 格写 `avatar: {use: true, source: suggested, reason: "…", model: minimax-h3}`，理由写给用户看（为什么需要人出镜、用哪张照片、大约多少钱），**第 7 格经用户确认之后** `avatar_cloud.py generate` 才会生成；没写或没确认，脚本直接拒绝。默认 `use: false`。没有决策书的临时项目，只有用户明确要求时用 `--user-asked "用户原话"` 记下来。做法见 [数字人](avatar.md)。
- 用户改了决策书但与原则 4（真实可追溯）冲突：执行用户决定，第 7 格标注该段为示意，交付时按 [验收与交付](qa.md) 如实标注。
- 决策书只记录实际发生的判断与确认；没问过用户的格不标 `confirmed`。
