"""
Shared utilities for Oli custom nodes.

Public API
----------
get_model_details(model)
    → (lines, class_name, dim)  — model architecture introspection

get_upstream_label(extra_pnginfo, unique_id, input_name, depth=1)
    → str  — title of the upstream node connected to `input_name`,
              traversing `depth` levels up the workflow graph.
              Muted nodes are skipped; when multiple active inputs are
              found at the target level the labels cycle one per execution.
"""

import nodes as _comfy_nodes

# ---------------------------------------------------------------------------
# Model introspection
# ---------------------------------------------------------------------------

_DIM_ATTRS = (
    "hidden_size", "dim", "embed_dim", "hidden_dim",
    "d_model", "inner_dim", "width", "model_dim",
)


def _safe_getattr(obj, attr, default=None):
    """Get attribute without triggering ComfyUI model_config __getattr__ warnings."""
    try:
        d = object.__getattribute__(obj, "__dict__")
        if attr in d:
            return d[attr]
    except (AttributeError, TypeError):
        pass
    for cls in type(obj).__mro__:
        if attr in cls.__dict__:
            v = cls.__dict__[attr]
            if isinstance(v, property):
                try:
                    return v.fget(obj)
                except Exception:
                    pass
            elif not callable(v) and not isinstance(v, (staticmethod, classmethod)):
                return v
    return default


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
            val = _safe_getattr(o, attr)
            if isinstance(val, int) and 64 <= val <= 32768:
                return val
        for cfg_attr in ("config", "model_config"):
            cfg = _safe_getattr(o, cfg_attr)
            if cfg:
                for attr in _DIM_ATTRS:
                    val = _safe_getattr(cfg, attr)
                    if isinstance(val, int) and 64 <= val <= 32768:
                        return val
    return None


def get_model_details(model):
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

    mt = getattr(inner, "model_type", None)
    if mt is not None:
        try:
            lines.append(f"type:   {mt.name}")
        except Exception:
            lines.append(f"type:   {mt}")

    dim = _find_dim(inner) or 0
    if dim:
        lines.append(f"dim:    {dim}")

    p = _count_params(inner)
    if p:
        lines.append(f"params: {p}")

    lines.append(f"format: {fmt}")

    return lines, class_name, dim


# ---------------------------------------------------------------------------
# Workflow graph traversal
# ---------------------------------------------------------------------------

_MUTED = 2  # ComfyUI node mode: Never / muted
_label_counters: dict = {}  # {unique_id: {"index": int, "labels_hash": int}}


def get_upstream_label(extra_pnginfo, unique_id, input_name, depth=1):
    """
    Return the title of the node connected to `input_name` of node `unique_id`,
    traversing `depth` levels up the workflow graph.

    - depth=1 : label of the direct parent
    - depth=N : navigates N-1 levels via the first active input, then collects
                labels of ALL active inputs at that level.
    - When multiple active inputs are found (e.g. Make List), labels cycle one
      per execution via an internal counter that resets on list change.
    - Muted nodes (mode=2) are excluded from traversal and collection.
    """
    workflow      = (extra_pnginfo or {}).get("workflow") or {}
    nodes_map     = {str(n["id"]): n for n in workflow.get("nodes", [])}
    links_map     = {str(l[0]): l  for l in workflow.get("links", [])}
    display_names = _comfy_nodes.NODE_DISPLAY_NAME_MAPPINGS

    def node_label(n):
        if not n:
            return ""
        title = n.get("title") or ""
        return title if title else display_names.get(n.get("type", ""), n.get("type", ""))

    def is_active(n):
        return bool(n) and n.get("mode", 0) != _MUTED

    def first_active_upstream(n):
        for inp in (n or {}).get("inputs", []):
            if inp.get("link") is not None:
                lnk = links_map.get(str(inp["link"]))
                if lnk:
                    candidate = nodes_map.get(str(lnk[1]))
                    if is_active(candidate):
                        return candidate
        return None

    # Find the node connected to our named input (1 hop)
    this_node   = nodes_map.get(str(unique_id), {})
    source_node = None
    for inp in this_node.get("inputs", []):
        if inp.get("name") == input_name and inp.get("link") is not None:
            lnk = links_map.get(str(inp["link"]))
            if lnk:
                source_node = nodes_map.get(str(lnk[1]))
            break

    if depth == 1:
        return node_label(source_node)

    # Navigate depth-2 more levels via first active input each time
    current = source_node
    for _ in range(depth - 2):
        current = first_active_upstream(current)
        if not current:
            return ""

    if not current:
        return ""

    # Collect labels of ACTIVE connected inputs only
    labels = []
    for inp in current.get("inputs", []):
        if inp.get("link") is not None:
            lnk = links_map.get(str(inp["link"]))
            if lnk:
                upstream = nodes_map.get(str(lnk[1]))
                if is_active(upstream):
                    labels.append(node_label(upstream))

    if not labels:
        return node_label(current)

    if len(labels) == 1:
        return labels[0]

    # Multiple active inputs: cycle through labels one per execution
    uid         = str(unique_id)
    labels_hash = hash(tuple(labels))
    state       = _label_counters.setdefault(uid, {"index": 0, "labels_hash": None})

    if state["labels_hash"] != labels_hash or state["index"] >= len(labels):
        state["index"]       = 0
        state["labels_hash"] = labels_hash

    label          = labels[state["index"]]
    state["index"] += 1
    return label
