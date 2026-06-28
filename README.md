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

### 🖼️ PJ Image Preview/Save
- **输入参数**:
  - `images`: 图 A 输入。
  - `images_b` (可选): 图 B 输入。同时接入时激活滑动对比。
  - `save_image`: 切换按钮。**Preview Only**（仅预览，不存盘） / **Save Enabled**（保存至 output 目录）。
  - `filename_prefix`: 文件名前缀。

---

## 📄 License

MIT License
