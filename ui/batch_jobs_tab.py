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

        # Create frames
        batch_tab.grid_columnconfigure(0, weight=1)
        batch_tab.grid_rowconfigure(0, weight=1)

        # Create main frame with two panels
        main_frame = ctk.CTkFrame(batch_tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Left panel - Batch list and management
        left_panel = theme.card(main_frame)
        left_panel.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")

        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        # Batch management buttons
        batch_controls = ctk.CTkFrame(left_panel, fg_color="transparent")
        batch_controls.grid(row=0, column=0, padx=6, pady=(6, 6), sticky="new")

        batch_controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Batch list header
        theme.section_label(batch_controls, "Batch Jobs").grid(
            row=0, column=0, columnspan=4, padx=10, pady=(10, 16), sticky="w"
        )

        # Batch controls
        self.new_batch_button = theme.secondary_button(
            batch_controls,
            text="New Batch",
            command=self.new_batch
        )
        self.new_batch_button.grid(row=1, column=0, padx=4, pady=5, sticky="ew")

        self.run_batch_button = theme.primary_button(
            batch_controls,
            text="Run Selected",
            command=self.run_selected_batch
        )
        self.run_batch_button.grid(row=1, column=1, padx=4, pady=5, sticky="ew")

        self.delete_batch_button = theme.danger_button(
            batch_controls,
            text="Delete",
            command=self.delete_batch,
        )
        self.delete_batch_button.grid(row=1, column=2, padx=4, pady=5, sticky="ew")

        self.cancel_batch_button = theme.secondary_button(
            batch_controls,
            text="Cancel Batch",
            command=self.cancel_batch,
            state="disabled",
        )
        self.cancel_batch_button.grid(row=1, column=3, padx=4, pady=5, sticky="ew")

        # Batch list
        self.batch_list_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.batch_list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.batch_list_frame.grid_columnconfigure(0, weight=1)

        # Right panel - Batch details and job management
        right_panel = theme.card(main_frame)
        right_panel.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")

        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=0)
        right_panel.grid_rowconfigure(1, weight=0)
        right_panel.grid_rowconfigure(2, weight=0)
        right_panel.grid_rowconfigure(3, weight=1)

        # Batch details section
        batch_details_frame = ctk.CTkFrame(right_panel, fg_color=theme.SURFACE_ALT,
                                            corner_radius=theme.RADIUS_SM)
        batch_details_frame.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="new")

        batch_details_frame.grid_columnconfigure(1, weight=1)

        # Batch name
        ctk.CTkLabel(batch_details_frame, text="Batch Name", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        self.batch_name_var = ctk.StringVar()
        batch_name_entry = ctk.CTkEntry(
            batch_details_frame,
            textvariable=self.batch_name_var,
            width=250,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
        )
        batch_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Batch description
        ctk.CTkLabel(batch_details_frame, text="Description", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )

        self.batch_description_var = ctk.StringVar()
        batch_description_entry = ctk.CTkEntry(
            batch_details_frame,
            textvariable=self.batch_description_var,
            width=250,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
        )
        batch_description_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Save batch button
        self.save_batch_button = theme.primary_button(
            batch_details_frame,
            text="Save Batch",
            command=self.save_batch
        )
        self.save_batch_button.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="e")

        # Job management section
        job_management_frame = ctk.CTkFrame(right_panel, fg_color=theme.SURFACE_ALT,
                                             corner_radius=theme.RADIUS_SM)
        job_management_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="new")

        job_management_frame.grid_columnconfigure(0, weight=1)
        job_management_frame.grid_columnconfigure(1, weight=1)

        # Available jobs
        ctk.CTkLabel(job_management_frame, text="Available Jobs", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=0, column=0, padx=10, pady=(10, 4), sticky="w"
        )

        self.available_jobs_var = ctk.StringVar()
        self.available_jobs = ctk.CTkOptionMenu(
            job_management_frame,
            variable=self.available_jobs_var,
            values=["No jobs available"],
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            dropdown_fg_color=theme.SURFACE,
            corner_radius=theme.RADIUS_SM,
        )
        self.available_jobs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Add job button
        self.add_job_to_batch_button = theme.primary_button(
            job_management_frame,
            text="Add to Batch →",
            command=self.add_job_to_batch
        )
        self.add_job_to_batch_button.grid(row=1, column=1, padx=10, pady=(0, 10))

        # Batch jobs list section
        theme.section_label(right_panel, "Jobs in this Batch", font=theme.FONT_H2).grid(
            row=2, column=0, padx=12, pady=(4, 5), sticky="nw"
        )

        self.batch_jobs_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.batch_jobs_frame.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.batch_jobs_frame.grid_columnconfigure(0, weight=1)

        # Initialize batch editing state
        self.load_batch_jobs()
        self.new_batch()

    def new_batch(self):
        """Clear the batch form for a new batch"""
        self.current_editing_batch_id = None
        self.batch_name_var.set("")
        self.batch_description_var.set("")
        self.save_batch_button.configure(text="Create Batch")
        self.delete_batch_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

        # Clear the jobs in batch frame
        for widget in self.batch_jobs_frame.winfo_children():
            widget.destroy()

        # Update available jobs dropdown
        self.update_available_jobs_dropdown()

    def save_batch(self):
        """Save the current batch being edited"""
        name = self.batch_name_var.get().strip()
        description = self.batch_description_var.get().strip()

        if not name:
            CTkMessagebox(
                title="Error",
                message="Batch name is required",
                icon="cancel"
            )
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
                CTkMessagebox(
                    title="Error",
                    message="An active batch with this name already exists",
                    icon="cancel"
                )
                return

            if self.current_editing_batch_id is not None:
                # Updating existing batch
                batch = self.db_session.get(BatchJob, self.current_editing_batch_id)
                if batch:
                    batch.name = name
                    batch.description = description
                    self.db_session.commit()
                    CTkMessagebox(
                        title="Success",
                        message="Batch updated successfully",
                        icon="check"
                    )
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
                self.save_batch_button.configure(text="Update Batch")
                self.delete_batch_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)

                CTkMessagebox(
                    title="Success",
                    message="Batch created successfully",
                    icon="check"
                )

            # Refresh the batch list
            self.load_batch_jobs()

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

            # Add batches to the batch list
            if not batches:
                ctk.CTkLabel(
                    self.batch_list_frame, text="No batches yet — create one above.",
                    font=theme.FONT_BODY, text_color=theme.TEXT_MUTED,
                ).grid(row=0, column=0, padx=10, pady=20, sticky="w")

            for i, batch in enumerate(batches):
                batch_frame = ctk.CTkFrame(self.batch_list_frame, fg_color=theme.SURFACE_ALT,
                                            corner_radius=theme.RADIUS_SM)
                batch_frame.grid(row=i, column=0, padx=6, pady=6, sticky="ew")
                batch_frame.grid_columnconfigure(0, weight=1)

                # Batch Name
                ctk.CTkLabel(batch_frame, text=batch.name, font=theme.FONT_H2).grid(
                    row=0, column=0, padx=12, pady=(10, 4), sticky="w"
                )

                # Batch Description
                description_text = batch.description if batch.description else "No description"
                if len(description_text) > 40:
                    description_text = description_text[:37] + "..."
                ctk.CTkLabel(batch_frame, text=description_text, font=theme.FONT_SMALL,
                             text_color=theme.TEXT_MUTED).grid(
                    row=1, column=0, padx=12, pady=0, sticky="w"
                )

                # Last Run
                last_run = "Never" if not batch.last_run else batch.last_run.strftime("%Y-%m-%d %H:%M")
                ctk.CTkLabel(batch_frame, text=f"Last Run: {last_run}", font=theme.FONT_SMALL,
                             text_color=theme.TEXT_MUTED).grid(
                    row=2, column=0, padx=12, pady=(0, 10), sticky="w"
                )

                # Edit button
                edit_button = theme.secondary_button(
                    batch_frame,
                    text="Edit",
                    width=60,
                    command=lambda b=batch: self.edit_batch(b)
                )
                edit_button.grid(row=0, column=1, rowspan=3, padx=12, pady=10)

        except Exception as e:
            logger.error(f"Error loading batch jobs: {e}")
            self.parent.log_message(f"Error loading batch jobs: {e}")

    def edit_batch(self, batch):
        """Load a batch into the edit form"""
        self.current_editing_batch_id = batch.id
        self.batch_name_var.set(batch.name)
        self.batch_description_var.set(batch.description if batch.description else "")
        self.save_batch_button.configure(text="Update Batch")
        self.delete_batch_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)

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
            message="Are you sure you want to delete this batch?",
            icon="question",
            option_1="Cancel",
            option_2="Delete"
        )
        response = messagebox.get()

        if response == "Delete":
            try:
                BatchJob = self.parent.BatchJob
                batch = self.db_session.get(BatchJob, self.current_editing_batch_id)
                if batch:
                    # Mark as inactive instead of deleting permanently
                    batch.is_active = False
                    self.db_session.commit()

                    CTkMessagebox(
                        title="Success",
                        message="Batch deleted successfully",
                        icon="check"
                    )

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
                self.add_job_to_batch_button.configure(state="normal")
            else:
                self.available_jobs.configure(values=["No jobs available"])
                self.available_jobs_var.set("No jobs available")
                self.add_job_to_batch_button.configure(state="disabled")

        except Exception as e:
            logger.error(f"Error updating available jobs: {e}")
            self.parent.log_message(f"Error updating available jobs: {e}")

    def add_job_to_batch(self):
        """Add the selected job to the current batch"""
        if self.current_editing_batch_id is None:
            CTkMessagebox(
                title="Error",
                message="Please create or select a batch first",
                icon="cancel"
            )
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
                ctk.CTkLabel(self.batch_jobs_frame, text="No jobs in this batch",
                             font=theme.FONT_BODY, text_color=theme.TEXT_MUTED).grid(
                    row=0, column=0, padx=10, pady=10, sticky="w"
                )
                return

            # Add jobs to the list
            for i, item in enumerate(batch_items):
                job = self.db_session.get(BackupJob, item.job_id)
                if job:
                    job_frame = ctk.CTkFrame(self.batch_jobs_frame, fg_color=theme.SURFACE_ALT,
                                              corner_radius=theme.RADIUS_SM)
                    job_frame.grid(row=i, column=0, padx=6, pady=6, sticky="ew")
                    job_frame.grid_columnconfigure(1, weight=1)

                    # Job order indicator
                    order_label = ctk.CTkLabel(job_frame, text=f"{i + 1}.", font=theme.FONT_H2,
                                                text_color=theme.TEXT_MUTED)
                    order_label.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=10)

                    # Job Name
                    ctk.CTkLabel(job_frame, text=job.name, font=theme.FONT_BODY_BOLD).grid(
                        row=0, column=1, padx=5, pady=(10, 0), sticky="w"
                    )

                    # Source Path
                    source_text = f"Source: {job.source_path}"
                    if len(source_text) > 40:
                        source_text = source_text[:37] + "..."
                    ctk.CTkLabel(job_frame, text=source_text, font=theme.FONT_SMALL,
                                 text_color=theme.TEXT_MUTED).grid(
                        row=1, column=1, padx=5, pady=(0, 10), sticky="w"
                    )

                    # Enable/Disable toggle
                    is_enabled_var = ctk.BooleanVar(value=item.is_enabled)
                    toggle_switch = ctk.CTkSwitch(
                        job_frame,
                        text="",
                        variable=is_enabled_var,
                        command=lambda v=is_enabled_var, item_id=item.id: self.toggle_job_enabled(item_id, v),
                        progress_color=theme.SUCCESS if item.is_enabled else theme.DANGER,
                        button_color=theme.SUCCESS_HOVER if item.is_enabled else theme.DANGER_HOVER,
                    )
                    toggle_switch.grid(row=0, column=2, rowspan=2, padx=10, pady=10)

                    # Remove button
                    remove_button = theme.danger_button(
                        job_frame,
                        text="×",
                        width=30,
                        command=lambda item_id=item.id: self.remove_job_from_batch(item_id),
                    )
                    remove_button.grid(row=0, column=3, rowspan=2, padx=5, pady=10)

                    # Move up/down buttons
                    move_frame = ctk.CTkFrame(job_frame, fg_color="transparent")
                    move_frame.grid(row=0, column=4, rowspan=2, padx=5, pady=10)

                    up_button = theme.secondary_button(
                        move_frame,
                        text="▲",
                        width=30,
                        command=lambda item_id=item.id: self.move_job_up(item_id),
                        state="disabled" if i == 0 else "normal"
                    )
                    up_button.grid(row=0, column=0, padx=2, pady=2)

                    down_button = theme.secondary_button(
                        move_frame,
                        text="▼",
                        width=30,
                        command=lambda item_id=item.id: self.move_job_down(item_id),
                        state="disabled" if i == len(batch_items) - 1 else "normal"
                    )
                    down_button.grid(row=1, column=0, padx=2, pady=2)

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
            message="Are you sure you want to run this batch?",
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
        self.parent.tab_view.set("Backup")

        # Clear the log
        self.parent.backup_tab.log_text.configure(state="normal")
        self.parent.backup_tab.log_text.delete("1.0", "end")
        self.parent.backup_tab.log_text.configure(state="disabled")

        self.parent.log_message(start_message)

        self._batch_cancelled.clear()
        self.run_batch_button.configure(state="disabled")
        self.cancel_batch_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)
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
                    backup_tab.progress_label.configure(text=f"Job {index + 1} / {total}")

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
                backup_tab.progress_label.configure(text=f"Run completed: {successful_jobs}/{total_jobs} jobs successful")
                backup_tab._backup_active = False
                self.run_batch_button.configure(state="normal")
                self.cancel_batch_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)
                # Refresh batch list
                self.load_batch_jobs()

            self.parent.post_to_ui(update_ui)

        except Exception as e:
            logger.error(f"Error in batch thread: {e}")
            self.parent.log_message(f"Error in batch: {e}")

            def reset_buttons():
                self.parent.backup_tab._backup_active = False
                self.run_batch_button.configure(state="normal")
                self.cancel_batch_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

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
            backup_tab.progress_label.configure(text=f"Job {job_index + 1} / {total_jobs} completed")

        self.parent.post_to_ui(update_progress)