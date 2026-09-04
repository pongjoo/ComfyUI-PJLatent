import os
import cv2
import torch
import numpy as np

# Tracks internal state across executions per node ID
# Format: { unique_id : { "last_widget_index": int, "current_index": int } }
NODE_STATE = {}

class BatchVideoPathProvider:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "视频目录_directory": ("STRING", {"default": "C:/videos/"}),
                "自动前进_auto_advance": (["disabled", "enabled"],),
                "到达末尾_on_end": (["loop_循环", "stop_停止此队列"],),
                "索引_index": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"}
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("视频路径 (video_path)", "无后缀文件名 (filename_no_ext)")
    FUNCTION = "get_path"
    CATEGORY = "PJ/批量视频"

    def get_path(self, 视频目录_directory, 自动前进_auto_advance, 到达末尾_on_end, 索引_index, unique_id):
        directory = 视频目录_directory
        auto_advance = 自动前进_auto_advance
        index = 索引_index
        
        if unique_id not in NODE_STATE:
            NODE_STATE[unique_id] = {"last_widget_index": index, "current_index": index}

        state = NODE_STATE[unique_id]

        if state["last_widget_index"] != index:
            state["current_index"] = index
            state["last_widget_index"] = index

        current_idx = state["current_index"] if auto_advance == "enabled" else index

        if not os.path.isdir(directory):
            raise ValueError(f"Directory not found: {directory}")

        valid_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and os.path.splitext(f)[1].lower() in valid_extensions]
        files.sort()

        if not files:
            raise ValueError(f"No video files found in {directory}")

        if 到达末尾_on_end == "stop_停止此队列" and current_idx >= len(files):
            raise ValueError(f"\n=========================================\n✅ 批量处理已完成！\n已成功处理 {len(files)} 个视频，队列自动安全停止。\n如果想再次运行，请将 索引/随机种子的值 重置为 0。\n=========================================")

        actual_index = current_idx % len(files)
        selected_file = files[actual_index]
        video_path = os.path.join(directory, selected_file)
        file_no_ext = os.path.splitext(selected_file)[0]

        if auto_advance == "enabled":
            state["current_index"] += 1

        return (video_path, file_no_ext)

    @classmethod
    def IS_CHANGED(s, 视频目录_directory, 自动前进_auto_advance, 到达末尾_on_end, 索引_index, unique_id=""):
        if 自动前进_auto_advance == "enabled":
            return float("nan")
        return f"{视频目录_directory}_{索引_index}_{到达末尾_on_end}"

class BatchVideoLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "视频目录_directory": ("STRING", {"default": "C:/videos/"}),
                "自动前进_auto_advance": (["disabled", "enabled"],),
                "到达末尾_on_end": (["loop_循环", "stop_停止此队列"],),
                "索引_index": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "加载帧数上限_frame_cap": ("INT", {"default": 0, "min": 0, "max": 9999999}),
                "跳过前N帧_skip_first": ("INT", {"default": 0, "min": 0, "max": 9999999}),
                "每N帧提取_select_nth": ("INT", {"default": 1, "min": 1, "max": 9999999}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"}
        }

    RETURN_TYPES = ("IMAGE", "INT", "STRING", "STRING")
    RETURN_NAMES = ("图像流 (IMAGE)", "帧数 (frame_count)", "视频路径 (video_path)", "无后缀文件名 (filename_no_ext)")
    FUNCTION = "load_video"

    CATEGORY = "PJ/批量视频"

    def load_video(self, 视频目录_directory, 自动前进_auto_advance, 到达末尾_on_end, 索引_index, 加载帧数上限_frame_cap, 跳过前N帧_skip_first, 每N帧提取_select_nth, unique_id):
        directory = 视频目录_directory
        auto_advance = 自动前进_auto_advance
        index = 索引_index
        frame_load_cap = 加载帧数上限_frame_cap
        skip_first_frames = 跳过前N帧_skip_first
        select_every_nth = 每N帧提取_select_nth
        
        if unique_id not in NODE_STATE:
            NODE_STATE[unique_id] = {"last_widget_index": index, "current_index": index}

        state = NODE_STATE[unique_id]

        if state["last_widget_index"] != index:
            state["current_index"] = index
            state["last_widget_index"] = index

        current_idx = state["current_index"] if auto_advance == "enabled" else index

        if not os.path.isdir(directory):
            raise ValueError(f"Directory not found: {directory}")

        valid_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and os.path.splitext(f)[1].lower() in valid_extensions]
        files.sort()

        if not files:
            raise ValueError(f"No video files found in {directory}")

        if 到达末尾_on_end == "stop_停止此队列" and current_idx >= len(files):
            raise ValueError(f"\n=========================================\n✅ 批量处理已完成！\n已成功处理 {len(files)} 个视频，队列自动安全停止。\n如果想再次运行，请将 索引/随机种子的值 重置为 0。\n=========================================")


        actual_index = current_idx % len(files)
        selected_file = files[actual_index]
        video_path = os.path.join(directory, selected_file)
        file_no_ext = os.path.splitext(selected_file)[0]

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")

        frames = []
        read_count = 0
        saved_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if read_count >= skip_first_frames:
                # 按照 select_every_nth 过滤帧
                if (read_count - skip_first_frames) % select_every_nth == 0:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame = frame.astype(np.float32) / 255.0
                    frames.append(frame)
                    saved_count += 1
                    
                    if frame_load_cap > 0 and saved_count >= frame_load_cap:
                        break
                        
            read_count += 1

        cap.release()
        
        if not frames:
            raise ValueError(f"No frames could be read from video: {video_path}")

        image_tensor = torch.from_numpy(np.array(frames))
        frame_count = len(frames)

        if auto_advance == "enabled":
            state["current_index"] += 1

        return (image_tensor, frame_count, video_path, file_no_ext)

    @classmethod
    def IS_CHANGED(s, 视频目录_directory, 自动前进_auto_advance, 到达末尾_on_end, 索引_index, 加载帧数上限_frame_cap, 跳过前N帧_skip_first, 每N帧提取_select_nth, unique_id=""):
        if 自动前进_auto_advance == "enabled":
            return float("nan")
        return f"{视频目录_directory}_{索引_index}_{加载帧数上限_frame_cap}_{跳过前N帧_skip_first}_{每N帧提取_select_nth}_{到达末尾_on_end}"
