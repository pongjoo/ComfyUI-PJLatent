import { app } from "/scripts/app.js";

app.registerExtension({
    name: "PJ.ImageSliceReassembler",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Image_Slice_Reassembler") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // 设置舒适的默认节点尺寸
                if (!this.size || this.size[0] < 340 || this.size[1] < 420) {
                    this.size = [360, 460];
                }

                // 节点外观微调
                this.color = "#1e293b";
                this.bgcolor = "#0f172a";

                return r;
            };

            // 绘制节点底部提示小徽章
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function (ctx) {
                onDrawForeground?.apply(this, arguments);

                if (this.flags?.collapsed) return;

                ctx.save();
                ctx.font = "11px sans-serif";
                ctx.fillStyle = "rgba(148, 163, 184, 0.6)";
                ctx.textAlign = "center";
                ctx.fillText("🧩 PJ 切片原位还原器 • 余弦平滑接缝融合", this.size[0] / 2, this.size[1] - 8);
                ctx.restore();
            };
        }
    }
});
