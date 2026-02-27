"""
OliModelInfo — returns architecture details of any connected model
(MODEL, CLIP, VAE, or any other type accepted via wildcard input).
"""

_DIM_ATTRS = (
    "hidden_size", "dim", "embed_dim", "hidden_dim",
    "d_model", "inner_dim", "width", "model_dim",
)


def _count_params(obj):
    try:
        n = sum(p.numel() for p in obj.parameters())
        if n >= 1_000_000_000:
            return f"{n / 1e9:.1f}B"
        if n >= 1_000_000:
            return f"{n / 1e6:.0f}M"
        return str(n)
    except Exception:
        return None


def _find_dim(obj):
    search = [obj]
    for attr in ("diffusion_model", "transformer", "model", "net", "backbone"):
        sub = getattr(obj, attr, None)
        if sub is not None and sub is not obj:
            search.append(sub)
    for o in search:
        for attr in _DIM_ATTRS:
            val = getattr(o, attr, None)
            if isinstance(val, int) and 64 <= val <= 32768:
                return val
        for cfg_attr in ("config", "model_config"):
            cfg = getattr(o, cfg_attr, None)
            if cfg:
                for attr in _DIM_ATTRS:
                    val = getattr(cfg, attr, None)
                    if isinstance(val, int) and 64 <= val <= 32768:
                        return val
    return None


def _get_model_details(model):
    """
    Returns (display_lines, class_name, dim).
    Handles MODEL (ModelPatcher / GGUFModelPatcher), CLIP, VAE, and unknowns.
    """
    if model is None:
        return ["—"], "", 0

    outer_class = type(model).__name__
    lines = []

    # ── CLIP ──────────────────────────────────────────────────────────────
    if outer_class == "CLIP" or hasattr(model, "cond_stage_model"):
        inner = getattr(model, "cond_stage_model", model)
        class_name = type(inner).__name__
        lines.append(f"class:  {class_name}")
        lines.append(f"format: clip")
        p = _count_params(inner)
        if p:
            lines.append(f"params: {p}")
        return lines, class_name, 0

    # ── VAE ───────────────────────────────────────────────────────────────
    if outer_class == "VAE" or hasattr(model, "first_stage_model"):
        inner = getattr(model, "first_stage_model", model)
        class_name = type(inner).__name__
        lines.append(f"class:  {class_name}")
        lines.append(f"format: vae")
        p = _count_params(inner)
        if p:
            lines.append(f"params: {p}")
        return lines, class_name, 0

    # ── MODEL (ModelPatcher or GGUFModelPatcher) ───────────────────────────
    fmt = "gguf" if "GGUF" in outer_class else "standard"

    inner = model
    for accessor in ("model", "diffusion_model"):
        sub = getattr(inner, accessor, None)
        if sub is not None:
            inner = sub
            break

    class_name = type(inner).__name__
    lines.append(f"class:  {class_name}")

    # Training parameterization (FLOW, EPS, V_PREDICTION…)
    mt = getattr(inner, "model_type", None)
    if mt is not None:
        try:
            lines.append(f"type:   {mt.name}")
        except Exception:
            lines.append(f"type:   {mt}")

    # Hidden dimension
    dim = _find_dim(inner) or 0
    if dim:
        lines.append(f"dim:    {dim}")

    # Parameter count
    p = _count_params(inner)
    if p:
        lines.append(f"params: {p}")

    lines.append(f"format: {fmt}")

    return lines, class_name, dim


class OliModelInfo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "model": ("*",),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("class_name", "dim")
    FUNCTION = "execute"
    OUTPUT_NODE = True
    CATEGORY = "Oli/utils"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, model=None):
        lines, class_name, dim = _get_model_details(model)
        return {
            "ui":    {"text": ["\n".join(lines)]},
            "result": (class_name, dim),
        }


NODE_CLASS_MAPPINGS        = {"OliModelInfo": OliModelInfo}
NODE_DISPLAY_NAME_MAPPINGS = {"OliModelInfo": "Model Info (Oli)"}
