"""
OliLoraLoader — Power Lora Loader with automatic compatibility filtering.

Fork of rgthree's Power Lora Loader (MIT licence).
Adds: reads each LoRA's safetensors header (no weight loading) and compares
keys against ComfyUI's own key-mapping for the connected model.
Incompatible LoRAs are silently skipped — no log pollution.
"""

import folder_paths
import comfy.lora
from nodes import LoraLoader


# ── Flexible input type ────────────────────────────────────────────────────────
# Same pattern as rgthree's AnyType / FlexibleOptionalInputType.
# Lets ComfyUI accept any number of dynamically-named lora_N kwargs.

class _AnyType(str):
    """A type string that compares equal to any other type."""
    def __ne__(self, other):
        return False

_any = _AnyType("*")


class _FlexibleInputs(dict):
    """Dict that claims to contain any key — allows dynamic widget inputs."""
    def __init__(self, fallback_type, data=None):
        self._fallback = fallback_type
        super().__init__(data or {})

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return super().__getitem__(key) if key in self.keys() else (self._fallback,)


# ── Compatibility check ────────────────────────────────────────────────────────

_LORA_SUFFIXES = (
    ".lora_up.weight", ".lora_down.weight", ".alpha",
    ".lora_A.weight",  ".lora_B.weight",
    ".diff",           ".diff_b",
)


def _read_lora_keys(lora_path):
    """Return the set of tensor key names without loading weights."""
    # Fast path: safetensors header only
    try:
        from safetensors import safe_open
        with safe_open(lora_path, framework="pt", device="cpu") as f:
            return set(f.keys())
    except Exception:
        pass
    # Fallback: full torch load (older .ckpt / .pt files)
    try:
        import torch
        sd = torch.load(lora_path, map_location="cpu", weights_only=True)
        return set(sd.keys())
    except Exception:
        return None


def _check_compat(model, lora_path):
    """
    Return (compatible: bool, reason: str).

    Uses ComfyUI's own model_lora_keys_unet() to build the expected key map
    for the connected model, then checks whether any LoRA base-key appears in
    that map.  Reads only the safetensors header — no weight tensors loaded.
    """
    if model is None:
        return True, "no model"

    lora_keys = _read_lora_keys(lora_path)
    if lora_keys is None:
        return True, "unreadable"
    if not lora_keys:
        return True, "empty"

    # Build model's expected LoRA key map via ComfyUI's own utility
    try:
        model_map = {}
        comfy.lora.model_lora_keys_unet(model.model, model_map)
    except Exception as e:
        return True, f"key-map error: {e}"

    # Strip LoRA suffixes to get base key names, then check against model map
    base_keys = set()
    for k in lora_keys:
        for sfx in _LORA_SUFFIXES:
            if k.endswith(sfx):
                base_keys.add(k[: -len(sfx)])
                break

    if not base_keys:
        return True, "no weight keys found"

    matches = sum(1 for k in base_keys if k in model_map)
    return matches > 0, f"{matches}/{len(base_keys)} keys matched"


# ── Node ───────────────────────────────────────────────────────────────────────

class OliLoraLoader:
    """Power Lora Loader with automatic compatibility filtering."""

    CATEGORY = "Oli/loaders"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": _FlexibleInputs(_any, {
                "model":      ("MODEL",),
                "clip":       ("CLIP",),
                "lora_stack": ("LORA_STACK",),
            }),
            "hidden": {},
        }

    RETURN_TYPES = ("MODEL", "CLIP", "LORA_STACK")
    RETURN_NAMES = ("MODEL", "CLIP", "lora_stack")
    FUNCTION     = "load_loras"
    OUTPUT_NODE  = True   # needed to return compat info to the JS front-end

    def load_loras(self, model=None, clip=None, lora_stack=None, **kwargs):
        compat    = {}              # filename → True | False | None (disabled)
        out_stack = list(lora_stack) if lora_stack else []

        # ── 1. Apply incoming stack loras first (no compat check — upstream decision) ──
        for (filename, strength_model, strength_clip) in (lora_stack or []):
            if not filename or filename == "None":
                continue
            if model is not None:
                model, clip = LoraLoader().load_lora(
                    model, clip, filename, strength_model, strength_clip
                )

        # ── 2. Apply our own lora rows ──────────────────────────────────────────────
        for key, value in kwargs.items():
            if not key.upper().startswith("LORA_"):
                continue
            if not isinstance(value, dict):
                continue
            if not {"on", "lora", "strength"}.issubset(value):
                continue

            filename = value.get("lora") or ""
            if not filename or filename == "None":
                continue

            if not value["on"]:
                compat[filename] = None   # disabled — grey in UI
                continue

            strength_model = value["strength"]
            strength_clip  = value.get("strengthTwo")
            if clip is None:
                strength_clip = 0
            elif strength_clip is None:
                strength_clip = strength_model

            if strength_model == 0 and strength_clip == 0:
                continue

            lora_path = folder_paths.get_full_path("loras", filename)
            if lora_path is None:
                print(f"\033[33m[Oli Lora Loader]\033[0m LoRA not found: {filename}")
                compat[filename] = False
                continue

            compatible, reason = _check_compat(model, lora_path)
            compat[filename] = compatible

            if not compatible:
                print(f"\033[33m[Oli Lora Loader]\033[0m "
                      f"Skip incompatible LoRA: {filename} ({reason})")
                continue

            # Add to outgoing stack (settings only — applied below)
            out_stack.append((filename, strength_model,
                              strength_clip if strength_clip is not None else strength_model))

            if model is not None:
                model, clip = LoraLoader().load_lora(
                    model, clip, filename, strength_model, strength_clip
                )

        return {
            "ui":     {"compat": [compat]},
            "result": (model, clip, out_stack),
        }


NODE_CLASS_MAPPINGS        = {"OliLoraLoader": OliLoraLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"OliLoraLoader": "Power Lora Loader (Oli)"}
