"""
OliVideoFrameLimit — caps video duration to avoid OOM crashes.

Formula: max_frames = total_vram × safety / (width × height × bytes_per_pixel)

Equivalent to: total_vram × safety / (tokens_per_frame × bytes_per_token)
  where tokens_per_frame = (width/8) × (height/8)
  and   bytes_per_token  = bytes_per_pixel × 64

The bytes_per_pixel constant is the peak VRAM cost per input pixel per frame.
It captures activations, KV cache, Q/K/V tensors, etc. during inference.
It is model-dependent — calibrate once per model family:
  ~64   : AnimateDiff (windowed temporal attention, low overhead)
  ~256  : Wan 1.3B, CogVideoX (hidden_dim ≈ 1536, full 3D attention)
  ~640  : Wan 14B (hidden_dim ≈ 4096)

Why total VRAM and not free VRAM:
  ComfyUI offloads model weights layer by layer during inference.
  Peak VRAM = one layer's weights + activation tensors — not "total - model size".
  Total VRAM is therefore the correct capacity to budget against.
"""

import torch


class OliVideoFrameLimit:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width":    ("INT",   {"default": 832,   "min": 64,  "max": 8192,   "step": 8}),
                "height":   ("INT",   {"default": 480,   "min": 64,  "max": 8192,   "step": 8}),
                "duration": ("FLOAT", {"default": 5.0,   "min": 0.1, "max": 3600.0, "step": 0.1}),
                "fps":      ("FLOAT", {"default": 8.0,   "min": 1.0, "max": 120.0,  "step": 0.5}),
                "safety_margin": ("FLOAT", {
                    "default": 0.9,
                    "min": 0.5, "max": 1.0, "step": 0.05,
                    "tooltip": "Fraction of total VRAM to budget. 0.9 = 10% headroom.",
                }),
                "bytes_per_pixel": ("INT", {
                    "default": 256,
                    "min": 1, "max": 8192, "step": 1,
                    "tooltip": (
                        "Peak VRAM cost per input pixel per frame. Model-dependent: "
                        "~64 AnimateDiff | ~256 Wan 1.3B / CogVideoX | ~640 Wan 14B. "
                        "To calibrate: adjust until the formula matches your known working limit."
                    ),
                }),
            },
        }

    RETURN_TYPES = ("INT",           "FLOAT")
    RETURN_NAMES = ("capped_frames", "capped_duration")
    FUNCTION = "execute"
    CATEGORY = "Oli/utils"

    def execute(self, width, height, duration, fps,
                safety_margin=0.9, bytes_per_pixel=256):

        requested_frames = max(1, round(duration * fps))

        if not torch.cuda.is_available():
            return (requested_frames, float(requested_frames / fps))

        # Total VRAM — correct base, see module docstring.
        total_vram = torch.cuda.get_device_properties(0).total_memory
        vram_budget = total_vram * safety_margin

        bytes_per_frame = width * height * bytes_per_pixel
        max_frames = max(1, int(vram_budget / bytes_per_frame))

        actual_frames = min(requested_frames, max_frames)
        actual_duration = actual_frames / fps

        return (actual_frames, float(actual_duration))


NODE_CLASS_MAPPINGS = {
    "OliVideoFrameLimit": OliVideoFrameLimit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliVideoFrameLimit": "Oli - Video Frame Limit",
}
