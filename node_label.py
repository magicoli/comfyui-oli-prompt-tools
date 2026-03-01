"""
OliNodeLabel — passes any value through and outputs the upstream node's title.

See oli_utils.get_upstream_label() for traversal semantics.
"""

import nodes as _comfy_nodes
from .utils import get_upstream_label


class _AnyType(str):
    def __ne__(self, other):
        return False

_any = _AnyType("*")


class OliNodeLabel:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "depth": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
            },
            "optional": {
                "node": (_any,),
            },
            "hidden": {
                "unique_id":     "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = (_any, "STRING")
    RETURN_NAMES = ("node", "label")
    FUNCTION     = "execute"
    CATEGORY     = "Oli/utils"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, depth=1, node=None, unique_id=None, extra_pnginfo=None):
        label = get_upstream_label(extra_pnginfo, unique_id, "node", depth)
        return (node, label)


NODE_CLASS_MAPPINGS        = {"OliNodeLabel": OliNodeLabel}
NODE_DISPLAY_NAME_MAPPINGS = {"OliNodeLabel": "Node Label (Oli)"}
