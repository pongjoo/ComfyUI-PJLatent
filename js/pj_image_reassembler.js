import { app } from "/scripts/app.js";

app.registerExtension({
    name: "PJ.ImageSliceReassembler",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Image_Slice_Reassembler") {
            const MAX_BLOCKS = 30;
            const DEFAULT_BLOCKS = 9; // 默认 9 块 (九宫格)

            // 从连接线智能探测上游分割器的切块总数
            nodeType.prototype.detectTotalBlocksFromLink = function () {
                if (!this.inputs) return DEFAULT_BLOCKS;
                const sliceDataInput = this.inputs.find(inp => inp.name === "切片数据");
                if (!sliceDataInput || sliceDataInput.link == null) {
                    // 未连接切片数据时，检查是否已有连接的块端口，保留最高连接块号
                    let maxConnected = DEFAULT_BLOCKS;
                    for (const inp of this.inputs) {
                        const m = inp.name.match(/^块(\d+)_图片$/);
                        if (m && inp.link != null) {
                            maxConnected = Math.max(maxConnected, parseInt(m[1]));
                        }
                    }
                    return maxConnected;
                }

                const link = app.graph?.links ? app.graph.links[sliceDataInput.link] : null;
                if (!link) return DEFAULT_BLOCKS;

                const originNode = app.graph.getNodeById(link.origin_id);
                if (!originNode) return DEFAULT_BLOCKS;

                // 优先从上游分割器实例的切线数据中读取
                if (originNode.cutlines) {
                    const h = (originNode.cutlines.horizontal || []).length;
                    const v = (originNode.cutlines.vertical || []).length;
                    const total = (h + 1) * (v + 1);
                    if (total > 0) return Math.min(MAX_BLOCKS, total);
                }

                // 备选从上游切线数据 widget 中解析
                const cutWidget = originNode.widgets?.find(w => w.name === "切线数据");
                if (cutWidget && cutWidget.value) {
                    try {
                        const parsed = typeof cutWidget.value === "string" ? JSON.parse(cutWidget.value) : cutWidget.value;
                        const h = (parsed.horizontal || []).length;
                        const v = (parsed.vertical || []).length;
                        const total = (h + 1) * (v + 1);
                        if (total > 0) return Math.min(MAX_BLOCKS, total);
                    } catch (e) {}
                }

                return DEFAULT_BLOCKS;
            };

            // 实时动态同步输入端口数
            nodeType.prototype.syncDynamicInputs = function (totalBlocks) {
                if (!totalBlocks || totalBlocks < 1) {
                    totalBlocks = this.detectTotalBlocksFromLink();
                }
                totalBlocks = Math.min(MAX_BLOCKS, Math.max(1, totalBlocks));

                if (!this.inputs) this.inputs = [];

                // 确保已有连线的端口绝不被意外截断
                for (let i = 0; i < this.inputs.length; i++) {
                    const inp = this.inputs[i];
                    const m = inp.name.match(/^块(\d+)_图片$/);
                    if (m && inp.link != null) {
                        const num = parseInt(m[1]);
                        if (num > totalBlocks) {
                            totalBlocks = Math.min(MAX_BLOCKS, num);
                        }
                    }
                }

                const desiredInputs = [
                    { name: "基底原图", type: "IMAGE" },
                    { name: "切片数据", type: "STRING" },
                    { name: "批次替换图片", type: "IMAGE" }
                ];

                for (let i = 1; i <= totalBlocks; i++) {
                    desiredInputs.push({ name: `块${i}_图片`, type: "IMAGE" });
                }

                let needsUpdate = false;
                if (this.inputs.length !== desiredInputs.length) {
                    needsUpdate = true;
                } else {
                    for (let i = 0; i < desiredInputs.length; i++) {
                        if (this.inputs[i].name !== desiredInputs[i].name) {
                            needsUpdate = true;
                            break;
                        }
                    }
                }

                if (needsUpdate) {
                    // 安全裁剪多余端口（只裁剪末尾无连线端口）
                    while (this.inputs.length > desiredInputs.length) {
                        const lastIdx = this.inputs.length - 1;
                        if (this.inputs[lastIdx].link != null) break;
                        this.removeInput(lastIdx);
                    }

                    for (let i = 0; i < desiredInputs.length; i++) {
                        const desired = desiredInputs[i];
                        if (i < this.inputs.length) {
                            this.inputs[i].name = desired.name;
                            this.inputs[i].type = desired.type;
                        } else {
                            this.addInput(desired.name, desired.type);
                        }
                    }

                    this.setSize(this.computeSize());
                    this.setDirtyCanvas(true, true);
                }
            };

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                if (!this.size || this.size[0] < 340 || this.size[1] < 360) {
                    this.size = [350, 420];
                }

                this.color = "#1e293b";
                this.bgcolor = "#0f172a";

                // 首次创建时同步端口
                setTimeout(() => {
                    this.syncDynamicInputs();
                }, 20);

                return r;
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
                setTimeout(() => {
                    this.syncDynamicInputs();
                }, 50);
                return r;
            };

            // 监听连线变动事件：连入或断开【切片数据】时立即自适应更新端口数量
            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function (type, index, isConnected, link_info) {
                onConnectionsChange?.apply(this, arguments);

                // type: 1 代表 INPUT 输入端连接变动
                if (type === 1) {
                    setTimeout(() => {
                        const total = this.detectTotalBlocksFromLink();
                        this.syncDynamicInputs(total);
                    }, 30);
                }
            };

            // 绘制节点底部提示小徽章
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function (ctx) {
                onDrawForeground?.apply(this, arguments);

                if (this.flags?.collapsed) return;

                const blockInputs = (this.inputs || []).filter(inp => inp.name.startsWith("块"));
                const count = blockInputs.length;

                ctx.save();
                ctx.font = "11px sans-serif";
                ctx.fillStyle = "rgba(148, 163, 184, 0.6)";
                ctx.textAlign = "center";
                ctx.fillText(`🧩 PJ 切片原位还原器 • 动态感应: ${count} 块`, this.size[0] / 2, this.size[1] - 8);
                ctx.restore();
            };
        }
    }
});
