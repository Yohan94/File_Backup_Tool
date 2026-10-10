import customtkinter as ctk
import logging
import threading
import time
import datetime
from ui.messagebox import CTkMessagebox

from ui import theme

# Configure logging
logger = logging.getLogger(__name__)


class BatchJobsTab:
    """UI for the Batch Jobs tab"""

    def __init__(self, parent, tab_view, db_session, backup_engine, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.backup_engine = backup_engine
        self.current_editing_batch_id = None
        self._batch_cancelled = threading.Event()
        self._last_job_succeeded = False

        # Store the session factory for creating new sessions in threads
        self.Session = session_factory

        # Setup the batch jobs tab UI
        self.setup_batch_jobs_tab(tab_view)

    def setup_batch_jobs_tab(self, tab_view):
        """Setup the batch jobs tab"""
        batch_tab = tab_view.tab("Batch Jobs")
        batch_tab.grid_columnconfigure(0, weight=5, uniform="batch")
        batch_tab.grid_columnconfigure(1, weight=6, uniform="batch")
        batch_tab.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------- left: batch list
        left_panel = theme.card(batch_tab)
        left_panel.grid(row=0, column=0, padx=(12, theme.GAP // 2), pady=12, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1)

        list_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        list_header.grid(row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 2), sticky="ew")
        list_header.grid_columnconfigure(0, weight=1)
        theme.section_label(list_header, "Your batches").grid(row=0, column=0, sticky="w")

        self.new_batch_button = theme.secondary_button(
            list_header, text="New batch", width=100, command=self.new_batch)
        self.new_batch_button.grid(row=0, column=1, sticky="e")

        theme.hint_label(left_panel, "Select a batch to edit or run it.").grid(
            row=1, column=0, padx=theme.PAD, pady=(0, 8), sticky="w")

        self.batch_list_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.batch_list_frame.grid(row=2, column=0, padx=(theme.PAD - 8, 8), pady=(0, 12), sticky="nsew")
        self.batch_list_frame.grid_columnconfigure(0, weight=1)
        self.batch_rows = {}

        # ------------------------------------------- right: selected batch
        right_panel = theme.card(batch_tab)
        right_panel.grid(row=0, column=1, padx=(theme.GAP // 2, 12), pady=12, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(7, weight=1)

        self.batch_form_title = theme.section_label(right_panel, "New batch")
        self.batch_form_title.grid(row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 14), sticky="w")

        # Name + description
        details = ctk.CTkFrame(right_panel, fg_color="transparent")
        details.grid(row=1, column=0, padx=theme.PAD, sticky="ew")
        details.grid_columnconfigure((0, 1), weight=1)

        theme.field_label(details, "Name").grid(row=0, column=0, padx=(0, 6), pady=(0, 4), sticky="w")
        theme.field_label(details, "Description (optional)").grid(
            row=0, column=1, padx=(6, 0), pady=(0, 4), sticky="w")

        self.batch_name_var = ctk.StringVar()
        batch_name_entry = theme.entry(details, textvariable=self.batch_name_var,
                                       placeholder_text="e.g. End of day")
        batch_name_entry.grid(row=1, column=0, padx=(0, 6), sticky="ew")
        batch_name_entry.bind("<Return>", lambda _e: self.save_batch())

        self.batch_description_var = ctk.StringVar()
        theme.entry(details, textvariable=self.batch_description_var).grid(
            row=1, column=1, padx=(6, 0), sticky="ew")

        # Save / delete
        form_buttons = ctk.CTkFrame(right_panel, fg_color="transparent")
        form_buttons.grid(row=2, column=0, padx=theme.PAD, pady=(12, 18), sticky="ew")
        form_buttons.grid_columnconfigure(1, weight=1)

        self.save_batch_button = theme.secondary_button(
            form_buttons, text="Create batch", width=130, command=self.save_batch)
        self.save_batch_button.grid(row=0, column=0, sticky="w")

        self.delete_batch_button = theme.danger_button(
            form_buttons, text="Delete batch", width=120, command=self.delete_batch)
        self.delete_batch_button.grid(row=0, column=2, sticky="e")

        ctk.CTkFrame(right_panel, fg_color=theme.LINE, height=1, corner_radius=0).grid(
            row=3, column=0, padx=theme.PAD, sticky="ew")

        # Jobs in the batch
        jobs_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        jobs_header.grid(row=4, column=0, padx=theme.PAD, pady=(16, 2), sticky="ew")
        jobs_header.grid_columnconfigure(0, weight=1)
        theme.section_label(jobs_header, "Jobs in this batch", font=theme.FONT_H2).grid(
            row=0, column=0, sticky="w")
        theme.hint_label(right_panel, "They run top to bottom. Switch one off to skip it.").grid(
            row=5, column=0, padx=theme.PAD, pady=(0, 10), sticky="w")

        # Add a job
        job_management_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        job_management_frame.grid(row=6, column=0, padx=theme.PAD, pady=(0, 8), sticky="ew")
        job_management_frame.grid_columnconfigure(0, weight=1)

        self.available_jobs_var = ctk.StringVar()
        self.available_jobs = theme.option_menu(
            job_management_frame, variable=self.available_jobs_var, values=["No jobs available"])
        self.available_jobs.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.add_job_to_batch_button = theme.secondary_button(
            job_management_frame, text="Add job", width=100, command=self.add_job_to_batch)
        self.add_job_to_batch_button.grid(row=0, column=1)

        self.batch_jobs_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.batch_jobs_frame.grid(row=7, column=0, padx=(theme.PAD - 8, 8), pady=(0, 8), sticky="nsew")
        self.batch_jobs_frame.grid_columnconfigure(0, weight=1)

        # Run / cancel: the page's primary action, anchored at the bottom
        run_bar = ctk.CTkFrame(right_panel, fg_color="transparent")
        run_bar.grid(row=8, column=0, padx=theme.PAD, pady=(4, theme.PAD), sticky="ew")
        run_bar.grid_columnconfigure(0, weight=1)

        self.run_batch_button = theme.primary_button(
            run_bar, text="Run this batch", command=self.run_selected_batch)
        self.run_batch_button.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.cancel_batch_button = theme.danger_button(
            run_bar, text="Stop batch", width=110, command=self.cancel_batch, state="disabled")
        self.cancel_batch_button.grid(row=0, column=1)
        theme.set_enabled(self.cancel_batch_button, False)

        # Initialize batch editing state
        self.load_batch_jobs()
        self.new_batch()

    def _highlight_editing_row(self):
        for batch_id, row in self.batch_rows.items():
            selected = batch_id == self.current_editing_batch_id
            theme.set_row_base(row, theme.RAISED_HOVER if selected else theme.RAISED)
            row.configure(border_width=1 if selected else 0, border_color=theme.LINE_STRONG)

    def _set_editing_state(self, editing, name=""):
        """Keep the form title and buttons in step with what's being edited."""
        self.batch_form_title.configure(text=f"Edit {name}" if editing else "New batch")
        self.save_batch_button.configure(text="Save changes" if editing else "Create batch")
        theme.set_enabled(self.delete_batch_button, editing)
        if not self.parent.backup_tab._backup_active:
            theme.set_enabled(self.run_batch_button, editing)
        self._highlight_editing_row()

    def new_batch(self):
        """Clear the batch form for a new batch"""
        self.current_editing_batch_id = None
        self.batch_name_var.set("")
        self.batch_description_var.set("")
        self._set_editing_state(False)

        # Clear the jobs in batch frame
        for widget in self.batch_jobs_frame.winfo_children():
            widget.destroy()
        theme.hint_label(self.batch_jobs_frame, "Create the batch first, then add jobs to it.").grid(
            row=0, column=0, padx=8, pady=10, sticky="w")

        # Update available jobs dropdown
        self.update_available_jobs_dropdown()

    def save_batch(self):
        """Save the current batch being edited"""
        name = self.batch_name_var.get().strip()
        description = self.batch_description_var.get().strip()

        if not name:
            self.parent.toast("Give the batch a name.", kind="error")
            return

        try:
            BatchJob = self.parent.BatchJob

            # Check uniqueness among active batches on both create and edit.
            clash = self.db_session.query(BatchJob).filter(
                BatchJob.name == name,
                BatchJob.is_active.is_(True),
                BatchJob.id != (self.current_editing_batch_id or -1),
            ).first()
            if clash:
                self.parent.toast(f"A batch named \"{name}\" already exists. Pick another name.", kind="error")
                return

            if self.current_editing_batch_id is not None:
                # Updating existing batch
                batch = self.db_session.get(BatchJob, self.current_editing_batch_id)
                if batch:
                    batch.name = name
                    batch.description = description
                    self.db_session.commit()
                    self.parent.toast("Changes saved")
            else:
                # Creating new batch
                batch = BatchJob(
                    name=name,
                    description=description,
                    created_date=datetime.datetime.now(),
                    is_active=True
                )
                self.db_session.add(batch)
                self.db_session.commit()
                self.current_editing_batch_id = batch.id
                self.parent.toast(f"Batch created: {name}. Now add jobs to it.")

            # Refresh the batch list
            self.load_batch_jobs()
            self._set_editing_state(True, name)
            self.load_jobs_in_batch(self.current_editing_batch_id)

        except Exception as e:
            logger.error(f"Error saving batch: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error saving batch: {str(e)}",
                icon="cancel"
            )

    def load_batch_jobs(self):
        """Load existing batch jobs from the database"""
        try:
            # Clear existing batch list
            for widget in self.batch_list_frame.winfo_children():
                widget.destroy()

            # Get all active batches
            BatchJob = self.parent.BatchJob
            batches = self.db_session.query(BatchJob).filter_by(is_active=True).all()

            self.batch_rows = {}
            if not batches:
                theme.hint_label(
                    self.batch_list_frame,
                    "No batches yet. A batch runs several jobs in a row, like an end-of-day backup.",
                    wraplength=300,
                ).grid(row=0, column=0, padx=8, pady=20, sticky="w")

            for i, batch in enumerate(batches):
                row = ctk.CTkFrame(self.batch_list_frame, fg_color=theme.RAISED,
                                   corner_radius=theme.RADIUS_SM)
                row.grid(row=i, column=0, padx=0, pady=4, sticky="ew")
                row.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(row, text=batch.name, font=theme.FONT_H2, anchor="w").grid(
                    row=0, column=0, padx=14, pady=(12, 0), sticky="w")

                if batch.description:
                    description = batch.description
                    if len(description) > 48:
                        description = description[:47] + "…"
                    theme.hint_label(row, description).grid(row=1, column=0, padx=14, sticky="w")

                last_run = ("Never run" if not batch.last_run
                            else f"Last run {batch.last_run:%d %b %Y, %H:%M}")
                theme.hint_label(row, last_run, text_color=theme.TEXT_FAINT).grid(
                    row=2, column=0, padx=14, pady=(0, 12), sticky="w")

                theme.make_clickable(row, lambda b=batch: self.edit_batch(b))
                self.batch_rows[batch.id] = row

            self._highlight_editing_row()

        except Exception as e:
            logger.error(f"Error loading batch jobs: {e}")
            self.parent.log_message(f"Error loading batch jobs: {e}")

    def edit_batch(self, batch):
        """Load a batch into the edit form"""
        self.current_editing_batch_id = batch.id
        self.batch_name_var.set(batch.name)
        self.batch_description_var.set(batch.description if batch.description else "")
        self._set_editing_state(True, batch.name)

        # Clear and reload the jobs in this batch
        self.load_jobs_in_batch(batch.id)

        # Update available jobs dropdown
        self.update_available_jobs_dropdown()

    def delete_batch(self):
        """Delete the current batch"""
        if self.current_editing_batch_id is None:
            return

        # Show confirmation dialog
        messagebox = CTkMessagebox(
            title="Confirm Deletion",
            message=f"Delete \"{self.batch_name_var.get()}\"? The jobs in it are kept.",
            icon="question",
            option_1="Cancel",
            option_2="Delete batch"
        )
        response = messagebox.get()

        if response == "Delete batch":
            try:
                BatchJob = self.parent.BatchJob
                batch = self.db_session.get(BatchJob, self.current_editing_batch_id)
                if batch:
                    # Mark as inactive instead of deleting permanently
                    batch.is_active = False
                    self.db_session.commit()

                    self.parent.toast(f"Batch deleted: {batch.name}")

                    # Refresh batch list and clear form
                    self.load_batch_jobs()
                    self.new_batch()

            except Exception as e:
                logger.error(f"Error deleting batch: {e}")
                CTkMessagebox(
                    title="Error",
                    message=f"Error deleting batch: {str(e)}",
                    icon="cancel"
                )

    def update_available_jobs_dropdown(self):
        """Update the available jobs dropdown with jobs not already in the batch"""
        try:
            # Get all active jobs
            BackupJob = self.parent.BackupJob
            BatchItem = self.parent.BatchItem
            all_jobs = self.db_session.query(BackupJob).filter_by(is_active=True).all()

            # If editing a batch, exclude jobs already in the batch
            jobs_in_batch = []
            if self.current_editing_batch_id is not None:
                batch_items = self.db_session.query(BatchItem).filter_by(
                    batch_id=self.current_editing_batch_id
                ).all()
                jobs_in_batch = [item.job_id for item in batch_items]

            # Filter jobs not in the batch
            available_jobs = [job for job in all_jobs if job.id not in jobs_in_batch]

            # Update dropdown
            if available_jobs:
                self.available_jobs.configure(values=[job.name for job in available_jobs])
                self.available_jobs_var.set(available_jobs[0].name)
                theme.set_enabled(self.add_job_to_batch_button, True)
            else:
                self.available_jobs.configure(values=["No jobs available"])
                self.available_jobs_var.set("No jobs available")
                theme.set_enabled(self.add_job_to_batch_button, False)

        except Exception as e:
            logger.error(f"Error updating available jobs: {e}")
            self.parent.log_message(f"Error updating available jobs: {e}")

    def add_job_to_batch(self):
        """Add the selected job to the current batch"""
        if self.current_editing_batch_id is None:
            self.parent.toast("Create the batch first, then add jobs to it.", kind="error")
            return

        job_name = self.available_jobs_var.get()
        if job_name == "No jobs available":
            return

        try:
            # Get the job
            BackupJob = self.parent.BackupJob
            BatchItem = self.parent.BatchItem

            job = self.db_session.query(BackupJob).filter_by(name=job_name).first()
            if not job:
                CTkMessagebox(
                    title="Error",
                    message="Job not found",
                    icon="cancel"
                )
                return

            # Get the highest order in the batch
            max_order = self.db_session.query(BatchItem).filter_by(
                batch_id=self.current_editing_batch_id
            ).count()

            # Add the job to the batch
            batch_item = BatchItem(
                batch_id=self.current_editing_batch_id,
                job_id=job.id,
                is_enabled=True,
                order=max_order
            )
            self.db_session.add(batch_item)
            self.db_session.commit()

            # Refresh jobs in batch
            self.load_jobs_in_batch(self.current_editing_batch_id)

            # Update available jobs
            self.update_available_jobs_dropdown()

        except Exception as e:
            logger.error(f"Error adding job to batch: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error adding job to batch: {str(e)}",
                icon="cancel"
            )

    def load_jobs_in_batch(self, batch_id):
        """Load jobs in the current batch"""
        try:
            # Clear existing jobs list
            for widget in self.batch_jobs_frame.winfo_children():
                widget.destroy()

            # Get batch items ordered by order field
            BatchItem = self.parent.BatchItem
            BackupJob = self.parent.BackupJob

            batch_items = self.db_session.query(BatchItem).filter_by(
                batch_id=batch_id
            ).order_by(BatchItem.order).all()

            if not batch_items:
                theme.hint_label(self.batch_jobs_frame,
                                 "No jobs yet. Pick one above and select Add job.").grid(
                    row=0, column=0, padx=8, pady=10, sticky="w"
                )
                return

            # Add jobs to the list. The number is real: it's the run order.
            for i, item in enumerate(batch_items):
                job = self.db_session.get(BackupJob, item.job_id)
                if not job:
                    continue
                job_frame = ctk.CTkFrame(self.batch_jobs_frame, fg_color=theme.RAISED,
                                         corner_radius=theme.RADIUS_SM)
                job_frame.grid(row=i, column=0, padx=0, pady=4, sticky="ew")
                job_frame.grid_columnconfigure(1, weight=1)

                name_color = theme.INK if item.is_enabled else theme.TEXT_FAINT
                ctk.CTkLabel(job_frame, text=f"{i + 1}", font=theme.FONT_H2, width=22,
                             text_color=theme.TEXT_FAINT).grid(
                    row=0, column=0, rowspan=2, padx=(12, 6), pady=10)

                ctk.CTkLabel(job_frame, text=job.name, font=theme.FONT_BODY_BOLD,
                             text_color=name_color, anchor="w").grid(
                    row=0, column=1, padx=4, pady=(10, 0), sticky="w")
                theme.hint_label(
                    job_frame,
                    theme.shorten_path(job.source_path, 36) if item.is_enabled else "Skipped when the batch runs",
                    font=theme.FONT_MONO if item.is_enabled else theme.FONT_SMALL,
                    text_color=theme.TEXT_MUTED if item.is_enabled else theme.TEXT_FAINT,
                ).grid(row=1, column=1, padx=4, pady=(0, 10), sticky="w")

                is_enabled_var = ctk.BooleanVar(value=item.is_enabled)
                ctk.CTkSwitch(
                    job_frame, text="", width=44, variable=is_enabled_var,
                    command=lambda v=is_enabled_var, item_id=item.id: self.toggle_job_enabled(item_id, v),
                ).grid(row=0, column=2, rowspan=2, padx=(6, 0), pady=10)

                small = dict(width=30, height=28, font=theme.FONT_SMALL_BOLD)
                theme.secondary_button(
                    job_frame, text="▲", **small,
                    command=lambda item_id=item.id: self.move_job_up(item_id),
                    state="disabled" if i == 0 else "normal",
                ).grid(row=0, column=3, rowspan=2, padx=(6, 2))
                theme.secondary_button(
                    job_frame, text="▼", **small,
                    command=lambda item_id=item.id: self.move_job_down(item_id),
                    state="disabled" if i == len(batch_items) - 1 else "normal",
                ).grid(row=0, column=4, rowspan=2, padx=2)
                theme.danger_button(
                    job_frame, text="✕", **small,
                    command=lambda item_id=item.id: self.remove_job_from_batch(item_id),
                ).grid(row=0, column=5, rowspan=2, padx=(2, 12))

        except Exception as e:
            logger.error(f"Error loading jobs in batch: {e}")
            self.parent.log_message(f"Error loading jobs in batch: {e}")

    def toggle_job_enabled(self, batch_item_id, is_enabled_var):
        """Toggle the enabled state of a job in a batch"""
        try:
            BatchItem = self.parent.BatchItem
            batch_item = self.db_session.get(BatchItem, batch_item_id)
            if batch_item:
                # Update the enabled state
                batch_item.is_enabled = is_enabled_var.get()
                self.db_session.commit()

                # Refresh jobs in batch to update toggle colors
                self.load_jobs_in_batch(self.current_editing_batch_id)

        except Exception as e:
            logger.error(f"Error toggling job enabled state: {e}")
            self.parent.log_message(f"Error toggling job enabled state: {e}")

    def remove_job_from_batch(self, batch_item_id):
        """Remove a job from the batch"""
        try:
            BatchItem = self.parent.BatchItem
            batch_item = self.db_session.get(BatchItem, batch_item_id)
            if batch_item:
                # Remove the batch item
                self.db_session.delete(batch_item)
                self.db_session.commit()

                # Reorder remaining items
                batch_items = self.db_session.query(BatchItem).filter_by(
                    batch_id=self.current_editing_batch_id
                ).order_by(BatchItem.order).all()

                for i, item in enumerate(batch_items):
                    item.order = i

                self.db_session.commit()

                # Refresh jobs in batch
                self.load_jobs_in_batch(self.current_editing_batch_id)

                # Update available jobs
                self.update_available_jobs_dropdown()

        except Exception as e:
            logger.error(f"Error removing job from batch: {e}")
            self.parent.log_message(f"Error removing job from batch: {e}")

    def move_job_up(self, batch_item_id):
        """Move a job up in the batch order"""
        try:
            # Get the batch item
            BatchItem = self.parent.BatchItem
            batch_item = self.db_session.get(BatchItem, batch_item_id)
            if not batch_item:
                return

            # Get the item above it
            above_item = self.db_session.query(BatchItem).filter_by(
                batch_id=self.current_editing_batch_id,
                order=batch_item.order - 1
            ).first()

            if above_item:
                # Swap orders
                above_item.order, batch_item.order = batch_item.order, above_item.order
                self.db_session.commit()

                # Refresh jobs in batch
                self.load_jobs_in_batch(self.current_editing_batch_id)

        except Exception as e:
            logger.error(f"Error moving job up: {e}")
            self.parent.log_message(f"Error moving job up: {e}")

    def move_job_down(self, batch_item_id):
        """Move a job down in the batch order"""
        try:
            # Get the batch item
            BatchItem = self.parent.BatchItem
            batch_item = self.db_session.get(BatchItem, batch_item_id)
            if not batch_item:
                return

            # Get the item below it
            below_item = self.db_session.query(BatchItem).filter_by(
                batch_id=self.current_editing_batch_id,
                order=batch_item.order + 1
            ).first()

            if below_item:
                # Swap orders
                below_item.order, batch_item.order = batch_item.order, below_item.order
                self.db_session.commit()

                # Refresh jobs in batch
                self.load_jobs_in_batch(self.current_editing_batch_id)

        except Exception as e:
            logger.error(f"Error moving job down: {e}")
            self.parent.log_message(f"Error moving job down: {e}")

    def run_selected_batch(self):
        """Run the currently selected batch"""
        if self.current_editing_batch_id is None:
            CTkMessagebox(
                title="Error",
                message="Please select a batch first",
                icon="cancel"
            )
            return

        if self.backup_engine.running:
            CTkMessagebox(
                title="Error",
                message="A backup is already running",
                icon="cancel"
            )
            return

        # Show confirmation dialog
        messagebox = CTkMessagebox(
            title="Confirm Batch Run",
            message=f"Run \"{self.batch_name_var.get()}\" now? Its jobs run one after another.",
            icon="question",
            option_1="Cancel",
            option_2="Run"
        )
        response = messagebox.get()

        if response == "Run":
            try:
                # Get enabled batch items ordered by order field
                BatchItem = self.parent.BatchItem
                BatchJob = self.parent.BatchJob

                batch_items = self.db_session.query(BatchItem).filter_by(
                    batch_id=self.current_editing_batch_id,
                    is_enabled=True
                ).order_by(BatchItem.order).all()

                if not batch_items:
                    CTkMessagebox(
                        title="Error",
                        message="No enabled jobs in this batch",
                        icon="cancel"
                    )
                    return

                # Resolve everything we need to primitives before crossing the
                # thread boundary — ORM objects belong to this (main) thread's session.
                job_ids = [item.job_id for item in batch_items]
                batch_id = self.current_editing_batch_id
                batch = self.db_session.get(BatchJob, batch_id)

                self._start_job_run(job_ids, batch_id, f"Starting batch job: {batch.name}")

            except Exception as e:
                logger.error(f"Error starting batch: {e}")
                self.parent.log_message(f"Error starting batch: {e}")

    def run_all_jobs(self):
        """Run every active backup job once, back to back — the Jobs tab's
        Run All button wires straight into this so a one-off "run everything"
        doesn't require first grouping jobs into a saved batch."""
        if self.backup_engine.running:
            CTkMessagebox(
                title="Error",
                message="A backup is already running",
                icon="cancel"
            )
            return

        BackupJob = self.parent.BackupJob
        jobs = self.db_session.query(BackupJob).filter_by(is_active=True).order_by(BackupJob.name).all()

        if not jobs:
            CTkMessagebox(
                title="Error",
                message="No backup jobs to run",
                icon="cancel"
            )
            return

        messagebox = CTkMessagebox(
            title="Confirm Run All",
            message=f"Run all {len(jobs)} backup job(s) now?",
            icon="question",
            option_1="Cancel",
            option_2="Run"
        )
        response = messagebox.get()

        if response == "Run":
            try:
                job_ids = [job.id for job in jobs]
                self._start_job_run(job_ids, None, f"Starting all jobs ({len(jobs)} total)")
            except Exception as e:
                logger.error(f"Error starting run-all: {e}")
                self.parent.log_message(f"Error starting run-all: {e}")

    def _start_job_run(self, job_ids, batch_id, start_message):
        """Kick off a sequential run of job_ids on a worker thread.

        batch_id is the BatchJob to stamp last_run on, or None for an ad hoc
        run (e.g. Run All) that isn't tied to a saved batch.
        """
        # Switch to Backup tab to show progress
        self.parent.show_page("Backup")

        # Clear the log
        self.parent.backup_tab.clear_log()

        self.parent.log_message(start_message)

        self._batch_cancelled.clear()
        theme.set_enabled(self.run_batch_button, False)
        theme.set_enabled(self.cancel_batch_button, True)
        # Held for the whole run — Start/Scan on the Backup tab must
        # stay disabled between jobs, not just during each individual job.
        self.parent.backup_tab._backup_active = True

        threading.Thread(
            target=self._run_batch_thread,
            args=(job_ids, batch_id),
            daemon=True
        ).start()

    def cancel_batch(self):
        """Cancel the batch after the currently running job finishes"""
        self._batch_cancelled.set()
        self.backup_engine.cancel_backup()
        self.parent.log_message("Cancelling batch after the current job...")

    def _run_batch_thread(self, job_ids, batch_id):
        """Run batch jobs in a separate thread"""
        # Create a new session for this thread
        session = self.Session()

        try:
            total_jobs = len(job_ids)
            successful_jobs = 0
            failed_jobs = 0

            batch_start_time = time.time()

            BackupJob = self.parent.BackupJob
            BatchJob = self.parent.BatchJob

            for i, job_id in enumerate(job_ids):
                if self._batch_cancelled.is_set():
                    self.parent.log_message(f"Run cancelled before job {i + 1}/{total_jobs}")
                    break

                job = session.get(BackupJob, job_id)
                job_name = job.name if job else f"Job ID {job_id}"

                self.parent.log_message(f"Running job {i + 1}/{total_jobs}: {job_name}")

                # Update progress display (schedule on main thread)
                def update_progress(index=i, total=total_jobs):
                    backup_tab = self.parent.backup_tab
                    backup_tab.progress_bar.set(index / total)
                    backup_tab.progress_label.configure(text=f"Job {index + 1} of {total}")

                self.parent.post_to_ui(update_progress)

                job_done = threading.Event()

                def on_done(success, message, idx=i):
                    self._batch_job_completed_callback(success, message, idx, total_jobs)
                    job_done.set()

                # Run the backup job
                started = self.backup_engine.run_backup_job(job_id, callback=on_done)
                if not started:
                    failed_jobs += 1
                    continue

                job_done.wait()  # set by the callback, no polling
                if self._last_job_succeeded:
                    successful_jobs += 1
                else:
                    failed_jobs += 1

            # Update batch last run time (skipped for an ad hoc run-all, which
            # has no batch_id)
            if batch_id is not None:
                batch_obj = session.get(BatchJob, batch_id)
                if batch_obj:
                    batch_obj.last_run = datetime.datetime.now()
                    session.commit()

            # Calculate total time
            total_time = time.time() - batch_start_time
            hours, remainder = divmod(int(total_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Log completion
            self.parent.log_message(f"Run completed: {successful_jobs} successful, {failed_jobs} failed")
            self.parent.log_message(f"Total time: {time_str}")

            # Update progress to complete (schedule on main thread)
            def update_ui():
                backup_tab = self.parent.backup_tab
                backup_tab.progress_bar.set(1.0)
                backup_tab.progress_label.configure(text=f"Finished: {successful_jobs} of {total_jobs} jobs succeeded")
                backup_tab._backup_active = False
                theme.set_enabled(self.run_batch_button, self.current_editing_batch_id is not None)
                theme.set_enabled(self.cancel_batch_button, False)
                self.parent.toast(f"Run finished: {successful_jobs} of {total_jobs} jobs succeeded",
                                  kind="success" if failed_jobs == 0 else "error")
                # Refresh batch list
                self.load_batch_jobs()

            self.parent.post_to_ui(update_ui)

        except Exception as e:
            logger.error(f"Error in batch thread: {e}")
            self.parent.log_message(f"Error in batch: {e}")

            def reset_buttons():
                self.parent.backup_tab._backup_active = False
                theme.set_enabled(self.run_batch_button, self.current_editing_batch_id is not None)
                theme.set_enabled(self.cancel_batch_button, False)

            self.parent.post_to_ui(reset_buttons)
        finally:
            session.close()

    def _batch_job_completed_callback(self, success, message, job_index, total_jobs):
        """Callback for when a job in a batch completes"""
        self._last_job_succeeded = success
        self.parent.log_message(message)

        # Update progress for the current job (schedule on main thread)
        def update_progress():
            backup_tab = self.parent.backup_tab
            progress = (job_index + 1) / total_jobs
            backup_tab.progress_bar.set(progress)
            backup_tab.progress_label.configure(text=f"Job {job_index + 1} of {total_jobs} finished")

        self.parent.post_to_ui(update_progress)