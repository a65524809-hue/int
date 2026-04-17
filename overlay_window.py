"""Floating overlay window: semi-transparent, always-on-top, draggable, resizable."""
import sys
import platform
import tkinter as tk
from tkinter import font as tkfont

# Defaults; overridden by config (clear_after_seconds no longer used; clear only via Alt+C or Clear button)
DEFAULT_ALPHA = 0.8

# Windows: exclude window from screen capture - Win10 2004+
# Must use an OPAQUE window (no -alpha); SetWindowDisplayAffinity does not work on layered windows.
WDA_EXCLUDEFROMCAPTURE = 0x00000011
# Hide from taskbar (tool windows don't get a taskbar button)
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


class OverlayWindow:
    def __init__(self, config: dict):
        self.config = config
        self.alpha = float(config.get("transparency", DEFAULT_ALPHA))
        # Extra transparency level when exam mode is toggled from the UI button.
        self.exam_alpha = float(config.get("exam_mode_transparency", 0.3))
        self.exclude_from_capture = config.get("exclude_from_capture", True)
        self.root = None
        self.text_widget = None
        self._drag_start = None
        self._resize_start = None
        self.exam_mode = False

    def _create_window(self):
        root = tk.Tk()
        root.title("InterviewWhisper")
        root.attributes("-topmost", True)
        # Use opaque window when excluding from capture: SetWindowDisplayAffinity does NOT work on layered (-alpha) windows.
        use_stealth = platform.system() == "Windows" and self.exclude_from_capture
        if use_stealth:
            root.attributes("-alpha", 1.0)
        else:
            root.attributes("-alpha", self.alpha)
        root.overrideredirect(True)
        root.configure(bg="#1a1a2e")
        root.geometry("420x320+100+100")
        root.minsize(200, 120)

        # Title bar (draggable) + Clear button
        title_bar = tk.Frame(root, bg="#16213e", height=28, cursor="fleur")
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        title_lbl = tk.Label(
            title_bar,
            text="InterviewWhisper",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 10, "bold"),
        )
        title_lbl.pack(side=tk.LEFT, padx=8, pady=4)
        
        # Bind drag to title label as well
        title_lbl.bind("<Button-1>", self._start_drag)
        title_lbl.bind("<B1-Motion>", self._on_drag)
        title_lbl.bind("<Double-Button-1>", lambda e: self._toggle_alpha())
        # Exam mode toggle: makes the window extra transparent so you can
        # see on-screen MCQ questions while still keeping the overlay handy.
        exam_btn = tk.Button(
            title_bar,
            text="Exam",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.toggle_exam_mode,
        )
        exam_btn.pack(side=tk.RIGHT, padx=4, pady=4)
        
        code_btn = tk.Button(
            title_bar,
            text="Code",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.toggle_exam_mode,
        )
        code_btn.pack(side=tk.RIGHT, padx=4, pady=4)
        
        amp_btn = tk.Button(
            title_bar,
            text="Amp",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.toggle_exam_mode,
        )
        amp_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        exit_btn = tk.Button(
            title_bar,
            text="Exit",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=2,
            cursor="hand2",
            command=self.quit,
        )
        exit_btn.pack(side=tk.RIGHT, padx=2, pady=4)
        clear_btn = tk.Button(
            title_bar,
            text="Clear",
            bg="#16213e",
            fg="#4a5a7a",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=2,
            cursor="hand2",
            command=self.clear,
        )
        clear_btn.pack(side=tk.RIGHT, padx=6, pady=4)
        title_bar.bind("<Button-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._on_drag)
        title_bar.bind("<Double-Button-1>", lambda e: self._toggle_alpha())

        # Content
        content = tk.Frame(root, bg="#1a1a2e", padx=8, pady=8)
        content.pack(fill=tk.BOTH, expand=True)
        text_font = tkfont.Font(family="Segoe UI", size=10)
        self.text_widget = tk.Text(
            content,
            wrap=tk.WORD,
            bg="#1a1a2e",
            fg="#5a5a75",
            insertbackground="#5a5a75",
            selectbackground="#5a5a75",
            font=text_font,
            relief=tk.FLAT,
            padx=4,
            pady=4,
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        self.text_widget.insert(
            tk.END,
            "Hold Alt+R to record a question. Release to get an answer.\n"
            "Exam/Code/Amp (buttons): window becomes extra transparent.\n"
            "Alt+S to scan screen MCQ. Alt+Q to scan code. Alt+W to scan amp.\n"
            "Hold Alt+A to show the answer for the last scan.\n"
            "Clear: Alt+C or click Clear.",
        )
        self.text_widget.config(state=tk.DISABLED)
        
        # Bind drag to text widget background as well to make it easier to grab when transparent
        self.text_widget.bind("<Button-1>", self._start_drag)
        self.text_widget.bind("<B1-Motion>", self._on_drag)

        # Resize handle (bottom-right)
        resize_handle = tk.Frame(root, bg="#16213e", width=12, height=12, cursor="sizing")
        resize_handle.place(relx=1, rely=1, anchor=tk.SE)
        resize_handle.bind("<Button-1>", self._start_resize)
        resize_handle.bind("<B1-Motion>", self._on_resize)

        self.root = root
        self._use_stealth = use_stealth
        # Windows: hide from taskbar always; when stealth, also exclude from screen capture (delay until window exists).
        if platform.system() == "Windows":
            root.after(800, self._apply_stealth_flags)
        return root

    def _toggle_alpha(self):
        """Double-click title bar to quickly toggle between normal and fully opaque."""
        if self.root is None:
            return
        a = float(self.root.attributes("-alpha"))
        # When exam mode is active, keep using the exam alpha level.
        if self.exam_mode:
            self.root.attributes("-alpha", self.exam_alpha)
            return
        self.root.attributes("-alpha", 1.0 if a < 1.0 else self.alpha)

    def toggle_exam_mode(self):
        """Toggle exam mode transparency. This is purely visual; hotkeys are handled in main."""
        if self.root is None:
            return
        self.exam_mode = not self.exam_mode
        target_alpha = self.exam_alpha if self.exam_mode else self.alpha
        try:
            self.root.attributes("-alpha", float(target_alpha))
        except Exception:
            # Fallback: if setting alpha fails (e.g. on some platforms), ignore.
            pass
        # Make sure toggling exam mode never causes the window to reappear
        # in the taskbar on Windows.
        if platform.system() == "Windows":
            try:
                self.root.after(10, self._apply_stealth_flags)
            except Exception:
                pass

    def _get_hwnd(self):
        """Get Windows HWND; try frame() then winfo_id()."""
        try:
            f = self.root.frame()
            if f is not None:
                return int(f, 16)
        except Exception:
            pass
        wid = self.root.winfo_id()
        return int(wid) if isinstance(wid, str) else wid

    def _apply_stealth_flags(self):
        """Windows: hide from taskbar (WS_EX_TOOLWINDOW); when stealth, also exclude from screen capture (WDA_EXCLUDEFROMCAPTURE)."""
        if self.root is None:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
            user32.GetWindowLongW.restype = wintypes.LONG
            user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
            user32.SetWindowLongW.restype = wintypes.LONG
            if self._use_stealth:
                user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
                user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
            candidates = [self._get_hwnd()]
            wid = self.root.winfo_id()
            if isinstance(wid, str):
                try:
                    candidates.append(int(wid, 16) if (wid.startswith("0x") or wid.startswith("0X")) else int(wid))
                except ValueError:
                    pass
            else:
                candidates.append(wid)
            seen = set()
            for hwnd in candidates:
                h = int(hwnd) if isinstance(hwnd, str) else hwnd
                if h in seen:
                    continue
                seen.add(h)
                hwnd_val = ctypes.c_void_p(h)
                # Hide from taskbar: add WS_EX_TOOLWINDOW so window has no taskbar button
                try:
                    ex = user32.GetWindowLongW(hwnd_val, GWL_EXSTYLE)
                    if ex != 0:
                        user32.SetWindowLongW(hwnd_val, GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW)
                except Exception:
                    pass
                # Exclude from screen capture (only when stealth enabled)
                if self._use_stealth:
                    try:
                        if user32.SetWindowDisplayAffinity(hwnd_val, WDA_EXCLUDEFROMCAPTURE):
                            return
                    except Exception:
                        continue
            if self._use_stealth:
                err = ctypes.get_last_error()
                if err:
                    print(f"[Overlay] SetWindowDisplayAffinity failed (err={err}). Window is opaque for stealth; try exclude_from_capture: false if you need transparency.", file=sys.stderr)
        except Exception as e:
            print(f"[Overlay] Stealth flags not applied: {e}", file=sys.stderr)

    def _start_drag(self, event):
        self._drag_start = (event.x_root, event.y_root)

    def _on_drag(self, event):
        if self._drag_start is None:
            return
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        self._drag_start = (event.x_root, event.y_root)
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _start_resize(self, event):
        self._resize_start = (
            event.x_root,
            event.y_root,
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

    def _on_resize(self, event):
        if not hasattr(self, "_resize_start"):
            return
        ox, oy, w0, h0 = self._resize_start
        dw = event.x_root - ox
        dh = event.y_root - oy
        w = max(200, w0 + dw)
        h = max(120, h0 + dh)
        self.root.geometry(f"{w}x{h}")
        self._resize_start = (event.x_root, event.y_root, w, h)

    def show(self):
        if self.root is None:
            self._create_window()
        self.root.deiconify()
        self.root.lift()
        # Re-apply stealth flags after deiconify so the window never shows
        # in the taskbar, even after toggling exam mode or hiding/showing.
        if platform.system() == "Windows":
            try:
                self.root.after(10, self._apply_stealth_flags)
            except Exception:
                pass

    def hide(self):
        """Hide the overlay window (used briefly while capturing screenshots in exam mode)."""
        if self.root is None:
            return
        self.root.withdraw()

    def set_text(self, text: str):
        if self.text_widget is None:
            return
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, text)
        self.text_widget.config(state=tk.DISABLED)

    def _do_clear(self):
        if self.text_widget is None:
            return
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(
            tk.END,
            "Hold Alt+R to record a question. Release to get an answer.\n"
            "Exam/Code/Amp (buttons): window becomes extra transparent.\n"
            "Alt+S to scan screen MCQ. Alt+Q to scan code. Alt+W to scan amp.\n"
            "Hold Alt+A to show the answer for the last scan.\n"
            "Clear: Alt+C or click Clear.",
        )
        self.text_widget.config(state=tk.DISABLED)

    def clear(self):
        self._do_clear()

    def run(self):
        if self.root is None:
            self._create_window()
        self.root.mainloop()

    def quit(self):
        if self.root:
            self.root.quit()
            self.root.destroy()
