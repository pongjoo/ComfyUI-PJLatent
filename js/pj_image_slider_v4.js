import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

function imageDataToUrl(data) {
    if (!data) return "";
    return api.apiURL(`/view?filename=${encodeURIComponent(data.filename)}&type=${data.type}&subfolder=${encodeURIComponent(data.subfolder)}${app.getPreviewFormatParam()}${app.getRandParam()}`);
}

app.registerExtension({
    name: "PJ.ImageSlider",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Image_Handler") {

            nodeType.prototype.onNodeCreated = function () {
                this.pj_imgs = [null, null];
                this.pj_ratio = 0.5;
                this.is_hovering_image = false;
                this.size = [400, 520];
            };

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                // Pass the original unmodified message to the base onExecuted handler.
                // This ensures ComfyUI's history and assets managers receive the 'images' key
                // and display the previews correctly in both preview and save modes.
                onExecuted?.apply(this, arguments);

                const load = (meta, idx) => {
                    if (meta && meta.length > 0) {
                        const img = new Image();
                        img.onload = () => {
                            this.pj_imgs[idx] = img;
                            this.setDirtyCanvas(true);
                        };
                        img.src = imageDataToUrl(meta[0]);
                    } else {
                        this.pj_imgs[idx] = null;
                        this.setDirtyCanvas(true);
                    }
                };

                load(message.a_images, 0);
                load(message.b_images, 1);

                this.imgs = null;
                this.setDirtyCanvas(true);
            };

            nodeType.prototype.onMouseEnter = function () {
                // Nothing special here
            };

            nodeType.prototype.onMouseLeave = function () {
                this.is_hovering_image = false;
                this.setDirtyCanvas(true);
            };

            nodeType.prototype.onMouseMove = function (e, pos) {
                const margin = 10;
                const widgetHeight = (this.widgets ? this.widgets.length * 28 : 0) + 45;
                const w = this.size[0] - margin * 2;
                const h = this.size[1] - widgetHeight - margin - 20;

                const isOverImage = pos[0] >= margin && pos[0] <= margin + w && pos[1] >= widgetHeight && pos[1] <= widgetHeight + h;

                if (isOverImage) {
                    if (!this.is_hovering_image) {
                        this.is_hovering_image = true;
                    }
                    if (this.pj_imgs[1]) {
                        this.pj_ratio = (pos[0] - margin) / w;
                    }
                } else {
                    this.is_hovering_image = false;
                }
                this.setDirtyCanvas(true);
            };

            nodeType.prototype.onDrawForeground = function (ctx) {
                // Constantly filter out any standard preview widgets added by ComfyUI (V1 or V2 frontend)
                // We do this during drawing so that the widget is immediately unmounted from the DOM
                // and cannot block mouse events on the canvas, even if ComfyUI recreates it.
                if (this.widgets) {
                    const originalLength = this.widgets.length;
                    this.widgets = this.widgets.filter(w => w.name === "save_image" || w.name === "filename_prefix");
                    if (this.widgets.length !== originalLength) {
                        this.setDirtyCanvas(true);
                    }
                }

                if (this.flags.collapsed || !this.pj_imgs[0]) return;

                const margin = 10;
                const widgetHeight = (this.widgets ? this.widgets.length * 28 : 0) + 45;
                const textSpace = 20;

                const w = this.size[0] - margin * 2;
                const h = this.size[1] - widgetHeight - margin - textSpace;
                if (h < 30) return;

                const showComparison = this.is_hovering_image && this.pj_imgs[1];
                const ratio = showComparison ? this.pj_ratio : 1.0;

                const drawBalanced = (img, clipW) => {
                    if (!img || !img.complete || img.naturalWidth === 0) return;
                    const iR = img.naturalWidth / img.naturalHeight;
                    const aR = w / h;
                    let dw, dh, dx, dy;
                    if (iR > aR) { dw = w; dh = w / iR; } else { dh = h; dw = h * iR; }
                    dx = margin + (w - dw) / 2;
                    dy = widgetHeight + (h - dh) / 2;

                    ctx.save();
                    if (clipW !== undefined) {
                        ctx.beginPath();
                        ctx.rect(margin, widgetHeight, clipW, h);
                        ctx.clip();
                    }
                    ctx.drawImage(img, dx, dy, dw, dh);
                    ctx.restore();
                };

                ctx.save();
                if (showComparison) {
                    drawBalanced(this.pj_imgs[1]);
                    drawBalanced(this.pj_imgs[0], w * ratio);

                    const lx = margin + w * ratio;
                    ctx.strokeStyle = "rgba(255,255,255,0.8)";
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(lx, widgetHeight);
                    ctx.lineTo(lx, widgetHeight + h);
                    ctx.stroke();
                } else {
                    drawBalanced(this.pj_imgs[0]);

                    if (this.pj_imgs[0] && this.pj_imgs[0].naturalWidth > 0) {
                        const sizeText = `${this.pj_imgs[0].naturalWidth} x ${this.pj_imgs[0].naturalHeight}`;
                        ctx.fillStyle = "#AAA";
                        ctx.font = "14px Arial";
                        ctx.textAlign = "center";
                        ctx.fillText(sizeText, this.size[0] / 2, this.size[1] - 8);
                    }
                }
                ctx.restore();
            };
        }
    }
});
