import os
import json
import re
import torch
import torch.nn.functional as F
import numpy as np

def parse_index_string(s: str, total_blocks: int = 30) -> list:
    """
    解析用户输入的块序号字符串，支持:
    - '5'
    - '2, 5, 8'
    - '1-3, 5'
    - '全部', 'all'
    """
    if not s or not isinstance(s, str):
        return []
    s = s.strip()
    if not s:
        return []

    if s in ["全部", "all", "ALL", "All", "*"]:
        return list(range(1, total_blocks + 1))

    indices = []
    # 替换中文逗号、分号为英文逗号
    s_clean = s.replace("，", ",").replace("；", ";").replace(";", ",")
    tokens = [t.strip() for t in re.split(r"[\s,]+", s_clean) if t.strip()]

    for token in tokens:
        # 支持区间格式，如 1-3 或 1~3
        range_match = re.match(r"^(\d+)\s*[-~]\s*(\d+)$", token)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start <= end:
                indices.extend(list(range(start, end + 1)))
            else:
                indices.extend(list(range(end, start + 1)))
        elif token.isdigit():
            indices.append(int(token))

    # 保持顺序但去除连续重复项
    seen = set()
    result = []
    for idx in indices:
        if idx not in seen and 1 <= idx <= total_blocks:
            seen.add(idx)
            result.append(idx)
    return result


class PJ_Image_Slice_Reassembler:
    """
    PJ 图像切片原位还原器 (PJ Image Slice Reassembler)
    搭配 PJ 图像交互式智能分割器 使用。
    功能：
    1. 接收分割器生成的结构化【切片数据】；
    2. 支持单块或多块原位替换（提供 8 个独立槽位 + 批次批量输入）；
    3. 支持边缘羽化过渡（余弦平滑S曲线，自动避开画幅外边框，实现无缝无痕拼接）；
    4. 支持分辨率自适应（单块超分高清重绘后可自动缩回原图分辨率，或整图等比无损放大）；
    5. 输出还原后高品质完整图像、替换区域遮罩 MASK 以及详细还原报告。
    """
    MAX_SLOTS = 8

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        optional_dict = {
            "基底原图": ("IMAGE", ),
            "切片数据": ("STRING", {
                "forceInput": True,
                "multiline": False,
                "tooltip": "请连接 PJ 图像交互式智能分割器 的【切片数据】输出端口"
            }),
            "批次替换图片": ("IMAGE", ),
            "批次对应块序号": ("STRING", {
                "default": "",
                "tooltip": "指定批次替换图片对应的原图切块序号，如 '5'、'2,5,8'、'1-3,5' 或 '全部'。图片将按顺序对号入座"
            }),
        }

        # 直连端口：支持最高 30 块，前端将随切片数据动态自适应展示实际块数
        for i in range(1, 31):
            optional_dict[f"块{i}_图片"] = ("IMAGE", )

        return {
            "required": {
                "边缘羽化像素": ("INT", {
                    "default": 16,
                    "min": 0,
                    "max": 256,
                    "step": 2,
                    "tooltip": "切块与周围图像拼接边缘的渐变羽化宽度（像素）。0为硬边缘直接贴入，建议12~32消除缝隙接痕"
                }),
                "分辨率处理模式": ([
                    "缩放替换块至原切片尺寸 (维持基底分辨率)",
                    "整图等比高清放大 (自适应替换块最高倍率)",
                    "强制拉伸切片区域"
                ], {
                    "default": "缩放替换块至原切片尺寸 (维持基底分辨率)"
                }),
            },
            "optional": optional_dict
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("还原后图像", "替换区域遮罩", "还原汇总信息")
    FUNCTION = "reassemble_image"
    CATEGORY = "PJ_Nodes/Image"

    def reassemble_image(self, **kwargs):
        cut_data_raw = kwargs.get("切片数据", "")
        feather_px = int(kwargs.get("边缘羽化像素", 16))
        res_mode = kwargs.get("分辨率处理模式", "缩放替换块至原切片尺寸 (维持基底分辨率)")
        base_img = kwargs.get("基底原图", None)

        # 1. 解析切片元数据
        if not cut_data_raw or not isinstance(cut_data_raw, str) or not cut_data_raw.strip():
            err_msg = "错误: 未接收到有效【切片数据】，请确认已将 PJ 图像交互式智能分割器 的【切片数据】端口连接至本节点。"
            print(f"[PJ Image Reassembler] {err_msg}")
            dummy_img = base_img if (base_img is not None and isinstance(base_img, torch.Tensor)) else torch.zeros((1, 512, 512, 3))
            dummy_mask = torch.zeros((dummy_img.shape[0], dummy_img.shape[1], dummy_img.shape[2]))
            return (dummy_img, dummy_mask, err_msg)

        try:
            meta = json.loads(cut_data_raw)
        except Exception as e:
            err_msg = f"错误: 解析切片元数据 JSON 失败: {e}"
            dummy_img = base_img if (base_img is not None and isinstance(base_img, torch.Tensor)) else torch.zeros((1, 512, 512, 3))
            dummy_mask = torch.zeros((dummy_img.shape[0], dummy_img.shape[1], dummy_img.shape[2]))
            return (dummy_img, dummy_mask, err_msg)

        orig_w = int(meta.get("orig_w", 512))
        orig_h = int(meta.get("orig_h", 512))
        overlap = int(meta.get("overlap", 0))
        num_rows = int(meta.get("num_rows", 1))
        num_cols = int(meta.get("num_cols", 1))
        total_blocks = int(meta.get("total_blocks", num_rows * num_cols))

        blocks_meta = meta.get("blocks", {})
        if isinstance(blocks_meta, list):
            blocks_meta = {str(b["block_idx"]): b for b in blocks_meta}

        # 2. 收集需要替换的块图片
        # 映射: target_block_idx (int) -> (img_tensor [1, H, W, C], source_desc)
        replacements = {}

        # A. 解析批次替换图片
        batch_img = kwargs.get("批次替换图片", None)
        batch_indices_str = kwargs.get("批次对应块序号", "")
        if batch_img is not None and isinstance(batch_img, torch.Tensor) and batch_img.shape[0] > 0:
            target_indices = parse_index_string(batch_indices_str, total_blocks)
            if not target_indices:
                # 默认按 1, 2, 3... 对应
                target_indices = list(range(1, min(batch_img.shape[0], total_blocks) + 1))

            for i, blk_idx in enumerate(target_indices):
                if i < batch_img.shape[0]:
                    replacements[blk_idx] = (batch_img[i:i + 1], f"批次图片[{i + 1}]")

        # B. 解析直连块输入 (块1_图片 ~ 块30_图片，改了哪块就直连哪块)
        for i in range(1, 31):
            blk_img = kwargs.get(f"块{i}_图片", None)
            if blk_img is not None and isinstance(blk_img, torch.Tensor) and blk_img.shape[0] > 0:
                replacements[i] = (blk_img[0:1], f"【块{i}_图片】")

        if not replacements:
            warn_msg = "提示: 未连接任何替换块图片（槽位或批次），直接输出基底原图。"
            print(f"[PJ Image Reassembler] {warn_msg}")
            dummy_img = base_img if (base_img is not None and isinstance(base_img, torch.Tensor)) else torch.zeros((1, orig_h, orig_w, 3))
            dummy_mask = torch.zeros((dummy_img.shape[0], dummy_img.shape[1], dummy_img.shape[2]))
            return (dummy_img, dummy_mask, warn_msg)

        # 3. 初始化基底画布
        base_provided = (base_img is not None and isinstance(base_img, torch.Tensor) and base_img.shape[0] > 0)
        if base_provided:
            canvas = base_img.clone()
        else:
            # 未连接基底原图时，按切片元数据的原图尺寸创建全黑画布
            canvas = torch.zeros((1, orig_h, orig_w, 3), dtype=torch.float32)

        cur_b, cur_h, cur_w, cur_c = canvas.shape
        device = canvas.device
        dtype = canvas.dtype

        # 4. 判断分辨率处理模式：整图等比高清放大
        global_scale = 1.0
        if res_mode.startswith("整图等比高清放大"):
            # 探测所有替换块的最大放大倍数
            max_scale = 1.0
            for blk_idx, (r_img, _) in replacements.items():
                b_info = blocks_meta.get(str(blk_idx))
                if b_info:
                    orig_bw = b_info.get("width", b_info["x_end"] - b_info["x_start"])
                    orig_bh = b_info.get("height", b_info["y_end"] - b_info["y_start"])
                    if orig_bw > 0 and orig_bh > 0:
                        sw = r_img.shape[2] / orig_bw
                        sh = r_img.shape[1] / orig_bh
                        block_scale = max(sw, sh)
                        if block_scale > max_scale:
                            max_scale = block_scale

            if max_scale > 1.05:
                global_scale = max_scale
                target_canvas_w = int(round(cur_w * global_scale))
                target_canvas_h = int(round(cur_h * global_scale))
                canvas_chw = canvas.permute(0, 3, 1, 2)
                upscaled_canvas = F.interpolate(canvas_chw, size=(target_canvas_h, target_canvas_w), mode="bicubic", align_corners=False)
                canvas = torch.clamp(upscaled_canvas.permute(0, 2, 3, 1), 0.0, 1.0)
                cur_h, cur_w = target_canvas_h, target_canvas_w
                feather_px = int(round(feather_px * global_scale))

        # 5. 如果当前基底与元数据原图尺寸不一致（例如基底外部已做过缩放），自适应换算比例
        coord_scale_x = cur_w / orig_w
        coord_scale_y = cur_h / orig_h

        # 6. 逐块执行原位精准覆盖与羽化融合
        mask_canvas = torch.zeros((cur_b, cur_h, cur_w), dtype=dtype, device=device)
        replaced_logs = []

        for blk_idx in sorted(replacements.keys()):
            if str(blk_idx) not in blocks_meta:
                replaced_logs.append(f"• 块 {blk_idx}: 忽略 (切片数据中未找到块 {blk_idx} 的坐标信息)")
                continue

            b_info = blocks_meta[str(blk_idx)]
            r_img, source_desc = replacements[blk_idx]

            # 映射目标贴合像素坐标
            tgt_xs = max(0, int(round(b_info["x_start"] * coord_scale_x)))
            tgt_xe = min(cur_w, int(round(b_info["x_end"] * coord_scale_x)))
            tgt_ys = max(0, int(round(b_info["y_start"] * coord_scale_y)))
            tgt_ye = min(cur_h, int(round(b_info["y_end"] * coord_scale_y)))

            target_w = tgt_xe - tgt_xs
            target_h = tgt_ye - tgt_ys

            if target_w <= 0 or target_h <= 0:
                continue

            # 调整替换图片尺寸
            _, r_h, r_w, r_c = r_img.shape
            r_tensor = r_img.to(device=device, dtype=dtype)
            if r_w != target_w or r_h != target_h:
                r_chw = r_tensor.permute(0, 3, 1, 2)
                interp_mode = "bilinear" if res_mode.startswith("强制拉伸") else "bicubic"
                resized_r = F.interpolate(r_chw, size=(target_h, target_w), mode=interp_mode, align_corners=False)
                r_tensor = torch.clamp(resized_r.permute(0, 2, 3, 1), 0.0, 1.0)

            # 7. 计算 2D 余弦 S 曲线边缘羽化遮罩
            fy = min(feather_px, target_h // 2)
            fx = min(feather_px, target_w // 2)

            vy = np.ones((target_h,), dtype=np.float32)
            # 只有当切片不贴在全图外边界时，才对该方向做渐变融合；全图边缘保持满打满贴
            if tgt_ys > 0 and fy > 0:
                vy[:fy] = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, fy, endpoint=False))
            if tgt_ye < cur_h and fy > 0:
                vy[-fy:] = 0.5 + 0.5 * np.cos(np.pi * np.linspace(0, 1, fy, endpoint=False))

            hx = np.ones((target_w,), dtype=np.float32)
            if tgt_xs > 0 and fx > 0:
                hx[:fx] = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, fx, endpoint=False))
            if tgt_xe < cur_w and fx > 0:
                hx[-fx:] = 0.5 + 0.5 * np.cos(np.pi * np.linspace(0, 1, fx, endpoint=False))

            mask_2d_np = vy[:, None] * hx[None, :]
            mask_2d = torch.from_numpy(mask_2d_np).to(device=device, dtype=dtype) # [target_h, target_w]
            mask_4d = mask_2d.unsqueeze(0).unsqueeze(-1) # [1, target_h, target_w, 1]

            # 通道与批次自适应对齐 (防止如 Inpaint/抠图/去底等上游节点输出 RGBA 4通道导致尺寸不匹配报错)
            canvas_c = canvas.shape[-1]
            r_c = r_tensor.shape[-1]
            if r_c != canvas_c:
                if canvas_c == 3 and r_c == 4:
                    # RGBA -> RGB: 提取 Alpha 透明度通道与边缘羽化遮罩相乘融合，完美保留半透明区域
                    alpha_channel = r_tensor[..., 3:4]
                    mask_4d = mask_4d * alpha_channel
                    r_tensor = r_tensor[..., :3]
                elif canvas_c == 4 and r_c == 3:
                    # RGB -> RGBA: 补充全不透明 Alpha
                    alpha_fill = torch.ones_like(r_tensor[..., :1])
                    r_tensor = torch.cat([r_tensor, alpha_fill], dim=-1)
                elif r_c == 1:
                    r_tensor = r_tensor.repeat(1, 1, 1, canvas_c)
                elif canvas_c == 1:
                    r_tensor = r_tensor[..., :1]
                elif r_c > canvas_c:
                    r_tensor = r_tensor[..., :canvas_c]
                elif r_c < canvas_c:
                    r_tensor = r_tensor.repeat(1, 1, 1, canvas_c)

            if r_tensor.shape[0] != cur_b and r_tensor.shape[0] == 1:
                r_tensor = r_tensor.repeat(cur_b, 1, 1, 1)

            # 执行混合融合
            sub_canvas = canvas[:, tgt_ys:tgt_ye, tgt_xs:tgt_xe, :]
            blended = sub_canvas * (1.0 - mask_4d) + r_tensor * mask_4d
            canvas[:, tgt_ys:tgt_ye, tgt_xs:tgt_xe, :] = blended

            # 累计更新全图修改区域遮罩
            mask_canvas[:, tgt_ys:tgt_ye, tgt_xs:tgt_xe] = torch.maximum(
                mask_canvas[:, tgt_ys:tgt_ye, tgt_xs:tgt_xe],
                (mask_4d[..., 0] if mask_4d.shape[-1] == 1 else mask_4d.mean(dim=-1)).squeeze(0)
            )

            replaced_logs.append(
                f"• 块 {blk_idx} (来自 {source_desc}): 坐标 X[{tgt_xs}:{tgt_xe}], Y[{tgt_ys}:{tgt_ye}] "
                f"| 原始切块尺寸 {b_info.get('width', target_w)}x{b_info.get('height', target_h)}, "
                f"替换输入尺寸 {r_w}x{r_h} -> 贴合尺寸 {target_w}x{target_h}"
            )

        # 8. 生成结构化报告
        unreplaced_indices = [i for i in range(1, total_blocks + 1) if i not in replacements]
        unreplaced_str = ", ".join(str(i) for i in unreplaced_indices) if unreplaced_indices else "无 (所有切块全部被替换)"

        summary_lines = [
            "【PJ 图像切片原位还原报告】",
            f"最终图像分辨率: {cur_w} x {cur_h} (处理模式: {res_mode})",
            f"原切片规格: {orig_w} x {orig_h} | 总块数: {total_blocks} 块 ({num_rows}行 x {num_cols}列) | 重叠缝隙: {overlap} px",
            f"边缘羽化过渡: {feather_px} px (平滑余弦过渡)",
            f"基底来源: {'用户连接基底原图' if base_provided else '自动创建对应尺寸底板'}",
            f"成功还原块数: {len(replacements)} 块",
            "-" * 40,
            "【替换块详情】"
        ]
        summary_lines.extend(replaced_logs)
        summary_lines.append("-" * 40)
        summary_lines.append(f"未修改原图保留块: {unreplaced_str}")

        summary_text = "\n".join(summary_lines)

        return (canvas, mask_canvas, summary_text)
