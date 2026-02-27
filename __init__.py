from .prompt_line_pick  import NODE_CLASS_MAPPINGS as _m1, NODE_DISPLAY_NAME_MAPPINGS as _n1
from .video_frame_limit import NODE_CLASS_MAPPINGS as _m2, NODE_DISPLAY_NAME_MAPPINGS as _n2
from .model_name        import NODE_CLASS_MAPPINGS as _m3, NODE_DISPLAY_NAME_MAPPINGS as _n3  # OliModelInfo

NODE_CLASS_MAPPINGS        = {**_m1, **_m2, **_m3}
NODE_DISPLAY_NAME_MAPPINGS = {**_n1, **_n2, **_n3}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("\033[34m[ComfyUI Oli Prompt Tools]\033[0m \033[92mLoaded\033[0m")
