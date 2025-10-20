"""
Import and Generate Combined Screen - Upload files and generate planning in one view
Combines file upload functionality with planning generation interface
"""

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import sys
import os
from pathlib import Path
import pandas as pd
import threading
from datetime import datetime
import logging
import traceback

# Import database operations
try:
    # Try absolute import first (for PyInstaller)
    from src.db.db_operations import DatabaseManager, import_excel_data_to_db
    from src.decision_support import DecisionSupportSystem
    HAS_DATABASE = True
except ImportError:
    try:
        # Add parent directories to path for imports (development mode)
        current_dir = os.path.dirname(__file__)
        parent_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
        src_dir = os.path.join(parent_dir, 'src')
        db_dir = os.path.join(src_dir, 'db')
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        if db_dir not in sys.path:
            sys.path.insert(0, db_dir)
        
        from db_operations import DatabaseManager, import_excel_data_to_db
        from decision_support import DecisionSupportSystem
        HAS_DATABASE = True
    except ImportError as e:
        HAS_DATABASE = False
        print(f"⚠️  Database integration not available: {e}")

# Import file validator
try:
    # Try absolute import first
    from screens.file_validator import FileValidator
    HAS_VALIDATOR = True
except Exception:
    try:
        # Try direct import (if screens is in path)
        from file_validator import FileValidator
        HAS_VALIDATOR = True
    except Exception:
        HAS_VALIDATOR = False
        print("Warning: File validator not available")

# Import backend modules
try:
    # Try absolute import first (for PyInstaller)
    from src.exam_scheduler import generate_enhanced_planning
    from src.exam_scheduler_db import generate_planning_from_db
    HAS_SCHEDULER = True
except Exception:
    try:
        # Add src to path and import
        current_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        src_dir = os.path.join(project_root, 'src')
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        
        from exam_scheduler import generate_enhanced_planning
        from exam_scheduler_db import generate_planning_from_db
        HAS_SCHEDULER = True
    except Exception as e:
        HAS_SCHEDULER = False
        print(f"Warning: Scheduler not available: {e}")


class ImportAndGenerateScreen(ctk.CTkFrame):
    """Combined screen for importing files and generating planning"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # File paths storage
        self.file_paths = {
            'teachers': None,
            'slots': None,
            'preferences': None
        }
        
        # Configuration state - store all parameter widgets
        self.config_widgets = {}
        self.config_defaults = {}  # Store default values for reset
        
        # Use app-level generation state for persistence across screen switches
        if not hasattr(self.app, 'generation_state'):
            self.app.generation_state = {
                'is_generating': False,
                'generation_thread': None,
                'generation_progress': 0,
                'cancel_requested': False
            }
        
        # Base directory (robust for both development and PyInstaller bundles)
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            self.base_dir = Path(sys.executable).parent
        else:
            # Running in development mode
            self.base_dir = Path(__file__).resolve().parents[2]

        # Setup logger for this module (logs to base_dir/app.log)
        try:
            log_file = self.base_dir / 'app.log'
            self.logger = logging.getLogger('ISIApp')
            if not self.logger.handlers:
                fh = logging.FileHandler(str(log_file), encoding='utf-8')
                formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
                self.logger.setLevel(logging.DEBUG)
            self.logger.debug(f'ImportAndGenerateScreen initialized, base_dir={self.base_dir}')
        except Exception as e:
            # If logging fails, fallback to print
            print(f'Warning: could not initialize logger: {e}')

        # Database connection
        if HAS_DATABASE:
            db_path = self.base_dir / "planning.db"
            try:
                self.db = DatabaseManager(str(db_path))
            except Exception as e:
                print(f"⚠️  Could not initialize DatabaseManager: {e}")
                self.db = None
            self.current_session_id = None
        else:
            self.db = None
        self.teachers_file = self.base_dir / "resources" / "Enseignants.xlsx"
        self.voeux_file = self.base_dir / "resources" / "Souhaits.xlsx"
        self.slots_file = self.base_dir / "resources" / "Repartitions.xlsx"
        
        # Restore previously imported files from app state
        self.restore_imported_files()
        
        # Initialize quota choice flag (default: use auto-adjusted quotas)
        self.use_custom_quotas_flag = False
        
        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Content
        self.grid_columnconfigure(0, weight=1)
        
        self.create_header()
        self.create_content_area()
        
        # Restore generation UI if generation is in progress
        self.after(100, self.check_generation_status)
    
    def check_generation_status(self):
        """Check if generation is in progress and restore UI accordingly"""
        if self.app.generation_state['is_generating']:
            # Restore generation UI
            self.show_loading_ui()
            self.animate_spinner()
            # Update progress display
            progress = self.app.generation_state['generation_progress']
            status = getattr(self.app, 'generation_status', 'Génération en cours...')
            self.update_progress(progress, status)
    
    # Helper properties for cleaner code
    @property
    def is_generating(self):
        return self.app.generation_state['is_generating']
    
    @is_generating.setter
    def is_generating(self, value):
        self.app.generation_state['is_generating'] = value
    
    @property
    def cancel_requested(self):
        return self.app.generation_state['cancel_requested']
    
    @cancel_requested.setter
    def cancel_requested(self, value):
        self.app.generation_state['cancel_requested'] = value
    
    @property
    def generation_progress(self):
        return self.app.generation_state['generation_progress']
    
    @generation_progress.setter
    def generation_progress(self, value):
        self.app.generation_state['generation_progress'] = value
    
    @property
    def generation_thread(self):
        return self.app.generation_state['generation_thread']
    
    @generation_thread.setter
    def generation_thread(self, value):
        self.app.generation_state['generation_thread'] = value
    
    def restore_imported_files(self):
        """Restore previously imported files from app state"""
        if hasattr(self.app, 'imported_files'):
            for file_type, path in self.app.imported_files.items():
                if path:
                    self.file_paths[file_type] = path
    
    def update_app_file_state(self):
        """Update app state with current file paths"""
        self.app.imported_files = self.file_paths.copy()
    
    def create_header(self):
        """Create page header with step indicator"""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(15, 5))
        
        # Modern step indicator - Step 1 (Import & Générer)
        try:
            # Try absolute import first
            from widgets.step_indicator import StepIndicator
        except ImportError:
            try:
                # Try with tkinter_isi prefix
                from tkinter_isi.widgets.step_indicator import StepIndicator
            except ImportError:
                # Fallback: add widgets dir to path
                widgets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'widgets')
                if widgets_dir not in sys.path:
                    sys.path.insert(0, widgets_dir)
                from step_indicator import StepIndicator
        
        step_indicator = StepIndicator(header_frame, current_step=1, colors=self.colors)
        step_indicator.pack(fill="x")
    
    def create_content_area(self):
        """Create main content area with two columns"""
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=30, pady=(10, 40))
        
        # Configure grid - two columns: left for upload, right for config
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)  # Left column (upload)
        content_frame.grid_columnconfigure(1, weight=1)  # Right column (config)
        
        # Left column - Upload files
        self.create_upload_section(content_frame)
        
        # Right column - Configuration
        self.create_configuration_section(content_frame)
    
    def create_upload_section(self, parent):
        """Create file upload section on the left matching reference image"""
        upload_frame = ctk.CTkFrame(parent, fg_color="transparent")
        upload_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        upload_frame.grid_propagate(False)  # Prevent frame from resizing
        
        # Upload card with border and fixed width
        upload_card = ctk.CTkFrame(
            upload_frame,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        upload_card.pack(fill="both", expand=True)
        upload_card.pack_propagate(True)  # Allow internal content to flow
        
        # Drag and drop zone - increased height
        drop_zone = ctk.CTkFrame(
            upload_card,
            fg_color=self.colors['background'],
            corner_radius=12,
            border_width=2,
            border_color=self.colors['border'],
            height=300.0
        )
        drop_zone.pack(fill="x", padx=30, pady=(25, 20))
        drop_zone.pack_propagate(False)
        
        # Upload icon
        upload_icon = ctk.CTkLabel(
            drop_zone,
            text="☁️",
            font=("Segoe UI", 50),
            text_color=self.colors['text_secondary']
        )
        upload_icon.place(relx=0.5, rely=0.40, anchor="center")
        
        # Upload text
        upload_text = ctk.CTkLabel(
            drop_zone,
            text="Choisissez un fichier ou glissez‑déposez",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary']
        )
        upload_text.place(relx=0.5, rely=0.58, anchor="center")
        
        # Format info
        format_left = ctk.CTkLabel(
            drop_zone,
            text="Supported formats : XLSX",
            font=("Segoe UI", 9),
            text_color=self.colors['text_secondary']
        )
        format_left.place(relx=0.5, rely=0.70, anchor="center")
        
        # Make drop zone clickable to browse all files
        drop_zone.bind("<Button-1>", lambda e: self.browse_multiple_files())
        upload_icon.bind("<Button-1>", lambda e: self.browse_multiple_files())
        upload_text.bind("<Button-1>", lambda e: self.browse_multiple_files())
        format_left.bind("<Button-1>", lambda e: self.browse_multiple_files())
        
        # Add hover effect
        def on_enter(e):
            drop_zone.configure(border_color=self.colors['primary'])
        def on_leave(e):
            drop_zone.configure(border_color=self.colors['border'])
        
        drop_zone.bind("<Enter>", on_enter)
        drop_zone.bind("<Leave>", on_leave)
        upload_icon.bind("<Enter>", on_enter)
        upload_icon.bind("<Leave>", on_leave)
        upload_text.bind("<Enter>", on_enter)
        upload_text.bind("<Leave>", on_leave)
        format_left.bind("<Enter>", on_enter)
        format_left.bind("<Leave>", on_leave)
        
        # Enable drag-and-drop
        dnd_enabled = False
        try:
            from tkinterdnd2 import DND_FILES
            drop_zone.drop_target_register(DND_FILES)
            drop_zone.dnd_bind('<<Drop>>', self.handle_drop)
            drop_zone.dnd_bind('<<DragEnter>>', lambda e: drop_zone.configure(border_color=self.colors['primary']))
            drop_zone.dnd_bind('<<DragLeave>>', lambda e: drop_zone.configure(border_color=self.colors['border']))
            dnd_enabled = True
            print("Drag-and-drop enabled successfully!")
        except (ImportError, Exception) as e:
            # TkinterDnD not available or not properly configured
            print(f"⚠️  Drag-and-drop not available: {e}")
            pass
        
        # Update text based on drag-and-drop availability
        if not dnd_enabled:
            upload_text.configure(text="Click here to choose files")
        
        # Store drop_zone reference for later
        self.drop_zone = drop_zone
        
        # File upload items list
        self.create_file_upload_items(upload_card)
        
        # Clear button at bottom
        clear_btn = ctk.CTkButton(
            upload_card,
            text="Retirer les fichiers",
            width=100,
            height=38,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['background'],
            font=("Segoe UI", 11),
            command=self.clear_all
        )
        clear_btn.pack(padx=30, pady=(15, 25), anchor="w")
    
    def create_file_upload_items(self, parent):
        """Create individual file upload items"""
        # Container for upload items
        items_container = ctk.CTkFrame(parent, fg_color="transparent")
        items_container.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        # File types - Initial state shows placeholders
        file_types = [
            {
                "icon": "📄",
                "label": "liste des enseignants",
                "file_type": "teachers",
                "status": "en attente"
            },
            {
                "icon": "📄",
                "label": "liste descréneaux de surveillance",
                "file_type": "slots",
                "status": "en attente"
            },
            {
                "icon": "📄",
                "label": "Liste des vœux des enseignants",
                "file_type": "preferences",
                "status": "en attente"
            }
        ]
        
        self.upload_items = {}
        for data in file_types:
            item_frame = self.create_upload_item(items_container, data)
            item_frame.pack(fill="x", pady=8)
            self.upload_items[data['file_type']] = item_frame
        
        # Restore UI state for previously imported files
        self.restore_ui_state()
        
        # Update button state after restoring files
        self.after(100, self.update_generate_button_state)
    
    def create_upload_item(self, parent, data):
        """Create a single upload item row with modern status display"""
        # Main container with fixed height
        item = ctk.CTkFrame(parent, fg_color=self.colors['background'], corner_radius=8, height=56)
        item.pack_propagate(False)  # Maintain fixed height
        
        # Left side - Icon and file name only
        left_frame = ctk.CTkFrame(item, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True, padx=15, pady=0)
        left_frame.pack_propagate(False)
        
        # Content row - Icon + Filename
        content_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        content_row.place(relx=0, rely=0.5, anchor="w")
        
        # Icon
        icon_label = ctk.CTkLabel(
            content_row,
            text=data['icon'],
            font=("Segoe UI", 20)
        )
        icon_label.pack(side="left", padx=(0, 12))
        
        # File name
        name_label = ctk.CTkLabel(
            content_row,
            text=data['label'],
            font=("Segoe UI", 12, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        name_label.pack(side="left")
        
        # Right side - Status badge + Action button
        right_frame = ctk.CTkFrame(item, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=0)
        
        # Status badge (small, modern pill)
        status_badge = ctk.CTkFrame(
            right_frame,
            fg_color=self.colors['border'],
            corner_radius=10,
            height=20
        )
        status_badge.pack(side="left", padx=(0, 12))
        
        status_label = ctk.CTkLabel(
            status_badge,
            text="Pending",
            font=("Segoe UI", 9, "bold"),
            text_color=self.colors['text_secondary']
        )
        status_label.pack(padx=8, pady=2)
        
        # Action button with fixed size
        action_btn = ctk.CTkButton(
            right_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="transparent",
            hover_color=self.colors['hover'],
            text_color=self.colors['text_primary'],
            font=("Segoe UI", 16),
            command=lambda ft=data['file_type']: self.browse_file(ft)
        )
        action_btn.pack(side="left")
        
        # Store references
        item.icon_label = icon_label
        item.name_label = name_label
        item.status_badge = status_badge
        item.status_label = status_label
        item.action_btn = action_btn
        item.file_type = data['file_type']
        
        # Make item clickable to browse
        for widget in [item, left_frame, content_row]:
            widget.bind("<Button-1>", lambda e, ft=data['file_type']: self.browse_file(ft))
        
        return item
    
    def restore_ui_state(self):
        """Restore UI state for previously imported files"""
        for file_type, path in self.file_paths.items():
            if path and Path(path).exists():
                self.update_upload_item_status(file_type, "complete", Path(path).name)
    
    def create_configuration_section(self, parent):
        """Create configuration section on the right with fixed button"""
        config_frame = ctk.CTkFrame(parent, fg_color="transparent")
        config_frame.grid(row=0, column=1, sticky="nsew", padx=(15, 0))
        
        # Configure grid for fixed button at bottom
        config_frame.grid_rowconfigure(0, weight=1)  # Scrollable content
        config_frame.grid_rowconfigure(1, weight=0)  # Fixed button
        config_frame.grid_columnconfigure(0, weight=1)
        
        # Configuration card (scrollable) with title inside
        config_card = ctk.CTkScrollableFrame(
            config_frame,
            fg_color=self.colors['surface'],
            corner_radius=12
        )
        config_card.grid(row=0, column=0, sticky="nsew")
        
        # Configuration title inside the card
        config_title = ctk.CTkLabel(
            config_card,
            text="Configurations",
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        config_title.pack(fill="x", padx=20, pady=(20, 15))
        
        # Configuration sliders for all roles
        self.create_config_sliders(config_card)
        
        # Generate button frame (fixed at bottom, outside scrollable area)
        button_frame = ctk.CTkFrame(config_frame, fg_color=self.colors['surface'], corner_radius=12)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(15, 0))
        
        # Generate button with loading spinner
        self.create_generate_button_section(button_frame)
    
    def create_config_sliders(self, parent):
        """Create configuration sliders for all roles
        UPDATED quotas (October 2025)
        """
        # First: Supervisors per room configuration (minimum 2, max 4)
        self.create_slider_field(
            parent, 
            "Surveillant par salle", 
            "Nombre de surveillant requis par salle (minimum 2)", 
            2, 4, 2,
            "supervisors_per_room"
        )
        
        # UPDATED role quotas from official requirements
        roles_config = [
            ("Professeurs (PR)", "Nombre minimum de créneaux", 4, "quota_PR"),
            ("Maîtres de Conférences (MC)", "Nombre minimum de créneaux", 4, "quota_MC"),
            ("Maîtres Assistants (MA)", "Nombre minimum de créneaux", 7, "quota_MA"),
            ("Assistants (AS)", "Nombre minimum de créneaux", 8, "quota_AS"),
            ("Assistants Contractuels (AC)", "Nombre minimum de créneaux", 9, "quota_AC"),
            ("Professeurs Tronc Commun (PTC)", "Nombre minimum de créneaux", 9, "quota_PTC"),
            ("Professeurs d'Enseignement Secondaire (PES)", "Nombre minimum de créneaux", 9, "quota_PES"),
            ("Experts (EX)", "Nombre minimum de créneaux", 3, "quota_EX"),
            ("Vacataires (V)", "Nombre minimum de créneaux", 4, "quota_V"),
        ]
        
        for label, desc, default, key in roles_config:
            self.create_slider_field(parent, label, desc, 0, 15, default, key)
    
    def create_slider_field(self, parent, label, description, min_val, max_val, default, key):
        """Create a slider input field"""
        container = ctk.CTkFrame(parent, fg_color=self.colors['background'], corner_radius=8)
        container.pack(fill="x", padx=20, pady=6)
        
        # Label row with value
        label_frame = ctk.CTkFrame(container, fg_color="transparent")
        label_frame.pack(fill="x", padx=15, pady=(12, 5))
        
        title_label = ctk.CTkLabel(
            label_frame,
            text=label,
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        title_label.pack(side="left")
        
        # Value badge
        value_badge = ctk.CTkFrame(
            label_frame,
            fg_color=self.colors['primary'],
            corner_radius=12,
            width=40,
            height=24
        )
        value_badge.pack(side="right")
        value_badge.pack_propagate(False)
        
        value_label = ctk.CTkLabel(
            value_badge,
            text=str(default),
            font=("Segoe UI", 11, "bold"),
            text_color="white"
        )
        value_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Description
        desc_label = ctk.CTkLabel(
            container,
            text=description,
            font=("Segoe UI", 9),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        desc_label.pack(fill="x", padx=15, pady=(0, 5))
        
        # Slider
        slider = ctk.CTkSlider(
            container,
            from_=min_val,
            to=max_val,
            number_of_steps=max_val - min_val,
            command=lambda v: value_label.configure(text=f"{int(v)}")
        )
        slider.set(default)
        slider.pack(fill="x", padx=15, pady=(0, 12))
        
        # Store widget, value label, and default value for later retrieval
        self.config_widgets[key] = {
            'slider': slider,
            'label': value_label
        }
        self.config_defaults[key] = default
    
    def create_generate_button_section(self, parent):
        """Create generate button with loading spinner - compact version"""
        button_container = ctk.CTkFrame(parent, fg_color="transparent")
        button_container.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Button row frame
        button_row = ctk.CTkFrame(button_container, fg_color="transparent")
        button_row.pack(fill="x")
        
        # Reset button (on the left)
        self.reset_btn = ctk.CTkButton(
            button_row,
            text="↺ Réinitialiser",
            height=45,
            width=100,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            hover_color=self.colors['hover'],
            text_color=self.colors['text_primary'],
            font=("Segoe UI", 13),
            command=self.reset_configuration
        )
        self.reset_btn.pack(side="left", padx=(0, 10))
        
        # Generate button (on the right, initially disabled)
        # Removed analyze button - analysis now shows when Generate is clicked
        self.generate_btn = ctk.CTkButton(
            button_row,
            text="Générer le Planning",
            height=45,
            corner_radius=8,
            state="disabled",  # Initially disabled
            fg_color=self.colors['border'],  # Gray when disabled
            hover_color=self.colors['border'],
            font=("Segoe UI", 15, "bold"),
            command=self.start_generation
        )
        self.generate_btn.pack(side="left", fill="x", expand=True)
        
        # Loading spinner and progress (shown below button during generation)
        self.loading_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        
        # Compact progress display
        progress_row = ctk.CTkFrame(self.loading_frame, fg_color="transparent")
        progress_row.pack(pady=(10, 0))
        
        # Spinner label (smaller)
        self.spinner_label = ctk.CTkLabel(
            progress_row,
            text="⏳",
            font=("Segoe UI", 20),
            text_color=self.colors['primary']
        )
        self.spinner_label.pack(side="left", padx=(0, 10))
        
        # Progress percentage
        self.progress_percentage = ctk.CTkLabel(
            progress_row,
            text="0%",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['primary']
        )
        self.progress_percentage.pack(side="left", padx=(0, 10))
        
        # Status message
        self.progress_status = ctk.CTkLabel(
            self.loading_frame,
            text="Préparation...",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary']
        )
        self.progress_status.pack(pady=(5, 0))
        
        # Cancel button (shown during generation)
        self.cancel_btn = ctk.CTkButton(
            self.loading_frame,
            text="Annuler",
            font=("Segoe UI", 12, "bold"),
            fg_color="#DC3545",
            hover_color="#C82333",
            height=36,
            corner_radius=8,
            command=self.cancel_generation
        )
        self.cancel_btn.pack(fill="x", pady=(10, 0))
    
    def browse_file(self, file_type):
        """Open file browser dialog"""
        filename = filedialog.askopenfilename(
            title=f"Sélectionner le fichier {file_type}",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            # Check if slot already has a file
            if self.file_paths[file_type] is not None:
                # Ask for confirmation to replace
                file_type_names = {
                    'teachers': 'enseignants',
                    'slots': 'souhaits',
                    'preferences': 'créneaux'
                }
                friendly_name = file_type_names.get(file_type, file_type)
                
                result = messagebox.askyesno(
                    "Fichier déjà importé",
                    f"Un fichier {friendly_name} est déjà importé.\n\n"
                    f"Voulez-vous le remplacer par le nouveau fichier ?\n\n"
                    f"Ancien : {Path(self.file_paths[file_type]).name}\n"
                    f"Nouveau : {Path(filename).name}"
                )
                
                if not result:
                    return  # User chose not to replace
            
            self.file_paths[file_type] = filename
            self.update_app_file_state()
            
            # Update UI to show loading
            self.update_upload_item_status(file_type, "uploading", Path(filename).name)
            
            # Validate file
            self.validate_file(file_type, filename)
    
    def browse_multiple_files(self):
        """Open file browser to select multiple files"""
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les fichiers",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filenames:
            # Process files without limit
            self.process_uploaded_files(list(filenames))
    
    def handle_drop(self, event):
        """Handle drag-and-drop of files"""
        # Parse dropped files
        files = event.data
        
        # Handle different formats of dropped data
        if isinstance(files, str):
            # Split by spaces but handle paths with spaces
            import re
            files = re.findall(r'\{[^}]+\}|[^\s]+', files)
            files = [f.strip('{}') for f in files]
        
        # Filter for XLSX files only
        xlsx_files = [f for f in files if f.lower().endswith(('.xlsx', '.xls'))]
        
        if not xlsx_files:
            messagebox.showerror(
                "Format invalide",
                "Veuillez déposer uniquement des fichiers XLSX."
            )
            return
        
        # Reset border color
        if hasattr(self, 'drop_zone'):
            self.drop_zone.configure(border_color=self.colors['border'])
        
        # Process files without limit
        self.process_uploaded_files(xlsx_files)
    
    def process_uploaded_files(self, files):
        """Process uploaded files and match them to correct types by structure"""
        matched = {
            'teachers': None,
            'slots': None,
            'preferences': None
        }
        unmatched = []
        
        for filename in files:
            file_type = self.identify_file_type(filename)
            
            if file_type:
                matched[file_type] = filename
            else:
                unmatched.append(Path(filename).name)
        
        # Show message for unmatched files
        if unmatched:
            messagebox.showwarning(
                "Fichiers non reconnus",
                f"Les fichiers suivants n'ont pas pu être identifiés par leur structure:\n\n" +
                "\n".join(f"• {name}" for name in unmatched) +
                "\n\nVeuillez vérifier la structure des fichiers."
            )
        
        # Check for files that would replace existing ones
        files_to_replace = {}
        for file_type, filename in matched.items():
            if filename and self.file_paths[file_type] is not None:
                files_to_replace[file_type] = filename
        
        # If there are files to replace, ask for confirmation
        if files_to_replace:
            file_type_names = {
                'teachers': 'enseignants',
                'slots': 'souhaits',
                'preferences': 'créneaux'
            }
            
            replace_messages = []
            for file_type, new_file in files_to_replace.items():
                friendly_name = file_type_names.get(file_type, file_type)
                replace_messages.append(
                    f"• {friendly_name.capitalize()}\n"
                    f"  Ancien : {Path(self.file_paths[file_type]).name}\n"
                    f"  Nouveau : {Path(new_file).name}"
                )
            
            result = messagebox.askyesno(
                "Remplacer les fichiers existants ?",
                f"Les fichiers suivants sont déjà importés :\n\n" +
                "\n\n".join(replace_messages) +
                "\n\nVoulez-vous les remplacer par les nouveaux fichiers ?"
            )
            
            if not result:
                # User chose not to replace, remove these from matched
                for file_type in files_to_replace.keys():
                    matched[file_type] = None
        
        # Upload matched files (only those not removed by user choice)
        for file_type, filename in matched.items():
            if filename:
                self.file_paths[file_type] = filename
                self.update_app_file_state()
                self.update_upload_item_status(file_type, "uploading", Path(filename).name)
                self.validate_file(file_type, filename)
    
    def identify_file_type(self, filename):
        """Identify file type by checking its structure (exact column names)
        UPDATED for new file format (October 2025)
        """
        try:
            df = pd.read_excel(filename, nrows=1)  # Read only first row for speed
            columns = [col.lower().strip() for col in df.columns]
            columns_str = ' '.join(columns)
            
            # NEW FORMAT - Teachers file: nom_ens, prenom_ens, abrv_ens, email_ens, grade_code_ens, code_smartex_ens, participe_surveillance
            if all(keyword in columns_str for keyword in ['nom_ens', 'prenom_ens', 'grade_code_ens', 'code_smartex_ens']):
                return 'teachers'
            
            # NEW FORMAT - Preferences/Souhaits file: Enseignant, Semestre, Session, Jour, Séances
            elif all(keyword in columns_str for keyword in ['enseignant', 'semestre', 'session', 'jour', 'séances']):
                return 'preferences'
            
            # NEW FORMAT - Slots/Repartitions file: dateExam, h_debut, h_fin, session, type ex, semestre, enseignant, cod_salle
            elif all(keyword in columns_str for keyword in ['dateexam', 'h_debut', 'h_fin', 'cod_salle']):
                return 'slots'
            
            # Try to match by filename as fallback
            name_lower = Path(filename).name.lower()
            if 'enseignant' in name_lower or 'teacher' in name_lower:
                return 'teachers'
            elif 'souhait' in name_lower or 'voeux' in name_lower:
                return 'preferences'
            elif 'creneau' in name_lower or 'slot' in name_lower or 'repartition' in name_lower:
                return 'slots'
            
            return None
            
        except Exception as e:
            print(f"Error identifying file {filename}: {e}")
            return None
    
    def validate_file(self, file_type, filename):
        """Validate uploaded file"""
        # Map UI file types to validator file types
        validator_type_map = {
            'teachers': 'teachers',
            'slots': 'slots',
            'preferences': 'voeux'
        }
        validator_file_type = validator_type_map.get(file_type, file_type)
        
        if HAS_VALIDATOR:
            is_valid, errors, file_info = FileValidator.validate_file(filename, validator_file_type)
            
            if is_valid:
                self.update_upload_item_status(file_type, "complete", Path(filename).name)
                self.app.update_status(f"Fichier validé: {file_info.get('rows', 0)} lignes")
                
                # Import into database if session exists
                self.import_file_to_database(file_type, filename)
            else:
                self.update_upload_item_status(file_type, "failed", Path(filename).name)
                messagebox.showerror("Fichier invalide", "Structure du fichier incorrecte.")
                self.file_paths[file_type] = None
                self.update_app_file_state()
        else:
            # No validator, just check if readable
            try:
                df = pd.read_excel(filename)
                self.update_upload_item_status(file_type, "complete", Path(filename).name)
                
                # Import into database if session exists
                self.import_file_to_database(file_type, filename)
            except Exception:
                self.update_upload_item_status(file_type, "failed", Path(filename).name)
                messagebox.showerror("Erreur", "Impossible de lire le fichier.")
                self.file_paths[file_type] = None
                self.update_app_file_state()
        
        # Update generate button state
        self.update_generate_button_state()
    
    def import_file_to_database(self, file_type, filename):
        """Import validated file data into database"""
        # Only import if we have database support and an active session
        if not HAS_DATABASE or not self.db:
            return
        
        if not hasattr(self.app, 'current_session_id') or self.app.current_session_id is None:
            return
        
        try:
            import pandas as pd
            
            # Read the file
            df = pd.read_excel(filename)
            
            if file_type == 'teachers':
                # Import teachers
                count = self.db.import_teachers_from_excel(self.app.current_session_id, df)
                print(f"Imported {count} teachers to database")
                
                # If all files are now available, import everything
                self.import_all_if_ready()
                
            elif file_type == 'preferences':
                # Mark that preferences are available
                print("Preferences file ready")
                # If all files are now available, import everything
                self.import_all_if_ready()
                    
            elif file_type == 'slots':
                # Mark that slots are available
                print("Slots file ready")
                # If all files are now available, import everything
                self.import_all_if_ready()
                
        except Exception as e:
            print(f"⚠️ Error importing {file_type} to database: {e}")
            import traceback
            traceback.print_exc()
    
    def import_all_if_ready(self):
        """Import all data to database if all three files are available"""
        # Check if all files are uploaded
        if not all([
            self.file_paths.get('teachers'),
            self.file_paths.get('preferences'),
            self.file_paths.get('slots')
        ]):
            print("⏳ Waiting for all files before importing to database...")
            return
        
        # Only import if we have database support and an active session
        if not HAS_DATABASE or not self.db:
            return
        
        if not hasattr(self.app, 'current_session_id') or self.app.current_session_id is None:
            return
        
        try:
            print("\n🔄 All files available - importing to database...")
            
            # Get database path
            db_path = str(self.base_dir / "planning.db")
            
            # Use import_excel_data_to_db which handles all files
            result = import_excel_data_to_db(
                self.app.current_session_id,
                self.file_paths['teachers'],
                self.file_paths['preferences'],
                self.file_paths['slots'],
                db_path
            )
            
            print(f"All data successfully imported to database!")
            print(f"   • Teachers: {result['teachers_imported']}")
            print(f"   • Voeux: {result['voeux_imported']}")
            print(f"   • Slots: {result['slots_imported']}")
            
        except Exception as e:
            print(f"⚠️ Error importing all data to database: {e}")
            import traceback
            traceback.print_exc()
    
    def truncate_filename(self, filename, max_length=30):
        """Truncate long filenames with ellipsis"""
        if len(filename) <= max_length:
            return filename
        
        # Keep extension visible
        name, ext = os.path.splitext(filename)
        if len(ext) > 10:  # Very long extension, just truncate
            return filename[:max_length-3] + "..."
        
        # Calculate how much of the name we can keep
        available = max_length - len(ext) - 3  # -3 for "..."
        if available <= 0:
            return filename[:max_length-3] + "..."
        
        return name[:available] + "..." + ext
    
    def update_upload_item_status(self, file_type, status, filename):
        """Update upload item visual status with modern badges"""
        if file_type not in self.upload_items:
            return
        
        item = self.upload_items[file_type]
        
        # Truncate filename for display
        display_name = self.truncate_filename(filename)
        
        if status == "uploading":
            item.name_label.configure(text=display_name)
            item.icon_label.configure(text="🔄")
            # Update status badge to "Validating"
            item.status_badge.configure(fg_color=self.colors['accent'])
            item.status_label.configure(text="Validating", text_color="white")
            # Keep action button as browse during validation
            item.action_btn.configure(
                text="",
                command=lambda ft=file_type: self.browse_file(ft)
            )
        elif status == "complete":
            item.name_label.configure(text=display_name)
            item.icon_label.configure(text="")
            # Update status badge to "Ready"
            item.status_badge.configure(fg_color=self.colors['success'])
            item.status_label.configure(text="Ready", text_color="white")
            # Change action button to delete
            item.action_btn.configure(
                text="🗑️",
                command=lambda ft=file_type: self.clear_file(ft)
            )
        elif status == "failed":
            item.name_label.configure(text=display_name)
            item.icon_label.configure(text="")
            # Update status badge to "Error"
            item.status_badge.configure(fg_color=self.colors['error'])
            item.status_label.configure(text="Error", text_color="white")
            # Change action button to retry
            item.action_btn.configure(
                text="🔄",
                command=lambda ft=file_type: self.browse_file(ft)
            )
    
    def clear_file(self, file_type):
        """Clear a specific file"""
        self.file_paths[file_type] = None
        self.update_app_file_state()
        
        # Reset to default placeholder state
        file_labels = {
            'teachers': 'enseignant.xlsx',
            'slots': 'creneaux.xlsx',
            'preferences': 'souhaites.xlsx'
        }
        
        if file_type in self.upload_items:
            item = self.upload_items[file_type]
            item.name_label.configure(text=file_labels[file_type])
            item.icon_label.configure(text="📄")
            # Reset status badge to "Pending"
            item.status_badge.configure(fg_color=self.colors['border'])
            item.status_label.configure(text="Pending", text_color=self.colors['text_secondary'])
            # Reset action button to browse
            item.action_btn.configure(
                text="",
                command=lambda ft=file_type: self.browse_file(ft)
            )
        
        # Update generate button state
        self.update_generate_button_state()
    
    def clear_all(self):
        """Clear all files"""
        for file_type in self.file_paths.keys():
            self.clear_file(file_type)
    
    def update_generate_button_state(self):
        """Enable generate button only when all 3 files are uploaded correctly"""
        all_files_uploaded = all(path is not None for path in self.file_paths.values())
        
        if all_files_uploaded:
            # Enable button - make it bright
            self.generate_btn.configure(
                state="normal",
                fg_color=self.colors['primary'],
                hover_color="#6D28D9"
            )
        else:
            # Disable button - make it gray
            self.generate_btn.configure(
                state="disabled",
                fg_color=self.colors['border'],
                hover_color=self.colors['border']
            )
    
    def reset_configuration(self):
        """Reset all configuration sliders to their default values"""
        for key, widget_dict in self.config_widgets.items():
            if key in self.config_defaults:
                default_val = self.config_defaults[key]
                widget_dict['slider'].set(default_val)
                widget_dict['label'].configure(text=str(int(default_val)))
        
        # Show confirmation message
        messagebox.showinfo("Reset", "Configuration réinitialisée aux valeurs par défaut")
    
    def start_generation(self):
        """Start the planning generation process - shows analysis modal first"""
        if self.is_generating:
            messagebox.showwarning("En cours", "Génération déjà en cours...")
            return
        
        # Validate that all files are uploaded
        if not all(self.file_paths.values()):
            messagebox.showerror(
                "Fichiers manquants",
                "Veuillez télécharger les 3 fichiers requis."
            )
            return
        
        # Show analysis modal ONLY - generation will be triggered by button clicks in modal
        # Do not start generation here
        if HAS_DATABASE and hasattr(self.app, 'current_session_id') and self.app.current_session_id:
            try:
                self.show_feasibility_analysis()
            except Exception as e:
                print(f"Warning: Could not show feasibility analysis: {e}")
                messagebox.showerror("Erreur", f"Erreur lors de l'analyse:\n{str(e)}")
    
    def _start_generation_after_analysis(self):
        """Actually start generation after user has made quota choice in analysis modal"""
        # Clear any old planning state to ensure fresh load from database
        if hasattr(self.app, 'loaded_planning_state'):
            self.app.loaded_planning_state = None
            print("🗑️  Cleared old planning state")
        
        # Get configuration
        config = self.get_configuration()
        
        # Reset cancellation flag
        self.cancel_requested = False
        
        # Show loading UI
        self.show_loading_ui()
        
        self.is_generating = True
        self.generation_progress = 0
        self.app.update_status("Génération du planning en cours...")
        
        # Start generation in background thread
        self.generation_thread = threading.Thread(
            target=self.run_generation_thread,
            args=(config,),
            daemon=True
        )
        self.generation_thread.start()
        
        # Start spinner animation
        self.animate_spinner()
    
    
    
    
    def show_loading_ui(self):
        """Show loading spinner below button (keep button visible)"""
        self.loading_frame.pack(fill="x", pady=(10, 0))
        # Disable button during generation
        self.generate_btn.configure(state="disabled", fg_color=self.colors['border'])
    
    def hide_loading_ui(self):
        """Hide loading spinner and re-enable button"""
        self.loading_frame.pack_forget()
        # Re-enable button
        self.generate_btn.configure(state="normal", fg_color=self.colors['primary'])
    
    def cancel_generation(self):
        """Cancel the ongoing generation process"""
        if not self.is_generating:
            return
        
        # Confirm cancellation
        result = messagebox.askyesno(
            "Annuler la génération",
            "Êtes-vous sûr de vouloir annuler la génération du planning?\n\n"
            "Toute progression sera perdue."
        )
        
        if not result:
            return
        
        # Set cancellation flag
        self.cancel_requested = True
        self.update_progress(0, "Annulation en cours...")
        
        # Stop generation
        self.is_generating = False
        
        # Hide loading UI
        self.hide_loading_ui()
        
        # Clear any partial outputs
        self.cleanup_partial_results()
        
        # Reset status
        self.app.update_status("Génération annulée")
        
        messagebox.showinfo(
            "Annulation",
            "La génération a été annulée avec succès."
        )
    
    def cleanup_partial_results(self):
        """Remove any partial results from cancelled generation"""
        try:
            # Check for recent output files that might be incomplete
            output_dir = self.base_dir / "output"
            if output_dir.exists():
                # Get files modified in the last minute (likely from cancelled generation)
                import time
                current_time = time.time()
                for file_path in output_dir.glob("planning_*"):
                    if file_path.is_file():
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age < 60:  # Less than 1 minute old
                            try:
                                file_path.unlink()
                            except:
                                pass
        except Exception as e:
            print(f"Warning: Could not cleanup partial results: {e}")
    
    def animate_spinner(self):
        """Animate the loading spinner"""
        if not self.is_generating:
            return
        
        spinner_chars = ["⏳", "⌛", "⏳", "⌛"]
        current_char = self.spinner_label.cget("text")
        try:
            current_index = spinner_chars.index(current_char)
            next_index = (current_index + 1) % len(spinner_chars)
        except ValueError:
            next_index = 0
        
        self.spinner_label.configure(text=spinner_chars[next_index])
        self.after(300, self.animate_spinner)
    
    def update_progress(self, percentage, status_text):
        """Update progress percentage and status"""
        self.generation_progress = percentage
        self.app.generation_status = status_text  # Store in app for persistence
        self.progress_percentage.configure(text=f"{int(percentage * 100)}%")
        self.progress_status.configure(text=status_text)
    
    def get_configuration(self):
        """Get current configuration from UI widgets
        UPDATED for new quotas (October 2025)
        """
        config = {}
        
        # Get quotas for all role types (removed VA, it's same as V)
        quotas = {}
        role_keys = ['PR', 'MC', 'MA', 'AS', 'AC', 'PTC', 'PES', 'EX', 'V']
        
        for grade_key in role_keys:
            widget_key = f'quota_{grade_key}'
            if widget_key in self.config_widgets:
                quotas[grade_key] = int(self.config_widgets[widget_key]['slider'].get())
            else:
                # Default values for roles without widgets (backward compatibility)
                default_quotas = {
                    'PR': 4, 'MC': 4, 'MA': 7, 'AS': 8, 'AC': 9,
                    'PTC': 9, 'PES': 9, 'EX': 3, 'V': 4
                }
                quotas[grade_key] = default_quotas.get(grade_key, 5)
        
        config['quotas'] = quotas
        
        # Get other parameters
        if 'supervisors_per_room' in self.config_widgets:
            config['supervisors_per_room'] = int(self.config_widgets['supervisors_per_room']['slider'].get())
        
        # Set defaults for parameters not in UI
        config['compactness_weight'] = 10
        config['gap_penalty_weight'] = 50
        config['max_sessions_per_day'] = 4  # Changed from 3 to 4 to allow more flexibility
        config['max_solve_time'] = 60.0
        
        return config
    
    def run_generation_thread(self, config):
        """Run the actual generation in a background thread"""
        # Top-level error handler to catch ANY exception
        try:
            self._run_generation_thread_impl(config)
        except Exception as e:
            # Catch absolutely everything and log it
            error_msg = str(e)
            try:
                tb = traceback.format_exc()
                if hasattr(self, 'logger') and self.logger:
                    self.logger.critical('CRITICAL ERROR in generation thread: %s', error_msg)
                    self.logger.critical(tb)
                else:
                    print(f"CRITICAL ERROR: {error_msg}")
                    print(tb)
                
                # Write to a fallback file if logger failed
                try:
                    with open('generation_error.log', 'w', encoding='utf-8') as f:
                        f.write(f"Error: {error_msg}\n\n")
                        f.write(tb)
                except:
                    pass
            except:
                pass
            
            # Show error to user
            self.after(0, lambda: self.update_progress(0, f"ERROR: {error_msg}"))
            self.after(0, lambda: messagebox.showerror("Erreur Critique", f"Erreur lors de la génération:\n{error_msg}\n\nVeuillez consulter generation_error.log"))
        finally:
            self.is_generating = False
            self.after(0, self.hide_loading_ui)
    
    def _run_generation_thread_impl(self, config):
        """Internal implementation of generation thread"""
        try:
            start_time = datetime.now()
            
            # Update progress - Loading data
            self.after(0, lambda: self.update_progress(0.1, "Chargement des fichiers..."))
            
            # Check for cancellation
            if self.cancel_requested:
                self.cancel_requested = False
                return
            
            # Use the imported file paths
            teachers_file = self.file_paths['teachers']
            slots_file = self.file_paths['slots']
            preferences_file = self.file_paths['preferences']
            
            # Check if scheduler is available
            if not HAS_SCHEDULER:
                raise Exception("Le module de planification n'est pas disponible. Veuillez vérifier l'installation.")
            
            # Check if we should use database-integrated scheduler
            use_db_scheduler = (HAS_DATABASE and self.db and 
                              hasattr(self.app, 'current_session_id') and 
                              self.app.current_session_id is not None)
            
            # Initialize satisfaction_report
            satisfaction_report = None
            
            if use_db_scheduler:
                self.after(0, lambda: self.update_progress(0.2, "Génération depuis la base de données..."))
                
                # Check for cancellation
                if self.cancel_requested:
                    self.cancel_requested = False
                    return
                
                self.after(0, lambda: self.update_progress(0.3, "Lecture des données..."))
                
                # Check if user wants to use custom quotas
                use_custom = getattr(self, 'use_custom_quotas_flag', False)
                
                # Use database-integrated scheduler
                result = generate_planning_from_db(
                    session_id=self.app.current_session_id,
                    db_path=str(self.base_dir / "planning.db"),
                    supervisors_per_room=config.get('supervisors_per_room', 2),
                    max_sessions_per_day=config.get('max_sessions_per_day', 3),
                    max_solve_time=config.get('max_solve_time', 60.0),
                    use_custom_quotas=use_custom,
                    custom_quotas=config.get('quotas') if use_custom else None
                )
                
                # Check if generation was successful
                if result is None:
                    raise Exception("La génération a échoué. Veuillez vérifier les logs pour plus de détails.")
                
                # Unpack the result
                assignments, teachers_df, slot_info, satisfaction_report = result
                
                self.after(0, lambda: self.update_progress(0.6, "Calcul des affectations..."))
                
                # For database mode, set empty defaults for file-based parameters
                responsible_schedule = []
                all_teachers_lookup = None
                
            else:
                # Use file-based scheduler
                self.after(0, lambda: self.update_progress(0.2, "Configuration du modèle..."))
                
                # Check for cancellation
                if self.cancel_requested:
                    self.cancel_requested = False
                    return
                
                self.after(0, lambda: self.update_progress(0.25, "Analyse des enseignants..."))
                
                # Import the satisfaction analysis function
                from exam_scheduler import analyze_teacher_satisfaction
                
                self.after(0, lambda: self.update_progress(0.35, "🔍 Analyse des préférences..."))
                
                result = generate_enhanced_planning(
                    teachers_file,
                    preferences_file,
                    slots_file,
                    supervisors_per_room=config.get('supervisors_per_room', 2),
                    compactness_weight=config.get('compactness_weight', 10),
                    gap_penalty_weight=config.get('gap_penalty_weight', 50),
                    max_sessions_per_day=config.get('max_sessions_per_day', 3),
                    max_solve_time=config.get('max_solve_time', 60.0)
                )
                
                # Check if generation was successful
                if result is None:
                    raise Exception("La génération a échoué. Veuillez vérifier les logs pour plus de détails.")
                
                # Unpack the result
                assignments, teachers_df, slot_info, responsible_schedule, all_teachers_lookup = result
                
                self.after(0, lambda: self.update_progress(0.55, "Optimisation en cours..."))
                
                # Check for cancellation
                if self.cancel_requested:
                    self.cancel_requested = False
                    return
                
                self.after(0, lambda: self.update_progress(0.65, "Calcul de satisfaction..."))
                
                # Calculate satisfaction report
                try:
                    min_quotas = {}
                    for tid in teachers_df.index:
                        # Handle both column names: 'grade' (new) or 'grade_code_ens' (old)
                        grade = teachers_df.loc[tid].get('grade') or teachers_df.loc[tid].get('grade_code_ens')
                        min_quotas[tid] = config['quotas'].get(grade, 5)
                    
                    from collections import defaultdict
                    slots_by_date = defaultdict(list)
                    for s_idx, slot in enumerate(slot_info):
                        slots_by_date[slot['date']].append(s_idx)
                    
                    satisfaction_report = analyze_teacher_satisfaction(
                        assignments, teachers_df, min_quotas, slot_info, slots_by_date
                    )
                except Exception as e:
                    print(f"⚠️  Satisfaction calculation failed: {e}")
                    satisfaction_report = None
            
            # Update progress - Optimization complete
            self.after(0, lambda: self.update_progress(0.7, "Optimisation terminée"))
            
            # Check for cancellation
            if self.cancel_requested:
                self.cancel_requested = False
                return
            
            # Calculate statistics
            # Handle both assignment formats: dict of lists OR dict of dicts
            if assignments and isinstance(next(iter(assignments.values())), list):
                # New format: {teacher_id: [slot_indices]}
                total_assignments = sum(len(slots) for slots in assignments.values())
            else:
                # Old format: {teacher_id: {'surveillant': [...]}}
                total_assignments = sum(len(a.get('surveillant', [])) for a in assignments.values())
            
            num_teachers = len(assignments)
            num_slots = len(slot_info)
            
            # Note: Database save is already done inside generate_planning_from_db()
            # No need to export files - planning is saved in database
            
            # Complete
            execution_time = (datetime.now() - start_time).total_seconds()
            self.after(0, lambda: self.update_progress(1.0, "Génération terminée et sauvegardée!"))
            
            # Final check for cancellation before showing success
            if self.cancel_requested:
                self.cancel_requested = False
                return
            
            # Set flag to load this session in edit page
            self.app.should_load_from_db = True
            print(f"Generation complete - Session ID: {self.app.current_session_id}")
            print(f"Flag set: should_load_from_db = {self.app.should_load_from_db}")
            
            # Show success message and navigate to edit page
            self.after(0, lambda: self.show_success_message(num_teachers, total_assignments))
            
        except Exception as e:
            error_msg = str(e)
            # Log full traceback for diagnostics
            try:
                tb = traceback.format_exc()
                if hasattr(self, 'logger') and self.logger:
                    self.logger.exception('Error during generation: %s', error_msg)
                    self.logger.debug(tb)
                else:
                    print(tb)
            except Exception:
                pass

            self.after(0, lambda: self.update_progress(0, f"ERROR: {error_msg}"))
            self.after(0, lambda: messagebox.showerror("Erreur", f"Erreur lors de la génération:\n{error_msg}"))
        
        finally:
            self.is_generating = False
            self.after(0, self.hide_loading_ui)
    
    def show_success_message(self, num_teachers, total_assignments):
        """Show success message and navigate to edit page"""
        # Get session info for display
        session_name = "Session actuelle"
        if hasattr(self.app, 'current_session_id') and self.app.current_session_id:
            try:
                session = self.db.get_session(self.app.current_session_id)
                if session:
                    session_name = session['nom']
            except:
                pass
        
        result = messagebox.askyesno(
            "Génération Terminée",
            f"Planning généré avec succès pour {session_name}!\n\n"
            f"• Enseignants: {num_teachers}\n"
            f"• Affectations: {total_assignments}\n"
            f"• Sauvegardé dans la base de données\n\n"
            f"Voulez-vous ouvrir l'éditeur de planning?"
        )
        
        if result:
            self.app.show_edit_planning()
    
    def show_feasibility_analysis(self):
        """Show feasibility analysis based on uploaded files"""
        # Prevent multiple analysis windows
        if hasattr(self, '_analysis_window') and self._analysis_window and self._analysis_window.winfo_exists():
            self._analysis_window.focus_force()
            return
        
        # Default to using custom quotas unless the user explicitly chooses suggested
        self.use_custom_quotas_flag = True

        if not HAS_DATABASE:
            messagebox.showerror("Erreur", "Base de données non disponible")
            return
        
        # Get current session ID
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showerror("Erreur", "Aucune session active. Veuillez d'abord télécharger les fichiers.")
            return
        
        try:
            # Get current configuration (including custom quotas)
            config = self.get_configuration()
            custom_quotas = config.get('quotas', None)
            supervisors_per_room = config.get('supervisors_per_room', 2)
            
            # Create decision support system
            dss = DecisionSupportSystem(self.db)
            
            # Analyze session with custom quotas
            report = dss.analyze_session(
                self.app.current_session_id,
                supervisors_per_room=supervisors_per_room,
                custom_quotas=custom_quotas
            )
            
            # Create modal window
            analysis_window = ctk.CTkToplevel(self)
            self._analysis_window = analysis_window  # Store reference to prevent duplicates
            analysis_window.title("Analyse de Faisabilité")
            
            # Disable window resize to prevent rerenders
            analysis_window.resizable(False, False)
            
            # Set fixed size
            window_width = 950
            window_height = 850
            
            # Center the window immediately (before showing)
            screen_width = analysis_window.winfo_screenwidth()
            screen_height = analysis_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            analysis_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Make it modal
            analysis_window.transient(self)
            analysis_window.grab_set()
            
            # Focus the window
            analysis_window.focus_force()
            
            # Header with status
            header_frame = ctk.CTkFrame(analysis_window, fg_color=self.colors['surface'], corner_radius=10)
            header_frame.pack(fill="x", padx=20, pady=20)
            
            # Status color coding
            status_colors = {
                "excellent": "#059669",
                "good": "#10B981", 
                "warning": "#F59E0B",
                "critical": "#EF4444"
            }
            status_color = status_colors.get(report.status, "#6B7280")
            
            # Status badge
            status_frame = ctk.CTkFrame(header_frame, fg_color=status_color, corner_radius=20)
            status_frame.pack(pady=10)
            
            status_label = ctk.CTkLabel(
                status_frame,
                text=f"  {report.status.upper()}  ",
                font=("Segoe UI", 14, "bold"),
                text_color="white"
            )
            status_label.pack(padx=20, pady=5)
            
            # Feasibility score
            score_label = ctk.CTkLabel(
                header_frame,
                text=f"Score de Faisabilité: {report.feasibility_score:.0f}/100",
                font=("Segoe UI", 20, "bold"),
                text_color=self.colors['text_primary']
            )
            score_label.pack(pady=(5, 10))
            
            # Scrollable content frame - optimized for performance
            content_frame = ctk.CTkFrame(
                analysis_window,
                fg_color=self.colors['surface'],
                corner_radius=10
            )
            content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
            
            # Format and display report
            report_text = dss.format_report_text(report)
            
            # Use a single textbox with built-in scrolling (no nested scroll frames)
            text_widget = ctk.CTkTextbox(
                content_frame,
                font=("Consolas", 11),  # Monospace font for better alignment
                wrap="word",
                fg_color=self.colors['background'],
                scrollbar_button_color=self.colors['primary'],
                scrollbar_button_hover_color=self.colors['hover_dark']
            )
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)
            text_widget.insert("1.0", report_text)
            text_widget.configure(state="disabled")
            
            # Quota choice section (if custom quotas were used)
            if report.using_custom_quotas and report.suggested_quotas:
                quota_frame = ctk.CTkFrame(
                    analysis_window,
                    fg_color=self.colors['surface'],
                    corner_radius=10
                )
                quota_frame.pack(fill="x", padx=20, pady=(0, 10))
                
                quota_title = ctk.CTkLabel(
                    quota_frame,
                    text="⚙️ Quotas de Surveillance",
                    font=("Segoe UI", 16, "bold"),
                    text_color=self.colors['text_primary']
                )
                quota_title.pack(pady=(10, 5))
                
                # Show quota comparison if different
                current_total = sum(custom_quotas.get(g, 0) * report.capacity_analysis['grade_capacity'].get(g, {}).get('count', 0) 
                                  for g in custom_quotas.keys())
                suggested_total = report.quota_analysis.get('total_adjusted', 0)
                
                if abs(current_total - suggested_total) > 1:  # If there's a meaningful difference
                    quota_info = ctk.CTkLabel(
                        quota_frame,
                        text=f"Vos quotas: {current_total} surveillances | Quotas suggérés: {suggested_total} surveillances",
                        font=("Segoe UI", 12),
                        text_color=self.colors['text_secondary']
                    )
                    quota_info.pack(pady=5)
                    
                    # Choice buttons
                    button_frame = ctk.CTkFrame(quota_frame, fg_color="transparent")
                    button_frame.pack(pady=10)
                    
                    def use_current_quotas():
                        # Set flag to use custom quotas
                        self.use_custom_quotas_flag = True
                        self.quota_choice = 'current'
                        analysis_window.destroy()
                        # Automatically start generation
                        self.after(100, self._start_generation_after_analysis)
                    
                    def use_suggested_quotas():
                        # Update the UI sliders with suggested quotas
                        for grade, quota_value in report.suggested_quotas.items():
                            widget_key = f'quota_{grade}'
                            if widget_key in self.config_widgets:
                                self.config_widgets[widget_key]['slider'].set(quota_value)
                                self.config_widgets[widget_key]['label'].configure(text=str(quota_value))
                        # Set flag to NOT use custom quotas (algorithm will auto-adjust)
                        self.use_custom_quotas_flag = False
                        self.quota_choice = 'suggested'
                        analysis_window.destroy()
                        # Automatically start generation
                        self.after(100, self._start_generation_after_analysis)
                    
                    current_btn = ctk.CTkButton(
                        button_frame,
                        text="Utiliser mes quotas",
                        command=use_current_quotas,
                        height=35,
                        width=180,
                        fg_color=self.colors['surface'],
                        border_width=2,
                        border_color=self.colors['primary'],
                        text_color=self.colors['primary'],
                        hover_color=self.darken_color(self.colors['surface']),
                        font=("Segoe UI", 12)
                    )
                    current_btn.pack(side="left", padx=5)
                    
                    suggested_btn = ctk.CTkButton(
                        button_frame,
                        text="Utiliser quotas suggérés",
                        command=use_suggested_quotas,
                        height=35,
                        width=180,
                        fg_color=self.colors['primary'],
                        hover_color="#6D28D9",
                        font=("Segoe UI", 12)
                    )
                    suggested_btn.pack(side="left", padx=5)
            
            # Close button
            close_btn = ctk.CTkButton(
                analysis_window,
                text="Annuler",
                command=analysis_window.destroy,
                height=40,
                fg_color="#6B7280",
                hover_color="#4B5563",
                font=("Segoe UI", 13)
            )
            close_btn.pack(pady=(0, 15))
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'analyse:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def darken_color(self, color):
        """Darken a hex color"""
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, int(r * 0.8))
        g = max(0, int(g * 0.8))
        b = max(0, int(b * 0.8))
        return f'#{r:02x}{g:02x}{b:02x}'
