import os
import json
import hashlib
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageOps
import folder_paths

MAX_OUTPUT_BLOCKS = 30

class PJ_Image_Interactive_Slicer:
    """
    PJ 图像交互式智能分割器 (PJ Image Interactive Slicer)
    支持：
    1. 直接在节点上选择已有图片、点击按钮上传图片、或拖拽本地图片到节点；
    2. 兼容从上游节点接入“图像”输入；
    3. 交互式切刀拖放（横线、竖线），点击切线可重新调整移动，按 DEL/退格键删除；
    4. 实时统计总块数，自适应动态增减图像输出端口。
    """
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = []
        if os.path.exists(input_dir):
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
            files = folder_paths.filter_files_content_types(files, ["image"])
        files = sorted(files)

        return {
            "required": {
                "上传图片": (files, {"image_upload": True}),
                "重叠缝隙像素": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 512,
                    "step": 8,
                    "tooltip": "切块边缘是否保留重叠像素（用于拼接过渡）"
                }),
                "尺寸对齐倍数": ([
                    "自动对齐到 8 倍数 (推荐·生图/VAE无损标准)",
                    "自动对齐到 16 倍数 (视频/深度学习标准)",
                    "不对齐 (原始任意像素)"
                ], {
                    "default": "自动对齐到 8 倍数 (推荐·生图/VAE无损标准)",
                    "tooltip": "是否将切块尺寸吸附对齐为8或16的整数倍。杜绝VAE Encode强制裁切丢像素或报错"
                }),
                "切线数据": ("STRING", {
                    "default": "{\"horizontal\": [], \"vertical\": []}",
                    "multiline": False
                }),
            },
            "optional": {
                "图像": ("IMAGE", ),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE", "STRING") + tuple(["IMAGE"] * MAX_OUTPUT_BLOCKS)
    RETURN_NAMES = ("原图", "切片数据", "全部块_批次", "切片信息") + tuple([f"块{i}_图片" for i in range(1, MAX_OUTPUT_BLOCKS + 1)])
    FUNCTION = "slice_image"
    CATEGORY = "PJ_Nodes/Image"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(s, **kwargs):
        img_name = kwargs.get("上传图片", "")
        if img_name:
            try:
                image_path = folder_paths.get_annotated_filepath(img_name)
                if os.path.exists(image_path):
                    m = hashlib.sha256()
                    with open(image_path, 'rb') as f:
                        m.update(f.read())
                    return m.digest().hex()
            except Exception:
                pass
        return float("NaN")

    @classmethod
    def VALIDATE_INPUTS(s, **kwargs):
        if "图像" in kwargs and kwargs["图像"] is not None:
            return True
        img_name = kwargs.get("上传图片", "")
        if img_name:
            if not folder_paths.exists_annotated_filepath(img_name):
                return f"找不到指定的图片: {img_name}"
            return True
        return True

    def load_image_from_file(self, image_name):
        image_path = folder_paths.get_annotated_filepath(image_name)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"找不到指定的图片文件: {image_path}")
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        img_rgb = img.convert("RGB")
        img_np = np.array(img_rgb).astype(np.float32) / 255.0
        return torch.from_numpy(img_np)[None, ...]

    def slice_image(self, **kwargs):
        upstream_img = kwargs.get("图像", kwargs.get("image", None))
        image_name = kwargs.get("上传图片", kwargs.get("image_upload", ""))
        overlap = int(kwargs.get("重叠缝隙像素", kwargs.get("overlap", 0)))
        align_mode = str(kwargs.get("尺寸对齐倍数", "自动对齐到 8 倍数 (推荐·生图/VAE无损标准)"))
        align_step = 8 if "8" in align_mode else (16 if "16" in align_mode else 1)
        cut_data_raw = kwargs.get("切线数据", kwargs.get("cut_data", "{}"))
        unique_id = str(kwargs.get("unique_id", "default_slicer"))

        # 优先使用上游传入图像；若未传入则使用上传或选中的本地图像
        image = upstream_img
        if image is None or not isinstance(image, torch.Tensor) or image.shape[0] == 0:
            if image_name:
                try:
                    image = self.load_image_from_file(image_name)
                except Exception as e:
                    print(f"[PJ Image Slicer] 加载本地图片失败: {e}")

        if image is None or not isinstance(image, torch.Tensor) or image.shape[0] == 0:
            blank = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            dummy_outputs = [blank] * MAX_OUTPUT_BLOCKS
            return tuple([blank, "{}", blank, "错误: 未提供有效图片，请先上传图片或连接上游图像"] + dummy_outputs)

        # 1. 保存当前图像的一张临时缩略图供前端交互画布绘制
        preview_info = []
        try:
            first_img = image[0:1]
            h, w = first_img.shape[1], first_img.shape[2]
            max_side = max(h, w)
            scale = 1.0
            if max_side > 1024:
                scale = 1024.0 / max_side
            preview_h = max(1, int(round(h * scale)))
            preview_w = max(1, int(round(w * scale)))

            img_chw = first_img.permute(0, 3, 1, 2)
            resized = F.interpolate(img_chw, size=(preview_h, preview_w), mode="bilinear", align_corners=False)
            np_arr = np.clip(255.0 * resized.squeeze(0).permute(1, 2, 0).cpu().numpy(), 0, 255).astype(np.uint8)
            pil_img = Image.fromarray(np_arr)

            file_name = f"pj_slicer_preview_{unique_id}.png"
            full_path = os.path.join(self.output_dir, file_name)
            pil_img.save(full_path, compress_level=self.compress_level)
            preview_info = [{"filename": file_name, "subfolder": "", "type": "temp"}]
        except Exception as err:
            print(f"[PJ Image Slicer] 保存预览图失败: {err}")

        # 2. 解析切线比例数据
        h_ratios = []
        v_ratios = []
        try:
            if isinstance(cut_data_raw, str) and cut_data_raw.strip():
                data = json.loads(cut_data_raw)
                h_ratios = [float(r) for r in data.get("horizontal", []) if 0.0 < float(r) < 1.0]
                v_ratios = [float(r) for r in data.get("vertical", []) if 0.0 < float(r) < 1.0]
            elif isinstance(cut_data_raw, dict):
                h_ratios = [float(r) for r in cut_data_raw.get("horizontal", []) if 0.0 < float(r) < 1.0]
                v_ratios = [float(r) for r in cut_data_raw.get("vertical", []) if 0.0 < float(r) < 1.0]
        except Exception:
            h_ratios, v_ratios = [], []

        h_ratios = sorted(list(set(h_ratios)))
        v_ratios = sorted(list(set(v_ratios)))

        # 3. 计算真实像素切割边界
        orig_h = image.shape[1]
        orig_w = image.shape[2]

        y_splits = [0] + [int(round(r * orig_h)) for r in h_ratios] + [orig_h]
        x_splits = [0] + [int(round(r * orig_w)) for r in v_ratios] + [orig_w]

        for i in range(1, len(y_splits)):
            if y_splits[i] <= y_splits[i - 1]:
                y_splits[i] = min(orig_h, y_splits[i - 1] + 1)
        for i in range(1, len(x_splits)):
            if x_splits[i] <= x_splits[i - 1]:
                x_splits[i] = min(orig_w, x_splits[i - 1] + 1)

        num_rows = len(y_splits) - 1
        num_cols = len(x_splits) - 1
        total_blocks = num_rows * num_cols

        # 4. 逐块执行切片
        sliced_blocks = []
        blocks_meta = []
        block_info_lines = [
            f"【PJ 图像分割汇总信息】",
            f"原图分辨率: {orig_w} x {orig_h}",
            f"横切线数: {len(h_ratios)} 条 | 竖切线数: {len(v_ratios)} 条",
            f"总分割块数: {total_blocks} 块 ({num_rows} 行 x {num_cols} 列)",
            f"重叠缝隙: {overlap} px",
            "-" * 40
        ]

        block_idx = 1
        for r in range(num_rows):
            for c in range(num_cols):
                y_start = max(0, y_splits[r] - overlap)
                y_end = min(orig_h, y_splits[r + 1] + overlap)
                x_start = max(0, x_splits[c] - overlap)
                x_end = min(orig_w, x_splits[c + 1] + overlap)

                # 智能吸附对齐 8 或 16 的整数倍（消除 VAE 编码强制裁切与变形）
                if align_step > 1:
                    bw = x_end - x_start
                    bh = y_end - y_start
                    rem_w = bw % align_step
                    if rem_w != 0:
                        diff_w = align_step - rem_w
                        if x_end + diff_w <= orig_w:
                            x_end += diff_w
                        elif x_start - diff_w >= 0:
                            x_start -= diff_w
                        elif bw - rem_w >= align_step:
                            x_end -= rem_w

                    rem_h = bh % align_step
                    if rem_h != 0:
                        diff_h = align_step - rem_h
                        if y_end + diff_h <= orig_h:
                            y_end += diff_h
                        elif y_start - diff_h >= 0:
                            y_start -= diff_h
                        elif bh - rem_h >= align_step:
                            y_end -= rem_h

                block_tensor = image[:, y_start:y_end, x_start:x_end, :].clone()
                sliced_blocks.append(block_tensor)

                bw = x_end - x_start
                bh = y_end - y_start

                blocks_meta.append({
                    "block_idx": block_idx,
                    "row": r,
                    "col": c,
                    "x_start": x_start,
                    "x_end": x_end,
                    "y_start": y_start,
                    "y_end": y_end,
                    "width": bw,
                    "height": bh,
                    "inner_box": [x_splits[c], x_splits[c + 1], y_splits[r], y_splits[r + 1]]
                })

                block_info_lines.append(f"块 {block_idx}: 尺寸 {bw}x{bh} (行{r+1}, 列{c+1}) | 坐标: X[{x_start}:{x_end}], Y[{y_start}:{y_end}]")
                block_idx += 1

        # 5. 准备批次图像
        max_bw = max(b.shape[2] for b in sliced_blocks)
        max_bh = max(b.shape[1] for b in sliced_blocks)
        channels = image.shape[3]
        device = image.device
        dtype = image.dtype

        batch_list = []
        for b in sliced_blocks:
            _, bh, bw, _ = b.shape
            if bw == max_bw and bh == max_bh:
                batch_list.append(b)
            else:
                b_chw = b.permute(0, 3, 1, 2)
                resized = F.interpolate(b_chw, size=(max_bh, max_bw), mode="bilinear", align_corners=False)
                batch_list.append(resized.permute(0, 2, 3, 1))

        all_batch = torch.cat(batch_list, dim=0)

        # 构造用于原位还原的结构化切片坐标数据
        slice_meta = {
            "orig_w": orig_w,
            "orig_h": orig_h,
            "num_rows": num_rows,
            "num_cols": num_cols,
            "total_blocks": total_blocks,
            "overlap": overlap,
            "blocks": {str(b["block_idx"]): b for b in blocks_meta},
            "blocks_list": blocks_meta
        }
        slice_data_json = json.dumps(slice_meta, ensure_ascii=False)
        info_text = "\n".join(block_info_lines)

        # 6. 构造返回元组: [原图, 切片数据, 全部块_批次, 切片信息] + [块1..30]
        results = [image, slice_data_json, all_batch, info_text]
        for i in range(MAX_OUTPUT_BLOCKS):
            if i < len(sliced_blocks):
                results.append(sliced_blocks[i])
            else:
                results.append(sliced_blocks[0] if sliced_blocks else torch.zeros((1, 64, 64, 3)))

        return {
            "ui": {
                "pj_preview": preview_info,
                "total_blocks": [total_blocks],
                "rows": [num_rows],
                "cols": [num_cols]
            },
            "result": tuple(results)
        }
