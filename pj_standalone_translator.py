import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# 将当前目录添加到 sys.path 以便导入 pj_nodes 中的核心翻译逻辑
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from pj_nodes import PJ_Text_Translator
except ImportError as e:
    messagebox.showerror("错误", f"无法加载 PJ 翻译核心模块: {e}")
    sys.exit(1)

class PJStandaloneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PJ 本地离线智能双向翻译器 v1.0")
        self.root.geometry("680x620")
        self.root.minsize(550, 500)
        
        # 初始化翻译器实例
        self.translator = PJ_Text_Translator()
        
        # 设置风格主题
        style = ttk.Style()
        style.theme_use('clam')
        
        self.create_widgets()
        
    def create_widgets(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部控制面板
        control_frame = ttk.LabelFrame(main_frame, text=" ⚙️ 翻译设置 ", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 模式选择
        ttk.Label(control_frame, text="翻译模式:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.mode_var = tk.StringVar(value="Auto (智能双向检测)")
        mode_cb = ttk.Combobox(control_frame, textvariable=self.mode_var, values=[
            "Auto (智能双向检测)", "ZH -> EN (中译英)", "EN -> ZH (英译中)"
        ], state="readonly", width=22)
        mode_cb.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 设备选择
        ttk.Label(control_frame, text="运行设备:").grid(row=0, column=2, sticky=tk.W, padx=(15, 5), pady=5)
        self.device_var = tk.StringVar(value="auto")
        device_cb = ttk.Combobox(control_frame, textvariable=self.device_var, values=["auto", "cuda", "cpu"], state="readonly", width=8)
        device_cb.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # 选项复选框
        self.clean_punct_var = tk.BooleanVar(value=True)
        clean_cb = ttk.Checkbutton(control_frame, text="规范化英文标点", variable=self.clean_punct_var)
        clean_cb.grid(row=0, column=4, sticky=tk.W, padx=(15, 5), pady=5)
        
        # 前缀后缀框
        prefix_suffix_frame = ttk.Frame(control_frame)
        prefix_suffix_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W+tk.E, pady=(5, 0))
        
        ttk.Label(prefix_suffix_frame, text="前缀词:").pack(side=tk.LEFT, padx=(5, 2))
        self.prefix_var = tk.StringVar(value="")
        prefix_entry = ttk.Entry(prefix_suffix_frame, textvariable=self.prefix_var, width=22)
        prefix_entry.pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(prefix_suffix_frame, text="后缀词:").pack(side=tk.LEFT, padx=(5, 2))
        self.suffix_var = tk.StringVar(value="")
        suffix_entry = ttk.Entry(prefix_suffix_frame, textvariable=self.suffix_var, width=22)
        suffix_entry.pack(side=tk.LEFT)
        
        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text=" 📥 输入文本 (中文或英文) ", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.input_text = tk.Text(input_frame, wrap=tk.WORD, font=("Consolas", 10), undo=True)
        input_scroll = ttk.Scrollbar(input_frame, command=self.input_text.yview)
        self.input_text.configure(yscrollcommand=input_scroll.set)
        
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        input_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮栏
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.trans_btn = ttk.Button(btn_frame, text="⚡ 开始离线翻译 (Ctrl+Enter)", command=self.start_translation_thread)
        self.trans_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        clear_btn = ttk.Button(btn_frame, text="清空输入", command=self.clear_input)
        clear_btn.pack(side=tk.RIGHT, width=100)
        
        # 绑定快捷键 Ctrl+Enter 或 Alt+Enter
        self.root.bind("<Control-Return>", lambda e: self.start_translation_thread())
        self.root.bind("<Alt-Return>", lambda e: self.start_translation_thread())
        
        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text=" 📤 翻译结果 ", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = tk.Text(output_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.NORMAL)
        output_scroll = ttk.Scrollbar(output_frame, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=output_scroll.set)
        
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部状态栏和复制按钮
        status_frame = ttk.Frame(main_frame, padding=(0, 5, 0, 0))
        status_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="就绪 - 100% 纯本地离线运行", font=("Microsoft YaHei", 9))
        self.status_label.pack(side=tk.LEFT)
        
        copy_btn = ttk.Button(status_frame, text="📋 复制结果", command=self.copy_output)
        copy_btn.pack(side=tk.RIGHT)

    def clear_input(self):
        self.input_text.delete("1.0", tk.END)

    def copy_output(self):
        result = self.output_text.get("1.0", tk.END).strip()
        if result:
            self.root.clipboard_clear()
            self.root.clipboard_append(result)
            self.status_label.config(text="已成功复制结果到剪贴板！")
        else:
            self.status_label.config(text="结果为空，无法复制")

    def start_translation_thread(self):
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            self.status_label.config(text="提示: 请先输入需要翻译的文本")
            return
            
        self.trans_btn.config(state=tk.DISABLED)
        self.status_label.config(text="⌛ 正在离线翻译中，请稍候...")
        
        # 在子线程中运行翻译，防止界面卡顿
        threading.Thread(target=self.run_translation, args=(text,), daemon=True).start()

    def run_translation(self, text):
        try:
            mode = self.mode_var.get()
            device = self.device_var.get()
            clean_punct = self.clean_punct_var.get()
            prefix = self.prefix_var.get()
            suffix = self.suffix_var.get()
            
            # 调用节点逻辑
            final_res, _ = self.translator.translate(
                text=text,
                mode=mode,
                device=device,
                clean_punctuation=clean_punct,
                keep_in_memory=True,
                prefix=prefix,
                suffix=suffix
            )
            
            # 主线程更新 UI
            self.root.after(0, self.update_output, final_res, "翻译完成！")
        except Exception as e:
            self.root.after(0, self.update_output, f"翻译发生错误: {e}", "翻译失败")

    def update_output(self, result_text, status_msg):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, result_text)
        self.status_label.config(text=status_msg)
        self.trans_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = PJStandaloneApp(root)
    root.mainloop()
