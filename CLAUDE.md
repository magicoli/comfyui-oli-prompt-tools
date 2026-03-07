# CLAUDE.md

Guidance for Claude Code when working in this repository.

For node documentation (what each node does, inputs/outputs, examples), refer to **README.md** — it is the single source of truth for that.

## Project overview

A ComfyUI custom node pack. No build step, no test suite, no linting config.

**Dev cycle:** edit files → restart ComfyUI or reload custom nodes via ComfyUI Manager → test manually in the UI.

## Architecture

### Python nodes

Each node lives in its own file (`lora_loader.py`, `mega_string_list.py`, …) and exports:
- A node class with `INPUT_TYPES()`, `RETURN_TYPES`, `RETURN_NAMES`, `FUNCTION`, `CATEGORY`
- `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` at module level

`__init__.py` merges all those dicts for ComfyUI discovery. To add a node: create `newnode.py`, import its dicts in `__init__.py`.

**Key patterns:**
- `_AnyType(str)` with `__ne__` always `False` — wildcard input type accepted by any connection
- `_FlexibleInputs(dict)` with `__contains__` always `True` — lets dynamic `lora_N` / `string_N` kwargs reach `execute(**kwargs)`
- `INPUT_IS_LIST = True` — ComfyUI delivers the full list without batch-expanding; used by `OliMegaStringList`
- `IS_CHANGED` returning `float("nan")` — forces re-execution every queue (used when output depends on graph structure, not just values)
- `OUTPUT_NODE = True` with `{"ui": {…}, "result": (…)}` — sends display data to the JS frontend

### Frontend (`web/`)

ES modules, no bundler. Files import directly from each other or from ComfyUI's `scripts/`.

- **`oli_widgets_common.js`** — shared drawing and drag utilities (constants, hit-test, row background, toggle pill, delete button, disabled overlay, `startRowDrag`, `installDragForeground`). Import from here rather than duplicating.
- **`oli_lora_loader.js`** — `OliLoraRowWidget`, LoRA search panel, compat colouring via `onExecuted`
- **`oli_mega_string_list.js`** — `OliStringRowWidget`, per-row connector bullets, `configure` restore logic

When adding shared display or interaction logic, put it in `oli_widgets_common.js`.

### Shared Python utilities (`utils.py`)

- `get_model_details(model)` — extracts class name and hidden dim from any ComfyUI model object
- `get_upstream_label(extra_pnginfo, unique_id, input_name, depth)` — walks the workflow JSON to find the title of an upstream node

## Working conventions

### Git branches
- Work on the `dev` branch; `master` is stable and public
- Only the user merges dev → master and pushes

### Git commits
- Write short, descriptive imperative messages (English)
- Prefix with `(untested)` when the change hasn't been verified in ComfyUI yet; reword after a successful test
- Never claim co-authorship in commit messages or anywhere else
- **Never push to any remote.** Only the user pushes. Never suggest or offer to push either.

### Testing
No automated tests. Verify by reloading in ComfyUI and exercising the affected node(s) manually.
If a change is committed before testing, mark it `(untested)` so it's easy to find in the log.

### Documentation
README.md documents what nodes do for users. CLAUDE.md documents how to work on the code. Keep them focused on their respective roles.
