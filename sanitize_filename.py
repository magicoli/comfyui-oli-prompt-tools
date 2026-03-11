"""
OliSanitizeFilename — sanitize strings for safe use as file paths.

Whitelist approach: only safe characters survive.
  - Letters and digits (ASCII always; unicode optionally)
  - Hyphens
  - Spaces (optional — replaced when disabled)
  - Forward slashes (optional — treated as path separators)
Everything else is replaced by the configured replacement character.

Any run of 2+ consecutive separators is collapsed into one, using the
highest-priority character present:  /  >  -  >  space  >  replacement.

Inputs:
  filename       — the name to sanitize (may contain path separators)
  folder         — optional folder prefix (always allows slashes)
  extension      — optional file extension (leading dot stripped)

Outputs:
  prefix   — folder/filename without extension (feed to Save Image etc.)
  path     — folder/filename.ext
  filename — filename.ext (no folder)
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_to_str(val, joiner):
    """Convert a str, list, or nested list to a single joined string."""
    if val is None:
        return ""
    if isinstance(val, list):
        parts = []
        for item in val:
            s = _flatten_to_str(item, joiner)
            if s:
                parts.append(s)
        return joiner.join(parts)
    return str(val)

def _transliterate_to_ascii(text: str) -> str:
    """Strip diacritics via NFKD decomposition (à→a, é→e, ü→u, ñ→n, etc.).

    Works well for Latin-script languages.  Characters with no ASCII
    decomposition (e.g. ideographs, ß, æ) are dropped silently.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _safe_replacement(r: str) -> str:
    """Validate replacement: must be a single non-alphanumeric ASCII char."""
    if len(r) == 1 and r.isascii() and not r.isalnum() and r not in "/\\":
        return r
    return "_"


def _normalise_backslashes(text):
    r"""Handle backslash sequences before the character filter.

    - ``\\`` (two consecutive backslashes) → ``/``  (path separator)
    - ``\`` followed by any other char → both characters removed
    - Trailing lone ``\`` → removed
    """
    text = re.sub(r"\\(.)", lambda m: "/" if m.group(1) == "\\" else "", text, flags=re.DOTALL)
    return text.rstrip("\\")


def _filter_and_collapse(text, allow_spaces, allow_slash, allow_unicode, repl):
    """Replace disallowed characters and collapse consecutive separators.

    After the character-level filter the text contains only alphanumeric
    characters, hyphens, and (optionally) spaces, slashes, and the
    replacement character.  Any run of 2+ consecutive non-alphanumeric
    characters is then collapsed into the single highest-priority separator
    present in that run:  ``/`` > ``-`` > *space* > *repl*.
    """
    # Normalise all whitespace (newlines, tabs, …) to plain spaces
    text = re.sub(r"[\n\r\t]+", " ", text)

    # When keeping unicode, normalise to NFC so that combining marks
    # (e + U+0301 → é) merge into single alphanumeric codepoints.
    if allow_unicode:
        text = unicodedata.normalize("NFC", text)

    # ---- character-level filter ----
    out: list[str] = []
    for ch in text:
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif allow_unicode and not ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch == "-":
            out.append(ch)
        elif ch == " ":
            out.append(" " if allow_spaces else repl)
        elif ch == "/" and allow_slash:
            out.append("/")
        else:
            out.append(repl)
    text = "".join(out)

    # ---- collapse 2+ consecutive separator characters ----
    # Build a character class covering every separator that can appear.
    sep_chars = {repl, "-"}
    if allow_spaces:
        sep_chars.add(" ")
    if allow_slash:
        sep_chars.add("/")
    # Escape each char individually and build [...]
    sep_class = "[" + "".join(re.escape(c) for c in sorted(sep_chars)) + "]"

    def _pick_winner(m):
        s = m.group()
        if allow_slash and "/" in s:
            return "/"
        if "-" in s:
            return "-"
        if allow_spaces and " " in s:
            return " "
        return repl

    text = re.sub(f"{sep_class}{{2,}}", _pick_winner, text)

    return text


def _strip_edges(name, repl):
    """Strip separator / dot characters from edges of a path component."""
    if not name:
        return name
    return name.strip(f" .-{repl}")


def _truncate_bytes(text, max_length, repl):
    """Truncate to *max_length* UTF-8 bytes, keeping valid characters."""
    if max_length <= 0 or len(text.encode("utf-8")) <= max_length:
        return text
    truncated = text.encode("utf-8")[:max_length].decode("utf-8", errors="ignore")
    return _strip_edges(truncated, repl)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class OliSanitizeFilename:
    """Sanitize a string for safe use as a filename or file path."""

    CATEGORY = "Oli/utils"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "filename": (_any, {}),
                "folder": (_any, {}),
                "extension": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                        "tooltip": "File extension (with or without leading dot).",
                    },
                ),
                "allow_spaces": (
                    "BOOLEAN",
                    {"default": True, "label_on": "true", "label_off": "→ _"},
                ),
                "allow_slash": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "true",
                        "label_off": "→ _",
                        "tooltip": "Preserve / as path separator in the filename input.",
                    },
                ),
                "allow_unicode": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "true",
                        "label_off": "→ ascii",
                        "tooltip": "If disabled, diacritics are transliterated via NFKD: "
                                   "à→a, é→e, ü→u, etc.",
                    },
                ),
                "max_length": (
                    "INT",
                    {
                        "default": 240,
                        "min": 0,
                        "max": 4096,
                        "step": 1,
                        "tooltip": "Max bytes for the filename component (0 = no limit). "
                                   "Default 240 leaves room for the counter and extension "
                                   "that save nodes typically append. OS limit is 255 bytes.",
                    },
                ),
                "replacement": (
                    "STRING",
                    {
                        "default": "_",
                        "tooltip": "Character used in place of disallowed characters. "
                                   "Must be a single non-alphanumeric ASCII character; "
                                   "invalid values fall back to _.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prefix", "path", "filename")
    OUTPUT_NODE = True
    FUNCTION = "execute"

    def execute(
        self,
        filename="",
        folder="",
        extension: str = "",
        allow_spaces: bool = True,
        allow_slash: bool = True,
        allow_unicode: bool = False,
        max_length: int = 240,
        replacement: str = "_",
    ):
        repl = _safe_replacement(replacement)

        # --- Flatten list inputs (hidden bonus) ---
        filename = _flatten_to_str(filename, repl)
        folder = _flatten_to_str(folder, "/")

        # --- Transliterate early if needed ---
        if not allow_unicode:
            filename = _transliterate_to_ascii(filename)
            folder = _transliterate_to_ascii(folder)

        # --- Handle backslash sequences ---
        filename = _normalise_backslashes(filename)
        folder = _normalise_backslashes(folder)

        # --- Sanitize filename input ---
        filename = _filter_and_collapse(
            filename, allow_spaces, allow_slash, allow_unicode, repl,
        )

        # Split the filename into path components when slashes are kept
        if allow_slash and "/" in filename:
            parts = filename.split("/")
            parts = [_strip_edges(p, repl) for p in parts]
            parts = [p for p in parts if p]
            if parts:
                name_part = parts[-1]
                extra_folder_parts = parts[:-1]
            else:
                name_part = ""
                extra_folder_parts = []
        else:
            name_part = filename
            extra_folder_parts = []

        name_part = _strip_edges(name_part, repl)
        name_part = _truncate_bytes(name_part, max_length, repl)

        # --- Sanitize folder input (always allow slashes) ---
        folder = _filter_and_collapse(folder, allow_spaces, True, allow_unicode, repl)
        folder_parts = folder.split("/")
        folder_parts = [_strip_edges(p, repl) for p in folder_parts]
        folder_parts = [p for p in folder_parts if p]

        # Merge folder sources
        all_folder_parts = folder_parts + extra_folder_parts
        folder_str = "/".join(all_folder_parts)

        # --- Clean extension (keep only alphanumeric) ---
        ext = extension.strip().lstrip(".")
        ext = "".join(c for c in ext if c.isalnum())

        # --- Build outputs ---
        prefix = f"{folder_str}/{name_part}" if folder_str else name_part

        if ext:
            filename_out = f"{name_part}.{ext}"
            path = f"{prefix}.{ext}"
        else:
            filename_out = name_part
            path = prefix

        # --- Send the actual replacement char to the frontend for labels ---
        return {
            "ui": {"repl": [repl]},
            "result": (prefix, path, filename_out),
        }


NODE_CLASS_MAPPINGS        = {"OliSanitizeFilename": OliSanitizeFilename}
NODE_DISPLAY_NAME_MAPPINGS = {"OliSanitizeFilename": "Sanitize Filename (Oli)"}
