/**
 * OliMegaStringList — Mega String List frontend.
 *
 * Each string row is both a canvas-drawn widget AND an input connector bullet.
 * The bullet is positioned at the widget's row Y by LiteGraph's
 * #arrangeWidgetInputSlots mechanism (triggered by inp.widget = { name }).
 * It is hidden by default and appears on hover or when connected — standard
 * ComfyUI "converted widget" behaviour.
 *
 * Each row accepts:
 *   - Typed text (widget mode, unconnected)
 *   - Any connected node output: STRING scalar, LIST of strings, etc.
 *
 * No separate list1/list2 inputs are needed — the per-row bullet handles both.
 *
 * Features:
 *   - Drag-to-reorder with blue insertion-line indicator
 *   - Always-visible empty placeholder row at end (also has a bullet)
 *   - Toggle (enable/disable individual row)
 *   - Delete (✕) — works whether row is connected or not
 *   - Serialise / restore from widgets_values
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "OliMegaStringList";
const ROW_H = LiteGraph.NODE_WIDGET_HEIGHT ?? 20;
const MIN_W = 320;
const PAD = 15;  // right margin — matches standard ComfyUI widget margins
const PAD_L = 15; // left margin — bullet at x≈10 r≈5 stays left of background

// ── Hit-test helper ───────────────────────────────────────────────────────────

function hit(pos, x, y, w, h) {
	return pos[0] >= x && pos[0] <= x + w && pos[1] >= y && pos[1] <= y + h;
}

// ── OliStringRowWidget ────────────────────────────────────────────────────────

class OliStringRowWidget {
	constructor(name) {
		this.name = name;
		this.type = "custom";
		this.y = 0;
		this.last_y = 0;
		this.options = {};

		this._value = { on: true, text: "" };

		this._rHandle = null;
		this._rToggle = null;
		this._rText = null;
		this._rDel = null;
	}

	get value() {
		return this._value;
	}
	set value(v) {
		if (v === undefined) return;
		this._value =
			v && typeof v === "object" && "text" in v
				? { on: true, text: "", ...v }
				: { on: true, text: "" };
	}

	/** True when this row has no text and no connected input. */
	_isEmpty(node) {
		if ((this._value.text ?? "").trim()) return false;
		const inp = node?.inputs?.find((i) => i.name === this.name);
		return inp ? inp.link == null : true;
	}

	computeSize(width) {
		return [width, ROW_H];
	}

	draw(ctx, node, width, posY, height) {
		this.last_y = posY;
		const mid = posY + height / 2;
		const fsize = Math.round(height * 0.6);
		const font = `${fsize}px sans-serif`;
		const empty = this._isEmpty(node);

		ctx.save();
		// ComfyUI dims connected widget-inputs via globalAlpha before calling draw().
		// We reset it here so buttons stay visually active; the text area uses
		// colour/style (italic, blue) to convey read-only state instead.
		ctx.globalAlpha = 1.0;

		// Row background — same colour and margins as standard ComfyUI widgets
		ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR ?? "#222";
		ctx.beginPath();
		ctx.roundRect(PAD_L, posY + 1, width - PAD_L - PAD, height - 2, 3);
		ctx.fill();

		if (empty) {
			// Placeholder: just hint text, no controls
			ctx.fillStyle = "#444";
			ctx.font = font;
			ctx.textAlign = "left";
			ctx.textBaseline = "middle";
			const maxW = width - PAD_L - PAD - 8;
			let phLabel = "← connect string/list or type string";
			while (ctx.measureText(phLabel).width > maxW && phLabel.length > 4) {
				phLabel = phLabel.slice(0, -4) + "…";
			}
			ctx.fillText(phLabel, PAD_L + 6, mid);
			this._rHandle = null;
			this._rToggle = null;
			this._rDel = null;
			this._rText = [
				PAD_L + 2,
				posY + 1,
				width - PAD_L - PAD - 2,
				height - 2,
			];
			ctx.restore();
			return;
		}

		const fade = this._value.on ? 1.0 : 0.4;
		let x = PAD_L + 4;

		// Drag handle  ≡
		const HW = 14;
		ctx.fillStyle = "#777";
		ctx.font = font;
		ctx.textAlign = "center";
		ctx.textBaseline = "middle";
		ctx.fillText("≡", x + HW / 2, mid);
		this._rHandle = [x, posY + 1, HW, height - 2];
		x += HW + 4;

		// Toggle pill
		const TW = Math.round(height * 1.4),
			TH = Math.round(height * 0.6);
		const tx = x,
			ty = mid - TH / 2;
		ctx.fillStyle = this._value.on ? "#4a7a4a" : "#555";
		ctx.beginPath();
		ctx.roundRect(tx, ty, TW, TH, TH / 2);
		ctx.fill();
		ctx.fillStyle = "#ddd";
		const kx = this._value.on ? tx + TW - TH / 2 - 1 : tx + TH / 2 + 1;
		ctx.beginPath();
		ctx.arc(kx, mid, TH / 2 - 1, 0, Math.PI * 2);
		ctx.fill();
		this._rToggle = [tx, ty, TW, TH];
		x += TW + 6;

		// Delete button (rightmost) — just ✕, no background
		const DW = 14;
		const dx = width - PAD - 6 - DW;
		ctx.fillStyle = "#f99";
		ctx.font = `${fsize - 1}px sans-serif`;
		ctx.textAlign = "center";
		ctx.textBaseline = "middle";
		ctx.fillText("✕", dx + DW / 2, mid);
		this._rDel = [dx, posY + 2, DW, height - 4];

		// Text content (dimmed when row is toggled off)
		ctx.globalAlpha = fade;
		const lx = x,
			lw = dx - x - 6;

		const inp = node?.inputs?.find((i) => i.name === this.name);
		const connected = inp?.link != null;

		if (connected) {
			// Show the source node's title so the user knows what's connected
			const link = app.graph.links[inp.link];
			const srcNode = link ? app.graph.getNodeById(link.origin_id) : null;
			const srcTitle = srcNode?.title ?? srcNode?.type ?? "?";
			ctx.fillStyle = "#88aacc";
			ctx.font = `italic ${fsize}px sans-serif`;
			ctx.textAlign = "left";
			ctx.textBaseline = "middle";
			let label = srcTitle;
			while (ctx.measureText(label).width > lw - 2 && label.length > 4) {
				label = label.slice(0, -4) + "…";
			}
			ctx.fillText(label, lx, mid);
			this._rText = null;
		} else {
			const hasText = (this._value.text ?? "").trim().length > 0;
			ctx.fillStyle = hasText
				? (LiteGraph.WIDGET_TEXT_COLOR ?? "#ccc")
				: "#555";
			ctx.font = font;
			ctx.textAlign = "left";
			ctx.textBaseline = "middle";
			let label = (this._value.text || "(empty — click to edit)").replace(
				/\n/g,
				" ↵ ",
			);
			while (ctx.measureText(label).width > lw - 2 && label.length > 4) {
				label = label.slice(0, -4) + "…";
			}
			ctx.fillText(label, lx, mid);
			this._rText = [lx, posY + 1, lw, height - 2];
		}

		ctx.globalAlpha = 1;

		// Dim row when node's enable widget is false
		const enableW = node.widgets?.find((w) => w.name === "enable");
		if (enableW?.value === false) {
			ctx.fillStyle = "rgba(0,0,0,0.65)";
			ctx.beginPath();
			ctx.roundRect(PAD_L, posY + 1, width - PAD_L - PAD, height - 2, 3);
			ctx.fill();
		}

		ctx.restore();
	}

	mouse(event, pos, node) {
		if (node._dragWidget && node._dragWidget !== this) return false;

		if (event.type === "pointerdown") {
			if (this._rHandle && hit(pos, ...this._rHandle)) {
				_startDrag(node, this);
				return true;
			}
			node._pendingClick = this;
			return true;
		}

		if (event.type === "pointerup") {
			if (node._pendingClick === this) {
				node._pendingClick = null;
				if (this._rDel && hit(pos, ...this._rDel)) {
					this._delete(node);
				} else if (this._rToggle && hit(pos, ...this._rToggle)) {
					this._toggle(node);
				} else if (this._rText && hit(pos, ...this._rText)) {
					this._editText(event, node);
				}
			}
			return true;
		}

		return false;
	}

	_delete(node) {
		const idx = node.widgets.indexOf(this);
		if (idx >= 0) {
			node.widgets.splice(idx, 1);
			const inpIdx = (node.inputs ?? []).findIndex(
				(i) => i.name === this.name,
			);
			if (inpIdx >= 0) {
				node.disconnectInput?.(inpIdx); // sever any live link first
				node.removeInput(inpIdx);
			}
			_syncStringSlots(node);
			node.setSize([node.size[0], node.computeSize()[1]]);
			node.setDirtyCanvas(true, true);
		}
	}

	_toggle(node) {
		this._value.on = !this._value.on;
		node.setDirtyCanvas(true);
	}

	_editText(event, node) {
		app.canvas.prompt(
			"String",
			this._value.text ?? "",
			(v) => {
				this._value.text = v;
				_syncStringSlots(node);
				node.setDirtyCanvas(true);
			},
			event,
		);
	}

	serializeValue() {
		return { ...this._value };
	}
}

// ── Drag-to-reorder ───────────────────────────────────────────────────────────

function _startDrag(node, widget) {
	node._dragWidget = widget;
	node._dragCurrentY = widget.last_y;

	const canvasEl = app.canvas.canvas;

	function toNodeLocalY(ev) {
		const rect = canvasEl.getBoundingClientRect();
		const scale = app.canvas.ds.scale;
		const offset = app.canvas.ds.offset;
		return (ev.clientY - rect.top) / scale - offset[1] - node.pos[1];
	}

	function onMove(ev) {
		if (!node._dragWidget) return;
		ev.stopPropagation();
		node._dragCurrentY = toNodeLocalY(ev);
		node.setDirtyCanvas(true);
	}

	function onUp(ev) {
		ev.stopPropagation();
		canvasEl.removeEventListener("pointermove", onMove, true);
		canvasEl.removeEventListener("pointerup", onUp, true);
		if (node._dragWidget) {
			_finalizeDrag(node, toNodeLocalY(ev));
			node._dragWidget = null;
			node._dragCurrentY = null;
		}
		node.setDirtyCanvas(true, true);
	}

	canvasEl.addEventListener("pointermove", onMove, true);
	canvasEl.addEventListener("pointerup", onUp, true);
}

function _finalizeDrag(node, currentY) {
	const dragWidget = node._dragWidget;
	if (!dragWidget) return;

	const strWidgets = _getStringWidgets(node);
	const srcIdx = node.widgets.indexOf(dragWidget);
	if (srcIdx < 0) return;

	let insertBefore = null;
	for (const w of strWidgets) {
		if (w === dragWidget) continue;
		if (currentY < w.last_y + ROW_H / 2) {
			insertBefore = w;
			break;
		}
	}

	node.widgets.splice(srcIdx, 1);
	const dstIdx =
		insertBefore === null
			? node.widgets.length
			: Math.max(0, node.widgets.indexOf(insertBefore));
	node.widgets.splice(dstIdx, 0, dragWidget);

	// Rename string1..N in new visual order so Python sees the right sequence
	_renumberStringSlots(node);

	node.setDirtyCanvas(true, true);
}

// ── String slot management ────────────────────────────────────────────────────

function _isStringWidget(w) {
	return w instanceof OliStringRowWidget;
}
function _getStringWidgets(node) {
	return (node.widgets ?? []).filter(_isStringWidget);
}

/**
 * After a drag reorder, rename widget + input names to string1..N in visual
 * order so Python's _sorted_slot_keys processes them correctly.
 * Links are safe: LiteGraph tracks them by input INDEX, not name.
 */
function _renumberStringSlots(node) {
	const strWidgets = _getStringWidgets(node);
	// Capture widget→input associations BEFORE any renaming to avoid
	// collision when two widgets temporarily share the same name mid-loop.
	const inpOf = new Map(
		strWidgets.map((w) => [
			w,
			(node.inputs ?? []).find((s) => s.name === w.name) ?? null,
		]),
	);
	strWidgets.forEach((w, i) => {
		const newName = "string" + (i + 1);
		if (w.name === newName) return;
		w.name = newName;
		const inp = inpOf.get(w);
		if (inp) {
			inp.name = newName;
			if (inp.widget) inp.widget.name = newName;
		}
	});
	node._stringCounter = strWidgets.length;
}

/**
 * Add a new string row widget + its input connector bullet.
 * Setting inp.widget = { name } tells LiteGraph to position the bullet at
 * the widget's Y coordinate (#arrangeWidgetInputSlots).
 */
function _addStringRow(node, value) {
	node._stringCounter = (node._stringCounter ?? 0) + 1;
	const name = "string" + node._stringCounter;

	const w = new OliStringRowWidget(name);
	if (value) w.value = value;
	node.addCustomWidget(w);

	// Add the input connector and mark it as a widget-input slot
	node.addInput(name, "*");
	const inp = (node.inputs ?? []).find((i) => i.name === name);
	if (inp) inp.widget = { name };

	node.setSize([node.size[0], node.computeSize()[1]]);
	node.setDirtyCanvas?.(true, true);
	return w;
}

/**
 * Ensure exactly one empty placeholder row at the end.
 * Removes ALL empty rows anywhere in the list, then adds one at the end.
 * This handles legacy workflows that may have empty stubs in the middle.
 */
function _syncStringSlots(node) {
	// Remove ALL empty rows (no text, no connection) regardless of position
	const toRemove = _getStringWidgets(node).filter((w) => w._isEmpty(node));
	for (const w of toRemove) {
		const widgetIdx = node.widgets.indexOf(w);
		if (widgetIdx >= 0) node.widgets.splice(widgetIdx, 1);
		const inpIdx = (node.inputs ?? []).findIndex(
			(inp) => inp.name === w.name,
		);
		if (inpIdx >= 0) node.removeInput(inpIdx);
	}

	// Ensure exactly one empty placeholder row at the end
	const after = _getStringWidgets(node);
	if (after.length === 0 || !after[after.length - 1]._isEmpty(node)) {
		_addStringRow(node, null);
	}
}

// ── Extension ─────────────────────────────────────────────────────────────────

app.registerExtension({
	name: "oli.megaStringList",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== NODE_TYPE) return;

		// computeSize ─────────────────────────────────────────────────────────
		const _computeSize = nodeType.prototype.computeSize;
		nodeType.prototype.computeSize = function () {
			const s = _computeSize
				? _computeSize.apply(this, arguments)
				: [MIN_W, 60];
			s[0] = Math.max(s[0], MIN_W);
			return s;
		};

		// onNodeCreated ───────────────────────────────────────────────────────
		const _onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function () {
			_onNodeCreated?.apply(this, arguments);
			this.serialize_widgets = true;
			this._stringCounter = 0;
			this._dragWidget = null;
			this._dragCurrentY = null;
			this._pendingClick = null;
			this._configuring = false;

			_syncStringSlots(this);

			const s = this.computeSize();
			this.setSize([Math.max(s[0], MIN_W), s[1]]);
		};

		// configure (workflow restore) ─────────────────────────────────────────
		const _configure = nodeType.prototype.configure;
		nodeType.prototype.configure = function (info) {
			// Guard: suppress onConnectionsChange side-effects during configure
			this._configuring = true;

			// 1. Remove existing string row widgets
			this.widgets = (this.widgets ?? []).filter(
				(w) => !_isStringWidget(w),
			);
			this._stringCounter = 0;

			// 2. Remove all stringN inputs (walk backwards to keep indices stable)
			(this.inputs ?? [])
				.map((inp, i) => ({ inp, i }))
				.filter(({ inp }) => /^string\d+$/.test(inp.name))
				.sort((a, b) => b.i - a.i)
				.forEach(({ i }) => this.removeInput(i));

			// 3. Restore widgets_values: type-dispatch for each value
			for (const v of info.widgets_values ?? []) {
				if (typeof v === "boolean") {
					const w = this.widgets?.find((w) => w.name === "enable");
					if (w) w.value = v;
				} else if (typeof v === "string") {
					const w = this.widgets?.find((w) => w.name === "delimiter");
					if (w) w.value = v;
				} else if (v && typeof v === "object" && "text" in v) {
					// Restore all string rows, including connected ones (text="").
					// _syncStringSlots will remove actual empties and add one placeholder.
					_addStringRow(this, v);
				}
			}

			// 4. Let LiteGraph restore connections (pass undefined to skip
			//    index-based widget value re-apply which would corrupt custom widgets)
			_configure?.apply(this, [{ ...info, widgets_values: undefined }]);

			// 5. After links are restored: ensure placeholder at end
			this._configuring = false;
			_syncStringSlots(this);
		};

		// onConnectionsChange — keep placeholder slot in sync ─────────────────
		const _onConnectionsChange = nodeType.prototype.onConnectionsChange;
		nodeType.prototype.onConnectionsChange = function (
			type,
			index,
			connected,
			link,
			ioSlot,
		) {
			_onConnectionsChange?.apply(this, arguments);
			if (type !== LiteGraph.INPUT) return;
			// Skip all processing while configure is active to avoid spurious
			// placeholder additions / deletions during link restoration.
			if (this._configuring) return;
			const inp = this.inputs?.[index];
			if (!inp || !/^string\d+$/.test(inp.name)) return;

			if (!connected) {
				// If the row has no text, delete it rather than leaving an
				// un-deletable empty stub where a connection used to be.
				const w = (this.widgets ?? []).find(
					(ww) =>
						ww instanceof OliStringRowWidget &&
						ww.name === inp.name,
				);
				if (w && !(w._value.text ?? "").trim()) {
					// Defer one tick so LiteGraph finishes its own link cleanup.
					// Re-check inside the callback: if the slot was reconnected
					// (link replacement) in the same tick, bail out — don't delete.
					const self = this;
					const slotName = inp.name;
					setTimeout(() => {
						const ii = (self.inputs ?? []).findIndex(
							(s) => s.name === slotName,
						);
						// Bail if reconnected (link replacement race condition)
						if (ii >= 0 && self.inputs[ii].link != null) return;
						const wi = (self.widgets ?? []).indexOf(w);
						if (wi >= 0) self.widgets.splice(wi, 1);
						if (ii >= 0) self.removeInput(ii);
						_syncStringSlots(self);
						self.setSize([self.size[0], self.computeSize()[1]]);
						self.setDirtyCanvas(true, true);
					}, 0);
					return;
				}
				_syncStringSlots(this);
			} else {
				_syncStringSlots(this);
				// Deferred redraw: LiteGraph may finish link bookkeeping (inp.link)
				// after onConnectionsChange returns. A tick-delayed dirty ensures
				// draw() sees the new connection and shows the source node name
				// even when connecting to a row that already has typed text.
				const self = this;
				setTimeout(() => self.setDirtyCanvas?.(true, true), 0);
			}
		};

		// onMouseDown — intercept connected-row controls BEFORE LiteGraph's
		// slot-click handler (which runs after onMouseDown but before widget.mouse()).
		const _onMouseDown = nodeType.prototype.onMouseDown;
		nodeType.prototype.onMouseDown = function (e, pos) {
			for (const w of _getStringWidgets(this)) {
				const inp = (this.inputs ?? []).find(
					(i) => i.name === w.name,
				);
				if (inp?.link == null) continue;
				if (w._rHandle && hit(pos, ...w._rHandle)) {
					_startDrag(this, w);
					return true;
				}
				if (w._rDel && hit(pos, ...w._rDel)) {
					w._delete(this);
					return true;
				}
				if (w._rToggle && hit(pos, ...w._rToggle)) {
					w._toggle(this);
					return true;
				}
			}
			return _onMouseDown?.call(this, e, pos) ?? false;
		};

		// onDrawForeground — blue insertion line during drag ───────────────────
		const _onDrawForeground = nodeType.prototype.onDrawForeground;
		nodeType.prototype.onDrawForeground = function (ctx) {
			_onDrawForeground?.apply(this, arguments);
			if (!this._dragWidget) return;

			const strWidgets = _getStringWidgets(this);
			const dragY = this._dragCurrentY ?? 0;

			let lineY = null;
			for (const w of strWidgets) {
				if (w === this._dragWidget) continue;
				if (dragY < w.last_y + ROW_H / 2) {
					lineY = w.last_y;
					break;
				}
			}
			if (lineY === null) {
				const last = strWidgets[strWidgets.length - 1];
				lineY = last ? last.last_y + ROW_H : 30;
			}

			ctx.save();
			ctx.strokeStyle = "#4af";
			ctx.lineWidth = 2;
			ctx.beginPath();
			ctx.moveTo(PAD, lineY);
			ctx.lineTo(this.size[0] - PAD, lineY);
			ctx.stroke();
			ctx.restore();
		};
	},
});
