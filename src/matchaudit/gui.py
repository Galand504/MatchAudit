"""MatchAudit GUI — desktop interface for the comparison engine.

Requires ``customtkinter`` (install with ``pip install matchaudit[gui]``).

Usage::

    python -m matchaudit.gui
    # or:  matchaudit-gui
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path
from tkinter import messagebox, filedialog
from typing import Any

import customtkinter as ctk

from matchaudit.cli import _auto_detect_key_columns, _is_image
from matchaudit.core.comparator import compare as run_comparison
from matchaudit.core.models import ComparisonResult, RowDiff, RowShift
from matchaudit.readers import detect_reader
from matchaudit.readers.ocr import OcrReader

# ── Colour palette ────────────────────────────────────────────────────────────
COLOR_MATCH = "#2ecc71"
COLOR_MISMATCH = "#e74c3c"
COLOR_WARNING = "#f39c12"
COLOR_BG = "#1a1a2e"
COLOR_SURFACE = "#16213e"
COLOR_TEXT = "#eeeeee"
COLOR_ACCENT = "#0f3460"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MatchAuditApp(ctk.CTk):
    """Desktop GUI for MatchAudit — compare source data against captures."""

    def __init__(self) -> None:
        super().__init__()

        self.title("MatchAudit")
        self.geometry("960x720")
        self.minsize(800, 600)
        self.configure(fg_color=COLOR_BG)

        # ── state ────────────────────────────────────────────────────────
        self.source_path: Path | None = None
        self.captured_path: Path | None = None
        self._ocr_reader: OcrReader | None = None
        self._result: ComparisonResult | None = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_config_panel()
        self._build_results_panel()

    # ── config panel (left) ───────────────────────────────────────────────

    def _build_config_panel(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(
            frame, text="⚙️  Configuración",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT,
        ).grid(row=0, column=0, columnspan=3, pady=(10, 15), sticky="w")

        # ── Source file ──
        ctk.CTkLabel(frame, text="📁 Archivo fuente:", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=1, column=0, columnspan=3,
                                                       sticky="w", padx=10, pady=(0, 2))
        self._src_label = ctk.CTkLabel(frame, text="(ninguno)", anchor="w",
                                        fg_color=COLOR_BG, corner_radius=6,
                                        text_color="#8899aa")
        self._src_label.grid(row=2, column=0, columnspan=2, sticky="ew",
                              padx=10, pady=(0, 5), ipady=4)
        ctk.CTkButton(frame, text="Examinar", width=80,
                       command=self._browse_source,
                       fg_color=COLOR_ACCENT).grid(row=2, column=2, padx=(0, 10))

        # ── Captured file ──
        ctk.CTkLabel(frame, text="📸 Captura:", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=3, column=0, columnspan=3,
                                                       sticky="w", padx=10, pady=(8, 2))
        self._cap_label = ctk.CTkLabel(frame, text="(ninguno)", anchor="w",
                                        fg_color=COLOR_BG, corner_radius=6,
                                        text_color="#8899aa")
        self._cap_label.grid(row=4, column=0, columnspan=2, sticky="ew",
                              padx=10, pady=(0, 5), ipady=4)
        ctk.CTkButton(frame, text="Examinar", width=80,
                       command=self._browse_captured,
                       fg_color=COLOR_ACCENT).grid(row=4, column=2, padx=(0, 10))

        # ── Key column ──
        ctk.CTkLabel(frame, text="🔑 Columna clave:", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=5, column=0, columnspan=3,
                                                       sticky="w", padx=10, pady=(8, 2))
        self._key_dropdown = ctk.CTkComboBox(frame, values=["(auto-detectar)"],
                                              state="readonly", width=200)
        self._key_dropdown.grid(row=6, column=0, columnspan=3, sticky="ew",
                                 padx=10, pady=(0, 5))

        # ── Options ──
        self._upscale_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="OCR upscale (más lento, más preciso)",
                         variable=self._upscale_var,
                         font=ctk.CTkFont(size=12)).grid(row=7, column=0, columnspan=3,
                                                          sticky="w", padx=10, pady=(8, 5))

        # ── Compare button ──
        self._compare_btn = ctk.CTkButton(
            frame, text="🔍  Comparar",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            fg_color=COLOR_ACCENT,
            hover_color="#1a5276",
            command=self._run_comparison,
        )
        self._compare_btn.grid(row=8, column=0, columnspan=3, sticky="ew",
                                padx=10, pady=(15, 0))

        # ── Progress ──
        self._progress = ctk.CTkProgressBar(frame, mode="indeterminate",
                                             fg_color=COLOR_BG,
                                             progress_color=COLOR_ACCENT)
        self._progress.grid(row=9, column=0, columnspan=3, sticky="ew",
                             padx=10, pady=(8, 0))
        self._progress.grid_remove()

        self._status_label = ctk.CTkLabel(frame, text="", anchor="w",
                                           font=ctk.CTkFont(size=12))
        self._status_label.grid(row=10, column=0, columnspan=3, sticky="sw",
                                 padx=10, pady=(5, 10))

    # ── results panel (right) ─────────────────────────────────────────────

    def _build_results_panel(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=12)
        frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)

        # ── Match rate ──
        self._match_rate_label = ctk.CTkLabel(
            frame, text="Resultados",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#667788",
        )
        self._match_rate_label.grid(row=0, column=0, pady=(15, 5))

        # ── Summary stats ──
        self._stats_frame = ctk.CTkFrame(frame, fg_color=COLOR_BG, corner_radius=8)
        self._stats_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        self._stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        stats_labels = ["Esperadas", "Capturadas", "Coinciden", "Diferencias", "Match %"]
        self._stat_values: dict[str, ctk.CTkLabel] = {}
        for i, text in enumerate(stats_labels):
            ctk.CTkLabel(self._stats_frame, text=text, font=ctk.CTkFont(size=11),
                          text_color="#8899aa").grid(row=0, column=i, padx=4, pady=(6, 0))
            val = ctk.CTkLabel(self._stats_frame, text="—", font=ctk.CTkFont(size=18, weight="bold"),
                                text_color="#667788")
            val.grid(row=1, column=i, padx=4, pady=(0, 6))
            self._stat_values[text] = val

        # ── Tabbed details ──
        self._tabs = ctk.CTkTabview(frame, fg_color=COLOR_BG,
                                     segmented_button_fg_color=COLOR_BG,
                                     segmented_button_selected_color=COLOR_ACCENT)
        self._tabs.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))

        # Create tabs but leave them empty until results arrive
        self._tabs.add("Diferencias")
        self._tabs.add("Faltantes")
        self._tabs.add("Sobrantes")

        self._diff_textbox = self._make_textbox(self._tabs.tab("Diferencias"))
        self._missing_textbox = self._make_textbox(self._tabs.tab("Faltantes"))
        self._extra_textbox = self._make_textbox(self._tabs.tab("Sobrantes"))

        # ── Export button ──
        self._export_btn = ctk.CTkButton(
            frame, text="📤 Exportar JSON", width=120,
            fg_color=COLOR_ACCENT, hover_color="#1a5276",
            command=self._export_json,
        )
        self._export_btn.grid(row=3, column=0, sticky="e", padx=15, pady=(0, 10))
        self._export_btn.grid_remove()

    @staticmethod
    def _make_textbox(parent: ctk.CTkFrame) -> ctk.CTkTextbox:
        tb = ctk.CTkTextbox(parent, wrap="none", font=ctk.CTkFont(family="Consolas", size=12),
                             fg_color=COLOR_BG, text_color=COLOR_TEXT)
        tb.grid(sticky="nsew")
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        return tb

    # ── file dialogs ──────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo fuente",
            filetypes=[
                ("Archivos de datos", "*.csv *.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls"),
            ],
        )
        if path:
            self.source_path = Path(path)
            self._src_label.configure(
                text=self.source_path.name,
                text_color=COLOR_TEXT,
            )
            self._refresh_key_columns()

    def _browse_captured(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar captura",
            filetypes=[
                ("Capturas e imágenes", "*.png *.jpg *.jpeg *.csv *.xlsx *.xls"),
                ("Imágenes", "*.png *.jpg *.jpeg"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls"),
            ],
        )
        if path:
            self.captured_path = Path(path)
            self._cap_label.configure(
                text=self.captured_path.name,
                text_color=COLOR_TEXT,
            )
            self._refresh_key_columns()

    def _refresh_key_columns(self) -> None:
        """Try to auto-detect key columns based on selected files."""
        if self.source_path is None or self.captured_path is None:
            return
        try:
            source_df = detect_reader(self.source_path).read(self.source_path)
            if _is_image(self.captured_path):
                # We don't OCR just to populate the dropdown — read headers only
                cap_df = source_df.head(0).copy()  # empty schema placeholder
            else:
                cap_df = detect_reader(self.captured_path).read(self.captured_path)
            detected = _auto_detect_key_columns(source_df, cap_df)

            # Populate dropdown with all common columns + detected default
            common = sorted(set(source_df.columns) & set(cap_df.columns)) if not _is_image(self.captured_path) else sorted(source_df.columns)
            candidates = ["(auto-detectar)"] + common
            self._key_dropdown.configure(values=candidates)

            if detected:
                idx = candidates.index(detected[0]) if detected[0] in candidates else 0
                self._key_dropdown.set(detected[0])
            else:
                self._key_dropdown.set("(auto-detectar)")
        except Exception:
            pass  # swallow errors — dropdown just stays with defaults

    # ── comparison runner (async) ──────────────────────────────────────────

    def _run_comparison(self) -> None:
        if self.source_path is None or self.captured_path is None:
            messagebox.showwarning("Faltan archivos",
                                    "Seleccioná archivo fuente y captura primero.")
            return

        self._compare_btn.configure(state="disabled", text="⏳ Comparando…")
        self._match_rate_label.configure(text="Procesando…", text_color="#8899aa")
        self._progress.grid()
        self._progress.start()
        self._status_label.configure(text="Leyendo archivos…")

        threading.Thread(target=self._compare_thread, daemon=True).start()

    def _compare_thread(self) -> None:
        try:
            lang = ["es", "en"]
            upscale = self._upscale_var.get()

            # ── 1. Read source ──
            self.after(0, lambda: self._status_label.configure(text="Leyendo archivo fuente…"))
            source_reader = detect_reader(self.source_path)
            source_df = source_reader.read(self.source_path)

            # ── 2. Read captured ──
            self.after(0, lambda: self._status_label.configure(text="Leyendo captura…"))
            if _is_image(self.captured_path):
                if self._ocr_reader is None:
                    self._ocr_reader = OcrReader()
                captured_df = self._ocr_reader.read(
                    self.captured_path, language=lang,
                    ocr_upscale=upscale,
                )
            else:
                captured_df = detect_reader(self.captured_path).read(self.captured_path)

            # ── 3. Key columns ──
            key_raw = self._key_dropdown.get()
            if key_raw and key_raw != "(auto-detectar)":
                keys = [key_raw]
            else:
                detected = _auto_detect_key_columns(source_df, captured_df)
                if detected:
                    keys = detected
                else:
                    self.after(0, lambda: self._show_error(
                        "No se pudo detectar columna clave automáticamente.\n"
                        "Seleccioná una manualmente en el menú desplegable."
                    ))
                    return

            # ── 4. Compare ──
            self.after(0, lambda: self._status_label.configure(text="Comparando datos…"))
            result = run_comparison(source_df, captured_df, keys)
            self._result = result

            # ── 5. Render ──
            self.after(0, lambda: self._show_results(result, keys))

        except Exception:
            self.after(0, lambda e=traceback.format_exc(): self._show_error(e))

    def _show_error(self, message: str) -> None:
        self._progress.stop()
        self._progress.grid_remove()
        self._compare_btn.configure(state="normal", text="🔍  Comparar")
        self._match_rate_label.configure(text="❌ Error", text_color=COLOR_MISMATCH)
        self._status_label.configure(text="")
        messagebox.showerror("Error", message)

    # ── results display ───────────────────────────────────────────────────

    def _show_results(self, result: ComparisonResult, keys: list[str]) -> None:
        self._progress.stop()
        self._progress.grid_remove()
        self._compare_btn.configure(state="normal", text="🔍  Comparar")
        self._status_label.configure(text="")

        stats = result.stats
        if stats is None:
            return

        # ── Match rate ──
        pct = stats.match_rate * 100
        status_text = f"{pct:.1f}% match"
        if stats.severity == "ok":
            color = COLOR_MATCH
            icon = "✅"
        elif stats.severity == "warning":
            color = COLOR_WARNING
            icon = "⚠️"
        else:
            color = COLOR_MISMATCH
            icon = "❌"
        self._match_rate_label.configure(text=f"{icon}  {status_text}", text_color=color)

        # ── Stats ──
        self._stat_values["Esperadas"].configure(text=str(stats.total_expected))
        self._stat_values["Capturadas"].configure(text=str(stats.total_captured))
        self._stat_values["Coinciden"].configure(text=str(result.matched_rows))
        self._stat_values["Diferencias"].configure(text=str(len(result.mismatched_rows)))
        self._stat_values["Match %"].configure(text=f"{stats.match_rate:.0%}", text_color=color)

        # ── Tabs ──
        self._fill_textbox(self._diff_textbox, result.mismatched_rows,
                            header=f"{'Key':25s} {'Columna':20s} {'Esperado':25s} {'Actual':25s}\n" +
                                   "─" * 95)
        self._fill_textbox(self._missing_textbox, result.missing_rows,
                            header=f"{'Key':25s}\n" + "─" * 30,
                            key_only=True)
        self._fill_textbox(self._extra_textbox, result.extra_rows,
                            header=f"{'Key':25s}\n" + "─" * 30,
                            key_only=True)

        # ── Export ──
        has_issues = bool(result.mismatched_rows or result.missing_rows or result.extra_rows)
        if has_issues:
            self._export_btn.grid()
        else:
            self._export_btn.grid_remove()

    @staticmethod
    def _fill_textbox(
        tb: ctk.CTkTextbox,
        rows: list[RowDiff],
        header: str,
        key_only: bool = False,
    ) -> None:
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.insert("1.0", header + "\n")
        if not rows:
            tb.insert("end", "\n(todo en orden — sin diferencias)\n")
        else:
            for r in rows:
                if key_only:
                    tb.insert("end", f"{str(r.key):25s}\n")
                else:
                    tb.insert("end",
                              f"{str(r.key):25s} {str(r.column or ''):20s} "
                              f"{str(r.expected):25s} {str(r.actual):25s}\n")
        tb.configure(state="disabled")

    # ── export ────────────────────────────────────────────────────────────

    def _export_json(self) -> None:
        if self._result is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Guardar resultado como JSON",
        )
        if not path:
            return
        try:
            import json
            from dataclasses import asdict

            payload = asdict(self._result)
            # Convert non-serialisable fields
            if self._result.stats:
                payload["match_rate_pct"] = round(self._result.stats.match_rate * 100, 1)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            messagebox.showinfo("Exportado", f"Resultado guardado en:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))


def main() -> None:
    app = MatchAuditApp()
    app.mainloop()


if __name__ == "__main__":
    main()
