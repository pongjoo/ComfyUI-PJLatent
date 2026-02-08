
import torch

class PJ_Latent_Generator:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "aspect_ratio": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"],),
                "longest_side": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),
            }
        }

    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"

    def generate(self, aspect_ratio, longest_side, batch_size):
        # 1. Parse aspect ratio
        w_ratio, h_ratio = map(int, aspect_ratio.split(":"))

        # 2. Calculate dimensions based on longest side
        if w_ratio > h_ratio:
            # Landscape
            width = longest_side
            height = int(longest_side * (h_ratio / w_ratio))
        elif h_ratio > w_ratio:
            # Portrait
            height = longest_side
            width = int(longest_side * (w_ratio / h_ratio))
        else:
            # Square
            width = longest_side
            height = longest_side

        # 3. Ensure dimensions are divisible by 8 (standard for SD/Flux latents)
        width = (width // 8) * 8
        height = (height // 8) * 8

        # 4. Generate empty latent
        # Latent shape: [batch_size, 4, height // 8, width // 8]
        latent = torch.zeros([batch_size, 4, height // 8, width // 8])

        return ({"samples": latent}, width, height)


class PJ_Video_Latent_Generator:
    def __init__(self):
        pass


    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "aspect_ratio": (["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9", "9:21"],),
                "longest_side": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 16}),
                "duration_seconds": ("INT", {"default": 5, "min": 1, "max": 60, "step": 1}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),
            }
        }

    RETURN_TYPES = ("LATENT", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("LATENT", "width", "height", "length", "batch_size")
    FUNCTION = "generate"
    CATEGORY = "PJ_Nodes/Latent"

    def generate(self, aspect_ratio, longest_side, duration_seconds, batch_size):
        # 0. Force longest_side to nearest multiple of 16
        longest_side = (longest_side + 8) // 16 * 16

        # 1. Parse aspect ratio
        w_ratio, h_ratio = map(int, aspect_ratio.split(":"))

        # 2. Calculate dimensions based on longest side
        if w_ratio > h_ratio:
            # Landscape
            width = longest_side
            height = int(longest_side * (h_ratio / w_ratio))
        elif h_ratio > w_ratio:
            # Portrait
            height = longest_side
            width = int(longest_side * (w_ratio / h_ratio))
        else:
            # Square
            width = longest_side
            height = longest_side

        # 3. Ensure dimensions are divisible by 16 (round to nearest)
        width = (width + 8) // 16 * 16
        height = (height + 8) // 16 * 16

        # Helper to calc integer frames from seconds
        # Formula requested: seconds * 16 + 1
        length = int(duration_seconds * 16) + 1

        # 4. Generate Latent (Hunyuan/Wan compatible 16ch)
        # Hunyuan/Wan Video Logic
        # Channels: 16
        # Temporal Compression: ~4x ((T-1)//4 + 1)
        # Shape: [batch_size, 16, time_latent, height // 8, width // 8]
        
        # Note: Hunyuan VAE downsamples spatial by 8x.
        
        time_latent = (length - 1) // 4 + 1
        latent = torch.zeros([batch_size, 16, time_latent, height // 8, width // 8])

        return ({"samples": latent}, width, height, length, batch_size)

# Node mapping
NODE_CLASS_MAPPINGS = {
    "PJ_Latent_Generator": PJ_Latent_Generator,
    "PJ_Video_Latent_Generator": PJ_Video_Latent_Generator
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PJ_Latent_Generator": "PJ Latent Generator",
    "PJ_Video_Latent_Generator": "PJ Video Latent Generator"
}
