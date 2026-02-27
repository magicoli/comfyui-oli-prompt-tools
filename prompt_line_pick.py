"""
OliPromptLinePick — fork of easy promptLine.

Replaces start_index + max_rows with a seed. Item is picked via
sha256(seed:node_id) % len(lines): perfectly uniform distribution,
fully independent between instances — no prime modulos needed.
"""

import hashlib


class OliPromptLinePick:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "prompt 1\nprompt 2\nprompt3",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "control_after_generate": "fixed",
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

        return (lines[index], lines[index])


NODE_CLASS_MAPPINGS = {
    "OliPromptLinePick": OliPromptLinePick,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliPromptLinePick": "Prompt Line Pick (Oli)",
}
