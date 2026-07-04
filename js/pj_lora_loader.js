import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
    name: "PJ.LoraLoader",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "PJ_Lora_Loader") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);

                const dirWidget = this.widgets.find(w => w.name === "lora_directory");
                const nameWidget = this.widgets.find(w => w.name === "lora_name");

                if (dirWidget && nameWidget) {
                    const updateLoras = async () => {
                        const folder = dirWidget.value;
                        if (!folder) {
                            nameWidget.options.values = [""];
                            nameWidget.value = "";
                            return;
                        }

                        try {
                            const response = await api.fetchApi(`/pj/list_loras?folder=${encodeURIComponent(folder)}`);
                            const data = await response.json();
                            if (data.files && data.files.length > 0) {
                                nameWidget.options.values = data.files;
                                // Keep the current value if it's still in the list, otherwise select the first one
                                if (!data.files.includes(nameWidget.value)) {
                                    nameWidget.value = data.files[0];
                                }
                            } else {
                                nameWidget.options.values = [""];
                                nameWidget.value = "";
                            }
                        } catch (e) {
                            console.error("[PJ Lora Loader] 获取LoRA列表失败:", e);
                            nameWidget.options.values = [""];
                            nameWidget.value = "";
                        }
                    };

                    // Listen to value changes
                    dirWidget.callback = function (value) {
                        updateLoras();
                    };

                    // Also run initially when node is created
                    setTimeout(updateLoras, 100);
                }
            };
            
            // To ensure it updates when workflow is loaded
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                onConfigure?.apply(this, arguments);
                const dirWidget = this.widgets.find(w => w.name === "lora_directory");
                const nameWidget = this.widgets.find(w => w.name === "lora_name");
                if (dirWidget && nameWidget) {
                    const currentVal = nameWidget.value;
                    const folder = dirWidget.value;
                    if (folder) {
                        api.fetchApi(`/pj/list_loras?folder=${encodeURIComponent(folder)}`)
                            .then(res => res.json())
                            .then(data => {
                                if (data.files && data.files.length > 0) {
                                    nameWidget.options.values = data.files;
                                    if (data.files.includes(currentVal)) {
                                        nameWidget.value = currentVal;
                                    }
                                }
                            }).catch(err => {});
                    }
                }
            };
        }
    }
});
