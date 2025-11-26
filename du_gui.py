#!/usr/bin/env python3

import fnmatch
import math
import os
import threading
import time
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- Проверка зависимостей ---
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    has_matplotlib = True
except Exception:
    has_matplotlib = False

try:
    import squarify
    has_squarify = True
except Exception:
    has_squarify = False


# --- Вспомогательные функции ---
def human_readable(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(max(size_bytes, 1), 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


def parse_patterns(text: str):
    if not text:
        return []
    parts = [p.strip() for p in text.replace(";", ",").split(",")]
    return [p for p in parts if p]


def matches_any(path: str, patterns):
    if not patterns:
        return False
    basename = os.path.basename(path)
    for pat in patterns:
        if os.path.sep in pat or "/" in pat:
            if fnmatch.fnmatch(path, pat):
                return True
        else:
            if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(path, pat):
                return True
    return False


def normalize_exts(text: str):
    if not text:
        return []
    parts = [p.strip().lower() for p in text.replace(";", ",").split(",")]
    out = []
    for p in parts:
        if not p:
            continue
        if not p.startswith("."):
            p = "." + p
        out.append(p)
    return out


def get_dir_size(path: str, exclude_patterns, include_exts, max_depth=None, _cur_depth=0) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            full = entry.path
            if matches_any(full, exclude_patterns):
                continue
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                if max_depth is None or _cur_depth < max_depth:
                    total += get_dir_size(full, exclude_patterns, include_exts, max_depth, _cur_depth + 1)
            else:
                if include_exts:
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() not in include_exts:
                        continue
                try:
                    total += entry.stat(follow_symlinks=False).st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def scan_tree(root_path, exclude_patterns, include_exts, max_depth=None):
    results = []
    root_path = os.path.abspath(root_path)

    def walk_dir(current, level):
        try:
            for entry in os.scandir(current):
                full = entry.path
                if matches_any(full, exclude_patterns):
                    continue
                if entry.is_symlink():
                    continue
                rel = os.path.relpath(full, root_path)
                if entry.is_dir(follow_symlinks=False):
                    size = get_dir_size(full, exclude_patterns, include_exts,
                                        max_depth=(max_depth - level - 1) if max_depth is not None else None)
                    results.append({
                        "path": rel,
                        "full": full,
                        "bytes": size,
                        "is_dir": True,
                        "mtime": entry.stat().st_mtime
                    })
                    if max_depth is None or level + 1 < max_depth:
                        walk_dir(full, level + 1)
                else:
                    if include_exts:
                        _, ext = os.path.splitext(entry.name)
                        if ext.lower() not in include_exts:
                            continue
                    try:
                        size = entry.stat(follow_symlinks=False).st_size
                        mtime = entry.stat(follow_symlinks=False).st_mtime
                    except Exception:
                        size, mtime = 0, 0
                    results.append({
                        "path": rel,
                        "full": full,
                        "bytes": size,
                        "is_dir": False,
                        "mtime": mtime
                    })
        except Exception:
            pass

    walk_dir(root_path, 0)
    return results


# --- Основной GUI ---
class DUApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Disk Usage — Treemap GUI")
        self.geometry("1400x800")

        # Переменные
        self.selected_dir = tk.StringVar()
        self.exclude_text = tk.StringVar()
        self.include_ext_text = tk.StringVar()
        self.sort_by = tk.StringVar(value="size")
        self.reverse = tk.BooleanVar(value=False)
        self.depth = tk.IntVar(value=2)
        self.topn = tk.IntVar(value=0)
        self.block_size = tk.IntVar(value=0)
        self.percent_threshold = tk.DoubleVar(value=0.0)

        # Состояние
        self.results = []
        self.figure = None
        self.canvas = None
        self._zoom_state = {"press": None}
        self.tooltip = None

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(top, text="Directory:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.selected_dir).grid(row=0, column=1, sticky=tk.EW, padx=4)
        ttk.Button(top, text="Browse...", command=self.browse).grid(row=0, column=2, padx=4)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Exclude patterns:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.exclude_text).grid(row=1, column=1, sticky=tk.EW, padx=4)

        ttk.Label(top, text="Include extensions:").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.include_ext_text).grid(row=2, column=1, sticky=tk.EW, padx=4)

        ttk.Label(top, text="Sort by:").grid(row=1, column=2, sticky=tk.W)
        ttk.Combobox(top, textvariable=self.sort_by,
                     values=["size", "name", "date"], state="readonly", width=10).grid(row=1, column=3, sticky=tk.W)

        ttk.Checkbutton(top, text="Reverse", variable=self.reverse).grid(row=2, column=2, sticky=tk.W)

        ttk.Label(top, text="Depth:").grid(row=3, column=0, sticky=tk.W)
        ttk.Spinbox(top, from_=0, to=10, textvariable=self.depth, width=6).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(top, text="Top N (0=all):").grid(row=3, column=2, sticky=tk.W)
        ttk.Spinbox(top, from_=0, to=1000, textvariable=self.topn, width=6).grid(row=3, column=3, sticky=tk.W)

        ttk.Label(top, text="Block size:").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.block_size, width=8).grid(row=4, column=1, sticky=tk.W)

        ttk.Label(top, text="Threshold %:").grid(row=4, column=2, sticky=tk.W)
        ttk.Entry(top, textvariable=self.percent_threshold, width=8).grid(row=4, column=3, sticky=tk.W)

        ttk.Button(top, text="Scan", command=self.start_scan).grid(row=5, column=0, pady=5)
        ttk.Button(top, text="Apply % Filter", command=self.apply_percent_filter).grid(row=5, column=1, pady=5)
        ttk.Button(top, text="Save Treemap PNG", command=self.save_treemap).grid(row=5, column=2, pady=5)

        # Панель с таблицей и treemap
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Левая таблица
        left = ttk.Frame(main)
        main.add(left, weight=1)
        cols = ("path", "bytes", "human", "type", "blocks", "percent", "date")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            if c == "path":
                self.tree.column(c, anchor=tk.W, width=420)
            elif c == "date":
                self.tree.column(c, anchor=tk.CENTER, width=120)
            else:
                self.tree.column(c, anchor=tk.E, width=100)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Правая treemap
        right = ttk.Frame(main)
        main.add(right, weight=1)
        self.treemap_frame = ttk.Frame(right)
        self.treemap_frame.pack(fill=tk.BOTH, expand=True)

        self.lbl_status = ttk.Label(self, text="Ready")
        self.lbl_status.pack(anchor=tk.W, padx=8, pady=4)

        if not has_matplotlib or not has_squarify:
            self._set_status("⚠️ Для treemap установите matplotlib и squarify")

    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.selected_dir.set(d)

    def start_scan(self):
        path = self.selected_dir.get()
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", "Выберите корректную директорию.")
            return
        threading.Thread(target=self._scan_thread, args=(path,), daemon=True).start()

    def _scan_thread(self, target):
        self._set_status("Сканирование...")
        exclude = parse_patterns(self.exclude_text.get())
        include_exts = normalize_exts(self.include_ext_text.get())
        entries = scan_tree(target, exclude, include_exts, self.depth.get())

        total = sum(e["bytes"] for e in entries)

        # сортировка
        if self.sort_by.get() == "size":
            entries.sort(key=lambda e: e["bytes"], reverse=not self.reverse.get())
        elif self.sort_by.get() == "name":
            entries.sort(key=lambda e: e["path"].lower(), reverse=self.reverse.get())
        else:
            entries.sort(key=lambda e: e["mtime"], reverse=not self.reverse.get())

        topn = self.topn.get()
        if topn > 0:
            entries = entries[:topn]

        for e in entries:
            e["human"] = human_readable(e["bytes"])
            if self.block_size.get() > 0:
                e["blocks"] = math.ceil(e["bytes"]/self.block_size.get())
            else:
                e["blocks"] = ""
            e["percent"] = round((e["bytes"]/total*100) if total>0 else 0, 2)
            e["date_str"] = datetime.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d %H:%M")

        self.results = entries
        self.after(0, self.populate_tree)

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for e in self.results:
            self.tree.insert("", tk.END,
                             values=(e["path"], e["bytes"], e["human"],
                                     "dir" if e["is_dir"] else "file",
                                     e["blocks"], f"{e['percent']}%", e["date_str"]))
        self.draw_treemap(self.results)
        self._set_status(f"Готово. {len(self.results)} элементов.")

    # --- фильтр по проценту ---
    def apply_percent_filter(self):
        thr = self.percent_threshold.get()
        filtered = [e for e in self.results if e["percent"] >= thr]
        self.tree.delete(*self.tree.get_children())
        for e in filtered:
            self.tree.insert("", tk.END,
                             values=(e["path"], e["bytes"], e["human"],
                                     "dir" if e["is_dir"] else "file",
                                     e["blocks"], f"{e['percent']}%", e["date_str"]))
        self.draw_treemap(filtered)
        self._set_status(f"Фильтр: >= {thr}%, элементов: {len(filtered)}")

    # --- Treemap ---
    def draw_treemap(self, items):
        if not (has_matplotlib and has_squarify):
            return

        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.figure:
            plt.close(self.figure)

        self.figure, ax = plt.subplots(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.treemap_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        sizes = [e["bytes"] for e in items if e["bytes"] > 0]
        if not sizes:
            ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
            self.canvas.draw()
            return

        labels = [os.path.basename(e["path"]) or e["path"] for e in items]
        rects = squarify.squarify(squarify.normalize_sizes(sizes, 100, 100), 0, 0, 100, 100)
        total = sum(sizes)
        colors = plt.cm.tab20.colors
        self.rect_info = []

        for i, (rect, e) in enumerate(zip(rects, items)):
            x, y, dx, dy = rect["x"], rect["y"], rect["dx"], rect["dy"]
            ax.add_patch(plt.Rectangle((x, y), dx, dy,
                                       facecolor=colors[i % len(colors)],
                                       edgecolor="white"))
            percent = e["bytes"] / total * 100
            if percent > 1.0:
                ax.text(x + dx / 2, y + dy / 2,
                        f"{labels[i]}\n{percent:.1f}%",
                        ha="center", va="center", fontsize=8)
            self.rect_info.append((x, y, dx, dy, e))

        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")

        self.tooltip = tk.Label(self.treemap_frame, bg="lightyellow", relief="solid", bd=1)
        self.tooltip.place_forget()

        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

        self.canvas.draw()

    # --- Навигация и масштабирование ---
    def _on_scroll(self, event):
        if event.inaxes is None:
            return
        ax = event.inaxes
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        zoom = 1.15 if event.button == "up" else 0.87
        xdata, ydata = event.xdata or 50, event.ydata or 50
        new_w = (x_max - x_min) / zoom
        new_h = (y_max - y_min) / zoom
        ax.set_xlim(xdata - new_w / 2, xdata + new_w / 2)
        ax.set_ylim(ydata - new_h / 2, ydata + new_h / 2)
        ax.figure.canvas.draw_idle()

    def _on_press(self, event):
        if event.inaxes and event.button == 1:
            self._zoom_state["press"] = {
                "x": event.x,
                "y": event.y,
                "xlim": event.inaxes.get_xlim(),
                "ylim": event.inaxes.get_ylim(),
                "last_update": 0
            }

    def _on_motion(self, event):
        if not self._zoom_state.get("press") or event.inaxes is None:
            return
        state = self._zoom_state["press"]
        ax = event.inaxes
        now = time.time()
        if now - state["last_update"] < 0.016:
            return
        state["last_update"] = now
        dx = event.x - state["x"]
        dy = event.y - state["y"]
        x0, x1 = state["xlim"]
        y0, y1 = state["ylim"]
        width = (x1 - x0)
        height = (y1 - y0)
        speed = 1
        fig_w, fig_h = event.canvas.get_width_height()
        dx_data = -dx / fig_w * width * speed
        dy_data = -dy / fig_h * height * speed
        ax.set_xlim(x0 + dx_data, x1 + dx_data)
        ax.set_ylim(y0 + dy_data, y1 + dy_data)
        event.canvas.draw_idle()

    def _on_release(self, event):
        self._zoom_state["press"] = None

    def _on_hover(self, event):
        if not hasattr(self, "rect_info"):
            return
        found = None
        for x, y, dx, dy, e in self.rect_info:
            if event.xdata and event.ydata and x <= event.xdata <= x + dx and y <= event.ydata <= y + dy:
                found = e
                break
        if found:
            txt = f"{found['full']}\n{found['human']} ({found['percent']}%)"
            self.tooltip.config(text=txt)
            self.tooltip.place(x=event.x + 15, y=event.y + 15)
        else:
            self.tooltip.place_forget()

    def save_treemap(self):
        if not self.figure:
            messagebox.showinfo("Info", "Нет карты для сохранения")
            return
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG", "*.png")])
        if not p:
            return
        self.figure.savefig(p)
        messagebox.showinfo("Сохранено", f"Treemap сохранён в {p}")

    def _set_status(self, text):
        self.lbl_status.config(text=text)


if __name__ == "__main__":
    app = DUApp()
    app.mainloop()
