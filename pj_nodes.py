import torch
import os
import json
import re
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import folder_paths
try:
    from server import PromptServer
    from aiohttp import web
except ImportError:
    PromptServer = None
    web = None

try:
    from .pj_image_stitcher import PJ_Image_Stitcher
except (ImportError, ValueError):
    from pj_image_stitcher import PJ_Image_Stitcher

try:
    from .pj_image_slicer import PJ_Image_Interactive_Slicer
except (ImportError, ValueError):
    from pj_image_slicer import PJ_Image_Interactive_Slicer

try:
    from .pj_image_reassembler import PJ_Image_Slice_Reassembler
except (ImportError, ValueError):
    from pj_image_reassembler import PJ_Image_Slice_Reassembler

try:
    from .pj_wildcard_node import PJWildcardNode, PJWildcardParserNode, PJTextCombine
    from .pj_json_extractor import PJ_JSON_To_Prompt
except (ImportError, ValueError):
    from pj_wildcard_node import PJWildcardNode, PJWildcardParserNode, PJTextCombine
    from pj_json_extractor import PJ_JSON_To_Prompt

try:
    from .batch_video_loader import BatchVideoLoader, BatchVideoPathProvider
    from .batch_video_saver import BatchVideoSaver
    from .bridge_official_video import PJ_LoadVideoPathForOfficial
except (ImportError, ValueError):
    from batch_video_loader import BatchVideoLoader, BatchVideoPathProvider
    from batch_video_saver import BatchVideoSaver
    from bridge_official_video import PJ_LoadVideoPathForOfficial

class PJ_Image_Handler:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "图片A": ("IMAGE", ),
                "保存图片": ("BOOLEAN", {"default": False, "label_on": "开启保存", "label_off": "仅预览"}),
                "文件名前缀": ("STRING", {"default": "PJ_Image"}),
            },
            "optional": { "图片B_对比图": ("IMAGE", ) },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    OUTPUT_NODE = True
    CATEGORY = "PJ_Nodes/Image"

    def process(self, **kwargs):
        images = kwargs.get("图片A", kwargs.get("images"))
        save_image = kwargs.get("保存图片", kwargs.get("save_image", False))
        filename_prefix = kwargs.get("文件名前缀", kwargs.get("filename_prefix", "PJ_Image"))
        images_b = kwargs.get("图片B_对比图", kwargs.get("images_b", None))
        prompt = kwargs.get("prompt", None)
        extra_pnginfo = kwargs.get("extra_pnginfo", None)

        # 1. 准备元数据 (仅用于 A 图)
        metadata = PngInfo()
        if prompt is not None:
            metadata.add_text("prompt", json.dumps(prompt))
        if extra_pnginfo is not None:
            for x in extra_pnginfo:
                metadata.add_text(x, json.dumps(extra_pnginfo[x]))

        # 处理保存/预览的辅助函数
        def handle_batch(img_batch, tag, is_permanent_save):
            if img_batch is None: return []
            
            # 如果是永久保存，存到 output；否则存到 temp 供预览
            base_dir = self.output_dir if is_permanent_save else folder_paths.get_temp_directory()
            type_str = "output" if is_permanent_save else "temp"

            full_path, filename, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, base_dir, img_batch[0].shape[1], img_batch[0].shape[0])
            results = []
            
            for img in img_batch:
                i = 255. * img.cpu().numpy()
                pil_img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                
                suffix_str = f"_{tag}" if tag else ""
                file_name = f"{filename}_{counter:05}{suffix_str}_.png"
                
                # 只有永久保存时才加 metadata
                png_info = metadata if is_permanent_save else None
                pil_img.save(os.path.join(full_path, file_name), pnginfo=png_info, compress_level=self.compress_level)
                
                results.append({"filename": file_name, "subfolder": subfolder, "type": type_str})
                counter += 1
            return results

        # 始终生成预览数据 (存入 temp，供 JS 对比滑块显示)
        preview_a = handle_batch(images, "A", False)
        preview_b = handle_batch(images_b, "B", False) if images_b is not None else []

        # 根据用户要求：如果开启 save_image，只保存图片 A 到 output
        saved_images = []
        if save_image:
            saved_images = handle_batch(images, "", True)

        # 始终返回 images 键，以便 ComfyUI 的历史记录和资产管理器在两种模式下都能捕捉到图片
        ui_images = saved_images if (save_image and saved_images) else preview_a

        # 返回 UI 数据供 JS 使用
        return { "ui": { "a_images": preview_a, "b_images": preview_b, "images": ui_images } }

class PJ_Latent_Generator:
    def __init__(self): pass
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "宽高比": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"], {"default": "1:1"}),
                "最长边": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "批次大小": ("INT", {"default": 1, "min": 1, "max": 64}),
            }
        }
    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("潜空间", "宽度", "高度")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"
    def generate(self, **kwargs):
        aspect_ratio = kwargs.get("宽高比", kwargs.get("aspect_ratio", "1:1"))
        longest_side = kwargs.get("最长边", kwargs.get("longest_side", 1024))
        batch_size = kwargs.get("批次大小", kwargs.get("batch_size", 1))

        w_ratio, h_ratio = map(int, aspect_ratio.split(":"))
        width, height = (longest_side, int(longest_side*(h_ratio/w_ratio))) if w_ratio > h_ratio else (int(longest_side*(w_ratio/h_ratio)), longest_side) if h_ratio > w_ratio else (longest_side, longest_side)
        return ({"samples": torch.zeros([batch_size, 4, (height//8)*8//8, (width//8)*8//8])}, (width//8)*8, (height//8)*8)

class PJ_Video_Latent_Generator:
    def __init__(self): pass
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "宽高比": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"], {"default": "16:9"}),
                "最长边": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 16}),
                "视频时长_秒": ("INT", {"default": 5, "min": 1, "max": 60, "step": 1}),
                "批次大小": ("INT", {"default": 1, "min": 1, "max": 64}),
            }
        }
    RETURN_TYPES = ("LATENT", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("潜空间", "宽度", "高度", "帧数", "批次大小")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"
    def generate(self, **kwargs):
        aspect_ratio = kwargs.get("宽高比", kwargs.get("aspect_ratio", "16:9"))
        longest_side = kwargs.get("最长边", kwargs.get("longest_side", 1024))
        duration_seconds = kwargs.get("视频时长_秒", kwargs.get("duration_seconds", 5))
        batch_size = kwargs.get("批次大小", kwargs.get("batch_size", 1))

        ls = (longest_side + 8) // 16 * 16
        w, h = map(int, aspect_ratio.split(":"))
        width, height = (ls, int(ls*(h/w))) if w > h else (int(ls*(w/h)), ls) if h > w else (ls, ls)
        width, height, length = (width+8)//16*16, (height+8)//16*16, int(duration_seconds*16)+1
        return ({"samples": torch.zeros([batch_size, 16, (length-1)//4+1, height//8, width//8])}, width, height, length, batch_size)

TRANSLATOR_CACHE = {}
REQUIRED_FILES = [
    "config.json",
    "pytorch_model.bin",
    "source.spm",
    "target.spm",
    "tokenizer_config.json",
    "vocab.json"
]

def download_opus_model_if_missing(target_dir, repo_id="Helsinki-NLP/opus-mt-zh-en"):
    os.makedirs(target_dir, exist_ok=True)
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(target_dir, f))]
    if not missing:
        return target_dir

    print(f"\n[PJ Translator] 正在自动下载缺失的离线模型文件 ({len(missing)}个文件) [{repo_id}] 至: {target_dir} ...")
    try:
        from huggingface_hub import hf_hub_download
        for f in missing:
            print(f"[PJ Translator] 正在从 HuggingFace 下载必须文件: {f} ...")
            hf_hub_download(
                repo_id=repo_id,
                filename=f,
                local_dir=target_dir
            )
        print("[PJ Translator] 所有必须的离线模型文件已成功下载！\n")
    except Exception as e:
        print(f"[PJ Translator] huggingface_hub 自动下载产生异常 ({e})，尝试备用网络通道...")
        import urllib.request
        base_urls = [
            f"https://hf-mirror.com/{repo_id}/resolve/main/",
            f"https://huggingface.co/{repo_id}/resolve/main/"
        ]
        for f in missing:
            local_file_path = os.path.join(target_dir, f)
            downloaded = False
            for base_url in base_urls:
                url = base_url + f
                try:
                    print(f"[PJ Translator] 正在下载 {f} 来自 {base_url} ...")
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=60) as response, open(local_file_path, 'wb') as out_file:
                        out_file.write(response.read())
                    downloaded = True
                    break
                except Exception as err:
                    print(f"[PJ Translator] 从 {base_url} 下载 {f} 失败: {err}")
            if not downloaded:
                raise RuntimeError(f"[PJ Translator] 自动下载失败！请检查网络或手动下载必须文件至: {target_dir}")
    return target_dir

def get_translator_models():
    search_dirs = []
    if hasattr(folder_paths, "models_dir") and folder_paths.models_dir:
        search_dirs.append(folder_paths.models_dir)
        
    if hasattr(folder_paths, "folder_names_and_paths"):
        for k, v in folder_paths.folder_names_and_paths.items():
            if isinstance(v, tuple) and len(v) > 0 and isinstance(v[0], list):
                for p in v[0]:
                    if p and os.path.exists(p):
                        search_dirs.append(p)
                        
    aki_models = r"D:\ComfyUI-aki-v1.3\models"
    if os.path.exists(aki_models):
        search_dirs.append(aki_models)
        
    local_models = os.path.join(os.path.dirname(__file__), "models")
    search_paths_all = search_dirs + [local_models]

    unique_search_dirs = []
    for d in search_paths_all:
        norm = os.path.normpath(d)
        if norm not in unique_search_dirs and os.path.exists(norm):
            unique_search_dirs.append(norm)

    found = {}
    categories = ["prompt_generator", "LLM", "transformers", "opus-mt-zh-en", "NLP", "translation"]

    for b_dir in unique_search_dirs:
        prefix = "Aki" if "aki" in b_dir.lower() else "models"
        if os.path.exists(os.path.join(b_dir, "config.json")):
            name = os.path.basename(b_dir)
            if "opus" in name.lower() or "trans" in name.lower() or "zh" in name.lower():
                found[f"[{prefix}] {name}"] = b_dir
            
        try:
            for sub in os.listdir(b_dir):
                sub_path = os.path.join(b_dir, sub)
                if os.path.isdir(sub_path):
                    if os.path.exists(os.path.join(sub_path, "config.json")):
                        if "opus" in sub.lower() or "trans" in sub.lower() or "zh" in sub.lower():
                            found[f"[{prefix}] {sub}"] = sub_path
                    if sub.lower() in [c.lower() for c in categories]:
                        for sub2 in os.listdir(sub_path):
                            sub2_path = os.path.join(sub_path, sub2)
                            if os.path.isdir(sub2_path) and os.path.exists(os.path.join(sub2_path, "config.json")):
                                found[f"[{prefix}] {sub}/{sub2}"] = sub2_path
        except Exception:
            pass

    choices = ["Auto / opus-mt-zh-en (自动检测/自动下载)"] + list(found.keys())
    return choices, found

class PJ_Text_Translator:
    def __init__(self): pass

    @classmethod
    def INPUT_TYPES(s):
        choices, _ = get_translator_models()
        return {
            "required": {
                "文本内容": ("STRING", {"multiline": True, "default": "", "dynamicPrompts": False}),
                "翻译模式": (["智能双向检测 (Auto)", "中译英 (ZH -> EN)", "英译中 (EN -> ZH)"], {"default": "智能双向检测 (Auto)"}),
                "翻译模型": (choices, ),
                "运行设备": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "规范标点符号": ("BOOLEAN", {"default": True, "label_on": "规范化英文标点", "label_off": "保留原始标点"}),
                "常驻显存": ("BOOLEAN", {"default": True, "label_on": "保持常驻", "label_off": "用完即释放"}),
            },
            "optional": {
                "前缀文本": ("STRING", {"multiline": False, "default": "", "dynamicPrompts": False}),
                "后缀文本": ("STRING", {"multiline": False, "default": "", "dynamicPrompts": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("翻译结果", "原始文本")
    FUNCTION = "translate"
    CATEGORY = "PJ_Nodes/Text"

    def clean_text_punctuation(self, text):
        if not text: return ""
        replacements = {
            '，': ', ', '。': '. ', '！': '! ', '？': '? ',
            '；': '; ', '：': ': ', '“': '"', '”': '"',
            '（': ' (', '）': ') ', '【': ' [', '】': '] '
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r' ,', ',', text)
        return text.strip()

    def translate(self, **kwargs):
        text = kwargs.get("文本内容", kwargs.get("text", ""))
        mode = kwargs.get("翻译模式", kwargs.get("mode", "智能双向检测 (Auto)"))
        model = kwargs.get("翻译模型", kwargs.get("model", "Auto / opus-mt-zh-en (自动检测/自动下载)"))
        device = kwargs.get("运行设备", kwargs.get("device", "auto"))
        clean_punctuation = kwargs.get("规范标点符号", kwargs.get("clean_punctuation", True))
        keep_in_memory = kwargs.get("常驻显存", kwargs.get("keep_in_memory", True))
        prefix = kwargs.get("前缀文本", kwargs.get("prefix", ""))
        suffix = kwargs.get("后缀文本", kwargs.get("suffix", ""))

        original_text = text if text is not None else ""
        if not text or not text.strip():
            return ("", original_text)

        has_chinese = bool(re.search(r'[\u4e00-\u9fa5]', text))

        # 确定实际的翻译方向和模型仓库
        target_repo = "Helsinki-NLP/opus-mt-zh-en"
        folder_name = "opus-mt-zh-en"

        if "英译中" in mode or "EN -> ZH" in mode:
            target_repo = "Helsinki-NLP/opus-mt-en-zh"
            folder_name = "opus-mt-en-zh"
        elif "中译英" in mode or "ZH -> EN" in mode:
            target_repo = "Helsinki-NLP/opus-mt-zh-en"
            folder_name = "opus-mt-zh-en"
        else: # Auto
            if has_chinese:
                target_repo = "Helsinki-NLP/opus-mt-zh-en"
                folder_name = "opus-mt-zh-en"
            else:
                target_repo = "Helsinki-NLP/opus-mt-en-zh"
                folder_name = "opus-mt-en-zh"

        choices, found_map = get_translator_models()
        model_path = found_map.get(model, None)

        # 如果用户选的是 Auto 或者特定名称匹配上了
        if not model_path or "Auto" in model or not os.path.exists(model_path):
            search_dirs = [folder_paths.models_dir] if hasattr(folder_paths, "models_dir") else []
            aki_models = r"D:\ComfyUI-aki-v1.3\models"
            if os.path.exists(aki_models):
                search_dirs.append(aki_models)
            search_dirs.append(os.path.join(os.path.dirname(__file__), "models"))

            possible_paths = []
            for root_dir in search_dirs:
                possible_paths.extend([
                    os.path.join(root_dir, "prompt_generator", folder_name),
                    os.path.join(root_dir, "LLM", folder_name),
                    os.path.join(root_dir, "transformers", folder_name),
                    os.path.join(root_dir, folder_name),
                ])
            for p in possible_paths:
                if os.path.exists(os.path.join(p, "config.json")):
                    model_path = p
                    break

        if not model_path or not os.path.exists(os.path.join(model_path, "config.json")):
            target_dir = os.path.join(folder_paths.models_dir, "prompt_generator", folder_name)
            model_path = download_opus_model_if_missing(target_dir, repo_id=target_repo)

        if device == "auto":
            target_device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            target_device = device

        global TRANSLATOR_CACHE
        cache_key = (model_path, target_device)

        if cache_key in TRANSLATOR_CACHE:
            tokenizer, net = TRANSLATOR_CACHE[cache_key]
            if not keep_in_memory:
                del TRANSLATOR_CACHE[cache_key]
        else:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            net = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True)
            net.to(target_device)
            net.eval()
            if keep_in_memory:
                TRANSLATOR_CACHE[cache_key] = (tokenizer, net)

        lines = text.split('\n')
        translated_lines = []
        for line in lines:
            if not line.strip():
                translated_lines.append("")
                continue
            inputs = tokenizer(line, return_tensors="pt", padding=True, truncation=True).to(target_device)
            with torch.no_grad():
                outputs = net.generate(**inputs)
            out_str = tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated_lines.append(out_str)

        final_result = '\n'.join(translated_lines)
        if clean_punctuation and folder_name == "opus-mt-zh-en":
            final_result = self.clean_text_punctuation(final_result)

        # 拼接前缀和后缀
        final_parts = [p.strip() for p in [prefix, final_result, suffix] if p and p.strip()]
        final_result = ", ".join(final_parts) if folder_name == "opus-mt-zh-en" else "".join(final_parts)

        if not keep_in_memory and cache_key not in TRANSLATOR_CACHE:
            del net
            del tokenizer
            if target_device == "cuda":
                torch.cuda.empty_cache()

        return (final_result, original_text)

# API 路由：用于动态列出自定义文件夹中的 LoRA 模型文件
if PromptServer is not None and getattr(PromptServer, "instance", None) is not None:
    @PromptServer.instance.routes.get("/pj/list_loras")
    async def list_loras(request):
        folder = request.query.get("folder", "").strip()
        if not folder or not os.path.isdir(folder):
            return web.json_response({"files": []})
        try:
            files = []
            for root, dirs, filenames in os.walk(folder):
                for f in filenames:
                    if f.endswith(('.safetensors', '.ckpt', '.pt')):
                        rel_path = os.path.relpath(os.path.join(root, f), folder)
                        rel_path = rel_path.replace("\\", "/")
                        files.append(rel_path)
            files.sort()
            return web.json_response({"files": files})
        except Exception as e:
            return web.json_response({"error": str(e), "files": []})

class PJ_Lora_Loader:
    def __init__(self):
        self.loaded_lora = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "模型": ("MODEL",),
                "LoRA文件夹路径": ("STRING", {"default": "输入你存放LoRA模型的文件夹路径，例如: E:\\models\\loras"}),
                "LoRA文件": ([""],),
                "模型权重": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.01}),
                "CLIP权重": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.01}),
            },
            "optional": {
                "CLIP": ("CLIP",),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("模型", "CLIP")
    FUNCTION = "load_lora"
    CATEGORY = "PJ_Nodes/Model"

    @classmethod
    def VALIDATE_INPUTS(s, **kwargs):
        lora_name = kwargs.get("LoRA文件", kwargs.get("lora_name", ""))
        lora_directory = kwargs.get("LoRA文件夹路径", kwargs.get("lora_directory", ""))
        if not lora_name or lora_name == "":
            return True
        lora_path = os.path.join(lora_directory, lora_name)
        if not os.path.exists(lora_path):
            return f"找不到指定的LoRA模型文件: {lora_path}"
        return True

    def load_lora(self, **kwargs):
        model = kwargs.get("模型", kwargs.get("model"))
        clip = kwargs.get("CLIP", kwargs.get("clip", None))
        lora_directory = kwargs.get("LoRA文件夹路径", kwargs.get("lora_directory", ""))
        lora_name = kwargs.get("LoRA文件", kwargs.get("lora_name", ""))
        strength_model = kwargs.get("模型权重", kwargs.get("strength_model", 1.0))
        strength_clip = kwargs.get("CLIP权重", kwargs.get("strength_clip", 1.0))

        if strength_model == 0 and strength_clip == 0:
            return (model, clip)

        if not lora_name or lora_name == "":
            return (model, clip)

        lora_path = os.path.join(lora_directory, lora_name)
        if not os.path.exists(lora_path):
            raise FileNotFoundError(f"找不到指定的LoRA模型文件: {lora_path}")

        lora = None
        lora_metadata = None
        if self.loaded_lora is not None:
            if self.loaded_lora[0] == lora_path:
                lora = self.loaded_lora[1]
                lora_metadata = self.loaded_lora[2] if len(self.loaded_lora) > 2 else None
            else:
                self.loaded_lora = None

        if lora is None:
            import comfy.utils
            lora, lora_metadata = comfy.utils.load_torch_file(lora_path, safe_load=True, return_metadata=True)
            self.loaded_lora = (lora_path, lora, lora_metadata)

        import comfy.sd
        model_lora, clip_lora = comfy.sd.load_lora_for_models(model, clip, lora, strength_model, strength_clip, lora_metadata=lora_metadata)
        return (model_lora, clip_lora)

NODE_CLASS_MAPPINGS = { 
    "PJ_Latent_Generator": PJ_Latent_Generator, 
    "PJ_Video_Latent_Generator": PJ_Video_Latent_Generator, 
    "PJ_Image_Handler": PJ_Image_Handler,
    "PJ_Text_Translator": PJ_Text_Translator,
    "PJ_Image_Stitcher": PJ_Image_Stitcher,
    "PJ_Image_Interactive_Slicer": PJ_Image_Interactive_Slicer,
    "PJ_Image_Slice_Reassembler": PJ_Image_Slice_Reassembler,
    "PJ_Lora_Loader": PJ_Lora_Loader,
    # PJ Text Nodes
    "PJWildcardNode": PJWildcardNode,
    "PJWildcardParserNode": PJWildcardParserNode,
    "PJTextCombine": PJTextCombine,
    "PJ_JSON_To_Prompt": PJ_JSON_To_Prompt,
    # PJ Video Nodes
    "BatchVideoLoader": BatchVideoLoader,
    "BatchVideoPathProvider": BatchVideoPathProvider,
    "BatchVideoSaver": BatchVideoSaver,
    "PJ_LoadVideoPathForOfficial": PJ_LoadVideoPathForOfficial
}
NODE_DISPLAY_NAME_MAPPINGS = { 
    "PJ_Latent_Generator": "PJ Latent 图像潜空间生成器", 
    "PJ_Video_Latent_Generator": "PJ Video 视频潜空间生成器", 
    "PJ_Image_Handler": "PJ 图像预览与保存 (双图对比)",
    "PJ_Text_Translator": "PJ 智能双向文本翻译器 (中英互译)",
    "PJ_Image_Stitcher": "PJ 图像智能记忆拼接器",
    "PJ_Image_Interactive_Slicer": "PJ 图像交互式智能分割器",
    "PJ_Image_Slice_Reassembler": "PJ 图像切片原位还原器",
    "PJ_Lora_Loader": "PJ LoRA 自定义路径加载器",
    # PJ Text Nodes
    "PJWildcardNode": "PJ-通配符单选",
    "PJWildcardParserNode": "PJ-通配符大师",
    "PJTextCombine": "PJ-动态文本拼接",
    "PJ_JSON_To_Prompt": "PJ-JSON提示词提取器 (Gemma 4适配)",
    # PJ Video Nodes
    "BatchVideoLoader": "PJ-视频加载 (Batch Video Loader)",
    "BatchVideoPathProvider": "PJ-视频路径加载 (Batch Video Path)",
    "BatchVideoSaver": "PJ-视频与标签保存 (Batch Video Saver)",
    "PJ_LoadVideoPathForOfficial": "PJ-官方Gemini格式转换 (Bridge to Official)"
}

WEB_DIRECTORY = "./js"
