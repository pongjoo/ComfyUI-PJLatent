import os
try:
    from comfy_api.latest import InputImpl
except ImportError:
    pass

class PJ_LoadVideoPathForOfficial:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "视频绝对路径_video_path": ("STRING", {"forceInput": True, "default": ""}),
            }
        }
    
    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("官方 VIDEO 对象",)
    FUNCTION = "load_video"
    CATEGORY = "PJ/批量视频"

    def load_video(self, 视频绝对路径_video_path):
        if not os.path.exists(视频绝对路径_video_path):
            raise ValueError(f"找不到视频文件，请检查路径是否正确: {视频绝对路径_video_path}")
        
        # 将字符串路径转换为官方新版 API 要求的底层 Video 对象！
        video_obj = InputImpl.VideoFromFile(视频绝对路径_video_path)
        
        print(f"✅ 已成功加载视频并转换为官方格式: {视频绝对路径_video_path}")
        return (video_obj,)
