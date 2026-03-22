"""
OliMegaStringList — Mega String List node.

Collects strings from multiple sources into a unified list:
  - optional_prompt_list (LIST) — always included when enable=True, or
    returned unchanged when enable=False (pass-through / chaining)
  - per-row string slots (string1, string2, …) — each slot is a canvas
    widget row with a bullet connector; accepts typed text (widget dict
    {on, text}) or any connected node output (STRING, LIST, etc.)

INPUT_IS_LIST = True prevents ComfyUI from batch-expanding LIST outputs
connected to our string slots — we receive the full list at once and
insert it at the correct position in the result.

Items in the text widget are separated by NEWLINES (one item per line).
The delimiter is only used to JOIN items in the `string` output.
Escape sequences are decoded at runtime (\\n → real newline, etc.).

Strings equal to "none" (case-insensitive) are filtered from all sources
— SDXL Prompt Styler empty/ignore sentinel.

Outputs:
  prompt_list    — LIST for PromptLinePick / easy promptList chaining
  prompt_strings — STRING (output list), same format as easy promptList
  num_strings    — INT count of items in the combined list
  string         — STRING items joined by delimiter (single value)
"""


class _AnyType(str):
    """A type string that compares equal to any other type."""

    def __ne__(self, other):
        return False


_any = _AnyType("*")


class _FlexibleInputs(dict):
    """Dict that accepts any key — lets dynamic string slot inputs
    (string1, string2, …) pass ComfyUI validation and reach execute(**kwargs).
    """

    def __init__(self, fallback_type, data=None):
        self._fallback = fallback_type
        super().__init__(data or {})

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return super().__getitem__(key) if key in self.keys() else (self._fallback,)


class OliMegaStringList:
    """Combine strings from multiple sources into a unified list."""

    CATEGORY = "Oli/prompt"

    # Prevents ComfyUI from batch-expanding list inputs; we handle the full
    # list ourselves so that it can be inserted at the correct slot position.
    INPUT_IS_LIST = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": _FlexibleInputs(_any, {
                "optional_prompt_list": ("LIST", {}),
                "enable":          ("BOOLEAN", {"default": True, "label_on": "enabled", "label_off": "pass-through"}),
                "delimiter":       ("STRING",  {"default": ", "}),
                "_disabled_slots": ("STRING",  {"default": ""}),
                # string1, string2, … are added dynamically by the JS frontend.
            }),
        }

    RETURN_TYPES   = ("LIST", "STRING", "INT", "STRING")
    RETURN_NAMES   = ("prompt_list", "prompt_strings", "num_strings", "string")
    # string output (index 3): OUTPUT_IS_LIST=True + 1-element list return
    # so ComfyUI iterates once and downstream nodes receive a plain STRING.
    # (With INPUT_IS_LIST=True, OUTPUT_IS_LIST=False would wrap the value in
    # a list that some nodes reject as a list instead of a scalar.)
    # string output (index 3): OUTPUT_IS_LIST=True + 1-element list so downstream
    # nodes receive a plain STRING scalar, not a list.
    OUTPUT_IS_LIST = (False, True, False, True)
    FUNCTION       = "execute"

    def execute(
        self,
        enable=None,
        delimiter=None,
        optional_prompt_list=None,
        **kwargs,
    ):
        # INPUT_IS_LIST=True wraps scalar widget values in lists; unwrap them.
        enable    = _first(_ensure_list(enable),    default=True)
        delimiter = _first(_ensure_list(delimiter), default=", ")
        decoded_delim = _decode_escapes(delimiter)

        # Disabled slots: comma-separated slot names toggled off in the UI.
        disabled_raw = _first(_ensure_list(kwargs.pop("_disabled_slots", None)), default="")
        disabled = set(s.strip() for s in disabled_raw.split(",") if s.strip())

        # When disabled: pass through optional_prompt_list unchanged.
        if not enable:
            result = []
            for item in _ensure_list(optional_prompt_list):
                result.extend(_val_to_strings(item, decoded_delim))
            result = _filter_none(result)
            num = len(result)
            return (result, result, num, [decoded_delim.join(result)])

        result = []

        # 1. optional_prompt_list (chaining input; INPUT_IS_LIST may wrap it)
        for item in _ensure_list(optional_prompt_list):
            result.extend(_val_to_strings(item, decoded_delim))

        # 2. Per-row string slots — sorted by numeric suffix = widget order
        for key in _sorted_slot_keys(kwargs, "string"):
            if key in disabled:
                continue
            slot_val = kwargs[key]
            for val in _ensure_list(slot_val):
                result.extend(_val_to_strings(val, decoded_delim))

        result = _filter_none(result)
        num = len(result)
        # string output: 1-element list so OUTPUT_IS_LIST=True passes it as a
        # single STRING to downstream nodes (see OUTPUT_IS_LIST comment above).
        return (result, result, num, [decoded_delim.join(result)])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _val_to_strings(val, decoded_delim=""):
    """Recursively convert any input value to a flat list of strings."""
    if val is None:
        return []
    if isinstance(val, dict):
        # Unconnected widget: {on: bool, text: str}
        if not val.get("on", True):
            return []
        text = val.get("text", "")
        return _split_text(text, decoded_delim) if text.strip() else []
    if isinstance(val, list):
        out = []
        for item in val:
            out.extend(_val_to_strings(item, decoded_delim))
        return out
    # Scalar (str, int, …) — skip blank values
    s = str(val)
    return [s] if s.strip() else []


def _split_text(text, delimiter):
    """Split text by delimiter, stripping and filtering empty parts.

    If the text starts with the delimiter (e.g. absolute path '/foo' with
    delimiter '/'), the whole text is returned as a single item to avoid
    silently discarding the leading character.
    """
    if not delimiter:
        stripped = text.strip()
        return [stripped] if stripped else []
    # Leading delimiter → treat whole value as one item (e.g. absolute path)
    if text.lstrip().startswith(delimiter):
        stripped = text.strip()
        return [stripped] if stripped else []
    return [p.strip() for p in text.split(delimiter) if p.strip()]


def _ensure_list(val):
    """Wrap a non-list value in a list; return [] for None."""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _first(lst, default=None):
    """Return the first item of a list, or default if empty."""
    return lst[0] if lst else default


def _sorted_slot_keys(mapping, prefix):
    """Return keys matching prefix+digits, sorted numerically by suffix."""
    pairs = []
    for key in mapping:
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix):]
        if suffix.isdigit():
            pairs.append((int(suffix), key))
    pairs.sort()
    return [key for _, key in pairs]


def _decode_escapes(s):
    r"""Decode Python string escape sequences (\n → newline, \t → tab, …)."""
    if not s:
        return s
    try:
        return s.encode("raw_unicode_escape").decode("unicode_escape")
    except Exception:
        return s


def _filter_none(lst):
    """Remove strings equal to 'none' (case-insensitive) — SDXL sentinel."""
    return [s for s in lst if s.strip().lower() != "none"]


# ── Registrations ──────────────────────────────────────────────────────────────

NODE_CLASS_MAPPINGS        = {"OliMegaStringList": OliMegaStringList}
NODE_DISPLAY_NAME_MAPPINGS = {"OliMegaStringList": "Mega String List (Oli)"}
