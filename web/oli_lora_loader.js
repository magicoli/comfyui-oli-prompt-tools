/**
 * OliLoraLoader — Power Lora Loader with compatibility checking.
 * Self-contained, no rgthree dependency.
 */

import { app } from "../../scripts/app.js";
import {
	ROW_H, PAD, PAD_L,
	hit,
	drawRowBackground, drawHandle, drawTogglePill, drawDeleteBtn, drawDisabledOverlay,
	startRowDrag, installDragForeground,
} from "./oli_widgets_common.js";

const NODE_TYPE = "OliLoraLoader";
const MIN_W     = 340;

// ── Lora list (cached) ────────────────────────────────────────────────────────

let _loraCache = null;
async function fetchLoras() {
	if (_loraCache) return _loraCache;
	try {
		const r = await fetch("/object_info/LoraLoader");
		const d = await r.json();
		_loraCache = d?.LoraLoader?.input?.required?.lora_name?.[0] ?? [];
	} catch {
		_loraCache = [];
	}
	return _loraCache;
}

// ── Coordinate helper ─────────────────────────────────────────────────────────

/** Convert a LiteGraph event to screen { clientX, clientY }. */
function eventToScreen(e) {
	if (e?.clientX || e?.clientY) return { clientX: e.clientX, clientY: e.clientY };
	if (e?.canvasX !== undefined) {
		const canvas = app.canvas;
		const rect   = canvas.canvas.getBoundingClientRect();
		const scale  = canvas.ds.scale;
		const off    = canvas.ds.offset;
		return {
			clientX: rect.left + (e.canvasX + off[0]) * scale,
			clientY: rect.top  + (e.canvasY + off[1]) * scale,
		};
	}
	return { clientX: window.innerWidth / 2, clientY: window.innerHeight / 2 };
}

// ── Lora selector (DOM overlay with search) ───────────────────────────────────

function showLoraSelector(screenX, screenY, loras, callback, current = null) {
	document.querySelector(".oli-lora-selector")?.remove();

	const panel = document.createElement("div");
	panel.className = "oli-lora-selector";
	Object.assign(panel.style, {
		position:      "fixed",
		left:          screenX + "px",
		top:           screenY + "px",
		background:    "#1e1e1e",
		border:        "1px solid #555",
		borderRadius:  "4px",
		zIndex:        "10000",
		width:         "300px",
		maxHeight:     "420px",
		display:       "flex",
		flexDirection: "column",
		boxShadow:     "0 4px 20px rgba(0,0,0,.6)",
	});

	const search = document.createElement("input");
	search.type        = "text";
	search.placeholder = "Search LoRAs…";
	Object.assign(search.style, {
		padding:      "6px 8px",
		background:   "#111",
		border:       "none",
		borderBottom: "1px solid #444",
		color:        "#ddd",
		fontSize:     "13px",
		outline:      "none",
		flexShrink:   "0",
	});
	panel.appendChild(search);

	const list = document.createElement("div");
	Object.assign(list.style, { overflowY: "auto", flexGrow: "1" });
	panel.appendChild(list);

	let filteredList = [];
	let selectedIdx  = -1;

	function selectIdx(idx) {
		selectedIdx = Math.max(-1, Math.min(idx, filteredList.length - 1));
		Array.from(list.children).forEach((el, i) => {
			el.style.background = i === selectedIdx ? "#2a4a6a" : "";
		});
		if (selectedIdx >= 0 && list.children[selectedIdx]) {
			list.children[selectedIdx].scrollIntoView({ block: "nearest" });
		}
	}

	function closePanel() {
		panel.remove();
		document.removeEventListener("pointerdown", outsideClose, true);
	}

	function confirmSelection() {
		if (selectedIdx >= 0 && filteredList[selectedIdx]) {
			callback(filteredList[selectedIdx]);
			closePanel();
		}
	}

	function render(filter) {
		list.innerHTML = "";
		const q = filter.toLowerCase();
		filteredList = q ? loras.filter(l => l.toLowerCase().includes(q)) : loras.slice();

		for (let i = 0; i < filteredList.length; i++) {
			const lora = filteredList[i];
			const item = document.createElement("div");
			item.textContent = lora;
			Object.assign(item.style, {
				padding:      "4px 10px",
				cursor:       "pointer",
				fontSize:     "12px",
				color:        "#ccc",
				whiteSpace:   "nowrap",
				overflow:     "hidden",
				textOverflow: "ellipsis",
			});
			item.title = lora;
			const ii = i;
			item.addEventListener("mouseover", () => selectIdx(ii));
			item.addEventListener("pointerdown", (ev) => {
				ev.stopPropagation();
				callback(lora);
				closePanel();
			});
			list.appendChild(item);
		}

		if (!filteredList.length) {
			const empty = document.createElement("div");
			empty.textContent = "No results";
			Object.assign(empty.style, { padding: "8px", color: "#666", fontSize: "12px" });
			list.appendChild(empty);
		}

		const autoIdx = (current && filteredList.includes(current))
			? filteredList.indexOf(current)
			: (filteredList.length > 0 ? 0 : -1);
		selectIdx(autoIdx);
	}

	search.addEventListener("input", () => render(search.value));
	search.addEventListener("keydown", (ev) => {
		switch (ev.key) {
			case "ArrowDown": ev.preventDefault(); selectIdx(selectedIdx + 1); break;
			case "ArrowUp":   ev.preventDefault(); selectIdx(selectedIdx - 1); break;
			case "Enter":     ev.preventDefault(); confirmSelection();         break;
			case "Escape":    ev.preventDefault(); closePanel();               break;
		}
	});

	render("");
	document.body.appendChild(panel);
	search.focus();

	requestAnimationFrame(() => {
		const r = panel.getBoundingClientRect();
		if (r.right  > window.innerWidth)  panel.style.left = (window.innerWidth  - r.width  - 6) + "px";
		if (r.bottom > window.innerHeight) panel.style.top  = (window.innerHeight - r.height - 6) + "px";
	});

	const outsideClose = (ev) => { if (!panel.contains(ev.target)) closePanel(); };
	setTimeout(() => document.addEventListener("pointerdown", outsideClose, true), 0);
}

// ── Lora row widget ───────────────────────────────────────────────────────────

class OliLoraRowWidget {
	constructor(name) {
		this.name    = name;
		this.type    = "custom";
		this.y       = 0;
		this.last_y  = 0;
		this.options = {};

		this._value  = { on: true, lora: null, strength: 1.0 };
		this._compat = undefined;   // undefined=unknown, true=ok, false=incompatible

		this._rHandle = null;
		this._rToggle = null;
		this._rLora   = null;
		this._rDec    = null;
		this._rVal    = null;
		this._rInc    = null;
		this._rDel    = null;

		this._mouseDown  = false;
		this._dragStartX = 0;
		this._dragStartS = 1.0;
		this._dragging   = false;
	}

	get value() { return this._value; }
	set value(v) {
		if (v === undefined) return;
		this._value = (v && typeof v === "object")
			? { on: true, lora: null, strength: 1.0, ...v }
			: { on: true, lora: null, strength: 1.0 };
	}

	computeSize(width) { return [width, ROW_H]; }

	draw(ctx, node, width, posY, height) {
		this.last_y = posY;
		const mid   = posY + height / 2;
		const fade  = this._value.on ? 1.0 : 0.4;
		const fsize = Math.round(height * 0.6);
		const font  = `${fsize}px sans-serif`;

		ctx.save();

		drawRowBackground(ctx, posY, width, height, "#252525");

		let x = PAD_L + 4;

		// Drag handle ≡
		({ rect: this._rHandle, nextX: x } = drawHandle(ctx, x, posY, mid, height, font));

		// Toggle pill — compat=false shows red, undefined/true shows green
		({ rect: this._rToggle, nextX: x } = drawTogglePill(ctx, x, mid, height, this._value.on, this._compat));

		// Delete button ✕
		const { rect: delRect, leftX: dx } = drawDeleteBtn(ctx, width, posY, mid, height, fsize);
		this._rDel = delRect;

		// Strength control  ◀  0.00  ▶
		const AW = 13, VW = 38;
		const sx = dx - 4 - AW - VW - AW;

		ctx.globalAlpha = fade;
		ctx.font = font;

		ctx.fillStyle = "#3a3a3a";
		ctx.beginPath(); ctx.roundRect(sx, posY + 2, AW, height - 4, 2); ctx.fill();
		ctx.fillStyle = "#aaa";
		ctx.textAlign = "center";
		ctx.fillText("◀", sx + AW / 2, mid);
		this._rDec = [sx, posY + 2, AW, height - 4];

		ctx.fillStyle = "#2e2e2e";
		ctx.fillRect(sx + AW, posY + 2, VW, height - 4);
		ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR ?? "#ddd";
		ctx.fillText(parseFloat(this._value.strength ?? 1).toFixed(2), sx + AW + VW / 2, mid);
		this._rVal = [sx + AW, posY + 2, VW, height - 4];

		ctx.fillStyle = "#3a3a3a";
		ctx.beginPath(); ctx.roundRect(sx + AW + VW, posY + 2, AW, height - 4, 2); ctx.fill();
		ctx.fillStyle = "#aaa";
		ctx.fillText("▶", sx + AW + VW + AW / 2, mid);
		this._rInc = [sx + AW + VW, posY + 2, AW, height - 4];

		// LoRA name label
		const lx = x, lw = sx - x - 4;
		ctx.globalAlpha = fade;
		ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR ?? "#ccc";
		ctx.textAlign = "left";
		ctx.font = font;
		let label = this._value.lora ?? "";
		while (ctx.measureText(label).width > lw - 2 && label.length > 4) {
			label = label.slice(0, -4) + "…";
		}
		ctx.fillText(label, lx, mid);
		this._rLora = [lx, posY + 1, lw, height - 2];

		ctx.globalAlpha = 1;
		ctx.restore();

		// Dim row when node's enable widget is false (drawn after restore so it sits on top)
		const enableWidget = node.widgets?.find(w => w.name === "enable");
		if (enableWidget?.value === false) drawDisabledOverlay(ctx, posY, width, height);
	}

	mouse(event, pos, node) {
		// Suppress while another row is being dragged
		if (node._dragWidget && node._dragWidget !== this) return false;

		if (event.type === "pointerdown") {
			// Handle drag takes priority — initiate reorder from widget.mouse()
			// (avoids the LiteGraph event-routing issue that occurs when drag
			// is started from onMouseDown)
			if (this._rHandle && hit(pos, ...this._rHandle)) {
				startRowDrag(node, this, () => _getLoraWidgets(node));
				return true;
			}
			this._mouseDown  = true;
			this._dragging   = false;
			this._dragStartX = pos[0];
			this._dragStartS = this._value.strength ?? 1;
			return true;
		}

		if (event.type === "pointermove" && this._mouseDown) {
			if (this._rVal && hit([this._dragStartX, pos[1]], ...this._rVal)) {
				const dx = pos[0] - this._dragStartX;
				if (Math.abs(dx) > 3) {
					this._dragging = true;
					this._value.strength = Math.round((this._dragStartS + dx * 0.01) * 100) / 100;
					node.setDirtyCanvas(true);
				}
			}
			return false;
		}

		if (event.type === "pointerup") {
			const wasDrag = this._dragging;
			this._mouseDown = false;
			this._dragging  = false;
			if (!wasDrag) {
				if      (this._rDel    && hit(pos, ...this._rDel))    { this._delete(node); }
				else if (this._rToggle && hit(pos, ...this._rToggle)) { this._toggle(node); }
				else if (this._rDec   && hit(pos, ...this._rDec))    { this._step(-0.05, node); }
				else if (this._rInc   && hit(pos, ...this._rInc))    { this._step(+0.05, node); }
				else if (this._rVal   && hit(pos, ...this._rVal))    { this._promptStrength(event, node); }
				else if (this._rLora  && hit(pos, ...this._rLora))   { this._openSelector(event, node); }
			}
			return true;
		}
		return false;
	}

	_delete(node) {
		const idx = node.widgets.indexOf(this);
		if (idx >= 0) {
			node.widgets.splice(idx, 1);
			node.setSize([node.size[0], node.computeSize()[1]]);
			node.setDirtyCanvas(true, true);
		}
	}

	_toggle(node) {
		this._value.on = !this._value.on;
		node.setDirtyCanvas(true);
	}

	_step(d, node) {
		this._value.strength = Math.round(((this._value.strength ?? 1) + d) * 100) / 100;
		node.setDirtyCanvas(true);
	}

	_promptStrength(event, node) {
		app.canvas.prompt("Strength", this._value.strength ?? 1, (v) => {
			this._value.strength = Number(v);
			node.setDirtyCanvas(true);
		}, event);
	}

	async _openSelector(event, node) {
		const sc    = eventToScreen(event);
		const loras = await fetchLoras();
		showLoraSelector(sc.clientX, sc.clientY, loras, (lora) => {
			this._value.lora = lora;
			this._compat = undefined;
			node.setDirtyCanvas(true);
		}, this._value.lora);
	}

	serializeValue() { return { ...this._value }; }
}

// ── Extension ─────────────────────────────────────────────────────────────────

app.registerExtension({
	name: "oli.loraLoader",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== NODE_TYPE) return;

		const _computeSize = nodeType.prototype.computeSize;
		nodeType.prototype.computeSize = function () {
			const enableWidget = this.widgets?.find(w => w.name === "enable");
			if (enableWidget) enableWidget.hidden = _getLoraWidgets(this).length === 0;
			const s = _computeSize ? _computeSize.apply(this, arguments) : [MIN_W, 60];
			s[0] = Math.max(s[0], MIN_W);
			return s;
		};

		const _onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function () {
			_onNodeCreated?.apply(this, arguments);
			this.serialize_widgets = true;
			this._loraCounter  = 0;
			this._dragWidget   = null;
			this._dragCurrentY = null;
			this._addBtn = this.addWidget("button", "➕ Add LoRA", "", _noop, { serialize: false });
			this._addBtn.callback = (v, canvas, node, pos, e) => _openAddSelector(e, node);
			const s = this.computeSize();
			this.setSize([Math.max(s[0], MIN_W), s[1]]);
		};

		const _configure = nodeType.prototype.configure;
		nodeType.prototype.configure = function (info) {
			this.widgets = (this.widgets ?? []).filter(w => !_isLoraWidget(w));
			this._loraCounter = 0;
			for (const v of info.widgets_values ?? []) {
				if (v && typeof v === "object" && "lora" in v) _addLoraRow(this, v);
			}
			const savedEnable = (info.widgets_values ?? []).find(v => typeof v === "boolean");
			if (savedEnable !== undefined) {
				const enableWidget = this.widgets?.find(w => w.name === "enable");
				if (enableWidget) enableWidget.value = savedEnable;
			}
			_configure?.apply(this, [{ ...info, widgets_values: undefined }]);
		};

		const _onExecuted = nodeType.prototype.onExecuted;
		nodeType.prototype.onExecuted = function (message) {
			_onExecuted?.apply(this, [message]);
			const compat = message?.compat?.[0];
			if (!compat) return;
			for (const w of _getLoraWidgets(this)) {
				if (w._value?.lora != null) w._compat = compat[w._value.lora];
			}
			this.setDirtyCanvas?.(true);
		};


		// Blue insertion line during drag
		installDragForeground(nodeType, _getLoraWidgets);

		// Right-click context menu (Move Up / Move Down / Remove)
		const _getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
		nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
			const base     = _getExtraMenuOptions?.apply(this, [canvas, options]) ?? [];
			const mouse    = app.canvas.graph_mouse;
			const localY   = mouse[1] - this.pos[1];
			const loraWgts = _getLoraWidgets(this);

			for (const w of loraWgts) {
				if (localY < w.last_y || localY > w.last_y + ROW_H) continue;
				const idx     = loraWgts.indexOf(w);
				const nodeIdx = this.widgets.indexOf(w);
				return [
					{
						content:  "⬆️ Move Up",
						disabled: idx === 0,
						callback: () => {
							if (idx === 0) return;
							const prevNodeIdx = this.widgets.indexOf(loraWgts[idx - 1]);
							[this.widgets[prevNodeIdx], this.widgets[nodeIdx]] =
								[this.widgets[nodeIdx], this.widgets[prevNodeIdx]];
							this.setDirtyCanvas(true, true);
						},
					},
					{
						content:  "⬇️ Move Down",
						disabled: idx === loraWgts.length - 1,
						callback: () => {
							if (idx === loraWgts.length - 1) return;
							const nextNodeIdx = this.widgets.indexOf(loraWgts[idx + 1]);
							[this.widgets[nextNodeIdx], this.widgets[nodeIdx]] =
								[this.widgets[nodeIdx], this.widgets[nextNodeIdx]];
							this.setDirtyCanvas(true, true);
						},
					},
					{
						content:  "🗑️ Remove",
						callback: () => {
							this.widgets.splice(nodeIdx, 1);
							this.setSize([this.size[0], this.computeSize()[1]]);
							this.setDirtyCanvas(true, true);
						},
					},
					null,
					...base,
				];
			}
			return base;
		};
	},
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function _noop() {}
function _isLoraWidget(w)  { return w instanceof OliLoraRowWidget; }
function _getLoraWidgets(node) { return (node.widgets ?? []).filter(_isLoraWidget); }

function _addLoraRow(node, value) {
	node._loraCounter = (node._loraCounter ?? 0) + 1;
	const w = new OliLoraRowWidget("lora_" + node._loraCounter);
	if (value) w.value = value;
	const btnIdx = node._addBtn ? node.widgets.indexOf(node._addBtn) : -1;
	if (btnIdx >= 0) {
		node.widgets.splice(btnIdx, 0, w);
	} else {
		node.addCustomWidget(w);
	}
	node.setSize([node.size[0], node.computeSize()[1]]);
	node.setDirtyCanvas?.(true, true);
	return w;
}

async function _openAddSelector(event, node) {
	const sc    = eventToScreen(event);
	const loras = await fetchLoras();
	showLoraSelector(sc.clientX, sc.clientY, loras, (lora) => {
		_addLoraRow(node, { on: true, lora, strength: 1.0 });
	});
}
