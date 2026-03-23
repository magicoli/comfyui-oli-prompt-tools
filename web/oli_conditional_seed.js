/**
 * OliConditionalSeed — frontend.
 *
 * - When seed_value is connected as input:
 *     disable control_after_generate and enable_rule (pass-through mode)
 * - When enable_rule = false:
 *     disable control_after_generate
 * - After execution:
 *     update seed_value widget with next_seed_value from Python
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "OliConditionalSeed";

function getWidget(node, name) {
	return (node.widgets ?? []).find((w) => w.name === name);
}

function isSeedConnected(node) {
	return (node.inputs ?? []).some((i) => i.name === "seed_value" && i.link != null);
}

function syncWidgets(node) {
	const connected   = isSeedConnected(node);
	const enableRule  = getWidget(node, "enable_rule");
	const control     = getWidget(node, "control_after_generate");

	if (enableRule) enableRule.disabled = connected;
	if (control)    control.disabled    = connected || !enableRule?.value;

	node.setDirtyCanvas(true);
}

app.registerExtension({
	name: "oli.conditionalSeed",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== NODE_TYPE) return;

		const _onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function () {
			_onNodeCreated?.apply(this, arguments);
			syncWidgets(this);
		};

		const _onConfigure = nodeType.prototype.onConfigure;
		nodeType.prototype.onConfigure = function () {
			_onConfigure?.apply(this, arguments);
			syncWidgets(this);
		};

		const _onConnectionsChange = nodeType.prototype.onConnectionsChange;
		nodeType.prototype.onConnectionsChange = function () {
			_onConnectionsChange?.apply(this, arguments);
			syncWidgets(this);
		};

		// Intercept enable_rule toggle
		const _onWidgetChanged = nodeType.prototype.onWidgetChanged;
		nodeType.prototype.onWidgetChanged = function (name) {
			_onWidgetChanged?.apply(this, arguments);
			if (name === "enable_rule") syncWidgets(this);
		};

		// Update seed_value widget after execution
		const _onExecuted = nodeType.prototype.onExecuted;
		nodeType.prototype.onExecuted = function (message) {
			_onExecuted?.apply(this, arguments);
			if (isSeedConnected(this)) return;
			const next = message?.next_seed_value?.[0];
			if (next === undefined) return;
			const w = getWidget(this, "seed_value");
			if (w) w.value = Number(next);
			syncWidgets(this);
		};
	},
});
