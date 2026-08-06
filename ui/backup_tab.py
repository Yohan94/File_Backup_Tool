# ui/backup_tab.py
import os
import customtkinter as ctk
import logging
import time
import threading

from ui import theme

# Configure logging
logger = logging.getLogger(__name__)


class BackupTab:
    """UI for the Backup tab"""

    def __init__(self, parent, tab_view, db_session, backup_engine, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.backup_engine = backup_engine
        self.job_details_labels = []
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

        # Create frames
        self.backup_left_frame = theme.card(backup_tab)
        self.backup_left_frame.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="nsew")

        backup_tab.grid_columnconfigure(0, weight=3)
        backup_tab.grid_columnconfigure(1, weight=2)

        self.backup_right_frame = theme.card(backup_tab)
        self.backup_right_frame.grid(row=0, column=1, padx=(8, 0), pady=8, sticky="nsew")

        # Configure left frame (job selection and controls)
        self.backup_left_frame.grid_columnconfigure(0, weight=1)
        self.backup_left_frame.grid_rowconfigure(3, weight=1)

        # Job selection
        theme.section_label(self.backup_left_frame, "Select Backup Job").grid(
            row=0, column=0, padx=16, pady=(16, 6), sticky="w"
        )

        self.job_selection_var = ctk.StringVar()
        self.job_selection = ctk.CTkOptionMenu(
            self.backup_left_frame,
            variable=self.job_selection_var,
            values=["No jobs available"],
            width=280,
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_ALT,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            dropdown_fg_color=theme.SURFACE_ALT,
            corner_radius=theme.RADIUS_SM,
            command=self.on_job_selected
        )
        self.job_selection.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # Buttons frame
        button_frame = ctk.CTkFrame(self.backup_left_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")

        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.scan_button = theme.secondary_button(
            button_frame,
            text="Scan",
            command=self.scan_job
        )
        self.scan_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.backup_button = theme.primary_button(
            button_frame,
            text="Start Backup",
            command=self.start_backup
        )
        self.backup_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.cancel_button = theme.secondary_button(
            button_frame,
            text="Cancel",
            command=self.cancel_backup,
            state="disabled"
        )
        self.cancel_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        # Job details
        job_details_frame = ctk.CTkScrollableFrame(
            self.backup_left_frame, label_text="Job Details",
            label_font=theme.FONT_H2, fg_color=theme.SURFACE_ALT,
            corner_radius=theme.RADIUS_SM,
        )
        job_details_frame.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        job_details_frame.grid_columnconfigure(1, weight=1)

        self.job_details_labels = []
        for i, label_text in enumerate([
            "Name:", "Source:", "Destination:", "Last Backup:", "Status:"
        ]):
            label = ctk.CTkLabel(job_details_frame, text=label_text, font=theme.FONT_BODY_BOLD,
                                  text_color=theme.TEXT_MUTED)
            label.grid(row=i, column=0, padx=(6, 10), pady=4, sticky="w")

            if label_text == "Status:":
                value_label = theme.badge(job_details_frame, "-", kind="neutral")
            else:
                value_label = ctk.CTkLabel(job_details_frame, text="-", font=theme.FONT_BODY, anchor="w")
            value_label.grid(row=i, column=1, padx=6, pady=4, sticky="w")
            self.job_details_labels.append(value_label)

        # Configure right frame (backup progress and log)
        self.backup_right_frame.grid_columnconfigure(0, weight=1)
        self.backup_right_frame.grid_rowconfigure(4, weight=1)

        # Progress section
        theme.section_label(self.backup_right_frame, "Backup Progress").grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w"
        )

        # Progress bar
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(
            self.backup_right_frame, height=14, corner_radius=7,
            progress_color=theme.ACCENT, fg_color=theme.SURFACE_ALT,
        )
        self.progress_bar.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.progress_bar.set(0)

        # Progress details
        self.progress_label = ctk.CTkLabel(
            self.backup_right_frame, text="0 / 0 files processed (0%)", font=theme.FONT_BODY_BOLD
        )
        self.progress_label.grid(row=2, column=0, padx=16, pady=0, sticky="w")

        self.time_label = ctk.CTkLabel(
            self.backup_right_frame, text="Time elapsed: 00:00:00",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        )
        self.time_label.grid(row=3, column=0, padx=16, pady=(2, 12), sticky="w")

        # Log section
        log_frame = ctk.CTkFrame(self.backup_right_frame, fg_color=theme.SURFACE_ALT,
                                  corner_radius=theme.RADIUS_SM)
        log_frame.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        theme.section_label(log_frame, "Backup Log", font=theme.FONT_H2).grid(
            row=0, column=0, padx=12, pady=(10, 4), sticky="w"
        )

        self.log_text = ctk.CTkTextbox(
            log_frame, height=200, font=theme.FONT_MONO,
            fg_color=theme.SURFACE, corner_radius=theme.RADIUS_SM,
        )
        self.log_text.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.log_text.configure(state="disabled")

        # Link log_text to parent's log_text
        self.parent.log_text = self.log_text
        logger.info(f"log_text set to: {self.log_text}")

    def _get_selected_job(self, job_name):
        """Resolve the dropdown selection to a job by id, not by (reusable) name."""
        job_id = self.job_ids_by_name.get(job_name)
        if job_id is None:
            return None
        return self.db_session.get(self.parent.BackupJob, job_id)

    def on_job_selected(self, job_name):
        """Handle job selection from dropdown"""
        if job_name == "No jobs available":
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
        if not job:
            for label in self.job_details_labels[:4]:
                label.configure(text="-")
            theme.set_badge(self.job_details_labels[4], "-", kind="neutral")
            return

        # Update labels with job details
        self.job_details_labels[0].configure(text=job.name)
        self.job_details_labels[1].configure(text=job.source_path)
        self.job_details_labels[2].configure(text=job.destination_path)

        last_backup = "Never" if not job.last_backup else job.last_backup.strftime("%Y-%m-%d %H:%M")
        self.job_details_labels[3].configure(text=last_backup)

        if self.backup_engine.running:
            theme.set_badge(self.job_details_labels[4], "Running Backup", kind="info")
        elif self.backup_engine.paused:
            theme.set_badge(self.job_details_labels[4], "Paused", kind="warning")
        else:
            theme.set_badge(self.job_details_labels[4], "Ready", kind="success")

    def scan_job(self):
        """Scan the selected job for changes"""
        job_name = self.job_selection_var.get()
        if job_name == "No jobs available":
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
        if job_name == "No jobs available":
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
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

            self.log_message(f"Starting backup job: {job.name}")

            # Reset progress
            self.progress_bar.set(0)
            self.progress_label.configure(text="0 / 0 files processed (0%)")
            self.time_label.configure(text="Time elapsed: 00:00:00")

            # Update UI controls
            self._backup_active = True
            self.backup_button.configure(state="disabled")
            self.scan_button.configure(state="disabled")
            self.cancel_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)

            # Start the backup process
            success = self.backup_engine.run_backup_job(
                job.id,
                callback=self.backup_completed_callback
            )

            if not success:
                self.log_message("Failed to start backup")
                self._backup_active = False
                self.backup_button.configure(state="normal")
                self.scan_button.configure(state="normal")
                self.cancel_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

        except Exception as e:
            logger.error(f"Error starting backup: {e}")
            self.log_message(f"Error starting backup: {e}")
            self._backup_active = False
            self.backup_button.configure(state="normal")
            self.scan_button.configure(state="normal")
            self.cancel_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

    def backup_completed_callback(self, success, message):
        """Callback for when backup completes"""
        self.log_message(message)

        # Schedule UI updates on main thread
        def update_ui():
            # Update UI controls
            self._backup_active = False
            self.backup_button.configure(state="normal")
            self.scan_button.configure(state="normal")
            self.cancel_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

            # Reload job details
            job_name = self.job_selection_var.get()
            if job_name != "No jobs available":
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
                    text=f"{self.backup_engine.processed_files} / {self.backup_engine.total_files} "
                         f"files copied ({percent}%) — {self.backup_engine.scanned_files_count} scanned"
                )

                # Update time elapsed
                if self.backup_engine.start_time:
                    elapsed = time.time() - self.backup_engine.start_time
                    hours, remainder = divmod(int(elapsed), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.time_label.configure(
                        text=f"Time elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"
                    )

            # Update job status
            job_name = self.job_selection_var.get()
            if job_name != "No jobs available":
                theme.set_badge(self.job_details_labels[4], "Running Backup", kind="info")

        # Button state is owned explicitly by _backup_active, not inferred from
        # widget state or engine.running (which toggles between jobs in a batch
        # — see BatchJobsTab, which holds this flag for the whole batch).
        if self._backup_active:
            self.backup_button.configure(state="disabled")
            self.scan_button.configure(state="disabled")
            self.cancel_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)
        else:
            self.backup_button.configure(state="normal")
            self.scan_button.configure(state="normal")
            self.cancel_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)