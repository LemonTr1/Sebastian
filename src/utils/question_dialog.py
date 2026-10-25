#!/usr/bin/env python3
"""提问弹窗 - 独立进程版
用法: python question_dialog.py /path/to/request.json

该进程由 question_client.py 通过 subprocess.Popen 启动，
拥有独立的 Python 解释器和 Tcl/Tk 事件循环，天然线程安全。

与审批弹窗（approval_dialog.py）的区别：这是"提问"而非"审批"，
用户可点选 Agent 给出的选项，也可自由输入文本，结果为文本答案而非布尔值。
"""
import json
import sys
import tkinter as tk
from tkinter import ttk

try:
    from .dialog_common import apply_base_style, center_window, get_theme, write_result_atomic
except ImportError:  # 以脚本方式被 subprocess 直接执行时没有包上下文
    from dialog_common import apply_base_style, center_window, get_theme, write_result_atomic

# 自由输入（"其他"）在 selection 中的哨兵值
OTHER = "__other__"


def main():
    req_file = sys.argv[1]
    with open(req_file, "r", encoding="utf-8") as f:
        req = json.load(f)

    result_file = req["result_file"]
    question_text = req.get("question", "")
    options = list(req.get("options") or [])
    timeout = req.get("timeout")
    theme_name = req.get("theme", "dark")
    t = get_theme(theme_name)

    has_options = len(options) > 0
    left_padding = 20
    min_width = 620

    root = tk.Tk()
    root.withdraw()

    dialog = tk.Toplevel(root)
    dialog.title("Agent Question")
    dialog.resizable(False, False)
    dialog.configure(bg=t["bg"])
    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()

    # ========== 结果 ==========
    result = {"status": "cancelled", "answer": None, "selected_option": None, "is_free_text": False}
    _done = {"saved": False}

    def save_and_exit():
        """原子写结果文件后关闭窗口（tmp + os.replace，避免读到半截 JSON）"""
        if _done["saved"]:
            return
        _done["saved"] = True
        try:
            write_result_atomic(result_file, result)
        except OSError:
            # 本进程 stderr 被父进程丢弃；读取结果缺失时 question_client 会打印兜底告警
            print(f"[question_dialog] 写入结果文件失败：{result_file}", file=sys.stderr)
        root.destroy()

    # ========== 样式 ==========
    style = ttk.Style()
    apply_base_style(style, t)

    # ========== Header ==========
    header = ttk.Frame(dialog, padding=(left_padding, 12, left_padding, 5))
    header.pack(fill=tk.X)
    tk.Label(header, text="?", font=("monospace", 22, "bold"),
             fg=t["accent"], bg=t["bg"], width=2).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Label(header, text="Agent 需要你的回答", style="Header.TLabel").pack(side=tk.LEFT, anchor=tk.W)

    ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=left_padding, pady=2)

    # ========== 内容 ==========
    content = ttk.Frame(dialog, padding=(left_padding, 8, left_padding, 6))
    content.pack(fill=tk.BOTH, expand=True)

    tk.Label(content, text=question_text, font=("Noto Sans CJK SC", 12, "bold"),
             fg=t["fg"], bg=t["bg"], wraplength=min_width - 2 * left_padding - 20,
             justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

    selection = tk.StringVar()
    answer_var = tk.StringVar()
    hint_var = tk.StringVar(value="")

    # ---------- 选项区 ----------
    if has_options:
        opt_card = tk.Frame(content, bg=t["card"], bd=1, relief=tk.SOLID,
                            highlightbackground=t["border"], highlightthickness=1)
        opt_card.pack(fill=tk.X, pady=(0, 8))

        max_visible = 8
        if len(options) + 1 > max_visible:
            # 选项过多时套滚动容器，高度锁定 8 行
            canvas = tk.Canvas(opt_card, bg=t["card"], highlightthickness=0,
                               height=max_visible * 28 + 12)
            scrollbar = tk.Scrollbar(opt_card, orient=tk.VERTICAL, command=canvas.yview)
            inner = tk.Frame(canvas, bg=t["card"])
            inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            def _on_inner_config(_event):
                canvas.configure(scrollregion=canvas.bbox("all"))

            def _on_canvas_config(event):
                canvas.itemconfigure(inner_id, width=event.width)

            inner.bind("<Configure>", _on_inner_config)
            canvas.bind("<Configure>", _on_canvas_config)

            # 平台无关滚轮
            if sys.platform == "linux":
                for widget in (canvas, inner):
                    widget.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
                    widget.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))
            else:
                def _on_mousewheel(event):
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

                for widget in (canvas, inner):
                    widget.bind("<MouseWheel>", _on_mousewheel)
            opt_parent = inner
        else:
            opt_parent = tk.Frame(opt_card, bg=t["card"])
            opt_parent.pack(fill=tk.X)

        for index, option in enumerate(options):
            tk.Radiobutton(
                opt_parent, text=option, variable=selection, value=f"__opt_{index}",
                bg=t["card"], fg=t["fg"], selectcolor=t["card"],
                activebackground=t["card"], activeforeground=t["fg"],
                font=("Noto Sans CJK SC", 11), anchor=tk.W, justify=tk.LEFT,
                wraplength=min_width - 90, cursor="hand2",
                highlightthickness=0, bd=0,
            ).pack(fill=tk.X, padx=10, pady=2)

        tk.Radiobutton(
            opt_parent, text="其他 / 自定义回答", variable=selection, value=OTHER,
            bg=t["card"], fg=t["fg"], selectcolor=t["card"],
            activebackground=t["card"], activeforeground=t["fg"],
            font=("Noto Sans CJK SC", 11), anchor=tk.W, justify=tk.LEFT,
            wraplength=min_width - 90, cursor="hand2",
            highlightthickness=0, bd=0,
        ).pack(fill=tk.X, padx=10, pady=2)

        selection.set("__opt_0")
    else:
        selection.set(OTHER)

    # ---------- 自由输入框 ----------
    entry_card = tk.Frame(content, bg=t["card"], bd=1, relief=tk.SOLID,
                          highlightbackground=t["border"], highlightthickness=1)
    entry_card.pack(fill=tk.X)
    entry = tk.Entry(entry_card, textvariable=answer_var, bg=t["card"], fg=t["fg"],
                     insertbackground=t["fg"], font=("Noto Sans CJK SC", 11),
                     bd=0, relief=tk.FLAT, highlightthickness=0)
    entry.pack(fill=tk.X, padx=10, pady=9)

    def _current_option_text():
        """当前选中的选项原文；处于自由输入态则返回 None"""
        sel = selection.get()
        if sel == OTHER:
            return None
        try:
            return options[int(sel.rsplit("_", 1)[-1])]
        except (ValueError, IndexError):
            return None

    def _sync_hint(*_args):
        # 输入框始终保持 NORMAL（disabled 会吞掉鼠标事件，导致无法切换到自由输入），
        # 因此用提示文案表达当前取值来源
        if selection.get() == OTHER:
            hint_var.set("直接输入你的回答，按 Enter 提交")
        else:
            hint_var.set("或直接在输入框中输入自定义回答")

    selection.trace_add("write", _sync_hint)

    def _use_free_text(_event=None):
        """用户开始敲键盘/点击输入框时，自动切到自由输入态"""
        if selection.get() != OTHER:
            selection.set(OTHER)

    entry.bind("<Button-1>", _use_free_text)
    entry.bind("<Key>", _use_free_text)
    entry.bind("<<Paste>>", _use_free_text)

    _sync_hint()

    hint_label = ttk.Label(content, textvariable=hint_var, style="Dim.TLabel")
    hint_label.pack(anchor=tk.W, pady=(6, 0))

    # ========== 交互 ==========
    def submit():
        hint_var.set("")
        sel = selection.get()
        if has_options and sel != OTHER:
            text = _current_option_text()
            result.update(status="answered", answer=text, selected_option=text, is_free_text=False)
            save_and_exit()
            return
        text = answer_var.get().strip()
        if not text:
            # 空回答不算作答：拒绝提交并保留窗口，而不是静默当作取消
            hint_var.set("请先选择选项或输入回答")
            return
        result.update(status="answered", answer=text, selected_option=None, is_free_text=True)
        save_and_exit()

    def cancel():
        result.update(status="cancelled", answer=None, selected_option=None, is_free_text=False)
        save_and_exit()

    # 只绑 Toplevel 一级：Entry 上的 Return 会冒泡到这里，绑两级会重复触发 submit
    dialog.bind("<Return>", lambda e: submit())
    dialog.bind("<KP_Enter>", lambda e: submit())
    dialog.bind("<Escape>", lambda e: cancel())
    dialog.protocol("WM_DELETE_WINDOW", cancel)

    # ========== 按钮栏 ==========
    btn_frame = ttk.Frame(dialog, padding=(left_padding, 8, left_padding, 14))
    btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

    countdown_var = tk.StringVar(value="")
    ttk.Label(btn_frame, textvariable=countdown_var, style="Dim.TLabel").pack(side=tk.LEFT)

    btn_container = ttk.Frame(btn_frame)
    btn_container.pack(side=tk.RIGHT)

    tk.Button(btn_container, text="取消 (Esc)", command=cancel,
              bg=t["danger"], fg="white", font=("Noto Sans CJK SC", 11),
              activebackground="#c62828", activeforeground="white",
              relief=tk.FLAT, padx=14, pady=4, cursor="hand2",
              borderwidth=0, highlightthickness=0).pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(btn_container, text="提交 (Enter)", command=submit,
              bg=t["accent"], fg="white", font=("Noto Sans CJK SC", 11, "bold"),
              activebackground="#2e7d32", activeforeground="white",
              relief=tk.FLAT, padx=14, pady=4, cursor="hand2",
              borderwidth=0, highlightthickness=0).pack(side=tk.LEFT)

    # ========== 尺寸与居中（pack 完成后测量，选项数可变时比手算公式可靠） ==========
    dialog.update_idletasks()
    width = max(min_width, dialog.winfo_reqwidth())
    height = min(max(dialog.winfo_reqheight(), 200), int(dialog.winfo_screenheight() * 0.8))
    center_window(dialog, width, height)

    if not has_options:
        entry.focus_set()

    # ========== 超时倒计时 ==========
    if timeout and timeout > 0:
        remaining = int(timeout)

        def tick():
            nonlocal remaining
            if not root.winfo_exists():
                return
            if remaining <= 0:
                result.update(status="timeout", answer=None, selected_option=None, is_free_text=False)
                save_and_exit()
                return
            countdown_var.set(f"自动关闭倒计时 {remaining}s")
            remaining -= 1
            dialog.after(1000, tick)

        tick()

    root.mainloop()


if __name__ == "__main__":
    main()