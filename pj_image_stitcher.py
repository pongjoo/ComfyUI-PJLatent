import torch
import torch.nn.functional as F
import numpy as np
import hashlib

# 全局图像缓存字典，按 unique_id 隔离不同节点实例
# 数据结构: { unique_id: { slot_idx (int): { "tensor": torch.Tensor, "hash": str } } }
STITCHER_CACHE = {}

def compute_tensor_hash(tensor: torch.Tensor) -> str:
    """计算图像张量的内容哈希指纹"""
    if tensor is None:
        return ""
    arr = tensor.detach().cpu().contiguous().numpy()
    return hashlib.md5(arr.tobytes()).hexdigest()

def resize_tensor(img_tensor: torch.Tensor, target_w: int, target_h: int) -> torch.Tensor:
    """双线性插值调整图像张量尺寸 [1, H, W, C] -> [1, target_h, target_w, C]"""
    _, h, w, c = img_tensor.shape
    if w == target_w and h == target_h:
        return img_tensor
    img_chw = img_tensor.permute(0, 3, 1, 2)
    resized = F.interpolate(img_chw, size=(target_h, target_w), mode="bilinear", align_corners=False)
    return torch.clamp(resized.permute(0, 2, 3, 1), 0.0, 1.0)

def resize_and_fit_image(img_tensor: torch.Tensor, target_w: int, target_h: int, fit_mode: str, bg_color_val: list) -> torch.Tensor:
    """
    调整单张图像张量 [1, H, W, C] 适配目标网格单元尺寸 [1, target_h, target_w, C]
    """
    _, h, w, c = img_tensor.shape
    device = img_tensor.device
    dtype = img_tensor.dtype

    if w == target_w and h == target_h:
        return img_tensor

    img_chw = img_tensor.permute(0, 3, 1, 2)

    if fit_mode.startswith("拉伸"):
        resized = F.interpolate(img_chw, size=(target_h, target_w), mode="bilinear", align_corners=False)
        return torch.clamp(resized.permute(0, 2, 3, 1), 0.0, 1.0)

    elif fit_mode.startswith("保持比例"):
        scale = min(target_w / w, target_h / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))

        scaled = F.interpolate(img_chw, size=(new_h, new_w), mode="bilinear", align_corners=False)
        scaled_hwc = torch.clamp(scaled.permute(0, 2, 3, 1), 0.0, 1.0)

        bg_tensor = torch.tensor(bg_color_val[:c], dtype=dtype, device=device).view(1, 1, 1, c)
        canvas = bg_tensor.repeat(1, target_h, target_w, 1)

        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        canvas[:, y_offset:y_offset + new_h, x_offset:x_offset + new_w, :] = scaled_hwc
        return canvas

    else:
        # 等比裁剪并填充 (Cover 模式)
        scale = max(target_w / w, target_h / h)
        new_w = max(target_w, int(round(w * scale)))
        new_h = max(target_h, int(round(h * scale)))

        scaled = F.interpolate(img_chw, size=(new_h, new_w), mode="bilinear", align_corners=False)
        scaled_hwc = torch.clamp(scaled.permute(0, 2, 3, 1), 0.0, 1.0)

        y_offset = (new_h - target_h) // 2
        x_offset = (new_w - target_w) // 2
        cropped = scaled_hwc[:, y_offset:y_offset + target_h, x_offset:x_offset + target_w, :]
        return cropped


class PJ_Image_Stitcher:
    """
    PJ 图像智能记忆拼接器 (PJ Image Stitcher & Memory)
    默认提供 5 个初始槽位，支持前端根据连线动态自动增加槽位输入（最高支持 30 槽位）。
    具备槽位变动检测与多轮旧图记忆回读功能，支持上下/左右/宫格及自定义排版。
    """
    MAX_SLOTS = 30

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        optional_dict = {
            "自定义行数": ("INT", {"default": 2, "min": 1, "max": 20, "step": 1}),
            "自定义列数": ("INT", {"default": 2, "min": 1, "max": 20, "step": 1}),
        }

        # 动态槽位支持 1~30（前端默认展示前 5 个，连线时自动新增扩展）
        for i in range(1, s.MAX_SLOTS + 1):
            optional_dict[f"槽位{i}_图片"] = ("IMAGE", )

        optional_dict["批次图片输入"] = ("IMAGE", )

        return {
            "required": {
                "拼接模式": ([
                    "四宫格 (2x2)",
                    "左右横向拼接",
                    "上下纵向拼接",
                    "九宫格 (3x3)",
                    "自定义网格"
                ], {"default": "四宫格 (2x2)"}),
                "尺寸适配方式": ([
                    "等比裁剪并填充 (Cover)",
                    "保持比例并居中留白",
                    "拉伸至统一尺寸 (Stretch)"
                ], {"default": "等比裁剪并填充 (Cover)"}),
                "拼接边尺寸限制": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 16384,
                    "step": 8,
                    "tooltip": "0 为自动按输入图片中最长边智能对齐；大于 0 时强制设定拼接基准边尺寸（横拼限制高度，竖拼限制宽度，网格限制单元格最长边）"
                }),
                "拼缝间距": ("INT", {"default": 0, "min": 0, "max": 200, "step": 1}),
                "背景填充颜色": (["黑色", "白色", "灰色", "透明/暗色"], {"default": "黑色"}),
                "记忆缓存模式": ([
                    "正常记忆 (自动检测改动)",
                    "锁定记忆 (仅读取旧图)",
                    "清空重置 (强制覆盖)"
                ], {"default": "正常记忆 (自动检测改动)"}),
            },
            "optional": optional_dict,
            "hidden": {
                "unique_id": "UNIQUE_ID"
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("拼接大图", "记忆图批次")
    FUNCTION = "stitch"
    CATEGORY = "PJ_Nodes/Image"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    def stitch(self, **kwargs):
        unique_id = str(kwargs.get("unique_id", "default_node"))
        stitch_mode = kwargs.get("拼接模式", "四宫格 (2x2)")
        fit_mode = kwargs.get("尺寸适配方式", "等比裁剪并填充 (Cover)")
        size_limit = int(kwargs.get("拼接边尺寸限制", 0))
        spacing = int(kwargs.get("拼缝间距", 0))
        bg_color_name = kwargs.get("背景填充颜色", "黑色")
        cache_mode = kwargs.get("记忆缓存模式", "正常记忆 (自动检测改动)")

        custom_rows = int(kwargs.get("自定义行数", 2))
        custom_cols = int(kwargs.get("自定义列数", 2))

        # 颜色映射
        color_map = {
            "黑色": [0.0, 0.0, 0.0, 1.0],
            "白色": [1.0, 1.0, 1.0, 1.0],
            "灰色": [0.5, 0.5, 0.5, 1.0],
            "透明/暗色": [0.0, 0.0, 0.0, 0.0]
        }
        bg_color_val = color_map.get(bg_color_name, [0.0, 0.0, 0.0, 1.0])

        # 初始化/清空记忆缓存
        global STITCHER_CACHE
        if cache_mode.startswith("清空重置") or unique_id not in STITCHER_CACHE:
            STITCHER_CACHE[unique_id] = {}

        node_memory = STITCHER_CACHE[unique_id]

        # 1. 提取批次输入 (最高支持 30 张)
        batch_images = kwargs.get("批次图片输入", None)
        if batch_images is not None and isinstance(batch_images, torch.Tensor) and batch_images.shape[0] > 0:
            b_count = batch_images.shape[0]
            for b in range(min(b_count, self.MAX_SLOTS)):
                slot_key = b + 1
                img_slice = batch_images[b:b+1].detach()
                curr_hash = compute_tensor_hash(img_slice)
                
                if not cache_mode.startswith("锁定记忆"):
                    if slot_key not in node_memory or node_memory[slot_key]["hash"] != curr_hash:
                        node_memory[slot_key] = {
                            "tensor": img_slice,
                            "hash": curr_hash
                        }

        # 2. 遍历动态槽位 1~30，根据用户连线和指纹变动更新
        for i in range(1, self.MAX_SLOTS + 1):
            slot_input = kwargs.get(f"槽位{i}_图片", kwargs.get(f"image_{i}", None))
            if slot_input is not None and isinstance(slot_input, torch.Tensor) and slot_input.shape[0] > 0:
                img_slice = slot_input[0:1].detach()
                curr_hash = compute_tensor_hash(img_slice)

                if cache_mode.startswith("清空重置"):
                    node_memory[i] = {"tensor": img_slice, "hash": curr_hash}
                elif cache_mode.startswith("锁定记忆"):
                    if i not in node_memory:
                        node_memory[i] = {"tensor": img_slice, "hash": curr_hash}
                else:
                    if i not in node_memory or node_memory[i]["hash"] != curr_hash:
                        node_memory[i] = {"tensor": img_slice, "hash": curr_hash}

        # 3. 收集所有有效槽位图片
        active_slots = [i for i in range(1, self.MAX_SLOTS + 1) if i in node_memory and node_memory[i]["tensor"] is not None]
        if not active_slots:
            blank = torch.zeros((1, 512, 512, 3), dtype=torch.float32)
            return (blank, blank)

        channels = node_memory[active_slots[0]]["tensor"].shape[3]
        device = node_memory[active_slots[0]]["tensor"].device
        dtype = node_memory[active_slots[0]]["tensor"].dtype

        # -------------------------------------------------------------
        # 4. 左右横向拼接 (对齐边为 高度 Height)
        # -------------------------------------------------------------
        if stitch_mode.startswith("左右"):
            max_h = max(node_memory[i]["tensor"].shape[1] for i in active_slots)
            align_h = size_limit if size_limit > 0 else max_h

            scaled_list = []
            for i in sorted(active_slots):
                t = node_memory[i]["tensor"]
                _, cur_h, cur_w, _ = t.shape
                scale = align_h / cur_h
                new_w = max(1, int(round(cur_w * scale)))
                scaled_t = resize_tensor(t, new_w, align_h)
                scaled_list.append(scaled_t)

            total_canvas_w = sum(t.shape[2] for t in scaled_list) + (len(scaled_list) - 1) * spacing
            total_canvas_h = align_h

            bg_tensor = torch.tensor(bg_color_val[:channels], dtype=dtype, device=device).view(1, 1, 1, channels)
            canvas = bg_tensor.repeat(1, total_canvas_h, total_canvas_w, 1)

            curr_x = 0
            for t in scaled_list:
                tw = t.shape[2]
                canvas[:, :, curr_x:curr_x + tw, :] = t
                curr_x += tw + spacing

            batch_fitted = [resize_and_fit_image(t, scaled_list[0].shape[2], align_h, fit_mode, bg_color_val) for t in scaled_list]
            return (canvas, torch.cat(batch_fitted, dim=0))

        # -------------------------------------------------------------
        # 5. 上下纵向拼接 (对齐边为 宽度 Width)
        # -------------------------------------------------------------
        elif stitch_mode.startswith("上下"):
            max_w = max(node_memory[i]["tensor"].shape[2] for i in active_slots)
            align_w = size_limit if size_limit > 0 else max_w

            scaled_list = []
            for i in sorted(active_slots):
                t = node_memory[i]["tensor"]
                _, cur_h, cur_w, _ = t.shape
                scale = align_w / cur_w
                new_h = max(1, int(round(cur_h * scale)))
                scaled_t = resize_tensor(t, align_w, new_h)
                scaled_list.append(scaled_t)

            total_canvas_w = align_w
            total_canvas_h = sum(t.shape[1] for t in scaled_list) + (len(scaled_list) - 1) * spacing

            bg_tensor = torch.tensor(bg_color_val[:channels], dtype=dtype, device=device).view(1, 1, 1, channels)
            canvas = bg_tensor.repeat(1, total_canvas_h, total_canvas_w, 1)

            curr_y = 0
            for t in scaled_list:
                th = t.shape[1]
                canvas[:, curr_y:curr_y + th, :, :] = t
                curr_y += th + spacing

            batch_fitted = [resize_and_fit_image(t, align_w, scaled_list[0].shape[1], fit_mode, bg_color_val) for t in scaled_list]
            return (canvas, torch.cat(batch_fitted, dim=0))

        # -------------------------------------------------------------
        # 6. 网格拼接 (四宫格 2x2, 九宫格 3x3, 自定义网格)
        # -------------------------------------------------------------
        else:
            if stitch_mode.startswith("四宫格"):
                rows, cols = 2, 2
            elif stitch_mode.startswith("九宫格"):
                rows, cols = 3, 3
            else:
                rows = max(1, custom_rows)
                cols = max(1, custom_cols)

            total_cells = rows * cols

            base_w = max(node_memory[i]["tensor"].shape[2] for i in active_slots)
            base_h = max(node_memory[i]["tensor"].shape[1] for i in active_slots)

            if size_limit > 0:
                longest = max(base_w, base_h)
                scale = size_limit / longest
                cell_w = max(1, int(round(base_w * scale)))
                cell_h = max(1, int(round(base_h * scale)))
            else:
                cell_w = base_w
                cell_h = base_h

            cell_images = {}
            batch_list = []
            for i in range(1, total_cells + 1):
                if i in node_memory and node_memory[i]["tensor"] is not None:
                    fitted = resize_and_fit_image(node_memory[i]["tensor"], cell_w, cell_h, fit_mode, bg_color_val)
                    cell_images[i] = fitted
                    batch_list.append(fitted)

            if batch_list:
                batch_output = torch.cat(batch_list, dim=0)
            else:
                batch_output = torch.zeros((1, cell_h, cell_w, channels), dtype=dtype, device=device)

            total_canvas_w = cols * cell_w + (cols - 1) * spacing
            total_canvas_h = rows * cell_h + (rows - 1) * spacing

            bg_tensor = torch.tensor(bg_color_val[:channels], dtype=dtype, device=device).view(1, 1, 1, channels)
            canvas = bg_tensor.repeat(1, total_canvas_h, total_canvas_w, 1)

            for idx in range(total_cells):
                slot_num = idx + 1
                if slot_num in cell_images:
                    r = idx // cols
                    c = idx % cols
                    y1 = r * (cell_h + spacing)
                    y2 = y1 + cell_h
                    x1 = c * (cell_w + spacing)
                    x2 = x1 + cell_w
                    canvas[:, y1:y2, x1:x2, :] = cell_images[slot_num]

            return (canvas, batch_output)
