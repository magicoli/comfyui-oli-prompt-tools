"""
OliConditionalSeed — seed node with a boolean gate.

enable_rule = False  →  returns seed_value unchanged.
enable_rule = True   →  applies control_after_generate rule, returns
                        the new seed and persists it so the next run
                        with enable_rule=False returns the same value.

State is stored per node instance (keyed by unique_id) in ComfyUI's
user directory (/opt/ComfyUI/user/oli-prompt-tools/), not in the
custom node package itself.

JS (oli_conditional_seed.js) updates seed_value and previous_seed
widgets after execution for visual feedback in the UI.
Both UI and API modes work correctly.
"""

import json
import os
import random

try:
    import folder_paths as _fp
    _STATE_DIR = os.path.join(_fp.get_user_directory(), "oli-prompt-tools")
except Exception:
    _STATE_DIR = os.path.join(os.path.expanduser("~"), ".comfyui-oli-prompt-tools")

os.makedirs(_STATE_DIR, exist_ok=True)
_STATE_FILE = os.path.join(_STATE_DIR, "conditional_seed_state.json")

# TODO: Ideally this should match ComfyUI's declared limit (0xFFFFFFFFFFFFFFFF = 2^64-1)
# but values above 2^53-1 lose precision in JS (float64/IEEE 754), causing
# display mismatches between Python output and widget values, and breaking
# API workflows that round-trip through JSON. Easy Seed (comfyui-easy-use)
# uses 2^50 for the same reason. A proper fix would use BigInt throughout
# the JS layer, but LiteGraph serialises widget values as JSON numbers,
# making this non-trivial without patching ComfyUI core.
_MAX_SEED = 2**50 - 1  # 1125899906842623 — same as Easy Seed (comfyui-easy-use)
_MODES    = ["fixed", "randomize", "increment", "decrement"]


def _load_state() -> dict:
    if os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    with open(_STATE_FILE, "w") as f:
        json.dump(state, f)


class OliConditionalSeed:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed_value": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": _MAX_SEED,
                        "step": 1,
                        "display": "number",
                    },
                ),
                "control_after_generate": (_MODES, {"default": "randomize"}),
                "enable_rule": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    OUTPUT_NODE  = True
    FUNCTION     = "execute"
    CATEGORY     = "Oli/utils"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, seed_value: int, control_after_generate: str,
                enable_rule: bool, unique_id=None) -> dict:
        state = _load_state()
        key   = str(unique_id) if unique_id else None

        if key is None:
            # API mode: JS never updates widgets, use persisted next_val
            if "api" in state:
                seed_value = state["api"]

        # Always output the current seed_value (what's displayed)
        out = seed_value

        # Compute next seed for the following run
        if not enable_rule or control_after_generate == "fixed":
            next_val = seed_value
        elif control_after_generate == "randomize":
            next_val = random.randint(0, _MAX_SEED)
        elif control_after_generate == "increment":
            next_val = (seed_value + 1) % (_MAX_SEED + 1)
        else:  # decrement
            next_val = (seed_value - 1) % (_MAX_SEED + 1)

        # Persist next_val for the next run (used in API mode)
        state[key] = next_val
        _save_state(state)

        return {
            "ui": {
                "seed_out":        [str(out)],
                "next_seed_value": [str(next_val)],
            },
            "result": (out,),
        }


NODE_CLASS_MAPPINGS = {
    "OliConditionalSeed": OliConditionalSeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OliConditionalSeed": "Conditional Seed (Oli)",
}
