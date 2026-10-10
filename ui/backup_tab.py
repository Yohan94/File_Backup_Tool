# ui/backup_tab.py
import os
import customtkinter as ctk
import logging
import time
import threading

from ui import theme

# Configure logging
logger = logging.getLogger(__name__)

NO_JOBS = "No jobs available"


class BackupTab:
    """UI for the Backup tab"""

    def __init__(self, parent, tab_view, db_session, backup_engine, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.backup_engine = backup_engine
        self.job_ids_by_name = {}
        self._backup_active = False

        # Store the session factory for creating new sessions in threads
        self.Session = session_factory

        # References to parent widgets
        self.log_message = parent.log_message

        # Setup the backup tab UI
        self.setup_backup_tab(tab_view)

    def setup_backup_tab(self, tab_view):
        backup_tab = tab_view.tab("Backup")
        backup_tab.grid_columnconfigure(0, weight=5, uniform="backup")
        backup_tab.grid_columnconfigure(1, weight=6, uniform="backup")

        # ---------------------------------------------------- left: the job
        left = theme.card(backup_tab)
        left.grid(row=0, column=0, padx=(12, theme.GAP // 2), pady=12, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(4, weight=1)
        self.backup_left_frame = left

        theme.section_label(left, "Job").grid(
            row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 10), sticky="w")

        self.job_selection_var = ctk.StringVar()
        self.job_selection = theme.option_menu(
            left, variable=self.job_selection_var, values=[NO_JOBS],
            command=self.on_job_selected,
        )
        self.job_selection.grid(row=1, column=0, padx=theme.PAD, pady=(0, 14), sticky="ew")

        # Actions sit right under the selector: pick a job, then act on it.
        button_frame = ctk.CTkFrame(left, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=theme.PAD, pady=(0, 18), sticky="ew")
        button_frame.grid_columnconfigure(2, weight=1)

        self.backup_button = theme.primary_button(
            button_frame, text="Start backup", width=130, command=self.start_backup)
        self.backup_button.grid(row=0, column=0, padx=(0, 8))

        self.scan_button = theme.secondary_button(
            button_frame, text="Check for changes", width=160, command=self.scan_job)
        self.scan_button.grid(row=0, column=1)

        self.cancel_button = theme.danger_button(
            button_frame, text="Cancel", width=90, command=self.cancel_backup, state="disabled")
        self.cancel_button.grid(row=0, column=2, sticky="e")
        theme.set_enabled(self.cancel_button, False)

        ctk.CTkFrame(left, fg_color=theme.LINE, height=1, corner_radius=0).grid(
            row=3, column=0, padx=theme.PAD, sticky="ew")

        # Details: a quiet definition list
        details = ctk.CTkFrame(left, fg_color="transparent")
        details.grid(row=4, column=0, padx=theme.PAD, pady=(16, theme.PAD), sticky="nsew")
        details.grid_columnconfigure(1, weight=1)
        self.details_frame = details

        self.job_details = {}
        for i, (key, label_text) in enumerate([
            ("status", "Status"), ("source", "Copies from"),
            ("destination", "Copies to"), ("last_backup", "Last backup"),
        ]):
            theme.field_label(details, label_text).grid(
                row=i, column=0, padx=(0, 18), pady=7, sticky="nw")
            if key == "status":
                value = theme.badge(details, "-", kind="neutral")
            elif key in ("source", "destination"):
                value = ctk.CTkLabel(details, text="-", font=theme.FONT_MONO, anchor="w",
                                     justify="left", wraplength=320)
            else:
                value = ctk.CTkLabel(details, text="-", font=theme.FONT_BODY, anchor="w")
            value.grid(row=i, column=1, pady=7, sticky="w")
            self.job_details[key] = value

        # Empty state: shown instead of the details when there are no jobs
        self.empty_state = ctk.CTkFrame(left, fg_color="transparent")
        theme.section_label(self.empty_state, "No jobs yet", font=theme.FONT_H2).grid(
            row=0, column=0, sticky="w")
        theme.hint_label(
            self.empty_state,
            "A job pairs a folder to protect with a place to copy it.\n"
            "Create one, then come back here to run it.",
        ).grid(row=1, column=0, pady=(2, 12), sticky="w")
        theme.primary_button(
            self.empty_state, text="Create a job",
            command=lambda: self.parent.show_page("Jobs"),
        ).grid(row=2, column=0, sticky="w")

        # --------------------------------------------------- right: progress
        right = theme.card(backup_tab)
        right.grid(row=0, column=1, padx=(theme.GAP // 2, 12), pady=12, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(5, weight=1)
        self.backup_right_frame = right

        theme.section_label(right, "Progress").grid(
            row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 12), sticky="w")

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = theme.ProgressBar(right, height=8, corner_radius=4)
        self.progress_bar.grid(row=1, column=0, padx=theme.PAD, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            right, text="Not started", font=theme.FONT_BODY_BOLD, anchor="w")
        self.progress_label.grid(row=2, column=0, padx=theme.PAD, sticky="w")

        self.time_label = theme.hint_label(right, "Elapsed 00:00:00")
        self.time_label.grid(row=3, column=0, padx=theme.PAD, pady=(0, 16), sticky="w")

        log_header = ctk.CTkFrame(right, fg_color="transparent")
        log_header.grid(row=4, column=0, padx=theme.PAD, pady=(0, 6), sticky="ew")
        log_header.grid_columnconfigure(0, weight=1)
        theme.section_label(log_header, "Activity", font=theme.FONT_H2).grid(
            row=0, column=0, sticky="w")
        theme.secondary_button(
            log_header, text="Clear", width=64, height=28, font=theme.FONT_SMALL_BOLD,
            command=self.clear_log,
        ).grid(row=0, column=1, sticky="e")

        self.log_text = ctk.CTkTextbox(
            right, font=theme.FONT_MONO, fg_color=theme.CANVAS, border_width=1,
            border_color=theme.LINE, corner_radius=theme.RADIUS_SM, wrap="word",
            text_color=theme.TEXT_MUTED,
        )
        self.log_text.grid(row=5, column=0, padx=theme.PAD, pady=(0, theme.PAD), sticky="nsew")
        self.log_text.configure(state="disabled")

        # Link log_text to parent's log_text
        self.parent.log_text = self.log_text
        logger.info(f"log_text set to: {self.log_text}")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def set_jobs(self, jobs):
        """Refresh the job selector, keeping the current selection if it still exists."""
        self.job_ids_by_name = {job.name: job.id for job in jobs}
        if not jobs:
            self.job_selection.configure(values=[NO_JOBS])
            self.job_selection_var.set(NO_JOBS)
            self.update_job_details(None)
            return
        names = [job.name for job in jobs]
        self.job_selection.configure(values=names)
        current = self.job_selection_var.get()
        selected = current if current in self.job_ids_by_name else names[0]
        self.job_selection_var.set(selected)
        self.on_job_selected(selected)

    def select_job(self, job_name):
        """Select a job by name and bring the Backup page forward."""
        if job_name in self.job_ids_by_name:
            self.job_selection_var.set(job_name)
            self.on_job_selected(job_name)
        self.parent.show_page("Backup")

    def _get_selected_job(self, job_name):
        """Resolve the dropdown selection to a job by id, not by (reusable) name."""
        job_id = self.job_ids_by_name.get(job_name)
        if job_id is None:
            return None
        return self.db_session.get(self.parent.BackupJob, job_id)

    def on_job_selected(self, job_name):
        """Handle job selection from dropdown"""
        if job_name == NO_JOBS:
            self.update_job_details(None)
            return

        try:
            job = self._get_selected_job(job_name)
            if job:
                self.update_job_details(job)
        except Exception as e:
            logger.error(f"Error selecting job: {e}")
            self.log_message(f"Error selecting job: {e}")

    def update_job_details(self, job):
        """Update job details display"""
        has_jobs = bool(self.job_ids_by_name)
        if has_jobs:
            self.empty_state.grid_forget()
            self.details_frame.grid()
        else:
            self.details_frame.grid_remove()
            self.empty_state.grid(row=4, column=0, padx=theme.PAD, pady=(16, theme.PAD), sticky="nw")
        if not self._backup_active:
            theme.set_enabled(self.backup_button, has_jobs)
            theme.set_enabled(self.scan_button, has_jobs)

        if not job:
            for key in ("source", "destination", "last_backup"):
                self.job_details[key].configure(text="-")
            theme.set_badge(self.job_details["status"], "-", kind="neutral")
            return

        self.job_details["source"].configure(text=job.source_path)
        self.job_details["destination"].configure(text=job.destination_path)

        last_backup = "Never" if not job.last_backup else job.last_backup.strftime("%d %b %Y, %H:%M")
        self.job_details["last_backup"].configure(text=last_backup)

        if self.backup_engine.running:
            theme.set_badge(self.job_details["status"], "Running", kind="info")
        elif self.backup_engine.paused:
            theme.set_badge(self.job_details["status"], "Paused", kind="warning")
        else:
            theme.set_badge(self.job_details["status"], "Ready", kind="success")

    def scan_job(self):
        """Scan the selected job for changes"""
        job_name = self.job_selection_var.get()
        if job_name == NO_JOBS:
            self.log_message("No job selected")
            return

        try:
            job = self._get_selected_job(job_name)
            if not job:
                self.log_message("Job not found")
                return

            # Check if source directory exists
            if not os.path.exists(job.source_path):
                self.log_message(f"Error: Source directory not found: {job.source_path}")
                return

            # Check if destination directory is available
            if not os.path.exists(job.destination_path):
                self.log_message(f"Error: Destination directory not available: {job.destination_path}")
                self.log_message("Please ensure the external drive is connected or the destination path is accessible")
                return

            self.log_message(f"Scanning job: {job.name}")

            # Start a thread to scan the files. Only the job id crosses the
            # thread boundary — the worker re-queries with its own session.
            threading.Thread(target=self._scan_job_thread, args=(job.id,), daemon=True).start()

        except Exception as e:
            logger.error(f"Error scanning job: {e}")
            self.log_message(f"Error scanning job: {e}")

    def _scan_job_thread(self, job_id):
        """Thread for scanning job files"""
        session = self.Session()
        try:
            job = session.get(self.parent.BackupJob, job_id)
            if not job:
                self.log_message("Job not found")
                return

            source_path = job.source_path
            destination_path = job.destination_path

            # Get source files
            self.log_message("Scanning source directory...")
            from file_scanner import FileScanner, needs_backup as file_needs_backup
            source_files, scan_errors = FileScanner.scan_directory(source_path)

            if scan_errors:
                self.log_message(f"Warning: {len(scan_errors)} paths could not be read — see backup_app.log")
                logger.warning(f"Scan errors for {source_path}: {scan_errors[:10]}")

            if not source_files:
                self.log_message("No files found in source directory")
                return

            self.log_message(f"Found {len(source_files)} files in source directory")

            # Check which files need backup
            files_needing_backup = []
            for file_data in source_files:
                file_meta = session.query(self.parent.FileMetadata).filter_by(
                    job_id=job_id,
                    file_path=file_data['path']
                ).first()

                rel_path = os.path.relpath(file_data['path'], source_path)
                dest_file = os.path.join(destination_path, rel_path)

                if file_needs_backup(file_meta, file_data, dest_file):
                    files_needing_backup.append(file_data['path'])

            if not files_needing_backup:
                self.log_message("All files are up to date")
            else:
                self.log_message(f"{len(files_needing_backup)} files need to be backed up")
                # Show some examples of files needing backup
                for i, file_path in enumerate(files_needing_backup[:5]):
                    rel_path = os.path.relpath(file_path, source_path)
                    self.log_message(f"  - {rel_path}")

                if len(files_needing_backup) > 5:
                    self.log_message(f"  ... and {len(files_needing_backup) - 5} more files")

        except Exception as e:
            logger.error(f"Error in scan thread: {e}")
            self.log_message(f"Error scanning: {e}")
        finally:
            session.close()

    def start_backup(self):
        """Start the backup process for the selected job"""
        job_name = self.job_selection_var.get()
        if job_name == NO_JOBS:
            self.log_message("No job selected")
            return

        try:
            job = self._get_selected_job(job_name)
            if not job:
                self.log_message("Job not found")
                return

            # Check if source directory exists
            if not os.path.exists(job.source_path):
                self.log_message(f"Error: Source directory not found: {job.source_path}")
                return

            # Check if destination directory is available
            if not os.path.exists(job.destination_path):
                self.log_message(f"Error: Destination directory not available: {job.destination_path}")
                self.log_message("Please ensure the external drive is connected or the destination path is accessible")
                return

            # Clear the log
            self.clear_log()

            self.log_message(f"Starting backup job: {job.name}")

            # Reset progress
            self.progress_bar.set(0)
            self.progress_label.configure(text="Looking for changed files")
            self.time_label.configure(text="Elapsed 00:00:00")

            # Update UI controls
            self._backup_active = True
            theme.set_enabled(self.backup_button, False)
            theme.set_enabled(self.scan_button, False)
            theme.set_enabled(self.cancel_button, True)

            # Start the backup process
            success = self.backup_engine.run_backup_job(
                job.id,
                callback=self.backup_completed_callback
            )

            if not success:
                self.log_message("Failed to start backup")
                self._backup_active = False
                theme.set_enabled(self.backup_button, True)
                theme.set_enabled(self.scan_button, True)
                theme.set_enabled(self.cancel_button, False)

        except Exception as e:
            logger.error(f"Error starting backup: {e}")
            self.log_message(f"Error starting backup: {e}")
            self._backup_active = False
            theme.set_enabled(self.backup_button, True)
            theme.set_enabled(self.scan_button, True)
            theme.set_enabled(self.cancel_button, False)

    def backup_completed_callback(self, success, message):
        """Callback for when backup completes"""
        self.log_message(message)

        # Schedule UI updates on main thread
        def update_ui():
            # Update UI controls
            self._backup_active = False
            theme.set_enabled(self.backup_button, True)
            theme.set_enabled(self.scan_button, True)
            theme.set_enabled(self.cancel_button, False)
            self.parent.toast(message, kind="success" if success else "error")

            # The 1 s poll stops once the engine does, so write the final
            # numbers here rather than leaving the last sampled percentage.
            done, total = self.backup_engine.processed_files, self.backup_engine.total_files
            if total:
                self.progress_bar.set(done / total)
                verb = "Finished" if success else "Stopped"
                self.progress_label.configure(text=f"{verb}  —  {done:,} of {total:,} files copied")
            else:
                self.progress_bar.set(1.0 if success else 0)
                self.progress_label.configure(text="Finished  —  nothing needed copying"
                                              if success else "Stopped")

            # Reload job details
            job_name = self.job_selection_var.get()
            if job_name != NO_JOBS:
                self.on_job_selected(job_name)

            # Refresh jobs list
            self.parent.load_backup_jobs()

        self.parent.post_to_ui(update_ui)

    def cancel_backup(self):
        """Cancel the current backup operation"""
        if self.backup_engine.running:
            self.log_message("Cancelling backup...")
            self.backup_engine.cancel_backup()

    def update_ui(self):
        """Update the UI based on the current state"""
        # Update progress display
        if self.backup_engine.running:
            if self.backup_engine.total_files > 0:
                progress = self.backup_engine.processed_files / self.backup_engine.total_files
                self.progress_bar.set(progress)

                percent = int(progress * 100)
                self.progress_label.configure(
                    text=f"{percent}%  —  {self.backup_engine.processed_files:,} of "
                         f"{self.backup_engine.total_files:,} files copied"
                )

                # Update time elapsed
                if self.backup_engine.start_time:
                    elapsed = time.time() - self.backup_engine.start_time
                    hours, remainder = divmod(int(elapsed), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.time_label.configure(
                        text=f"Elapsed {hours:02d}:{minutes:02d}:{seconds:02d}  "
                             f"({self.backup_engine.scanned_files_count:,} files checked)"
                    )

            # Update job status
            job_name = self.job_selection_var.get()
            if job_name != NO_JOBS:
                theme.set_badge(self.job_details["status"], "Running", kind="info")

        # Button state is owned explicitly by _backup_active, not inferred from
        # widget state or engine.running (which toggles between jobs in a batch
        # — see BatchJobsTab, which holds this flag for the whole batch).
        if self._backup_active:
            theme.set_enabled(self.backup_button, False)
            theme.set_enabled(self.scan_button, False)
            theme.set_enabled(self.cancel_button, True)
        else:
            has_jobs = bool(self.job_ids_by_name)
            theme.set_enabled(self.backup_button, has_jobs)
            theme.set_enabled(self.scan_button, has_jobs)
            theme.set_enabled(self.cancel_button, False)