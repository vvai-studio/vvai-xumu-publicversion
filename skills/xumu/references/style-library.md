# 风格参考片库：推荐时有图看

风格单一的根源不是目录条目少，而是推荐时用户看的是文字。参考片库把每种风格落成三样东西：**规范**（[style-spec.md](style-spec.md)）、**代表帧与样片**（画廊）、**用户学过的参考片**（本机）。推荐时直接贴图，用户点一个。

## 1. 媒体目录

规范 `library/styles/<key>/style.json` 随 Skill 发布；图和视频一律在工作区的媒体目录（`backends.local.json` 的 `learning.media_root`，或环境变量 `XUMU_LIBRARY_MEDIA`，命令上也可 `--media`），不进仓库：

```text
<media_root>/styles/
  index.html                 # 画廊索引页（gallery html 生成；网页看板也读它）
  <key>/concept.jpg          # 生图示意帧（frame_kind=concept）
  <key>/render.jpg           # 真帧：首次成片验收后登记（frame_kind=render）
  <key>/refs.json            # 用户给的参考片索引（仅本机）
  <key>/refs/01/meta.json    # 每份参考：来源、切点密度、运动量、亮度、色板、关键帧、10 秒样片
  <key>/refs/01/kf_01.jpg …  # 关键帧
  <key>/refs/01/sample.mp4
  _generated/                # 生图的原始产物与计费日志（image_cloud 的 edit 目录）
```

`style.json` 的 `gallery.frame` / `gallery.sample` 是相对媒体目录的路径，`frame_kind` 说明它是什么：

| frame_kind | 来源 | 可信度 |
|---|---|---|
| `render` | 实际成片通过验收后的帧 | 真实效果 |
| `concept` | 造物社生图的风格示意板（约 ¥0.04 一张，16:9）；原图在媒体目录，640 宽的小图打包进 Skill 的 `assets/gallery/<key>.jpg` 随包发布，所以装了序幕的人画廊一开始就是满的 | 只示意观感，不代表动态；画面上标"示例" |
| `reference` | 用户给的参考片关键帧；挑 1–3 帧拼成 640×360 打包进 `assets/gallery/<key>.jpg` 随包发布，其余关键帧与样片仅本机 | 真实，但不是序幕做的 |

`opuscar-` 开头的 59 种风格的代表帧也是 `reference`：取自 Lemo-Opuscar 样片（CC BY 4.0，`gallery.credit` 署名），样片不随包，`gallery.sample_url` 是在线直链，`gallery sample <key…>` 先报大小、加 `--yes` 才下载到 `<media_root>/styles/<key>/sample.mp4` 并核对哈希（见 [风格与技术栈](style-stack.md#11-开源风格包opuscar)）。

第一次用某个风格做出成片后，用 `gallery set <key> --frame styles/<key>/render.jpg --kind render` 把示意换成真帧。

**新增风格或模板时代表帧的来源顺序**：用户有视频案例 → `learn` 从视频截关键帧（`reference`），色板与节奏也从它学；没有视频案例 → `gallery concept` 用图片模型生成示意板（`concept`）；做出成片后 → 换成真帧（`render`）。先问有没有参考视频，有就不要直接生图。

```text
python <skill>/scripts/style_tools.py gallery estimate [--keys …]            # 报价：还没代表帧的有几张、每张多少
python <skill>/scripts/style_tools.py gallery concept [--keys …] --confirmed [--max-cost 1] [--jobs 4] [--force]   # 生成示意帧，默认按 budget.concurrency 并发，自动写回 gallery
python <skill>/scripts/style_tools.py gallery set <key> --frame <相对路径> [--sample …] --kind render|concept|reference
python <skill>/scripts/style_tools.py gallery html [--out …]                 # 重建索引页
python <skill>/scripts/style_tools.py gallery pack                           # 媒体目录里的示意帧补打包进 assets/gallery/
python <skill>/scripts/style_tools.py gallery sample <key…> [--yes]          # 开源风格包的样片：报大小 / 下载并核对哈希
```

生图走 [造物社](backends.md#造物社-api配置一次图片配音配乐共用) 的生图规则：先报价，用户在个人配置里设了免确认额度时额度内直接执行；失败不扣费、不自动换渠道。示意帧的提示词由规范的观感、标志动作、适合内容拼成（`concept_prompt`），要求像真实视频截图、无水印无 logo、不画人脸特写、不出现真实品牌。

## 2. 推荐：三个方向，不同大类，有图优先

```text
python <skill>/scripts/style_tools.py recommend --edit <edit> [--content 教程] [--tone 克制] [--platform 抖音] [--query …] [--apply]
python <skill>/scripts/style_tools.py recommend --content 记录 --tone 中 --json
```

打分（每条风格）：

| 项 | 分 |
|---|---|
| 内容描述、栏目标题与描述、决策书一句话 与 风格名称、适合内容、观感 的字词命中（中文按相邻两字） | 每个 +1，最多 6 |
| `--tone` 给了动作语气：规范的 `strength_max` 不超过它 | +1；超过 −2 并注明 |
| 有模板 / 有参考片 | +2 / +1 |
| 有代表帧 | +1 |
| 栏目 `avoid` 里的 | 不参与 |
| 频道日志里最近被换掉的（`style.main：A → B` 的 A） | −3 并注明 |

按分数排序后，从不同大类各取一个，共三个（`--n` 可改）。`--apply` 把三个方向写进决策书第 6 格的 `style_options`（key、代表帧、样片、一句话差别），`style_choice` 留给用户点。没有代表帧的方向，按 [创作板块](director.md#导演页) 的规则现场渲染一张效果草稿。

推荐只是起点：用户给了参考（`director.py reference`）就不走推荐；用户点名的风格按原则 3 照做。

## 3. 学习：用户的参考片进库

用户发来一支喜欢的片子说"学一下这个风格"时，先按 [学习模式](learning.md) 取得文件（下载前说明来源与大小并取得同意），再：

```text
python <skill>/scripts/style_tools.py learn --ref <本地视频> --key <风格key> [--title <新风格名>] [--source <链接>] [--note …] [--keyframes 8]
```

它复用 [剪素材链](footage-cut.md) 的扫描：场景切点密度（每分钟切几次）、运动量、亮度、主色（每秒一帧量化后取最多的 6 色）、8 张关键帧、中段 10 秒样片，全部存进媒体目录的 `refs/<n>/`，并在 `refs.json` 记一条。规范只补两处：色板为空就填学到的色板（`palette_status=draft`），没有代表帧就用中间那张关键帧（`frame_kind=reference`）；切点密度与运动量换算成动作档位提示 `learned.strength_hint`（≥30 切/分或运动 ≥8 为强，≤8 切/分且运动 <3 为克制）。

目录里没有的风格：给 `--title` 建一条 `family="X. 用户新增"` 的规范，同时在 [风格目录](style-catalog.md) 加条目，下次 `sync-catalog` 会把描述字段对齐。

**边界**：只学画面语言、结构与节奏参数，不复制对方素材、字体与音乐（`refs.json` 每条都带这句）；参考片的具体内容和品牌不进规范；关键帧与样片只在本机。色板与档位是粗判，首次成片后按验收结果回写。

## 4. 按需找参考（用户没想法时）

导演可以按栏目的内容类型和平台去搜同类热门片（用会话里实际可用的搜索与抓取工具，抖音需要用户自己保存文件），拿封面与关键帧回来给用户看两三组，用户点一组再 `learn` 进库、`recommend` 时自然排前。这是流程，不是脚本：每一步要说明来源，抓取前取得同意。
