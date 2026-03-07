# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A ComfyUI custom node pack. No build step, no test suite, no linting config. Development cycle: edit files, restart ComfyUI (or reload custom nodes via ComfyUI Manager).

To install/run: drop this directory into `ComfyUI/custom_nodes/` and start ComfyUI. No pip installs required — all dependencies (torch, safetensors) come with ComfyUI.

## Architecture

### Python node structure

Each node is one file (`prompt_line_pick.py`, `lora_loader.py`, etc.) containing:
- A node class with class-level attributes: `INPUT_TYPES()`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, `CATEGORY`
- `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` dicts at module level

`__init__.py` merges all those dicts into the top-level mappings that ComfyUI discovers. To add a new node: create `newnode.py`, then import both dicts into `__init__.py`.

### Key patterns

**Wildcard input type** — `_AnyType(str)` with `__ne__` always returning `False` makes ComfyUI accept any connection type. Used in `lora_loader.py` and `node_label.py`.

**Dynamic widget inputs** — `_FlexibleInputs(dict)` overrides `__contains__` to always return `True`, allowing dynamically-named `lora_N` kwargs to reach the Python `execute()` via `**kwargs` (see `lora_loader.py`).

**Frontend data return** — Nodes with `OUTPUT_NODE = True` can return `{"ui": {...}, "result": (...)}` instead of a plain tuple. The `ui` dict is sent to the JS frontend; `result` is the normal node output. Used by `OliLoraLoader` (compat status), `OliModelInfo`, and `OliVideoFrameLimit` (display text).

**Always re-execute** — `IS_CHANGED` returning `float("nan")` forces ComfyUI to run the node on every queue. Used by `OliModelInfo` and `OliNodeLabel` since their output depends on the workflow graph structure (via `EXTRA_PNGINFO`), not just input values.

**Workflow graph traversal** — `utils.get_upstream_label()` receives `EXTRA_PNGINFO` (the full workflow JSON) and `UNIQUE_ID` (this node's ID) as hidden inputs, then walks the `nodes`/`links` arrays to find upstream node titles. This is how `OliNodeLabel` and `OliModelInfo` read the title of whatever node is connected to them.

### Shared utilities (`utils.py`)

- `get_model_details(model)` — introspects any ComfyUI model object (MODEL/CLIP/VAE) to extract class name and hidden dimension. Uses `_safe_getattr` to avoid triggering ComfyUI's noisy `__getattr__` warnings on model config objects.
- `get_upstream_label(extra_pnginfo, unique_id, input_name, depth)` — workflow graph traversal as described above.

### Frontend (`web/`)

- `oli_prompt_tools.js` — registers extensions for `OliPromptLinePick` (adds "get values from COMBO link" button), `OliModelInfo`, and `OliVideoFrameLimit` (both add a read-only multiline STRING widget that displays the `ui.text` payload after execution).
- `oli_lora_loader.js` — fully custom widget (`OliLoraRowWidget`) drawn on the LiteGraph canvas. Each LoRA row is a custom widget with toggle, name, strength controls, and delete. Compat status (`ui.compat`) received in `onExecuted` colors the toggle (green=ok, red=incompatible, grey=disabled). The "➕ Add LoRA" button opens a DOM overlay search panel (`showLoraSelector`).

### LoRA compatibility check (`lora_loader.py`)

`_check_compat(model, lora_path)` reads only the safetensors header (no weights loaded), strips LoRA suffixes to get base key names, then checks them against `comfy.lora.model_lora_keys_unet(model.model, model_map)`. Returns `(bool, reason_str)`. Incompatible LoRAs are skipped silently (logged to console only).
