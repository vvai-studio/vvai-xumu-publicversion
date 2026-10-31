# 命令速查与项目记录

全部脚本的用法一览。身份文件和流程细则只写工具名，参数以本文件和各脚本 `--help` 为准。

## 项目记录

跨片：工作区 `channel/`（`brand.json`、`series/<栏目>.json`、`changelog.md`）。按需生成：`director.json` 与 `创作决策书.md`（本片决策，唯一事实源是 JSON）、`project.md`（定位由 `director.py merge` 写入、确认、主风格与避开清单、进度、续作）、`footage/`（素材扫描、缩略图墙、选段）与 `edl_footage.json`、`beats.json`（剪素材链）、`edl.json`（使用 Video Use 时）、`visual-plan.json`（帧级时序与镜头）、`assets.json`（来源与授权）、`shot-selection.md`（选镜头与 MG 取舍，可并入 project.md）、`shots/<shot_id>/brief.md`（定制 MG 时）、`verify/`（验收证据与自检记录）。只记录实际发生的结果。

## 命令

```text
python <skill>/scripts/check_update.py [--force] [--json]   # 启动时后台跑：比对公开版本列表，只提示不更新
python <skill>/scripts/first_run.py [--check] [--no-key] [--smoke]   # 第一次用的总入口：环境自装 + 相邻 Skill + 动效索引 + 密钥网页 + 配置 + 免费体检
python <skill>/scripts/setup_env.py [--check]          # 每次进实际制作前：自检自装免费依赖（--check 只报告）
python <skill>/scripts/director.py init --workspace <工作区> --name <频道名> --platform <平台>   # 建频道档案（品牌层）
python <skill>/scripts/director.py series add --channel <工作区>/channel --key <栏目> --title <名> [--spine narration|storyline|script|music|order] [--style <风格key>] [--copy-from <栏目>]
python <skill>/scripts/director.py propose --edit <edit> --channel <工作区>/channel [--series <栏目>] [--inputs <素材…>] [--first-time]   # 决策书草稿
python <skill>/scripts/director.py inventory --edit <edit> --inputs <素材…> [--speech]   # 重新清点 + 脊梁建议
python <skill>/scripts/director.py classify --edit <edit> [--describe "这期一句话"] [--apply]   # 栏目打分 → 第 0 格
python <skill>/scripts/director.py reference --edit <edit> --ref <链接或文件> [--style-key <key>]   # "照着这个做"
python <skill>/scripts/director.py change --edit <edit> --scope one-off|series|new-series|brand --set 字段=值 [--reason "原话"]   # 改动范围三选一
python <skill>/scripts/director.py update --edit <edit> --from <内容.json>   # 总控填编剧页与导演页
python <skill>/scripts/director.py confirm --edit <edit> (--all | --grids 0,4,6) [--mode full-auto|semi|pro]
python <skill>/scripts/director.py check --edit <edit> --ready && python <skill>/scripts/director.py merge --edit <edit>   # 合并三层 → project.md 制作定位
python <skill>/scripts/director.py gates --edit <edit> | gate pass|skip <确认点> --edit <edit> [--note …]   # 决策书之后的确认点，按模式列出与记录
python <skill>/scripts/director.py migrate --edit <edit> --channel <工作区>/channel [--series <栏目>] | migrate --edit <edit> --skip   # 旧项目：建档 / 记下不建
python <skill>/scripts/board.py serve --workspace <工作区> [--edit <edit>] [--port 8765]   # 本地看板：决策书 / 频道 / 素材 / 画廊 / 进度，只做点风格、确认格、过确认点
python <skill>/scripts/mg_inspiration.py --use <用途> --max-energy <强度>   # 定制 MG 时筛灵感
python <skill>/scripts/style_tools.py list | show <风格key>                 # 风格规范：色板、字体、动作档位、标志动作
python <skill>/scripts/style_tools.py check --edit <edit> [--frames <静帧目录>] [--strict]   # 自由度与风格合规，报告进 verify/
python <skill>/scripts/style_tools.py set <风格key> --set 'spec.palette=[…]' --set spec.palette_status=verified   # 首次成片后回写规范
python <skill>/scripts/style_tools.py recommend --edit <edit> [--content 教程] [--tone 克制] [--apply]   # 3 个不同大类的方向配代表帧 → 第 6 格
python <skill>/scripts/style_tools.py learn --ref <参考视频> --key <风格key> [--title <新风格>] [--source <链接>]   # 参考片进库（仅本机）
python <skill>/scripts/style_tools.py gallery estimate | concept --confirmed | set <key> --frame … --kind render | html   # 代表帧与画廊
python <skill>/scripts/style_tools.py gallery sample <opuscar-key…> [--yes]   # 开源风格包的样片：先报大小，--yes 下载到媒体目录
python <skill>/scripts/craft.py recipes [词] | suggest --edit <edit> | apply <配方id> --edit <edit> | search <词> [--layer 转场] | show <id>   # 组合配方与表达指导
python <skill>/scripts/plan_tools.py check <edit>/visual-plan.json
python <skill>/scripts/plan_tools.py check <edit>/visual-plan.json --ready
python <skill>/scripts/plan_tools.py export <edit>/visual-plan.json --out <edit>/render-manifest.json
python <skill>/scripts/plan_tools.py stamp <edit>/visual-plan.json --shot <id> --force   # 镜头渲染验收后记录指纹
python <skill>/scripts/plan_tools.py diff <旧计划> <新计划>      # 修改影响：重渲 / 复用 / 只重新合成
python <skill>/scripts/plan_tools.py stale <edit>/visual-plan.json   # 哪些镜头文件已过期
```

剪辑与时间工具（用法见 [制作路线与合成](production.md#口播剪辑链)、[时间线契约](timeline.md#时间引用)）：

```text
python <skill>/scripts/voice_edit.py edl <edit>/keeps.json --out <edit>/edl_voice.json --report <edit>/剪后口播_核对.txt
python <skill>/scripts/voice_edit.py render <edit>/edl_voice.json --out <edit>/build/voice_cut.mp4 [--size 1080x1920]
python <skill>/scripts/voice_edit.py listen <edit>/edl_voice.json --video <edit>/build/voice_cut.mp4 --out-dir <edit>/verify/listen [--at 0:52] [--with-source]
python <skill>/scripts/voice_edit.py cues <edit>/edl_voice.json --transcripts <edit>/transcripts --out-dir <edit>
python <skill>/scripts/cue.py --edit <edit> resolve '{"cue": "跟地图", "section": "B09", "offset": 2.4}' '{"clip": "c0103", "edge": "end"}' '{"beat_near": 12.3}'
python <skill>/scripts/footage.py scan --edit <edit> --inputs <视频或目录…> [--scene 0.3] [--faces]   # 切镜头、打分、缩略图墙 footage/scan.html
python <skill>/scripts/footage.py beats --edit <edit> --music <曲>                               # 节拍 → beats.json
python <skill>/scripts/footage.py select --edit <edit> [--max-shot 6] [--min-score 50] [--music] | select --from <手选.json>   # 按故事线选段 → footage/picks.json
python <skill>/scripts/footage.py render --edit <edit> [--size 1080x1920] [--keep-audio] [--music <曲>] [--force]   # 粗剪预览 + edl_footage.json
python <skill>/scripts/cue.py --edit <edit> sync <edit>/visual-plan.json --out <edit>/visual-plan.r2.json --revision r2
python <skill>/scripts/transcribe_cloud.py estimate <素材…>    # 转录前：各引擎是否可用、是否上传、预估费用
python <skill>/scripts/transcribe_cloud.py run --engine azure|funasr <素材> --edit <edit> --confirmed   # 用户同意后
python <skill>/scripts/key_setup.py --status [--var VVAI_API_KEY]   # 查密钥是否已保存（离线，不显示密钥）；0 可用，1 未配置；“只有当前会话能读到”表示没存进这台电脑
python <skill>/scripts/key_setup.py [--var VVAI_API_KEY] [--replace]   # 后台运行：未配置时开本机临时网页，用户粘贴密钥，验证通过才保存；换密钥加 --replace；退出码 4 表示沙箱不让保存，照提示在沙箱外运行
python <skill>/scripts/audio_cloud.py setup [--yes]           # 写入造物社默认设置（生图 / 配音 / 配乐），不写密钥
python <skill>/scripts/audio_cloud.py setup --smoke --out <目录> --confirmed   # 试跑一句配音 + 一张图
python <skill>/scripts/audio_cloud.py doctor                  # 配置、密钥是否存在、连通、余额、各项渠道价格
python <skill>/scripts/audio_cloud.py voice list | presets [--gender 女] | audition --provider <服务商> --ids <ID,ID> --out <目录> --confirmed
python <skill>/scripts/audio_cloud.py voice register <名字> --provider <服务商> (--voice-id <ID> | --preset <ID>) [--yes]
python <skill>/scripts/audio_cloud.py voice estimate <文案.md> [--voice <名字>] [--edit <edit>]   # 报价，免费
python <skill>/scripts/audio_cloud.py voice speak <文案.md> --edit <edit> [--section S1] --confirmed [--max-cost N]
python <skill>/scripts/audio_cloud.py voice align --edit <edit>   # 逐字时间套回原文 → cue_chars.json、sections.json
python <skill>/scripts/avatar_cloud.py check --image <照片> | plan --edit <edit> [--model kling-v4|wan-3-0|kling-avatar] | estimate --edit <edit>   # 数字人：查图、分段、报价
python <skill>/scripts/avatar_cloud.py generate --edit <edit> --image <照片> --motion 中 --voice-ok "用户原话" [--only N] --confirmed   # 先样段再全量
python <skill>/scripts/avatar_cloud.py finish --edit <edit>   # 拼接、质检、逐字对齐 → avatar/final_avatar.mp4 + anomalies.json
python <skill>/scripts/audio_cloud.py music generate --edit <edit> --prompt … [--style …] --confirmed   # 配乐，一次两首
python <skill>/scripts/audio_cloud.py music fit <曲> --len <秒> --out <wav> | music mix --music <wav> --video <片> --out <片>
python <skill>/scripts/image_cloud.py estimate --prompt … [--aspect 16:9]   # 生图报价，免费
python <skill>/scripts/image_cloud.py generate --edit <edit> --name <镜头名> --prompt … [--aspect 9:16] [--ref <图>] [--transparent] --confirmed
python <shotcraft>/assets/scripts/sfx-source.py search "paper slide" --max-duration 1 --limit 5 | get fs:<id> --out-dir <edit>/audio/sfx | analyze <文件>   # Freesound 真实音效（<shotcraft> = 相邻 video-shotcraft 目录，默认 CC0）
python <skill>/scripts/sfx_synth.py make pop --out pop.wav | track events.json --len <秒> --out sfx.wav   # 本地合成 UI 提示音；events 里的 file 事件把下载的音效按能量峰铺进同一条轨
python <skill>/scripts/media_tools.py clips | cutpoint | level | measure | normalize | fontcheck ...
python <skill>/scripts/hf_upgrade_check.py --work <空目录>     # 每月一次：HyperFrames 受控升级检查
python <skill>/scripts/motion_index.py search 对比 | show gn:split-compare | show mg15:19-paperclip | show opus:caption-news | build --force
```

手法库工具（用法见 [学习模式](learning.md)）：

```text
python <skill>/scripts/library_tools.py new --name "<名称>" --kind <类别>
python <skill>/scripts/library_tools.py search <关键词…>
python <skill>/scripts/library_tools.py confirm <卡片 ID>
python <skill>/scripts/library_tools.py list | check
```

`<skill>` 换成本 Skill 的绝对路径；`python` 换成可用的 Python 3 解释器（Windows 上 `python`/`python3` 可能是微软商店占位符；可在个人 `backends.local.json` 中记录实际路径，见 `backends.local.example.json`）。所有工具默认只新建文件，覆盖需显式 `--force`。`export` 只输出标准化交接清单，目标文件已存在时拒绝覆盖。协议见 [时间线契约](timeline.md)。

