# ComfyUI-PJLatent

A powerful and convenient custom node suite for ComfyUI, providing aspect-ratio-based Latent generation, video Latent creation, interactive image comparison/saving, and offline Chinese-to-English translation.

功能强大的 ComfyUI 自定义节点套件，提供基于长边与高宽比的空 Latent 生成、视频 Latent 生成、交互式双图对比预览/保存、以及智能离线中文转英文翻译节点。

---

## 🌟 Features / 功能特性

### 1. PJ Text Translator (ZH -> EN) | 离线中文转英文翻译节点
- **纯离线/自动下载 (Offline / Auto Download)**: 基于 `Helsinki-NLP/opus-mt-zh-en` 模型。自动检测本地模型文件；若本地未找到，会自动从 HuggingFace/镜像站定向下载仅需的 6 个核心模型文件。
- **全路模型智能扫描 (Smart Multi-Path Scan)**: 自动扫描便携版及 Aki 整合包等多套 `models` 路径（如 `prompt_generator` / `LLM` / `transformers`）。
- **多行提示词分行处理 (Multi-line Support)**: 完美支持带换行符的长文本与多行 Prompt 逐行精准翻译。
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

### 📄 PJ Text Translator (ZH -> EN)
- **输入参数**:
  - `text`: 输入需要翻译的中文文本或提示词（支持多行）。
  - `model`: 默认 `Auto / opus-mt-zh-en (自动检测/自动下载)`。也可选择扫描到的具体本地模型目录。
  - `device`: `auto`（优先 CUDA 显卡加速）、`cuda` 或 `cpu`。
  - `keep_in_memory`: 是否驻留显存/内存（默认开启）。
- **离线模型手动存放路径（可选）**:
  若手动下载，请将解压后的 6 个核心文件（`config.json`, `pytorch_model.bin`, `source.spm`, `target.spm`, `tokenizer_config.json`, `vocab.json`）放入以下任意路径：
  - 便携版: `ComfyUI/models/prompt_generator/opus-mt-zh-en/`
  - Aki整合包: `D:/ComfyUI-aki-v1.3/models/prompt_generator/opus-mt-zh-en/`

### 🖼️ PJ Image Preview/Save
- **输入参数**:
  - `images`: 图 A 输入。
  - `images_b` (可选): 图 B 输入。同时接入时激活滑动对比。
  - `save_image`: 切换按钮。**Preview Only**（仅预览，不存盘） / **Save Enabled**（保存至 output 目录）。
  - `filename_prefix`: 文件名前缀。

---

## 📄 License

MIT License
