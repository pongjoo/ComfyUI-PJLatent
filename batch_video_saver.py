import os
import cv2
import json
import numpy as np
import datetime
import folder_paths

class BatchVideoSaver:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "标签文本_tag_text": ("STRING", {"forceInput": True}),
                "附加文本_extra_text": ("STRING", {"multiline": True, "default": ""}),
                "附加位置_extra_position": (["开头_Start", "结尾_End"],),
                "自定义保存路径_custom_path": ("STRING", {"default": ""}),
                "自定义文件名_custom_filename": ("STRING", {"default": ""}),
                "移除自定义后缀_remove_ext": ("BOOLEAN", {"default": True}),
                "文件名前缀_prefix": ("STRING", {"default": "video"}),
                "时间戳_timestamp": (["None", "Second", "Millisecond"],),
                "帧率_fps": ("FLOAT", {"default": 16.0, "min": 1.0, "max": 120.0, "step": 0.1}),
                "视频格式_format": (["mp4", "avi"],),
            },
            "optional": {
                "图像流_images": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_video_and_tags"
    OUTPUT_NODE = True
    CATEGORY = "PJ/批量视频"

    def save_video_and_tags(self, 标签文本_tag_text, 附加文本_extra_text="", 附加位置_extra_position="结尾_End", 自定义保存路径_custom_path="", 自定义文件名_custom_filename="", 移除自定义后缀_remove_ext=True, 文件名前缀_prefix="video", 时间戳_timestamp="None", 帧率_fps=16.0, 视频格式_format="mp4", 图像流_images=None, prompt=None, extra_pnginfo=None):
        images = 图像流_images
        tag_text = 标签文本_tag_text
        extra_text = 附加文本_extra_text
        extra_pos = 附加位置_extra_position
        custom_path = 自定义保存路径_custom_path
        custom_filename = 自定义文件名_custom_filename
        remove_custom_filename_ext = 移除自定义后缀_remove_ext
        filename_prefix = 文件名前缀_prefix
        timestamp = 时间戳_timestamp
        fps = 帧率_fps
        format = 视频格式_format
        
        filename_prefix += self.prefix_append

        base_output_dir = self.output_dir
        if custom_path and custom_path.strip() != "":
            base_output_dir = os.path.normpath(custom_path.strip())
            os.makedirs(base_output_dir, exist_ok=True)

        # Handle custom_filename logic
        if custom_filename and custom_filename.strip() != "":
            # Replace backslashes
            custom_filename = custom_filename.replace("\\", "/")
            
            # Determine directory and file basename
            if os.path.isabs(custom_filename):
                full_output_folder = os.path.dirname(custom_filename)
                file = os.path.basename(custom_filename)
            else:
                parts = custom_filename.split("/")
                file = parts[-1]
                subfolder = "/".join(parts[:-1])
                full_output_folder = os.path.join(base_output_dir, subfolder)
            
            if remove_custom_filename_ext:
                file = os.path.splitext(file)[0]
                
            os.makedirs(full_output_folder, exist_ok=True)
            
            base_name = file
            if filename_prefix:
                base_name = f"{filename_prefix}_{base_name}"
            
            # Timestamp
            ts_str = ""
            if timestamp == "Second":
                ts_str = f"_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            elif timestamp == "Millisecond":
                ts_str = f"_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"
                
            base_name += ts_str
            
            video_file_name = f"{base_name}.{format}"
            txt_file_name = f"{base_name}.txt"
        else:
            # Standard ComfyUI counter behavior
            img_width = images[0].shape[1] if images is not None else 0
            img_height = images[0].shape[0] if images is not None else 0
            full_output_folder, filename, counter, subfolder, filename_prefix_res = folder_paths.get_save_image_path(filename_prefix, base_output_dir, img_width, img_height)
            
            ts_str = ""
            if timestamp == "Second":
                ts_str = f"_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            elif timestamp == "Millisecond":
                ts_str = f"_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"

            base_name = f"{filename}_{counter:05}{ts_str}"
            video_file_name = f"{base_name}.{format}"
            txt_file_name = f"{base_name}.txt"

        video_output_path = os.path.join(full_output_folder, video_file_name)
        txt_output_path = os.path.join(full_output_folder, txt_file_name)

        # Safely convert tag_text to string if it's a list (some taggers output a list of strings)
        if isinstance(tag_text, list):
            tag_text = "\n".join([str(t) for t in tag_text])
        elif not isinstance(tag_text, str):
            tag_text = str(tag_text)
            
        if isinstance(extra_text, list):
            extra_text = "\n".join([str(t) for t in extra_text])
        elif not isinstance(extra_text, str):
            extra_text = str(extra_text)

        final_text = tag_text
        if extra_text.strip():
            if final_text:
                if extra_pos == "开头_Start":
                    final_text = extra_text + "\n" + final_text
                else:
                    final_text = final_text + "\n" + extra_text
            else:
                final_text = extra_text

        # Save tag text
        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(final_text)

        # Save video
        if images is not None:
            frames = (images.cpu().numpy() * 255.0).astype(np.uint8)
            batch_size, height, width, channels = frames.shape

            if format == "mp4":
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            else: # avi
                fourcc = cv2.VideoWriter_fourcc(*'XVID')

            out = cv2.VideoWriter(video_output_path, fourcc, float(fps), (width, height))

            for i in range(batch_size):
                frame = frames[i]
                if channels == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                elif channels == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                out.write(frame)

            out.release()
            return {"ui": {"text": [f"Saved {video_file_name}\nSaved {txt_file_name}"]}}
        else:
            return {"ui": {"text": [f"Saved {txt_file_name} (文本模式)"]}}
