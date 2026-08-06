# ui/modified_files_tab.py
import os
import datetime
import logging
import threading
import customtkinter as ctk

from ui import theme
from file_scanner import FileScanner, needs_backup

logger = logging.getLogger(__name__)


class ModifiedFilesTab:
    """UI for the Modified Files tab: a table of backup jobs that currently
    have source files pending backup (changed since the last run)."""

    def __init__(self, parent, tab_view, db_session, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.Session = session_factory
        self._scanning = False

        self.setup_tab(tab_view)

    def setup_tab(self, tab_view):
        tab = tab_view.tab("Modified Files")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)

        # Controls
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=0, pady=(0, 6), sticky="ew")
        controls_frame.grid_columnconfigure(0, weight=1)

        theme.section_label(controls_frame, "Jobs With Modified Files").grid(
            row=0, column=0, sticky="w"
        )

        self.refresh_button = theme.primary_button(
            controls_frame, text="Refresh", command=self.refresh
        )
        self.refresh_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.status_label = ctk.CTkLabel(
            main_frame, text="Click Refresh to scan backup jobs for changes.",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        )
        self.status_label.grid(row=1, column=0, padx=2, pady=(0, 8), sticky="w")

        # Table
        table_card = theme.card(main_frame)
        table_card.grid(row=2, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        self._column_weights = [3, 4, 2, 2, 2]
        header = ctk.CTkFrame(table_card, fg_color=theme.SURFACE_ALT, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))
        for col, text in enumerate(["Job", "Source Path", "Modified Files", "Last Backup", ""]):
            header.grid_columnconfigure(col, weight=self._column_weights[col])
            ctk.CTkLabel(header, text=text, font=theme.FONT_BODY_BOLD).grid(
                row=0, column=col, padx=12, pady=8, sticky="w"
            )

        self.table_body = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.table_body.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        for col, weight in enumerate(self._column_weights):
            self.table_body.grid_columnconfigure(col, weight=weight)

    def refresh(self):
        """Rescan every active job's source directory for pending changes."""
        if self._scanning:
            return
        self._scanning = True
        self.refresh_button.configure(state="disabled", text="Scanning...")
        self.status_label.configure(text="Scanning backup jobs...")
        self._clear_rows()

        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _clear_rows(self):
        for widget in self.table_body.winfo_children():
            widget.destroy()

    def _scan_thread(self):
        session = self.Session()
        try:
            BackupJob = self.parent.BackupJob
            FileMetadata = self.parent.FileMetadata
            jobs = session.query(BackupJob).filter_by(is_active=True).order_by(BackupJob.name).all()

            results = []
            for job in jobs:
                if not os.path.exists(job.source_path):
                    results.append({
                        "name": job.name, "source_path": job.source_path,
                        "last_backup": job.last_backup, "modified_files": None,
                        "error": "Source not found",
                    })
                    continue

                source_files, scan_errors = FileScanner.scan_directory(job.source_path)
                if scan_errors:
                    logger.warning(f"{len(scan_errors)} paths unreadable while scanning {job.source_path}")

                modified = []
                for file_data in source_files:
                    file_meta = session.query(FileMetadata).filter_by(
                        job_id=job.id, file_path=file_data["path"]
                    ).first()
                    rel_path = os.path.relpath(file_data["path"], job.source_path)
                    dest_file = os.path.join(job.destination_path, rel_path) if job.destination_path else None
                    if needs_backup(file_meta, file_data, dest_file):
                        modified.append(rel_path)

                results.append({
                    "name": job.name, "source_path": job.source_path,
                    "last_backup": job.last_backup, "modified_files": modified,
                    "error": None,
                })

            self.parent.post_to_ui(lambda: self._show_results(results))
        except Exception as e:
            logger.error(f"Error scanning jobs for modified files: {e}")
            self.parent.post_to_ui(lambda: self._show_error(str(e)))
        finally:
            session.close()

    def _show_error(self, message):
        self._scanning = False
        self.refresh_button.configure(state="normal", text="Refresh")
        self.status_label.configure(text=f"Error: {message}")

    def _show_results(self, results):
        self._scanning = False
        self.refresh_button.configure(state="normal", text="Refresh")
        self._clear_rows()

        rows = [r for r in results if r["error"] or r["modified_files"]]
        now = datetime.datetime.now().strftime("%H:%M:%S")

        if not rows:
            self.status_label.configure(text=f"All jobs are up to date. Last checked {now}.")
            ctk.CTkLabel(
                self.table_body, text="No jobs currently have modified files.",
                font=theme.FONT_BODY, text_color=theme.TEXT_MUTED,
            ).grid(row=0, column=0, columnspan=5, padx=10, pady=20, sticky="w")
            return

        self.status_label.configure(
            text=f"{len(rows)} of {len(results)} job(s) have modified files. Last checked {now}."
        )

        for i, r in enumerate(rows):
            ctk.CTkLabel(self.table_body, text=r["name"], font=theme.FONT_BODY, anchor="w").grid(
                row=i, column=0, padx=12, pady=6, sticky="w"
            )

            source_text = r["source_path"]
            if len(source_text) > 50:
                source_text = "..." + source_text[-47:]
            ctk.CTkLabel(self.table_body, text=source_text, font=theme.FONT_SMALL,
                         text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=i, column=1, padx=12, pady=6, sticky="w"
            )

            if r["error"]:
                theme.badge(self.table_body, r["error"], kind="danger").grid(
                    row=i, column=2, padx=12, pady=6, sticky="w"
                )
            else:
                count = len(r["modified_files"])
                theme.badge(
                    self.table_body, f"{count} file{'s' if count != 1 else ''}", kind="warning"
                ).grid(row=i, column=2, padx=12, pady=6, sticky="w")

            last_backup = "Never" if not r["last_backup"] else r["last_backup"].strftime("%Y-%m-%d %H:%M")
            ctk.CTkLabel(self.table_body, text=last_backup, font=theme.FONT_SMALL,
                         text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=i, column=3, padx=12, pady=6, sticky="w"
            )

            if r["modified_files"]:
                view_button = theme.secondary_button(
                    self.table_body, text="View", width=64,
                    command=lambda name=r["name"], src=r["source_path"], files=r["modified_files"]:
                        self._view_files(name, src, files)
                )
                view_button.grid(row=i, column=4, padx=12, pady=6, sticky="w")

    def _view_files(self, job_name, source_path, modified_files):
        """Popup listing the specific files pending backup for one job."""
        win = ctk.CTkToplevel(self.parent)
        win.title(f"Modified Files - {job_name}")
        win.geometry("520x420")
        win.transient(self.parent)
        win.grab_set()

        ctk.CTkLabel(
            win, text=f"{len(modified_files)} file(s) pending backup in {source_path}",
            font=theme.FONT_BODY_BOLD, wraplength=480, justify="left",
        ).pack(padx=12, pady=(12, 6), anchor="w")

        box = ctk.CTkTextbox(win, font=theme.FONT_MONO)
        box.pack(padx=12, pady=(0, 12), fill="both", expand=True)
        box.insert("1.0", "\n".join(modified_files))
        box.configure(state="disabled")

        theme.secondary_button(win, text="Close", command=win.destroy).pack(padx=12, pady=(0, 12))
