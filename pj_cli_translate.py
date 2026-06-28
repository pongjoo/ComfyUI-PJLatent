import os
import sys
import json
import argparse

# 将当前目录添加到 sys.path
current_dir = os.path.dirname(os.abspath(__file__)) if hasattr(os, 'abspath') else os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from pj_nodes import PJ_Text_Translator
except Exception as e:
    print(json.dumps({"error": f"导入模块失败: {str(e)}"}, ensure_ascii=False))
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=str, default="")
    parser.add_argument("--mode", type=str, default="Auto (智能双向检测)")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--prefix", type=str, default="")
    parser.add_argument("--suffix", type=str, default="")
    args = parser.parse_args()

    translator = PJ_Text_Translator()
    try:
        res, _ = translator.translate(
            text=args.text,
            mode=args.mode,
            device=args.device,
            clean_punctuation=True,
            keep_in_memory=False,
            prefix=args.prefix,
            suffix=args.suffix
        )
        print(json.dumps({"result": res}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
