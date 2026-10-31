# 剪素材链：没有旁白做脊梁时怎么剪

脊梁是故事线、音乐或用户给的顺序（见 [创作板块](director.md#2-创作决策书) 第 2 格）时，流程 2 不走 `voice_edit.py` 的剪话链，走这条：**扫描 → 看图定取舍 → 选段 → 粗剪试看 → 锚点交给画面**。工具是 `scripts/footage.py`，产物都在 `<edit>/footage/` 和 `<edit>/build/`。

有旁白也有大量素材时（旁白为脊梁、素材做 B-roll），仍走剪话链锁时间线，本链只用 `scan` 给素材打分、做缩略图，选段时按句引用。

## 1. 扫描：切镜头、打分、缩略图

```text
python <skill>/scripts/footage.py scan --edit <edit> --inputs <视频或目录…> [--scene 0.30] [--min-shot 1.0] [--faces]
```

每条素材：ffprobe 时长与音视频轨 → ffmpeg 场景切分（`scene` 阈值，越低切得越碎；切点间短于 `--min-shot` 的碎片并入后一段）→ 每秒两帧的低分辨率灰度抽帧算亮度、过曝比例、清晰度（梯度均值）、运动量与运动方差 → 有音轨时静音检测算每个镜头的有声比例 → 有 OpenCV 且加 `--faces` 时在几帧上找正脸。

每个镜头一个 **可用度分**（0～100）和原因标记。阈值是经验值，只为排除明显不能用的镜头：

| 扣分 | 条件 | 标记 |
|---|---|---|
| −30 | 平均亮度 < 40 | 过暗 |
| −20 | 平均亮度 > 215 | 过亮 |
| −15 | 过曝像素 > 30% | 大面积过曝 |
| −20 | 清晰度不到本文件中位数一半 | 偏糊 |
| −15 | 运动方差 > 60（切点那一帧不算） | 抖/乱 |
| −5 | 运动量 < 0.3 | 几乎静止 |
| −10 | 短于 1.5 秒 | 太短 |
| 0 | 有声比例 ≥ 0.5 / 找到人脸 | 有声 / 有人脸（只是标记，选段时参考） |

产物：`footage/scan.json`（每个镜头 `id`、起止、各项指标、分数、标记、缩略图路径、`summary` 留给总控填一句）、`footage/thumbs/<id>.jpg`（镜头中点一帧）、`footage/scan.html`（缩略图墙，用户和总控都看这个）。镜头 id 形如 `c0103`：第 1 个文件的第 3 个镜头。

**分数只排序，不决定**。总控看过缩略图墙后在 `summary` 里写每个镜头是什么（"她推门进来""俯拍桌面"），有歧义的镜头抽帧看；用户要的"那个镜头"按 `summary` 找。

## 2. 节拍（脊梁是音乐时）

```text
python <skill>/scripts/footage.py beats --edit <edit> --music <曲> [--bpm-min 60 --bpm-max 180]
```

能量包络的正变化做起音强度，自相关选周期（半周期也够强时取快的那个，避免把 120 认成 60），再对齐相位，写 `beats.json`（`bpm`、`period`、`times`）。复杂编曲或无鼓点的曲子估不准：看 `bpm` 是否合理，不合理就缩小 `--bpm-min/max` 或让用户报 BPM 后手写 `beats.json`。

## 3. 选段：按故事线填

```text
python <skill>/scripts/footage.py select --edit <edit> [--max-shot 6] [--min-score 50] [--music] [--order time|score] [--total 60]
python <skill>/scripts/footage.py select --edit <edit> --from <手选.json>
```

自动选段读 `director.json` 第 4 格的故事线：每段的 `est_duration` 是要填满的秒数，`source_refs` 点名了镜头 id 就只用那些，点名了文件名就限定到那些文件，没点名就全部候选。候选按分数从高到低取，每段最多 `--max-shot` 秒（从镜头开头留 0.2 秒再取，避开切点闪帧），填满为止；段内默认按素材时间顺序排（`--order time`），保持自然连续。`--music` 时每段时长按节拍取整。没有故事线就用 `--total` 做一段。

产物 `footage/picks.json`：每段 `segment`、`target_s`、`total_s`、`short_by_s`（没填满差多少）、`clips[]`（`id`、`file`、`in`、`out`、`dur`）。**改选段直接改这个文件**，或总控按用户意见写一份只含 `segment` 和 `clips[].id`（可带 `in` / `out`）的 JSON 用 `--from` 导入。缺口（`short_by_s`）如实告诉用户：补拍、放慢、或接受短一点。

## 4. 粗剪试看

```text
python <skill>/scripts/footage.py render --edit <edit> [--size 1080x1920] [--fps 30] [--keep-audio] [--music <曲> --music-db -14] [--out …] [--force]
```

按 `picks.json` 顺序裁剪、统一画幅（等比放大后居中裁切）、拼接；默认不带素材现场声（`--keep-audio` 保留），`--music` 垫一首并在结尾淡出 1 秒。输出 `build/粗剪_预览.mp4`，文件名带"预览"，按 [交付规格门禁](qa.md#交付规格门禁硬性) 不能当成片交。同时写 `<edit>/edl_footage.json`：每段在节目时间里的 `start` / `end`。

试看是必经一步（原则 5）：总控自己看不了时把预览交给用户，连同 `picks.json` 的段落表，让用户指出换哪段、哪段长了。改完重跑 `render --force`，`edl_footage.json` 随之更新。

## 5. 锚点交给画面

粗剪定下后，画面事件（花字、标题、贴纸、转场、音效）的时间按 [时间线契约](timeline.md#时间引用) 写成引用，`cue.py` 多了两种锚点：

| 写法 | 含义 |
|---|---|
| `{"clip": "c0103", "edge": "start" \| "end", "offset": 0.4}` | 粗剪里这一段的起止 |
| `{"beat": 12}` / `{"beat_near": 12.3}` | 第 13 拍（从 0 数）/ 离 12.3 秒最近的一拍 |

没有旁白的片子不需要 `cue_chars.json`，`cue.py` 只读 `edl_footage.json` 与 `beats.json`；两种都有时可以混用（旁白段按句、空镜段按 clip）。`visual-plan.json` 的镜头照常用 `anchor` 引用，换一次选段后 `cue.py sync --revision` 顺延，`plan_tools.py diff` 列出要重渲的。

## 6. 边界

- 素材只有照片：`scan` 不处理图片；照片按阅读停留排帧，直接写进 `visual-plan.json`，时间用 `at` 或相邻 clip 的锚点。
- 一条素材里既有讲话又有大量空镜：先决定脊梁。旁白为脊梁时走剪话链，本链只扫描打分；画面为脊梁时讲话段也当镜头，`有声` 标记帮你找回来。
- 场景切分把缓慢的推拉当成一个镜头、把闪光灯当成切点：调 `--scene`，或在 `picks.json` 里手写 `in` / `out`。
- 没有 OpenCV 时 `faces` 为 `null`，不扣分也不加分。
- 分数、节拍都是粗判，和"以实物验收"不冲突：它们只决定先看哪些，不决定最终用哪些。
