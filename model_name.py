"""
OliModelInfo — returns architecture details of any connected model
(MODEL, CLIP, VAE, or any other type accepted via wildcard input),
plus the title of the upstream node that produced it.
"""

from .utils import get_model_details, get_upstream_label


class OliModelInfo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "model": ("*",),
            },
            "hidden": {
                "unique_id":     "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("class_name", "dim", "label")
    FUNCTION     = "execute"
    OUTPUT_NODE  = True
    CATEGORY     = "Oli/utils"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, model=None, unique_id=None, extra_pnginfo=None):
        lines, class_name, dim = get_model_details(model)
        label = get_upstream_label(extra_pnginfo, unique_id, "model", depth=1)
        return {
            "ui":     {"text": ["\n".join(lines)]},
            "result": (class_name, dim, label),
        }


NODE_CLASS_MAPPINGS        = {"OliModelInfo": OliModelInfo}
NODE_DISPLAY_NAME_MAPPINGS = {"OliModelInfo": "Model Info (Oli)"}
