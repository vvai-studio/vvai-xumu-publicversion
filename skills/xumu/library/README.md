# 手法库

从用户发来的剪辑视频、风格案例和教程中归纳出的手法卡。

- `inbox/`：待用户确认的新卡（status: draft），制作时默认不检索。
- `cards/`：已确认入库的卡（status: confirmed），制作时按内容匹配调用。

规则见 `references/learning.md`；工具见 `scripts/library_tools.py`。素材（视频、抽帧、转录）不放这里，放在本机媒体目录。

- `styles/<key>/style.json`：298 种画面风格的规范（色板、字体、动作档位、可读性、标志动作、禁用项），由 `scripts/style_tools.py sync-catalog` 从 `references/style-catalog.md` 生成，`spec` 人填。合规检查见 `references/style-spec.md`。代表帧、样片与参考片媒体放工作区 `library-media/`，不放这里。
- `craft/recipes.json`、`craft/expressions.json`：18 类组合配方与 64 项表达指导（来自 chaojifeng-video-design，MIT），`scripts/craft.py` 检索；用法见 `references/craft.md`。
