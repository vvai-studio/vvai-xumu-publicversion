# 风格目录：画面语言速查

镜头的 `style` 字段取本目录的 key。选法与分层规则见 [风格与技术栈](style-stack.md)；句子级的画面组织见 [解说语法](explainer-grammar.md)；素材与字体的许可见 [素材来源](asset-sources.md)。表中 `gn:` / `hf:` / `mg15:` / `opus:` 为 `motion_index.py` 可查的现成实现。

每部片通常一个主风格加至多一个辅助风格。用户没指定时，从不同大类里挑 2–3 个拉开差别的方向，各配一张代表帧。需要新风格时，先在 project.md 写下 key、观感、标志动作与实现，再使用。

标注说明：**已验证** = 在序幕实际成片中跑通；**有模板** = `assets/templates/` 下有可运行模板；**需素材** = 依赖生成图或授权图片，代码无法独立完成；**有参考片** = [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) 有这种风格的 10 秒参考成片、完整提示词、确定性源码和可检验的标志特征（`mg15:` 编号，用法见 [风格与技术栈](style-stack.md#10-风格参考片mg15)），或 [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) 有这种风格的完整规则、原生动作菜单、一支 30 秒到 2 分多钟的样片和确定性源码（`opus:` 编号，key 以 `opuscar-` 开头，用法见 [风格与技术栈](style-stack.md#11-开源风格包opuscar)）。`opuscar-` 的 59 种和目录里原有的风格有些相近（"近亲"一栏写在实现里），它们是独立的风格：观感和标志动作以样片为准。其余风格目前只有目录条目与组件指引，首次实际使用时按 [风格与技术栈](style-stack.md#9-风格模板的沉淀) 沉淀模板。

## A. 教学解说

| key | 观感（底色 · 字体 · 图形） | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `whiteboard-world` 白板一镜到底 **已验证 · 有模板**（[做法](whiteboard-world.md)） | 白底大画布、手写体、灰色手绘箭头串起各站点 | 一台镜头推、甩、拉，下潜进手绘显示器接真实录屏；画笔手跟随 | 教程、案例拆解、工作流讲解 | HyperFrames；`hf:whiteboard-ink` `hf:hw-arrow` `hf:pan-stations` `gn:infinite-pan`；站酷快乐体 |
| `whiteboard-ink` 白板手画 | 白板 + 马克笔，图和字一笔一笔画出来 | 描边画出、手写出字，跟口播节奏 | 知识科普、流程讲解 | `hf:whiteboard-ink` `hf:hw-write-title` `gn:handwriting-write-on`；rough.js |
| `chalkboard` 黑板粉笔 | 墨绿或黑板底、粉笔纹理、手写 | 粉笔描画、擦除转场 | 课堂感、数学、复盘 | SVG 描边 + 粉笔纹理滤镜；`gn:line-boil` `gn:scribble-wipe` |
| `notebook-doodle` 笔记本涂鸦 | 方格或横线纸、圆珠笔蓝、便利贴 | 涂鸦圈注、便利贴贴上、翻页 | 学习笔记、个人经验 | rough-notation；`hf:hw-underline` `hf:hw-callout-circle` `gn:page-turn` |
| `flat-diagram` 扁平图解 | 浅底、SVG 分层图形、实体色块 | 实体保持身份，按阅读顺序登场 | 概念、机制、流程 | `hf:flowchart` `gn:progressive-disclosure` `gn:dashed-flow` |
| `isometric` 等距 2.5D **有参考片** | 等距网格、立体方块、柔和阴影 | 分层抬升、爆炸拆解、镜头缓移 | 系统架构、产品结构、空间 | SVG 或 Three.js 正交相机；`gn:exploded-assembly` `gn:layer-separation`；`mg15:03-isometric` |
| `sticker-explainer` 贴纸科普（回形针式） **有参考片** | 冷静的蓝灰或米白底、照片抠图加粗白描边成"贴纸"、扁平图标与精确图表、等线字体 | 超大画布上一台镜头长缓动平移缩放，每句旁白带出一个新元素；柱状图生长、数字滚动、路线描出 | 硬核科普、财经、跨学科知识口播 | `mg15:19-paperclip` `gn:infinite-pan` `hf:data-chart`；照片 **需素材** |
| `cartoon-collage` 卡通拼贴 | 米色纸纹、扁平插画剪贴、色块胶囊、手写 | 剪贴落地、近景 → 滑行 → 拉远 | 科普、轻教育 | 插画剪贴 **需素材**（Open Peeps 或生成后去背）；`hf:hw-box-label` |
| `cartoon-stage` 卡通舞台 | 明亮扁平、一景一个舞台、关节角色、无字幕 | 角色动作讲故事，机器、水、植物自己动 | 有角色的科普、社会议题 | SVG 关节角色；`gn:character-articulation` `gn:walk-cycle` `hf:lottie-character-walk` |
| `blueprint` 蓝图工程 | 蓝底白线、网格、尺寸标注、等宽字 | 线条描出结构、尺寸线展开、局部放大 | 产品原理、结构拆解、技术方案 | `gn:line-draw` `gn:outline-then-fill` `hf:svg-stroke-trace` |
| `math` 原理推导 | 素底、精确图形与公式 | 一次只变一处 | 数学、物理、算法 | Manim 或 SVG；`gn:vector-tip-to-tail` `gn:plane-transformation` |
| `particle-explainer` 暗场粒子讲解 | 纯黑底、成千上万的细发光粒子与轨迹线，一条黄色主轨迹，斜体西文标题，论文截图斜放入画 | 粒子从噪声团沿轨迹流向目标形状；路径一步步拉直；数值与步数标注随步骤刷新；整片无人出镜，旁白驱动 | AI 原理、生成模型、算法、物理过程 | Three.js `Points` 或 Canvas 2D，按确定性种子逐帧算；`gn:particle-assemble` `gn:particle-force-field` `gn:ambient-particle-drift`；论文截图 **需素材** |
| `opuscar-whiteboard` 白板讲解 **有参考片** | 一块反光白板，单线手写一笔一笔写出，马克笔悬空自己写，磁贴可移动，留着旧课残影 | 按笔顺书写、笔带着镜头走、板擦倒带擦除、最后拉出整板 | 知识科普、网课、理科讲解 | `opus:whiteboard`（Canvas / SVG 源码）；近亲 `whiteboard-ink` |
| `opuscar-iso-infographic` 等距信息图 **有参考片** | 等距视角的扁平三色块小场景、细墨线标签、Isotype 计数小人 | 剖开看内部、数字用图形个数画出来、焦点加上下文、尺度揭示 | 流程讲解、供应链、年报 | `opus:iso-infographic`（Canvas / SVG 源码）；近亲 `isometric` |
| `opuscar-briefing-board` 工程简报板 **有参考片** | 实拍白板墙：窗光、擦过的残影，真实物件抠图贴上，磁贴、尺子、印章，三色马克笔各有固定含义 | 镜头沿尺寸线从一条事实走到下一条、磁贴当计数、擦成残影、最后拉远看整面简报 | 工程方案、方案对比、汇报简报 | `opus:briefing-board`（Canvas / SVG 源码）；物件照片 **需素材** |
| `opuscar-blueprint` 蓝图 / 工程制图 **有参考片** | 普鲁士蓝晒图纸、白色工程线稿、标题栏、尺寸标注 | 按制图顺序画出、标注会动、图号当转场、投影视图当镜头 | 工程、硬件发布、技术讲解 | `opus:blueprint`（Canvas / SVG 源码）；近亲 `blueprint` |
| `opuscar-midcentury-toon` 50s 扁平卡通 **有参考片** | 1950 年代平涂色块，颜色印得偏离断续墨线，抽象色块房间，冷爵士配乐 | 身体不动只有手在做事、圆形标注、编号奖章、最后功能变装饰 | 操作指南、帮助中心、跟着做的教程 | `opus:midcentury-toon`（Canvas / SVG 源码）；近亲 `flat-vector` |

## B. 新闻纪实

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `visual-journalism` 视觉新闻 | 黑底、真实照片配来源标签、黄色荧光笔、红色警示、虚线标注 | 照片推近、荧光扫过、圈注、数字计数 | 时事、行业事件、争议话题 | `hf:vox-annotate` `hf:marker-highlight` `gn:annotation-callout`；真实图片 **需素材** 且需授权 |
| `editorial-light` 杂志编辑 | 白或米底、大留白、细线、衬线标题配小号无衬线 | 线条描出、平稳滑入 | 深度分析、商业、观点 | `hf:caption-editorial-emphasis` `gn:underline-draw`；思源宋体 |
| `documentary-archive` 档案纪录 | 老照片、胶片框、打字机文字、档案夹、日期戳 | 慢推老照片、盖章、打字 | 人物史、公司史、复盘 | `gn:ken-burns` `gn:typewriter` `gn:stamp-impact` `gn:film-dust-scratches` |
| `data-viz` 数据图解 | 干净底色、坐标与单位清晰 | 数据驱动的生长、计数、排序 | 指标、对比、趋势 | `gn-recipe:data-story` `hf:data-chart` `hf:bar-chart-race`；数值来自来源文件 |
| `map-journey` 地图叙事 | 简化地图、路线、定位钉 | 定位 → 路线描画 → 沿途标注 | 旅行、物流、地缘、扩张 | `gn:map-route-animation` `hf:world-map` `hf:nyc-paris-flight` |
| `vintage-engraving` 复古版画 | 棕黄旧纸、铜版或木刻插图、古典衬线、锈红批注 | 版画逐层显现、手写批注 | 历史、传记、发明史 | 版画插图 **需素材**（公版图或生成）；`gn:hatch-fill` `gn:outline-then-fill` |
| `opuscar-caption-news` 字幕新闻 **有参考片** | 真实画面与原始文件铺底，超大中文字幕是主角，关键词压黄色块，角落挂来源标签与素材署名 | 第 4 帧砸出最大的数字、字幕分块砸入、原文件高亮后才报数字、定格提问、分账双栏、推近圈注 | 社交新闻、报告解读、数据短片；静音也能看懂 | `opus:caption-news`（素材合成 源码）；近亲 `visual-journalism`；真实素材 **需素材** |
| `opuscar-news-package` 电视新闻包装 **有参考片** | 电视台包装系统：片头变台标角标、常驻底栏、今日要闻目录、翻牌价格板、引语卡、印章 | 片头缩成角标、要闻目录逐条打勾、底栏不离场、翻牌前后对比、数值冲破阈值线 | 新闻汇总、快讯、行情播报 | `opus:news-package`（素材合成 源码）；真实素材 **需素材** |
| `opuscar-visual-investigation` 视觉调查 **有参考片** | 冷色调查桌：同一件事的视频、照片、文件、声音、地图对齐在同一条时钟上 | 定格圈出放大、硬同步点、三栏同步网格、带播放头的数据图、已知与未知分栏、证据地图收尾 | 事件复盘、事实核查、事故还原 | `opus:visual-investigation`（素材合成 源码）；近亲 `visual-journalism`；真实素材 **需素材** |
| `opuscar-kino-montage` 构成主义蒙太奇 **有参考片** | 档案影像、照片、文件印成一张黑白纸本海报，只有一种红，斜向色带承载文字 | 文件用红笔标出而不是引用、文件变图表、两张图撞出第三个意思、人物剪下堆成结构、静默后重击 | 行业史、里程碑、集体奋斗 | `opus:kino-montage`（素材合成 源码）；近亲 `bauhaus-geometric`；档案素材 **需素材** |
| `opuscar-countdown` 实时倒计时分屏 **有参考片** | 一个有确定零点的真实事件（发射、宣判、终场哨），屏幕时间等于事件时间，秒表常驻 | 越接近零点分屏越多、每格同一秒、归零时合成一个画面、时钟翻转 | 发布倒计时、直播事件、重大时刻 | `opus:countdown`（素材合成 源码）；事件录像 **需素材** |
| `opuscar-telestrator` 体育战术板 **有参考片** | 电视足球分析：真实比赛画面上直接画，脚下光圈、马克笔箭头、红色空当，比分条与角标包装 | 定格后画线、跟踪光圈、逐帧秒表、双机位定格、透视压平成战术板 | 体育分析、比赛复盘、教练讲解；也可借来拆解任何录像 | `opus:telestrator`（素材合成 源码）；比赛录像 **需素材** |
| `opuscar-city-symphony` 延时交响 **有参考片** | 城市延时摄影把车流、人流、云变成光河，没有旁白，音乐主导 | 切点随配乐细分越来越密、一处慢到几乎停住、在重拍上硬切黑场 | 城市片、音乐蒙太奇、开场 | `opus:city-symphony`（素材合成 源码）；延时素材 **需素材** |
| `opuscar-archive-lighttable` 档案灯台 **有参考片** | 冷色背光灯台上摊着真实档案：玻璃底片、幻灯片、信件、电报、剪报；干净现代，不加做旧滤镜 | 放大镜落下、底片在镜里转成正片、一行字亮起、照片打开纵深、两份记录并排对照 | 品牌史、档案故事、博物馆 | `opus:archive-lighttable`（Canvas / SVG 源码）；近亲 `documentary-archive`；档案扫描 **需素材** |
| `opuscar-satellite-briefing` 卫星简报 **有参考片** | 真实卫星图压成分析员灰，地面上画细白测量线：锁定准星、轮廓、测距线、一个读数 | 从轨道一镜推到地面再拉回、锁定画面里时间流动、故事转折处颜色回来 | 气候、新闻解读、地理 | `opus:satellite-briefing`（Canvas / SVG 源码）；近亲 `map-journey`；卫星图 **需素材** |
| `opuscar-dataviz` 数据叙事 **有参考片** | 米色纸上红蓝铅笔逐个画出真实数据点，手写批注钉在数字旁 | 一个标记一个事实、坐标轴随故事伸长、编码变形、尺度切换、留出空白的下一格 | 数据新闻、报告、气候与科学 | `opus:dataviz`（Canvas / SVG 源码）；近亲 `data-viz`；数据来自来源文件 |
| `opuscar-microscope` 显微叙事 **有参考片** | 真实显微图像，一次连续变倍从手里的载玻片推到单个细胞；比例尺、视野、读数来自图像元数据 | 下潜、变倍时对焦呼吸、焦平面扫过、两个圆圈对比下结论、再爬回来 | 生物医学、材料科学、护肤科学 | `opus:microscope`（Canvas / SVG 源码）；显微图像 **需素材** |
| `opuscar-engraving` 铜版画 **有参考片** | 铜版自己雕刻：刻刀切出粗细变化的线，排线、交叉排线逐层加深，雕刻字与放大圆窗 | 三遍刻线成像、拓印出样张、放大圆窗看细节、手工上色 | 博物馆说明、科学讲解、品牌传承 | `opus:engraving`（Canvas / SVG 源码）；近亲 `vintage-engraving` |

## C. 界面与产品

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `clean-ui` 干净界面 | 真实截图或真实网页为底 | 镜头推到真实按钮；尺寸与圆角变化用弹簧 | 工具教程、产品功能 | `hf:ui-focus-zoom` `gn-recipe:product-demo` `hf:browser-device-stage` |
| `white-catalog` 白底目录 | 白色网格、产品抠图、混排字体、涂鸦 | 网格逐格填入、盖章、日期块 | 产品介绍、品牌、合集盘点 | `hf:grid-card-assemble` `hf:mk-placeholder-grid` `gn:stamp-impact` |
| `glass-ui` 液态玻璃 / 弥散渐变 **有参考片** | 半透明玻璃卡片、柔光、模糊背景 | 卡片浮起、折射扫光 | 科技产品、苹果风界面 | `hf:vfx-liquid-glass` `hf:ios26-liquid-glass` `gn:glass-refraction`；`mg15:12-aurora-glass` |
| `terminal-code` 终端代码 | 深色编辑器或终端、等宽字、语法高亮 | 打字、逐行高亮、diff 对比 | 编程、AI 工具、开发教程 | `hf:code-typing` `hf:code-diff` `hf:code-highlight` `hf:terminal-simulator` |
| `mascot-ui-diorama` 吉祥物界面剧场 | 深色软件窗口做成有厚度、受光、有投影的 3D 面板，原创体素小角色站在输入框上；暗红渐变底，换场后是深蓝走廊、夜城等低多边形场景 | 角色看着字被打出、对回复做反应；慢推 → 漫画惊吓猛拉（速度线、问号）；像素块斜向铺满再同向散开换章节；常驻 HUD 记录筹码与倒计时 | AI 工具拟人化、挑战实验、无旁白剧情短片、口播里的演绎插入段 | Three.js + HTML 逐帧；`hf:grid-pixelate-wipe` `gn:radial-speed-lines` `gn:character-gaze-reaction` `gn:squash-stretch` `gn:rolling-digits`；界面为示意重绘，角色用原创或已授权形象 |
| `brutalist-mono` 粗野等宽 | 黑白硬网格、等宽与窄体字、光标闪烁 | 硬切、方块位移、乱码解码 | 开发者、极客、冷观点 | `gn:hard-cut` `gn:hard-appearance` `hf:scramble-reveal` |
| `opuscar-dark-keynote` 暗色科技发布 **有参考片** | 近黑渐变、发丝网格、柔光、一个品牌强调色，界面本身是主角 | 吸附网格精准移动、光扫揭示、乱码滚成一个巨大数字、定格、收起 | 产品发布、SaaS、发布会 | `opus:dark-keynote`（Canvas / SVG 源码）；近亲 `cinematic-dark` |
| `opuscar-living-screencast` 活体实机录屏 **有参考片** | 看起来像真实录屏，低分辨率吉祥物住在高清界面里，替软件把正在做的事演出来 | 光标和吉祥物都是角色、聚光定格、带标签的快进、卡拉 OK 小球跟字 | 产品教程、功能上线、新手引导 | `opus:living-screencast`（Canvas / SVG 源码）；近亲 `mascot-ui-diorama`；产品界面 **需素材** |
| `opuscar-hologram-hud` 科幻全息界面 **有参考片** | 物体被扫描成发光线框，目标框锁住部件，引线拉出，数字从乱码滚到真实数值 | 扫描生长、目标锁定、局部爆炸、数字滚动、最后亮成实体全息 | 参数讲解、发布视频、展会 | `opus:hologram-hud`（Canvas / SVG 源码）；近亲 `cyber-hud` |
| `opuscar-glass-product` 玻璃质感产品 **有参考片** | 暗场棚拍、透明与磨砂玻璃产品、灯条扫光、色散、焦散，光在物体内部走 | 透明折射、光在内部穿行、慢速爆炸图在重拍上合拢、磨砂变透明 | 产品发布、消费电子、美妆 | `opus:glass-product`（Three.js / WebGL 源码）；近亲 `soft-3d` |
| `opuscar-teardown` 产品拆解 **有参考片** | 用产品自己的工程文件（CAD、PCB、物料表）建模，棚拍质感，当着镜头拆开 | 部件沿一条轴波浪抬升、镜头穿进缝隙、引线落到零件并报出文件里的数值、合拢 | 硬件发布、产品详情页、参数讲解 | `opus:teardown`（Three.js / WebGL 源码）；近亲 `exploded-diagram`；工程文件 **需素材** |

## D. 平面设计流派

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `kinetic-type` 大字排版 | 一屏一句、字号层级克制 | 遮罩揭示，在语义词处落定 | 观点、金句、章节标题 | `gn-recipe:title-opener` `hf:per-word-rise` `gn:mask-reveal` |
| `poster-colorblock` 海报色块 | 大面积纯色场、超粗大字被画框裁切 | 色块擦除、字撞画框 | 观点冲击、口号、活动 | `hf:headline-slam` `hf:caption-kinetic-slam` `gn:kinetic-type-sweep` |
| `swiss-grid` 瑞士国际主义 | 严格网格、无衬线、不对称、红黑白 | 沿网格滑入、对齐落定 | 理性分析、方法论、设计话题 | `gn:grid-draw` `gn:motion-hierarchy` `hf:dynamic-grid` |
| `bauhaus-geometric` 包豪斯几何 **有参考片** | 原色圆、方、三角，几何构成 | 形状组合拼成意象、旋转咬合 | 抽象概念、结构关系 | `gn:shape-split-merge` `gn:piece-assembly` `gn:shape-built-letters`；`mg15:09-bauhaus` |
| `line-art` 一笔画线条 **有参考片** | 单色或双色等宽细线、大量留白 | 线条自我描出并转折成下一个图形，上一形的尾线即下一形的起线；描完轮廓再由锚点铺满色面 | 品牌片、概念串联、logo 落版 | `mg15:02-line-art` `gn:line-draw` `hf:svg-stroke-trace` |
| `morph` 形变叙事 **有参考片** | 少量纯色图形、色场 | 一个图形连续变成另一个（手机变定位钉），复杂形先收成圆或胶囊再展开，形变中带挤压与轻转 | 概念转换、因果串联、品牌意象 | `mg15:08-morph` `gn:shape-morph`；路径插值用 flubber 或 MorphSVG |
| `memphis` 孟菲斯 | 撞色、波浪线、点阵、几何碎片 | 弹跳、抖动、贴纸弹出 | 轻松话题、年轻向、生活方式 | `gn:jello` `gn:wobble` `hf:spring-pop` |
| `risograph` 孔版印刷 | 有限套色、套印错位、颗粒 | 图层错位抖动、颗粒闪动 | 文艺、独立品牌、读书 | 多色图层 + 混合模式；`gn:animated-dither` `gn:halftone-motion` |
| `halftone-comic` 美漫网点 | 网点阴影、粗描边、分格、拟声字 | 分格推进、拟声字爆出、速度线 | 故事化讲述、反转、娱乐 | `hf:halftone-field` `hf:halftone-dissolve` `gn:radial-speed-lines` |
| `manga` 日漫 | 黑白网点、速度线、集中线、竖排对白 | 集中线冲击、分镜格切换 | 情绪高点、二次元、游戏 | `gn:radial-speed-lines` `gn:stamp-impact`；角色 **需素材** |
| `opuscar-swiss-motion` 瑞士动态排版 **有参考片** | 模块网格、一种字体、一种信号色，运动像印刷机一样精确 | 网格有含义、吸附即拍点、极端字号对比、一处例外、刀切、重新排版 | 品牌识别、活动、设计教育 | `opus:swiss-motion`（Canvas / SVG 源码）；近亲 `swiss-grid` |
| `opuscar-art-deco` 装饰艺术 **有参考片** | 黑漆、雕刻金线、喷枪几何，1930 年代海报动起来；构图有中轴 | 灯泡一盏盏亮起计数、沿中轴开合的门、机械万花筒、表盘推进剧情、金属光泽扫过 | 奢侈品与酒店、晚宴、邀请函 | `opus:art-deco`（Canvas / SVG 源码）；近亲 `luxury-dark` |
| `opuscar-pictogram-motion` 象形运动图形 **有参考片** | 方格核心图形（圆、半圆、花纹小格成排滑动）、圆头粗线拼成的象形小人、粗体双语字 | 一卡一项、每章一个颜色、每项一个动词、计数砸出、图标墙；每次切换都在鼓点上 | 体育赛事、视觉识别、活动开场 | `opus:pictogram-motion`（Canvas / SVG 源码）；近亲 `kinetic-type` |
| `opuscar-spy-titles` 60s 间谍片头 **有参考片** | 剪纸感四色片头，剪影人物穿过由片头字幕本身搭成的场景 | 文字就是布景、字幕当节奏、图形匹配剪、斜向网格、剪影木偶、最后拼出片名 | 片头、活动开场、预告片 | `opus:spy-titles`（Canvas / SVG 源码）；近亲 `poster-colorblock` |
| `opuscar-silkscreen-poster` 丝印旅行海报 **有参考片** | 不透明硬边平涂，每张 4–6 色，色阶代替渐变，套印错位留出细白缝 | 一色一拍逐层印出、分色喷泉渐变、换色重印、错位后对齐、路线作为一层印上 | 目的地介绍、文旅、活动海报 | `opus:silkscreen-poster`（Canvas / SVG 源码）；近亲 `poster-colorblock` |
| `opuscar-risograph` Risograph 孔版印刷 **有参考片** | 暖纸上两三种半透明专色叠印、网点、油墨颗粒，版永远对不准 | 分版讲故事、两色相交出第三色、叠印转场、错版做节奏、镂空揭示 | 独立品牌、杂志、生活方式 | `opus:risograph`（Canvas / SVG 源码）；近亲 `risograph` |
| `opuscar-halftone-dossier` 复古半调案卷 **有参考片** | 米色档案纸、几种平涂油墨叠印网点、巨大粗标题带错位阴影、粗描边角色 | 指控画面、编号证物、印章砸下、嫌疑人照、证据板、涂黑 | 幽默、宠物、社交短片 | `opus:halftone-dossier`（Canvas / SVG 源码）；近亲 `halftone-comic` |
| `opuscar-stained-glass` 彩色玻璃窗 **有参考片** | 暗石厅里看中世纪彩色玻璃窗，只有阳光照到的地方是活的 | 光就是时钟和镜头、玻璃投影到石墙、玻璃裂开铅条修补、窗格当图解 | 传说、遗产、节日故事 | `opus:stained-glass`（Canvas / SVG 源码） |
| `opuscar-woodcut` 木刻版画 **有参考片** | 每一帧都是一块黑木板，光只在刀刻掉的地方；最多一种颜色，只给燃烧的东西 | 刻即是时间、反刻木板拓出正像、刀痕当肌理、唯一色版扩散又收回、无字连环画式叙事 | 民间故事、手作品牌、图书预告 | `opus:woodcut`（Canvas / SVG 源码）；近亲 `vintage-engraving` |

## E. 插画与手作

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `hand-drawn` 手绘线条 / 线条沸腾 **有参考片** | 线条手绘、轻微抖动 | 笔触每秒变 12 次、镜头逐帧平滑 | 故事、经验分享 | p5.brush 或 SVG 描边；`gn:line-boil` `hf:hw-boil`；`mg15:05-cel-boil` |
| `watercolor-storybook` 水彩绘本 | 水彩晕染、纸纹、柔和笔触 | 笔刷铺色、角色轻动、翻页 | 故事、情感、童趣 | p5.brush、ClaudeAnimationBase；`gn:page-turn` `gn:popup-book`；渲染慢 |
| `paper-craft` 纸艺定格 | 纸片、撕边、投影、定格抖动 | 纸片按 8–12fps 定格移动、撕纸转场 | 手作感科普、生活 | `hf:stop-motion-cadence` `gn:paper-crumple` `gn:perforated-tear` `gn:papercut-placement` |
| `flat-vector` 扁平矢量 **有参考片** | 实色填充、风格化的手、扁平界面 | 形状轻微回弹 | 金融科技、App 宣传 | SVG；`gn:spring-overshoot`；Open Peeps；`mg15:01-flat-vector` |
| `sticker-pop` 贴纸照片 | 浅底与品牌色块交替、照片抠图、贴纸 | 抠图弹出、色块随节拍切换 | 种草、消费、电商 | `hf:badge-pop` `hf:spring-pop` `gn:scale-pop`；照片 **需素材** |
| `collage` 拼贴剪贴 **有参考片** | 老照片与报纸剪影加白边、半调网点、纸纹、比例失衡的超现实拼装 | 肩肘下颌分段转动、嘴巴换帧开合、主体按 12fps 定格并轻微手抖，"手拍上来"或翻纸转场 | 文化评论、音乐、潮流、脑洞话题 | 照片 **需素材**（CC0 / 公有领域，去背后加白边）；`mg15:06-collage` `gn:papercut-placement` |
| `variety-caption` 综艺花字 **有参考片** | 多层描边的胖圆体字、撞色加白边与投影、爆炸框汗滴闪光等手绘符号 | 弹性弹出（约 8 帧冲过再回落），比说话晚 2–3 帧出现，驻留时轻微摆动；情绪决定字形与符号 | vlog、萌宠、访谈、轻综艺；叠在人物画面上 | `mg15:18-hanazi` `hf:badge-pop` `hf:spring-pop`；花字与原话字幕样式区分（见 [综艺包装层](production-profile.md#4-综艺包装层)） |
| `opuscar-crayon-book` 蜡笔儿童绘本 **有参考片** | 粗纹纸上现场画蜡笔，水彩刷过时显出蜡笔藏着的东西 | 蜡笔防水显形、现场画出、涂色就是动作、线条抖动、孩子的逻辑、它是一本书 | 绘本、睡前故事、儿童学习 | `opus:crayon-book`（Canvas / SVG 源码）；近亲 `watercolor-storybook` |
| `opuscar-impasto` 油画厚涂 **有参考片** | 刮刀厚涂油画：大块锐边色面，侧光照出颜料起伏；先明暗结构后肌理 | 刮刀重铺颜色、只有一样东西有颜色、运动在画布上画出画面、侧光、覆盖式转场、声音可视化 | 音乐 MV、艺术文化、情感广告 | `opus:impasto`（Canvas / SVG 源码） |
| `opuscar-one-line` 一笔画 **有参考片** | 一根不离纸的墨线，画面上一切都是这根线正在画 | 笔不抬起、线就是时间、变形代替切换、停笔是事件、线变图表 | 品牌故事、人生节点、极简广告 | `opus:one-line`（Canvas / SVG 源码）；近亲 `line-art` |
| `opuscar-urban-sketch` 钢笔淡彩 **有参考片** | 现场写生本：棕褐细针管笔线抖动、出头、不封口，透明水彩随手点上、溢出线外 | 先线后色、上色表示到达、只给一样东西上色、纸页就是画框、胡萝卜小人 | 城市与旅行、建筑、生活方式品牌 | `opus:urban-sketch`（Canvas / SVG 源码）；近亲 `hand-drawn` |
| `opuscar-watercolor` 水彩笔刷 **有参考片** | 暖色棉纸上自己画出来的手绘日志：半透明笔触带飞白，手写注释，没有矢量线 | 画出即揭示、色块晕开、调色盘当数据、标本加注释、雾气擦除、地图随时间画出 | 自然纪录、旅行、科学讲解 | `opus:watercolor`（Canvas / SVG 源码）；近亲 `watercolor-storybook` |
| `opuscar-paper-popup` 纸片立体书 **有参考片** | 真实桌面上的立体书变成舞台：白边剪纸演员在从书页弹起的纸布景前表演，真实台灯与微距镜头 | 打开书、翻页换场、拉片机关、纸就是角色、真实物件参演 | 儿童书、游戏预告、故事短片 | `opus:paper-popup`（Three.js / WebGL 源码）；近亲 `paper-craft` |
| `opuscar-scifi-toon` 科幻情景喜剧卡通 **有参考片** | 成人向科幻情景喜剧：粗抖动描边、平涂、反应对不上的双人组、发光传送门，每个世界一套色 | 平行世界、双人反差、三连后连发、冷场反转、回扣收尾 | 喜剧、科技品牌、社交短片 | `opus:scifi-toon`（Canvas / SVG 源码）；近亲 `cartoon-stage` |

## F. 复古年代

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `pixel` 像素复古 **有参考片** | 小画布整数倍放大、关闭平滑 | 姿势按 8–12fps 量化，特效逐帧动 | 游戏、怀旧、科技史 | Canvas 2D；`gn:stepped-motion`；`mg15:20-pixel` |
| `crt-film` 老电视 / 胶片 | 扫描线、弧面、荧光点、颗粒、光晕 | 作为质感层叠在其他风格上 | 回忆、年代感 | WebGL 质感层；`gn:crt-scanlines` `gn:film-grain` `gn:vhs-tracking` |
| `retro-analog` 模拟复古 | 褪色、颗粒、70–90 年代几何字体 | 可控故障、粗推、定格 | 怀旧、音乐、娱乐 | `gn:gate-weave` `gn:film-grain` `hf:grain-overlay` |
| `vaporwave-y2k` 蒸汽波 / Synthwave / Y2K **有参考片** | 粉紫渐变、铬金属字、网格地平线、旧系统窗口 | 网格滚动、铬字旋转 | 互联网文化、潮流 | `gn:perspective-grid-drift` `hf:liquid-metal` `gn:liquid-metal`；`mg15:10-synthwave` |
| `opuscar-newsreel` 1920s 新闻影片 **有参考片** | 1920 年代末有声新闻片：探照灯地球台标配铜管、旋转飞来的报纸、快嘴解说、地点日期卡 | 台标仪式、报纸旋入、地图展开、照片发牌变翻页书、文件画线、蜡笔定格、乐队急停抖包袱 | 历史故事、年代潮流、周年纪念 | `opus:newsreel`（素材合成 源码）；近亲 `documentary-archive`；档案素材 **需素材** |
| `opuscar-silent-film` 1920s 默片 **有参考片** | 影院放映的版画插图默片：墨线银灰、4:3 拷贝闪烁晃动、天鹅绒幕布、字幕卡代替台词、钢琴伴奏 | 一镜到底的连锁反应、险些撞上、字幕卡反转、快放混乱、光圈收在眼神上 | 喜剧、复古品牌、无声叙事 | `opus:silent-film`（Canvas / SVG 源码）；近亲 `crt-film` |
| `opuscar-backrooms` 后室 / 新怪谈 **有参考片** | 从空荡、无尽、日光灯照明的空间里找回的摄像机录像带；没有怪物只有规则 | 自动对焦与曝光来回找、磁带跟踪损坏、屏显信息就是剧情、规则写在画面里、空与重复 | 悬疑、ARG、游戏预告 | `opus:backrooms`（Three.js / WebGL 源码）；近亲 `retro-analog` |
| `opuscar-rubber-hose` 1930s 橡皮管卡通 **有参考片** | 黑白手绘墨线卡通，万物都活着，跟着热爵士乐摇摆 | 一切按拍呼吸、音画同步、橡皮管拉伸、变形、跳球跟唱、胶片是实物 | 食品饮料、复古广告、儿童 | `opus:rubber-hose`（Canvas / SVG 源码）；近亲 `cartoon-stage` |
| `opuscar-cel-anime-80s` 80 年代赛璐璐动画 **有参考片** | 黄金年代 OVA 手绘赛璐璐：两色平涂角色、喷枪背景、逆光霓虹、有限动画节奏，按 80 年代录像带在 CRT 上播放 | 巨大画面里的小英雄、静止即戏剧、逆光、速度线、定格画上扫光、磁带瑕疵当标点 | 音乐 MV、游戏预告、怀旧 | `opus:cel-anime-80s`（Canvas / SVG 源码）；近亲 `manga` |
| `opuscar-pixel-rpg` 16-bit 像素 RPG **有参考片** | 看起来、听起来、用起来都像 90 年代中期主机 RPG：320×180、索引色、会打字的对话框、菜单、存档、芯片音乐 | 色板塌缩与泛色、存档当回忆、游戏界面当旁白、升级、遇敌旋涡、时代切换 | 游戏预告、年度回顾、怀旧 | `opus:pixel-rpg`（Canvas / SVG 源码）；近亲 `pixel` |
| `opuscar-ascii-crt` ASCII / CRT 终端 **有参考片** | 屏上一切都是等宽网格里的真实字符，被老式单色 CRT 的荧光点亮 | 画面由文字组成、字号即镜头、打字节奏即剪辑节奏、CRT 物理、一次换色、日志文件 | 开发者工具、科幻、科技品牌 | `opus:ascii-crt`（Canvas / SVG 源码）；近亲 `terminal-code` |

## G. 科技与氛围

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `cinematic-dark` 电影暗调 | 近黑渐变、粒子、辉光只给物体 | 推入穿越、镜头前的光 | 发布、AI、游戏 | `hf:cinematic-zoom` `hf:godrays` `gn:atmospheric-depth` |
| `grainy-gradient` 颗粒渐变 | 深底、饱和发光形状、细颗粒 | 层层打开、镜头穿过形状 | AI、科技品牌、音乐 | `hf:mesh-gradient` `hf:flowing-gradient` `gn:mesh-gradient-flow` |
| `cyber-hud` 赛博 HUD **有参考片** | 深色、青与品红、扫描线、数据面板 | 扫描、解码、故障 | 科技、安全、游戏 | `hf:telemetry-hud` `hf:camcorder-hud` `hf:matrix-decode` `gn:glitch-scan-band`；`mg15:22-hud` |
| `liquid` 液态流动 **有参考片** | 有机曲面、高光、颜料或液体质感 | 液滴融合拉丝再断开回弹，波浪前沿扫过换场，次级液滴迟 2–3 帧跟随 | 开场、转场包装、饮品与潮流、情绪高点 | `mg15:07-liquid` `gn:fluid-ink` `hf:vfx-liquid-background`；WebGL 着色器 |
| `neon` 霓虹 | 黑底霓虹灯管字、辉光 | 闪烁点亮 | 夜生活、娱乐、潮流 | `gn:neon-sign-flicker` `hf:caption-neon-glow` `hf:lt-neon-border` |
| `luxury-dark` 奢华暗金 | 黑配金铜、柔和阴影、高挑衬线 | 慢动作、扫光、纵深 | 高端产品、品牌 | `gn:light-sweep` `hf:gloss-sweep` `hf:light-sweep-pass` |
| `pastel-playful` 糖果童趣 | 叠加粉彩、大圆形、圆体粗字 | 弹性回弹、形状绽放 | 亲子、健康、生活方式 | `gn:squash-stretch` `gn:bounce-landing` `hf:spring-pop` |
| `opuscar-game-show` 综艺节奏扁平 **有参考片** | 节奏游戏综艺的扁平矢量：粗墨线玩具感吉祥物、糖果色条纹与放射光，每次击打都落在固定节拍上 | 回合卡、成绩单、一呼一应、预告下一关、判定词、数据做成游戏界面 | 科技时间线、年度回顾、综艺 | `opus:game-show`（Canvas / SVG 源码）；近亲 `pastel-playful` |
| `opuscar-microgame` 微游戏快闪 **有参考片** | 派对小游戏快闪：一个指令词、几秒、一个动作；每个小游戏完全不同的画风，越来越快 | 每关换画风、指令词、生命值界面、加速、失败变解法、Boss 混合规则、即时回放 | 游戏预告、新手引导、社交短片 | `opus:microgame`（Canvas / SVG 源码）；近亲 `era-mix` |

## H. 东方传统

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `ink-wash` 水墨 | 宣纸底、墨晕、留白、朱红印章、楷书或行书 | 墨迹晕开揭示、毛笔描写、印章落下 | 传统文化、历史、东方美学、哲思 | `hf:ink-bleed-reveal` `gn:ink-bleed` `gn:fluid-ink` `gn:stamp-impact`；马善政楷书、霞鹜文楷 |
| `paper-cut` 剪纸皮影 | 红纸镂空、剪影、多层叠放 | 剪影分层视差、皮影关节动作 | 民俗、节日、传统故事 | SVG 镂空；`gn:papercut-placement` `gn:layer-separation` `gn:deep-parallax` |
| `guochao` 国潮 | 高饱和撞色、传统纹样、描金、粗标题 | 纹样展开、描金扫光、印章 | 国货、消费、文化 | `gn:light-sweep` `gn:stamp-impact` `gn:tiled-pattern-drift`；纹样 **需素材** 或自绘 |
| `ukiyoe-print` 浮世绘版画 | 平涂、勾线、浪纹、和纸 | 平面分层视差、浪纹循环 | 日本文化、艺术史 | **需素材**（公版图或生成）；`gn:deep-parallax` `gn:wave-warp` |
| `opuscar-ink-wash` 中国水墨 **有参考片** | 宣纸写意水墨：留白是空间，一笔就是山、浪、手势或一次切换 | 一笔即一切、留白有分量、笔势即动作、飞白、墨晕转场、手卷横移 | 武侠、文化品牌、诗词 | `opus:ink-wash`（Canvas / SVG 源码）；近亲 `ink-wash` |
| `opuscar-papercut-red` 红色窗花剪纸 **有参考片** | 纸底上的红色关节剪纸，剪就是画，镂空是透光的地方 | 折、剪、展开，镂空即光，对称复制，边角料还有用，镜像成对 | 春节、节庆祝福、民间故事 | `opus:papercut-red`（Canvas / SVG 源码）；近亲 `paper-cut` |
| `opuscar-paper-lantern` 纸雕灯影 **有参考片** | 背光的多层纸雕灯盒：6–9 层卡纸叠在浅盒里，暖光透纸，窗与月从镂空处亮起，层层投影 | 灯亮起、两扇窗一盏灯、纵深即距离、纸自己写字、盒子当纪念品 | 节庆、礼品品牌、文化故事 | `opus:paper-lantern`（Three.js / WebGL 源码）；近亲 `paper-craft` |
| `opuscar-shadow-puppet` 皮影戏 **有参考片** | 半透明染色兽皮偶，镂刻如蕾丝，贴在棉布幕上，油灯从后面照 | 光就是世界、离幕变大变虚、绕到幕后、手持操纵感、换件、条带揭起 | 神话民俗、非遗、节庆 | `opus:shadow-puppet`（Canvas / SVG 源码）；近亲 `guochao` |
| `opuscar-ukiyoe` 浮世绘 **有参考片** | 江户木版画：平涂色块、刻线、天空晕染、能摸到的纸，镜头像展开手卷一样移动 | 名所系列、手卷、逐版套印、纸即是白、画框是实物、三联画 | 旅行、日本文化、诗歌 | `opus:ukiyoe`（Canvas / SVG 源码）；近亲 `ukiyoe-print` |

## I. 三维空间

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `3d-scene` 三维场景 | 代码几何、材质、灯光 | 镜头真实推拉环绕，主体占画面三分之一以上 | 产品展示、空间结构、宏大开场 | Three.js；`gn:camera-orbit` `gn:object-turntable`；写实产品需模型文件 |
| `soft-3d` 3D 渲染质感 **有参考片** | 软胶、玻璃、金属等真实材质，棚拍布光，浅景深，糖果色 | 克隆阵列群体波动、软体碰撞，长尾缓动（前 20% 走完 80% 路程），24fps 电影感 | 产品展示、品牌开场、片头 | `mg15:04-3d-render`；Blender 命令行渲染序列帧，**需安装 Blender**（新依赖先取得同意） |
| `low-poly-voxel` 低多边形 / 体素 | 小镇、方块世界、平涂明暗 | 搭建、绕转 | 游戏、世界观、过程 | Three.js；`gn:depth-assemble` |
| `exploded-diagram` 爆炸拆解 | 部件分离悬浮、引线标注 | 分离 → 标注 → 合拢 | 产品结构、硬件 | `gn:exploded-assembly` `gn:layer-separation` |
| `opuscar-brick-toy` 积木玩具 **有参考片** | 真实桌面上的积木定格动画，微距摄影质感，圆凸点塑料积木一格一格动 | 咔哒拼起、无害拆散、桌上玩具、手作定格、重拼成别的东西、尺度揭示 | 玩具与儿童、产品搭建、太空 | `opus:brick-toy`（Three.js / WebGL 源码）；近亲 `low-poly-voxel` |
| `opuscar-lowpoly-island` 低多边形等距 **有参考片** | 正交等距镜头下的多面体小世界，所有东西都是几何块，出现时带弹跳和一个音符 | 搭建即作曲、程序化生长、纯缩放换尺度、转台、光当时钟、暗处发光块 | 游戏预告、世界观、治愈内容 | `opus:lowpoly-island`（Three.js / WebGL 源码）；近亲 `low-poly-voxel` |
| `opuscar-tilt-shift` 移轴微缩 **有参考片** | 高处俯拍的真实地点，移轴镜头加延时，整个世界看起来像桌面模型 | 速度从 ×40 降到 ×1、清晰带当指针、上帝视角看系统、长曝光光轨、云影扫过 | 城市宣传、地产、交通 | `opus:tilt-shift`（Three.js / WebGL 源码）；近亲 `3d-scene` |
| `opuscar-hd-2d` HD-2D **有参考片** | 手绘像素精灵像纸片一样立在有光有雾的 3D 小场景里，高角度俯视加移轴，每盏灯都投下真实阴影 | 点灯时影子跳动、随身灯光当计量、灯一盏盏亮起、RPG 语法、天气掠过 | 游戏预告、奇幻、故事短片 | `opus:hd-2d`（Three.js / WebGL 源码）；近亲 `pixel` |
| `opuscar-data-physical` 数据实物化 **有参考片** | 真实统计做成真实物件：每个单位是一块可数的材料（板、块、硬币、条），按精确比例堆在底座上，产品棚拍光 | 单位特写、成对攀升、数据流入、图表拉远成装置、最后一个物件 | 年报、投资人材料、能源数据 | `opus:data-physical`（Three.js / WebGL 源码）；近亲 `data-viz`；数据来自来源文件 |
| `opuscar-white-model` 白模投影 **有参考片** | 暗室里底座上的纯白体块模型，投影仪把数据当光投上去，一次一层 | 关灯开投影、挖洞、按时间分层、水位上升、日照时钟、挑出一栋、开灯 | 城市规划、展览、城市数据 | `opus:white-model`（Three.js / WebGL 源码）；近亲 `3d-scene`；地块数据 **需素材** |
| `opuscar-lidar-survey` 点云测绘 **有参考片** | 真实机载激光点云悬浮在暗处，扫描线或剖切面穿过后点云凝成侧光实体表面，再用发丝仪器测量 | 照片变点云、剥开树冠、点云凝固、剖面、一镜飞穿点云、再生 | 文化遗产、环境、场地勘测 | `opus:lidar-survey`（Three.js / WebGL 源码）；近亲 `3d-scene`；点云数据 **需素材** |

## J. 口播呈现

真人口播本身怎么摆、字幕和包装怎么叠。每种都以出镜人物为主体，B-roll 与动效围着人走；和 A–I 的画面风格可以叠用（例如 `koubo-layout-card` 的窗口里放 `flat-diagram`）。剪口播的手法见手法卡（`library_tools.py search 口播`）。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `koubo-layout-card` 口播板式卡 | 竖屏；深灰网格动态底或暖橙光晕底；素材装进圆角"矩阵蒙版"窗口，人物抠像加白描边或投影压在窗口边上；主标题 + 副标题框、字幕条位置固定 | 七种板式按段落轮换：包围、上中下（圆形头像 / 大关键词）、三段、上下斜切、空间卡片、出框；窗口和关键词卡带轻微透视与发光边，层叠浮起 | 知识口播、财经、职场，有 B-roll 可放的竖屏口播 | 人物抠像（见 [人物抠像进场景](style-stack.md#5-人物抠像进场景)）+ HyperFrames 版式；`gn:perspective-tilt` `gn:card-stack-shuffle` `gn:lower-third-reveal`；B-roll **需素材**；七种板式的参数见手法卡 |
| `tech-explainer-koubo` 科技口播：插画与样机录屏 | 真人在书房口播；穿插纸艺感扁平插画（橙、墨绿、紫底，机器人角色），录屏装进显示器或手机样机、放在米色台面；深底方法卡，左上大标题，条目带红色序号 | 基本一句话一个画面，口播与插画、录屏交替；样机里的录屏缓推；方法卡条目逐条亮起；字幕单行白字居中 | AI 工具、科技产品、效率工作流、演示类口播 | `hf:device-frame-stage` `hf:vfx-iphone-device` `hf:browser-device-stage` `gn:progressive-disclosure`；插画 **需素材**（生图后统一色板） |
| `emotion-quote-koubo` 情感金句口播 | 近距自拍、暗暖室内光；字幕放在脸侧而不是底部，宋体或衬线中文配一行小号英文；关键词黄色；偶尔一个超大衬线词压在画面上方 | 一句拆两行：上行小字铺垫、下行大字落点；逐句出现不做弹跳；超大字只给核心词，一条片子两三次 | 情感、心理、人生感悟、金句类口播 | HyperFrames 字幕层；`hf:blur-in` `hf:per-word-rise`；思源宋体或霞鹜文楷；无需 B-roll |
| `typo-studio-koubo` 大字棚拍口播 | 横屏，灰色无缝背景布，人物半身居中；人后和四周是超大中文字，红、藏蓝、白三色，字号对比极大；章节用黑底红字加小号 "PART" 卡；偶尔叠取景器 REC 角标 | 关键词从四周飞入或砸下铺满背景；疑问词绕着人头散开；章节黑场闪切；字在人后 | 观点、方法论、个人 IP 干货 | 人物抠像 + HyperFrames 文字层；`hf:kinetic-type-swap` `gn:kinetic-beats` `gn:stamp-impact` `hf:camcorder-hud` `gn-recipe:chapter-transition` |
| `ip-interior-koubo` 实景高级感 IP 口播 | 实景办公室、沙发、落地窗，自然光；红色粗衬线标题带投影，关键词放大变橙红，小字白色衬线；景别在全身、中景之间切换 | 同一句话里一两个关键词放大变色，其余小字；景别切换换段落；包装按"字幕花字 → 音效 → 画中画素材"一层层加 | 个人 IP、创业、培训、高客单服务 | HyperFrames 字幕层；`hf:per-word-rise` `gn:lower-third-reveal`；画中画 **需素材** |

## K. 组合方式

| key | 说明 |
|---|---|
| `person-in-scene` 人物入景 | 口播人物抠像后放进任一场景风格，见 [人物抠像进场景](style-stack.md#5-人物抠像进场景) |
| `era-mix` 年代混合 | 每个时代一种画法（如像素 → 质感层 → 3D），换风格跟着时代走，配乐与字体贯穿全片 |
