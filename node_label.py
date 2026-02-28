"""
OliNodeLabel — passes any value through and outputs the upstream node's title.

depth=1 : label of the direct parent node
depth=N : navigates N-1 levels following the first connected input, then
          collects labels of ALL active (non-muted) connected inputs at that level.

When the target level has multiple active inputs (e.g. a Make List node), the
labels are returned one per execution in order, cycling through the list.
Muted nodes are ignored both during traversal and during label collection.
"""

import nodes as _comfy_nodes


class _AnyType(str):
    def __ne__(self, other):
        return False

_any = _AnyType("*")

_MUTED = 2  # ComfyUI node mode: Never / muted


class OliNodeLabel:
    _counters: dict = {}  # {unique_id: {"index": int, "labels_hash": int}}

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
            """Follow the first non-muted connected input of node n."""
            for inp in (n or {}).get("inputs", []):
                if inp.get("link") is not None:
                    lnk = links_map.get(str(inp["link"]))
                    if lnk:
                        candidate = nodes_map.get(str(lnk[1]))
                        if is_active(candidate):
                            return candidate
            return None

        # Find the node connected to our "node" input (1 hop)
        this_node   = nodes_map.get(str(unique_id), {})
        source_node = None
        for inp in this_node.get("inputs", []):
            if inp.get("name") == "node" and inp.get("link") is not None:
                lnk = links_map.get(str(inp["link"]))
                if lnk:
                    source_node = nodes_map.get(str(lnk[1]))
                break

        # depth=1: return the direct parent's label
        if depth == 1:
            return (node, node_label(source_node))

        # depth>1: navigate depth-2 more levels via first active input each time
        current = source_node
        for _ in range(depth - 2):
            current = first_active_upstream(current)
            if not current:
                return (node, "")

        if not current:
            return (node, "")

        # Collect labels of ACTIVE connected inputs only (muted nodes excluded)
        labels = []
        for inp in current.get("inputs", []):
            if inp.get("link") is not None:
                lnk = links_map.get(str(inp["link"]))
                if lnk:
                    upstream = nodes_map.get(str(lnk[1]))
                    if is_active(upstream):
                        labels.append(node_label(upstream))

        # No active upstream inputs: return this node's own label
        if not labels:
            return (node, node_label(current))

        # Single active upstream input: return it directly
        if len(labels) == 1:
            return (node, labels[0])

        # Multiple active inputs: cycle through labels one per execution.
        # The counter resets when the active-labels set changes (node muted /
        # unmuted, workflow edited) or when a full cycle is complete.
        uid         = str(unique_id)
        labels_hash = hash(tuple(labels))
        state       = OliNodeLabel._counters.setdefault(uid, {"index": 0, "labels_hash": None})

        if state["labels_hash"] != labels_hash or state["index"] >= len(labels):
            state["index"]       = 0
            state["labels_hash"] = labels_hash

        label          = labels[state["index"]]
        state["index"] += 1

        return (node, label)


NODE_CLASS_MAPPINGS        = {"OliNodeLabel": OliNodeLabel}
NODE_DISPLAY_NAME_MAPPINGS = {"OliNodeLabel": "Node Label (Oli)"}
