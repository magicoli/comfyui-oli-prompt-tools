from .lora_loader import NODE_CLASS_MAPPINGS as _m4  # OliLoraLoader
from .lora_loader import NODE_DISPLAY_NAME_MAPPINGS as _n4
from .mega_string_list import NODE_CLASS_MAPPINGS as _m6  # OliMegaStringList
from .mega_string_list import NODE_DISPLAY_NAME_MAPPINGS as _n6
from .model_name import NODE_CLASS_MAPPINGS as _m3  # OliModelInfo
from .model_name import NODE_DISPLAY_NAME_MAPPINGS as _n3
from .node_label import NODE_CLASS_MAPPINGS as _m5  # OliNodeLabel
from .node_label import NODE_DISPLAY_NAME_MAPPINGS as _n5
from .prompt_line_pick import NODE_CLASS_MAPPINGS as _m1
from .prompt_line_pick import NODE_DISPLAY_NAME_MAPPINGS as _n1
from .video_frame_limit import NODE_CLASS_MAPPINGS as _m2
from .video_frame_limit import NODE_DISPLAY_NAME_MAPPINGS as _n2

NODE_CLASS_MAPPINGS = {**_m1, **_m2, **_m3, **_m4, **_m5, **_m6}
NODE_DISPLAY_NAME_MAPPINGS = {**_n1, **_n2, **_n3, **_n4, **_n5, **_n6}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

__author__ = """Olivier van Helden"""
__email__ = "olivier@van-helden.net"
__version__ = "0.0.1"

print("\033[34m[ComfyUI Oli Prompt Tools]\033[0m \033[92mLoaded\033[0m")
