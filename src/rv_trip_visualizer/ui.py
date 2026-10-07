"""Tkinter desktop UI.

Select source files, check them for integrity problems, set page titles and
an output location, then build. Build is refused (by pipeline.build()
itself, not just by this UI) unless the check comes back completely clean -
there's no "build anyway" button, on purpose.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import pipeline, settings


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RV Trip Visualizer")
        self.geometry("880x680")
        self.minsize(760, 560)

        self.settings = settings.load()
        self.selected_files: list[str] = list(self.settings["selected_files"])

        self._build_widgets()
        self._refresh_file_list()
        self._set_build_enabled(False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI --
    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        files_frame = ttk.LabelFrame(self, text="Source files")
        files_frame.pack(fill="x", **pad)

        list_frame = ttk.Frame(files_frame)
        list_frame.pack(fill="x", padx=8, pady=6)
        self.file_listbox = tk.Listbox(list_frame, height=6, selectmode="extended")
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.file_listbox.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(files_frame)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Add Files...", command=self._add_files).pack(side="left")
        ttk.Button(btns, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Clear All", command=self._clear_files).pack(side="left", padx=(6, 0))
        self.check_button = ttk.Button(btns, text="Check Data", command=self._on_check)
        self.check_button.pack(side="right")

        titles_frame = ttk.LabelFrame(self, text="Page titles")
        titles_frame.pack(fill="x", **pad)
        self.itinerary_title_var = tk.StringVar(value=self.settings["itinerary_title"])
        self.map_title_var = tk.StringVar(value=self.settings["map_title"])
        ttk.Label(titles_frame, text="Itinerary page:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(titles_frame, textvariable=self.itinerary_title_var).grid(row=0, column=1, sticky="we", padx=8, pady=4)
        ttk.Label(titles_frame, text="Map page:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(titles_frame, textvariable=self.map_title_var).grid(row=1, column=1, sticky="we", padx=8, pady=4)
        titles_frame.columnconfigure(1, weight=1)

        out_frame = ttk.LabelFrame(self, text="Output")
        out_frame.pack(fill="x", **pad)
        self.output_dir_var = tk.StringVar(value=self.settings["output_dir"])
        self.base_name_var = tk.StringVar(value=self.settings["base_name"])
        ttk.Label(out_frame, text="Folder:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(out_frame, textvariable=self.output_dir_var).grid(row=0, column=1, sticky="we", padx=8, pady=4)
        ttk.Button(out_frame, text="Browse...", command=self._choose_output_dir).grid(row=0, column=2, padx=8, pady=4)
        ttk.Label(out_frame, text="Base filename:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(out_frame, textvariable=self.base_name_var).grid(row=1, column=1, sticky="we", padx=8, pady=4)
        out_frame.columnconfigure(1, weight=1)

        # Packed with side="bottom" (and before the expanding report panel
        # below) so this bar always keeps its space reserved at the bottom
        # of the window - otherwise, on a short window, pack stacks widgets
        # top-down in call order and the last one (this bar, with the Build
        # button) can get pushed below the visible area entirely, forcing a
        # manual resize just to find it. The report panel's expand=True
        # fill="both" claims whatever vertical space is left instead, which
        # is the thing that should shrink/scroll, not this bar.
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", **pad)
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")
        self.build_button = ttk.Button(bottom, text="Build", command=self._on_build)
        self.build_button.pack(side="right")

        report_frame = ttk.LabelFrame(self, text="Data check report")
        report_frame.pack(fill="both", expand=True, **pad)
        text_frame = ttk.Frame(report_frame)
        text_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.report_text = tk.Text(text_frame, wrap="word", height=14, state="disabled")
        self.report_text.pack(side="left", fill="both", expand=True)
        rscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.report_text.yview)
        rscroll.pack(side="left", fill="y")
        self.report_text.configure(yscrollcommand=rscroll.set)
        self.report_text.tag_configure("error", foreground="#a8311f")
        self.report_text.tag_configure("ok", foreground="#2f5233")
        self.report_text.tag_configure("muted", foreground="#6e7267")

    # ------------------------------------------------------------- files --
    def _add_files(self) -> None:
        initial = self.settings.get("last_browse_dir") or os.path.expanduser("~")
        paths = filedialog.askopenfilenames(
            title="Select trip export files",
            initialdir=initial,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not paths:
            return
        for p in paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
        self.settings["last_browse_dir"] = os.path.dirname(paths[0])
        self._refresh_file_list()
        self._invalidate_check()

    def _remove_selected(self) -> None:
        for i in reversed(self.file_listbox.curselection()):
            del self.selected_files[i]
        self._refresh_file_list()
        self._invalidate_check()

    def _clear_files(self) -> None:
        self.selected_files = []
        self._refresh_file_list()
        self._invalidate_check()

    def _refresh_file_list(self) -> None:
        self.file_listbox.delete(0, "end")
        for p in self.selected_files:
            self.file_listbox.insert("end", p)

    def _choose_output_dir(self) -> None:
        initial = self.output_dir_var.get() or os.path.expanduser("~")
        d = filedialog.askdirectory(title="Choose output folder", initialdir=initial)
        if d:
            self.output_dir_var.set(d)

    # -------------------------------------------------------------- check --
    def _invalidate_check(self) -> None:
        self._set_build_enabled(False)

    def _set_build_enabled(self, enabled: bool) -> None:
        self.build_button.configure(state="normal" if enabled else "disabled")

    def _write_report(self, lines_with_tags) -> None:
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        for text, tag in lines_with_tags:
            self.report_text.insert("end", text + "\n", tag or ())
        self.report_text.configure(state="disabled")

    def _render_report(self, report) -> None:
        if report.is_clean:
            lines = [(f"All {len(report.parsed_files)} file(s) passed. Ready to build.", "ok")]
            if report.log:
                lines += [("", None), ("Notes:", "muted")]
                lines += [(f"  - {l}", "muted") for l in report.log]
        else:
            lines = [(f"{len(report.findings)} issue(s) found - fix these in the source "
                       "data (and re-export, if needed) before building:", "error"), ("", None)]
            by_file: dict[str, list] = {}
            for f in report.findings:
                by_file.setdefault(f.file, []).append(f)
            for file, findings in by_file.items():
                lines.append((file, "error"))
                for f in findings:
                    row = f" (row {f.row})" if f.row else ""
                    lines.append((f"  - {f.message}{row}", None))
                lines.append(("", None))
        self._write_report(lines)

    def _on_check(self) -> None:
        if not self.selected_files:
            messagebox.showinfo("No files selected", "Add at least one source file first.")
            return
        self.status_var.set("Checking...")
        self.update_idletasks()
        report = pipeline.check(self.selected_files)
        self._render_report(report)
        self._set_build_enabled(report.is_clean)
        self.status_var.set("Check complete.")
        self._save_settings()

    # -------------------------------------------------------------- build --
    def _on_build(self) -> None:
        out_dir = self.output_dir_var.get().strip()
        base_name = self.base_name_var.get().strip()
        if not out_dir:
            messagebox.showinfo("Output folder needed", "Choose an output folder first.")
            return
        if not base_name:
            messagebox.showinfo("Base filename needed", "Enter a base filename first.")
            return

        self.status_var.set("Building...")
        self.update_idletasks()
        try:
            result = pipeline.build(
                self.selected_files,
                out_dir,
                base_name,
                self.itinerary_title_var.get().strip() or "The Itinerary",
                self.map_title_var.get().strip() or "Everywhere We've Stayed",
            )
        except pipeline.NotClean as e:
            self._render_report(e.report)
            self._set_build_enabled(False)
            self.status_var.set("Build refused - data isn't clean.")
            messagebox.showwarning("Build refused", str(e))
            return
        except Exception as e:
            self.status_var.set("Build failed.")
            messagebox.showerror("Build failed", str(e))
            return

        lines = [(f"Wrote {len(result['outputs'])} file(s) to {out_dir}:", "ok")]
        lines += [(f"  - {os.path.basename(p)}", None) for p in result["outputs"].values()]
        if result["log"]:
            lines += [("", None), ("Notes:", "muted")]
            lines += [(f"  - {l}", "muted") for l in result["log"]]
        self._write_report(lines)
        self.status_var.set("Build complete.")
        self._save_settings()

    # ------------------------------------------------------------ settings --
    def _save_settings(self) -> None:
        self.settings.update({
            "selected_files": list(self.selected_files),
            "output_dir": self.output_dir_var.get().strip(),
            "base_name": self.base_name_var.get().strip(),
            "itinerary_title": self.itinerary_title_var.get().strip(),
            "map_title": self.map_title_var.get().strip(),
        })
        settings.save(self.settings)

    def _on_close(self) -> None:
        self._save_settings()
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
