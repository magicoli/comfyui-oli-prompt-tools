"""
ComfyUI Oli Prompt Tools - nodes.py

OliPromptLinePick: fork of easy promptLine that replaces start_index + max_rows
with a seed input. The item is picked via sha256(seed:node_id) % len(lines),
giving a perfectly uniform distribution and full independence between instances
— no prime modulos, no manual channel numbers needed.
"""

import hashlib


class OliPromptLinePick:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "item 1\nitem 2\nitem 3",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
                "remove_empty_lines": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "COMBO")
    RETURN_NAMES = ("STRING", "COMBO")
    FUNCTION = "execute"
    CATEGORY = "Oli/prompt"

    def execute(self, prompt, seed, remove_empty_lines=True, unique_id=None):
        lines = prompt.split("\n")

        if remove_empty_lines:
            lines = [line.strip() for line in lines if line.strip()]
        else:
            lines = [line.strip() for line in lines]

        if not lines:
            return ("", "")

        digest = hashlib.sha256(f"{seed}:{unique_id}".encode()).hexdigest()
        index = int(digest, 16) % len(lines)

        selected = lines[index]
        return (selected, selected)


NODE_CLASS_MAPPINGS = {
    "OliPromptLinePick": OliPromptLinePick,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliPromptLinePick": "Oli - Prompt Line Pick",
}
