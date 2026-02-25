"""
ComfyUI Prompt Tools - nodes.py

PromptLinePick: picks one item from a multiline list using seed + node ID.

Unlike easy PromptLine which requires a manual 'max_rows' parameter
(causing the last item to be wildly over-represented), this node
automatically uses the actual list length for a perfectly uniform distribution.

Each node instance has a unique ID assigned by ComfyUI (stable across
executions). This ID is used as the channel discriminator internally via
sha256(seed:node_id) % length, giving fully independent selections across
all instances sharing the same seed — no manual channel management needed.
"""

import hashlib


class PromptLinePick:
    """
    Picks one item from a multiline list, seeded and automatically isolated.

    Uses the node's own unique ID as a discriminator, so multiple instances
    with the same seed always produce independent selections regardless of
    list lengths — no prime modulos, no manual channel numbers.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "item 1\nitem 2\nitem 3",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
            },
            "optional": {
                "remove_empty_lines": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("text", "index")
    FUNCTION = "execute"
    CATEGORY = "utils/prompt"

    def execute(self, text, seed, remove_empty_lines=True, unique_id=None):
        lines = text.split("\n")

        if remove_empty_lines:
            lines = [line.strip() for line in lines if line.strip()]
        else:
            lines = [line.strip() for line in lines]

        if not lines:
            return ("", 0)

        # sha256(seed:node_id) — node_id is unique per instance in the workflow,
        # stable across executions, requires zero manual maintenance.
        digest = hashlib.sha256(f"{seed}:{unique_id}".encode()).hexdigest()
        index = int(digest, 16) % len(lines)

        return (lines[index], index)


NODE_CLASS_MAPPINGS = {
    "PromptLinePick": PromptLinePick,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLinePick": "Prompt Line Pick",
}
