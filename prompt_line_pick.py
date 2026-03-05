"""
OliPromptLinePick — reimplementation of the easy promptLine concept.

Replaces easy promptLine's start_index with a seed. With uncorrelate=True
(default), the index is derived via sha256(seed:node_id) % len(lines),
giving a uniform distribution and full independence between node instances:
two pickers with the same seed pick at uncorrelated positions even when
their lists have the same length or lengths that are multiples of each other.
With uncorrelate=False, index = seed % len(lines), same direct mapping as
easy promptLine's start_index but wrapping instead of clamping.

Output format matches easy promptLine: STRING and COMBO are output lists
(is_output_list=True), each containing only the single picked item.
This makes COMBO compatible with any COMBO-typed input (SDXL Prompt Styler
etc.) and gives the outputs the list icon, matching easy promptLine.

Supports stacking: pass prompts_in from a previous picker; this node
appends its pick and returns the extended LIST via the prompts output,
compatible with easy promptList's optional_prompt_list input.

COMBO type compatibility
------------------------
ComfyUI's validate_node_input() in comfy_execution/validation.py rejects a
generic "COMBO" output when the destination input_type is a list of option
strings (e.g. SDXL Prompt Styler's artist/style fields).  The check that
gates everything is::

    if not received_type != input_type:
        return True

_ComboType is a str subclass whose __ne__ always returns False, so
``not received_type != input_type`` evaluates to ``not False`` = True and
validation passes immediately regardless of the option list on the other end.
This is the established ComfyUI pattern for this class of problem.
"""

import hashlib


class _ComboType(str):
    """str subclass whose __ne__ always returns False.

    ComfyUI's validate_node_input() first evaluates
    ``if not received_type != input_type: return True``.
    By making __ne__ return False the expression becomes ``not False`` = True,
    so validation passes immediately for any destination COMBO input regardless
    of its specific option list (SDXL Prompt Styler artist/style, etc.).
    """

    def __ne__(self, other: object) -> bool:
        return False


_COMBO = _ComboType("COMBO")


class OliPromptLinePick:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "prompt 1\nprompt 2\nprompt3",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": "fixed",
                    },
                ),
                "remove_empty_lines": ("BOOLEAN", {"default": True}),
                "uncorrelate": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "When on, index = sha256(seed:node_id) % len — each node instance "
                            "picks independently even with the same seed, avoiding correlation "
                            "between lists of the same or multiple lengths. "
                            "When off, index = seed % len — standard index behavior which could "
                            "result in correlated picks between similar-length lists."
                        ),
                    },
                ),
            },
            "optional": {
                "optional_prompt_list": ("LIST", {}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", _COMBO, "LIST", "STRING", "INT")
    RETURN_NAMES = ("STRING", "COMBO", "prompt_list", "prompt_strings", "seed")
    OUTPUT_IS_LIST = (False, True, False, True, False)
    FUNCTION = "execute"
    CATEGORY = "Oli/prompt"

    def execute(
        self,
        prompt,
        seed,
        remove_empty_lines=True,
        uncorrelate=True,
        optional_prompt_list=None,
        unique_id=None,
    ):
        lines = prompt.split("\n")

        if remove_empty_lines:
            lines = [line.strip() for line in lines if line.strip()]
        else:
            lines = [line.strip() for line in lines]

        out_list = (
            list(optional_prompt_list) if optional_prompt_list is not None else []
        )

        if not lines:
            return ("", [], out_list, out_list, seed)

        if uncorrelate:
            digest = hashlib.sha256(f"{seed}:{unique_id}".encode()).hexdigest()
            index = int(digest, 16) % len(lines)
        else:
            index = seed % len(lines)

        picked = lines[index]

        # COMBO output is a single-element list. OUTPUT_IS_LIST=True gives it
        # the list icon. The _ComboType subclass handles validation bypass.
        out_list.append(picked)

        return (picked, [picked], out_list, out_list, seed)


NODE_CLASS_MAPPINGS = {
    "OliPromptLinePick": OliPromptLinePick,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliPromptLinePick": "Prompt Line Pick (Oli)",
}
