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

        table_card = theme.card(tab)
        table_card.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(2, weight=1)

        # Controls
        controls_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 14), sticky="ew")
        controls_frame.grid_columnconfigure(0, weight=1)

        self.status_label = theme.hint_label(
            controls_frame, "Check your jobs to see which files changed since their last backup.",
            font=theme.FONT_BODY)
        self.status_label.grid(row=0, column=0, sticky="w")

        self.refresh_button = theme.primary_button(
            controls_frame, text="Check now", width=120, command=self.refresh)
        self.refresh_button.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.parent.bind_all("<F5>", lambda _e: self.refresh())

        # Table header. Header and body share column sizing so they line up.
        self._column_weights = [3, 5, 2, 3, 3]
        header = ctk.CTkFrame(table_card, fg_color="transparent", corner_radius=0)
        # Offsets match the scrollable body (its inner inset + scrollbar)
        header.grid(row=1, column=0, sticky="ew", padx=(theme.PAD + 14, theme.PAD + 22))
        for col, text in enumerate(["Job", "Folder", "Changed", "Last backup", ""]):
            header.grid_columnconfigure(col, weight=self._column_weights[col], uniform="cols")
            theme.field_label(header, text).grid(row=0, column=col, padx=8, pady=(0, 8), sticky="w")
        ctk.CTkFrame(header, fg_color=theme.LINE, height=1, corner_radius=0).grid(
            row=1, column=0, columnspan=5, sticky="ew")

        self.table_body = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.table_body.grid(row=2, column=0, sticky="nsew", padx=(theme.PAD, 8), pady=(0, 12))
        for col, weight in enumerate(self._column_weights):
            self.table_body.grid_columnconfigure(col, weight=weight, uniform="cols")

        self._show_placeholder("Nothing checked yet. Press Check now, or F5.")

    def _show_placeholder(self, text):
        theme.hint_label(self.table_body, text, font=theme.FONT_BODY).grid(
            row=0, column=0, columnspan=5, padx=8, pady=24, sticky="w")

    def refresh(self):
        """Rescan every active job's source directory for pending changes."""
        if self._scanning:
            return
        self._scanning = True
        theme.set_enabled(self.refresh_button, False)
        self.refresh_button.configure(text="Checking…")
        self.status_label.configure(text="Checking each job’s folder for changes…")
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
                        "error": "Folder missing",
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
        theme.set_enabled(self.refresh_button, True)
        self.refresh_button.configure(text="Check now")
        self.status_label.configure(text=f"The check stopped: {message}")

    def _show_results(self, results):
        self._scanning = False
        theme.set_enabled(self.refresh_button, True)
        self.refresh_button.configure(text="Check now")
        self._clear_rows()

        rows = [r for r in results if r["error"] or r["modified_files"]]
        now = datetime.datetime.now().strftime("%H:%M")

        if not results:
            self.status_label.configure(text="You don't have any jobs yet.")
            self._show_placeholder("Create a job on the Jobs page, then check it here.")
            return

        if not rows:
            self.status_label.configure(text=f"Everything is backed up. Checked at {now}.")
            self._show_placeholder("No job has changed files right now.")
            return

        self.status_label.configure(
            text=f"{len(rows)} of {len(results)} jobs need a backup. Checked at {now}."
        )

        for i, r in enumerate(rows):
            row = i * 2   # odd rows hold the divider lines
            pad_y = 10
            ctk.CTkLabel(self.table_body, text=r["name"], font=theme.FONT_BODY_BOLD, anchor="w").grid(
                row=row, column=0, padx=8, pady=pad_y, sticky="w"
            )
            ctk.CTkLabel(self.table_body, text=theme.shorten_path(r["source_path"], 32),
                         font=theme.FONT_MONO, text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=row, column=1, padx=8, pady=pad_y, sticky="w"
            )

            if r["error"]:
                theme.badge(self.table_body, r["error"], kind="danger").grid(
                    row=row, column=2, padx=8, pady=pad_y, sticky="w"
                )
            else:
                count = len(r["modified_files"])
                theme.badge(
                    self.table_body, f"{count:,} file{'s' if count != 1 else ''}", kind="warning"
                ).grid(row=row, column=2, padx=8, pady=pad_y, sticky="w")

            last_backup = "Never" if not r["last_backup"] else r["last_backup"].strftime("%d %b %Y, %H:%M")
            ctk.CTkLabel(self.table_body, text=last_backup, font=theme.FONT_SMALL,
                         text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=row, column=3, padx=8, pady=pad_y, sticky="w"
            )

            if r["modified_files"]:
                actions = ctk.CTkFrame(self.table_body, fg_color="transparent")
                actions.grid(row=row, column=4, padx=8, pady=pad_y, sticky="e")
                theme.secondary_button(
                    actions, text="View", width=60, height=30,
                    command=lambda name=r["name"], src=r["source_path"], files=r["modified_files"]:
                        self._view_files(name, src, files)
                ).grid(row=0, column=0, padx=(0, 6))
                theme.secondary_button(
                    actions, text="Back up", width=80, height=30,
                    command=lambda name=r["name"]: self.parent.backup_tab.select_job(name)
                ).grid(row=0, column=1)

            if i < len(rows) - 1:
                ctk.CTkFrame(self.table_body, fg_color=theme.LINE, height=1, corner_radius=0).grid(
                    row=row + 1, column=0, columnspan=5, sticky="ew", padx=8)

    def _view_files(self, job_name, source_path, modified_files):
        """Popup listing the specific files pending backup for one job."""
        win = ctk.CTkToplevel(self.parent)
        win.title(f"Changed files in {job_name}")
        win.geometry("620x480")
        win.transient(self.parent)
        win.grab_set()
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(2, weight=1)

        count = len(modified_files)
        theme.section_label(win, f"{count:,} changed file{'s' if count != 1 else ''}").grid(
            row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 0), sticky="w")
        theme.hint_label(win, f"Paths are relative to {source_path}", wraplength=560).grid(
            row=1, column=0, padx=theme.PAD, pady=(0, 10), sticky="w")

        box = ctk.CTkTextbox(win, font=theme.FONT_MONO, border_width=1,
                             border_color=theme.LINE, corner_radius=theme.RADIUS_SM)
        box.grid(row=2, column=0, padx=theme.PAD, pady=(0, 14), sticky="nsew")
        box.insert("1.0", "\n".join(modified_files))
        box.configure(state="disabled")

        buttons = ctk.CTkFrame(win, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=theme.PAD, pady=(0, theme.PAD), sticky="e")

        def back_up():
            win.destroy()
            self.parent.backup_tab.select_job(job_name)

        theme.secondary_button(buttons, text="Close", width=90, command=win.destroy).grid(
            row=0, column=0, padx=(0, 8))
        theme.primary_button(buttons, text="Back up this job", width=140, command=back_up).grid(
            row=0, column=1)
        win.bind("<Escape>", lambda _e: win.destroy())
