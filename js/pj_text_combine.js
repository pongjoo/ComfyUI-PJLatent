import { app } from "../../scripts/app.js";

app.registerExtension({
	name: "pj.TextCombine",
	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name === "PJTextCombine") {
			const onNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function () {
				const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
				
				// 寻找“合并行数”或“input_count”控件
				const countWidget = this.widgets.find(w => w.name === "合并行数" || w.name === "input_count");
				
				// 添加“更新输入端口”按钮
				this.addWidget("button", "更新输入端口 (Update Inputs)", null, () => {
					const targetCount = countWidget ? countWidget.value : 3;
					
					// 统计现有的输入端口
					const currentInputs = this.inputs ? this.inputs.filter(i => i.name.startsWith("文本_") || i.name.startsWith("text_")) : [];
					const currentCount = currentInputs.length;
					
					if (targetCount > currentCount) {
						// 增加端口
						for (let i = currentCount + 1; i <= targetCount; i++) {
							this.addInput(`文本_${i}`, "STRING");
						}
					} else if (targetCount < currentCount) {
						// 减少多余端口
						for (let i = currentCount; i > targetCount; i--) {
							const inputIdx = this.inputs.findIndex(inp => inp.name === `文本_${i}` || inp.name === `text_${i}`);
							if (inputIdx !== -1) {
								this.removeInput(inputIdx);
							}
						}
					}
					
					this.setDirtyCanvas(true, true);
				});
				
				return r;
			};
		}
	}
});
