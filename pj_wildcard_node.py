import os
import random
import pathlib
import re

# Path to the wildcards folder relative to this script
WILDCARDS_DIR = os.path.join(os.path.dirname(__file__), "wildcards")

class PJWildcardNode:
    @classmethod
    def INPUT_TYPES(s):
        # Scan for .txt files in the wildcards directory
        if not os.path.exists(WILDCARDS_DIR):
            os.makedirs(WILDCARDS_DIR)
            
        files = [f for f in os.listdir(WILDCARDS_DIR) if f.endswith(".txt") and os.path.isfile(os.path.join(WILDCARDS_DIR, f))]
        if not files:
            files = ["未找到词表文件.txt"]
            
        return {
            "required": {
                "词表文件": (files, {"default": files[0] if files else "未找到词表文件.txt"}),
                "随机种子": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("抽取文本",)
    FUNCTION = "pick_text"
    CATEGORY = "PJ_Text"

    def pick_text(self, **kwargs):
        category = kwargs.get("词表文件", kwargs.get("category", ""))
        seed = kwargs.get("随机种子", kwargs.get("seed", 0))

        file_path = os.path.join(WILDCARDS_DIR, category)
        
        if not os.path.exists(file_path):
            return (f"错误: 词表文件不存在 ({category})",)
            
        try:
            # Try UTF-8 first
            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    lines = [line.strip() for line in f.readlines()]
            except UnicodeDecodeError:
                # Fallback to GBK for Windows default encoding
                with open(file_path, "r", encoding="gbk") as f:
                    lines = [line.strip() for line in f.readlines()]
                
            # Filter out empty strings and comments
            options = [l for l in lines if l and not l.startswith("#")]
                
            if not options:
                return ("错误: 词表文件中无有效内容",)
                
            # Use the seed for reproducibility
            rng = random.Random(seed)
            selected = rng.choice(options)
            
            return (selected,)
            
        except Exception as e:
            return (f"错误: {str(e)}",)

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return kwargs.get("随机种子", kwargs.get("seed", 0))

class PJWildcardParserNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "提示词模板": ("STRING", {"multiline": True, "default": "一位女孩，__头发颜色__头发，穿着__衣着__，__构图__镜头，__动作__。"}),
                "随机种子": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("解析文本",)
    FUNCTION = "parse_text"
    CATEGORY = "PJ_Text"

    def parse_text(self, **kwargs):
        text = kwargs.get("提示词模板", kwargs.get("text", ""))
        seed = kwargs.get("随机种子", kwargs.get("seed", 0))
        rng = random.Random(seed)
        
        def replace_wildcard(match):
            wildcard_name = match.group(1)
            file_path = os.path.join(WILDCARDS_DIR, f"{wildcard_name}.txt")
            
            if not os.path.exists(file_path):
                return match.group(0)
                
            try:
                # Try UTF-8-SIG (handles BOM) first
                try:
                    with open(file_path, "r", encoding="utf-8-sig") as f:
                        lines = [line.strip() for line in f.readlines()]
                except UnicodeDecodeError:
                    # Fallback to GBK for legacy Windows text files
                    with open(file_path, "r", encoding="gbk") as f:
                        lines = [line.strip() for line in f.readlines()]
                        
                options = [l for l in lines if l and not l.startswith("#")]
                if options:
                    return rng.choice(options)
                else:
                    return match.group(0)
            except:
                return match.group(0)

        # Match patterns like __filename__ (supports Chinese characters too)
        result = re.sub(r"__([a-zA-Z0-9_\u4e00-\u9fa5]+)__", replace_wildcard, text)
        return (result,)

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return kwargs.get("随机种子", kwargs.get("seed", 0))

class PJTextCombine:
    @classmethod
    def INPUT_TYPES(s):
        optional_dict = {}
        for i in range(1, 21):
            optional_dict[f"文本_{i}"] = ("STRING", {"forceInput": True})
            
        return {
            "required": {
                "合并行数": ("INT", {"default": 3, "min": 1, "max": 20}),
                "连接分隔符": ("STRING", {"default": ", "}),
            },
            "optional": optional_dict
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("合并文本",)
    FUNCTION = "combine"
    CATEGORY = "PJ_Text"

    def combine(self, **kwargs):
        input_count = int(kwargs.get("合并行数", kwargs.get("input_count", 3)))
        delimiter = kwargs.get("连接分隔符", kwargs.get("delimiter", ", "))

        texts = []
        for i in range(1, input_count + 1):
            val = kwargs.get(f"文本_{i}", kwargs.get(f"text_{i}", None))
            if val is not None and str(val).strip():
                texts.append(str(val))
        
        # Handle escape characters
        sep = delimiter.replace("\\n", "\n").replace("\\t", "\t")
        result = sep.join(texts)
        return (result,)
