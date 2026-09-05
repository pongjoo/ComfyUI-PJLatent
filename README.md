# ComfyUI-PJLatent

A powerful and convenient custom node suite for ComfyUI, providing aspect-ratio-based Latent generation, video Latent creation, interactive image comparison/saving, and offline Chinese-to-English translation.

功能强大的 ComfyUI 自定义节点套件，提供基于长边与高宽比的空 Latent 生成、视频 Latent 生成、交互式双图对比预览/保存、以及智能离线中文转英文翻译节点。

---

## 🌟 Features / 功能特性

### 1. PJ Text Translator (Bi-Directional) | 智能双向文本翻译节点
- **智能双向互译 (Bi-Directional Translation)**: 支持 `Auto` 智能识别模式、`ZH -> EN` (中译英) 与 `EN -> ZH` (英译中)。输入中文自动转英文 Prompt，输入英文自动翻译为中文！
- **纯离线/自动下载 (Offline / Auto Download)**: 基于 `opus-mt-zh-en` 和 `opus-mt-en-zh` 离线小模型。若本地未找到模型文件，会自动从 HuggingFace/镜像站定向补齐所需核心文件。
- **提示词标点规范化 (Clean Punctuation)**: 自动将中文全角标点（`，` `。` `！`）清洗替换为标准的英文半角逗号加空格（`, `），符合 SD/Flux 提示词格式。
- **前缀与后缀拼接 (Prefix & Suffix)**: 支持在节点内部一键添加画质前缀词或自定义后缀。
- **显存驻留优化 (Memory Cache)**: 支持模型驻留，后续翻译实现毫秒级极速响应。

### 2. PJ Image Preview/Save | 图像对比预览与保存节点
- **交互式滑动对比 (Interactive Image Slider)**: 当同时连接两张图片时，支持在节点画布上通过鼠标左右移动进行实时滑动切分对比。
- **资产与历史无缝兼容 (Full Assets & History Sync)**: 严格兼容 ComfyUI 资产管理器与历史记录面板，自动录入生成的预览图与保存图。
- **无感剔除默认框**: 前端高频重绘自动过滤默认预览组件，保证滑动对比顺畅无遮挡。

### 3. PJ Latent Generator | 比例 Latent 生成器
- **按比例与长边生成**: 选择常用屏幕高宽比（`1:1`, `16:9`, `4:3`, `9:16` 等）及最长边像素，自动计算对应分辨率。
- **8倍倍数对齐**: 自动取整为 8 的倍数，符合 SD / Flux 等主流扩散模型的尺寸要求。

### 4. PJ Video Latent Generator | 视频 Latent 生成器
- **视频维度适配**: 专门针对视频大模型（如 HunyuanVideo / Wan 等），支持按秒设置视频时长（按 16 FPS 自动计算帧数 `秒数 * 16 + 1`）。
- **16倍倍数对齐与16通道**: 输出符合视频模型要求的 16 通道 5 维视频 Latent 张量。

### 5. PJ Lora Loader (Custom Path) | 自定义路径 LoRA 加载器
- **智能目录文件扫描 (Custom Path Scan)**: 支持直接输入任何盘符或自定义文件夹路径。节点会自动深度扫描该目录下所有子目录中的 `.safetensors`, `.ckpt`, `.pt` 格式 LoRA 模型。
- **前端动态下拉联动 (Dynamic Dropdown)**: 当你在前端修改 `LoRA文件夹路径` 时，`LoRA文件` 下拉框会自动通过后台 API 刷新该路径下的所有模型列表，并支持保留已有选值，无需手动输入文件名。
- **满血功能对齐**: 支持与原生 LoRA 加载器完全一致的 `模型权重` 和 `CLIP权重` 强度调节。

### 6. PJ Image Stitcher | PJ 图像智能记忆拼接器
- **局部重抽记忆回读**: 节点自动记录各槽位图像张量的 MD5 指纹。重新生成局部槽位图片时，未变动或留空的槽位自动回读上一轮旧图，即时无缝重新拼接！
- **满槽自动扩增机制**: 默认精致紧凑的 5 槽位；只有当现有槽位全部接满时，前端自动拓展出新槽位（最多支持 30 槽位），断开时自动回收。
- **最长边智能对齐与尺寸约束**: 默认按照拼接边中最长边的尺寸智能对齐；支持自由设定基准边尺寸限制。
- **丰富拼接模式**: 四宫格(2x2)、九宫格(3x3)、横向拼接、纵向拼接、自定义行列网格。

### 7. PJ Image Interactive Slicer | PJ 图像交互式智能分割器
- **原生支持上传与拖拽**: 自带图片选择与“选择文件上传”按钮，支持从电脑直接拖拽图片到节点，瞬间就位预览。
- **交互式自由切线**: 顶部直观的小按钮 `[ ── 横线 ] [ │ 竖线 ] [ 🗑️ 清空 ]`，鼠标移入画板实时跟随，左键单击即刻落刀锁定，按住 `Shift` 智能磁吸常用刻度。
- **节点内专属暗黑微调浮层**: 点击切线分值标签或双击切线，在节点内原地弹出暗黑风格精准微调卡片，支持直接输入百分比/像素，或一键点击 `[ 25% | 33.3% | 50% | 66.7% | 75% ]` 快捷等分！
- **方向键高精度精调**: 选中切线直接按键盘方向键以 `0.1%`（按住Shift为 `1.0%`，按住Ctrl为 `0.01%`）精细平移；按 `DEL` 键一键删除。
- **动态多端口输出**: 自动统计切块并动态生成对应数量的输出端口（`块1_图片` ~ `块K_图片`），外加批次张量与切片文本。

### 8. PJ Image Slice Reassembler | PJ 图像切片原位还原器
- **分割与还原闭环 (Slicer to Reassembler Workflow)**: 专门搭配 `PJ 图像交互式智能分割器` 使用。解决“把大图切成九宫格或多块后，单独修改某一块或多块（如局部重绘/高清放大），并无缝拼回原图原位”的核心需求！
- **单块与多块原位替换**:
  - **8 组独立快速槽位**: 连线 `槽位1_图片` 并指定 `槽位1_目标块序号`（如 5），即可单独替换第 5 块；支持同时连入多个槽位同时替换不同块。
  - **批次批量替换 (Batch Slices)**: 支持直接接入 `批次替换图片`，并在 `批次对应块序号` 中输入如 `"5"`、`"2, 5, 8"`、`"1-3, 5"` 或 `"全部"`，一键对号入座！
- **余弦 S 曲线边缘羽化过渡 (Cosine Feathering Blend)**:
  - 智能边缘检测：仅在切块内侧接缝处生成平滑柔和的渐变羽化过渡，自动避开画幅外框边缘，彻底消除切块接缝与像素硬痕！
- **多模式分辨率自适应 (Resolution Adaptive)**:
  - `缩放替换块至原切片尺寸 (维持基底分辨率)`: 局部块放大或重绘后，自动缩放至原切块像素并羽化拼回。
  - `整图等比高清放大 (自适应替换块最高倍率)`: 若单块经过 2x/4x 超分辨率放大，整图画布自动同比例高清放大，无损保留重绘切块的极致高清细节！
- **三项实用输出**:
  - `还原后图像` (IMAGE): 完整还原的高清合并大图。
  - `替换区域遮罩` (MASK): 对应修改切块的准确区域遮罩，方便后续进一步生图或检查。
  - `还原汇总信息` (STRING): 格式化文字报告，罗列各块替换坐标、分辨率缩放与未变动保留块。

### 9. PJ Text Suite | PJ 文本/提示词套件
- **PJ-通配符单选 (`PJWildcardNode`)**: 从 41 种内置中英文分类词表（或自定义词表）中按种子随机抽取词条。
- **PJ-通配符大师 (`PJWildcardParserNode`)**: 语法级模板通配符展开，支持嵌套与权重解析。
- **PJ-动态文本拼接 (`PJTextCombine`)**: 动态按需增减输入行数，多段提示词灵活合并。
- **PJ-JSON提示词提取器 (`PJ_JSON_To_Prompt`)**: 结构化 JSON 提示词解析器，完美兼容 Gemma 4 等大模型输出格式。

### 10. PJ Batch Video Suite | PJ 批量视频套件
- **PJ-视频加载 (`BatchVideoLoader`)**: 批量视频帧按批次读取提取为图像张量。
- **PJ-视频路径加载 (`BatchVideoPathProvider`)**: 自动步进读取视频路径与文件名称。
- **PJ-视频与标签保存 (`BatchVideoSaver`)**: 视频与对应文本标签同步导出。
- **PJ-官方Gemini格式转换 (`PJ_LoadVideoPathForOfficial`)**: 格式转换为 ComfyUI 官方 Video 对象。

---

## 🛠️ Installation / 安装说明

1. 克隆或下载本仓库至你的 ComfyUI `custom_nodes` 目录下：
   ```bash
   cd ComfyUI/custom_nodes/
   git clone https://github.com/pongjoo/ComfyUI-PJLatent.git
   ```
2. 重启 ComfyUI 即可自动加载所有节点。

---

## 📖 Node Usage / 节点使用指南

在 ComfyUI 工作流画布中右键 -> `PJ_Nodes` 找到对应节点：

### 📄 PJ Text Translator (Bi-Directional)
- **输入参数**:
  - `text`: 输入需要翻译的文本（支持多行）。
  - `mode`: 默认 `Auto (智能双向检测)`，也可手动选择 `ZH -> EN (中译英)` 或 `EN -> ZH (英译中)`。
  - `clean_punctuation`: 自动清理和规范化标点（默认开启）。
  - `prefix` / `suffix` (可选): 可在输出结果前后自动拼接文本。
  - `device`: `auto`（优先 CUDA 显卡加速）、`cuda` 或 `cpu`。
- **离线模型手动存放路径（可选）**:
  若手动下载，请将解压后的核心模型文件放入以下路径：
  - 中译英: `ComfyUI/models/prompt_generator/opus-mt-zh-en/`
  - 英译中: `ComfyUI/models/prompt_generator/opus-mt-en-zh/`

### 📄 PJ Lora Loader (Custom Path)
- **输入参数**:
  - `model`: 输入扩散模型。
  - `clip`: 输入 CLIP 模型。
  - `lora_directory`: 输入你存放 LoRA 的自定义绝对路径文件夹，如 `E:\Lora_Backup` 或 `D:\SD_Webui\models\Lora`。
  - `lora_name`: 点击下拉菜单，选择该文件夹中的 LoRA 模型名称（支持子目录路径显示）。
  - `strength_model`: 模型端强度（默认 1.0）。
  - `strength_clip`: CLIP 端强度（默认 1.0）。

### 🖼️ PJ Image Preview/Save
- **输入参数**:
  - `images`: 图 A 输入。
  - `images_b` (可选): 图 B 输入。同时接入时激活滑动对比。
  - `save_image`: 切换按钮。**Preview Only**（仅预览，不存盘） / **Save Enabled**（保存至 output 目录）。
  - `filename_prefix`: 文件名前缀。

### 🧩 PJ Image Interactive Slicer & Reassembler (切片与还原闭环工作流)
```
【原图】
   │
   ▼
[PJ 图像交互式智能分割器]
   │ ├── 【原图】──────┐
   │ ├── 【切片数据】───┼───────────────────────────┐
   │ ├── 【块5_图片】───┼─► [重绘/超分/修脸节点]      │
   │                   │          │ (修改后的图)     │
   │                   │          ▼                  ▼
   └───────────────────┴► [ 基底原图 ]  [ 槽位1_图片 ] [ 切片数据 ]
                                    ▼
                         [PJ 图像切片原位还原器]
                                    │
                                    ▼
                             [ 还原后图像 ] (无缝羽化接合)
```
- **步骤 1**: 在 `PJ 图像交互式智能分割器` 中上传图片，用横切、竖切线切成所需网格（如九宫格）。设置 `重叠缝隙像素`（例如 16px）。
- **步骤 2**: 将需要修改的块（如 `块5_图片`）连接到下游的处理流程（如 KSampler、Face Detailer、Supir 等进行高清重绘）。
- **步骤 3**: 添加 `PJ 图像切片原位还原器`：
  - 将分割器的 `原图` 连入 `基底原图`（或上游原图直接连入）；
  - 将分割器的 `切片数据` 连入 `切片数据`；
  - 将修改后的图片连入 `槽位1_图片`，并将 `槽位1_目标块序号` 设为 `5`；
  - 若同时修改了多个块（例如第 2 块与第 8 块），分别连入 `槽位2`、`槽位3` 并填入对应序号，或通过 `批次替换图片` 批量送入；
  - 设置 `边缘羽化像素`（推荐 12~24px），节点会自动进行余弦平滑羽化融合，完美还原无痕大图！

---

## 📄 License

MIT License
