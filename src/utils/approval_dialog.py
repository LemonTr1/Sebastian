#!/usr/bin/env python3
"""审批弹窗 - 独立进程版
用法: python approval_dialog.py /path/to/request.json

该进程由 approval_client.py 通过 subprocess.Popen 启动，
拥有独立的 Python 解释器和 Tcl/Tk 事件循环，天然线程安全。
"""
import json
import re
import sys
import tkinter as tk
from tkinter import ttk

_VALUE_PATTERN = re.compile(r'("(?:[^"\\]|\\.)*")|(\b(?:true|false|null)\b)|(\b\d+\.?\d*\b)')


def _insert_highlighted(text_widget, value_str):
    """Insert a plain string value token by token with syntax tags."""
    pos = 0
    for m in _VALUE_PATTERN.finditer(value_str):
        if m.start() > pos:
            text_widget.insert(tk.END, value_str[pos:m.start()], "plain")
        if m.group(1):
            text_widget.insert(tk.END, m.group(1), "string")
        elif m.group(2):
            text_widget.insert(tk.END, m.group(2), "bool")
        elif m.group(3):
            text_widget.insert(tk.END, m.group(3), "number")
        pos = m.end()
    if pos < len(value_str):
        text_widget.insert(tk.END, value_str[pos:], "plain")


def main():
    req_file = sys.argv[1]
    with open(req_file, "r", encoding="utf-8") as f:
        req = json.load(f)

    result_file = req["result_file"]
    tool_name = req.get("tool_name", "unknown")
    tool_args = req.get("tool_args", {})
    timeout = req.get("timeout")
    theme_name = req.get("theme", "dark")

    themes = {
        "light": {
            "bg": "#f5f5f5", "fg": "#1a1a1a",
            "accent": "#4CAF50", "danger": "#f44336",
            "card": "#ffffff", "border": "#dddddd",
        },
        "dark": {
            "bg": "#1e1e1e", "fg": "#d4d4d4",
            "accent": "#4ec9b0", "danger": "#f44747",
            "card": "#252526", "border": "#3e3e42",
        },
        "blue": {
            "bg": "#0a1929", "fg": "#e0e0e0",
            "accent": "#3182ce", "danger": "#e53e3e",
            "card": "#132f4c", "border": "#1e4976",
        },
    }
    t = themes.get(theme_name, themes["dark"])

    root = tk.Tk()
    root.withdraw()

    dialog = tk.Toplevel(root)
    dialog.title("Security Confirmation")
    dialog.resizable(False, False)
    dialog.configure(bg=t["bg"])

    dialog.attributes("-topmost", True)
    dialog.lift()
    dialog.focus_force()

    # ========== 布局参数 ==========
    left_padding = 20
    min_width = 680
    args_text_min_lines = 5
    args_text_max_lines = 18
    args_header_height = 30
    question_height = 50
    button_bar_height = 55
    header_height = 55
    separator_height = 6
    pad_height = 40
    line_height = 20

    has_args = len(tool_args) > 0
    if has_args:
        total_arg_lines = 0
        for k, v in tool_args.items():
            val_str = json.dumps(v, indent=2, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            total_arg_lines += len(val_str.split("\n"))
        display_lines = max(args_text_min_lines, min(total_arg_lines, args_text_max_lines))
    else:
        display_lines = args_text_min_lines

    args_card_height = display_lines * line_height + 20

    total_height = (
        header_height + separator_height + question_height +
        args_header_height + args_card_height + pad_height +
        button_bar_height
    )
    total_height = max(total_height, 240)
    total_height = min(total_height, 750)

    dialog.geometry(f"{min_width}x{total_height}")

    dialog.update_idletasks()
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f"{min_width}x{total_height}+{(sw - min_width) // 2}+{(sh - total_height) // 2}")

    # ========== 样式 ==========
    style = ttk.Style()
    style.configure("TFrame", background=t["bg"])
    style.configure("TLabel", background=t["bg"], foreground=t["fg"], font=("Noto Sans CJK SC", 11))
    style.configure("Header.TLabel", font=("Noto Sans CJK SC", 14, "bold"), foreground=t["fg"], background=t["bg"])
    style.configure("Args.TLabel", font=("monospace", 10), foreground=t["fg"], background=t["card"])
    style.configure("Dim.TLabel", font=("Noto Sans CJK SC", 9), foreground="#888888", background=t["bg"])

    # ========== 结果 ==========
    result = {"approved": False, "timed_out": False}

    def save_and_exit():
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f)
        root.destroy()

    def on_yes():
        result["approved"] = True
        save_and_exit()

    def on_no():
        save_and_exit()

    dialog.bind("<Return>", lambda e: on_yes())
    dialog.bind("<Escape>", lambda e: on_no())
    dialog.bind("<y>", lambda e: on_yes())
    dialog.bind("<Y>", lambda e: on_yes())
    dialog.bind("<n>", lambda e: on_no())
    dialog.bind("<N>", lambda e: on_no())
    dialog.protocol("WM_DELETE_WINDOW", on_no)

    # ========== UI ==========
    # Header
    header = ttk.Frame(dialog, padding=(left_padding, 12, left_padding, 5))
    header.pack(fill=tk.X)
    icon = tk.Label(header, text="!", font=("monospace", 24, "bold"),
                    fg=t["danger"], bg=t["bg"], width=2)
    icon.pack(side=tk.LEFT, padx=(0, 10))
    ttk.Label(header, text="Agent Rrequested Approval", style="Header.TLabel").pack(side=tk.LEFT, anchor=tk.W)

    ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=left_padding, pady=2)

    # Question
    content = ttk.Frame(dialog, padding=(left_padding, 6, left_padding, 6))
    content.pack(fill=tk.BOTH, expand=True)
    ttk.Label(content, text=f"Do you want to allow '{tool_name}' to run?",
              font=("Noto Sans CJK SC", 12, "bold"),
              foreground=t["fg"], background=t["bg"]).pack(anchor=tk.W, pady=(0, 8))

    # Arguments card with scrollbar and syntax highlighting
    if has_args:
        card = tk.Frame(content, bg=t["card"], bd=1, relief=tk.SOLID,
                        highlightbackground=t["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        header_bar = tk.Frame(card, bg=t["card"])
        header_bar.pack(fill=tk.X, padx=10, pady=(6, 2))
        tk.Label(header_bar, text=f"Parameters ({len(tool_args)} items)", font=("Noto Sans CJK SC", 9),
                fg="#888888", bg=t["card"]).pack(side=tk.LEFT)

        text_container = tk.Frame(card, bg=t["card"])
        text_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

        args_text = tk.Text(text_container, bg=t["card"], fg=t["fg"],
                           font=("monospace", 10), bd=0, wrap=tk.WORD,
                           height=display_lines, padx=10, pady=6,
                           state=tk.NORMAL, cursor="arrow")
        scrollbar = tk.Scrollbar(text_container, orient=tk.VERTICAL, command=args_text.yview)
        args_text.configure(yscrollcommand=scrollbar.set, cursor="arrow")

        args_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        args_text.tag_configure("key", foreground=t["accent"], font=("monospace", 10, "bold"))
        args_text.tag_configure("string", foreground="#6a9955", font=("monospace", 10))
        args_text.tag_configure("number", foreground="#ce9178", font=("monospace", 10))
        args_text.tag_configure("bool", foreground="#c586c0", font=("monospace", 10))
        args_text.tag_configure("plain", foreground=t["fg"], font=("monospace", 10))
        args_text.tag_configure("dim", foreground="#888888", font=("monospace", 10))

        first_entry = True
        for k, v in tool_args.items():
            if not first_entry:
                args_text.insert(tk.END, "\n")
            first_entry = False

            args_text.insert(tk.END, f"  {k}:", "key")

            if isinstance(v, (dict, list)):
                val_str = json.dumps(v, indent=2, ensure_ascii=False)
                val_lines = val_str.split("\n")
                for i, line in enumerate(val_lines):
                    if i == 0:
                        args_text.insert(tk.END, " " + line.lstrip(), "plain")
                    else:
                        args_text.insert(tk.END, "\n" + line, "plain")
            else:
                val_str = str(v)
                args_text.insert(tk.END, " ", "plain")
                _insert_highlighted(args_text, val_str)

        args_text.configure(state=tk.DISABLED)

        def _on_mousewheel(event):
            args_text.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Platform-independent scroll
        if sys.platform == "linux":
            args_text.bind("<Button-4>", lambda e: args_text.yview_scroll(-3, "units"))
            args_text.bind("<Button-5>", lambda e: args_text.yview_scroll(3, "units"))
            scrollbar.bind("<Button-4>", lambda e: args_text.yview_scroll(-3, "units"))
            scrollbar.bind("<Button-5>", lambda e: args_text.yview_scroll(3, "units"))
        else:
            args_text.bind("<MouseWheel>", _on_mousewheel)
            scrollbar.bind("<MouseWheel>", _on_mousewheel)
    else:
        card = tk.Frame(content, bg=t["card"], bd=1, relief=tk.SOLID,
                        highlightbackground=t["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text="Parameters (0 items)", font=("Noto Sans CJK SC", 9),
                fg="#888888", bg=t["card"]).pack(anchor=tk.W, padx=10, pady=(6, 2))
        args_text = tk.Text(card, bg=t["card"], fg="#888888",
                           font=("monospace", 10, "italic"), bd=0, wrap=tk.WORD,
                           height=1, padx=10, pady=6, cursor="arrow")
        args_text.insert("1.0", "  (no parameters)")
        args_text.configure(state=tk.DISABLED)
        args_text.pack(fill=tk.BOTH, expand=True)

    # Buttons
    btn_frame = ttk.Frame(dialog, padding=(left_padding, 8, left_padding, 14))
    btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

    countdown_var = tk.StringVar(value="")
    countdown_label = ttk.Label(btn_frame, textvariable=countdown_var, style="Dim.TLabel")
    countdown_label.pack(side=tk.LEFT)

    btn_container = ttk.Frame(btn_frame)
    btn_container.pack(side=tk.RIGHT)

    tk.Button(btn_container, text="Deny (N/Esc)", command=on_no,
              bg=t["danger"], fg="white", font=("Noto Sans CJK SC", 11),
              activebackground="#c62828", activeforeground="white",
              relief=tk.FLAT, padx=14, pady=4, cursor="hand2",
              borderwidth=0, highlightthickness=0).pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(btn_container, text="Allow (Y/Enter)", command=on_yes,
              bg=t["accent"], fg="white", font=("Noto Sans CJK SC", 11, "bold"),
              activebackground="#388e3c" if theme_name == "light" else "#2e7d32",
              activeforeground="white", relief=tk.FLAT, padx=14, pady=4,
              cursor="hand2", borderwidth=0, highlightthickness=0).pack(side=tk.LEFT)

    # ========== 超时倒计时 ==========
    if timeout and timeout > 0:
        remaining = timeout

        def tick():
            nonlocal remaining
            if not root.winfo_exists():
                return
            if remaining <= 0:
                result["timed_out"] = True
                save_and_exit()
                return
            countdown_var.set(f"Auto-deny in {remaining}s")
            remaining -= 1
            dialog.after(1000, tick)

        tick()

    root.mainloop()


if __name__ == "__main__":
    main()
