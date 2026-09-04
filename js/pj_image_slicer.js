import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

function getImageUrl(data) {
    if (!data) return "";
    return api.apiURL(`/view?filename=${encodeURIComponent(data.filename)}&type=${data.type}&subfolder=${encodeURIComponent(data.subfolder)}${app.getPreviewFormatParam()}${app.getRandParam()}`);
}

app.registerExtension({
    name: "PJ.ImageInteractiveSlicer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Image_Interactive_Slicer") {
            const MAX_BLOCKS = 30;

            // 1. 核心防护：拦截 ComfyUI 前端自动为图片节点创建的 DOM 浮层与图片元素
            const origAddDOMWidget = nodeType.prototype.addDOMWidget;
            nodeType.prototype.addDOMWidget = function (name, type, element, options) {
                if (type === "img" || type === "image" || name === "preview" || (element && element.querySelector && element.querySelector("img"))) {
                    if (element && element.parentNode) {
                        element.parentNode.removeChild(element);
                    }
                    return null;
                }
                return origAddDOMWidget ? origAddDOMWidget.apply(this, arguments) : null;
            };

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                this.cutlines = { horizontal: [], vertical: [] };
                this.selectedLine = null; // { type: 'h' | 'v', index: number }
                this.hoverLine = null;
                this.hoverTag = null; // { type: 'h' | 'v', index: number }
                this.activeMode = "idle"; // 'idle', 'add_h', 'add_v', 'moving_line'
                this.mousePos = [0, 0];
                this.isFocused = false;
                this.previewImg = null;

                // 锁定 node.imgs 永远为 null，彻底杜绝 ComfyUI / LiteGraph 在底层自动绘制浮层
                try {
                    Object.defineProperty(this, "imgs", {
                        get: () => null,
                        set: (v) => {},
                        configurable: true
                    });
                    Object.defineProperty(this, "image", {
                        get: () => null,
                        set: (v) => {},
                        configurable: true
                    });
                    Object.defineProperty(this, "images", {
                        get: () => null,
                        set: (v) => {},
                        configurable: true
                    });
                } catch (e) {}

                // 设置默认初始节点尺寸
                if (!this.size || this.size[0] < 480 || this.size[1] < 640) {
                    this.size = [480, 640];
                }

                // 隐藏内部数据通信控件
                this.cleanInternalWidgets();

                // 恢复保存的切线数据
                const cutWidget = this.widgets ? this.widgets.find(w => w.name === "切线数据") : null;
                if (cutWidget && cutWidget.value) {
                    try {
                        const parsed = typeof cutWidget.value === "string" ? JSON.parse(cutWidget.value) : cutWidget.value;
                        if (parsed.horizontal) this.cutlines.horizontal = parsed.horizontal;
                        if (parsed.vertical) this.cutlines.vertical = parsed.vertical;
                    } catch (e) {}
                }

                // 监听图片上传/选择事件
                this.setupImageWidgetListener();

                // 动态端口初始化
                this.updateDynamicOutputs();

                // 全局键盘监听：DEL/退格键删除、方向键精确微调、回车精准输入
                if (!this._keyHandlerBound) {
                    this._keyHandler = (e) => {
                        const isNodeSelected = app.canvas?.selected_nodes && app.canvas.selected_nodes[this.id];
                        if (!isNodeSelected || !this.selectedLine) return;

                        const { type, index } = this.selectedLine;
                        const isH = (type === "h");
                        const arr = isH ? this.cutlines.horizontal : this.cutlines.vertical;
                        if (arr[index] === undefined) return;

                        // 1. 删除切线 (DEL / 退格键)
                        if (e.key === "Delete" || e.key === "Backspace") {
                            arr.splice(index, 1);
                            this.selectedLine = null;
                            this.hoverLine = null;
                            this.hoverTag = null;
                            this.activeMode = "idle";
                            this.saveCutData();
                            this.updateDynamicOutputs();
                            this.setDirtyCanvas(true, true);
                            e.preventDefault();
                            e.stopPropagation();
                            return;
                        }

                        // 2. 回车键直接弹出精确分值输入对话框
                        if (e.key === "Enter") {
                            this.showPrecisionPopover(null, type, index);
                            e.preventDefault();
                            e.stopPropagation();
                            return;
                        }

                        // 3. 方向键高精度微调：
                        //    默认步长: 0.1% (0.001)
                        //    按住 Shift: 1.0% (0.01)
                        //    按住 Ctrl/Alt: 0.01% (0.0001)
                        let delta = 0;
                        const step = (e.ctrlKey || e.altKey) ? 0.0001 : (e.shiftKey ? 0.01 : 0.001);

                        if (isH) {
                            if (e.key === "ArrowUp") delta = -step;
                            else if (e.key === "ArrowDown") delta = step;
                        } else {
                            if (e.key === "ArrowLeft") delta = -step;
                            else if (e.key === "ArrowRight") delta = step;
                        }

                        if (delta !== 0) {
                            let updated = arr[index] + delta;
                            updated = Math.max(0.001, Math.min(0.999, parseFloat(updated.toFixed(4))));
                            arr[index] = updated;
                            this.saveCutData();
                            this.updateDynamicOutputs();
                            this.setDirtyCanvas(true);
                            e.preventDefault();
                            e.stopPropagation();
                        }
                    };
                    window.addEventListener("keydown", this._keyHandler);
                    this._keyHandlerBound = true;
                }

                return r;
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
                this.cleanInternalWidgets();
                this.setupImageWidgetListener();
                return r;
            };

            const onRemoved = nodeType.prototype.onRemoved;
            nodeType.prototype.onRemoved = function () {
                if (this._keyHandler) {
                    window.removeEventListener("keydown", this._keyHandler);
                    this._keyHandler = null;
                }
                onRemoved?.apply(this, arguments);
            };

            // 清理并隐藏内部 widgets 与 ComfyUI 自动创建的图片 preview widget
            nodeType.prototype.cleanInternalWidgets = function () {
                if (!this.widgets) return;
                for (let i = this.widgets.length - 1; i >= 0; i--) {
                    const w = this.widgets[i];
                    if (w.name === "切线数据") {
                        w.type = "hidden";
                        w.computeSize = () => [0, -4];
                    }
                    if (w.type === "img" || w.type === "image" || w.name === "preview" || (w.element && w.element.querySelector && w.element.querySelector("img"))) {
                        if (w.element && w.element.parentNode) {
                            w.element.parentNode.removeChild(w.element);
                        }
                        this.widgets.splice(i, 1);
                    }
                }
            };

            // 监听图片选择
            nodeType.prototype.setupImageWidgetListener = function () {
                const imgWidget = this.widgets ? this.widgets.find(w => w.name === "上传图片" || w.name === "image") : null;
                if (imgWidget && !imgWidget._pj_hooked) {
                    const origCallback = imgWidget.callback;
                    imgWidget.callback = (val) => {
                        if (origCallback) origCallback.apply(imgWidget, arguments);
                        if (val) this.loadPreviewFromInput(val);
                    };
                    imgWidget._pj_hooked = true;

                    if (imgWidget.value) {
                        this.loadPreviewFromInput(imgWidget.value);
                    }
                }
            };

            // 加载 ComfyUI input 目录的图片
            nodeType.prototype.loadPreviewFromInput = function (filename) {
                if (!filename || typeof filename !== "string") return;
                const img = new Image();
                img.onload = () => {
                    this.previewImg = img;
                    this.setDirtyCanvas(true, true);
                };
                img.src = api.apiURL(`/view?filename=${encodeURIComponent(filename)}&type=input`);
            };

            // 支持直接拖拽图片文件到节点
            nodeType.prototype.onDragOver = function (e) {
                if (e.dataTransfer && e.dataTransfer.types.includes("Files")) {
                    return true;
                }
            };

            nodeType.prototype.onDropFile = function (file) {
                if (!file || !file.type.startsWith("image/")) return false;
                const formData = new FormData();
                formData.append("image", file);
                formData.append("overwrite", "true");
                api.fetchApi("/upload/image", { method: "POST", body: formData })
                    .then(res => res.json())
                    .then(data => {
                        if (data?.name) {
                            const w = this.widgets?.find(w => w.name === "上传图片" || w.name === "image");
                            if (w) {
                                if (w.options?.values && !w.options.values.includes(data.name)) {
                                    w.options.values.push(data.name);
                                }
                                w.value = data.name;
                                if (w.callback) w.callback(data.name);
                            }
                            this.loadPreviewFromInput(data.name);
                        }
                    })
                    .catch(err => {
                        console.error("[PJ Image Slicer] 上传图片失败:", err);
                    });
                return true;
            };

            nodeType.prototype.saveCutData = function () {
                this.cutlines.horizontal.sort((a, b) => a - b);
                this.cutlines.vertical.sort((a, b) => a - b);
                const str = JSON.stringify(this.cutlines);
                const widget = this.widgets ? this.widgets.find(w => w.name === "切线数据") : null;
                if (widget) {
                    widget.value = str;
                }
            };

            nodeType.prototype.updateDynamicOutputs = function () {
                const hCount = this.cutlines.horizontal.length;
                const vCount = this.cutlines.vertical.length;
                const totalBlocks = Math.min(MAX_BLOCKS, (hCount + 1) * (vCount + 1));

                if (!this.outputs) this.outputs = [];

                const desiredNames = [];
                for (let i = 1; i <= totalBlocks; i++) {
                    desiredNames.push(`块${i}_图片`);
                }
                desiredNames.push("全部块_批次");
                desiredNames.push("切片信息");

                let needsUpdate = false;
                if (this.outputs.length !== desiredNames.length) {
                    needsUpdate = true;
                } else {
                    for (let i = 0; i < desiredNames.length; i++) {
                        if (this.outputs[i].name !== desiredNames[i]) {
                            needsUpdate = true;
                            break;
                        }
                    }
                }

                if (needsUpdate) {
                    this.outputs = [];
                    for (let i = 0; i < desiredNames.length; i++) {
                        const name = desiredNames[i];
                        const type = name === "切片信息" ? "STRING" : "IMAGE";
                        this.addOutput(name, type);
                    }
                    this.setDirtyCanvas(true, true);
                }
            };

            // 监听节点运行完成事件 (接收上游生图传递的预览)
            nodeType.prototype.onExecuted = function (message) {
                if (message?.pj_preview && message.pj_preview.length > 0) {
                    const img = new Image();
                    img.onload = () => {
                        this.previewImg = img;
                        this.setDirtyCanvas(true);
                    };
                    img.src = getImageUrl(message.pj_preview[0]);
                }
            };

            // 精准计算各绘制层坐标，确保控件层、按钮层、图片层绝不重叠
            nodeType.prototype.getCanvasRect = function () {
                const margin = 12;
                const toolbarHeight = 30;
                const bottomBarHeight = 32;

                let widgetsBottom = 50;
                const inCount = this.inputs ? this.inputs.length : 0;
                const outCount = this.outputs ? this.outputs.length : 0;
                widgetsBottom = Math.max(widgetsBottom, 30 + Math.max(inCount, outCount) * 20);

                if (this.widgets) {
                    for (const w of this.widgets) {
                        if (w.type !== "hidden" && (!w.computeSize || w.computeSize()[1] > 0)) {
                            const wy = (w.last_y !== undefined && w.last_y > 0) ? (w.last_y + (w.height || 26)) : 0;
                            if (wy > widgetsBottom) widgetsBottom = wy;
                        }
                    }
                }

                if (widgetsBottom < 145) {
                    widgetsBottom = 145;
                }

                const toolbarY = widgetsBottom + 8;
                const contentTop = toolbarY + toolbarHeight + 10;

                const minWidth = 480;
                const minHeight = contentTop + 240 + bottomBarHeight;
                if (this.size[0] < minWidth) this.size[0] = minWidth;
                if (this.size[1] < minHeight) this.size[1] = minHeight;

                const cw = Math.max(100, this.size[0] - margin * 2);
                const ch = Math.max(100, this.size[1] - contentTop - bottomBarHeight);

                if (this.previewImg && this.previewImg.naturalWidth > 0) {
                    const ir = this.previewImg.naturalWidth / this.previewImg.naturalHeight;
                    const ar = cw / ch;
                    let dw, dh;
                    if (ir > ar) {
                        dw = cw;
                        dh = cw / ir;
                    } else {
                        dh = ch;
                        dw = ch * ir;
                    }
                    const dx = margin + (cw - dw) / 2;
                    const dy = contentTop + (ch - dh) / 2;
                    return {
                        x: dx, y: dy, w: dw, h: dh,
                        toolbarY: toolbarY,
                        toolbarH: toolbarHeight,
                        contentTop: contentTop,
                        boxX: margin, boxY: contentTop, boxW: cw, boxH: ch
                    };
                }

                return {
                    x: margin, y: contentTop, w: cw, h: ch,
                    toolbarY: toolbarY,
                    toolbarH: toolbarHeight,
                    contentTop: contentTop,
                    boxX: margin, boxY: contentTop, boxW: cw, boxH: ch
                };
            };

            // 获取切线百分比标签的点击判定矩形
            nodeType.prototype.getTagRect = function (rect, type, index) {
                const tagW = 54;
                const tagH = 20;
                if (type === "h") {
                    const ratio = this.cutlines.horizontal[index];
                    if (ratio === undefined) return null;
                    const ly = rect.y + ratio * rect.h;
                    return { x: rect.x + 4, y: ly - 10, w: tagW, h: tagH };
                } else {
                    const ratio = this.cutlines.vertical[index];
                    if (ratio === undefined) return null;
                    const lx = rect.x + ratio * rect.w;
                    return { x: lx - tagW / 2, y: rect.y + 4, w: tagW, h: tagH };
                }
            };

            // 优雅节点内原生暗黑风格精准微调弹层 (彻底替代浏览器原生系统 window.prompt)
            nodeType.prototype.showPrecisionPopover = function (e, type, index) {
                const isH = (type === "h");
                const arr = isH ? this.cutlines.horizontal : this.cutlines.vertical;
                if (arr[index] === undefined) return;

                const oldPopover = document.getElementById("pj-slicer-popover");
                if (oldPopover) oldPopover.remove();

                const currentRatio = arr[index];
                const currentPercent = (currentRatio * 100).toFixed(2);
                const totalPx = isH
                    ? (this.previewImg?.naturalHeight || 0)
                    : (this.previewImg?.naturalWidth || 0);
                const currentPx = totalPx > 0 ? Math.round(currentRatio * totalPx) : null;

                const popover = document.createElement("div");
                popover.id = "pj-slicer-popover";
                popover.style.cssText = `
                    position: fixed;
                    background: #202020;
                    border: 1.5px solid #FFD700;
                    border-radius: 8px;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.85);
                    padding: 12px 14px;
                    z-index: 100000;
                    color: #eee;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                    font-size: 12px;
                    min-width: 250px;
                    user-select: none;
                    backdrop-filter: blur(8px);
                    transform: translate(-50%, -100%);
                    margin-top: -12px;
                `;

                let screenX = window.innerWidth / 2;
                let screenY = window.innerHeight / 2;
                if (e && e.clientX && e.clientY) {
                    screenX = Math.max(140, Math.min(window.innerWidth - 140, e.clientX));
                    screenY = Math.max(120, Math.min(window.innerHeight - 30, e.clientY));
                }
                popover.style.left = `${screenX}px`;
                popover.style.top = `${screenY}px`;

                popover.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="color: #FFD700; font-weight: bold; font-size: 13px;">✂️ 精准调整 ${isH ? "横向切线" : "竖向切线"}</span>
                        <button id="pj-pop-close" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px; padding: 0 4px;">✕</button>
                    </div>
                    <div style="color: #aaa; font-size: 11px; margin-bottom: 8px;">
                        当前位置: <b style="color: #00E5FF;">${currentPercent}%</b> ${currentPx ? `(约 ${currentPx}px / 总长 ${totalPx}px)` : ""}
                    </div>
                    <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                        <input id="pj-pop-input" type="text" value="${(currentRatio * 100).toFixed(1)}" placeholder="例如: 50 或 500px" style="
                            flex: 1;
                            background: #121212;
                            border: 1px solid #555;
                            color: #fff;
                            padding: 6px 10px;
                            border-radius: 4px;
                            font-size: 13px;
                            outline: none;
                            font-weight: bold;
                            text-align: center;
                        " />
                        <button id="pj-pop-submit" style="
                            background: #009688;
                            border: none;
                            color: #fff;
                            padding: 6px 14px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-weight: bold;
                            font-size: 12px;
                            white-space: nowrap;
                        ">确定</button>
                    </div>
                    <div style="color: #777; font-size: 10px; margin-bottom: 6px;">快捷等分比例：</div>
                    <div style="display: flex; gap: 4px; justify-content: space-between;">
                        <button class="pj-quick-ratio" data-ratio="0.25" style="background: #2a2a2a; border: 1px solid #444; color: #ddd; padding: 3px 6px; border-radius: 3px; cursor: pointer; font-size: 11px; flex: 1;">25%</button>
                        <button class="pj-quick-ratio" data-ratio="0.3333" style="background: #2a2a2a; border: 1px solid #444; color: #ddd; padding: 3px 6px; border-radius: 3px; cursor: pointer; font-size: 11px; flex: 1;">33.3%</button>
                        <button class="pj-quick-ratio" data-ratio="0.50" style="background: #2a2a2a; border: 1px solid #444; color: #ddd; padding: 3px 6px; border-radius: 3px; cursor: pointer; font-size: 11px; flex: 1;">50%</button>
                        <button class="pj-quick-ratio" data-ratio="0.6667" style="background: #2a2a2a; border: 1px solid #444; color: #ddd; padding: 3px 6px; border-radius: 3px; cursor: pointer; font-size: 11px; flex: 1;">66.7%</button>
                        <button class="pj-quick-ratio" data-ratio="0.75" style="background: #2a2a2a; border: 1px solid #444; color: #ddd; padding: 3px 6px; border-radius: 3px; cursor: pointer; font-size: 11px; flex: 1;">75%</button>
                    </div>
                `;

                document.body.appendChild(popover);

                const inputElem = popover.querySelector("#pj-pop-input");
                const submitBtn = popover.querySelector("#pj-pop-submit");
                const closeBtn = popover.querySelector("#pj-pop-close");

                setTimeout(() => {
                    if (inputElem) {
                        inputElem.focus();
                        inputElem.select();
                    }
                }, 20);

                const closePopover = () => {
                    if (popover && popover.parentNode) {
                        popover.parentNode.removeChild(popover);
                    }
                    document.removeEventListener("mousedown", onDocMouseDown);
                    document.removeEventListener("keydown", onDocKeyDown);
                };

                const applyValue = (valStr) => {
                    if (!valStr || valStr.trim() === "") {
                        closePopover();
                        return;
                    }
                    const trimmed = valStr.trim();
                    let newRatio = null;

                    if (trimmed.endsWith("%")) {
                        const v = parseFloat(trimmed.slice(0, -1));
                        if (!isNaN(v)) newRatio = v / 100.0;
                    } else if (trimmed.toLowerCase().endsWith("px")) {
                        const v = parseFloat(trimmed.slice(0, -2));
                        if (!isNaN(v) && totalPx > 0) newRatio = v / totalPx;
                    } else {
                        const v = parseFloat(trimmed);
                        if (!isNaN(v)) {
                            if (v > 100 && totalPx > 0) {
                                newRatio = v / totalPx;
                            } else {
                                newRatio = v / 100.0;
                            }
                        }
                    }

                    if (newRatio !== null && !isNaN(newRatio)) {
                        newRatio = Math.max(0.001, Math.min(0.999, parseFloat(newRatio.toFixed(4))));
                        arr[index] = newRatio;
                        this.selectedLine = { type, index };
                        this.activeMode = "idle";
                        this.saveCutData();
                        this.updateDynamicOutputs();
                        this.setDirtyCanvas(true, true);
                    }
                    closePopover();
                };

                submitBtn.addEventListener("click", () => applyValue(inputElem.value));
                closeBtn.addEventListener("click", closePopover);

                popover.querySelectorAll(".pj-quick-ratio").forEach(btn => {
                    btn.addEventListener("click", () => {
                        const r = parseFloat(btn.getAttribute("data-ratio"));
                        if (!isNaN(r)) {
                            arr[index] = r;
                            this.selectedLine = { type, index };
                            this.activeMode = "idle";
                            this.saveCutData();
                            this.updateDynamicOutputs();
                            this.setDirtyCanvas(true, true);
                            closePopover();
                        }
                    });
                });

                const onDocKeyDown = (evt) => {
                    if (evt.key === "Enter") {
                        evt.preventDefault();
                        evt.stopPropagation();
                        applyValue(inputElem.value);
                    } else if (evt.key === "Escape") {
                        evt.preventDefault();
                        evt.stopPropagation();
                        closePopover();
                    }
                };
                document.addEventListener("keydown", onDocKeyDown);

                const onDocMouseDown = (evt) => {
                    if (!popover.contains(evt.target)) {
                        closePopover();
                    }
                };
                setTimeout(() => {
                    document.addEventListener("mousedown", onDocMouseDown);
                }, 50);
            };

            nodeType.prototype.onMouseMove = function (e, pos) {
                const rect = this.getCanvasRect();
                this.mousePos = [pos[0], pos[1]];

                const isInside = pos[0] >= rect.x && pos[0] <= rect.x + rect.w && pos[1] >= rect.y && pos[1] <= rect.y + rect.h;
                this.isFocused = isInside;

                // 辅助吸附函数：按住 Shift 时自动吸附到常用刻度 (10%, 20%, 25%, 33.3%, 50%, 66.7%, 75% 等)
                const snapRatio = (val) => {
                    if (!e.shiftKey) return val;
                    const snapPoints = [0.1, 0.2, 0.25, 0.3333, 0.4, 0.5, 0.6, 0.6667, 0.75, 0.8, 0.9];
                    for (const sp of snapPoints) {
                        if (Math.abs(val - sp) < 0.018) {
                            return sp;
                        }
                    }
                    return val;
                };

                // 处于“重新控制切线”状态，移动切线
                if (this.activeMode === "moving_line" && this.selectedLine && isInside) {
                    const { type, index } = this.selectedLine;
                    if (type === "h") {
                        let ratio = Math.max(0.01, Math.min(0.99, (pos[1] - rect.y) / rect.h));
                        ratio = snapRatio(ratio);
                        this.cutlines.horizontal[index] = parseFloat(ratio.toFixed(4));
                    } else if (type === "v") {
                        let ratio = Math.max(0.01, Math.min(0.99, (pos[0] - rect.x) / rect.w));
                        ratio = snapRatio(ratio);
                        this.cutlines.vertical[index] = parseFloat(ratio.toFixed(4));
                    }
                    this.setDirtyCanvas(true);
                    return;
                }

                // 悬停检测：优先检测是否悬停在百分比分值标签上
                this.hoverTag = null;
                this.hoverLine = null;

                if (isInside && this.activeMode === "idle") {
                    // 1. 检查横向标签悬停
                    for (let i = 0; i < this.cutlines.horizontal.length; i++) {
                        const tr = this.getTagRect(rect, "h", i);
                        if (tr && pos[0] >= tr.x && pos[0] <= tr.x + tr.w && pos[1] >= tr.y && pos[1] <= tr.y + tr.h) {
                            this.hoverTag = { type: "h", index: i };
                            this.hoverLine = { type: "h", index: i };
                            break;
                        }
                    }

                    // 2. 检查竖向标签悬停
                    if (!this.hoverTag) {
                        for (let i = 0; i < this.cutlines.vertical.length; i++) {
                            const tr = this.getTagRect(rect, "v", i);
                            if (tr && pos[0] >= tr.x && pos[0] <= tr.x + tr.w && pos[1] >= tr.y && pos[1] <= tr.y + tr.h) {
                                this.hoverTag = { type: "v", index: i };
                                this.hoverLine = { type: "v", index: i };
                                break;
                            }
                        }
                    }

                    // 3. 若不在标签上，检查切线身体悬停
                    if (!this.hoverTag) {
                        const tolerance = 8;
                        for (let i = 0; i < this.cutlines.horizontal.length; i++) {
                            const ly = rect.y + this.cutlines.horizontal[i] * rect.h;
                            if (Math.abs(pos[1] - ly) <= tolerance) {
                                this.hoverLine = { type: "h", index: i };
                                break;
                            }
                        }
                        if (!this.hoverLine) {
                            for (let i = 0; i < this.cutlines.vertical.length; i++) {
                                const lx = rect.x + this.cutlines.vertical[i] * rect.w;
                                if (Math.abs(pos[0] - lx) <= tolerance) {
                                    this.hoverLine = { type: "v", index: i };
                                    break;
                                }
                            }
                        }
                    }
                }

                this.setDirtyCanvas(true);
            };

            nodeType.prototype.onMouseLeave = function () {
                this.isFocused = false;
                this.hoverLine = null;
                this.hoverTag = null;
                this.setDirtyCanvas(true);
            };

            nodeType.prototype.onMouseDown = function (e, pos) {
                const rect = this.getCanvasRect();

                // 1. 最高优先级：工具栏按钮点击判定 (横线、竖线、清空)
                if (pos[1] >= rect.toolbarY && pos[1] <= rect.toolbarY + rect.toolbarH && pos[0] >= 12 && pos[0] <= this.size[0] - 12) {
                    const totalW = this.size[0] - 24;
                    const btnW = totalW / 3;
                    const btnIdx = Math.floor((pos[0] - 12) / btnW);

                    if (btnIdx === 0) {
                        this.activeMode = this.activeMode === "add_h" ? "idle" : "add_h";
                        this.selectedLine = null;
                        this.setDirtyCanvas(true);
                        return true;
                    } else if (btnIdx === 1) {
                        this.activeMode = this.activeMode === "add_v" ? "idle" : "add_v";
                        this.selectedLine = null;
                        this.setDirtyCanvas(true);
                        return true;
                    } else if (btnIdx === 2) {
                        this.cutlines.horizontal = [];
                        this.cutlines.vertical = [];
                        this.selectedLine = null;
                        this.hoverLine = null;
                        this.hoverTag = null;
                        this.activeMode = "idle";
                        this.saveCutData();
                        this.updateDynamicOutputs();
                        this.setDirtyCanvas(true, true);
                        return true;
                    }
                }

                // 2. 画布内部交互点击
                if (pos[0] >= rect.x && pos[0] <= rect.x + rect.w && pos[1] >= rect.y && pos[1] <= rect.y + rect.h) {
                    // 如果正在移动切线 -> 单击落位锁定
                    if (this.activeMode === "moving_line") {
                        this.activeMode = "idle";
                        this.saveCutData();
                        this.updateDynamicOutputs();
                        this.setDirtyCanvas(true, true);
                        return true;
                    }

                    // 如果处于新增横线模式 -> 落刀
                    if (this.activeMode === "add_h") {
                        let ratio = Math.max(0.01, Math.min(0.99, (pos[1] - rect.y) / rect.h));
                        if (e.shiftKey) {
                            const snapPoints = [0.1, 0.2, 0.25, 0.3333, 0.4, 0.5, 0.6, 0.6667, 0.75, 0.8, 0.9];
                            for (const sp of snapPoints) {
                                if (Math.abs(ratio - sp) < 0.018) { ratio = sp; break; }
                            }
                        }
                        this.cutlines.horizontal.push(parseFloat(ratio.toFixed(4)));
                        this.activeMode = "idle";
                        this.selectedLine = null;
                        this.saveCutData();
                        this.updateDynamicOutputs();
                        this.setDirtyCanvas(true, true);
                        return true;
                    }

                    // 如果处于新增竖线模式 -> 落刀
                    if (this.activeMode === "add_v") {
                        let ratio = Math.max(0.01, Math.min(0.99, (pos[0] - rect.x) / rect.w));
                        if (e.shiftKey) {
                            const snapPoints = [0.1, 0.2, 0.25, 0.3333, 0.4, 0.5, 0.6, 0.6667, 0.75, 0.8, 0.9];
                            for (const sp of snapPoints) {
                                if (Math.abs(ratio - sp) < 0.018) { ratio = sp; break; }
                            }
                        }
                        this.cutlines.vertical.push(parseFloat(ratio.toFixed(4)));
                        this.activeMode = "idle";
                        this.selectedLine = null;
                        this.saveCutData();
                        this.updateDynamicOutputs();
                        this.setDirtyCanvas(true, true);
                        return true;
                    }

                    // 核心亮点：点击百分比标签直接弹出节点内高颜值精确输入窗口！
                    if (this.hoverTag) {
                        const { type, index } = this.hoverTag;
                        this.selectedLine = { type, index };
                        this.setDirtyCanvas(true);
                        this.showPrecisionPopover(e, type, index);
                        return true;
                    }

                    // 单击切线身体 -> 选中切线并进入再次控制移动模式
                    if (this.hoverLine) {
                        this.selectedLine = { ...this.hoverLine };
                        this.activeMode = "moving_line";
                        this.setDirtyCanvas(true);
                        return true;
                    } else {
                        if (this.selectedLine) {
                            this.selectedLine = null;
                            this.setDirtyCanvas(true);
                        }
                    }
                }
            };

            // 支持双击切线或标签打开节点内精准输入
            nodeType.prototype.onDblClick = function (e, pos) {
                const target = this.hoverTag || this.hoverLine;
                if (target) {
                    this.showPrecisionPopover(e, target.type, target.index);
                    return true;
                }
            };

            nodeType.prototype.onDrawForeground = function (ctx) {
                if (this.flags.collapsed) return;

                this.cleanInternalWidgets();

                const rect = this.getCanvasRect();
                const totalW = this.size[0] - 24;

                // =============================================================
                // 层级 1 (底层): 绘制图像预览背景与底图
                // =============================================================
                ctx.save();
                ctx.fillStyle = "#121212";
                ctx.strokeStyle = "#383838";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.roundRect(rect.boxX, rect.boxY, rect.boxW, rect.boxH, 6);
                ctx.fill();
                ctx.stroke();

                const hasValidImage = this.previewImg && this.previewImg.complete && this.previewImg.naturalWidth > 0;

                if (hasValidImage) {
                    try {
                        ctx.drawImage(this.previewImg, rect.x, rect.y, rect.w, rect.h);
                        ctx.strokeStyle = "#444";
                        ctx.lineWidth = 1;
                        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
                    } catch (e) {}
                } else {
                    ctx.save();
                    ctx.strokeStyle = "#4A4A4A";
                    ctx.lineWidth = 1.5;
                    ctx.setLineDash([5, 5]);
                    ctx.strokeRect(rect.x + 10, rect.y + 10, rect.w - 20, rect.h - 20);
                    ctx.setLineDash([]);

                    ctx.fillStyle = "#DDD";
                    ctx.font = "bold 13px Arial";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText("📁 点击上方选择/上传图片，或直接拖拽图片到此", rect.x + rect.w / 2, rect.y + rect.h / 2 - 14);

                    ctx.fillStyle = "#888";
                    ctx.font = "11px Arial";
                    ctx.fillText("(也可从上游工作流节点连接“图像”输入)", rect.x + rect.w / 2, rect.y + rect.h / 2 + 12);
                    ctx.restore();
                }
                ctx.restore();

                // =============================================================
                // 层级 2 (切线层): 绘制横线、竖线及其百分比精准数值标签
                // =============================================================
                ctx.save();
                // 2.1 横向切线
                for (let i = 0; i < this.cutlines.horizontal.length; i++) {
                    const ratio = this.cutlines.horizontal[i];
                    const ly = rect.y + ratio * rect.h;
                    const isSelected = (this.selectedLine && this.selectedLine.type === "h" && this.selectedLine.index === i);
                    const isHover = (this.hoverLine && this.hoverLine.type === "h" && this.hoverLine.index === i);
                    const isTagHover = (this.hoverTag && this.hoverTag.type === "h" && this.hoverTag.index === i);

                    ctx.strokeStyle = isSelected ? "#FFD700" : (isHover ? "#FFF" : "#00E5FF");
                    ctx.lineWidth = (isSelected || isHover) ? 3 : 2;

                    ctx.beginPath();
                    ctx.moveTo(rect.x, ly);
                    ctx.lineTo(rect.x + rect.w, ly);
                    ctx.stroke();

                    // 百分比分值标签
                    const tr = this.getTagRect(rect, "h", i);
                    if (tr) {
                        ctx.fillStyle = isSelected ? "#FFD700" : (isTagHover ? "#FFFFFF" : "rgba(0, 229, 255, 0.9)");
                        ctx.beginPath();
                        ctx.roundRect(tr.x, tr.y, tr.w, tr.h, 4);
                        ctx.fill();

                        if (isTagHover || isSelected) {
                            ctx.strokeStyle = "#000";
                            ctx.lineWidth = 1.5;
                            ctx.stroke();
                        }

                        ctx.fillStyle = "#000";
                        ctx.font = "bold 10px Arial";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        const labelText = isTagHover ? `✎${(ratio * 100).toFixed(1)}%` : `${(ratio * 100).toFixed(1)}%`;
                        ctx.fillText(labelText, tr.x + tr.w / 2, tr.y + tr.h / 2);
                    }
                }

                // 2.2 竖向切线
                for (let i = 0; i < this.cutlines.vertical.length; i++) {
                    const ratio = this.cutlines.vertical[i];
                    const lx = rect.x + ratio * rect.w;
                    const isSelected = (this.selectedLine && this.selectedLine.type === "v" && this.selectedLine.index === i);
                    const isHover = (this.hoverLine && this.hoverLine.type === "v" && this.hoverLine.index === i);
                    const isTagHover = (this.hoverTag && this.hoverTag.type === "v" && this.hoverTag.index === i);

                    ctx.strokeStyle = isSelected ? "#FFD700" : (isHover ? "#FFF" : "#69F0AE");
                    ctx.lineWidth = (isSelected || isHover) ? 3 : 2;

                    ctx.beginPath();
                    ctx.moveTo(lx, rect.y);
                    ctx.lineTo(lx, rect.y + rect.h);
                    ctx.stroke();

                    // 百分比分值标签
                    const tr = this.getTagRect(rect, "v", i);
                    if (tr) {
                        ctx.fillStyle = isSelected ? "#FFD700" : (isTagHover ? "#FFFFFF" : "rgba(105, 240, 174, 0.9)");
                        ctx.beginPath();
                        ctx.roundRect(tr.x, tr.y, tr.w, tr.h, 4);
                        ctx.fill();

                        if (isTagHover || isSelected) {
                            ctx.strokeStyle = "#000";
                            ctx.lineWidth = 1.5;
                            ctx.stroke();
                        }

                        ctx.fillStyle = "#000";
                        ctx.font = "bold 10px Arial";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        const labelText = isTagHover ? `✎${(ratio * 100).toFixed(1)}%` : `${(ratio * 100).toFixed(1)}%`;
                        ctx.fillText(labelText, tr.x + tr.w / 2, tr.y + tr.h / 2);
                    }
                }
                ctx.restore();

                // =============================================================
                // 层级 3 (分块徽章层): 仅在图片有效存在时绘制块中心标号
                // =============================================================
                const hSplits = [0, ...this.cutlines.horizontal, 1];
                const vSplits = [0, ...this.cutlines.vertical, 1];
                const totalRows = hSplits.length - 1;
                const totalCols = vSplits.length - 1;
                const totalBlocks = totalRows * totalCols;

                if (hasValidImage) {
                    ctx.save();
                    let bIndex = 1;
                    for (let r = 0; r < totalRows; r++) {
                        for (let c = 0; c < totalCols; c++) {
                            const rx1 = rect.x + vSplits[c] * rect.w;
                            const rx2 = rect.x + vSplits[c + 1] * rect.w;
                            const ry1 = rect.y + hSplits[r] * rect.h;
                            const ry2 = rect.y + hSplits[r + 1] * rect.h;

                            const cx = (rx1 + rx2) / 2;
                            const cy = (ry1 + ry2) / 2;

                            ctx.fillStyle = "rgba(16, 16, 16, 0.82)";
                            ctx.strokeStyle = "rgba(255, 215, 0, 0.85)";
                            ctx.lineWidth = 1;
                            const badgeW = 48;
                            const badgeH = 22;
                            ctx.beginPath();
                            ctx.roundRect(cx - badgeW / 2, cy - badgeH / 2, badgeW, badgeH, 5);
                            ctx.fill();
                            ctx.stroke();

                            ctx.fillStyle = "#FFD700";
                            ctx.font = "bold 11px Arial";
                            ctx.textAlign = "center";
                            ctx.textBaseline = "middle";
                            ctx.fillText(`块 ${bIndex}`, cx, cy + 1);

                            bIndex++;
                        }
                    }
                    ctx.restore();
                }

                // =============================================================
                // 层级 4 (鼠标跟随与对焦层): 绘制活动切线光标
                // =============================================================
                if (this.isFocused) {
                    ctx.save();
                    if (this.activeMode === "add_h") {
                        const my = Math.max(rect.y + 2, Math.min(rect.y + rect.h - 2, this.mousePos[1]));
                        ctx.strokeStyle = "#FFD700";
                        ctx.lineWidth = 2;
                        ctx.setLineDash([6, 4]);

                        ctx.beginPath();
                        ctx.moveTo(rect.x, my);
                        ctx.lineTo(rect.x + rect.w, my);
                        ctx.stroke();

                        ctx.fillStyle = "rgba(255, 215, 0, 0.95)";
                        ctx.beginPath();
                        ctx.roundRect(rect.x + rect.w / 2 - 50, my - 11, 100, 22, 4);
                        ctx.fill();
                        ctx.fillStyle = "#000";
                        ctx.font = "bold 10px Arial";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        ctx.fillText("左键落刀 / Shift吸附", rect.x + rect.w / 2, my);
                    } else if (this.activeMode === "add_v") {
                        const mx = Math.max(rect.x + 2, Math.min(rect.x + rect.w - 2, this.mousePos[0]));
                        ctx.strokeStyle = "#FFD700";
                        ctx.lineWidth = 2;
                        ctx.setLineDash([6, 4]);

                        ctx.beginPath();
                        ctx.moveTo(mx, rect.y);
                        ctx.lineTo(mx, rect.y + rect.h);
                        ctx.stroke();

                        ctx.fillStyle = "rgba(255, 215, 0, 0.95)";
                        ctx.beginPath();
                        ctx.roundRect(mx - 50, rect.y + rect.h / 2 - 11, 100, 22, 4);
                        ctx.fill();
                        ctx.fillStyle = "#000";
                        ctx.font = "bold 10px Arial";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        ctx.fillText("左键落刀 / Shift吸附", mx, rect.y + rect.h / 2);
                    }
                    ctx.restore();
                }

                // =============================================================
                // 层级 5 (工具栏按钮层 - 确保位于画板顶层)
                // =============================================================
                ctx.save();
                const buttons = [
                    { id: "add_h", icon: "──", label: "横线", active: this.activeMode === "add_h" },
                    { id: "add_v", icon: "│", label: "竖线", active: this.activeMode === "add_v" },
                    { id: "clear", icon: "🗑️", label: "清空", active: false }
                ];
                const btnW = totalW / buttons.length;

                for (let i = 0; i < buttons.length; i++) {
                    const b = buttons[i];
                    const bx = 12 + i * btnW;
                    const by = rect.toolbarY;
                    const bw = btnW - 4;
                    const bh = rect.toolbarH;

                    ctx.fillStyle = b.active ? "#009688" : "#2A2A2A";
                    ctx.strokeStyle = b.active ? "#80CBC4" : "#444";
                    ctx.lineWidth = 1;

                    ctx.beginPath();
                    ctx.roundRect(bx, by, bw, bh, 4);
                    ctx.fill();
                    ctx.stroke();

                    ctx.fillStyle = b.active ? "#FFF" : "#DDD";
                    ctx.font = "bold 12px Arial";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(`${b.icon} ${b.label}`, bx + bw / 2, by + bh / 2);
                }
                ctx.restore();

                // =============================================================
                // 层级 6 (底部独立状态栏 - 提供高精度操作指示)
                // =============================================================
                ctx.save();
                const barY = this.size[1] - 28;
                const barH = 22;
                ctx.fillStyle = "rgba(22, 22, 22, 0.95)";
                ctx.strokeStyle = "#383838";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.roundRect(12, barY, this.size[0] - 24, barH, 4);
                ctx.fill();
                ctx.stroke();

                ctx.fillStyle = "#4DD0E1";
                ctx.font = "bold 11px Arial";
                ctx.textAlign = "left";
                ctx.textBaseline = "middle";
                ctx.fillText(`📊 分割: ${totalBlocks} 块 (${totalRows}行 x ${totalCols}列)`, 20, barY + barH / 2);

                let rightTip = "提示: 点击标签输入分值 / 方向键微调 / DEL删除";
                let rightColor = "#888";
                if (this.activeMode === "moving_line") {
                    rightTip = "[移动中] 单击锁定 / 按住Shift对齐刻度";
                    rightColor = "#FFD700";
                } else if (this.selectedLine) {
                    rightTip = "[已选中] 方向键微调(0.1%) / 回车或点标签改值 / DEL删除";
                    rightColor = "#00E5FF";
                } else if (this.activeMode === "add_h" || this.activeMode === "add_v") {
                    rightTip = "[点击落刀] 移动鼠标落刀 / 按住Shift吸附";
                    rightColor = "#69F0AE";
                }

                if (this.size[0] >= 440) {
                    ctx.fillStyle = rightColor;
                    ctx.textAlign = "right";
                    ctx.fillText(rightTip, this.size[0] - 20, barY + barH / 2);
                }
                ctx.restore();
            };
        }
    }
});
