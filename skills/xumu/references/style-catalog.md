# 风格目录：画面语言速查

镜头的 `style` 字段取本目录的 key。选法与分层规则见 [风格与技术栈](style-stack.md)；句子级的画面组织见 [解说语法](explainer-grammar.md)；素材与字体的许可见 [素材来源](asset-sources.md)。表中 `gn:` / `hf:` / `mg15:` / `opus:` 为 `motion_index.py` 可查的现成实现。

每部片通常一个主风格加至多一个辅助风格。用户没指定时，从不同大类里挑 2–3 个拉开差别的方向，各配一张代表帧。需要新风格时，先在 project.md 写下 key、观感、标志动作与实现，再使用。

标注说明：**已验证** = 在序幕实际成片中跑通；**有模板** = `assets/templates/` 下有可运行模板；**需素材** = 依赖生成图或授权图片，代码无法独立完成；**有参考片** = [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) 有这种风格的 10 秒参考成片、完整提示词、确定性源码和可检验的标志特征（`mg15:` 编号，用法见 [风格与技术栈](style-stack.md#10-风格参考片mg15)），或 [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) 有这种风格的完整规则、原生动作菜单、一支 30 秒到 2 分多钟的样片和确定性源码（`opus:` 编号，key 以 `opuscar-` 开头，用法见 [风格与技术栈](style-stack.md#11-开源风格包opuscar)）。`opuscar-` 的 59 种和目录里原有的风格有些相近（"近亲"一栏写在实现里），它们是独立的风格：观感和标志动作以样片为准。有 171 种带完整文字参考和示意图（`style_tools.py show` 看 `spec.brief`，见 [风格与技术栈](style-stack.md#12-带文字参考的风格)）。其余风格目前只有目录条目与组件指引，首次实际使用时按 [风格与技术栈](style-stack.md#9-风格模板的沉淀) 沉淀模板。

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
| `relation-arrows` 关系图箭头 | 深墨绿底、细描边圆形节点、带字的细箭头，全片只有一根珊瑚色关键箭头 | 节点依次弹出，箭头从起点生长到终点，话语沿箭头淡入，虚线箭头最后画，无关节点压暗 | 人物关系、因果链、利益博弈、组织结构 | SVG 画节点与箭头，Canvas 2D 也可；`gn:line-draw` `gn:scale-pop` `gn:motion-hierarchy`；近亲 `flat-diagram` |
| `split-compare` 分屏今昔 | 一条竖线分开两个时代：左半褪色冷灰带颗粒，右半干净暖色，同一构图两种质感 | 中线纵向划开画面，两侧同物对位变化，中线左右缓摆，胜出一侧吞满全屏，标签钉在两端 | 今昔对比、改版前后、两代人、行业变迁 | HTML 逐帧双层裁切，两侧共用构图，旧帧加颗粒；`hf:before-after-wipe` `hf:comparison-split` `gn:film-grain`；近亲 `era-mix` |
| `timeline-march` 时间轴推进 | 奶白底、贯穿全屏的钴蓝粗轴、明黄圆点节点，到点放大成整屏事件卡 | 时间轴持续向左推移，节点到中点弹开，镜头推进成事件卡，讲完缩回轴上，年份按位滚动 | 发展史、项目复盘、人物生平、行业大事记 | HTML 逐帧或 SVG，一条长轴做世界坐标；`hf:pan-stations` `gn:rolling-digits` `gn:scale-pop`；近亲 `map-journey` |
| `recipe-stack` 配方叠加 | 杏粉平底、居中线描透明容器、一层层彩色色块叠高，右侧用量标签逐条落下 | 空容器先画出，原料从顶部落入，液面升高成层，名称与用量同步拉线标出，成品放大亮相 | 工具教程、方法拆解、产品成分、成本构成 | SVG 或 Canvas 2D 画分层液面；`gn:line-draw` `gn:annotation-callout` `gn:rolling-digits`；近亲 `flat-diagram` |
| `manual-lineart` 说明书线稿 | 冷白纸、等粗黑线图、带圈编号与点划轴，当前零件只涂一块信号黄 | 步骤大数字先落下，线稿逐笔画完，零件沿点划线滑开，编号圈弹出，翻页换步骤 | 操作步骤、产品原理、安全须知、拆解讲解 | SVG 逐段描线，零件分组平移；`gn:exploded-assembly` `gn:line-draw` `gn:page-turn`；近亲 `exploded-diagram` |
| `transit-map` 线路图 | 深夜蓝底、彩色粗线 45° 转折、白环站点，列车小块沿线走，站牌式标题 | 彩线从起点描向终点，站点逐个点亮，列车沿线靠站，换乘环放大，终点牌亮出结论 | 流程路径、人生轨迹、产品路线图、多线并行 | SVG 路径描线加沿路径运动，站点按八方向栅格；`gn:line-draw` `hf:offset-path-traveler` `gn:scale-pop`；近亲 `map-journey` |
| `knolling` 平铺整理 | 芥末黄平底、顶光硬阴影，物件按大小成行成列，间距一致，全部与画框平行 | 物件从画外滑到位，旋转摆正对齐，间距收齐成阵列，逐件点名抬起，空位留虚线框 | 工具清单、装备开箱、要素盘点、成本拆分 | 生图 + 分层抠单件，或 Three.js 正交顶视，需素材；`gn:piece-assembly` `gn:layer-separation`；近亲 `white-catalog` |
| `section-axon` 建筑剖面轴测 | 浅天灰底、整栋建筑被纵向剖开，黑色切面，细线家具小人，层与层上下相通 | 切面沿轴线划开，墙体退去露出房间，镜头沿楼层升降，小人穿层走动，拉远见整张剖面 | 社会分层、产业链上下游、系统架构、组织层级 | SVG 画二等角，长画布做升降，复杂场景需素材；`gn:layer-separation` `gn:line-draw` `hf:scroll-camera-story`；近亲 `isometric` |
| `glass-equation` 窗上公式 | 暖暗室内框住方格窗，白色蜡笔手写在玻璃上，窗外柔焦，几处符号亮起金线相连 | 字迹一笔笔写上玻璃，关键符号逐个亮起，金线连成多边形，光点沿线游走，硬切贴近字迹 | 数学原理、灵感时刻、模型推导、规律发现 | HTML 逐帧叠两层：生图窗景加手写层，需素材；`gn:handwriting-write-on` `gn:line-draw` `gn:glass-refraction`；近亲 `chalkboard` |
| `watercolor-edu-card` 水彩科普卡 | 冷压水彩纸、湿边晕染的圆润小物，一张卡讲一件事，铅笔线与手写批注 | 颜料从中心湿染铺开，铅笔线随后勾形，批注逐字写上，小箭头轻轻画出，翻到下一张卡 | 健康科普、儿童知识、自然常识、生活原理 | 生图 + 分层，色块用遮罩扩散揭示，需素材；`hf:ink-bleed-reveal` `gn:line-boil` `hf:hw-arrow`；近亲 `watercolor-storybook` |
| `museum-exhibit` 博物馆展陈 | 近黑展厅、单束暖光切出展台，米色展签，铜锈青只给当前展品与导览点 | 光束从顶部缓缓打亮，展品在台上慢转，展签淡入定位，解说条逐字打出，灯灭移步下一展厅 | 物品史、文明史、产品回顾、作品集导览 | Three.js 低面数展品或生图抠图；`gn:object-turntable` `gn:ambient-particle-drift` `gn:typewriter`；近亲 `luxury-dark` |

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
| `detective-board` 线索板 | 台灯下的软木板，歪钉的卡片、便签与打印图，红线绷直把线索连成网 | 镜头横移扫过板面，新卡片钉上抖一下，红线从图钉拉紧到下一张，红笔圈出数字，闪白揭晓结果 | 商业调查、事实核查、悬疑解读、推理式科普 | HTML 大画布平移，红线 SVG 描线；`gn:line-draw` `gn:stamp-impact` `hf:hw-callout-circle`；近亲 `opuscar-visual-investigation` |
| `microfilm-reader` 缩微胶片 | 荧光绿单色的报纸网点图，暗色片基，扫描线与灰尘，只有主角保留一块橙色 | 胶片横滑过暗色帧隙，网点图缓慢推近，扫描光带从上扫下，标记框定位一行，主角留色 | 档案调查、历史钩沉、旧闻重读、数据溯源 | WebGL 网点，需素材；`hf:halftone-field` `gn:crt-scanlines` `gn:film-dust-scratches`；近亲 `opuscar-archive-lighttable` |
| `weather-forecast` 天气预报 | 海蓝陆绿的气象地图，白色等压线，冷暖锋符号，底部滚动预警条，一张卡一个指数 | 云团从卫星图旋入，等压线逐圈画开，风向虚线沿线流动，温度计升到位，斜切换到下一张 | 情绪趋势、市场冷暖、舆情走向、季度展望 | Canvas 2D 画等压线与云团，固定包装走 HTML；`hf:news-ticker` `gn:dashed-flow` `gn:rolling-digits`；近亲 `opuscar-news-package` |
| `sports-broadcast` 体育直播包装 | 炭黑底、角标记分牌、荧光黄绿与正红双方对阵色条，球衣斜纹，体育场光束 | 比分角标常驻角落，数字跳表翻到位，双方色条对冲填满，回放暂停画线标注，硬切进下一节 | 竞品对比、排名之争、产品 PK、年度回顾 | HTML 分层包装，数字用滚动组件；`gn:rolling-digits` `hf:news-ticker` `hf:bar-chart-race`；近亲 `opuscar-telestrator` |
| `photo-essay-spread` 画报新闻跨页 | 米白铜版纸、满版粗黑网点照片、竖向中缝折痕，主角单走一块青蓝专色 | 照片满版铺开，中缝压出折痕，网点由粗收细，专色版错位盖上，拉远成摊开的杂志 | 人物特稿、时代记录、城市观察、深度报道 | 生图灰调图 + 网点着色，Canvas 2D 合成，需素材；`gn:halftone-motion` `gn:ken-burns` `gn:page-turn`；近亲 `opuscar-halftone-dossier` |
| `letterpress-news` 活字线刻报纸 | 泛黄新闻纸、木活字通栏大标题、密排多栏铅字、线刻插图，只有一块暖红专色版 | 字块逐个砸下留印；整版受压一震；专色版晚半拍盖上；翻到下一版换场 | 历史事件、行业大事记、观点檄文、发布声明 | Canvas 2D 排版加油墨阈值，线刻需素材或程序排线；`gn:stamp-impact` `gn:hatch-fill` `gn:film-dust-scratches`；近亲 `vintage-engraving` |
| `family-album` 家庭相册快照 | 奶油色相册内页、褪色白边快照、发青的黑，圆珠笔手写说明，塑料膜微光 | 俯拍推进一张照片，照片铺满后颜色回暖，静帧活动起来，再拉出贴回相册页，手写说明逐字写上 | 个人故事、家族史、品牌创业史、情感回忆 | 生图或用户老照片，HTML 逐帧调色与推拉，需素材；`gn:ken-burns` `gn:handwriting-write-on` `gn:film-grain`；近亲 `documentary-archive` |

## C. 界面与产品

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `clean-ui` 干净界面 | 真实截图或真实网页为底 | 镜头推到真实按钮；尺寸与圆角变化用弹簧 | 工具教程、产品功能 | `hf:ui-focus-zoom` `gn-recipe:product-demo` `hf:browser-device-stage` |
| `keynote-ui` 发布会式界面动效 | 为这句话专门虚构的软件界面当主角：浅灰底、白色微倾斜圆角卡、一个蓝紫强调色、粗细对比强的黑体大字；讲钱切黑底香槟金，讲情绪切偏暗的全屏素材，三套皮肤硬切 | 带光晕的光标操作界面并牵动数据；新卡带模糊滑入盖住旧卡；模糊转清晰换字并留空档；大字不动底下快切素材；彩色褪成灰表达态度 | 产品介绍、AI 工具、数据复盘、商业拆解、收入盘点、知识口播的 B-roll | HTML 逐帧或 HyperFrames；`gn:rolling-digits` `hf:data-chart`；先比较 Shotcraft：`cursor-flyover` `blur-slide` `orbit-ring-title-open` `list-stack-press` `doc-park-left-pill-deal` `aurora-bloom-bg-flip`；近亲 `clean-ui`（要真实截图）、`opuscar-dark-keynote`（全片暗色）；界面为示意重绘，数字来自来源文件 |
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
| `split-flap` 翻牌显示板 | 炭灰板面、一格格翻片，中缝与铰链线，琥珀灯闪烁，像车站到发信息屏 | 字牌逐列哗啦翻动，字符落定一格，琥珀灯闪一下，时钟跳一格，整板换一条信息 | 标题金句、排行榜、时刻表、数据发布 | HTML 逐帧翻片，预设字符序列；`hf:split-flap-board` `gn:stepped-motion` `gn:rolling-digits`；近亲 `opuscar-news-package` |
| `thermal-receipt` 热敏小票 | 茄紫桌面、一卷灰白热敏纸从打印头长出，紫黑点阵字，锯齿撕边，蓝色印章 | 小票逐行打印向上长出，清单项逐条打勾，合计行加粗跳出，蓝章盖下，撕下纸条甩出画面 | 算账盘点、成本清单、权益对比、吐槽账单 | HTML 逐帧裁切纸条高度，字用阈值做点阵；`gn:perforated-tear` `gn:stamp-impact` `gn:stepped-motion`；近亲 `brutalist-mono` |
| `infomercial` 电视购物 | 满屏放射光底、粗描边大喊字、爆炸贴价格，底部红黄滚条，每拍换一种猛色 | 大字砸屏抖动，放射底换色，旧价划掉爆炸贴弹出，小人由灰变彩，滚条持续跑动 | 反讽吐槽、营销话术解构、消费陷阱、夸张促销 | HTML 分层，放射底用 CSS 圆锥渐变；`hf:headline-slam` `hf:strikethrough-replace` `hf:news-ticker`；近亲 `sticker-pop` |
| `quiz-show-studio` 答题演播室 | 蓝紫光束穿过薄雾、底光玻璃圆台、长六角答案框，锁定一格琥珀，外景用饱和橙青 | 光束扫过全场，答案框依次亮起，选中格锁成琥珀，四周压暗收束，判定闪绿后硬切外景 | 知识问答、悬念设问、决策选择、误区测试 | WebGL 画光束，答案框 SVG，外景生图需素材；`hf:godrays` `hf:vfx-anamorphic-flare` `gn:light-sweep`；近亲 `opuscar-game-show` |
| `logo-assemble` Logo 聚拢 | 珍珠灰平底、由标志本身切出的墨黑碎片，缓慢收拢，最后一笔品牌色点亮 | 碎片从四周缓慢漂入，按笔画顺序归位，缝隙一格格收紧，品牌色一笔扫亮，字标落定静止 | 频道片头、片尾署名、章节转场、品牌亮相 | SVG 切分标志路径，每片独立动画，需素材（用户标志矢量）；`gn:piece-assembly` `gn:particle-assemble` `hf:logo-sting`；近亲 `morph` |

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
| `text-rain` 字雨 | 暗酒红底、大小不一的话语从天而降，落地堆成字山，压住底部一粒暖光 | 句子从顶端陆续落下，大字快小字慢，落地压扁堆积，字山逐渐升高，光点被埋后变暗 | 重复说教、信息过载、舆论压力、焦虑情绪 | Canvas 2D 逐帧，预设字块堆叠位置保证可复现；`gn:bounce-landing` `gn:motion-hierarchy` `hf:stagger-cascade`；近亲 `kinetic-type` |
| `cursor-confession` 光标独白 | 近黑空屏，一行宋体字在中线偏左，一根青绿光标闪烁，字写了又退回 | 光标独自闪烁等待，字一个个打出，停顿后退格删掉，改打一句更短的话，最后只剩光标 | 内心独白、没说出口的话、道歉告白、创作者自述 | HTML 逐帧或 Canvas 2D，逐字时间表写死；`hf:typewriter` `hf:caret-swap`；近亲 `terminal-code` |
| `word-tunnel` 字的隧道 | 近黑深蓝底、同心环形排列的宋体字、远暗近亮的景深，灭点一团冷光 | 字环从灭点涌出；镜头匀速钻入；内外环反向自转；关键词减速定住；穿过灭点白闪换段 | 困局分析、连环追问、层层深挖一个问题 | Canvas 2D 画极坐标字环，或 Three.js 贴字；`hf:cinematic-zoom` `gn:atmospheric-depth`；近亲 `kinetic-type` |
| `text-scatter-reform` 字散再聚 | 素白宣纸底、墨点粒子组成的整句大字、一缕青绿色气流，疏朗安静 | 整句从笔画裂开；墨点被气流卷走；停半拍聚成薄雾；吸回拼成新句；改动的字转青绿 | 观念反转、误解澄清、换个角度看问题 | Canvas 2D 取字形蒙版采样成粒子，超过 3 万点改 WebGL；`gn:particle-assemble` `gn:particle-force-field`；近亲 `particle-explainer` |
| `word-architecture` 文字建筑 | 炭灰暗场、纸色粗字当梁柱地板的文字构筑物、一条地平线、一道琥珀色 | 地基词横落震地；词柱竖起撑高；词梁架上压实；末句走上平台站定；镜头拉出看全貌 | 结尾金句、论证推进、把理念一层层搭起来 | SVG 或 HTML 逐帧，用字形轮廓做碰撞与对齐；`gn:piece-assembly` `gn:shape-built-letters` `gn:bounce-landing`；近亲 `kinetic-type` |
| `lyric-sync` 歌词卡点 | 午夜蓝底、极淡网格、居中一张图解、底部一行逐词点亮的唱词 | 重拍逐词点亮；每行唱词换一张图解；光点沿连线跑过；副歌回到同图换强调色；顶部进度线走拍 | 配乐段、片尾歌、把知识点唱出来的解说 | HTML 逐帧，按节拍表驱动；`gn:kinetic-beats` `hf:per-word-rise` `gn:dashed-flow`；近亲 `kinetic-type` |
| `exhibition-yellow` 展览黄 | 暖羊皮纸、一轮巨大太阳黄光晕、靛蓝宋体大标题与发丝细线，像展览画册封面 | 黄色光晕缓缓胀开；发丝线从中心划向四边；标题逐行浮现；光晕滑到关键词身后；页码翻动 | 艺术人文、行业观察、纪录片章节卡 | Canvas 2D 径向渐变加纸纹缓存；`gn:line-draw` `hf:blur-in` `hf:grain-overlay`；近亲 `editorial-light` |
| `neo-brutal-block` 新粗野色块 | 米白底、粗黑框卡片、无模糊硬投影、桃粉薄荷亮黄的糖果撞色 | 卡片硬切砸入定位；按钮压下投影归零；新卡撞开旧卡；底色翻成糖果色；标签贴歪回正 | 互联网产品、工具测评、榜单、吐槽与清单 | HTML 逐帧或 SVG，CSS 盒阴影做硬投影；`gn:hard-appearance` `gn:spring-overshoot` `hf:badge-pop`；近亲 `brutalist-mono` |
| `cobalt-parchment` 钴蓝羊皮纸 | 羊皮纸与钴蓝大色面对切分屏，黑体标题配宋体正文，沉稳的汇报版式 | 钴蓝色面横推分屏；分界线滑到新比例；文字跨界自动反白；数据柱从分界长出；色面收成页脚 | 商业分析、财报解读、咨询式论证 | SVG 或 HTML 逐帧，用裁切蒙版做跨界反白；`gn:mask-reveal` `hf:data-chart` `gn:lower-third-reveal`；近亲 `editorial-light` |
| `script-poster` 花体海报 | 奶油纸底、满幅倾斜的朱红行书大字压住黑白主图，手写杂志封面 | 行书大字一笔写出；朱红横线收势；主图从字后探出；小字竖排贴边；整版微倾回正 | 人物专访、生活方式、品牌态度、情绪短片 | SVG 字形遮罩做书写，主图生图 + 分层，需素材；`gn:handwriting-write-on` `gn:layer-separation`；近亲 `poster-colorblock` |
| `industrial-broadside` 工业大字报 | 奶油新闻纸、撑满版面的墨黑巨字、粗横线分栏、一条火橙色块 | 巨字从版外横推入场；粗黑横线切开版面；火橙色条盖住一个词；整版上滚换版；编号跳格 | 产业新闻、制造业、宣言、重大消息 | HTML 逐帧或 SVG，文字可拉伸适配版宽；`hf:headline-slam` `gn:kinetic-type-sweep` `gn:film-grain`；近亲 `poster-colorblock` |
| `capsule-cream` 胶囊奶油 | 奶油纸底、一组圆头胶囊色块装下文字与数据，高反差宋体标题配糖果色 | 胶囊伸长装下文字；两颗胶囊并成一颗；胶囊排队长成柱图；胶囊翻面换色；滚动出画换场 | 消费生活、健康科普、产品卖点、轻量数据 | SVG 或 HTML 逐帧，圆头矩形做一切容器；`gn:shape-morph` `hf:spring-pop` `gn:shape-split-merge`；近亲 `pastel-playful` |
| `quiet-taupe` 留白灰褐 | 七成留白的暖米纸、一根发丝线、一行墨色细标题、一小块灰褐 | 一根细线缓慢划出；一行字在线上淡入；灰褐小方块挪一格；空场停一拍；线收回换场 | 哲思随笔、设计理念、个人叙述、高端品牌 | SVG 描线加 HTML 文字，几乎不用素材；`gn:line-draw` `gn:underline-draw` `gn:motion-hierarchy`；近亲 `line-art` |
| `cobalt-grid` 钴蓝网格 | 浅米坐标纸、钴蓝细网格铺满全屏、格内衬线字与蓝色实心单元，像测绘表 | 钴蓝网格逐线画满；内容吸附到格点；单元格逐格填蓝；标尺游标走到数值；网格平移一格换场 | 系统拆解、研究方法、比较表、技术报告 | SVG 网格加 HTML 逐帧；`gn:grid-draw` `hf:grid-card-assemble` `hf:dynamic-grid`；近亲 `swiss-grid` |
| `coral-condensed` 珊瑚窄体 | 奶油底、顶天立地的窄高字柱、珊瑚色满版反转，像体育海报的号码牌 | 窄高字柱逐列升起；字柱错落卷帘换句；珊瑚色满版反转；数字翻牌定格；字柱下沉退场 | 运动健身、榜单数字、品牌口号、快节奏盘点 | HTML 逐帧，逐字列蒙版；`gn:mask-reveal` `hf:kinetic-type-swap` `gn:rolling-digits`；近亲 `poster-colorblock` |
| `candy-block` 糖果粗字 | 奶油底、堆成一摞的超宽粗字，每字一种饱和糖果色，像桌上的玩具积木 | 粗字逐个弹落堆叠；落地挤压回弹；单字吹胀顶开邻字；重拍轮换颜色；整堆倾倒换场 | 轻科普、儿童向、活动预告、节奏欢快的盘点 | HTML 逐帧或 Canvas 2D，简单 2D 刚体；`gn:squash-stretch` `gn:bounce-landing` `gn:kinetic-beats`；近亲 `pastel-playful` |
| `daisy-garden` 雏菊花园 | 晴日奶油底、粉彩草地与花丛、炭灰手绘描边加小硬投影，圆胖字 | 雏菊从底边长出；花瓣逐片弹开；描边线条轻抖；花茎托起字卡；蝴蝶沿路径飞过 | 亲子教育、心理疗愈、生活小知识、春季活动 | SVG 手绘路径，12fps 线抖；`gn:line-boil` `gn:scale-pop` `hf:hw-boil`；近亲 `pastel-playful` |
| `forest-editorial` 森林杂志 | 深森林绿底、奶油楷书大标题、粉色块托引语、发丝线分栏的杂志跨页 | 整版翻页换跨页；发丝线划出分栏；粉色块滑入托住引语；楷书标题压边落定；图片裁框慢推 | 长篇报道、人文自然、品牌故事、深度访谈 | HTML 逐帧排版，配图需素材；`gn:page-turn` `gn:underline-draw` `hf:caption-editorial-emphasis`；近亲 `editorial-light` |
| `pop-art` 波普 | 红黄蓝原色平涂、纯黑粗轮廓、满版圆点底纹、爆炸框与对话框 | 爆炸框弹出拟声字；圆点底纹涌动扩张；对话框尾巴戳向主角；四宫格轮流换色；粗线先勾后填 | 抓眼球的转折、观点碰撞、消费话题 | SVG 加 Canvas 网点，主体可生图后分层；`hf:halftone-field` `gn:radial-speed-lines` `gn:stamp-impact`；近亲 `halftone-comic` |
| `photo-silkscreen-repeat` 照片丝网复制 | 银灰刷漆底、并排重印的黑色网点照片、错位的手刷平涂色块，一张印得不匀 | 同一图并排连印两三次；色块先刷网点后压；刮板横扫过版；错版抖一下；末版褪成银色 | 名人与符号、消费文化、流量现象、量产与复制 | 生图或授权图分层，需素材，Canvas 2D 阈值成网；`gn:halftone-motion` `gn:stepped-motion`；近亲 `opuscar-silkscreen-poster` |
| `wood-type-poster` 木活字海报 | 米黄纸、三色凸版、满是木纹的粗字实地与刻刀线人物，套印错位 | 木字块逐行压印；红蓝黑三版依次套上；错位抖动后定住；实地木纹显出；横幅滑入托字 | 公开宣言、社区活动、地方故事、节庆开场 | Canvas 2D 分版加木纹贴图，人物可生图 + 分层；`gn:stamp-impact` `gn:stepped-motion` `gn:film-grain`；近亲 `opuscar-woodcut` |
| `circus-chromolitho` 马戏彩色石印 | 奶油纸上铬黄朱红钴蓝三色大平涂、粗黑线、放射线背景，热闹的石印大帐篷 | 放射线从主角炸开；幕布向两侧拉开；三圈场景轮流点亮；主角叠印成橙；飘带展开标题 | 盛大发布、节日庆典、多线并行的大事记 | 生图 + 分层，需素材，Canvas 2D 做放射线；`gn:radial-speed-lines` `gn:layer-separation`；近亲 `opuscar-art-deco` |
| `wartime-litho` 战时石印海报 | 奶油纸、灰蓝蜡笔颗粒阴影、墨绿轮廓线，小主体立在巨大徽章形前 | 巨型徽章从地平线升起；斜向光带扫过削去阴影；小主体在前方站定；色版错位后归位；纸纹逐帧跳动 | 公共倡议、集体行动、年代回顾、动员式开场 | 生图 + 分层，需素材，蜡笔版用噪声阈值；`gn:deep-parallax` `gn:film-grain` `gn:ken-burns`；近亲 `opuscar-silkscreen-poster` |
| `belle-epoque-litho` 美好年代石印 | 奶油石版纸、黄橙橄榄大平涂、饱墨笔刷飞白轮廓、牙刷喷溅墨点，夜场海报 | 笔刷一气勾出轮廓；平涂色版随后落下；细墨点撒向暗面；前景大剪影滑过；平移后停在中景 | 都市文化、社交话题、讽刺评论、文娱行业 | 生图 + 分层，需素材，Canvas 2D 做喷溅；`gn:layer-separation` `gn:outline-then-fill`；近亲 `poster-colorblock` |
| `art-nouveau` 新艺术 | 奶油纸、粉彩平涂、膨胀褐色曲线、中央大圆环与拱格马赛克，装饰性满幅 | 鞭线藤蔓沿边生长；光环逐圈转开；轮廓先描后填色；拱格向两侧开启；铭文条由下升起 | 传统工艺、美学史、女性主题、节气与自然 | SVG 描线加平涂，主体可生图 + 分层，需素材；`gn:line-draw` `gn:outline-then-fill` `gn:tiled-pattern-drift`；近亲 `opuscar-art-deco` |
| `sports-litho` 复古赛事海报 | 旧奶油纸、全由油墨颗粒聚成的海蓝赭黄深棕，长焦低机位的古典人体横列 | 颗粒由疏到密聚成形体；人物横列慢跑过画；尘土水花带颗粒飘起；低机位横移；标题横带压底 | 运动史、长期主义、团队协作、耐力叙事 | 生图 + 分层，需素材，Canvas 2D 噪声阈值成粒；`gn:animated-dither` `gn:deep-parallax`；近亲 `opuscar-risograph` |
| `stencil-street` 模板喷漆 | 老红砖墙、奶油补丁上的多层喷漆模板画，毛边流挂、手喷短标语 | 模板贴墙一层层喷出；喷雾毛边扩散；流挂缓慢下淌；揭开模板露出连接筋；横移到下一件 | 社会观察、反讽评论、城市话题、亚文化 | 生图 + 分层，需素材，Canvas 2D 蒙版叠喷雾噪声；`gn:mask-reveal` `gn:layer-separation` `gn:film-grain`；近亲 `collage` |
| `line-title-noir` 白线片头 | 纯黑底、细白线滑入搭成透视阵列、灰阶四级平涂，全片只留一点琥珀色 | 白线滑入长成网格；灰面逐格填满；灯格成排点亮；琥珀色落到主角；硬切俯视成图案 | 组织架构、行业规模、职场话题、系统性问题 | SVG 画线加 Canvas 填灰；`gn:line-draw` `gn:grid-draw` `gn:hard-cut`；近亲 `opuscar-spy-titles` |
| `linen-postcard` 亚麻明信片 | 奶油白边卡片、细密亚麻布纹、喷枪饱和色风景、立体粗字嵌小景，亮面闪四角星 | 卡片从一摞中抽出铺满屏；画面局部循环活动；四角星逐点闪亮；翻到背面手写摘要；邮戳盖下换场 | 城市与地区、旅行路线、产业带、怀旧消费 | 生图底加分层，Canvas 叠布纹蒙版；`gn:layer-separation` `gn:card-flip` `gn:stamp-impact`；需素材；近亲 `retro-analog` |
| `block-print-textile` 木刻印花布 | 本色棉布、雕版纹样分带重复、靛蓝茜红姜黄分版套印、版缝跳色、染料顺纱线渗开 | 雕版压下抬起留印；同一块版连盖成带；第二色版错位叠上；长布向侧拉动；纹样单元转动换场 | 手工与产业、贸易史、数量对比、物产类内容 | Canvas 2D 纹样平铺加渗色蒙版；`gn:stamp-impact` `gn:tiled-pattern-drift` `gn:ink-bleed`；近亲 `opuscar-woodcut` |

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
| `chibi` Q 版 | 奶油浅底、两到三头身原创小人、圆头大眼短四肢、软彩平涂、道具比人还大 | 小人蹦入落地压扁回弹；头顶冒汗滴问号；抱起超大道具踉跄；转头盯住屏幕上的字 | 个人经验分享、知识科普、职场吐槽、轻教程 | SVG 部件骨骼加表情替换；`gn:character-articulation` `gn:squash-stretch` `gn:blink`；近亲 `sticker-explainer` |
| `kawaii` 卡哇伊 | 粉彩波点底、万物圆鼓鼓长出豆豆眼小嘴、腮红点缀、不画人，只有会呼吸的物件 | 物件睁开豆豆眼；腮红鼓一下；一排小物跟着轻晃；元素气泡般冒出；小星星飘散收尾 | 生活好物、温和科普、儿童内容、亲切的品牌介绍 | SVG 圆角形加脸部模板；`gn:breathing-loop` `gn:jello` `gn:tiled-pattern-drift`；近亲 `pastel-playful` |
| `stick-minimal` 极简线条小人 | 近白空纸、单根黑线小人、几笔物件、八成半留白，文字是小人能搬动的实物 | 一笔画出小人；小人推着文字走；直线弯成坡道；跌倒爬起接着走；纸面只留一根线换场 | 心智模型、方法论、成长话题、概念寓言 | SVG 描线加简易骨架；`gn:line-draw` `gn:walk-cycle` `gn:line-boil`；近亲 `line-art` |
| `corporate-flat` 长手脚扁平人 | 淡紫白底、小头巨肢扁平人、非写实肤色、有机色斑、弯曲手臂串起信息 | 长臂伸过画面递出卡片；人物滑坐到图表上；色斑变形成下一景；一路横移接力；叶片抖动落定 | 企业介绍、软件服务、工作流、培训课件 | SVG 路径插值做连续长卷；`gn:shape-morph` `gn:infinite-pan` `gn:focus-handoff`；近亲 `flat-vector` |
| `ligne-claire` 清线漫画 | 暖白书页、全图等宽细黑线、无阴影纯平涂、简笔人物配细密布景、方框旁白 | 格框逐个划出；线稿描完后色块平填；镜头沿阅读路线穿格；方框旁白滑入；拟声字破格弹出 | 冒险式历史、案件复盘、创业故事、旅行见闻 | SVG 等宽线分层平涂，布景可生图描线；`gn:outline-then-fill` `gn:step-panel-walkthrough`；近亲 `opuscar-midcentury-toon` |
| `modern-anime` 日式动画 | 绘景式天空与街景、干净线稿人物、两阶赛璐璐阴影、逆光光斑、暮色蓝橙对比 | 一拍三演动作；静帧慢推加发梢微动；速度线冲入切特写；逆光光斑扫过；纸片飘过换场 | 情绪叙事、成长故事、品牌短片、校园职场题材 | 生图分层加视差；`gn:stepped-motion` `gn:radial-speed-lines` `gn:deep-parallax`；需素材；近亲 `opuscar-cel-anime-80s` |
| `gouache-picturebook` 水粉绘本 | 厚涂水粉跨页、哑光不透明、干刷边缘、柔圆造型、暖土色，底部一句短文 | 书页翻开跨页展平；色块一刷一刷铺满；小角色慢慢走过；底部短句逐字写出；翻页换场 | 寓言式科普、亲子内容、品牌故事、温情回忆 | 生图分层加笔刷遮罩；`gn:page-turn` `gn:mask-reveal` `gn:breathing-loop`；需素材；近亲 `watercolor-storybook` |
| `newspaper-strip` 报纸四格 | 发黄新闻纸、黑墨笔锋线、四格等分、灰网点铺底、手写气泡，不用彩色 | 四格依次落下；气泡逐句弹出；第四格静一拍再抖包袱；网点铺满压暗；整条剪下滑走换场 | 职场段子、行业吐槽、概念类比、热点点评 | SVG 分格加网点蒙版；`gn:speech-bubble-reveal` `gn:hard-appearance` `gn:halftone-motion`；近亲 `halftone-comic` |
| `single-panel-gag` 单格漫画 | 白纸满版一幅、蘸水笔粗细线、几抹淡彩、生活场景，底下一行手写冷幽默 | 墨线几笔画完全图；淡彩晕开略出线；全图静住只微颤；图说逐字写出；轻推后停住 | 段落结尾的观点、吐槽、社会观察、生活哲理 | SVG 变宽笔触加水彩蒙版；`gn:tapered-stroke` `gn:line-boil` `gn:handwriting-write-on`；近亲 `opuscar-urban-sketch` |
| `caricature-line` 粗细线漫像 | 白纸黑墨、一笔长线勾人物、黑发黑衣成块、只夸张一个特征、主角胭脂红平涂 | 长线连续勾出人物；黑块整片落下；特征拉长放大；群像逐人点色；横摇扫过全场 | 人物类型盘点、行业群像、团队介绍、角色分析 | SVG 变宽描边；`gn:tapered-stroke` `gn:shape-morph` `gn:hatch-fill`；近亲 `opuscar-one-line` |
| `family-sitcom` 家庭情景喜剧 | 暖色客厅布景、粗圆轮廓平涂的一家人、正面固定机位，只动嘴和眼睛 | 外景房子一秒定场；沙发上只动嘴；一句话全家齐转头；硬切反应脸；电视屏里放证据 | 家庭消费、日常经济学、生活观察、轻讽刺 | SVG 平涂布景加口型替换；`gn:reaction-cut` `gn:character-gaze-reaction` `gn:blink`；近亲 `cartoon-stage` |
| `gothic-illustration` 哥特插画 | 深紫黑底、细长尖锐的剪影、暗红点缀、骨白刮痕细线，枝杈和瘦塔向上刺 | 尖枝从四角爬向中心；影子拉长越过人物；冷烛一明一灭；裂纹沿画面蔓开；雾层缓慢横移 | 心理恐惧、悬疑故事、黑暗童话、行业阴暗面 | Canvas 2D 枝条生长加 SVG 剪影；`gn:branch-growth` `gn:atmospheric-depth` `gn:smoke-plume`；近亲 `cinematic-dark` |
| `dark-academia` 旧学院风 | 胡桃木书桌、油灯光池、泛黄书页与皮面书脊、铜器，一片深棕里只亮一小块 | 书脊从架上抽出；书页翻到批注处；放大镜滑过要点；脚注编号落到页底；灯光移向下一本 | 历史、思想史、文学、读书类、学术脉络 | 生图分层或 Three.js 静物；`gn:page-turn` `gn:zoom-callout` `gn:handwriting-write-on`；需素材；近亲 `documentary-archive` |
| `origami` 折纸 | 素净浅灰台面、一张彩纸折出多面体、清晰折痕、明暗分面、纸边露白芯 | 整张纸沿折痕翻起；三角面逐片折成形；展开留下折痕再折新形；受光面随折角转变；纸背换色进入下一段 | 变化与转型、结构原理、产品迭代、数学科普 | Three.js 面片铰链；`gn:origami-fold` `gn:plane-transformation` `hf:facet-morph`；近亲 `paper-craft` |
| `clay-stopmotion` 黏土定格 | 手捏黏土小物、指纹压痕、哑光油感、微缩桌面布景，帧与帧之间表面在变 | 小人一格一格挪动；黏土压扁后重捏成新形；表面压痕逐帧变化；嘴型替换片换着贴；一只手伸入摆正物件 | 轻松科普、生活方法、儿童向内容、产品趣讲 | Three.js 置换贴图或生图分层；`hf:stop-motion-cadence` `gn:squash-stretch` `gn:shape-morph`；近亲 `soft-3d` |
| `handdrawn-pov` 手绘定格第一人称 | 粗纸速写本、彩铅涂色、线条逐帧重描抖动，镜头前的物件睁眼看你说话 | 物件睁眼开口说我；线条每帧重描抖动；彩铅涂痕闪动；手把下一张纸推入；物件指向自己的零件 | 工具介绍、产品自述、职业视角、拟人化科普 | SVG 描线加位移滤镜 8fps；`gn:line-boil` `hf:hw-boil` `gn:blink`；近亲 `hand-drawn` |
| `torn-paper` 撕纸拼贴 | 冷压纸底、手撕色纸片层层贴、白纤维毛边、柔和水洗色、小投影 | 纸片由远及近逐片贴上；手撕一道口露出下层；字条一条条压上；旧层剥落；新纸滑过盖住 | 回忆、城市变迁、人物小传、真相揭示类 | Canvas 噪声撕边分层投影；`hf:torn-paper-rip` `hf:paper-collage-reveal` `gn:layer-separation`；近亲 `collage` |
| `sand-art` 沙画 | 琥珀色灯箱、深褐沙粒堆出形体、指尖划开亮线，沙层厚薄决定明暗 | 沙流从上倾泻堆形；指尖划开沙面勾出亮线；手掌一抹擦成下一幅；沙粒吹散成数字 | 人生故事、城市变迁、时间长河、情绪回忆 | WebGL 沙层高度场加粒子；`gn:particle-image-reveal` `gn:wind-wipe` `gn:mask-reveal`；近亲 `opuscar-shadow-puppet` |
| `kid-crayon` 儿童蜡笔 | 白纸蜡笔用力涂抹、抖动深棕线、压扁透视、笑脸太阳，越重要画得越大 | 蜡笔来回涂出边界；抖线箭头指向名字；重要东西越画越大；旧纸抽走露出新画；笑脸太阳转眼偷看 | 孩子视角的解释、家庭话题、情感内容、科普开场 | Canvas 蜡笔笔触加纸纹阈值；`gn:scribble-wipe` `gn:line-boil` `hf:hw-arrow`；近亲 `opuscar-crayon-book` |
| `field-journal` 野外手记 | 发黄布浆本、铅笔打底透明水彩、铁墨小字、胶带标本签、手绘地图页 | 铅笔底稿先出再铺水彩；测量线拉出并标数字；胶带贴上标本签；路线沿手绘地图前进；翻到下一日 | 实地调查、探访纪实、旅行记录、观察类科普 | 生图分层，铅笔用 SVG 描线；`gn:outline-then-fill` `gn:map-route-animation`；需素材；近亲 `map-journey` |
| `fashion-ink` 时装墨线 | 白纸、疾速带飞白的墨线、粉与品红水彩色池、修长人形成列，溅点沿笔势飞出 | 一笔疾扫带飞白；水彩色池晕开；甩点沿笔势飞出；修长人影横向列队滑过；黑块压上图案 | 时尚美妆、生活方式、品牌气质、审美话题 | Canvas 笔刷贴图加水彩蒙版；`gn:tapered-stroke` `hf:ink-bleed-reveal` `gn:paint-splatter-wipe`；近亲 `watercolor-storybook` |
| `loose-ink-wash` 线色错位水彩 | 留白纸面、钴蓝柠黄玫红透明色块滑开，蓝黑快线画满全景，线和色永不对齐 | 色块先铺滑开；蓝黑快线飞速画满；树冠云朵画成一串小圈；错位量随内容改变；踩拍硬切 | 节庆、城市风情、音乐、计划与现实的对照 | Canvas 水彩块加 SVG 快线；`gn:line-draw` `gn:ink-bleed` `gn:kinetic-beats`；近亲 `opuscar-watercolor` |
| `graphite-editorial` 铅笔杂志插画 | 暖灰细齿纸、铺满画面的铅笔插画、顺形排线与擦抹过渡，全片只有一处单色彩铅 | 构图线淡淡先行；轮廓压线落定；排线逐遍加深；橡皮擦出高光；主角染上单色彩铅 | 人物故事、职场观察、社会议题、品牌往事 | Canvas 2D 分遍叠排线加纸齿阈值；`gn:hatch-fill` `gn:outline-then-fill`；人物需素材；近亲 `opuscar-urban-sketch` |
| `colored-pencil` 彩铅手绘 | 暖白粗纹纸、六七支彩铅交叠成色、统一斜向排线，大量留白与手写小注 | 笔尖沿轮廓勾出；斜向排线铺色；第二色叠上混色；小图标沿弧线跳入；手写注释补上 | 生活方式、科普启蒙、读书笔记、饮食健康 | Canvas 2D 斜向排线配纸齿遮罩；`gn:hatch-fill` `gn:line-boil` `gn:handwriting-write-on`；插画复杂时需素材；近亲 `opuscar-crayon-book` |
| `cosmic-comic` 宇宙能量漫画 | 泛黄新闻纸的整页分格漫画、粗细毛笔墨线与大块涂黑、四色网点、黑色能量泡 | 格子逐格盖上；镜头钻进下一格；能量泡沿轨道炸开；网点放大成圆斑；方块拟声字砸落 | 未来科技、宏大设想、产品愿景、太空与能源 | Canvas 2D 分版平涂后过 45° 网点；`gn:halftone-motion` `gn:energy-orb` `gn:page-turn`；机械与人物需素材或程序线稿；近亲 `halftone-comic` |
| `street-comic` 潮流美漫 | 满屏亮黄底、品红与青的闪电劈开画面、粗黑描边、深紫块面阴影与喷漆飞沫 | 闪电劈开底色；速度线向外炸开；人物整个前倾冲出；大字旋转砸落；喷漆一扫换场 | 潮流消费、运动、新品冲击、观点喊话 | SVG 分层，Canvas 2D 补飞沫；`gn:radial-speed-lines` `gn:hard-shadow-pop` `hf:headline-slam`；人物需素材；近亲 `halftone-comic` |
| `flat-dusk` 扁平黄昏 | 一整片黄昏渐变天、三层平涂城市剪影、无描边，只有招牌和小灯会发光 | 天色推进一档；窗灯一格格点亮；霓虹招牌换字；远处轻轨划过；前景剪影缓慢滑移 | 情绪独白、城市观察、年终回顾、个人成长 | SVG 平涂分层或 Canvas 2D 视差；`gn:parallax` `gn:neon-sign-flicker` `gn:gradient-drift`；纯代码可完成；近亲 `flat-vector` |
| `fantasy-map` 奇幻水彩地图 | 暖羊皮纸上的手绘墨线地图、透明水彩晕开山海，地图窗口里露出空气透视的远景 | 墨线勾出海岸；水彩沿等高线晕开；虚线路线走过地名；镜头下潜进水彩远景；手写地名落下 | 行业版图、创业历程、知识脉络、旅行故事 | Canvas 2D 墨线加水彩晕染遮罩，远景需素材分层；`gn:map-route-animation` `gn:ink-bleed` `gn:atmospheric-depth`；近亲 `map-journey` |

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
| `typewriter-art` 打字机字符画 | 米白打字纸、固定网格上逐格敲出的字符画、色带深浅不匀，只有一条红色带 | 字符逐格敲出成形；同格叠打加深；换红色带打主角；滑架回车换行；整页抽纸换场 | 档案回忆、内心独白、调查手记、技术史 | Canvas 2D 把灰度图映射成字符网格；`gn:typewriter` `gn:ascii-motion` `gn:hard-cut`；复杂形象需素材转灰度；近亲 `opuscar-ascii-crt` |
| `airbrush-80s` 80 年代喷枪 | 奶白与薄荷底、硬边遮罩内的喷枪渐变、镀铬高光、黑白地砖，叠细青色标注 | 遮罩抬起喷出渐变；镀铬物滑入反光；十字星闪现一次；青色引线圈住一组；数字滚到结果 | 消费品趋势、怀旧商业、数据清点、设计史 | Canvas 2D 遮罩内径向渐变加飞沫噪点，镀铬用天空色带；`gn:mask-reveal` `gn:light-sweep` `gn:rolling-digits`；近亲 `vaporwave-y2k` |
| `toy-theatre` 玩具纸剧场 | 镀金台口与红帷幔框住的卡纸小舞台、石印黑线加手工上色、纸人留剪刀白边 | 帷幔向两侧拉开；景片沿滑槽推入；纸人滑到台前微晃；脚灯把影子投到后景；暗场拉远见桌面 | 寓言式解说、历史故事、儿童教育、品牌故事 | Three.js 平行片层，人物景片需素材；`gn:papercut-placement` `gn:layer-separation` `hf:curtain-reveal`；近亲 `paper-craft` |
| `scrimshaw` 骨雕细线 | 深色木桌上一枚抛光的弯月形骨件，象牙底上密布黑色针刻线，只点红蓝黄三小块 | 针尖沿线刻入；擦上黑墨；抹布擦过线条显影；窗光沿弧面滑过；刻中波浪跟着起伏 | 海洋与航运、手艺匠人、家族往事、民间传说 | Three.js 曲面贴图加高光，刻线用 SVG；`gn:line-draw` `gn:hatch-fill` `gn:light-sweep`；物件底图需素材；近亲 `opuscar-engraving` |
| `admiralty-chart` 海图铜版 | 直纹旧纸上的铜版测绘海图：恒向线网、罗盘玫瑰、水深数字，沿岸一抹薄淡彩 | 罗盘玫瑰放射恒向线；刻度边框逐段走完；水深数字逐片浮现；虚线航迹自行延伸；滑入排线插图 | 航线与贸易、战略路径、风险排查、探索史 | SVG 线稿加 Canvas 2D 排线；`gn:map-route-animation` `gn:hatch-fill` `gn:zoom-to-detail`；插图需素材或程序排线；近亲 `map-journey` |
| `naturalist-plate` 博物图版 | 泛黄图版、居中的大标本图配四周编号小图、细铜版排线与点刻，线内薄涂水彩 | 版框压印成形；主标本由线到彩显出；编号小图逐个归位；引线指向局部；只有一处悄悄活动 | 知识分类、产品结构、生物科普、概念拆解 | Canvas 2D 排线点刻后平涂水彩，标本需素材；`gn:annotation-callout` `gn:hatch-fill` `gn:zoom-to-detail`；近亲 `vintage-engraving` |
| `satirical-etching` 讽刺铜版 | 帘纹旧纸上的讽刺版画：起伏刻线、漫画式群像，鲜亮水彩刷得溢出线外 | 全幅群像定格两秒；急推到一处笑点；横滑到旁观小动物；手写气泡弹出；水彩溢出线外 | 行业吐槽、荒诞现象、消费观察、评论短片 | Canvas 2D 分版：线版加偏移水彩版；`gn:speech-bubble-reveal` `gn:hatch-fill` `gn:push-in`；群像需素材；近亲 `vintage-engraving` |
| `arcade-fighter` 街机格斗 | 紫夜擂台、方块胖像素、顶部双指标条与回合计时，加轻扫描线的原创 16 位对决画面 | 投币字样闪动；回合横幅砸入；招式光弹飞过；命中停帧白闪；难题化成金币散开 | 竞品对比、攻克难题、挑战记录、知识闯关 | Canvas 2D 低分辨率绘制后最近邻放大；`gn:stepped-motion` `gn:crt-scanlines` `hf:headline-slam`；原创精灵程序绘制或需素材；近亲 `pixel` |
| `suburban-dv` 郊区 DV | 饱和对称的郊区住宅插画，与发软、偏绿、带录制角标的低清家庭录像交替出现 | 正面对称画面缓推；红叶积聚成风暴；风暴盖过剪切；切入 DV 录像；曝光一呼一吸 | 家庭叙事、体面背后、中产观察、回忆复盘 | 主画面需素材或生图分层，录像层用 Canvas 2D 降质；`hf:camcorder-hud` `gn:vhs-tracking` `gn:wind-wipe`；近亲 `retro-analog` |
| `cyber-pixel-street` 像素赛博街 | 俯视的深蓝紫像素街区、满街招牌与天桥、抖动光晕和斜落像素雨，人车流畅穿行 | 像素雨斜落不停；招牌轮流跳亮；行人打伞顺滑穿行；飞车掠过天桥；街尽头大屏换字 | 未来城市、科技趋势、游戏文化、夜经济 | Canvas 2D 小画布量化加拜耳抖动后放大；`gn:animated-dither` `gn:rain-streaks` `gn:neon-sign-flicker`；近亲 `opuscar-pixel-rpg` |

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
| `glitch-signal` 信号故障 | 近黑底、白字居中、红青通道错开，突发的横向撕裂带与块状压缩残影 | 画面稳定片刻；横带突然撕开；红青通道错位；块状残影拖过；一帧白闪后恢复 | 系统崩溃、舆论混乱、话题打断、安全事故 | Canvas 2D 分通道加横带位移；`gn:glitch-rgb-split` `gn:glitch-scan-band` `gn:datamosh-transition`；可压在实拍上；近亲 `crt-film` |
| `neon-rain-alley` 霓虹雨夜 | 一点透视的雨夜窄巷、竖招牌成排、青雾吞没远处，湿地倒影占下半屏 | 招牌逐块亮起；倒影被雨点打碎；青雾吞掉远处；镜头沿巷推向暖光；卷帘门掠过换场 | 都市悬疑、深夜情绪、赛博议题、行业暗面 | WebGL 雾与倒影，或生图分层后 Canvas 2D 合成，需素材；`gn:neon-sign-flicker` `gn:dynamic-reflection` `gn:rain-streaks`；近亲 `neon` |
| `green-industrial` 末日工业 | 几乎全绿的巨型机械层层退入雾中，远处一轮大圆环，顶部漏光，一个红衣小人 | 雾层逐层视差滑移；光柱从缝隙扫下；巨环极慢转动；红衣小人走一步；黑铁链掠过前景 | 基础设施、算力与能源、系统压迫感、未来预警 | Three.js 或多层 Canvas 2D 视差，结构可程序生成；`gn:deep-parallax` `gn:atmospheric-depth` `gn:god-rays`；近亲 `cinematic-dark` |
| `night-lighttrails` 夜景光轨 | 长曝光夜街：高架上横贯的白红光带、钠灯橙对青色招牌、焦外光斑，雪只在光锥里 | 车灯拉成连续光带；光带弯成数据曲线；焦点从前景转到远处；雪在光锥内显现；一镜连续俯仰 | 城市经济、物流出行、增长曲线、人群故事 | WebGL 或 Canvas 2D 叠加累积光带，底图需素材；`gn:motion-trails` `gn:path-beam` `gn:rack-focus`；近亲 `opuscar-city-symphony` |

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
| `gongbi` 工笔重彩 | 暖赭绢本、均匀细长的铁线描、层层分染的矿物重彩，提金提白，无投影 | 淡墨线先勾定；底色平涂；沿边分染加深；铁线复勾压稳；提金提白点醒 | 传统文化、精工制造、财富叙事、节气风物 | Canvas 2D 分层染色，沿边距离场做分染，线稿需素材或 SVG；`gn:outline-then-fill` `gn:line-draw` `gn:ken-burns`；近亲 `guochao` |
| `shanshui` 青绿山水 | 绢本长卷上的石青石绿山峦、赭石打底、云带留白，金线勾勒，亭台细小 | 长卷向左缓缓展开；云带横过分段；山色由赭转青；小舟沿水而行；题跋落印收束 | 历史长河、产业变迁、人生阶段、文旅宣传 | Canvas 2D 五层长卷视差，山体需素材；`gn:infinite-pan` `gn:image-unroll` `gn:atmospheric-depth`；近亲 `opuscar-ink-wash` |
| `nianhua` 年画 | 大红大绿的木版套色、粗黑墨线、满幅对称构图、吉祥纹样，版色轻微错位 | 黑线版压下成稿；色版逐一盖上；双扇门向两边打开；纹样撒满空地；朱印落款收尾 | 春节节庆、品牌贺岁、民俗文化、喜讯发布 | SVG 分版错位加木纹遮罩；`gn:stamp-impact` `gn:symmetric-panel-open` `gn:tiled-pattern-drift`；人物需素材；近亲 `ukiyoe-print` |
| `dunhuang` 敦煌壁画 | 土红泥壁上的矿物色壁画、起稿线外露、飘带回旋、藻井纹样，斑驳剥落，举灯才见 | 灯光圈扫过壁面；泥皮剥落显出画层；飘带沿曲线舒展；藻井逐层旋开；矿物色由暗渐醒 | 文明交流、丝路历史、艺术修复、时间与记忆 | Canvas 2D 壁面底图加灯光遮罩与剥落噪声，需素材或生图；`gn:lamp-cone-reveal` `gn:silk-flow` `gn:texture-fill-motion`；近亲 `guochao` |
| `blue-white` 青花 | 温润白釉上单一钴蓝的深浅分水，缠枝纹满铺边带，开光框内绘事，釉面微反光 | 瓷坯在转台缓转；笔锋勾出缠枝；蓝色分水洇开；开光框展开内容；釉光扫过收住 | 器物工艺、品牌传承、海上贸易、东方美学 | Three.js 器形转台贴图；`gn:object-turntable` `gn:branch-growth` `gn:ink-bleed`；纹样程序生成；近亲 `opuscar-ink-wash` |
| `opera-mask` 京剧脸谱 | 近黑或戏台红底，朱砂靛青金粉重彩纹样，黑勾线沿中轴对称，漆面一道高光 | 色块沿中轴镜像铺开；黑线勾出眉眼纹样；亮相定格一震；绕竖轴翻面换配色 | 传统文化、性格对比、立场表态、品牌人格 | SVG 分层上色并中轴镜像，漆面高光用 Canvas 叠加；`gn:outline-then-fill` `gn:stamp-impact` `gn:hard-cut`；近亲 `guochao` |
| `calligraphy` 书法 | 米白宣纸或深墨底，一个大字占满画面，浓淡枯润的笔迹与飞白，一点朱印 | 笔锋按笔顺写出；行笔提按变粗细；枯笔处露出纸纹；朱印收尾落定 | 金句、章节标题、结论、文化主题 | Canvas 2D 沿笔顺路径连续盖毛笔印，字形作蒙版；`gn:tapered-stroke` `gn:handwriting-write-on` `gn:ink-bleed`；近亲 `ink-wash` |
| `ink-comic` 水墨漫画 | 灰白宣纸底，粗细毛笔线勾形，水墨渍染暗部，分格大小错落，一点朱红 | 分格逐格落墨显出；毛笔线先勾轮廓；墨晕从暗部渗开；速度线一笔扫过；动作冲破格框 | 故事讲述、人物经历、历史逸闻、寓言类比 | Canvas 2D 线稿加墨晕蒙版，分格用 SVG 排；线稿需素材或生图；`gn:line-draw` `gn:ink-bleed` `gn:radial-speed-lines`；近亲 `manga` |
| `oriental-mood` 东方意境 | 青灰夜色一轮薄月，江面碎银微光，楼阁远山淡成几层，大片留白 | 山水层次缓慢错动；月光在水面碎开摇动；薄雾横向漂过；诗句逐字浮出后淡去 | 心境独白、文化随笔、片头、诗词解读 | WebGL 水面加多层 Canvas 远景；`gn:deep-parallax` `gn:water-refraction` `gn:atmospheric-depth`；近亲 `opuscar-ink-wash` |
| `eastern-cyber` 东方赛博 | 宣纸色天空悬朱红大日，飞檐楼阁挂霓虹竖招，淡墨未来塔群，倒影如墨晕散 | 霓虹竖招逐笔点亮；全息圆环绕檐顶旋转；淡墨塔群层层显出；灯串沿缆线亮起；水中倒影缓慢晕开 | 中国科技、新国货、未来城市、传统与算法 | 分层生图加 Canvas 合成，霓虹与全息用 WebGL 叠加，需素材；`gn:neon-sign-flicker` `gn:layer-separation` `gn:ink-bleed`；近亲 `cyber-hud` |

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
| `stylized-feature-3d` 动画长片 3D | 圆润夸张比例的三维角色与道具，柔和透光材质，暖色主光，浅景深背景虚化 | 角色先压缩蓄力再弹起；视线转向关键物件；道具落地挤压回弹；焦点从背景拉到表情 | 儿童科普、品牌形象、类比讲解、情绪高光 | Three.js 圆润基础形拼角色，精细版需 Blender；`gn:squash-stretch` `gn:character-gaze-reaction` `gn:rack-focus`；近亲 `soft-3d` |
| `toon-shaded-3d` 卡通渲染 3D | 三维模型配两到三阶硬边色块阴影，黑色外描边，明亮平涂天空与简化物件 | 光阶随转身跳变；描边随距离增减粗细；动作逐拍定格；环绕镜头保持顺滑；拖影帧甩出转折 | 科技概念、游戏话题、青年文化、机械结构 | Three.js 色阶材质加背面外扩描边；`gn:stepped-motion` `gn:smear-frame` `gn:camera-orbit`；近亲 `opuscar-scifi-toon` |
| `sunset-3d-void` 日落 3D 空镜 | 紫色积云压在日落海面，碎金光带从天边铺来，画面中央悬着一句短话 | 镜头贴海缓飞穿过云隙；云边由金转紫；海面光带随飞行摇晃；一句话逐词浮现并停住 | 情绪高点、收尾金句、品牌宣言、章节留白 | Three.js 着色器海面加程序积云，全程序；`gn:camera-flight` `gn:atmospheric-depth` `gn:word-rise-fade`；近亲 `3d-scene` |
| `epic-arena-3d` 史诗竞技场 3D | 烈日下的大理石与鎏金环形场，柱列雕像层层堆满，沙尘暖雾，主角是唯一饱和色 | 低机位贴主角跟拍；柱列连续掠过；步伐扬起沙尘；大全景揭示全场规模；俯拍见跑道成环 | 行业竞争、榜单对决、里程碑、宏大开场 | Three.js 实例化柱列看台，加沙尘粒子与暖雾；`gn:camera-follow` `gn:atmospheric-depth` `gn:motion-blur`；近亲 `3d-scene` |
| `saturated-stage-3d` 七彩舞台 3D | 橙红手绘天幕下的棚拍街区，红砖铁梯水塔布满细节，低角度暖光拉出长影 | 镜头从高处降入布景；主角腾跃定格衬天幕；人偶踩拍齐转身；暖光斜扫砖墙；幕布换色换场 | 团队故事、城市话题、情绪高点、社群文化 | Three.js 舞台式简化街区配贴图细节，手绘天幕用大面片；`gn:crane-tilt` `gn:kinetic-beats` `gn:moving-light`；近亲 `cartoon-stage` |
| `storybook-alpine-3d` 绘本山野 3D | 圆润雕塑感山脊，翠绿草坡，钴蓝晴空，棉絮白云，前景野花草浪随风起伏 | 高空飞越山谷；下降贴近草坡；草浪随风成片伏倒；低机位绕主体环行；云影滑过山坡 | 儿童教育、健康生活、文旅、成长故事 | Three.js 高度场地形加实例化草地，着色器风场；`gn:camera-flight` `gn:camera-orbit` `gn:wave-warp`；近亲 `opuscar-lowpoly-island` |
| `gritty-chase-3d` 16mm 街道追车 | 阴天近白天空下的高架街道，冷灰配暖棕砖木，16mm 粗颗粒，钢架投下条纹光 | 低机位向前疾冲；钢柱频闪掠过；条纹光扫过车身；回看机位盯住主角；片门抖动贯穿全程 | 时间压力、赶工冲刺、危机应对、抢占窗口 | Three.js 实例化街景，后期颗粒与片门着色器；`gn:film-grain` `gn:gate-weave` `gn:camera-shake`；近亲 `crt-film` |
| `long-shadow-3d` 长影写实 3D | 低太阳贴地平线金光侧扫，长影横过地面，冷蓝暗部，细颗粒的 35mm 写实 | 低机位从背后跟随上坡；登顶后绕主角边升边退；定机位看长影伸向镜头；太阳入画才起光晕 | 个人成长、创业复盘、长期主义、人物故事 | Three.js 低角度方向光加长阴影与雾，后期颗粒暗角；`gn:camera-follow` `gn:camera-orbit` `gn:film-grain`；近亲 `3d-scene` |
| `aerial-amber-3d` 琥珀低空飞行 | 逆光琥珀薄雾，淡奶油天空，赭黄大地与三四层远山，上千飞鸟错落惊起 | 越肩望向前方大地；贴水面低空掠过；鸟群分波错开起飞；转向太阳逆光；远山层层退开 | 旅行叙事、行业全景、回望历程、地域介绍 | Three.js 地形加实例化鸟群，噪声错峰起飞；`gn:camera-flight` `gn:atmospheric-depth` `gn:particle-force-field`；近亲 `3d-scene` |
| `backstage-oner-3d` 后台长镜头 | 狭窄旧走廊，暗红墙裙配烟黄灰墙，头顶管线，钨丝灯与闪烁日光灯交替 | 倒退领着主体前行；甩向门洞露出下一场；主体擦过镜头遮挡转场；转身跟上；冷暖灯光交替扫过 | 幕后揭秘、项目过程、一天工作流、连续叙事 | Three.js 走廊分段复用，样条镜头一镜走完；`gn:camera-flythrough` `gn:animated-lighting` `gn:whip-pan`；近亲 `opuscar-backrooms` |
| `underwater-caustics-3d` 水下焦散 | 青绿深水里焦散光网滑过物体，光柱向下探入，气泡微粒悬浮，一盏大暖灯 | 焦散光网滑过主体；光柱斜探入水；气泡上升带出文字；仰看水面慢推；暖灯亮起点题 | 科学科普、潜意识话题、情绪独白、沉浸式开场 | Three.js 投影动态焦散贴图加高度雾；`gn:caustic-ripples` `gn:water-refraction` `gn:ambient-particle-drift`；近亲 `liquid` |
| `particle-fireball-3d` 粒子火球 | 黎明前深蓝旷野，橙金粒子能量在主体身后绽放如光环，暖光铺地，细颗粒 | 白闪半秒打开；粒子球壳翻卷成环；能量环向外扫过地面；光屑飘升散开；主体被暖光勾边 | 突破时刻、概念诞生、科学原理、发布高潮 | WebGL 实例化粒子加卷曲噪声场，二十万粒起步；`gn:particle-burst` `gn:bloom-pulse` `gn:film-grain`；近亲 `particle-explainer` |
| `telephoto-road-3d` 长焦公路 | 漂白日光下的沙地公路，超长焦把坡谷压成层叠波浪，热浪扭曲，深色沥青 | 超长焦看主体沉入又冒出；热浪随距离加重；坡顶低机位掠过；车载机位贴路面；扬尘轻落 | 长期趋势、周期波动、赛道竞争、旅程叙事 | Three.js 窄视角 2–5 度加起伏地形，着色器热浪；`gn:camera-follow` `gn:wave-warp` `gn:film-grain`；近亲 `3d-scene` |
| `silver-deco-3d` 银幕黑白 3D | 三十年代银色黑白：大理石棋盘地、镀铬吊灯、对称纵深、分层转台，只留一个彩色主角 | 平视望进对称纵深；俯拍回廊同心收束；分层转台缓慢旋转；吊臂上升落到主角；光束从高处落下 | 品牌故事、行业历史、高端发布、人物群像 | Three.js 对称布景加去色调色，主角单独留色；`gn:camera-orbit` `gn:crane-tilt` `gn:film-grain`；近亲 `opuscar-art-deco` |
| `fog-castle-3d` 雾堡黑白 3D | 深焦黑白石砌城堡，低雾贴地，湿石发亮，银灰天空，礁石浪沫与银盐颗粒 | 镜头慢漂靠近城垛；沿高处横移；低雾缓缓流过下部；低机位仰看主角；云后光柱隐现 | 悬疑叙事、历史谜题、沉思独白、未解之问 | Three.js 实例化石块加高度雾，后期黑白调色；`gn:atmospheric-depth` `hf:godrays` `gn:film-grain`；近亲 `cinematic-dark` |
| `ortho-amber-3d` 琥珀染色 3D | 默片正色片调色，天空近白带淡琥珀，深黑只在剪影，片门抖动、划痕与圆角暗角 | 绑机位随主体震动；圆形光圈开场；穿云白场转场；灰尘划痕逐帧闪现；每两三秒一切 | 早期科技史、先驱故事、冒险叙事、复古品牌 | Three.js 平滑着色，后期正色调色与片门层；`gn:gate-weave` `gn:film-dust-scratches` `gn:film-grain`；近亲 `opuscar-silent-film` |
| `blueprint-to-render` 蓝图显影 3D | 开头是普鲁士蓝晒图白线，立起透视后显影成金色时刻写实三维，再入蓝调夜景 | 白线描出立面；滑动变焦立成透视；颜色从主体向外显影；幽灵线一秒内淡去；暖灯在蓝调中亮起 | 产品诞生、工程原理、从想法到落地、项目复盘 | Three.js 同一模型切线稿与实景两套材质，显影用球形蒙版；`gn:line-draw` `gn:dolly-zoom` `gn:mask-reveal`；近亲 `blueprint` |
| `multiverse-cut` 多宇宙跳切 | 同一主体跳进三四种画法：冷绿办公、宇宙光环、静默旷野、糖果棚拍，一枚信物贯穿 | 推进信物到满屏；拖影加色差撕开；彩环绽开至画高八成；白闪落入新世界；每个世界换调色 | 平行方案、如果当初、多种结局、创意脑洞 | WebGL 光线步进或 Three.js 多场景，转场用着色器；`gn:zoom-through` `gn:glitch-rgb-split` `gn:flash-transition`；近亲 `era-mix` |

## J. 口播呈现

真人口播本身怎么摆、字幕和包装怎么叠。每种都以出镜人物为主体，B-roll 与动效围着人走；和 A–I 的画面风格可以叠用（例如 `koubo-layout-card` 的窗口里放 `flat-diagram`）。剪口播的手法见手法卡（`library_tools.py search 口播`）。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `koubo-layout-card` 口播板式卡 | 竖屏；深灰网格动态底或暖橙光晕底；素材装进圆角"矩阵蒙版"窗口，人物抠像加白描边或投影压在窗口边上；主标题 + 副标题框、字幕条位置固定 | 七种板式按段落轮换：包围、上中下（圆形头像 / 大关键词）、三段、上下斜切、空间卡片、出框；窗口和关键词卡带轻微透视与发光边，层叠浮起 | 知识口播、财经、职场，有 B-roll 可放的竖屏口播 | 人物抠像（见 [人物抠像进场景](style-stack.md#5-人物抠像进场景)）+ HyperFrames 版式；`gn:perspective-tilt` `gn:card-stack-shuffle` `gn:lower-third-reveal`；B-roll **需素材**；七种板式的参数见手法卡 |
| `tech-explainer-koubo` 科技口播：插画与样机录屏 | 真人在书房口播；穿插纸艺感扁平插画（橙、墨绿、紫底，机器人角色），录屏装进显示器或手机样机、放在米色台面；深底方法卡，左上大标题，条目带红色序号 | 基本一句话一个画面，口播与插画、录屏交替；样机里的录屏缓推；方法卡条目逐条亮起；字幕单行白字居中 | AI 工具、科技产品、效率工作流、演示类口播 | `hf:device-frame-stage` `hf:vfx-iphone-device` `hf:browser-device-stage` `gn:progressive-disclosure`；插画 **需素材**（生图后统一色板） |
| `emotion-quote-koubo` 情感金句口播 | 近距自拍、暗暖室内光；字幕放在脸侧而不是底部，宋体或衬线中文配一行小号英文；关键词黄色；偶尔一个超大衬线词压在画面上方 | 一句拆两行：上行小字铺垫、下行大字落点；逐句出现不做弹跳；超大字只给核心词，一条片子两三次 | 情感、心理、人生感悟、金句类口播 | HyperFrames 字幕层；`hf:blur-in` `hf:per-word-rise`；思源宋体或霞鹜文楷；无需 B-roll |
| `typo-studio-koubo` 大字棚拍口播 | 横屏，灰色无缝背景布，人物半身居中；人后和四周是超大中文字，红、藏蓝、白三色，字号对比极大；章节用黑底红字加小号 "PART" 卡；偶尔叠取景器 REC 角标 | 关键词从四周飞入或砸下铺满背景；疑问词绕着人头散开；章节黑场闪切；字在人后 | 观点、方法论、个人 IP 干货 | 人物抠像 + HyperFrames 文字层；`hf:kinetic-type-swap` `gn:kinetic-beats` `gn:stamp-impact` `hf:camcorder-hud` `gn-recipe:chapter-transition` |
| `ip-interior-koubo` 实景高级感 IP 口播 | 实景办公室、沙发、落地窗，自然光；红色粗衬线标题带投影，关键词放大变橙红，小字白色衬线；景别在全身、中景之间切换 | 同一句话里一两个关键词放大变色，其余小字；景别切换换段落；包装按"字幕花字 → 音效 → 画中画素材"一层层加 | 个人 IP、创业、培训、高客单服务 | HyperFrames 字幕层；`hf:per-word-rise` `gn:lower-third-reveal`；画中画 **需素材** |
| `word-caption-white` 白底逐字口播 | 纯白底，一种字体的黑字，字幕逐词跟口播打出，穿插真实图片，镜头缓慢漂移 | 字幕按录音逐词出现；每段只漂移一次；图片踩十六分音符切换；关键句音乐抬起 | 口播主线、产品发布、观点讲述、知识分享 | HTML 逐帧排字，时间取语音转写时间戳，图片需素材；`gn:word-rise-fade` `gn:ken-burns` `gn:beat-sync`；近亲 `koubo-layout-card` |
| `vertical-pov` 竖屏 POV | 竖屏第一人称，手部入画，广角贴近物件，碎剪加满音效，安全区内一个大字 | 手伸入画面拿起物件；甩镜切入下一动作；踩拍跳切；速度骤变落定；音效对齐每次触碰 | 竖屏开头钩子、产品上手、流程快览 | 实拍素材为主，缺料用 Three.js 第一人称场景，需素材；`gn:jump-cut` `gn:whip-pan` `gn:speed-ramp`；近亲 `person-in-scene` |

## K. 组合方式

| key | 说明 |
|---|---|
| `person-in-scene` 人物入景 | 口播人物抠像后放进任一场景风格，见 [人物抠像进场景](style-stack.md#5-人物抠像进场景) |
| `era-mix` 年代混合 | 每个时代一种画法（如像素 → 质感层 → 3D），换风格跟着时代走，配乐与字体贯穿全片 |

## L. 诗意氛围

不讲信息只给情绪的画面：一个缓慢的自然现象或几何场，常作片头、段落呼吸和金句底。用代码就能画，不依赖素材。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `flowing-threads` 流动丝线 | 墨蓝近黑底、数千根发丝细线顺无形气流并行，疏密成云，一缕暖丝贯穿全场 | 线束绕开字形显出负形；乱线梳成同向；暖丝抽出领路；线束收成一股抽走换场 | 思绪梳理、情绪平复、趋势走向、抽丝剥茧式分析 | Canvas 2D 噪声流场逐帧积分，固定种子保证可复现；`gn:wave-warp` `gn:film-grain`；近亲 `liquid` |
| `firefly-dust` 萤火光尘 | 炭褐近黑底、三层景深的暖金光点缓慢上升，近处大而虚，远处小而实，暗处藏柔边剪影 | 光点自下而上飘升；一颗停住变亮成主角；近景光斑掠过镜头；光点围拢托出一行字 | 回忆、致谢、个人故事、品牌初心、温暖收尾 | Canvas 2D 三层粒子加屏幕混合；`gn:ambient-particle-drift` `gn:atmospheric-depth`；近亲 `cinematic-dark` |
| `particle-shapes` 粒子聚形 | 墨黑底、数千颗细亮粒子聚成实心轮廓，停稳后拉成弧形流线，奔向下一个图形 | 粒子沿弧线汇聚成形；成形后停住字幕升起；一阵风吹散外缘；同批粒子流向下一形 | 概念串联、因果递进、产品组成、一句一个比喻 | Canvas 2D 或 WebGL，图形采样成目标点，同序号粒子跨形复用；`gn:particle-assemble` `gn:particle-force-field`；近亲 `particle-explainer` |
| `star-network` 星空连线 | 靛黑夜空、冷白星点散布，细线按距离连成网，唯一一颗暖星居于网中 | 星点逐颗亮起；连线从暖星向外依次生长；一根线断开网络偏移；视角拉远见全网 | 人际关系、组织协作、生态系统、知识图谱 | Canvas 2D 节点图，弱力导向加固定种子；`gn:line-draw` `gn:ambient-particle-drift`；近亲 `particle-explainer` |
| `breathing-circle` 呼吸的圆 | 深灰绿底、画面正中一团柔软的粒子圆，随呼吸节拍胀缩，除它之外别无他物 | 圆团吸气胀大；屏息时停住；呼气收缩抖落外层粒子；一句字随呼气淡入 | 冥想引导、压力话题、慢节奏开场、章节之间的停顿 | Canvas 2D 径向分布粒子，半径由呼吸曲线驱动；`gn:ambient-particle-drift` `gn:motion-hierarchy`；近亲 `morph` |
| `contour-lines` 心里的等高线 | 暖灰纸色底、细墨绿等高线铺满全屏并缓慢起伏，峰顶处线条收紧，一点朱红标记高点 | 等高线缓慢隆起成峰；线距收紧显出陡坡；朱红标记沿路径攀升；地形抹平换段 | 情绪曲线、起伏历程、增长高低点、心理话题 | Canvas 2D 噪声高度场逐帧提取等值线；`gn:wave-warp` `gn:line-draw` `gn:map-route-animation`；近亲 `line-art` |
| `ripple` 涟漪 | 俯视深青水面、细亮同心环由一点荡开，环与环相交生出干涉纹，水下字迹随波微颤 | 一滴落下溅起小环；同心环向外推开；环碰到字激起二次波；水面归于平静 | 一句话的影响、余波、连锁反应、政策传导 | WebGL 或 Canvas 2D 波动高度场做折射与高光；`gn:wave-warp` `hf:blur-in`；近亲 `liquid` |
| `rain-window` 雨窗 | 夜色玻璃前景挂满水珠，背后是圆形虚化灯斑，水珠倒映倒置灯影，一道水痕缓缓滑落 | 水珠聚大后顺玻璃滑落；滑痕擦出一道清晰窗景；灯斑缓慢变色；雾气上手写短句 | 等待、夜间独白、想念、复盘失败、深夜故事 | WebGL 水滴折射，背景灯斑可程序生成；`gn:glass-refraction` `gn:film-grain`；近亲 `cinematic-dark` |
| `window-light-dust` 窗光与尘 | 老灰泥墙的暗室，一束斜光穿过窗棂落在地面，浮尘在光柱里缓慢翻动，光块随时间移动 | 光柱缓慢扫过墙面；尘粒在光里翻飞；地上窗格影子拉长；字被光块照亮再退暗 | 时间流逝、老行业、家族记忆、沉思段落 | Canvas 2D 光柱遮罩加粒子，房间可代码画或生图；`hf:godrays` `gn:ambient-particle-drift`；近亲 `cinematic-dark` |
| `snow-ember` 雪与火星 | 蓝黑夜空下细雪缓慢落下，几粒橙红火星逆向升起，一冷一热穿过彼此，地面只有一线暗影 | 雪片向下飘落；火星逆向上升；火星掠过时照亮周围雪片；最后一粒熄灭成字 | 告别、收官、逆境里的坚持、季度或年度总结 | Canvas 2D 两组反向粒子，火星带拖尾；`gn:ambient-particle-drift` `gn:atmospheric-depth`；近亲 `cinematic-dark` |
| `dawn-gradient` 天亮 | 一块由靛蓝过渡到杏粉的全屏天色，低处一线暗色地平，日轮缓缓出现，画面亮度随全片推进 | 天色逐段由冷转暖；地平线染出一线亮；日轮浮出地平；剪影随光显形；字由暗转亮 | 片尾收束、转机、新阶段、发布前夜到发布 | Canvas 2D 或 WebGL 多停靠点渐变按时间插值，抖动防色带；`gn:mesh-gradient-flow` `hf:flowing-gradient`；近亲 `grainy-gradient` |
| `symmetric-warm` 对称暖色小舞台 | 奶粉与杏黄的布景，严格中轴对称，物件成对摆放，像橱窗里精心搭好的小舞台 | 幕布或窗格左右对开；物件从中轴成对滑入；背景层缓慢换季；一件小物微微颤动 | 时间流逝、停更自述、阶段回顾、生活方式、品牌故事 | 生图 + 分层，需素材；HTML 逐帧或 Canvas 2D 做中轴镜像与景片移动；`gn:layer-separation` `gn:popup-book`；近亲 `cartoon-stage` |
| `abstract-emotion` 抽象情绪 | 单色场上几何形与文字互相挤压，颜色由一种状态漂向另一种，没有人物和物件 | 形状挤压文字；色场突然翻转；碎形积聚成压迫；字被撕开又重组；节奏由乱到稳 | 焦虑、恐惧、内耗、认知转变、片头情绪定调 | SVG 或 Canvas 2D 形变加逐字控制；`gn:shape-morph` `gn:kinetic-beats` `gn:wave-warp`；近亲 `morph` |

## M. 绘画与古典媒材

把画种本身当风格：油彩、蛋彩、色粉、炭笔、金箔、马赛克。动作要克制，运动通常就是"这幅画正在被画出来"或光在画面上移动。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `chiaroscuro-oil` 顶光明暗油画 | 17 世纪荷兰明暗法油画：七成琥珀暗部，一盏顶光落成光池，亮处厚涂，暗处薄罩 | 主体从暗部被光池托出；顶光缓慢下压；手部特写推进；一点暗红落下定调；光池收窄 | 权力结构、决策内幕、家族企业、严肃人物评述 | 生图 + 分层，需素材；Canvas 2D 叠光池遮罩和画布纹；`gn:ken-burns` `gn:layer-separation` `gn:film-grain`；近亲 `opuscar-impasto` |
| `moonlight-portrait` 月光蓝调肖像 | 夜色人物油画：蓝紫满幅，顶面受月光，侧缘透青绿，轮廓一道品红，笔触细密贴形 | 笔触沿形体反复重绘；水面碎光缓慢流动；品红轮廓光渐亮；人物静立不动 | 个人成长、身份认同、人物特写、孤独与自省 | 生图 + 分层，需素材；WebGL 水面碎光，Canvas 2D 叠笔触循环；`gn:ken-burns` `gn:layer-separation`；近亲 `opuscar-impasto` |
| `western-plains-oil` 西部油画 | 19 世纪末美国边疆油画：低地平线、金红晚霞横向长笔，大地与人物压成暗暖剪影 | 晚霞横向长笔渐次铺开；剪影沿地平线走入；向阳边亮起细轮廓；入夜后切成蓝绿雨夜 | 创业开拓、行业拓荒、人物传记、单打独斗的故事 | 生图 + 分层，需素材；Canvas 2D 叠前后景视差与雨；`gn:deep-parallax` `gn:ken-burns` `gn:film-grain`；近亲 `opuscar-impasto` |
| `old-master-portrait` 古典肖像油画 | 北方文艺复兴木板油画：墨绿帷幕前的正式半身像，毛皮、天鹅绒、金饰逐一细画，覆旧光油与龟裂 | 主体端坐入画；材质特写逐一扫过；窗口里露出小场景；手中物件翻转；龟裂纹缓慢爬开 | 机构档案、人物生平、制度史、把公司拟人讲述 | 生图 + 分层，需素材；Canvas 2D 叠光油和龟裂遮罩；`gn:ken-burns` `gn:mask-reveal` `gn:layer-separation`；近亲 `opuscar-impasto` |
| `quiet-realism` 静默写实 | 20 世纪中期美国写实绘画：大块淡绿与奶油平面、低角度硬边光块，人物相隔而立 | 长时间静止；地面光块缓慢移动；不到一秒的突发打破平静；人物各自站开不接触 | 职场疏离、制度与个体、等待、城市孤独 | 生图 + 分层，需素材；SVG 或 Canvas 2D 做硬边光块移动；`gn:hard-cut` `gn:light-sweep` `gn:layer-separation`；近亲 `editorial-light` |
| `dry-tempera` 干笔蛋彩 | 石膏底板蛋彩：干哑细密的交叉短笔，苍白阴天、枯草黄与赭褐，小主体偏居一隅 | 细笔一层层织出画面；一阵风压低草坡；唯一强调色小点出现；圆形遮罩收束切场 | 乡村题材、衰退产业、记忆书写、沉静传记 | 生图 + 分层，需素材；Canvas 2D 细笔排线逐层显现；`gn:hatch-fill` `gn:mask-reveal` `gn:ken-burns`；近亲 `opuscar-urban-sketch` |
| `social-realism` 社会写实蛋彩 | 1930–50 年代社会写实：颤动的转印墨线，下压错位的干笔蛋彩色块，灰蓝砖红赭黄 | 墨线断续抖动画出轮廓；色块慢半拍错位落下；干笔拖痕扫过；大手进画推动物件 | 劳动议题、产业变迁、基层故事、行业观察 | Canvas 2D 或 SVG 抖线加错位色块，人物需素材时再生图；`gn:line-boil` `gn:outline-then-fill` `gn:stepped-motion`；近亲 `hand-drawn` |
| `magazine-realism` 杂志封面写实 | 1930–50 年代美国周刊封面插画：块面塑造的人物、暖主光冷阴影，背景藏小故事 | 封面框收入刊头；次要人物各忙各的；焦点推向手上小物；一个表情定格成封面 | 消费史、职业故事、社区生活、怀旧主题、商业案例 | 生图 + 分层，需素材；HTML 逐帧叠刊头与景深；`gn:deep-parallax` `gn:ken-burns` `gn:page-turn`；近亲 `editorial-light` |
| `charcoal-gothic` 炭笔哥特 | 粗纹白纸上的炭笔：绒黑、抹灰与橡皮擦出的光，雾在横向擦痕里漂移，只有主角带一点色 | 炭笔侧锋扫出大暗块；手指抹开灰调；橡皮擦出光与雾；擦过处留残迹再重画 | 悬疑叙事、未解之谜、旧宅往事、黑暗历史中的日常 | Canvas 2D 纸纹阈值模拟炭粉，或生图 + 分层需素材；`gn:hatch-fill` `gn:scribble-wipe` `gn:line-boil`；近亲 `opuscar-engraving` |
| `pastel-dusk` 色粉黄昏 | 灰紫色纸上的软色粉：天空揉抹成金到紫的横向带，地面细草笔铺满，纸纹处处透出 | 天色由金转玫瑰再转紫；细草笔自前向后铺开；一盏小灯在暮色里亮起；画面缓慢横移 | 漂泊与旅程、退休人生、慢生活、告别一段职业 | 生图 + 分层，需素材；Canvas 2D 按时间调天色并叠纸纹；`gn:infinite-pan` `gn:deep-parallax` `gn:film-grain`；近亲 `opuscar-crayon-book` |
| `gouache-valley` 水粉山谷 | 不透明水粉山谷：金色天光、绿田与煤黑山体，方向性短块笔，断续深色线勾屋脊 | 笔块一层层盖满山坡；路从高处引向谷底；小屋沿坡逐级出现；炊烟循环飘动 | 家乡、县域经济、矿业地方史、集体记忆 | 生图 + 分层，需素材；Canvas 2D 烟云循环；`gn:infinite-pan` `gn:deep-parallax`；近亲 `opuscar-silkscreen-poster` |
| `epic-poster-gouache` 史诗海报水粉 | 1960 年代手绘片场海报：不透明水粉铺底，油性亮笔收边，蓝天压琥珀地，主角居中斜势 | 主角带斜线势入场；布料随风扬起；受光边压亮一笔；片名大字从底部升起 | 大事件、里程碑、人物宣传片、片头片尾、大决定 | 生图 + 分层，需素材；HTML 逐帧分层视差加片名；`gn:deep-parallax` `hf:headline-slam`；近亲 `opuscar-silkscreen-poster` |
| `illuminated-manuscript` 泥金手抄本 | 羊皮纸页、隆起贴金、青金与朱砂、宽边藤蔓花饰、窗口式小画 | 金箔随光扫过闪一下；大首字母逐笔描金；边框藤蔓沿页缘生长；小画窗口推入；翻页换章 | 编年史、行业起源、知识谱系、长期主义叙事 | Canvas 2D 分层，金箔用高光贴图；`gn:light-sweep` `hf:svg-stroke-trace` `gn:page-turn`；小画需素材；近亲 `opuscar-stained-glass` |
| `miniature-portrait` 宫廷细密画 | 群青圆底、金线椭圆挂坠、羊皮纸上不透明水彩、极细排线、暗红织锦衬底 | 椭圆框从中心开窗；排线逐层压出暗部；金字铭文绕框写出；挂坠翻面换场 | 人物小传、品牌故事、藏品解读、一句箴言 | Canvas 2D 合成椭圆蒙版与排线；`gn:hatch-fill` `gn:mask-reveal` `gn:light-sweep`；主体需素材；近亲 `vintage-engraving` |
| `mosaic` 罗马马赛克 | 暖灰灰缝、方形小石粒、赭金陶红天然石色、少量闪光玻璃片 | 轮廓先铺两圈定形；石粒由外向内逐粒铺满；金玻璃片随光闪烁；整面石粒翻转换场 | 古今对照、文明史、城市史、长期结构 | Canvas 2D 程序铺粒，顺边排列；`gn:piece-assembly` `hf:grid-pixelate-wipe` `gn:light-sweep`；近亲 `opuscar-stained-glass` |
| `rococo-silhouette` 洛可可剪影 | 纯黑侧影纸样、金色描边、象牙与暗红丝绒、卷草金框、烛光暖晕 | 剪刀沿轮廓剪出侧影；金边随烛火亮起；卷草金框从四角长出；丝绒幕合拢换场 | 人物关系、艺术史、社交礼仪、戏剧性反转 | SVG 或 Canvas 2D 分层；`gn:papercut-placement` `gn:layer-separation` `gn:ambient-particle-drift`；近亲 `paper-cut` |
| `textured-wall-interior` 斑驳墙室内 | 层层旧漆剥落的灰绿墙、磨穿露底、潮线裂纹、高窗冷光、人物偏居一角 | 墙皮随重音剥开一块；裂纹沿墙面爬行；旧漆字从墙里渗出；窗光斜移；人物退到角落 | 心理议题、沟通难题、转型阵痛、创始人自述 | 生图 + 分层，Canvas 2D 做剥落蒙版；`gn:mask-reveal` `hf:grain-overlay` `gn:ken-burns`；需素材；近亲 `opuscar-impasto` |

## N. 影像质感

胶片与早期摄影的成像质感：可以直接加在真实素材上，也可以给生成图统一影调。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `studio-noir` 片厂柔光黑白 | 银灰柔焦、喷枪式明暗、斜落条影、雾中光柱、小块发光白 | 条影缓缓扫过物面；暗角收拢聚焦主体；雾中光柱显形；溢光字幕柔出；叠化转场 | 悬念开场、商战博弈、案件复盘、人物抉择 | 生图 + 分层，WebGL 或 Canvas 做溢光；`gn:film-grain` `gn:gate-weave` `hf:godrays`；需素材；近亲 `cinematic-dark` |
| `high-key-bw` 高调黑白 | 亮灰天空、强日光短影、冲白高光、湿面反天、细银盐颗粒 | 日光一闪冲白转场；云影掠过地面；高光泛晕推入主体；黑字压上白墙 | 清醒观点、生活方式、人物故事、旅行与城市 | 生图或实拍调色，WebGL 曲线 + 光晕；`gn:film-grain` `gn:film-dust-scratches` `gn:ken-burns`；近亲 `documentary-archive` |
| `selective-color-bw` 黑白唯一色 | 冷灰黑白、粗银盐颗粒、高光微晕、全画面只留一件物体有色 | 灰色画面里种下一点颜色；有色物穿过灰色物群；颜色漫开铺满再收到下一物；结尾褪回灰 | 线索追踪、信息过滤、唯一变量、关键决策 | 实拍或生图转灰 + 分割蒙版，WebGL 逐帧；`gn:film-grain` `gn:mask-reveal` `hf:cinematic-zoom`；近亲 `cinematic-dark` |
| `albumen-panorama` 蛋白印相全景 | 金调棕褐、奶油高光、三联拼接接缝、长曝拖影、卡纸装裱 | 镜头沿全景横移；到站停住拉出注记线；穿过接缝进入下一联；动体拖影虚化 | 城市变迁、地理格局、产业版图、长时间跨度 | 生图分层，Canvas 2D 调色拼缝；`gn:infinite-pan` `hf:pan-stations`；需素材；近亲 `opuscar-archive-lighttable` |
| `daguerreotype` 银版显影 | 银灰镜面、黄铜衬框、皮盒丝绒内衬、边缘氧化晕、静止摆拍 | 影像由暗部向亮部显出；倾斜底版让正负像翻转；窗光掠过镜面；盒盖合上换场 | 溯源考据、单件物证、创始时刻、记忆与遗物 | Canvas 2D 或 WebGL 阈值显影；`gn:mask-reveal` `gn:light-sweep`；需素材；近亲 `opuscar-archive-lighttable` |
| `hand-tinted-photo` 手工上色老照片 | 棕褐底片、透明染料薄刷、颜色溢出轮廓、霉点裂角、边缘银化 | 笔刷沿主物刷上颜色；颜色溢出边线晕开；旧照抬起露出下一张；翻到背面看手写 | 家族故事、老店品牌、地方记忆、时代切面 | 旧照或生图转棕褐，Canvas 2D 笔刷上色；`gn:ink-bleed` `hf:ink-bleed-reveal` `gn:film-grain`；需素材；近亲 `era-mix` |
| `stage-spotlight` 红黑聚光舞台 | 漆黑舞台、深红幕布、硬边白追光、黑剪影描红边、橙红霓虹大字 | 追光啪地打到主角；灯格逐个亮起；红幕拉开亮出答案；霓虹字闪两下点亮 | 揭晓时刻、榜单排名、人物亮相、争议对决 | Canvas 2D 或 WebGL 算光锥与雾；`gn:neon-sign-flicker` `gn:hard-appearance` `hf:godrays`；近亲 `neon` |

## O. 结构手法

不规定画什么，规定全片怎么串：画面皮肤从 A–N 里另选一种叠上去，这里只管结构。

| key | 观感 | 标志动作 | 适合内容 | 实现与素材 |
|---|---|---|---|---|
| `single-thread` 一个元素串全片 | 素净底色、一个高饱和小元素、连续运动轨迹、场景随它变化 | 小方块滑入成为标点；拉长变成柱子；滚动化作窗格；收缩回到开场原位 | 全片串联、多风格混搭、概念递进、品牌短片 | SVG 或 HTML 逐帧，同一元素穿场；`gn:shape-morph` `gn:motion-hierarchy` `gn:spring-overshoot`；近亲 `morph` |
| `seamless-oner` 一镜到底 | 连续空间、场景互相长出、无切点、单向连贯运镜、层层穿越 | 镜头穿入物体内部；物件展开成下一场景；色块铺满接力；同形物接过画面 | 流程串讲、前后变化、产品全程、城市漫游 | Three.js 或 HTML 大画布相机；`hf:cinematic-zoom` `gn:mask-reveal` `gn:shape-morph`；近亲 `whiteboard-world` |
| `minimal-beat` 极简卡点 | 大片留白、紧字距无衬线、一个强调色、单镜单事、构图稳定 | 字词踩重拍遮罩显出；每一拍硬切换屏；强调色块横扫盖词；结尾空一拍留白 | 痛点排比、功能罗列、开场钩子、预告节奏 | HTML 逐帧按节拍表排时间点；`gn:kinetic-beats` `gn:hard-cut` `gn:mask-reveal`；音乐需授权；近亲 `kinetic-type` |
| `emotion-arc` 情绪弧线 | 由乱到序：碎片噪线收束成整齐线组，最后只剩一句话 | 杂乱碎片涌满画面；线条逐根理顺；形状接力收束成一块；噪点退场；一句话独留 | 整期结构、问题到解法、转型故事、产品价值 | Canvas 2D 或 WebGL 线束收束；`gn:shape-morph` `gn:line-boil` `gn:motion-hierarchy`；近亲 `morph` |
| `life-loop` 人生循环 | 同一主体依次变化、首尾同构、一条连续路径、环形时间 | 主体边走边长大；背景随阶段替换；终点身影迈回起点；首尾帧重合接回 | 成长史、产品迭代、行业周期、终身学习 | SVG 关节角色或生图分层；`gn:walk-cycle` `gn:shape-morph` `gn:infinite-pan`；近亲 `cartoon-stage` |
| `silent-short` 无对白短片 | 无对白、环境声主导、长停留画面、单一小故事、大片留白 | 画外声先于画面出现；人物停下转头；空镜停留等声音；物件交代结果；音乐最后才入 | 片头片尾、章节过渡、情绪段落、品牌小片 | 生图或实拍分层，Canvas 2D 动人物；`gn:character-articulation` `gn:atmospheric-depth` `gn:ken-burns`；需素材；近亲 `cartoon-stage` |
| `cosmic-zoom` 点到宇宙 | 黑场一点、层层尺度嵌套、角落读数、星点与灯光同构 | 黑屏一点展开成场景；连续拉远到地球再到星系；读数同步滚动；缩成一点推入新世界 | 尺度对比、规模感、系统全貌、小工具大影响 | WebGL 或 Three.js 嵌套贴图缩放；`hf:cinematic-zoom` `gn:rolling-digits` `gn:deep-parallax`；需素材；近亲 `opuscar-microscope` |
| `break-frame` 破框 | 平面海报或画框、主体越过边界、真实投影、框内框外两种空间 | 主体撞出边框；纸边卷起碎片缓落；投影落到框外墙面；框内世界定住 | 观念转折、打破常规、跳出行业、产品亮相 | Canvas 2D 分层或 Three.js；`gn:depth-assemble` `gn:layer-separation`；主体需素材；近亲 `poster-colorblock` |
| `movie-trailer` 电影预告片 | 2.39:1 遮幅、近黑暖褐天幕、漂浮尘埃、宽字距居中字卡、光晕呼吸 | 字卡从暗处亮起；经黑场换下一张；数字踩低频重音涌现；闪光后片名落定；淡出留日期 | 下期预告、频道宣传、产品预热、大事件开场 | HTML 逐帧或 WebGL 光晕；`gn:ambient-particle-drift` `hf:blur-in` `gn:film-grain`；音乐需授权；近亲 `cinematic-dark` |
