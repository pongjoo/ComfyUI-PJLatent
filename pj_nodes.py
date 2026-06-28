import torch
import os
import json
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import folder_paths

class PJ_Image_Handler:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", ),
                "save_image": ("BOOLEAN", {"default": False, "label_on": "Save Enabled", "label_off": "Preview Only"}),
                "filename_prefix": ("STRING", {"default": "PJ_Image"}),
            },
            "optional": { "images_b": ("IMAGE", ) },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    OUTPUT_NODE = True
    CATEGORY = "PJ_Nodes/Image"

    def process(self, images, save_image, filename_prefix="PJ_Image", images_b=None, prompt=None, extra_pnginfo=None):
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

            # 修复：get_save_image_path 的参数应为 (prefix, dir, width, height)
            # img_batch[0].shape 为 [H, W, C]，所以 shape[1] 是宽，shape[0] 是高
            full_path, filename, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, base_dir, img_batch[0].shape[1], img_batch[0].shape[0])
            results = []
            
            for img in img_batch:
                i = 255. * img.cpu().numpy()
                pil_img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                
                # 修复：ComfyUI 的 get_save_image_path 逻辑要求文件名以 "_{数字}_.png" 结尾才能正确识别并递增 Counter
                # 否则每次运行 get_save_image_path 都会返回 1
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
            saved_images = handle_batch(images, "", True) # A图作为主图保存，不带额外 Tag

        # 始终返回 images 键，以便 ComfyUI 的历史记录和资产管理器在两种模式下都能捕捉到图片
        ui_images = saved_images if (save_image and saved_images) else preview_a

        # 返回 UI 数据供 JS 使用
        return { "ui": { "a_images": preview_a, "b_images": preview_b, "images": ui_images } }

# 移除了 PJ_Image_Comparer 类，功能已合并

class PJ_Latent_Generator:
    def __init__(self): pass
    @classmethod
    def INPUT_TYPES(s): return {"required": {"aspect_ratio": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"],), "longest_side": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}), "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),}}
    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"
    def generate(self, aspect_ratio, longest_side, batch_size):
        w_ratio, h_ratio = map(int, aspect_ratio.split(":"))
        width, height = (longest_side, int(longest_side*(h_ratio/w_ratio))) if w_ratio > h_ratio else (int(longest_side*(w_ratio/h_ratio)), longest_side) if h_ratio > w_ratio else (longest_side, longest_side)
        return ({"samples": torch.zeros([batch_size, 4, (height//8)*8//8, (width//8)*8//8])}, (width//8)*8, (height//8)*8)

class PJ_Video_Latent_Generator:
    def __init__(self): pass
    @classmethod
    def INPUT_TYPES(s): return {"required": {"aspect_ratio": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"],), "longest_side": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 16}), "duration_seconds": ("INT", {"default": 5, "min": 1, "max": 60, "step": 1}), "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),}}
    RETURN_TYPES = ("LATENT", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height", "length", "batch_size")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"
    def generate(self, aspect_ratio, longest_side, duration_seconds, batch_size):
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

def download_opus_model_if_missing(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(target_dir, f))]
    if not missing:
        return target_dir

    print(f"\n[PJ Translator] 正在自动下载缺失的离线模型文件 ({len(missing)}个文件) 至: {target_dir} ...")
    try:
        from huggingface_hub import hf_hub_download
        for f in missing:
            print(f"[PJ Translator] 正在从 HuggingFace 下载必须文件: {f} ...")
            hf_hub_download(
                repo_id="Helsinki-NLP/opus-mt-zh-en",
                filename=f,
                local_dir=target_dir
            )
        print("[PJ Translator] 所有必须的离线模型文件已成功下载！\n")
    except Exception as e:
        print(f"[PJ Translator] huggingface_hub 自动下载产生异常 ({e})，尝试备用网络通道...")
        import urllib.request
        base_urls = [
            "https://hf-mirror.com/Helsinki-NLP/opus-mt-zh-en/resolve/main/",
            "https://huggingface.co/Helsinki-NLP/opus-mt-zh-en/resolve/main/"
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
                "text": ("STRING", {"multiline": True, "default": "", "dynamicPrompts": False}),
                "model": (choices, ),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "keep_in_memory": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "translate"
    CATEGORY = "PJ_Nodes/Text"

    def translate(self, text, model, device="auto", keep_in_memory=True):
        if not text or not text.strip():
            return ("",)

        choices, found_map = get_translator_models()
        model_path = found_map.get(model, None)

        if not model_path or not os.path.exists(model_path):
            search_dirs = [folder_paths.models_dir] if hasattr(folder_paths, "models_dir") else []
            aki_models = r"D:\ComfyUI-aki-v1.3\models"
            if os.path.exists(aki_models):
                search_dirs.append(aki_models)
            search_dirs.append(os.path.join(os.path.dirname(__file__), "models"))

            possible_paths = []
            for root_dir in search_dirs:
                possible_paths.extend([
                    os.path.join(root_dir, "prompt_generator", "opus-mt-zh-en"),
                    os.path.join(root_dir, "LLM", "opus-mt-zh-en"),
                    os.path.join(root_dir, "transformers", "opus-mt-zh-en"),
                    os.path.join(root_dir, "opus-mt-zh-en"),
                ])
            for p in possible_paths:
                if os.path.exists(os.path.join(p, "config.json")):
                    model_path = p
                    break

        if not model_path or not os.path.exists(os.path.join(model_path, "config.json")):
            target_dir = os.path.join(folder_paths.models_dir, "prompt_generator", "opus-mt-zh-en")
            model_path = download_opus_model_if_missing(target_dir)

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

        if not keep_in_memory and cache_key not in TRANSLATOR_CACHE:
            del net
            del tokenizer
            if target_device == "cuda":
                torch.cuda.empty_cache()

        return (final_result,)

NODE_CLASS_MAPPINGS = { 
    "PJ_Latent_Generator": PJ_Latent_Generator, 
    "PJ_Video_Latent_Generator": PJ_Video_Latent_Generator, 
    "PJ_Image_Handler": PJ_Image_Handler,
    "PJ_Text_Translator": PJ_Text_Translator
}
NODE_DISPLAY_NAME_MAPPINGS = { 
    "PJ_Latent_Generator": "PJ Latent Generator", 
    "PJ_Video_Latent_Generator": "PJ Video Latent Generator", 
    "PJ_Image_Handler": "PJ Image Preview/Save",
    "PJ_Text_Translator": "PJ Text Translator (ZH -> EN)"
}

WEB_DIRECTORY = "./js"
