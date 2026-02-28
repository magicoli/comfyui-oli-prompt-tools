# Oli Prompt Tools

Custom ComfyUI nodes for prompt selection and video workflow utilities.

## Nodes

- **Prompt Line Pick**: A seed-driven fork of [easy promptLine](https://github.com/yolain/ComfyUI-Easy-Use).
- **Video Frame Limit**: Caps video generation duration to avoid VRAM out-of-memory crashes.

### Prompt Line Pick (Oli)

Replaces `start_index + max_rows` with a single **seed** input. The selected line is determined by `sha256(seed:node_id) % len(lines)`, which gives:

- **Uniform distribution** — every line has an equal probability regardless of list length
- **Full independence** — multiple instances in the same workflow each pick independently, even with the same seed, because the node ID is used as a channel discriminator
- **No prime modulo management** — the sha256 hash eliminates correlation between lists of similar length

Preserves all original features: COMBO output, "get values from COMBO link" button.

**Inputs**

| Input | Type | Description |
|---|---|---|
| prompt | STRING | One item per line |
| seed | INT | Global workflow seed |
| remove_empty_lines | BOOLEAN | Strip blank lines before picking |

**Outputs:** `STRING`, `COMBO`

---

### Video Frame Limit (Oli)

Caps video generation duration to avoid VRAM out-of-memory crashes.

The frame budget is derived from first principles rather than empirical constants:

```
bytes_per_frame = TENSOR_COPIES × (width÷8) × (height÷8) × hidden_dim × 2
max_frames      = total_vram × safety_margin ÷ bytes_per_frame
```

Where `TENSOR_COPIES = 5` (Q, K, V, attention output, residual activations) and `hidden_dim` is **auto-detected** from the connected model. Uses **total VRAM** rather than free VRAM — ComfyUI offloads weights layer-by-layer so peak activation memory scales with total VRAM, not the remainder after model loading.

The node displays detected VRAM, hidden dim, requested frames and capped frames directly in the canvas after each execution.

**Inputs**

| Input | Type | Description |
|---|---|---|
| width / height | INT | Generation dimensions |
| fps | FLOAT | Frames per second (default 16) |
| duration | FLOAT | Requested duration in seconds (default 10) |
| safety_margin | FLOAT | Fraction of total VRAM to budget (default 0.95) |
| model | MODEL | Optional — enables hidden_dim auto-detection |

**Outputs:** `width` (INT), `height` (INT), `frames` (INT), `fps` (FLOAT), `duration` (FLOAT)

The node displays detected VRAM, model name, hidden dim, requested and capped frames directly in the canvas after each execution — making it usable as a standalone config panel.

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/magicoli/comfyui-oli-prompt-tools
```

Restart ComfyUI. No additional dependencies required.

## License

[GNU Affero General Public License v3.0](LICENSE)
