import { app } from "/scripts/app.js";

app.registerExtension({
    name: "PJ.ImageStitcher",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Image_Stitcher") {
            const DEFAULT_SLOTS = 5;
            const MAX_SLOTS = 30;

            function getSlotInputs(node) {
                if (!node.inputs) return [];
                const slots = [];
                for (let i = 0; i < node.inputs.length; i++) {
                    const match = node.inputs[i].name.match(/^槽位(\d+)_图片$/);
                    if (match) {
                        slots.push({
                            index: i,
                            slotNum: parseInt(match[1]),
                            input: node.inputs[i]
                        });
                    }
                }
                slots.sort((a, b) => a.slotNum - b.slotNum);
                return slots;
            }

            function checkAndAdjustSlots(node) {
                if (!node.inputs) return;

                let slots = getSlotInputs(node);

                // 1. 如果初始槽位数小于 5，补齐至默认 5 个
                let currentMax = slots.length > 0 ? slots[slots.length - 1].slotNum : 0;
                while (slots.length < DEFAULT_SLOTS) {
                    currentMax++;
                    const batchIdx = node.inputs.findIndex(inp => inp.name === "批次图片输入");
                    if (batchIdx !== -1) {
                        node.addInput(`槽位${currentMax}_图片`, "IMAGE");
                        const last = node.inputs.pop();
                        node.inputs.splice(batchIdx, 0, last);
                    } else {
                        node.addInput(`槽位${currentMax}_图片`, "IMAGE");
                    }
                    slots = getSlotInputs(node);
                }

                // 2. 检查现有所有槽位是否“全满”
                // 条件：当前所有已存在的槽位全部接上了连接线 (link != null)
                const allFull = slots.length > 0 && slots.every(s => s.input.link != null);

                if (allFull && slots.length < MAX_SLOTS) {
                    // 当槽位全满了，立即自动新增 1 个新槽位
                    const nextNum = slots[slots.length - 1].slotNum + 1;
                    const batchIdx = node.inputs.findIndex(inp => inp.name === "批次图片输入");
                    if (batchIdx !== -1) {
                        node.addInput(`槽位${nextNum}_图片`, "IMAGE");
                        const last = node.inputs.pop();
                        node.inputs.splice(batchIdx, 0, last);
                    } else {
                        node.addInput(`槽位${nextNum}_图片`, "IMAGE");
                    }
                    node.setSize(node.computeSize());
                    node.setDirtyCanvas(true, true);
                } else if (!allFull && slots.length > DEFAULT_SLOTS) {
                    // 如果槽位没满，且总槽位数大于 5：
                    // 若末尾存在未连线的空槽位，且前面也已经有空槽位时，清理末尾多余空槽位（保留最多1个空位供输入）
                    let updated = false;
                    for (let i = node.inputs.length - 1; i >= 0; i--) {
                        const match = node.inputs[i].name.match(/^槽位(\d+)_图片$/);
                        if (match) {
                            const slotNum = parseInt(match[1]);
                            const currentSlots = getSlotInputs(node);
                            if (currentSlots.length <= DEFAULT_SLOTS) break;

                            // 如果当前槽位没接线，且前面已经有空余槽位
                            if (node.inputs[i].link == null) {
                                const hasEmptyBefore = currentSlots.some(s => s.slotNum < slotNum && s.input.link == null);
                                if (hasEmptyBefore) {
                                    node.removeInput(i);
                                    updated = true;
                                }
                            }
                        }
                    }
                    if (updated) {
                        node.setSize(node.computeSize());
                        node.setDirtyCanvas(true, true);
                    }
                }
            }

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // 初始创建时，修剪多余的未连接槽位，默认只展示前 5 个槽位
                if (this.inputs) {
                    for (let i = this.inputs.length - 1; i >= 0; i--) {
                        const match = this.inputs[i].name.match(/^槽位(\d+)_图片$/);
                        if (match) {
                            const slotNum = parseInt(match[1]);
                            if (slotNum > DEFAULT_SLOTS && this.inputs[i].link == null) {
                                this.removeInput(i);
                            }
                        }
                    }
                }

                this.setSize(this.computeSize());
                return r;
            };

            // 监听连线事件：只有当现有槽位全都连满时，才自动新增一个槽位
            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function (type, index, isConnected, link_info, inputSlot) {
                const r = onConnectionsChange ? onConnectionsChange.apply(this, arguments) : undefined;

                if (type === 1 || type === (LiteGraph?.INPUT ?? 1)) {
                    checkAndAdjustSlots(this);
                }

                return r;
            };

            // 兼容已有工作流加载
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
                checkAndAdjustSlots(this);
                return r;
            };
        }
    }
});
