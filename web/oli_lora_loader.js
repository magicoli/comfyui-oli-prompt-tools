/**
 * OliLoraLoader — Power Lora Loader with compatibility checking.
 * Self-contained, no rgthree dependency.
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "OliLoraLoader";
const ROW_H     = LiteGraph.NODE_WIDGET_HEIGHT ?? 20;
const MIN_W     = 340;
const PAD       = 8;

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

// ── Coordinate helpers ────────────────────────────────────────────────────────

function hit(pos, x, y, w, h) {
	return pos[0] >= x && pos[0] <= x + w && pos[1] >= y && pos[1] <= y + h;
}

/** Convert a LiteGraph event to screen { clientX, clientY }. */
function eventToScreen(e) {
	if (e?.clientX || e?.clientY) return { clientX: e.clientX, clientY: e.clientY };
	// Fall back to computing from canvas + graph coordinates
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

function showLoraSelector(screenX, screenY, loras, callback) {
	// Remove any existing selector
	document.querySelector(".oli-lora-selector")?.remove();

	const panel = document.createElement("div");
	panel.className = "oli-lora-selector";
	Object.assign(panel.style, {
		position:     "fixed",
		left:         screenX + "px",
		top:          screenY + "px",
		background:   "#1e1e1e",
		border:       "1px solid #555",
		borderRadius: "4px",
		zIndex:       "10000",
		width:        "300px",
		maxHeight:    "420px",
		display:      "flex",
		flexDirection: "column",
		boxShadow:    "0 4px 20px rgba(0,0,0,.6)",
	});

	const search = document.createElement("input");
	search.type        = "text";
	search.placeholder = "Search LoRAs…";
	Object.assign(search.style, {
		padding:    "6px 8px",
		background: "#111",
		border:     "none",
		borderBottom: "1px solid #444",
		color:      "#ddd",
		fontSize:   "13px",
		outline:    "none",
		flexShrink: "0",
	});
	panel.appendChild(search);

	const list = document.createElement("div");
	Object.assign(list.style, {
		overflowY: "auto",
		flexGrow:  "1",
	});
	panel.appendChild(list);

	function render(filter) {
		list.innerHTML = "";
		const q = filter.toLowerCase();
		const filtered = q ? loras.filter(l => l.toLowerCase().includes(q)) : loras;
		for (const lora of filtered) {
			const item = document.createElement("div");
			item.textContent = lora;
			Object.assign(item.style, {
				padding:  "4px 10px",
				cursor:   "pointer",
				fontSize: "12px",
				color:    "#ccc",
				whiteSpace: "nowrap",
				overflow: "hidden",
				textOverflow: "ellipsis",
			});
			item.title = lora;
			item.addEventListener("mouseover", () => { item.style.background = "#333"; });
			item.addEventListener("mouseout",  () => { item.style.background = ""; });
			item.addEventListener("pointerdown", (ev) => {
				ev.stopPropagation();
				callback(lora);
				panel.remove();
			});
			list.appendChild(item);
		}
		if (!filtered.length) {
			const empty = document.createElement("div");
			empty.textContent = "No results";
			Object.assign(empty.style, { padding: "8px", color: "#666", fontSize: "12px" });
			list.appendChild(empty);
		}
	}

	search.addEventListener("input", () => render(search.value));
	render("");
	document.body.appendChild(panel);
	search.focus();

	// Clamp to viewport
	requestAnimationFrame(() => {
		const r = panel.getBoundingClientRect();
		if (r.right  > window.innerWidth)  panel.style.left = (window.innerWidth  - r.width  - 6) + "px";
		if (r.bottom > window.innerHeight) panel.style.top  = (window.innerHeight - r.height - 6) + "px";
	});

	// Close on outside click
	const close = (ev) => {
		if (!panel.contains(ev.target)) {
			panel.remove();
			document.removeEventListener("pointerdown", close, true);
		}
	};
	setTimeout(() => document.addEventListener("pointerdown", close, true), 0);
}

// ── Header widget (Toggle All) ────────────────────────────────────────────────

class OliLoraHeaderWidget {
	constructor() {
		this.name    = "_oli_header";
		this.type    = "custom";
		this.y       = 0;
		this.last_y  = 0;
		this.options = { serialize: false };
		this._rToggle = null;
	}

	computeSize(width) { return [width, ROW_H]; }

	draw(ctx, node, width, posY, height) {
		this.last_y = posY;
		const loraWidgets = _getLoraWidgets(node);
		if (!loraWidgets.length) return;

		const mid = posY + height / 2;
		ctx.save();

		const allOn  = loraWidgets.every(w => w._value.on);
		const allOff = loraWidgets.every(w => !w._value.on);
		const state  = allOn ? true : allOff ? false : null;

		// Toggle-all pill
		const tw = 90, th = height - 4;
		const tx = PAD, ty = posY + 2;
		ctx.fillStyle = state === true ? "#3a6a3a" : state === false ? "#444" : "#554";
		ctx.beginPath();
		ctx.roundRect(tx, ty, tw, th, 3);
		ctx.fill();
		ctx.fillStyle = "#bbb";
		ctx.font = `${Math.round(height * 0.55)}px sans-serif`;
		ctx.textAlign   = "center";
		ctx.textBaseline = "middle";
		ctx.fillText("Toggle All", tx + tw / 2, mid);
		this._rToggle = [tx, ty, tw, th];

		// Column labels
		ctx.globalAlpha = 0.5;
		ctx.fillStyle   = LiteGraph.WIDGET_TEXT_COLOR ?? "#aaa";
		ctx.textAlign   = "right";
		ctx.fillText("strength", width - PAD - 14 - 13 - 36 - 13 - 4, mid);

		ctx.restore();
	}

	mouse(event, pos, node) {
		if (event.type === "pointerup" && this._rToggle && hit(pos, ...this._rToggle)) {
			const loraWidgets = _getLoraWidgets(node);
			const allOn = loraWidgets.every(w => w._value.on);
			for (const w of loraWidgets) w._value.on = !allOn;
			node.setDirtyCanvas(true);
			return true;
		}
		return false;
	}

	serializeValue() { return undefined; }
}

// ── Lora row widget ───────────────────────────────────────────────────────────

class OliLoraRowWidget {
	constructor(name) {
		this.name    = name;
		this.type    = "custom";
		this.y       = 0;
		this.last_y  = 0;
		this.options = {};

		this._value   = { on: true, lora: null, strength: 1.0 };
		this._compat  = undefined;  // undefined=unknown, true=ok, false=incompatible

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
		this._value = (v && typeof v === "object")
			? { on: true, lora: null, strength: 1.0, ...v }
			: { on: true, lora: null, strength: 1.0 };
	}

	computeSize(width) { return [width, ROW_H]; }

	draw(ctx, node, width, posY, height) {
		this.last_y  = posY;
		const mid    = posY + height / 2;
		const fade   = this._value.on ? 1.0 : 0.4;
		const fsize  = Math.round(height * 0.6);
		const font   = `${fsize}px sans-serif`;

		ctx.save();

		// Row background
		ctx.fillStyle = "#252525";
		ctx.beginPath();
		ctx.roundRect(PAD, posY + 1, width - PAD * 2, height - 2, 3);
		ctx.fill();

		let x = PAD + 4;

		// Toggle — color encodes both on/off and compat status
		const TW = Math.round(height * 1.4), TH = Math.round(height * 0.6);
		const tx = x, ty = mid - TH / 2;
		if (!this._value.on) {
			ctx.fillStyle = "#555";                   // disabled
		} else if (this._compat === false) {
			ctx.fillStyle = "#7a3030";                // incompatible → red
		} else {
			ctx.fillStyle = "#4a7a4a";                // enabled (compat ok or unknown)
		}
		ctx.beginPath();
		ctx.roundRect(tx, ty, TW, TH, TH / 2);
		ctx.fill();
		ctx.fillStyle = "#ddd";
		const kx = this._value.on ? tx + TW - TH / 2 - 1 : tx + TH / 2 + 1;
		ctx.beginPath();
		ctx.arc(kx, mid, TH / 2 - 1, 0, Math.PI * 2);
		ctx.fill();
		this._rToggle = [tx, ty, TW, TH];
		x += TW + 5;

		// Delete button (rightmost)
		const DW = 14;
		const dx = width - PAD - 4 - DW;
		ctx.fillStyle = "#5a2020";
		ctx.beginPath();
		ctx.roundRect(dx, posY + 2, DW, height - 4, 2);
		ctx.fill();
		ctx.fillStyle = "#f99";
		ctx.font      = `${fsize - 1}px sans-serif`;
		ctx.textAlign = "center";
		ctx.textBaseline = "middle";
		ctx.fillText("✕", dx + DW / 2, mid);
		this._rDel = [dx, posY + 2, DW, height - 4];

		// Strength control
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

		// LoRA name
		const lx = x, lw = sx - x - 4;
		ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR ?? "#ccc";
		ctx.textAlign = "left";
		ctx.font      = font;
		let label = this._value.lora ?? "— click to select —";
		while (ctx.measureText(label).width > lw - 2 && label.length > 4) {
			label = label.slice(0, -4) + "…";
		}
		ctx.fillText(label, lx, mid);
		this._rLora = [lx, posY + 1, lw, height - 2];

		ctx.globalAlpha = 1;
		ctx.restore();
	}

	mouse(event, pos, node) {
		if (event.type === "pointerdown") {
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
					this._value.strength =
						Math.round((this._dragStartS + dx * 0.01) * 100) / 100;
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
			this._compat = undefined;  // reset compat until next execution
			node.setDirtyCanvas(true);
		});
	}

	serializeValue() {
		return { ...this._value };
	}
}

// ── Extension ─────────────────────────────────────────────────────────────────

app.registerExtension({
	name: "oli.loraLoader",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== NODE_TYPE) return;

		// Never let computeSize shrink the width below MIN_W or current size
		const _computeSize = nodeType.prototype.computeSize;
		nodeType.prototype.computeSize = function () {
			const s = _computeSize ? _computeSize.apply(this, arguments) : [MIN_W, 60];
			s[0] = Math.max(s[0], this.size?.[0] ?? 0, MIN_W);
			return s;
		};

		// onNodeCreated
		const _onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function () {
			_onNodeCreated?.apply(this, arguments);
			this.serialize_widgets = true;
			this._loraCounter = 0;
			this.addCustomWidget(new OliLoraHeaderWidget());
			this._addBtn = this.addWidget("button", "➕ Add LoRA", "", _noop, { serialize: false });
			// Override callback with the one that receives the event
			this._addBtn.callback = (v, canvas, node, pos, e) => _openAddSelector(e, node);
			const s = this.computeSize();
			this.setSize([Math.max(s[0], MIN_W), s[1]]);
		};

		// Restore from saved workflow
		const _configure = nodeType.prototype.configure;
		nodeType.prototype.configure = function (info) {
			this.widgets = (this.widgets ?? []).filter(w => !_isLoraWidget(w));
			this._loraCounter = 0;
			for (const v of info.widgets_values ?? []) {
				if (v && typeof v === "object" && "lora" in v) _addLoraRow(this, v);
			}
			const rest = (info.widgets_values ?? []).filter(
				v => !(v && typeof v === "object" && "lora" in v),
			);
			_configure?.apply(this, [{ ...info, widgets_values: rest }]);
		};

		// Update compat dots after execution
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

		// Right-click context menu on lora rows
		nodeType.prototype.getExtraMenuOptions = function (_canvas, options) {
			const mouse    = app.canvas.graph_mouse;
			const localY   = mouse[1] - this.pos[1];
			const loraWgts = _getLoraWidgets(this);

			for (const w of loraWgts) {
				if (localY < w.last_y || localY > w.last_y + ROW_H) continue;
				const idx     = loraWgts.indexOf(w);
				const nodeIdx = this.widgets.indexOf(w);
				options.push(
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
				);
				break;
			}
		};
	},
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function _noop() {}

function _isLoraWidget(w) {
	return w instanceof OliLoraRowWidget;
}

function _getLoraWidgets(node) {
	return (node.widgets ?? []).filter(_isLoraWidget);
}

function _addLoraRow(node, value) {
	node._loraCounter = (node._loraCounter ?? 0) + 1;
	const w = new OliLoraRowWidget("lora_" + node._loraCounter);
	if (value) w.value = value;

	// Insert before the "Add LoRA" button
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
		const w = _addLoraRow(node);
		w._value.lora = lora;
		node.setDirtyCanvas(true);
	});
}
