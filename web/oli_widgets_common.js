/**
 * oli_widgets_common.js — Shared drawing and drag utilities for Oli custom widgets.
 *
 * Imported by oli_lora_loader.js and oli_mega_string_list.js.
 * Keeps visual consistency and avoids duplicating display logic.
 */

import { app } from "../../scripts/app.js";

// ── Shared constants ──────────────────────────────────────────────────────────

export const ROW_H = LiteGraph.NODE_WIDGET_HEIGHT ?? 20;
export const PAD   = 15;   // right margin — matches standard ComfyUI widget margins
export const PAD_L = 15;   // left margin

// ── Hit-test helper ───────────────────────────────────────────────────────────

/** True if pos is inside the rectangle [x, y, w, h]. */
export function hit(pos, x, y, w, h) {
	return pos[0] >= x && pos[0] <= x + w && pos[1] >= y && pos[1] <= y + h;
}

// ── Drawing helpers ───────────────────────────────────────────────────────────
// All helpers assume ctx.save() / ctx.restore() is handled by the caller's draw()
// method, except drawDisabledOverlay() which manages its own save/restore.

/**
 * Draw the row background rounded rect.
 * @param {string} color - fill colour (e.g. "#252525" or LiteGraph.WIDGET_BGCOLOR)
 */
export function drawRowBackground(ctx, posY, width, height, color) {
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.roundRect(PAD_L, posY + 1, width - PAD_L - PAD, height - 2, 3);
	ctx.fill();
}

/**
 * Draw the drag handle ≡.
 * @returns {{ rect: number[], nextX: number }} hit-rect and next x position
 */
export function drawHandle(ctx, x, posY, mid, height, font) {
	const HW = 14;
	ctx.fillStyle = "#777";
	ctx.font = font;
	ctx.textAlign = "center";
	ctx.textBaseline = "middle";
	ctx.fillText("≡", x + HW / 2, mid);
	return {
		rect:  [x, posY + 1, HW, height - 2],
		nextX: x + HW + 4,
	};
}

/**
 * Draw the on/off toggle pill.
 * @param {boolean}           on     - whether the row is enabled
 * @param {boolean|undefined} compat - undefined/true = ok (green), false = incompatible (red)
 * @returns {{ rect: number[], nextX: number }}
 */
export function drawTogglePill(ctx, x, mid, height, on, compat = undefined) {
	const TW = Math.round(height * 1.4), TH = Math.round(height * 0.6);
	const ty = mid - TH / 2;
	if (!on) {
		ctx.fillStyle = "#555";
	} else if (compat === false) {
		ctx.fillStyle = "#7a3030";    // incompatible → red
	} else {
		ctx.fillStyle = "#4a7a4a";    // enabled (compat ok or unknown)
	}
	ctx.beginPath();
	ctx.roundRect(x, ty, TW, TH, TH / 2);
	ctx.fill();
	ctx.fillStyle = "#ddd";
	const kx = on ? x + TW - TH / 2 - 1 : x + TH / 2 + 1;
	ctx.beginPath();
	ctx.arc(kx, mid, TH / 2 - 1, 0, Math.PI * 2);
	ctx.fill();
	return {
		rect:  [x, ty, TW, TH],
		nextX: x + TW + 6,
	};
}

/**
 * Draw the delete button — ✕ text only, no background.
 * @returns {{ rect: number[], leftX: number }} hit-rect and left edge x (for placing controls to the left)
 */
export function drawDeleteBtn(ctx, width, posY, mid, height, fsize) {
	const DW = 14;
	const dx = width - PAD - 6 - DW;
	ctx.fillStyle = "#f99";
	ctx.font = `${fsize - 1}px sans-serif`;
	ctx.textAlign = "center";
	ctx.textBaseline = "middle";
	ctx.fillText("✕", dx + DW / 2, mid);
	return {
		rect:  [dx, posY + 2, DW, height - 4],
		leftX: dx,
	};
}

/**
 * Draw a semi-transparent overlay to dim a row (used when the node's enable toggle is off).
 * Manages its own ctx.save/restore so it can be called before or after the outer restore.
 */
export function drawDisabledOverlay(ctx, posY, width, height) {
	ctx.save();
	ctx.fillStyle = "rgba(0,0,0,0.65)";
	ctx.beginPath();
	ctx.roundRect(PAD_L, posY + 1, width - PAD_L - PAD, height - 2, 3);
	ctx.fill();
	ctx.restore();
}

// ── Drag-to-reorder ───────────────────────────────────────────────────────────

/**
 * Start a drag-to-reorder operation for a row widget.
 * Rows move in real time on each pointermove (live preview).
 * afterReorder is called once on pointerup (e.g. to rename slots).
 *
 * @param {object}    node          - LiteGraph node
 * @param {object}    widget        - The widget row being dragged
 * @param {Function}  getRowWidgets - () => widget[]  ordered list of draggable rows
 *                                    (should exclude any non-draggable placeholder row)
 * @param {Function}  [afterReorder]- Optional callback after drop
 */
export function startRowDrag(node, widget, getRowWidgets, afterReorder) {
	node._dragWidget   = widget;
	node._dragCurrentY = widget.last_y;

	const canvasEl = app.canvas.canvas;

	function toNodeLocalY(ev) {
		const rect  = canvasEl.getBoundingClientRect();
		const scale = app.canvas.ds.scale;
		const off   = app.canvas.ds.offset;
		return (ev.clientY - rect.top) / scale - off[1] - node.pos[1];
	}

	function onMove(ev) {
		if (!node._dragWidget) return;
		ev.stopPropagation();
		const currentY = toNodeLocalY(ev);
		node._dragCurrentY = currentY;
		_liveReorder(node, currentY, getRowWidgets);
		node.setDirtyCanvas(true);
	}

	function onUp(ev) {
		ev.stopPropagation();
		canvasEl.removeEventListener("pointermove", onMove, true);
		canvasEl.removeEventListener("pointerup",   onUp,   true);
		if (node._dragWidget) {
			afterReorder?.();
			node._dragWidget   = null;
			node._dragCurrentY = null;
		}
		node.setDirtyCanvas(true, true);
	}

	canvasEl.addEventListener("pointermove", onMove, true);
	canvasEl.addEventListener("pointerup",   onUp,   true);
}

/**
 * Move the dragged widget to its live target position in node.widgets.
 * getRowWidgets() should exclude any non-draggable placeholder at the end
 * so that the dragged widget always lands before it.
 */
function _liveReorder(node, currentY, getRowWidgets) {
	const dragWidget = node._dragWidget;
	if (!dragWidget) return;

	const rowWidgets = getRowWidgets();
	const srcIdx = node.widgets.indexOf(dragWidget);
	if (srcIdx < 0) return;

	// First row whose midpoint is below the cursor becomes the insertion target
	let insertBefore = null;
	for (const w of rowWidgets) {
		if (w === dragWidget) continue;
		if (currentY < w.last_y + ROW_H / 2) {
			insertBefore = w;
			break;
		}
	}

	node.widgets.splice(srcIdx, 1);

	let dstIdx;
	if (insertBefore !== null) {
		dstIdx = Math.max(0, node.widgets.indexOf(insertBefore));
	} else {
		// Cursor past all known rows: insert just after the last one.
		// Because getRowWidgets excludes the placeholder, this keeps the
		// placeholder at the very end of node.widgets.
		const lastKnown = rowWidgets.filter((w) => w !== dragWidget).pop();
		dstIdx = lastKnown ? node.widgets.indexOf(lastKnown) + 1 : node.widgets.length;
	}
	node.widgets.splice(dstIdx, 0, dragWidget);
}

// ── Node-level drag wiring ────────────────────────────────────────────────────

/**
 * Install onDrawForeground to highlight the dragged row during live reorder.
 * Because the row moves in real time (via _liveReorder), last_y already
 * reflects its current position — we just draw a coloured border around it.
 * Chains with any existing onDrawForeground on the nodeType.
 *
 * The second parameter is kept for API compatibility but is no longer used.
 */
export function installDragForeground(nodeType, _unused) {
	const _prev = nodeType.prototype.onDrawForeground;
	nodeType.prototype.onDrawForeground = function (ctx) {
		_prev?.apply(this, arguments);
		if (!this._dragWidget) return;

		const w = this._dragWidget;
		ctx.save();
		ctx.strokeStyle = "#4af";
		ctx.lineWidth   = 2;
		ctx.beginPath();
		ctx.roundRect(PAD_L, w.last_y + 1, this.size[0] - PAD_L - PAD, ROW_H - 2, 3);
		ctx.stroke();
		ctx.restore();
	};
}
