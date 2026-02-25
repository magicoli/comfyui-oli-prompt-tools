"""
ComfyUI Prompt Tools - nodes.py

PromptLinePick: picks one item from a multiline list using seed + channel.

Unlike easy PromptLine which requires a manual 'max_rows' parameter
(causing the last item to be wildly over-represented), this node
automatically uses the actual list length for a perfectly uniform distribution.

The 'channel' input solves the correlation problem that arises when using a
single global seed across multiple lists: instead of manually managing prime
modulos, just assign a unique channel number (0, 1, 2...) to each node.
Internally uses sha256(seed:channel) % length for true independence.
"""

import hashlib


class PromptLinePick:
    """
    Picks one item from a multiline list, seeded and channel-isolated.

    channel: assign a different integer to each instance of this node in your
    workflow. Nodes with the same seed but different channels always produce
    independent selections, regardless of list lengths.
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
                "channel": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 9999,
                    "tooltip": (
                        "Assign a unique channel per node instance. "
                        "Nodes sharing the same seed but with different channels "
                        "produce fully independent selections."
                    ),
                }),
            },
            "optional": {
                "remove_empty_lines": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("text", "index")
    FUNCTION = "execute"
    CATEGORY = "utils/prompt"

    def execute(self, text, seed, channel, remove_empty_lines=True):
        lines = text.split("\n")

        if remove_empty_lines:
            lines = [line.strip() for line in lines if line.strip()]
        else:
            lines = [line.strip() for line in lines]

        if not lines:
            return ("", 0)

        # sha256(seed:channel) gives a uniform, deterministic hash.
        # Different channels → fully independent selections, no primes needed.
        digest = hashlib.sha256(f"{seed}:{channel}".encode()).hexdigest()
        index = int(digest, 16) % len(lines)

        return (lines[index], index)


NODE_CLASS_MAPPINGS = {
    "PromptLinePick": PromptLinePick,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptLinePick": "Prompt Line Pick",
}
