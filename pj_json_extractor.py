import json
import re

class PJ_JSON_To_Prompt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "JSON文本": ("STRING", {"multiline": True, "default": "", "placeholder": "把 Gemma 4 等模型的 JSON 输出粘贴或连线到这里"}), 
                "提取模式": ([
                    "极简纯内容 (all_values)", 
                    "原样清理格式 (all_values_with_keys)", 
                    "精简标签列表 (metadata_tags)", 
                    "提取指定键 (specific_key)"
                ], {"default": "极简纯内容 (all_values)"}),
                "指定键名": ("STRING", {"default": "metadata_tags"}),
            },
            "optional": {
                "前缀文本": ("STRING", {"multiline": True, "default": "", "forceInput": True}),
                "后缀文本": ("STRING", {"multiline": True, "default": "", "forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("提示词文本",)
    FUNCTION = "extract"
    CATEGORY = "PJ_Text"

    def extract(self, **kwargs):
        json_text = kwargs.get("JSON文本", kwargs.get("json_text", ""))
        extract_mode = kwargs.get("提取模式", kwargs.get("extract_mode", "极简纯内容 (all_values)"))
        specific_key_name = kwargs.get("指定键名", kwargs.get("specific_key_name", "metadata_tags"))
        prefix = kwargs.get("前缀文本", kwargs.get("prefix", ""))
        suffix = kwargs.get("后缀文本", kwargs.get("suffix", ""))

        # 0. 预清理：去掉代码块标识
        raw_text = json_text.strip().removeprefix("```json").removesuffix("```").strip()
        
        # 模式一：原样清理版 (最稳，不走 JSON 解析)
        if "原样清理" in extract_mode or extract_mode.startswith("all_values_with_keys"):
            lines = raw_text.split("\n")
            cleaned_lines = []
            for line in lines:
                l = line.replace('"', '').replace('{', '').replace('}', '').replace('[', '').replace(']', '').strip()
                if l.endswith(","): l = l[:-1].strip()
                if l: cleaned_lines.append(l)
            res = "\n".join(cleaned_lines)
            
        else:
            # 其他模式需要解析 JSON 对象
            try:
                data = json.loads(raw_text)
            except Exception:
                # 解析失败的回退方案
                values = re.findall(r':\s*"([^"]*)"', raw_text)
                res = ", ".join(values) if values else raw_text
            else:
                if "极简纯内容" in extract_mode or extract_mode.startswith("all_values_paragraph") or extract_mode.startswith("all_values"):
                    def get_pure_values(obj):
                        items = []
                        if isinstance(obj, dict):
                            for v in obj.values(): items.extend(get_pure_values(v))
                        elif isinstance(obj, list):
                            for item in obj: items.extend(get_pure_values(item))
                        else:
                            if str(obj).strip(): items.append(str(obj))
                        return items
                    res = ", ".join(get_pure_values(data))
                    
                elif "精简标签" in extract_mode or extract_mode.startswith("metadata_tags"):
                    tags = data.get("metadata_tags", [])
                    res = ", ".join(tags) if isinstance(tags, list) else str(tags)
                    
                elif "指定键" in extract_mode or extract_mode.startswith("specific_key"):
                    parts = specific_key_name.split(".")
                    val = data
                    for p in parts:
                        if isinstance(val, dict): val = val.get(p, "")
                        else: break
                    res = str(val) if val else ""
                else:
                    res = raw_text

        # 最后拼装： 拼接 [前缀, 提取内容, 后缀]
        final = []
        if isinstance(prefix, str) and prefix.strip(): final.append(prefix.strip())
        if res.strip(): final.append(res.strip())
        if isinstance(suffix, str) and suffix.strip(): final.append(suffix.strip())
        
        return (", ".join(final),)

NODE_CLASS_MAPPINGS = {
    "PJ_JSON_To_Prompt": PJ_JSON_To_Prompt
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PJ_JSON_To_Prompt": "PJ-JSON提示词提取器 (Gemma 4适配)"
}
