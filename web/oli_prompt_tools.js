import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
	name: "oli.promptTools",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name === "OliPromptLinePick") {
			const onAdded = nodeType.prototype.onAdded;
			nodeType.prototype.onAdded = async function () {
				onAdded?.apply(this, []);

				const prompt_widget = this.widgets.find(
					(w) => w.name === "prompt",
				);

				this.addWidget(
					"button",
					"get values from COMBO link",
					"",
					() => {
						// The COMBO output is outputs[1]
						const output_link =
							this.outputs[1]?.links?.length > 0
								? this.outputs[1].links[0]
								: null;

						if (!output_link) {
							alert("No COMBO link connected.");
							return;
						}

						const all_nodes = app.graph._nodes;
						const target_node = all_nodes.find((n) =>
							n.inputs?.find(
								(input) => input.link === output_link,
							),
						);

						if (!target_node) {
							alert("Could not find connected node.");
							return;
						}

						const input = target_node.inputs.find(
							(i) => i.link === output_link,
						);
						const widget_name = input?.widget?.name;
						const widget = target_node.widgets?.find(
							(w) => w.name === widget_name,
						);
						const values = widget?.options?.values;

						if (values?.length) {
							prompt_widget.value = values.join("\n");
						}
					},
					{ serialize: false },
				);
			};
		}

		if (nodeData.name === "OliModelInfo") {
			const onAdded = nodeType.prototype.onAdded;
			nodeType.prototype.onAdded = function () {
				onAdded?.apply(this, []);
				const w = ComfyWidgets["STRING"](
					this,
					"model_class",
					["STRING", { multiline: true }],
					app,
				).widget;
				w.inputEl.readOnly = true;
				w.inputEl.style.opacity = 0.7;
				w.value = "—";
				this._name_widget = w;
				requestAnimationFrame(() => {
					w.inputEl.dispatchEvent(new Event("input"));
					app.graph.setDirtyCanvas(true, true);
				});
			};

			const onExecuted = nodeType.prototype.onExecuted;
			nodeType.prototype.onExecuted = function (message) {
				onExecuted?.apply(this, [message]);
				if (message?.text?.[0] !== undefined && this._name_widget) {
					this._name_widget.value = message.text[0];
					this._name_widget.inputEl?.dispatchEvent(
						new Event("input"),
					);
				}
			};
		}

		if (nodeData.name === "OliVideoFrameLimit") {
			const onAdded = nodeType.prototype.onAdded;
			nodeType.prototype.onAdded = function () {
				onAdded?.apply(this, []);
				// Use ComfyWidgets STRING so the textarea is a real DOM element
				// and updates correctly after execution (same approach as ShowText)
				const w = ComfyWidgets["STRING"](
					this,
					"info",
					["STRING", { multiline: true }],
					app,
				).widget;
				w.inputEl.readOnly = true;
				w.inputEl.style.opacity = 0.7;
				// 5-line placeholder so the node frame sizes itself correctly
				w.value =
					"CUDA VRAM: —\nmodel: —\ndim: —\nrequested: — frames\ncapped: — frames";
				this._info_widget = w;
				requestAnimationFrame(() => {
					w.inputEl.dispatchEvent(new Event("input"));
					const sz = this.computeSize();
					this.setSize([sz[0], sz[1] + 30]); // +30px for 2 extra lines
					app.graph.setDirtyCanvas(true, true);
				});
			};

			const onExecuted = nodeType.prototype.onExecuted;
			nodeType.prototype.onExecuted = function (message) {
				onExecuted?.apply(this, [message]);
				if (message?.text?.[0] !== undefined && this._info_widget) {
					this._info_widget.value = message.text[0];
					// Trigger DOM update and resize to fit new content
					this._info_widget.inputEl?.dispatchEvent(
						new Event("input"),
					);
					this.onResize?.(this.size);
				}
			};
		}
	},
});
