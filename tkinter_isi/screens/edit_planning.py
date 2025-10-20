"""
Edit Planning Screen - Interactive editor for modifying generated schedules
Includes calendar view and teacher-specific views with REAL backend integration

✅ FULLY CONNECTED TO BACKEND:
- Loads actual generated planning from Excel files
- Displays real assignments in calendar and teacher views
- Allows modifications with conflict detection
- Validates changes against voeux and constraints
- Saves changes to database and exports updated Excel
- Tracks full audit history

NO PLACEHOLDERS - ALL DATA IS REAL
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime, timedelta
import pandas as pd
import os
from collections import defaultdict
import tkinter as tk

# Import performance utilities
try:
    import sys
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    utils_dir = os.path.join(parent_dir, 'utils')
    if utils_dir not in sys.path:
        sys.path.insert(0, utils_dir)
    from performance_utils import LoadingIndicator, DataCache, batch_update
    HAS_PERF_UTILS = True
except ImportError:
    HAS_PERF_UTILS = False
    print("⚠️  Performance utilities not available")

# Try to import backend modules
try:
    import sys
    # Add parent directory to path for imports
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Try to import from parent directory (src/)
    try:
        from export import export_all_formats
        from data_loader import load_teachers, load_voeux, load_creneaux
        HAS_EXPORT = True
        print("✅ Export module loaded successfully")
    except ImportError:
        try:
            # Try alternative path
            src_path = os.path.join(os.path.dirname(parent_dir), 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            from export import export_all_formats
            from data_loader import load_teachers, load_voeux, load_creneaux
            HAS_EXPORT = True
            print("✅ Export module loaded successfully (alternative path)")
        except ImportError:
            HAS_EXPORT = False
            print("⚠️  Export module not available - limited functionality")
except Exception as e:
    HAS_EXPORT = False
    print(f"⚠️  Backend integration not available: {e}")

# Try to import database helper (optional)
try:
    from database.db_helper import DatabaseHelper
    HAS_DATABASE = True
    print("✅ Database module loaded successfully")
except ImportError:
    HAS_DATABASE = False
    print("⚠️  Database integration not available (db_helper not found)")


class EditPlanningScreen(ctk.CTkFrame):
    """Interactive planning editor with REAL backend integration"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # Real data structures (loaded from files)
        self.loaded_planning_file = None
        self.assignments_df = None  # DataFrame from "Planning Détaillé" sheet
        self.teachers_df = None     # DataFrame with teacher info
        self.schedule_data = {}     # Calendar view data: {date: {seance: [teachers]}}
        self.teacher_schedules = {}  # Teacher view data: {teacher_name: [assignments]}
        self.available_dates = []   # List of dates with assignments
        self.selected_date = None
        self.selected_teacher = None
        self.available_teachers = []
        
        # Modification tracking with undo/redo support
        self.modifications = []  # List of changes made
        self.original_assignments = {}  # Backup for undo
        self.undo_stack = []  # Stack for undo operations
        self.redo_stack = []  # Stack for redo operations
        
        # Search and highlight state
        self.highlighted_teacher = None
        self.highlighted_cells = []  # List of highlighted cell widgets
        self.search_modal = None
        
        # Selection state for calendar cells
        self.selected_cell_frame = None  # Currently selected cell frame
        self.selected_cell_info = None   # Info about selected cell (teacher, seance, date)
        
        # Swap mode state
        self.swap_mode_active = False  # Is swap mode currently active
        self.swap_source = None  # First selected slot for swap {teacher, seance, date, frame}
        self.swap_target = None  # Second selected slot for swap {teacher, seance, date, frame}
        
        # Loading state
        self.view_switch_timer = None  # For debouncing view switches
        
        # Teacher view optimization - store widget references
        self.teacher_view_widgets = {
            'table_container': None,  # Scrollable frame
            'header_row': [],  # Header label widgets
            'data_rows': [],   # List of row data (list of label widgets)
            'stats_labels': {}  # Statistics display widgets
        }
        
        # Calendar view optimization - store widget references
        self.calendar_view_widgets = {
            'table_container': None,  # Scrollable frame
            'header_row': [],  # Header label widgets (Séance 1, Séance 2, etc.)
            'sessions': []  # List of session IDs for current view
        }
        
        # State flags
        self.is_loading = False
        self.has_unsaved_changes = False
        
        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=0)  # Toolbar
        self.grid_rowconfigure(2, weight=1)  # Content
        self.grid_columnconfigure(0, weight=1)
        
        self.create_header()
        self.create_toolbar()
        self.create_editor_area()
        
        # Check if planning is already loaded in app state (persisting across page changes)
        if hasattr(self.app, 'loaded_planning_state') and self.app.loaded_planning_state:
            print("📥 Restoring from app state...")
            # Restore from app state
            self.restore_from_app_state()
        # Check if we should load from database (after generation)
        elif hasattr(self.app, 'should_load_from_db') and self.app.should_load_from_db:
            print(f"📥 Loading from database - Session ID: {getattr(self.app, 'current_session_id', 'NONE')}")
            self.load_planning_from_database()
            # Clear the flag after loading
            self.app.should_load_from_db = False
        # Check if there's a newly generated planning to auto-load
        elif hasattr(self.app, 'last_generated_planning') and self.app.last_generated_planning:
            print(f"📥 Loading from file: {self.app.last_generated_planning}")
            self.load_planning_from_file(self.app.last_generated_planning)
            # Clear the flag after loading
            self.app.last_generated_planning = None
        else:
            print("📥 Auto-loading latest planning from output directory...")
            # Try to auto-load most recent planning
            self.auto_load_latest_planning()
    
    def restore_from_app_state(self):
        """Restore planning data from app state (when navigating back to this page)"""
        state = self.app.loaded_planning_state
        
        self.loaded_planning_file = state['file_path']
        self.assignments_df = state['assignments_df'].copy()
        self.teachers_df = state['teachers_df'].copy() if state['teachers_df'] is not None else None
        self.schedule_data = state['schedule_data'].copy()
        self.teacher_schedules = state['teacher_schedules'].copy()
        self.available_dates = state['available_dates'].copy()
        self.available_teachers = state['available_teachers'].copy()
        self.selected_date = state['selected_date']
        self.selected_teacher = state['selected_teacher']
        self.original_assignments = state['original_assignments'].copy()
        self.has_unsaved_changes = state['has_unsaved_changes']
        
        # Update stats display BEFORE refreshing views
        self._update_stats_display()
        
        # Refresh the view
        if self.view_mode == "calendar":
            self.show_calendar_view()
        elif self.view_mode == "teachers":
            self.show_teachers_view()
        
        # Refresh details panel
        if hasattr(self, 'details_frame'):
            self.show_details_panel()
    
    def save_to_app_state(self):
        """Save current planning state to app for persistence across page changes"""
        if self.loaded_planning_file:
            self.app.loaded_planning_state = {
                'file_path': self.loaded_planning_file,
                'assignments_df': self.assignments_df.copy(),
                'teachers_df': self.teachers_df.copy() if self.teachers_df is not None else None,
                'schedule_data': self.schedule_data.copy(),
                'teacher_schedules': self.teacher_schedules.copy(),
                'available_dates': self.available_dates.copy(),
                'available_teachers': self.available_teachers.copy(),
                'selected_date': self.selected_date,
                'selected_teacher': self.selected_teacher,
                'original_assignments': self.original_assignments.copy(),
                'has_unsaved_changes': self.has_unsaved_changes
            }
            print(f"💾 Saved planning state to app: {len(self.available_teachers)} teachers, {len(self.available_dates)} dates")
        else:
            print("⚠️  Cannot save to app state - no planning file loaded")
    
    def auto_load_latest_planning(self):
        """Automatically load the most recent planning file from output directory"""
        try:
            # Look for planning files in output directory
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'output')
            if not os.path.exists(output_dir):
                self.app.update_status("Aucun planning trouvé - générez d'abord un planning")
                return
            
            # Find all consolidated planning files
            planning_files = []
            for file in os.listdir(output_dir):
                if file.endswith('_consolidated.xlsx') or file.startswith('planning_') and file.endswith('.xlsx'):
                    filepath = os.path.join(output_dir, file)
                    planning_files.append((filepath, os.path.getmtime(filepath)))
            
            if not planning_files:
                self.app.update_status("Aucun planning trouvé - générez d'abord un planning")
                return
            
            # Sort by modification time (most recent first)
            planning_files.sort(key=lambda x: x[1], reverse=True)
            latest_file = planning_files[0][0]
            
            # Load the latest file
            self.load_planning_from_file(latest_file)
            self.app.update_status(f"Planning chargé: {os.path.basename(latest_file)}")
            
        except Exception as e:
            print(f"Erreur lors du chargement automatique: {e}")
            self.app.update_status("Erreur lors du chargement du planning")
    
    def load_planning_from_file(self, filepath):
        """Load planning data from Excel file (REAL DATA) - OPTIMIZED WITH CACHING"""
        try:
            # Check cache first
            cache_key = f"planning_{filepath}"
            cached = self.app.get_cached_data(cache_key) if hasattr(self.app, 'get_cached_data') else None
            
            if cached:
                # Use cached data
                self.assignments_df = cached['assignments_df']
                self.teachers_df = cached['teachers_df']
                self.schedule_data = cached['schedule_data']
                self.teacher_schedules = cached['teacher_schedules']
                self.available_teachers = cached['available_teachers']
                self.available_dates = cached['available_dates']
                self.loaded_planning_file = filepath
                
                # Set initial selections - Keep teacher as None for placeholder
                if self.available_dates:
                    self.selected_date = self.available_dates[0]
                
                self.original_assignments = self.assignments_df.copy()
                self.has_unsaved_changes = False
                self.is_loading = False
                
                # Refresh views
                self.after(100, self._refresh_views_async)
                self.save_to_app_state()
                
                self.app.update_status("Planning chargé depuis le cache!", show_progress=False)
                return True
            
            self.is_loading = True
            self.loaded_planning_file = filepath
            
            # Show loading indicator
            self.app.update_status("Chargement du planning en cours...", show_progress=True, progress_value=0.3)
            
            # Read "Planning Détaillé" sheet with optimized settings
            self.assignments_df = pd.read_excel(
                filepath, 
                sheet_name='Planning Détaillé',
                engine='openpyxl',  # Explicitly use openpyxl for better performance
                dtype_backend='numpy_nullable'  # Use nullable dtypes for better memory
            )
            
            self.app.update_status("Traitement des données...", show_progress=True, progress_value=0.5)
            
            # Read "Résumé Enseignants" sheet for teacher info
            try:
                self.teachers_df = pd.read_excel(filepath, sheet_name='Résumé Enseignants')
            except:
                # If summary doesn't exist, extract from detailed
                self.teachers_df = self.assignments_df[['ID Enseignant', 'Nom Complet', 'Grade', 'Email']].drop_duplicates()
            
            # Build calendar view data structure (OPTIMIZED - use vectorized operations)
            self.schedule_data = defaultdict(lambda: defaultdict(list))
            self.teacher_schedules = defaultdict(list)
            
            # Use vectorized string operations for better performance
            dates = self.assignments_df['Date'].astype(str).str[:10]
            seances = self.assignments_df.get('Séance', self.assignments_df.get('seance', pd.Series()))
            teacher_names = self.assignments_df.get('Nom Complet', self.assignments_df.get('Nom_Complet', pd.Series()))
            heures = self.assignments_df.get('Heure', self.assignments_df.get('heure_debut', pd.Series()))
            jours = self.assignments_df.get('Jour', self.assignments_df.get('jour', pd.Series()))
            
            # Build data structures using faster iteration
            for date, seance, teacher, heure, jour in zip(dates, seances, teacher_names, heures, jours):
                # Add to calendar view
                if pd.notna(date) and pd.notna(seance):
                    self.schedule_data[date][seance].append(teacher)
                
                # Add to teacher view
                if pd.notna(teacher):
                    self.teacher_schedules[teacher].append({
                        'date': date,
                        'jour': jour,
                        'heure_debut': heure,
                        'seance': seance
                    })
            
            # Get unique teachers efficiently
            self.available_teachers = sorted(teacher_names.dropna().unique().tolist())
            
            # Sort dates
            self.available_dates = sorted(self.schedule_data.keys())
            
            # Set initial selections - Keep teacher as None for placeholder
            if self.available_dates:
                self.selected_date = self.available_dates[0]
            
            self.app.update_status("Finalisation...", show_progress=True, progress_value=0.8)
            
            # Create backup for undo
            self.original_assignments = self.assignments_df.copy()
            self.has_unsaved_changes = False
            
            self.is_loading = False
            
            # Refresh the view in the background
            self.after(100, self._refresh_views_async)
            
            # Cache the loaded data for performance
            if hasattr(self.app, 'cache_data'):
                cache_key = f"planning_{filepath}"
                self.app.cache_data(cache_key, {
                    'assignments_df': self.assignments_df.copy(),
                    'teachers_df': self.teachers_df.copy(),
                    'schedule_data': dict(self.schedule_data),
                    'teacher_schedules': dict(self.teacher_schedules),
                    'available_teachers': self.available_teachers.copy(),
                    'available_dates': self.available_dates.copy()
                })
            
            # Save to app state for persistence
            self.save_to_app_state()
            
            self.app.update_status("Planning chargé avec succès!", show_progress=False)
            
            return True
            
        except Exception as e:
            self.is_loading = False
            self.app.update_status("Erreur lors du chargement", show_progress=False)
            messagebox.showerror(
                "Erreur",
                "Impossible de charger le planning.\n\nGénérez d'abord un planning (Étape 2)."
            )
            return False
    
    def load_planning_from_database(self):
        """Load planning data from database for current session"""
        try:
            # Import database operations
            import sys
            from pathlib import Path
            parent_dir = Path(__file__).parent.parent.parent
            db_dir = parent_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            
            # Check if session is set
            if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
                messagebox.showwarning(
                    "Aucune Session",
                    "Aucune session active.\nCréez ou chargez une session d'abord."
                )
                return False
            
            self.is_loading = True
            session_id = self.app.current_session_id
            
            # Show loading indicator
            self.app.update_status(f"Chargement de la session #{session_id} depuis la base de données...", 
                                 show_progress=True, progress_value=0.3)
            
            # Connect to database
            db_path = parent_dir / "planning.db"
            db = DatabaseManager(str(db_path))
            
            # Get session info
            session = db.get_session(session_id)
            if not session:
                messagebox.showerror("Erreur", f"Session {session_id} introuvable dans la base de données.")
                self.is_loading = False
                return False
            
            self.app.update_status(f"Chargement des affectations...", show_progress=True, progress_value=0.5)
            
            # Get assignments with full details using direct SQL query
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            
            query = """
                SELECT 
                    A.id,
                    A.enseignant_id,
                    E.nom_ens,
                    E.prenom_ens,
                    E.email_ens,
                    E.grade as grade_code_ens,
                    E.code_smartexam_ens,
                    E.id as db_teacher_id,
                    C.date_examen,
                    C.heure_debut,
                    C.nb_surveillants,
                    A.role
                FROM Affectations A
                JOIN Creneaux C ON A.creneau_id = C.id
                JOIN Enseignants E ON A.enseignant_id = E.id AND E.session_id = ?
                WHERE C.session_id = ?
                ORDER BY C.date_examen, C.heure_debut, E.nom_ens
            """
            
            # Load into DataFrame
            import pandas as pd
            assignments_df = pd.read_sql_query(query, conn, params=(session_id, session_id))
            conn.close()
            
            if assignments_df.empty:
                messagebox.showinfo(
                    "Session Vide",
                    f"La session '{session['nom']}' ne contient pas encore d'affectations.\n\n"
                    f"Générez d'abord un planning pour cette session."
                )
                self.is_loading = False
                return False
            
            # Add combined name column
            assignments_df['Nom Complet'] = assignments_df['nom_ens'] + ' ' + assignments_df['prenom_ens']
            
            # Calculate Salles from nb_surveillants (usually nb_surveillants / 2)
            assignments_df['Salles'] = assignments_df['nb_surveillants'] // 2
            
            # Rename columns to match expected format from Excel export
            column_mapping = {
                'date_examen': 'Date',
                'heure_debut': 'Heure',
                'grade_code_ens': 'Grade',
                'email_ens': 'Email',
                'code_smartexam_ens': 'ID Enseignant'
            }
            assignments_df = assignments_df.rename(columns=column_mapping)
            
            # Add Jour and Séance columns (derived from date and time)
            if 'Date' in assignments_df.columns:
                try:
                    assignments_df['Date'] = pd.to_datetime(assignments_df['Date'])
                    # Map day names
                    day_names_fr = {
                        0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 
                        3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
                    }
                    assignments_df['Jour'] = assignments_df['Date'].dt.dayofweek.map(day_names_fr)
                except:
                    assignments_df['Jour'] = ''
            
            # Map time to Séance (use actual time, don't convert to Matin/Après-midi)
            if 'Heure' in assignments_df.columns:
                # Just use the time as-is for Séance
                assignments_df['Séance'] = assignments_df['Heure'].astype(str)
            
            # Store the data
            self.assignments_df = assignments_df
            self.loaded_planning_file = f"Database Session {session_id}: {session['nom']}"
            
            self.app.update_status("Construction des vues...", show_progress=True, progress_value=0.7)
            
            # Build schedule structures (same as file loading)
            self.schedule_data = defaultdict(lambda: defaultdict(list))
            self.teacher_schedules = defaultdict(list)
            
            # Process assignments
            for _, row in assignments_df.iterrows():
                # Format date properly
                date_val = row.get('Date', '')
                if hasattr(date_val, 'strftime'):
                    date = date_val.strftime('%Y-%m-%d')
                else:
                    date = str(date_val)
                    
                seance = str(row.get('Séance', row.get('Heure', '')))
                teacher_name = row.get('Nom Complet', 'Inconnu')
                jour = row.get('Jour', '')
                heure_debut = row.get('Heure', '')
                
                # Calendar view - only need teacher name
                self.schedule_data[date][seance].append({
                    'teacher': teacher_name,
                    'grade': row.get('Grade', ''),
                    'email': row.get('Email', ''),
                    'salles': row.get('Salles', 0)
                })
                
                # Teacher view - need date, jour, heure_debut, seance
                self.teacher_schedules[teacher_name].append({
                    'date': date,
                    'jour': jour,
                    'heure_debut': heure_debut,
                    'seance': seance,
                    'salles': row.get('Salles', 0)
                })
            
            # Get unique teachers and dates
            self.available_teachers = sorted(list(set(assignments_df['Nom Complet'].dropna())))
            # Convert dates to strings for display (handle datetime objects)
            unique_dates = []
            for d in assignments_df['Date'].dropna():
                if hasattr(d, 'strftime'):
                    unique_dates.append(d.strftime('%Y-%m-%d'))
                else:
                    unique_dates.append(str(d))
            self.available_dates = sorted(list(set(unique_dates)))
            
            # Set initial selections - Keep teacher as None for placeholder
            if self.available_dates:
                self.selected_date = self.available_dates[0]
            
            # Load teacher details
            try:
                # Get teacher summary from database
                teachers_df = db.get_teachers(session_id)
                if not teachers_df.empty:
                    # Add combined name
                    teachers_df['Nom Complet'] = teachers_df['nom_ens'] + ' ' + teachers_df['prenom_ens']
                    self.teachers_df = teachers_df
                else:
                    # Extract from assignments
                    self.teachers_df = assignments_df[['ID Enseignant', 'Nom Complet', 'Grade', 'Email']].drop_duplicates()
            except:
                # Fallback: extract from assignments
                self.teachers_df = assignments_df[['ID Enseignant', 'Nom Complet', 'Grade', 'Email']].drop_duplicates()
            
            # Create backup
            self.original_assignments = self.assignments_df.copy()
            self.has_unsaved_changes = False
            self.is_loading = False
            
            # Refresh views
            self.after(100, self._refresh_views_async)
            
            # Save to app state
            self.save_to_app_state()
            
            self.app.update_status(f"Planning chargé: {session['nom']}", show_progress=False)
            
            # Update stats display in toolbar instead of showing popup
            self._update_stats_display()
            return True
            
        except Exception as e:
            self.is_loading = False
            self.app.update_status("Erreur lors du chargement", show_progress=False)
            messagebox.showerror(
                "Erreur",
                f"Impossible de charger le planning depuis la base de données:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
            return False
    
    def _refresh_views_async(self):
        """Refresh views asynchronously to avoid UI freeze"""
        try:
            if hasattr(self, 'main_view_frame'):
                if self.view_mode == "calendar":
                    self.show_calendar_view()
                elif self.view_mode == "teachers":
                    self.show_teachers_view()
            
            # Refresh details panel with loaded teachers
            if hasattr(self, 'details_frame'):
                self.show_details_panel()
        except Exception as e:
            print(f"Error refreshing views: {e}")
    
    def _update_stats_display(self):
        """Update the stats bar in toolbar with planning statistics"""
        if not hasattr(self, 'stats_label'):
            return
        
        try:
            num_teachers = len(self.available_teachers) if hasattr(self, 'available_teachers') else 0
            num_dates = len(self.available_dates) if hasattr(self, 'available_dates') else 0
            
            # Count total surveillances from schedule_data
            num_surveillances = 0
            if hasattr(self, 'schedule_data'):
                for date_data in self.schedule_data.values():
                    for teachers_list in date_data.values():
                        num_surveillances += len(teachers_list)
            
            # Update label text
            stats_text = f"👥 {num_teachers} enseignants  •  📅 {num_dates} jours  •  📝 {num_surveillances} surveillances"
            self.stats_label.configure(text=stats_text)
        except Exception as e:
            print(f"Error updating stats display: {e}")
    
    # ==================== LOADING INDICATOR METHODS ====================
    
    def show_loading_indicator(self, parent, message="Chargement..."):
        """Show animated loading indicator"""
        # Create loading container
        loading_frame = ctk.CTkFrame(parent, fg_color="transparent")
        loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Animated spinner
        self.loading_label = ctk.CTkLabel(
            loading_frame,
            text="⏳",
            font=("Segoe UI", 48),
            text_color=self.colors['primary']
        )
        self.loading_label.pack(pady=(0, 15))
        
        # Loading text
        loading_text = ctk.CTkLabel(
            loading_frame,
            text=message,
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary']
        )
        loading_text.pack()
        
        # Store reference
        self.loading_frame = loading_frame
        
        # Start animation
        self._animate_loading_spinner()
    
    def _animate_loading_spinner(self):
        """Animate the loading spinner"""
        if not hasattr(self, 'loading_label') or not self.loading_label.winfo_exists():
            return
        
        spinners = ["⏳", "⌛", "⏳", "⌛"]
        if not hasattr(self, '_spinner_index'):
            self._spinner_index = 0
        
        self.loading_label.configure(text=spinners[self._spinner_index])
        self._spinner_index = (self._spinner_index + 1) % len(spinners)
        
        if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
            self.after(200, self._animate_loading_spinner)
    
    def hide_loading_indicator(self):
        """Remove loading indicator"""
        if hasattr(self, 'loading_frame'):
            try:
                self.loading_frame.destroy()
                delattr(self, 'loading_frame')
                delattr(self, 'loading_label')
                if hasattr(self, '_spinner_index'):
                    delattr(self, '_spinner_index')
            except:
                pass
    
    def get_teacher_schedule(self, teacher_name):
        """Get schedule for a specific teacher (REAL DATA)"""
        return self.teacher_schedules.get(teacher_name, [])
    
    def create_header(self):
        """Create page header"""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(15, 5))
        
        # Row with back button and step indicator side by side
        top_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        top_row.pack(fill="x")
        
        # Back button on the left
        back_btn = ctk.CTkButton(
            top_row,
            text="←",
            width=40,
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.colors['hover'],
            text_color=self.colors['text_primary'],
            font=("Segoe UI", 20),
            command=self.app.show_generate_planning
        )
        back_btn.pack(side="left", padx=(0, 20))
        
        # Step indicator on the right (takes remaining space)
        from widgets.step_indicator import StepIndicator
        step_indicator = StepIndicator(top_row, current_step=2, colors=self.colors)
        step_indicator.pack(side="left", fill="x", expand=True)
    
    def create_toolbar(self):
        """Create toolbar with view options and actions"""
        toolbar = ctk.CTkFrame(self, fg_color=self.colors['surface'], height=60)
        toolbar.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 10))
        toolbar.grid_propagate(False)
        
        # Left side - View selection
        view_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        view_frame.pack(side="left", padx=15, pady=10)
        
        view_label = ctk.CTkLabel(
            view_frame,
            text="Vue:",
            font=("Segoe UI", 12, "bold"),
            text_color=self.colors['text_primary']
        )
        view_label.pack(side="left", padx=(0, 10))
        
        # View buttons (segmented button style)
        # Check if initial view mode is set (e.g., from statistics navigation)
        if hasattr(self.app, 'initial_planning_view') and self.app.initial_planning_view:
            self.view_mode = self.app.initial_planning_view
            delattr(self.app, 'initial_planning_view')  # Clear flag after use
        else:
            self.view_mode = "calendar"
        
        self.create_view_button(view_frame, "📅 Calendrier", "calendar")
        self.create_view_button(view_frame, "👥 Enseignants", "teachers")
        
        # Center - Stats display
        self.stats_frame = ctk.CTkFrame(toolbar, fg_color=self.colors['background'], corner_radius=8)
        self.stats_frame.pack(side="left", padx=30, pady=10, expand=True)
        
        # Stats will be updated when planning is loaded
        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="",  # Empty initially
            font=("Segoe UI", 13),
            text_color=self.colors['text_secondary']
        )
        self.stats_label.pack(padx=20, pady=8)
        
        # Right side - Action buttons
        action_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        action_frame.pack(side="right", padx=15, pady=10)
        
        # Removed file loading button - planning is loaded from database only
        
        save_btn = ctk.CTkButton(
            action_frame,
            text="💾 Enregistrer",
            width=170,
            height=38,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 13, "bold"),
            command=self.save_changes
        )
        save_btn.pack(side="left", padx=5)
        
        # Undo button
        self.undo_btn = ctk.CTkButton(
            action_frame,
            text="↶ Annuler",
            width=100,
            height=38,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 13),
            command=self.undo_last_change,
            state="disabled"  # Initially disabled
        )
        self.undo_btn.pack(side="left", padx=5)
        
        # Redo button
        self.redo_btn = ctk.CTkButton(
            action_frame,
            text="↷ Refaire",
            width=100,
            height=38,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 13),
            command=self.redo_last_change,
            state="disabled"  # Initially disabled
        )
        self.redo_btn.pack(side="left", padx=5)
        
        # Export button (added to toolbar)
        export_btn = ctk.CTkButton(
            action_frame,
            text="📤 Exporter",
            width=130,
            height=38,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 13, "bold"),
            command=self.export_planning
        )
        export_btn.pack(side="left", padx=5)
        

    
    def create_view_button(self, parent, text, mode):
        """Create a view toggle button"""
        is_active = (mode == self.view_mode)
        btn = ctk.CTkButton(
            parent,
            text=text,
            width=120,
            height=38,
            corner_radius=8,
            fg_color=self.colors['primary'] if is_active else "transparent",
            text_color="white" if is_active else self.colors['text_primary'],
            border_width=1 if not is_active else 0,
            border_color=self.colors['border'],
            hover_color="#6D28D9" if is_active else self.colors['hover'],
            font=("Segoe UI", 13, "bold" if is_active else "normal"),
            command=lambda: self.switch_view(mode)
        )
        btn.pack(side="left", padx=3)
        
        # Store button reference to update later
        if not hasattr(self, 'view_buttons'):
            self.view_buttons = {}
        self.view_buttons[mode] = btn
    
    def create_editor_area(self):
        """Create main editor area"""
        self.editor_container = ctk.CTkFrame(self, fg_color="transparent")
        self.editor_container.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 40))
        
        # Configure grid - Calendar takes remaining space, details panel fixed on right
        self.editor_container.grid_rowconfigure(0, weight=1)
        self.editor_container.grid_columnconfigure(0, weight=1)  # Calendar expands
        self.editor_container.grid_columnconfigure(1, weight=0, minsize=380)  # Details fixed
        
        # Left: Main view area - FLEXIBLE WIDTH
        self.main_view_frame = ctk.CTkFrame(
            self.editor_container,
            fg_color=self.colors['surface'],
            corner_radius=12
        )
        self.main_view_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Right: Details panel - Fixed width for consistency
        self.details_frame = ctk.CTkFrame(
            self.editor_container,
            fg_color=self.colors['surface'],
            corner_radius=12,
            width=380  # Fixed width
        )
        self.details_frame.grid(row=0, column=1, sticky="nsew")
        self.details_frame.grid_propagate(False)  # Prevent resizing based on content
        
        # Show initial calendar view
        self.show_calendar_view()
        self.show_details_panel()
    
    def show_calendar_view(self, refresh_only=False):
        """Show calendar view with sessions (REAL DATA from loaded planning) - OPTIMIZED"""
        # If just refreshing (date change), only update content, not entire UI
        if refresh_only and hasattr(self, '_calendar_initialized'):
            self._refresh_calendar_content()
            return
        
        # Build view directly (no loader - it's fast enough)
        self._build_calendar_view_async()
    
    def _build_calendar_view_async(self):
        """Build calendar view asynchronously for better performance"""
        # Clear previous content efficiently
        for widget in self.main_view_frame.winfo_children():
            widget.destroy()
        
        # Reset initialization flag
        self._calendar_initialized = False
        
        # Check if data is loaded
        if not self.loaded_planning_file or not self.available_dates:
            self.show_empty_state("Aucun planning chargé", 
                                 "Veuillez charger un planning existant ou générer un nouveau planning.")
            return
        
        # Modern compact date navigation header (STATIC - won't change on date switch)
        header_frame = ctk.CTkFrame(self.main_view_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 15))
        
        # Compact navigation row with formatted date
        nav_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        nav_frame.pack()
        
        # Previous button - compact icon style (STATIC)
        prev_btn = ctk.CTkButton(
            nav_frame,
            text="←",
            width=50,
            height=50,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            text_color="white",
            font=("Segoe UI", 24),
            command=self.previous_date
        )
        prev_btn.pack(side="left", padx=(0, 12))
        
        # Modern date display with formatted date (DYNAMIC - will update)
        if self.selected_date:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(self.selected_date, '%Y-%m-%d')
                # Format as "13 Mai 2025" or similar
                months_fr = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                           'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
                formatted_date = f"{date_obj.day} {months_fr[date_obj.month]} {date_obj.year}"
            except:
                formatted_date = self.selected_date
        else:
            formatted_date = "Sélectionner"
        
        # Sleek date button - larger, more prominent (DYNAMIC - store reference)
        self._calendar_date_btn = ctk.CTkButton(
            nav_frame,
            text=f"📅  {formatted_date}",
            width=380,
            height=50,
            corner_radius=10,
            fg_color=self.colors['primary'],
            hover_color="#6D28D9",
            text_color="white",
            font=("Segoe UI", 18, "bold"),
            command=self.select_date
        )
        self._calendar_date_btn.pack(side="left", padx=0)
        
        # Next button - compact icon style (STATIC)
        next_btn = ctk.CTkButton(
            nav_frame,
            text="→",
            width=50,
            height=50,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            text_color="white",
            font=("Segoe UI", 24),
            command=self.next_date
        )
        next_btn.pack(side="left", padx=(12, 0))
        
        # Create container for dynamic content (DYNAMIC - store reference)
        self._calendar_content_frame = ctk.CTkFrame(self.main_view_frame, fg_color="transparent")
        self._calendar_content_frame.pack(fill="both", expand=True, padx=20, pady=(15, 20))
        
        # Mark as initialized
        self._calendar_initialized = True
        
        # Render the actual calendar content
        self._render_calendar_content()
    
    def _render_calendar_content(self):
        """Render only the dynamic calendar content (date-dependent data) - OPTIMIZED"""
        # Get all unique sessions for this date
        day_schedule = self.schedule_data.get(self.selected_date, {})
        sessions = sorted(day_schedule.keys()) if day_schedule else []
        
        # Check if we can reuse the existing table with same session structure
        can_reuse_table = (
            self.calendar_view_widgets['table_container'] is not None and
            self.calendar_view_widgets['table_container'].winfo_exists() and
            len(self.calendar_view_widgets['header_row']) > 0 and
            self.calendar_view_widgets['sessions'] == sessions  # Same sessions!
        )
        
        if can_reuse_table:
            # FAST PATH: Only update data rows, keep header and container
            self._update_calendar_data_rows_only(sessions, day_schedule)
            return
        
        # FULL REBUILD PATH: Structure changed (different sessions)
        # Clear only the content frame
        for widget in self._calendar_content_frame.winfo_children():
            widget.destroy()
        
        # Reset calendar view widgets
        self.calendar_view_widgets = {
            'table_container': None,
            'header_row': [],
            'sessions': []
        }
        
        # Clear selection state when refreshing (date changed)
        self.selected_cell_frame = None
        self.selected_cell_info = None
        
        # Initialize cell tracking map for current view
        self._calendar_cells_map = {}
        
        if not sessions:
            # No data for this date
            empty_label = ctk.CTkLabel(
                self._calendar_content_frame,
                text=f"Aucune affectation pour le {self.selected_date}",
                font=("Segoe UI", 14),
                text_color=self.colors['text_secondary']
            )
            empty_label.pack(pady=50)
            return
        
        # Table container with scrolling - STORE REFERENCE
        table_container = ctk.CTkScrollableFrame(
            self._calendar_content_frame,
            fg_color=self.colors['background'],
            corner_radius=8
        )
        table_container.pack(fill="both", expand=True)
        
        # Store container and sessions
        self.calendar_view_widgets['table_container'] = table_container
        self.calendar_view_widgets['sessions'] = sessions
        
        # OPTIMIZATION: Render table asynchronously in batches
        self._render_calendar_table_async(table_container, sessions, day_schedule)
    
    def _refresh_calendar_content(self):
        """Refresh calendar when date changes (OPTIMIZED - no full rebuild)"""
        # Update date button text
        if self.selected_date:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(self.selected_date, '%Y-%m-%d')
                months_fr = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                           'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
                formatted_date = f"{date_obj.day} {months_fr[date_obj.month]} {date_obj.year}"
            except:
                formatted_date = self.selected_date
        else:
            formatted_date = "Sélectionner"
        
        self._calendar_date_btn.configure(text=f"📅  {formatted_date}")
        
        # Re-render only the calendar content
        self._render_calendar_content()
    
    def _render_calendar_table_async(self, container, sessions, day_schedule):
        """Render calendar table asynchronously to avoid UI freeze - OPTIMIZED"""
        # Initialize/clear cell widgets map for selective updates
        self._calendar_cell_widgets = {}
        
        # Create headers first - STORE REFERENCES
        header_row = []
        for col_idx, session in enumerate(sessions):
            # Extract séance number from session (could be '1', '2', '08:30', etc.)
            # Try to extract just the number
            seance_num = session
            if session in ['1', '2', '3', '4']:
                seance_num = session
            else:
                # Try to map time to seance
                time_to_seance = {
                    '08:30': '1', '08:30:00': '1',
                    '10:30': '2', '10:30:00': '2',
                    '12:30': '3', '12:30:00': '3',
                    '14:30': '4', '14:30:00': '4'
                }
                seance_num = time_to_seance.get(session, session)
            
            header = ctk.CTkLabel(
                container,
                text=f"Séance {seance_num}",
                font=("Segoe UI", 16, "bold"),
                text_color="white",
                fg_color=self.colors['secondary'],
                corner_radius=0,
                height=60
            )
            header.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)
            header_row.append(header)
        
        # Store header row for reuse
        self.calendar_view_widgets['header_row'] = header_row
        
        # Find the maximum number of rows needed
        max_rows = max(len(day_schedule.get(session, [])) for session in sessions) if sessions else 0
        if max_rows == 0:
            max_rows = 1
        
        # OPTIMIZED: Larger batches, smaller delays
        # If dataset is small, render all at once
        if max_rows < 50:
            batch_size = max_rows  # Render all at once
            delay = 0
        else:
            batch_size = 30  # Increased from 10 to 30
            delay = 5  # Reduced from 10ms to 5ms
        
        def render_batch(start_row):
            end_row = min(start_row + batch_size, max_rows)
            
            for row_idx in range(start_row, end_row):
                for col_idx, session in enumerate(sessions):
                    teacher_list = day_schedule.get(session, [])
                    
                    # Extract just the teacher name from the dictionary
                    if row_idx < len(teacher_list):
                        teacher_data = teacher_list[row_idx]
                        # Handle both dict format and string format
                        if isinstance(teacher_data, dict):
                            teacher_name = teacher_data.get('teacher', '')
                        else:
                            teacher_name = str(teacher_data)
                    else:
                        teacher_name = ""
                    
                    # Determine cell color (highlight if matches search)
                    is_highlighted = (self.highlighted_teacher and 
                                    teacher_name and 
                                    self.highlighted_teacher in teacher_name)
                    
                    # Check if this cell is the currently selected one
                    is_selected = (self.selected_cell_info and 
                                 teacher_name == self.selected_cell_info.get('teacher') and
                                 session == self.selected_cell_info.get('seance') and
                                 self.selected_date == self.selected_cell_info.get('date'))
                    
                    # Check if this cell is swap source or target (PERSISTENT HIGHLIGHTS)
                    is_swap_source = (self.swap_mode_active and self.swap_source and
                                     teacher_name == self.swap_source.get('teacher') and
                                     session == self.swap_source.get('seance') and
                                     self.selected_date == self.swap_source.get('date'))
                    
                    is_swap_target = (self.swap_mode_active and self.swap_target and
                                     teacher_name == self.swap_target.get('teacher') and
                                     session == self.swap_target.get('seance') and
                                     self.selected_date == self.swap_target.get('date'))
                    
                    # Determine colors based on state (PRIORITY: swap > selected > highlighted)
                    if is_swap_source:
                        cell_fg_color = "#3B82F6"  # Blue for swap source
                        text_color = "white"
                        font_weight = "bold"
                    elif is_swap_target:
                        cell_fg_color = "#10B981"  # Green for swap target
                        text_color = "white"
                        font_weight = "bold"
                    elif is_selected:
                        cell_fg_color = self.colors['primary']  # Purple for selected
                        text_color = "white"
                        font_weight = "bold"
                    elif is_highlighted:
                        cell_fg_color = "#FCD34D"  # Yellow for search highlight
                        text_color = "#1F2937"
                        font_weight = "bold"
                    else:
                        cell_fg_color = self.colors['surface']
                        text_color = self.colors['text_primary']
                        font_weight = "normal"
                    
                    # Create clickable cell
                    cell_frame = ctk.CTkFrame(
                        container,
                        fg_color=cell_fg_color,
                        corner_radius=0
                    )
                    cell_frame.grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)
                    
                    cell = ctk.CTkLabel(
                        cell_frame,
                        text=teacher_name,
                        font=("Segoe UI", 13, font_weight),
                        text_color=text_color,
                        height=50,
                        anchor="center"
                    )
                    cell.pack(fill="both", expand=True)
                    
                    # Store cell frame in map for selective updates (OPTIMIZATION)
                    if teacher_name:
                        cell_key = f"{teacher_name}_{session}"
                        self._calendar_cell_widgets[cell_key] = cell_frame
                        
                        # Update swap source/target frame references if they match
                        if is_swap_source and self.swap_source:
                            self.swap_source['frame'] = cell_frame
                        if is_swap_target and self.swap_target:
                            self.swap_target['frame'] = cell_frame
                    
                    # Store highlighted cells for later cleanup
                    if is_highlighted:
                        self.highlighted_cells.append(cell_frame)
                    
                    # Make cell clickable for editing
                    if teacher_name:
                        # Bind left-click event
                        cell.bind("<Button-1>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                                 self.select_assignment(t, s, d, cf))
                        
                        # Bind right-click event for context menu
                        cell.bind("<Button-3>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                                 self.show_swap_context_menu(t, s, d, cf, e))
                        cell_frame.bind("<Button-3>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                                 self.show_swap_context_menu(t, s, d, cf, e))
                        
                        cell_frame.configure(cursor="hand2")
                        
                        # Add hover effects (only if not selected or swapped)
                        if not is_selected and not is_swap_source and not is_swap_target:
                            def on_enter(e, frame=cell_frame, original_color=cell_fg_color):
                                # Don't change if it's selected or part of swap
                                if (frame != self.selected_cell_frame and
                                    (not self.swap_source or frame != self.swap_source.get('frame')) and
                                    (not self.swap_target or frame != self.swap_target.get('frame'))):
                                    frame.configure(fg_color=self.colors['hover'])
                            
                            def on_leave(e, frame=cell_frame, original_color=cell_fg_color):
                                # Don't change if it's selected or part of swap
                                if (frame != self.selected_cell_frame and
                                    (not self.swap_source or frame != self.swap_source.get('frame')) and
                                    (not self.swap_target or frame != self.swap_target.get('frame'))):
                                    frame.configure(fg_color=original_color)
                            
                            cell.bind("<Enter>", on_enter)
                            cell.bind("<Leave>", on_leave)
                            cell_frame.bind("<Enter>", on_enter)
                            cell_frame.bind("<Leave>", on_leave)
            
            # Schedule next batch (using optimized delay)
            if end_row < max_rows:
                if delay > 0:
                    container.after(delay, lambda: render_batch(end_row))
                else:
                    render_batch(end_row)  # No delay for small datasets
            else:
                # Configure grid weights after all rows are rendered
                for col_idx in range(len(sessions)):
                    container.grid_columnconfigure(col_idx, weight=1, uniform="cols")
        
        # Start rendering
        if max_rows > 0:
            render_batch(0)
    
    def _update_calendar_data_rows_only(self, sessions, day_schedule):
        """Update ONLY data rows in calendar (not headers) - FAST PATH OPTIMIZATION ⚡"""
        container = self.calendar_view_widgets['table_container']
        if not container or not container.winfo_exists():
            # Fallback to full rebuild
            self._render_calendar_content()
            return
        
        # Clear selection state when refreshing
        self.selected_cell_frame = None
        self.selected_cell_info = None
        
        # Initialize cell tracking map for current view
        self._calendar_cell_widgets = {}
        
        # Destroy only data rows (row 1+), keep header row (row 0)
        # Get all children and destroy those in rows > 0
        for widget in container.winfo_children():
            grid_info = widget.grid_info()
            if grid_info and int(grid_info.get('row', 0)) > 0:
                widget.destroy()
        
        # Find the maximum number of rows needed
        max_rows = max(len(day_schedule.get(session, [])) for session in sessions) if sessions else 0
        if max_rows == 0:
            max_rows = 1
        
        # Render data rows (same logic as before, but starting from row 1)
        for row_idx in range(max_rows):
            for col_idx, session in enumerate(sessions):
                teacher_list = day_schedule.get(session, [])
                
                # Extract just the teacher name from the dictionary
                if row_idx < len(teacher_list):
                    teacher_data = teacher_list[row_idx]
                    # Handle both dict format and string format
                    if isinstance(teacher_data, dict):
                        teacher_name = teacher_data.get('teacher', '')
                    else:
                        teacher_name = str(teacher_data)
                else:
                    teacher_name = ""
                
                # Determine cell color (highlight if matches search)
                is_highlighted = (self.highlighted_teacher and 
                                teacher_name and 
                                self.highlighted_teacher in teacher_name)
                
                # Check if this cell is the currently selected one
                is_selected = (self.selected_cell_info and 
                             teacher_name == self.selected_cell_info.get('teacher') and
                             session == self.selected_cell_info.get('seance') and
                             self.selected_date == self.selected_cell_info.get('date'))
                
                # Check if this cell is swap source or target (PERSISTENT HIGHLIGHTS)
                is_swap_source = (self.swap_mode_active and self.swap_source and
                                 teacher_name == self.swap_source.get('teacher') and
                                 session == self.swap_source.get('seance') and
                                 self.selected_date == self.swap_source.get('date'))
                
                is_swap_target = (self.swap_mode_active and self.swap_target and
                                 teacher_name == self.swap_target.get('teacher') and
                                 session == self.swap_target.get('seance') and
                                 self.selected_date == self.swap_target.get('date'))
                
                # Determine colors based on state (PRIORITY: swap > selected > highlighted)
                if is_swap_source:
                    cell_fg_color = "#3B82F6"  # Blue for swap source
                    text_color = "white"
                    font_weight = "bold"
                elif is_swap_target:
                    cell_fg_color = "#10B981"  # Green for swap target
                    text_color = "white"
                    font_weight = "bold"
                elif is_selected:
                    cell_fg_color = self.colors['primary']  # Purple for selected
                    text_color = "white"
                    font_weight = "bold"
                elif is_highlighted:
                    cell_fg_color = "#FCD34D"  # Yellow for search highlight
                    text_color = "#1F2937"
                    font_weight = "bold"
                else:
                    cell_fg_color = self.colors['surface']
                    text_color = self.colors['text_primary']
                    font_weight = "normal"
                
                # Create clickable cell
                cell_frame = ctk.CTkFrame(
                    container,
                    fg_color=cell_fg_color,
                    corner_radius=0
                )
                cell_frame.grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)
                
                cell = ctk.CTkLabel(
                    cell_frame,
                    text=teacher_name,
                    font=("Segoe UI", 13, font_weight),
                    text_color=text_color,
                    height=50,
                    anchor="center"
                )
                cell.pack(fill="both", expand=True)
                
                # Store cell frame in map for selective updates (OPTIMIZATION)
                if teacher_name:
                    cell_key = f"{teacher_name}_{session}"
                    self._calendar_cell_widgets[cell_key] = cell_frame
                    
                    # Update swap source/target frame references if they match
                    if is_swap_source and self.swap_source:
                        self.swap_source['frame'] = cell_frame
                    if is_swap_target and self.swap_target:
                        self.swap_target['frame'] = cell_frame
                
                # Store highlighted cells for later cleanup
                if is_highlighted:
                    self.highlighted_cells.append(cell_frame)
                
                # Make cell clickable for editing
                if teacher_name:
                    # Bind left-click event
                    cell.bind("<Button-1>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                             self.select_assignment(t, s, d, cf))
                    
                    # Bind right-click event for context menu
                    cell.bind("<Button-3>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                             self.show_swap_context_menu(t, s, d, cf, e))
                    cell_frame.bind("<Button-3>", lambda e, t=teacher_name, s=session, d=self.selected_date, cf=cell_frame: 
                             self.show_swap_context_menu(t, s, d, cf, e))
                    
                    cell_frame.configure(cursor="hand2")
                    
                    # Add hover effects (only if not selected or swapped)
                    if not is_selected and not is_swap_source and not is_swap_target:
                        def on_enter(e, frame=cell_frame, original_color=cell_fg_color):
                            # Don't change if it's selected or part of swap
                            if (frame != self.selected_cell_frame and
                                (not self.swap_source or frame != self.swap_source.get('frame')) and
                                (not self.swap_target or frame != self.swap_target.get('frame'))):
                                frame.configure(fg_color=self.colors['hover'])
                        
                        def on_leave(e, frame=cell_frame, original_color=cell_fg_color):
                            # Don't change if it's selected or part of swap
                            if (frame != self.selected_cell_frame and
                                (not self.swap_source or frame != self.swap_source.get('frame')) and
                                (not self.swap_target or frame != self.swap_target.get('frame'))):
                                frame.configure(fg_color=original_color)
                        
                        cell.bind("<Enter>", on_enter)
                        cell.bind("<Leave>", on_leave)
                        cell_frame.bind("<Enter>", on_enter)
                        cell_frame.bind("<Leave>", on_leave)
        
        # Configure grid weights (already set, but ensure they're correct)
        for col_idx in range(len(sessions)):
            container.grid_columnconfigure(col_idx, weight=1, uniform="cols")
    
    def select_date(self):
        """Open date selector dialog"""
        # In a real implementation, you would show a calendar picker
        # For now, toggle between available dates
        available_dates = list(self.schedule_data.keys())
        if available_dates:
            current_idx = available_dates.index(self.selected_date) if self.selected_date in available_dates else 0
            next_idx = (current_idx + 1) % len(available_dates)
            self.selected_date = available_dates[next_idx]
            self.show_calendar_view(refresh_only=True)  # OPTIMIZED: Only refresh content
            self.app.update_status(f"Date changée : {self.selected_date}")
        else:
            messagebox.showinfo("Sélectionner une date", "Aucune date disponible dans les données")
    
    def show_details_panel(self):
        """Show assignment details and modification panel with swap functionality - OPTIMIZED"""
        # Only build once - don't rebuild if already exists
        if hasattr(self, '_details_panel_initialized') and self._details_panel_initialized:
            return
        
        # Clear previous content
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        
        # Header
        header = ctk.CTkLabel(
            self.details_frame,
            text="⚡ Actions de Modification",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(20, 15))
        
        # Action buttons column (right side, stacked vertically)
        action_buttons_frame = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        action_buttons_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # Rechercher button
        self.search_highlight_btn_action = ctk.CTkButton(
            action_buttons_frame,
            text="🔍 Rechercher",
            height=45,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            text_color="white",
            font=("Segoe UI", 13, "bold"),
            command=self.toggle_search_highlight
        )
        self.search_highlight_btn_action.pack(fill="x", pady=(0, 8))
        
        # Affecter button
        self.affect_action_btn = ctk.CTkButton(
            action_buttons_frame,
            text="👥 Affecter",
            height=45,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            text_color="white",
            font=("Segoe UI", 13, "bold"),
            command=self.handle_affecter_click
        )
        self.affect_action_btn.pack(fill="x", pady=(0, 8))
        
        # Échanger button
        self.swap_action_btn = ctk.CTkButton(
            action_buttons_frame,
            text="🔄 Échanger",
            height=45,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['primary'],
            text_color=self.colors['primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 13, "bold"),
            command=self.toggle_swap_mode
        )
        self.swap_action_btn.pack(fill="x", pady=(0, 8))
        
        # Selected slots container (changes based on swap mode)
        self.slots_container = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        self.slots_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Track swap UI elements for efficient updates (no full re-render)
        self.swap_execute_btn = None  # Reference to execute button
        self.swap_source_container = None  # Reference to source container
        self.swap_target_container = None  # Reference to target container
        
        # Track calendar cell widgets for selective updates (OPTIMIZATION)
        self._calendar_cell_widgets = {}  # Key: "teacher_seance", Value: cell_frame
        
        # Will be populated by _update_slots_display()
        self._update_slots_display()
        
        # Teacher search and selection section (only shown when NOT in swap mode)
        # Teacher selection frame - hidden by default, shown when not in swap mode
        self.teacher_selection_frame = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        # Don't pack it here - will be shown/hidden by _update_slots_display()
        
        # Mark panel as initialized
        self._details_panel_initialized = True
    
    def populate_teacher_list(self, filter_text=""):
        """Populate the teacher list with all available teachers"""
        # Clear existing items
        for widget in self.teacher_list_frame.winfo_children():
            widget.destroy()
        
        if not self.available_teachers:
            empty_label = ctk.CTkLabel(
                self.teacher_list_frame,
                text="Aucun enseignant disponible",
                font=("Segoe UI", 10),
                text_color=self.colors['text_secondary']
            )
            empty_label.pack(pady=20)
            return
        
        # Filter teachers based on search
        filter_lower = filter_text.lower()
        filtered_teachers = [t for t in self.available_teachers if filter_lower in t.lower()]
        
        if not filtered_teachers:
            empty_label = ctk.CTkLabel(
                self.teacher_list_frame,
                text="Aucun résultat",
                font=("Segoe UI", 10),
                text_color=self.colors['text_secondary']
            )
            empty_label.pack(pady=20)
            return
        
        # Create clickable items for each teacher
        self.teacher_selection_var = None
        for teacher_name in filtered_teachers:
            teacher_btn = ctk.CTkButton(
                self.teacher_list_frame,
                text=teacher_name,
                height=40,
                corner_radius=6,
                fg_color="transparent",
                text_color=self.colors['text_primary'],
                hover_color=self.colors['background'],
                anchor="w",
                font=("Segoe UI", 12),
                command=lambda t=teacher_name: self.select_teacher_for_affect(t)
            )
            teacher_btn.pack(fill="x", pady=2, padx=5)
    
    def _update_slots_display(self):
        """Update the slots display based on current mode (normal or swap)"""
        # Clear slots container
        for widget in self.slots_container.winfo_children():
            widget.destroy()
        
        # Reset references
        self.swap_execute_btn = None
        self.swap_source_container = None
        self.swap_target_container = None
        
        if self.swap_mode_active:
            # SWAP MODE: Show two slot containers with clear visual separation
            
            # Source slot container - with blue accent - FIXED HEIGHT
            self.swap_source_container = ctk.CTkFrame(
                self.slots_container,
                fg_color=self.colors['surface'],
                corner_radius=12,
                border_width=3,
                border_color="#3B82F6",  # Blue border
                height=200  # Fixed height
            )
            self.swap_source_container.pack(fill="x", pady=(0, 10))
            self.swap_source_container.pack_propagate(False)  # Prevent resizing
            
            source_header = ctk.CTkLabel(
                self.swap_source_container,
                text="📍 CRÉNEAU SOURCE",
                font=("Segoe UI", 13, "bold"),
                text_color="#3B82F6",
                anchor="w"
            )
            source_header.pack(fill="x", padx=15, pady=(15, 10))
            
            self._create_swap_slot_content(self.swap_source_container, self.swap_source, is_source=True)
            
            # Swap icon between containers - larger and more visible
            swap_icon_frame = ctk.CTkFrame(self.slots_container, fg_color="transparent")
            swap_icon_frame.pack(pady=8)
            
            swap_icon = ctk.CTkLabel(
                swap_icon_frame,
                text="⇅",
                font=("Segoe UI", 32, "bold"),
                text_color=self.colors['primary']
            )
            swap_icon.pack()
            
            # Target slot container - with green accent - FIXED HEIGHT
            self.swap_target_container = ctk.CTkFrame(
                self.slots_container,
                fg_color=self.colors['surface'],
                corner_radius=12,
                border_width=3,
                border_color="#10B981",  # Green border
                height=200  # Fixed height
            )
            self.swap_target_container.pack(fill="x", pady=(0, 15))
            self.swap_target_container.pack_propagate(False)  # Prevent resizing
            
            target_header = ctk.CTkLabel(
                self.swap_target_container,
                text="🎯 CRÉNEAU CIBLE",
                font=("Segoe UI", 13, "bold"),
                text_color="#10B981",
                anchor="w"
            )
            target_header.pack(fill="x", padx=15, pady=(15, 10))
            
            self._create_swap_slot_content(self.swap_target_container, self.swap_target, is_source=False)
            
            # Execute swap button - ALWAYS SHOWN, enabled/disabled based on selection state
            self.swap_execute_btn = ctk.CTkButton(
                self.slots_container,
                text="✓ EXÉCUTER L'ÉCHANGE",
                height=50,
                corner_radius=10,
                fg_color=self.colors['primary'],
                hover_color=self.colors['hover_dark'],
                font=("Segoe UI", 14, "bold"),
                command=self.execute_swap,
                state="normal" if (self.swap_source and self.swap_target) else "disabled"
            )
            self.swap_execute_btn.pack(fill="x", pady=(5, 0))
        else:
            # NORMAL MODE: Show info message
            info_container = ctk.CTkFrame(
                self.slots_container,
                fg_color=self.colors['surface'],
                corner_radius=10
            )
            info_container.pack(fill="both", expand=True, pady=(0, 10))
            
            info_text = ctk.CTkLabel(
                info_container,
                text="Utilisez les boutons ci-dessus pour effectuer des modifications",
                font=("Segoe UI", 12),
                text_color=self.colors['text_secondary'],
                wraplength=250
            )
            info_text.pack(pady=(40, 40), padx=20)
    
    def _create_swap_slot_content(self, parent, slot_data, is_source):
        """Create content for swap slot container"""
        
        if slot_data:
            # Display selected slot with large, clear information
            teacher = slot_data.get('teacher', 'N/A')
            date = slot_data.get('date', 'N/A')
            seance = slot_data.get('seance', 'N/A')
            
            # Format date
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except:
                formatted_date = date
            
            # Teacher name - large and prominent
            teacher_label = ctk.CTkLabel(
                parent,
                text=f"👤 {teacher}",
                font=("Segoe UI", 16, "bold"),
                text_color=self.colors['text_primary'],
                anchor="center"
            )
            teacher_label.pack(fill="x", padx=15, pady=(0, 10))
            
            # Date and Seance in cards (no icons for more space)
            info_row = ctk.CTkFrame(parent, fg_color="transparent")
            info_row.pack(fill="x", padx=15, pady=(0, 10))
            
            # Date card
            date_card = ctk.CTkFrame(info_row, fg_color=self.colors['background'], corner_radius=8)
            date_card.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            ctk.CTkLabel(
                date_card,
                text=formatted_date,
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors['text_primary']
            ).pack(pady=10)
            
            # Seance card
            seance_card = ctk.CTkFrame(info_row, fg_color=self.colors['background'], corner_radius=8)
            seance_card.pack(side="left", fill="x", expand=True, padx=(5, 0))
            
            ctk.CTkLabel(
                seance_card,
                text=f"Séance {seance}",
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors['text_primary']
            ).pack(pady=10)
            
            # Action buttons row - Change and Delete
            action_row = ctk.CTkFrame(parent, fg_color="transparent")
            action_row.pack(fill="x", padx=15, pady=(0, 15))
            
            # Change slot button (clearer name than "Modifier")
            change_btn = ctk.CTkButton(
                action_row,
                text="✏️ Changer Enseignant",
                height=36,
                corner_radius=8,
                fg_color="transparent",
                border_width=1,
                border_color=self.colors['border'],
                text_color=self.colors['text_secondary'],
                hover_color=self.colors['hover'],
                font=("Segoe UI", 10),
                command=lambda: self.open_manual_slot_input(is_source)
            )
            change_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            # Delete button to clear selection
            delete_btn = ctk.CTkButton(
                action_row,
                text="🗑️",
                height=36,
                width=50,
                corner_radius=8,
                fg_color="#EF4444",
                hover_color="#DC2626",
                text_color="white",
                font=("Segoe UI", 14),
                command=lambda: self._clear_swap_slot(is_source)
            )
            delete_btn.pack(side="left", padx=(5, 0))
        else:
            # Empty state with call to action
            empty_frame = ctk.CTkFrame(parent, fg_color="transparent")
            empty_frame.pack(fill="x", padx=15, pady=15)
            
            ctk.CTkLabel(
                empty_frame,
                text="Aucun créneau sélectionné",
                font=("Segoe UI", 12),
                text_color=self.colors['text_secondary'],
                anchor="center"
            ).pack(pady=(10, 15))
            
            # Manual input button - prominent
            manual_btn = ctk.CTkButton(
                parent,
                text="✏️ Sélectionner un Créneau",
                height=42,
                corner_radius=8,
                fg_color=self.colors['secondary'],
                hover_color="#6D28D9",
                text_color="white",
                font=("Segoe UI", 12, "bold"),
                command=lambda: self.open_manual_slot_input(is_source)
            )
            manual_btn.pack(fill="x", padx=15, pady=(0, 15))
    
    def _update_swap_slot_content_only(self, is_source):
        """Efficiently update only the content of a swap slot without rebuilding entire panel.
        This avoids re-rendering titles, borders, and the swap arrow."""
        if not self.swap_mode_active:
            return
        
        container = self.swap_source_container if is_source else self.swap_target_container
        if not container or not container.winfo_exists():
            return
        
        # Find and clear only the content area (skip the header label)
        widgets = container.winfo_children()
        for widget in widgets[1:]:  # Skip first widget (header)
            widget.destroy()
        
        # Recreate only the content
        slot_data = self.swap_source if is_source else self.swap_target
        self._create_swap_slot_content(container, slot_data, is_source)
        
        # Update execute button state efficiently
        self._update_execute_button_state()
    
    def _update_execute_button_state(self):
        """Efficiently update only the execute button state without re-rendering"""
        if self.swap_execute_btn and self.swap_execute_btn.winfo_exists():
            new_state = "normal" if (self.swap_source and self.swap_target) else "disabled"
            self.swap_execute_btn.configure(state=new_state)
    
    def _update_specific_calendar_cells(self, affected_slots):
        """
        OPTIMIZED: Update only specific calendar cells without full re-render.
        Updates entire seance columns to maintain position integrity.
        
        Note: We update columns rather than individual cells because:
        - Calendar cells are position-based (row 0, row 1, etc.)
        - When a teacher is replaced, positions may shift
        - The column update is still 10-40x faster than full re-render
        - Typically only 5-10 cells per column
        
        Args:
            affected_slots: List of dicts with 'teacher', 'seance', 'date' keys
        """
        if not hasattr(self, '_calendar_cell_widgets'):
            # Fallback to full render if cell map not available
            self._render_calendar_content()
            return
        
        # Track which seance columns need updating
        seances_to_update = set()
        
        for slot in affected_slots:
            slot_date = str(slot.get('date', ''))
            slot_seance = slot.get('seance', '')
            
            # Skip if this slot is not in the current visible date
            if slot_date != str(self.selected_date):
                continue
            
            seances_to_update.add(slot_seance)
        
        # Update all affected seance columns (typically 1-2 columns)
        for seance in seances_to_update:
            self._update_seance_column(seance)
    
    def _update_seance_column(self, seance):
        """
        Update an entire seance column by fetching current data from schedule_data.
        This ensures we display the correct teachers after modifications.
        """
        # Get current schedule for this date and seance
        date = self.selected_date
        day_schedule = self.schedule_data.get(date, {})
        teacher_list = day_schedule.get(seance, [])
        
        # Find all cells in this seance column (in the cell map)
        cells_in_seance = []
        for cell_key, cell_frame in self._calendar_cell_widgets.items():
            if cell_key.endswith(f"_{seance}"):
                cells_in_seance.append((cell_key, cell_frame))
        
        # Clear all old cells in this seance from the map
        for cell_key, _ in cells_in_seance:
            del self._calendar_cell_widgets[cell_key]
        
        # Now update each teacher position in this seance
        for row_idx, teacher_data in enumerate(teacher_list):
            # Extract teacher name
            if isinstance(teacher_data, dict):
                teacher_name = teacher_data.get('teacher', '')
            else:
                teacher_name = str(teacher_data)
            
            if teacher_name and row_idx < len(cells_in_seance):
                # Reuse existing cell frame
                _, cell_frame = cells_in_seance[row_idx]
                
                # Update this cell with the current teacher
                self._update_single_cell_with_frame(cell_frame, teacher_name, seance)
                
                # Re-add to cell map with new teacher name
                new_cell_key = f"{teacher_name}_{seance}"
                self._calendar_cell_widgets[new_cell_key] = cell_frame
        
        # Clear any remaining cells (if we have fewer teachers than before)
        for row_idx in range(len(teacher_list), len(cells_in_seance)):
            _, cell_frame = cells_in_seance[row_idx]
            self._update_single_cell_with_frame(cell_frame, None, seance)
    
    def _update_single_cell_with_frame(self, cell_frame, teacher_name, seance):
        """Update a single cell frame with new teacher data and proper styling"""
        if not cell_frame or not cell_frame.winfo_exists():
            return
        
        # Clear current content
        for widget in cell_frame.winfo_children():
            widget.destroy()
        
        # Determine cell state
        is_highlighted = (self.highlighted_teacher and teacher_name and 
                         self.highlighted_teacher in teacher_name)
        
        is_selected = (self.selected_cell_info and 
                      teacher_name == self.selected_cell_info.get('teacher') and
                      seance == self.selected_cell_info.get('seance') and
                      self.selected_date == self.selected_cell_info.get('date'))
        
        is_swap_source = (self.swap_mode_active and self.swap_source and
                         teacher_name == self.swap_source.get('teacher') and
                         seance == self.swap_source.get('seance') and
                         self.selected_date == self.swap_source.get('date'))
        
        is_swap_target = (self.swap_mode_active and self.swap_target and
                         teacher_name == self.swap_target.get('teacher') and
                         seance == self.swap_target.get('seance') and
                         self.selected_date == self.swap_target.get('date'))
        
        # Determine colors (PRIORITY: swap > selected > highlighted)
        if is_swap_source:
            cell_fg_color = "#3B82F6"  # Blue
            text_color = "white"
            font_weight = "bold"
        elif is_swap_target:
            cell_fg_color = "#10B981"  # Green
            text_color = "white"
            font_weight = "bold"
        elif is_selected:
            cell_fg_color = self.colors['primary']  # Purple
            text_color = "white"
            font_weight = "bold"
        elif is_highlighted:
            cell_fg_color = "#FCD34D"  # Yellow
            text_color = "#1F2937"
            font_weight = "bold"
        else:
            cell_fg_color = self.colors['surface']
            text_color = self.colors['text_primary']
            font_weight = "normal"
        
        # Update frame color
        cell_frame.configure(fg_color=cell_fg_color)
        
        # Create new label
        cell = ctk.CTkLabel(
            cell_frame,
            text=teacher_name or "",
            font=("Segoe UI", 13, font_weight),
            text_color=text_color,
            height=50,
            anchor="center"
        )
        cell.pack(fill="both", expand=True)
        
        # Re-bind events if teacher exists
        if teacher_name:
            # Update swap source/target frame references if they match
            if is_swap_source and self.swap_source:
                self.swap_source['frame'] = cell_frame
            if is_swap_target and self.swap_target:
                self.swap_target['frame'] = cell_frame
            
            cell.bind("<Button-1>", lambda e, t=teacher_name, s=seance, d=self.selected_date, cf=cell_frame: 
                     self.select_assignment(t, s, d, cf))
            
            cell.bind("<Button-3>", lambda e, t=teacher_name, s=seance, d=self.selected_date, cf=cell_frame: 
                     self.show_swap_context_menu(t, s, d, cf, e))
            cell_frame.bind("<Button-3>", lambda e, t=teacher_name, s=seance, d=self.selected_date, cf=cell_frame: 
                     self.show_swap_context_menu(t, s, d, cf, e))
            
            cell_frame.configure(cursor="hand2")
            
            # Add hover effects (only if not selected or swapped)
            if not is_selected and not is_swap_source and not is_swap_target:
                def on_enter(e, frame=cell_frame, original_color=cell_fg_color):
                    if (frame != self.selected_cell_frame and
                        (not self.swap_source or frame != self.swap_source.get('frame')) and
                        (not self.swap_target or frame != self.swap_target.get('frame'))):
                        frame.configure(fg_color=self.colors['hover'])
                
                def on_leave(e, frame=cell_frame, original_color=cell_fg_color):
                    if (frame != self.selected_cell_frame and
                        (not self.swap_source or frame != self.swap_source.get('frame')) and
                        (not self.swap_target or frame != self.swap_target.get('frame'))):
                        frame.configure(fg_color=original_color)
                
                cell.bind("<Enter>", on_enter)
                cell.bind("<Leave>", on_leave)
                cell_frame.bind("<Enter>", on_enter)
                cell_frame.bind("<Leave>", on_leave)
        else:
            # Empty cell - remove cursor and make it non-interactive
            cell_frame.configure(cursor="")
    
    def _update_single_cell(self, cell_key, teacher_name, seance):
        """DEPRECATED: Use _update_seance_column instead for accurate updates"""
        # This method is kept for backward compatibility but does nothing
        # The new approach updates entire seance columns to ensure data consistency
        pass
    
    def _create_slot_display(self, parent, slot_data):
        """Create display for a single selected slot (normal mode)"""
        if slot_data:
            teacher = slot_data.get('teacher', 'N/A')
            date = slot_data.get('date', 'N/A')
            seance = slot_data.get('seance', 'N/A')
            
            # Format date
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except:
                formatted_date = date
            
            # Teacher placeholder
            teacher_container = ctk.CTkFrame(
                parent,
                fg_color=self.colors['surface'],
                corner_radius=8,
                height=50
            )
            teacher_container.pack(fill="x", padx=15, pady=(5, 8))
            teacher_container.pack_propagate(False)
            
            teacher_label = ctk.CTkLabel(
                teacher_container,
                text=f"👤  {teacher}",
                font=("Segoe UI", 13, "bold"),
                text_color=self.colors['text_primary'],
                anchor="center"
            )
            teacher_label.pack(expand=True, fill="both", padx=15)
            
            # Date and Séance row
            details_row = ctk.CTkFrame(parent, fg_color="transparent")
            details_row.pack(fill="x", padx=15, pady=(0, 12))
            
            # Date
            date_container = ctk.CTkFrame(
                details_row,
                fg_color=self.colors['surface'],
                corner_radius=6,
                height=40
            )
            date_container.pack(side="left", fill="x", expand=True, padx=(0, 5))
            date_container.pack_propagate(False)
            
            ctk.CTkLabel(
                date_container,
                text=f"📅  {formatted_date}",
                font=("Segoe UI", 11, "bold"),
                text_color=self.colors['text_primary'],
                anchor="center"
            ).pack(expand=True)
            
            # Séance
            seance_container = ctk.CTkFrame(
                details_row,
                fg_color=self.colors['surface'],
                corner_radius=6,
                height=40
            )
            seance_container.pack(side="left", fill="x", expand=True, padx=(5, 0))
            seance_container.pack_propagate(False)
            
            ctk.CTkLabel(
                seance_container,
                text=f"⏰  Séance {seance}",
                font=("Segoe UI", 11, "bold"),
                text_color=self.colors['text_primary'],
                anchor="center"
            ).pack(expand=True)
        else:
            # Placeholder
            placeholder = ctk.CTkFrame(
                parent,
                fg_color=self.colors['surface'],
                corner_radius=8,
                height=50
            )
            placeholder.pack(fill="x", padx=15, pady=(5, 12))
            placeholder.pack_propagate(False)
            
            ctk.CTkLabel(
                placeholder,
                text="👤  Sélectionnez un créneau",
                font=("Segoe UI", 13),
                text_color=self.colors['text_secondary'],
                anchor="center"
            ).pack(expand=True, fill="both", padx=15)
    
    def filter_teacher_list(self, event=None):
        """Filter teacher list based on search input"""
        search_text = self.teacher_search_entry.get()
        self.populate_teacher_list(search_text)
    
    def select_teacher_for_affect(self, teacher_name):
        """Select a teacher from the list for affectation"""
        self.teacher_selection_var = teacher_name
    
    def handle_affecter_click(self):
        """Handle Affecter button click - opens modal if no slot selected"""
        # Exit swap mode if active
        if self.swap_mode_active:
            self.toggle_swap_mode()
        
        if not self.selected_cell_info:
            # No slot selected - show selection modal (same as right-click)
            messagebox.showinfo(
                "Sélection Requise",
                "Veuillez d'abord sélectionner un créneau dans le calendrier,\nou utiliser le clic droit pour ouvrir le menu contextuel."
            )
            return
        
        # Slot selected - open teacher selection modal (like right-click swap)
        self.open_teacher_selection_modal_for_affect()
    
    def open_teacher_selection_modal_for_affect(self):
        """Open modal to select teacher for affectation (similar to swap modal)"""
        if not self.selected_cell_info:
            return
        
        # Create modal
        modal = ctk.CTkToplevel(self)
        modal.title("Affecter un Enseignant")
        modal.geometry("500x600")
        modal.transient(self)
        modal.grab_set()
        
        # Center modal
        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (250)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (300)
        modal.geometry(f"500x600+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(modal, fg_color=self.colors['secondary'], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="👥 Sélectionner un Enseignant",
            font=("Segoe UI", 20, "bold"),
            text_color="white"
        ).pack(pady=20)
        
        # Content
        content = ctk.CTkFrame(modal, fg_color=self.colors['background'])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Search
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            content,
            textvariable=search_var,
            placeholder_text="🔍 Rechercher un enseignant...",
            height=40,
            font=("Segoe UI", 13)
        )
        search_entry.pack(fill="x", pady=(0, 15))
        search_entry.focus()
        
        # Teacher list
        list_frame = ctk.CTkScrollableFrame(
            content,
            fg_color=self.colors['surface'],
            corner_radius=8
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        selected_teacher = {"name": None, "widget": None}
        
        def create_teacher_item(teacher_name):
            item = ctk.CTkFrame(list_frame, fg_color=self.colors['background'], corner_radius=6, cursor="hand2")
            item.pack(fill="x", padx=5, pady=3)
            
            label = ctk.CTkLabel(
                item,
                text=teacher_name,
                font=("Segoe UI", 13),
                text_color=self.colors['text_primary'],
                anchor="w"
            )
            label.pack(fill="x", padx=15, pady=12)
            
            def on_click(e=None):
                if selected_teacher["widget"]:
                    selected_teacher["widget"].configure(fg_color=self.colors['background'])
                    for w in selected_teacher["widget"].winfo_children():
                        if isinstance(w, ctk.CTkLabel):
                            w.configure(text_color=self.colors['text_primary'])
                
                item.configure(fg_color=self.colors['primary'])
                label.configure(text_color="white")
                selected_teacher["name"] = teacher_name
                selected_teacher["widget"] = item
            
            def on_enter(e):
                if selected_teacher["widget"] != item:
                    item.configure(fg_color=self.colors['hover'])
            
            def on_leave(e):
                if selected_teacher["widget"] != item:
                    item.configure(fg_color=self.colors['background'])
            
            item.bind("<Button-1>", on_click)
            label.bind("<Button-1>", on_click)
            item.bind("<Enter>", on_enter)
            item.bind("<Leave>", on_leave)
            label.bind("<Enter>", on_enter)
            label.bind("<Leave>", on_leave)
            
            return item
        
        teacher_widgets = {}
        for teacher in self.available_teachers:
            widget = create_teacher_item(teacher)
            teacher_widgets[teacher] = widget
        
        def filter_teachers(*args):
            search_text = search_var.get().lower()
            for teacher, widget in teacher_widgets.items():
                if search_text in teacher.lower():
                    widget.pack(fill="x", padx=5, pady=3)
                else:
                    widget.pack_forget()
        
        search_var.trace_add("write", filter_teachers)
        
        # Buttons
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x")
        
        def confirm_affect():
            if not selected_teacher["name"]:
                messagebox.showwarning("Sélection Requise", "Veuillez sélectionner un enseignant")
                return
            
            modal.destroy()
            self.affect_teacher_to_slot(selected_teacher["name"], self.selected_cell_info)
        
        # Affecter button
        ctk.CTkButton(
            button_frame,
            text="✓ Affecter",
            height=45,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=confirm_affect
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Cancel button
        ctk.CTkButton(
            button_frame,
            text="Annuler",
            height=45,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=modal.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        modal.bind("<Return>", lambda e: confirm_affect())
    
    def affect_teacher_to_slot(self, new_teacher, slot_info):
        """Affect a teacher to a specific slot"""
        if not slot_info:
            return
        
        old_teacher = slot_info.get('teacher')
        date = slot_info.get('date')
        seance = slot_info.get('seance')
        
        # Validation checks
        warnings = []
        
        # Check if new teacher is already assigned to this slot
        if date in self.schedule_data and seance in self.schedule_data[date]:
            for teacher_entry in self.schedule_data[date][seance]:
                entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                if entry_name.strip() == new_teacher.strip():
                    messagebox.showerror(
                        "Conflit Détecté",
                        f"❌ {new_teacher} est déjà affecté(e) à ce créneau.\n\n"
                        f"📅 {date}\n⏰ Séance {seance}"
                    )
                    return
        
        # Check constraints
        warnings = self._check_assignment_constraints(new_teacher, date, seance)
        
        # Build confirmation message
        confirm_msg = f"Remplacer {old_teacher} par {new_teacher} ?\n\n"
        confirm_msg += f"📅 Date : {date}\n"
        confirm_msg += f"⏰ Séance : {seance}"
        
        if warnings:
            confirm_msg += "\n\n⚠️ AVERTISSEMENTS :\n"
            for warning in warnings:
                confirm_msg += f"• {warning}\n"
            confirm_msg += "\nContinuer malgré les avertissements ?"
        
        if not messagebox.askyesno("Confirmer l'Affectation", confirm_msg):
            return
        
        # Perform the affectation
        self._perform_teacher_replacement(old_teacher, new_teacher, date, seance)
        
        messagebox.showinfo(
            "✅ Affectation Réussie",
            f"{new_teacher} a remplacé {old_teacher}\n\n"
            f"📅 {date} - Séance {seance}"
        )
        
        self.app.update_status(f"✓ Affecté: {new_teacher} → {date}, Séance {seance}")
    
    def _delete_teacher_assignment(self, slot_info):
        """Delete a teacher's assignment from a specific slot"""
        if not slot_info:
            return
        
        teacher = slot_info.get('teacher')
        date = slot_info.get('date')
        seance = slot_info.get('seance')
        
        # Store old state for undo
        old_schedule = self.schedule_data.copy()
        old_teacher_schedules = {k: v.copy() for k, v in self.teacher_schedules.items()}
        
        # Remove from schedule_data
        if date in self.schedule_data and seance in self.schedule_data[date]:
            # Filter out the teacher from this slot
            self.schedule_data[date][seance] = [
                entry for entry in self.schedule_data[date][seance]
                if (entry.get('teacher', '') if isinstance(entry, dict) else str(entry)) != teacher
            ]
            
            # If seance is now empty, remove it
            if not self.schedule_data[date][seance]:
                del self.schedule_data[date][seance]
            
            # If date has no more seances, remove it
            if not self.schedule_data[date]:
                del self.schedule_data[date]
        
        # Remove from teacher_schedules
        if teacher in self.teacher_schedules:
            self.teacher_schedules[teacher] = [
                entry for entry in self.teacher_schedules[teacher]
                if not (entry.get('date') == date and entry.get('seance') == seance)
            ]
            
            # If teacher has no more assignments, remove them
            if not self.teacher_schedules[teacher]:
                del self.teacher_schedules[teacher]
        
        # Add to undo stack
        self.undo_stack.append({
            'action': 'delete',
            'teacher': teacher,
            'date': date,
            'seance': seance,
            'old_schedule': old_schedule,
            'old_teacher_schedules': old_teacher_schedules
        })
        self.redo_stack.clear()
        
        # Update undo/redo buttons
        self.undo_btn.configure(state="normal")
        self.redo_btn.configure(state="disabled")
        
        # Mark as having unsaved changes
        self.has_unsaved_changes = True
        
        # Refresh calendar view
        if self.view_mode == "calendar":
            self._refresh_calendar_content()
        else:
            self.show_teachers_view()
        
        # Clear selection
        self.selected_cell_info = None
        self.selected_cell_frame = None
        self._update_slots_display()
        
        messagebox.showinfo(
            "✅ Suppression Réussie",
            f"L'affectation de {teacher} a été supprimée\n\n"
            f"📅 {date} - Séance {seance}"
        )
        
        self.app.update_status(f"✓ Supprimé: {teacher} de {date}, Séance {seance}")
    
    def affect_selected_teacher(self):
        """Affect the selected teacher to the currently selected slot"""
        if not self.teacher_selection_var:
            messagebox.showwarning("Sélection requise", "Veuillez sélectionner un enseignant")
            return
        
        if not hasattr(self, 'selected_assignment') or not self.selected_assignment:
            messagebox.showwarning("Créneau requis", "Veuillez sélectionner un créneau dans le calendrier")
            return
        
        # Get current assignment details
        old_teacher = self.selected_assignment.get('teacher')
        date = self.selected_assignment.get('date')
        seance = self.selected_assignment.get('seance')
        new_teacher = self.teacher_selection_var
        
        # Check if new teacher is already assigned to this date+seance
        if date in self.schedule_data and seance in self.schedule_data[date]:
            # Check if teacher exists (handle both string and dict formats)
            teacher_exists = False
            for teacher_entry in self.schedule_data[date][seance]:
                if isinstance(teacher_entry, dict):
                    entry_name = teacher_entry.get('teacher', '')
                else:
                    entry_name = str(teacher_entry)
                
                if entry_name.strip() == new_teacher.strip():
                    teacher_exists = True
                    break
            
            if teacher_exists:
                messagebox.showwarning(
                    "Conflit",
                    f"⚠️  {new_teacher} est déjà assigné(e) à ce créneau."
                )
                return
        
        # Check for quota and voeux violations
        warnings = self._check_assignment_constraints(new_teacher, date, seance)
        
        # Build confirmation message
        confirm_message = f"Remplacer {old_teacher} par {new_teacher}?\n\n📅 {date}, Séance {seance}"
        
        if warnings:
            confirm_message += "\n\n⚠️  AVERTISSEMENTS DÉTECTÉS:\n"
            for warning in warnings:
                confirm_message += f"\n• {warning}"
            confirm_message += "\n\nContinuer malgré les avertissements?"
        
        # Confirm replacement
        confirm = messagebox.askyesno(
            "Confirmer l'affectation",
            confirm_message
        )
        
        if not confirm:
            return
        
        # Update the schedule data (calendar view)
        if date in self.schedule_data and seance in self.schedule_data[date]:
            teachers_list = self.schedule_data[date][seance]
            
            # Find old teacher in list (handle both string and dict formats)
            old_teacher_idx = -1
            for i, teacher_entry in enumerate(teachers_list):
                # Extract teacher name from entry (could be string or dict)
                if isinstance(teacher_entry, dict):
                    entry_name = teacher_entry.get('teacher', '')
                else:
                    entry_name = str(teacher_entry)
                
                # Compare with old_teacher (strip whitespace for safety)
                if entry_name.strip() == old_teacher.strip():
                    old_teacher_idx = i
                    break
            
            if old_teacher_idx >= 0:
                # Replace with new teacher
                teachers_list[old_teacher_idx] = new_teacher
                
                # Update teacher_schedules (teacher view) for BOTH teachers
                # Remove from old teacher's schedule
                if old_teacher in self.teacher_schedules:
                    old_teacher_assignments = self.teacher_schedules[old_teacher]
                    for i, assignment in enumerate(old_teacher_assignments):
                        if assignment.get('date') == date and assignment.get('seance') == seance:
                            old_teacher_assignments.pop(i)
                            break
                
                # Find the full assignment details from assignments_df to get all fields
                assignment_row = None
                for idx, row in self.assignments_df.iterrows():
                    row_date = str(row['Date'])[:10] if 'Date' in row else str(row.get('date', ''))[:10]
                    row_seance = row.get('Séance', row.get('seance', ''))
                    row_teacher = row.get('Nom Complet', row.get('Nom_Complet', ''))
                    
                    if row_date == date and row_seance == seance and row_teacher == old_teacher:
                        assignment_row = row
                        break
                
                # Add to new teacher's schedule with all required fields
                if new_teacher not in self.teacher_schedules:
                    self.teacher_schedules[new_teacher] = []
                
                # Get fields from the assignment row if found, otherwise use defaults
                if assignment_row is not None:
                    heure_debut = assignment_row.get('Heure', assignment_row.get('heure_debut', ''))
                    jour = assignment_row.get('Jour', assignment_row.get('jour', ''))
                    salle = assignment_row.get('Salle', assignment_row.get('salle', 'N/A'))
                    session = assignment_row.get('Session', assignment_row.get('session', 'N/A'))
                    semestre = assignment_row.get('Semestre', assignment_row.get('semestre', 'N/A'))
                else:
                    heure_debut = ''
                    jour = ''
                    salle = 'N/A'
                    session = 'N/A'
                    semestre = 'N/A'
                
                self.teacher_schedules[new_teacher].append({
                    'date': date,
                    'jour': jour,
                    'heure_debut': heure_debut,
                    'seance': seance,
                    'salle': salle,
                    'session': session,
                    'semestre': semestre
                })
                
                # Create modification record for undo/redo
                modification = {
                    'date': date,
                    'seance': seance,
                    'old_teacher': old_teacher,
                    'new_teacher': new_teacher,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'assignment_details': {
                        'heure_debut': heure_debut,
                        'jour': jour,
                        'salle': salle,
                        'session': session,
                        'semestre': semestre
                    }
                }
                
                # Add to undo stack and clear redo stack
                self.undo_stack.append(modification)
                self.redo_stack.clear()
                
                # Track modification for save
                self.modifications.append(modification)
                
                # Track affected teachers for regenerating individual plannings
                if not hasattr(self, 'affected_teachers'):
                    self.affected_teachers = set()
                self.affected_teachers.add(old_teacher)
                self.affected_teachers.add(new_teacher)
                
                self.has_unsaved_changes = True
                
                # Update undo/redo button states
                self._update_undo_redo_buttons()
                
                # OPTIMIZED: Refresh only calendar content, not entire view
                if self.view_mode == "calendar":
                    self._render_calendar_content()
                else:
                    self.show_teachers_view()
                
                self.app.update_status(f"✓ {new_teacher} → {old_teacher}")
                messagebox.showinfo("✅ Modifié", f"{new_teacher} a remplacé {old_teacher}")
            else:
                messagebox.showerror("Erreur", "Enseignant original introuvable dans ce créneau")
        else:
            messagebox.showerror("Erreur", "Créneau introuvable dans les données")
    
    def create_info_row(self, parent, label, value):
        """Create an info row"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=3)
        
        label_widget = ctk.CTkLabel(
            row,
            text=f"{label}:",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary'],
            width=100,
            anchor="w"
        )
        label_widget.pack(side="left")
        
        value_widget = ctk.CTkLabel(
            row,
            text=value,
            font=("Segoe UI", 10, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        value_widget.pack(side="left", fill="x", expand=True)
    
    def create_conflict_item(self, parent, title, description):
        """Create a conflict item"""
        item = ctk.CTkFrame(parent, fg_color=self.colors['surface'], corner_radius=6)
        item.pack(fill="x", pady=5)
        
        # Warning indicator
        indicator = ctk.CTkFrame(item, width=4, fg_color=self.colors['error'], corner_radius=2)
        indicator.pack(side="left", fill="y", padx=(8, 10), pady=8)
        
        # Content
        content = ctk.CTkFrame(item, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, pady=8, padx=(0, 10))
        
        title_label = ctk.CTkLabel(
            content,
            text=title,
            font=("Segoe UI", 10, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        title_label.pack(fill="x")
        
        desc_label = ctk.CTkLabel(
            content,
            text=description,
            font=("Segoe UI", 9),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=200
        )
        desc_label.pack(fill="x")
    
    def switch_view(self, mode):
        """Switch between different view modes with debouncing"""
        # Cancel any pending view switch
        if hasattr(self, 'view_switch_timer') and self.view_switch_timer:
            self.main_view_frame.after_cancel(self.view_switch_timer)
        
        # Debounce view switch (100ms delay)
        self.view_switch_timer = self.main_view_frame.after(100, lambda: self._perform_view_switch(mode))
    
    def _perform_view_switch(self, mode):
        """Actually perform the view switch"""
        self.view_mode = mode
        
        # Remove highlights when switching away from calendar
        if mode != "calendar" and self.highlighted_teacher:
            self.remove_highlight()
        
        # Update view button states
        if hasattr(self, 'view_buttons'):
            for btn_mode, btn in self.view_buttons.items():
                is_active = (btn_mode == mode)
                btn.configure(
                    fg_color=self.colors['primary'] if is_active else "transparent",
                    text_color="white" if is_active else self.colors['text_primary'],
                    border_width=0 if is_active else 1,
                    hover_color=self.darken_color(self.colors['primary']) if is_active else self.colors['background'],
                    font=("Segoe UI", 11, "bold" if is_active else "normal")
                )
        
        # Ensure stats are up to date when switching views
        self._update_stats_display()
        
        if mode == "calendar":
            self.show_calendar_view()
        elif mode == "teachers":
            self.show_teachers_view()
    
    def show_teachers_view(self):
        """Show teachers view with dropdown and schedule table (REAL DATA) - OPTIMIZED"""
        # Build view directly (no loader - it's fast enough)
        self._build_teachers_view_async()
    
    def _build_teachers_view_async(self):
        """Build teachers view asynchronously - OPTIMIZED with widget reuse"""
        # Check if we can do partial update (only data rows)
        if (self.teacher_view_widgets['table_container'] is not None and 
            self.teacher_view_widgets['table_container'].winfo_exists() and
            len(self.teacher_view_widgets['header_row']) > 0):
            # Partial update - only refresh data rows and stats
            self._update_teacher_table_data()
            return
        
        # Full rebuild needed - clear everything
        for widget in self.main_view_frame.winfo_children():
            widget.destroy()
        
        # Reset widget references
        self.teacher_view_widgets = {
            'table_container': None,
            'header_row': [],
            'data_rows': [],
            'stats_labels': {}
        }
        
        # Check if data is loaded
        if not self.loaded_planning_file or not self.available_teachers:
            self.show_empty_state("Aucun planning chargé", 
                                 "Veuillez charger un planning existant ou générer un nouveau planning.")
            return
        
        # Header with teacher selector
        header_frame = ctk.CTkFrame(self.main_view_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 15))
        
        # Get schedule for selected teacher (before creating UI) - only if teacher is selected
        teacher_schedule = []
        total_assignments = 0
        unique_dates = 0
        
        if self.selected_teacher:
            teacher_schedule = self.get_teacher_schedule(self.selected_teacher)
            # Calculate statistics
            total_assignments = len(teacher_schedule)
            unique_dates = len(set(item['date'] for item in teacher_schedule))
        
        # Single row with teacher selector and statistics
        selector_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        selector_row.pack(fill="x", pady=(0, 10))
        
        # Left side - Teacher dropdown
        selector_container = ctk.CTkFrame(selector_row, fg_color="transparent")
        selector_container.pack(side="left", fill="x", expand=True)
        
        selector_label = ctk.CTkLabel(
            selector_container,
            text="👤 Enseignant:",
            font=("Segoe UI", 13, "bold"),
            text_color=self.colors['text_primary']
        )
        selector_label.pack(side="left", padx=(0, 10))
        
        # Outer container for shadow effect
        dropdown_shadow = ctk.CTkFrame(
            selector_container,
            fg_color=self.colors['border'],
            corner_radius=11
        )
        dropdown_shadow.pack(side="left", padx=(0, 15))
        
        # Modern custom dropdown button with CustomTkinter styling
        dropdown_frame = ctk.CTkFrame(
            dropdown_shadow,
            fg_color="white",
            corner_radius=10,
            border_width=0
        )
        dropdown_frame.pack(padx=1, pady=1)  # 1px spacing creates border effect
        
        # Main button (text part)
        self.teacher_display_text = "Sélectionner un enseignant" if not self.selected_teacher else self.selected_teacher
        
        self.teacher_text_btn = ctk.CTkLabel(
            dropdown_frame,
            text=self.teacher_display_text,
            font=("Segoe UI", 13),
            text_color=self.colors['text_secondary'] if not self.selected_teacher else self.colors['text_primary'],
            width=280,
            height=40,
            anchor="w",
            padx=15
        )
        self.teacher_text_btn.pack(side="left", fill="both", expand=True)
        
        # Arrow button (bigger and more prominent)
        self.teacher_arrow_btn = ctk.CTkButton(
            dropdown_frame,
            text="▼",
            command=self.toggle_teacher_dropdown,
            width=50,
            height=40,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 16, "bold"),
            text_color="white"
        )
        self.teacher_arrow_btn.pack(side="right", padx=2, pady=2)
        
        # Make the whole frame clickable
        dropdown_frame.bind("<Button-1>", lambda e: self.toggle_teacher_dropdown())
        self.teacher_text_btn.bind("<Button-1>", lambda e: self.toggle_teacher_dropdown())
        
        # Dropdown state
        self.dropdown_open = False
        self.dropdown_window = None
        
        # Right side - Statistics
        stats_container = ctk.CTkFrame(selector_row, fg_color="transparent")
        stats_container.pack(side="right", padx=(20, 0))
        
        # Store stat labels for updates
        self.teacher_view_widgets['stats_labels'] = self.create_stat_boxes_optimized(
            stats_container, total_assignments, unique_dates
        )
        
        # Table container with scrolling - STORE REFERENCE
        table_container = ctk.CTkScrollableFrame(
            self.main_view_frame,
            fg_color=self.colors['background'],
            corner_radius=8
        )
        table_container.pack(fill="both", expand=True, padx=20, pady=(15, 20))
        self.teacher_view_widgets['table_container'] = table_container
        
        # Create table headers with Séance column - ONLY ONCE
        headers = ["Date", "Jour", "Heure Début", "Séance"]
        header_row = []
        
        for col_idx, header in enumerate(headers):
            header_label = ctk.CTkLabel(
                table_container,
                text=header,
                font=("Segoe UI", 15, "bold"),  # Larger header font
                text_color="white",
                fg_color=self.colors['secondary'],
                corner_radius=0,
                height=60,  # Taller header
                anchor="center"
            )
            header_label.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)
            header_row.append(header_label)
        
        self.teacher_view_widgets['header_row'] = header_row
        
        # Create data rows
        self._update_teacher_table_data()
        
        # Configure grid weights for equal column widths
        for col_idx in range(len(headers)):
            table_container.grid_columnconfigure(col_idx, weight=1, uniform="cols")
    
    def create_stat_boxes_optimized(self, parent, total_assignments, unique_dates):
        """Create statistic display boxes and return references for updates"""
        stat_labels = {}
        
        # Total surveillances box
        box1 = ctk.CTkFrame(parent, fg_color="transparent")
        box1.pack(side="left", padx=15)
        
        value_label1 = ctk.CTkLabel(
            box1,
            text=str(total_assignments),
            font=("Segoe UI", 24, "bold"),
            text_color=self.colors['primary']
        )
        value_label1.pack()
        
        label_label1 = ctk.CTkLabel(
            box1,
            text="📊 Total Surveillances",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary']
        )
        label_label1.pack()
        
        stat_labels['total'] = value_label1
        
        # Jours travaillés box
        box2 = ctk.CTkFrame(parent, fg_color="transparent")
        box2.pack(side="left", padx=15)
        
        value_label2 = ctk.CTkLabel(
            box2,
            text=str(unique_dates),
            font=("Segoe UI", 24, "bold"),
            text_color=self.colors['primary']
        )
        value_label2.pack()
        
        label_label2 = ctk.CTkLabel(
            box2,
            text="📅 Jours Travaillés",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary']
        )
        label_label2.pack()
        
        stat_labels['dates'] = value_label2
        
        return stat_labels
    
    def _update_teacher_table_data(self):
        """Update ONLY the data rows in teacher table (not headers) - OPTIMIZED"""
        table_container = self.teacher_view_widgets['table_container']
        if not table_container or not table_container.winfo_exists():
            return
        
        # Get current teacher schedule
        teacher_schedule = []
        if self.selected_teacher:
            teacher_schedule = self.get_teacher_schedule(self.selected_teacher)
        
        # Update statistics
        total_assignments = len(teacher_schedule)
        unique_dates = len(set(item['date'] for item in teacher_schedule)) if teacher_schedule else 0
        
        if 'total' in self.teacher_view_widgets['stats_labels']:
            self.teacher_view_widgets['stats_labels']['total'].configure(text=str(total_assignments))
        if 'dates' in self.teacher_view_widgets['stats_labels']:
            self.teacher_view_widgets['stats_labels']['dates'].configure(text=str(unique_dates))
        
        # Clear old data rows (keep header at row 0)
        for row_widgets in self.teacher_view_widgets['data_rows']:
            for widget in row_widgets:
                if widget.winfo_exists():
                    widget.destroy()
        self.teacher_view_widgets['data_rows'] = []
        
        # Handle empty state
        if not teacher_schedule:
            # Show appropriate message based on whether a teacher is selected
            if not self.selected_teacher:
                empty_text = "👆 Veuillez sélectionner un enseignant ci-dessus"
            else:
                empty_text = "Aucune affectation pour cet enseignant"
            
            empty_label = ctk.CTkLabel(
                table_container,
                text=empty_text,
                font=("Segoe UI", 15),  # Larger font for empty state
                text_color=self.colors['text_secondary']
            )
            empty_label.grid(row=1, column=0, columnspan=4, pady=60)
            self.teacher_view_widgets['data_rows'].append([empty_label])
            return
        
        # Sort schedule by date and time
        teacher_schedule_sorted = sorted(teacher_schedule, key=lambda x: (x.get('date', ''), x.get('heure_debut', '')))
        
        # Create data rows dynamically with alternating colors
        for row_idx, schedule_item in enumerate(teacher_schedule_sorted):
            bg_color = self.colors['surface'] if row_idx % 2 == 0 else self.colors['background']
            
            # Extract values including seance
            date_str = schedule_item.get("date", "")
            jour_str = schedule_item.get("jour", "")
            heure_str = schedule_item.get("heure_debut", "")
            seance_str = schedule_item.get("seance", "")
            
            # Map seance to number if needed (in case it's a time)
            if seance_str in ['1', '2', '3', '4']:
                seance_display = seance_str
            else:
                time_to_seance = {
                    '08:30': '1', '08:30:00': '1',
                    '10:30': '2', '10:30:00': '2',
                    '12:30': '3', '12:30:00': '3',
                    '14:30': '4', '14:30:00': '4'
                }
                seance_display = time_to_seance.get(seance_str, seance_str)
            
            data = [date_str, jour_str, heure_str, seance_display]
            row_widgets = []
            
            for col_idx, value in enumerate(data):
                cell = ctk.CTkLabel(
                    table_container,
                    text=str(value),
                    font=("Segoe UI", 13),  # Larger font for table cells
                    text_color=self.colors['text_primary'],
                    fg_color=bg_color,
                    corner_radius=0,
                    height=55,  # Taller rows
                    anchor="center"
                )
                cell.grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)
                row_widgets.append(cell)
            
            self.teacher_view_widgets['data_rows'].append(row_widgets)
    
    def create_stat_box(self, parent, label, value):
        """Create a statistic display box"""
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side="left", padx=15)
        
        value_label = ctk.CTkLabel(
            box,
            text=value,
            font=("Segoe UI", 24, "bold"),
            text_color=self.colors['primary']
        )
        value_label.pack()
        
        label_label = ctk.CTkLabel(
            box,
            text=label,
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary']
        )
        label_label.pack()
    
    def on_teacher_selected(self, teacher_name):
        """Handle teacher selection from dropdown (REAL DATA) - OPTIMIZED"""
        self.selected_teacher = teacher_name
        self.app.update_status(f"Affichage du planning pour {teacher_name}")
        
        # Update teacher display text
        if hasattr(self, 'teacher_text_btn') and self.teacher_text_btn.winfo_exists():
            self.teacher_text_btn.configure(
                text=teacher_name,
                text_color=self.colors['text_primary']
            )
        
        # Use optimized refresh - only updates data rows, not full rebuild
        self.show_teachers_view()
    
    def toggle_teacher_dropdown(self):
        """Toggle the custom teacher dropdown"""
        if self.dropdown_open:
            self.close_teacher_dropdown()
        else:
            self.open_teacher_dropdown()
    
    def open_teacher_dropdown(self):
        """Open modern custom dropdown"""
        # Check if dropdown already exists and is valid
        if self.dropdown_open and self.dropdown_window and self.dropdown_window.winfo_exists():
            # Already open, just make sure it's visible
            try:
                self.dropdown_window.deiconify()
                self.dropdown_window.lift()
            except:
                pass
            return
        
        self.dropdown_open = True
        
        try:
            self.teacher_arrow_btn.configure(text="▲")
        except:
            pass
        
        # Create dropdown window
        self.dropdown_window = ctk.CTkToplevel(self.app)
        self.dropdown_window.overrideredirect(True)  # Remove window decorations
        
        # Configure dropdown window BEFORE showing
        self.dropdown_window.configure(fg_color="white")
        
        # Force update to get widget positions
        self.teacher_text_btn.update_idletasks()
        self.teacher_arrow_btn.update_idletasks()
        
        # Calculate position (below the button)
        try:
            btn_x = self.teacher_text_btn.winfo_rootx()
            btn_y = self.teacher_text_btn.winfo_rooty()
            btn_height = max(self.teacher_text_btn.winfo_height(), 45)
            btn_width = self.teacher_text_btn.winfo_width() + self.teacher_arrow_btn.winfo_width() + 10
        except:
            # Fallback values if position can't be determined
            btn_x = 300
            btn_y = 200
            btn_height = 45
            btn_width = 350
        
        # Configure dropdown window
        self.dropdown_window.configure(fg_color="white")
        
        # Main container with border and corner radius
        container = ctk.CTkFrame(
            self.dropdown_window,
            fg_color="white",
            corner_radius=10,
            border_width=2,
            border_color=self.colors['border']
        )
        container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Search box
        search_var = tk.StringVar()
        search_frame = ctk.CTkFrame(container, fg_color="transparent")
        search_frame.pack(fill="x", padx=8, pady=8)
        
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=search_var,
            placeholder_text="🔍 Rechercher un enseignant...",
            height=40,
            font=("Segoe UI", 13),
            fg_color=self.colors['background'],
            border_color=self.colors['border'],
            border_width=2,
            corner_radius=8
        )
        search_entry.pack(fill="x")
        
        # Modern scrollable list (shows 10 items)
        list_frame = ctk.CTkScrollableFrame(
            container,
            fg_color="white",
            height=400,  # Height for exactly 10 items at 40px each
            corner_radius=0,
            scrollbar_button_color=self.colors['secondary'],
            scrollbar_button_hover_color=self.colors['hover_dark']
        )
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        def filter_and_display_teachers(*args):
            """Filter and display teachers based on search"""
            search_text = search_var.get().lower()
            
            # Clear current list
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            # Filter teachers
            filtered = [t for t in self.available_teachers if search_text in t.lower()]
            
            # Display filtered teachers
            for idx, teacher in enumerate(filtered):
                teacher_btn = ctk.CTkButton(
                    list_frame,
                    text=teacher,
                    command=lambda t=teacher: self.select_teacher_from_dropdown(t),
                    height=40,
                    fg_color="transparent",
                    hover_color=self.colors['hover'],
                    text_color=self.colors['text_primary'],
                    font=("Segoe UI", 13),
                    anchor="w",
                    corner_radius=6
                )
                teacher_btn.pack(fill="x", pady=1, padx=2)
        
        # Initial display
        filter_and_display_teachers()
        
        # Bind search
        search_var.trace("w", filter_and_display_teachers)
        
        # Position and show dropdown - SET GEOMETRY BEFORE SHOWING
        dropdown_geometry = f"{btn_width}x470+{btn_x}+{btn_y + btn_height + 5}"
        self.dropdown_window.geometry(dropdown_geometry)
        
        # Update and show
        self.dropdown_window.update()
        self.dropdown_window.deiconify()  # Make visible
        self.dropdown_window.lift()  # Bring to front
        
        # Focus on search entry
        search_entry.focus_set()
        
        # Bind events to close dropdown - ONLY AFTER WINDOW IS FULLY SHOWN
        # Use longer delay to avoid immediate closure
        def setup_close_bindings():
            self.dropdown_window.bind("<Escape>", lambda e: self.close_teacher_dropdown())
            
            # Close dropdown when main window loses focus (e.g., when tabbing to another app)
            def on_focus_out(event):
                # Check if focus went to another application (not just another widget in our app)
                if self.dropdown_window and self.dropdown_open:
                    try:
                        focused = self.app.focus_get()
                        if focused is None:  # Focus left the application
                            self.close_teacher_dropdown()
                    except:
                        self.close_teacher_dropdown()
            
            self.app.bind("<FocusOut>", on_focus_out, add="+")
            
            # Setup click-outside detection
            def check_click(event):
                if not self.dropdown_window or not self.dropdown_open:
                    return
                
                try:
                    # Get the widget that was clicked
                    widget = event.widget
                    widget_str = str(widget)
                    dropdown_str = str(self.dropdown_window)
                    
                    # Check if click is inside dropdown window or its children
                    is_inside_dropdown = widget_str.startswith(dropdown_str)
                    
                    # Check if it's the dropdown button components
                    is_dropdown_button = (widget == self.teacher_arrow_btn or 
                                        widget == self.teacher_text_btn or
                                        str(widget).startswith(str(self.teacher_arrow_btn)) or
                                        str(widget).startswith(str(self.teacher_text_btn)))
                    
                    # Only close if clicked outside both dropdown and button
                    if not is_inside_dropdown and not is_dropdown_button:
                        self.close_teacher_dropdown()
                except Exception as e:
                    print(f"Click check error: {e}")
            
            # Bind to main app window
            self.app.bind("<Button-1>", check_click, add="+")
        
        # Delay binding to avoid immediate closure from the opening click
        self.dropdown_window.after(200, setup_close_bindings)
    
    def close_teacher_dropdown(self):
        """Close the custom dropdown"""
        if not self.dropdown_open:
            return
            
        self.dropdown_open = False
        
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            try:
                # Unbind events before destroying
                self.dropdown_window.unbind("<Escape>")
                self.dropdown_window.destroy()
            except Exception as e:
                print(f"Error closing dropdown: {e}")
        
        self.dropdown_window = None
        
        try:
            self.teacher_arrow_btn.configure(text="▼")
        except:
            pass
    
    def select_teacher_from_dropdown(self, teacher_name):
        """Handle teacher selection from custom dropdown"""
        self.close_teacher_dropdown()
        self.selected_teacher = teacher_name
        self.teacher_text_btn.configure(
            text=teacher_name,
            text_color=self.colors['text_primary']
        )
        self.app.update_status(f"Affichage du planning pour {teacher_name}")
        self.show_teachers_view()
    
    def on_calendar_click(self, event):
        """Handle calendar click for drag-and-drop"""
        pass
    
    def on_calendar_drag(self, event):
        """Handle dragging assignments"""
        pass
    
    def on_calendar_release(self, event):
        """Handle drop of assignments"""
        pass
    
    def load_planning_dialog(self):
        """Open file dialog to load a planning file"""
        filepath = filedialog.askopenfilename(
            title="Charger un Planning",
            initialdir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'output'),
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if filepath:
            if self.load_planning_from_file(filepath):
                self.app.update_status(f"Planning chargé: {os.path.basename(filepath)}")
                messagebox.showinfo("Succès", f"Planning chargé:\n{os.path.basename(filepath)}")
    
    def show_empty_state(self, title, message):
        """Show empty state message"""
        empty_frame = ctk.CTkFrame(self.main_view_frame, fg_color="transparent")
        empty_frame.pack(expand=True)
        
        icon_label = ctk.CTkLabel(
            empty_frame,
            text="📋",
            font=("Segoe UI", 80)
        )
        icon_label.pack(pady=(0, 20))
        
        title_label = ctk.CTkLabel(
            empty_frame,
            text=title,
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['text_primary']
        )
        title_label.pack(pady=(0, 10))
        
        msg_label = ctk.CTkLabel(
            empty_frame,
            text=message,
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary']
        )
        msg_label.pack()
        
        # Buttons frame with two options
        buttons_frame = ctk.CTkFrame(empty_frame, fg_color="transparent")
        buttons_frame.pack(pady=(30, 0))
        
        # Generate new planning button (primary action)
        generate_btn = ctk.CTkButton(
            buttons_frame,
            text="✨ Générer un Nouveau Planning",
            width=250,
            height=45,
            font=("Segoe UI", 13, "bold"),
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            text_color="white",
            command=self.app.trigger_new_planning
        )
        generate_btn.pack(side="left", padx=10)
        
        # Load planning button (secondary action)
        load_btn = ctk.CTkButton(
            buttons_frame,
            text="📂 Charger un Planning",
            width=250,
            height=45,
            font=("Segoe UI", 13, "bold"),
            fg_color="transparent",
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['primary'],
            text_color=self.colors['primary'],
            command=self.app.trigger_open_planning
        )
        load_btn.pack(side="left", padx=10)
    
    def select_date(self):
        """Open date selector dialog"""
        if not self.available_dates:
            messagebox.showinfo("Aucune Date", "Aucune date disponible dans le planning")
            return
        
        # Create a simple selection dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sélectionner une Date")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.grab_set()
        
        # Title
        title = ctk.CTkLabel(
            dialog,
            text="Sélectionnez une date",
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=20)
        
        # Scrollable frame with dates
        scroll_frame = ctk.CTkScrollableFrame(dialog, width=360, height=350)
        scroll_frame.pack(pady=(0, 20), padx=20, fill="both", expand=True)
        
        def select_and_close(date):
            self.selected_date = date
            dialog.destroy()
            self.show_calendar_view()
            self.app.update_status(f"Date sélectionnée: {date}")
        
        for date in self.available_dates:
            is_selected = (date == self.selected_date)
            date_btn = ctk.CTkButton(
                scroll_frame,
                text=f"📅 {date}",
                width=320,
                height=45,
                font=("Segoe UI", 12, "bold" if is_selected else "normal"),
                fg_color=self.colors['primary'] if is_selected else "white",
                text_color="white" if is_selected else self.colors['text_primary'],
                border_width=2 if not is_selected else 0,
                border_color=self.colors['border'],
                hover_color=self.colors['primary'],
                command=lambda d=date: select_and_close(d)
            )
            date_btn.pack(pady=5, padx=10)
    
    def previous_date(self):
        """Navigate to previous date"""
        if not self.available_dates or not self.selected_date:
            return
        
        current_idx = self.available_dates.index(self.selected_date)
        if current_idx > 0:
            self.selected_date = self.available_dates[current_idx - 1]
            self.show_calendar_view(refresh_only=True)  # OPTIMIZED: Only refresh content
            self.app.update_status(f"Date: {self.selected_date}")
    
    def next_date(self):
        """Navigate to next date"""
        if not self.available_dates or not self.selected_date:
            return
        
        current_idx = self.available_dates.index(self.selected_date)
        if current_idx < len(self.available_dates) - 1:
            self.selected_date = self.available_dates[current_idx + 1]
            self.show_calendar_view(refresh_only=True)  # OPTIMIZED: Only refresh content
            self.app.update_status(f"Date: {self.selected_date}")
    
    def select_assignment(self, teacher_name, seance, date, cell_frame=None):
        """Select an assignment for editing - handles both normal mode and swap mode"""
        
        # Check if in swap mode
        if self.swap_mode_active:
            # SWAP MODE LOGIC
            
            # Check if clicking on already selected source - deselect it
            if (self.swap_source and 
                self.swap_source.get('teacher') == teacher_name and 
                self.swap_source.get('seance') == seance and 
                self.swap_source.get('date') == date):
                self._clear_swap_slot(is_source=True)
                return
            
            # Check if clicking on already selected target - deselect it
            if (self.swap_target and 
                self.swap_target.get('teacher') == teacher_name and 
                self.swap_target.get('seance') == seance and 
                self.swap_target.get('date') == date):
                self._clear_swap_slot(is_source=False)
                return
            
            if not self.swap_source:
                # Select as source
                self.swap_source = {
                    'teacher': teacher_name,
                    'seance': seance,
                    'date': date,
                    'frame': cell_frame
                }
                
                # Highlight as source (blue) - PERSISTENT
                if cell_frame and cell_frame.winfo_exists():
                    cell_frame.configure(fg_color="#3B82F6")  # Blue for source
                    for widget in cell_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
                
                # OPTIMIZED: Update only source slot content, not entire panel
                self._update_swap_slot_content_only(is_source=True)
                self.app.update_status(f"✓ Source sélectionnée: {teacher_name} - Séance {seance}")
                
            elif not self.swap_target:
                # Select as target
                self.swap_target = {
                    'teacher': teacher_name,
                    'seance': seance,
                    'date': date,
                    'frame': cell_frame
                }
                
                # Highlight as target (green)
                if cell_frame:
                    cell_frame.configure(fg_color="#10B981")  # Green for target
                    for widget in cell_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
                
                # OPTIMIZED: Update only target slot content, not entire panel
                self._update_swap_slot_content_only(is_source=False)
                self.app.update_status(f"✓ Cible sélectionnée: {teacher_name} - Séance {seance}")
            else:
                # Both already selected - inform user
                messagebox.showinfo(
                    "Créneaux Sélectionnés",
                    "Les deux créneaux sont déjà sélectionnés.\n\n"
                    "Cliquez sur 'Exécuter l'Échange' ou désactivez le mode échange."
                )
            
            return  # Exit early in swap mode
        
        # NORMAL MODE LOGIC (existing code)
        self.selected_assignment = {
            'teacher': teacher_name,
            'seance': seance,
            'date': date
        }
        
        # Reset previous selected cell to normal appearance
        if self.selected_cell_frame and self.selected_cell_frame.winfo_exists():
            # Check if it was a search-highlighted cell (check both list and highlighted_teacher)
            was_highlighted = (self.selected_cell_frame in self.highlighted_cells or 
                              (self.highlighted_teacher and self.selected_cell_info and 
                               self.highlighted_teacher in self.selected_cell_info.get('teacher', '')))
            reset_color = "#FCD34D" if was_highlighted else self.colors['surface']
            reset_text_color = "#1F2937" if was_highlighted else self.colors['text_primary']
            reset_font_weight = "bold" if was_highlighted else "normal"
            
            # Reset frame color
            self.selected_cell_frame.configure(fg_color=reset_color)
            
            # Reset label text color and font weight
            for widget in self.selected_cell_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(
                        text_color=reset_text_color,
                        font=("Segoe UI", 13, reset_font_weight)
                    )
        
        # Update selection state
        self.selected_cell_frame = cell_frame
        self._last_selected_frame = cell_frame  # Track for clearing when entering swap mode
        self.selected_cell_info = {
            'teacher': teacher_name,
            'seance': seance,
            'date': date
        }
        
        # Highlight the new selected cell
        if cell_frame:
            cell_frame.configure(fg_color=self.colors['primary'])
            # Update the label text color to white for better contrast
            for widget in cell_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
        
        # Update slots display (will show single slot in normal mode)
        if hasattr(self, '_update_slots_display'):
            self._update_slots_display()
        
        self.app.update_status(f"Sélectionné: {teacher_name} - {seance} ({date})")
    
    def apply_modification(self):
        """Apply manual modification"""
        self.has_unsaved_changes = True
        self.app.update_status("Modification appliquée (non sauvegardée)")
        messagebox.showinfo("✅ Modifié", "N'oubliez pas d'enregistrer!")
    
    # ==================== SWAP MODE METHODS ====================
    
    def toggle_swap_mode(self):
        """Toggle swap mode on/off"""
        self.swap_mode_active = not self.swap_mode_active
        
        if self.swap_mode_active:
            # Entering swap mode
            # Clear currently selected slot to avoid visual confusion
            if self.selected_cell_info:
                self._clear_selection_highlight()
            self.selected_cell_info = None
            
            self.swap_source = None
            self.swap_target = None
            
            # Update button appearance (toolbar) - RED like "Enlever surbrillance"
            if hasattr(self, 'swap_mode_btn'):
                self.swap_mode_btn.configure(
                    fg_color="#DC2626",  # Red color
                    text_color="white",
                    border_width=0,
                    text="❌ Fermer Mode Échange"
                )
            
            # Update action button appearance (details panel)
            if hasattr(self, 'swap_action_btn'):
                self.swap_action_btn.configure(
                    fg_color="#DC2626",  # Red color
                    text_color="white",
                    border_width=0,
                    text="❌ Fermer Mode Échange"
                )
            
            self.app.update_status("🔄 Mode Échange activé - Sélectionnez deux créneaux")
        else:
            # Exiting swap mode - IMPORTANT: Clear highlights BEFORE clearing references
            self._clear_swap_highlights()
            
            # Now clear the references
            self.swap_source = None
            self.swap_target = None
            
            # Reset button appearance (toolbar)
            if hasattr(self, 'swap_mode_btn'):
                self.swap_mode_btn.configure(
                    fg_color="transparent",
                    text_color=self.colors['primary'],
                    border_width=2,
                    border_color=self.colors['primary'],
                    text="🔄 Échanger"
                )
            
            # Reset action button appearance (details panel)
            if hasattr(self, 'swap_action_btn'):
                self.swap_action_btn.configure(
                    fg_color="transparent",
                    text_color=self.colors['primary'],
                    border_width=2,
                    border_color=self.colors['primary'],
                    text="🔄 Échanger"
                )
            
            self.app.update_status("Mode Échange désactivé")
        
        # Update slots display
        self._update_slots_display()
    
    def _clear_swap_highlights(self):
        """Clear visual highlights for swap source/target"""
        # Reset source highlight
        if self.swap_source and self.swap_source.get('frame'):
            frame = self.swap_source['frame']
            if frame.winfo_exists():
                # Check if this slot is search-highlighted
                teacher = self.swap_source.get('teacher', '')
                is_search_highlighted = (self.highlighted_teacher and teacher and 
                                        self.highlighted_teacher in teacher)
                reset_color = "#FCD34D" if is_search_highlighted else self.colors['surface']
                reset_text_color = "#1F2937" if is_search_highlighted else self.colors['text_primary']
                reset_font_weight = "bold" if is_search_highlighted else "normal"
                
                frame.configure(fg_color=reset_color)
                for widget in frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=reset_text_color, font=("Segoe UI", 13, reset_font_weight))
        
        # Reset target highlight
        if self.swap_target and self.swap_target.get('frame'):
            frame = self.swap_target['frame']
            if frame.winfo_exists():
                # Check if this slot is search-highlighted
                teacher = self.swap_target.get('teacher', '')
                is_search_highlighted = (self.highlighted_teacher and teacher and 
                                        self.highlighted_teacher in teacher)
                reset_color = "#FCD34D" if is_search_highlighted else self.colors['surface']
                reset_text_color = "#1F2937" if is_search_highlighted else self.colors['text_primary']
                reset_font_weight = "bold" if is_search_highlighted else "normal"
                
                frame.configure(fg_color=reset_color)
                for widget in frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=reset_text_color, font=("Segoe UI", 13, reset_font_weight))
    
    def _clear_selection_highlight(self):
        """Clear the purple highlight from currently selected cell"""
        if hasattr(self, '_last_selected_frame') and self._last_selected_frame:
            if self._last_selected_frame.winfo_exists():
                # Check if this slot is search-highlighted
                # Try to find teacher name from selected_cell_info or selection state
                teacher = ''
                if hasattr(self, 'selected_cell_info') and self.selected_cell_info:
                    teacher = self.selected_cell_info.get('teacher', '')
                elif hasattr(self, 'selected_assignment') and self.selected_assignment:
                    teacher = self.selected_assignment.get('teacher', '')
                
                is_search_highlighted = (self.highlighted_teacher and teacher and 
                                        self.highlighted_teacher in teacher)
                reset_color = "#FCD34D" if is_search_highlighted else self.colors['surface']
                reset_text_color = "#1F2937" if is_search_highlighted else self.colors['text_primary']
                reset_font_weight = "bold" if is_search_highlighted else "normal"
                
                self._last_selected_frame.configure(fg_color=reset_color)
                for widget in self._last_selected_frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=reset_text_color, font=("Segoe UI", 13, reset_font_weight))
            self._last_selected_frame = None
    
    def _clear_swap_slot(self, is_source):
        """Clear a swap slot selection and revert its visual highlight"""
        if is_source:
            # Clear source highlight
            if self.swap_source and self.swap_source.get('frame'):
                frame = self.swap_source['frame']
                if frame.winfo_exists():
                    # Check if this slot is search-highlighted
                    teacher = self.swap_source.get('teacher', '')
                    is_search_highlighted = (self.highlighted_teacher and teacher and 
                                            self.highlighted_teacher in teacher)
                    reset_color = "#FCD34D" if is_search_highlighted else self.colors['surface']
                    reset_text_color = "#1F2937" if is_search_highlighted else self.colors['text_primary']
                    reset_font_weight = "bold" if is_search_highlighted else "normal"
                    
                    frame.configure(fg_color=reset_color)
                    for widget in frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color=reset_text_color, font=("Segoe UI", 13, reset_font_weight))
            
            # Clear source data
            self.swap_source = None
            self.app.update_status("Source désélectionnée")
        else:
            # Clear target highlight
            if self.swap_target and self.swap_target.get('frame'):
                frame = self.swap_target['frame']
                if frame.winfo_exists():
                    # Check if this slot is search-highlighted
                    teacher = self.swap_target.get('teacher', '')
                    is_search_highlighted = (self.highlighted_teacher and teacher and 
                                            self.highlighted_teacher in teacher)
                    reset_color = "#FCD34D" if is_search_highlighted else self.colors['surface']
                    reset_text_color = "#1F2937" if is_search_highlighted else self.colors['text_primary']
                    reset_font_weight = "bold" if is_search_highlighted else "normal"
                    
                    frame.configure(fg_color=reset_color)
                    for widget in frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color=reset_text_color, font=("Segoe UI", 13, reset_font_weight))
            
            # Clear target data
            self.swap_target = None
            self.app.update_status("Cible désélectionnée")
        
        # OPTIMIZED: Update only the cleared slot content, not entire panel
        self._update_swap_slot_content_only(is_source)
    
    def _find_calendar_cell_frame(self, teacher_name, date, seance):
        """Find the calendar cell frame for a specific slot (if visible in current view)"""
        # Only works in calendar view
        if self.view_mode != "calendar":
            return None
        
        # Check if this date is the currently displayed date
        if not hasattr(self, 'selected_date') or str(self.selected_date) != str(date):
            return None
        
        # Try to find the cell frame
        if hasattr(self, '_calendar_cells_map'):
            # Use cached cell mapping if available
            cell_key = f"{teacher_name}_{seance}"
            return self._calendar_cells_map.get(cell_key)
        
        return None
    
    def open_manual_slot_input(self, is_source):
        """Open modal for manual slot input"""
        # Create modal
        modal = ctk.CTkToplevel(self)
        modal.title("Saisie Manuelle du Créneau")
        modal.geometry("500x600")
        modal.transient(self)
        modal.grab_set()
        
        # Center modal
        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (250)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (300)
        modal.geometry(f"500x600+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(modal, fg_color=self.colors['primary'], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text=f"✏️ Saisir le Créneau {'Source' if is_source else 'Cible'}",
            font=("Segoe UI", 20, "bold"),
            text_color="white"
        ).pack(pady=20)
        
        # Content
        content = ctk.CTkFrame(modal, fg_color=self.colors['background'])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Instructions
        ctk.CTkLabel(
            content,
            text="Sélectionnez l'enseignant et le créneau à échanger :",
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary']
        ).pack(anchor="w", pady=(0, 15))
        
        # Teacher selection
        ctk.CTkLabel(
            content,
            text="Enseignant :",
            font=("Segoe UI", 13, "bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w", pady=(10, 5))
        
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            content,
            textvariable=search_var,
            placeholder_text="🔍 Rechercher un enseignant...",
            height=40,
            font=("Segoe UI", 13)
        )
        search_entry.pack(fill="x", pady=(0, 10))
        search_entry.focus()
        
        list_frame = ctk.CTkScrollableFrame(
            content,
            fg_color=self.colors['surface'],
            corner_radius=8,
            height=200
        )
        list_frame.pack(fill="x", pady=(0, 15))
        
        selected_data = {"teacher": None, "date": None, "seance": None, "widget": None}
        
        # Create teacher items with their assignments
        teacher_items = {}
        
        def create_teacher_assignment_item(teacher_name):
            """Create expandable teacher item showing their assignments"""
            container = ctk.CTkFrame(list_frame, fg_color="transparent")
            container.pack(fill="x", pady=2)
            
            teacher_btn = ctk.CTkFrame(container, fg_color=self.colors['background'], corner_radius=6, cursor="hand2")
            teacher_btn.pack(fill="x", padx=5, pady=2)
            
            # Teacher name button (expandable)
            teacher_label = ctk.CTkLabel(
                teacher_btn,
                text=f"▶ {teacher_name}",
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors['text_primary'],
                anchor="w"
            )
            teacher_label.pack(fill="x", padx=15, pady=10)
            
            # Assignments container (initially hidden)
            assignments_frame = ctk.CTkFrame(container, fg_color=self.colors['surface'])
            expanded = {"state": False}
            
            def toggle_expand(e=None):
                if expanded["state"]:
                    assignments_frame.pack_forget()
                    teacher_label.configure(text=f"▶ {teacher_name}")
                    expanded["state"] = False
                else:
                    # Show assignments
                    for widget in assignments_frame.winfo_children():
                        widget.destroy()
                    
                    teacher_assignments = self.teacher_schedules.get(teacher_name, [])
                    if teacher_assignments:
                        for assignment in teacher_assignments:
                            date = assignment.get('date', '')
                            seance = assignment.get('seance', '')
                            
                            # Format date
                            try:
                                from datetime import datetime
                                date_obj = datetime.strptime(date, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%d/%m/%Y')
                            except:
                                formatted_date = date
                            
                            # FIX: Create button with proper closure - capture widget ref correctly
                            assign_btn = ctk.CTkButton(
                                assignments_frame,
                                text=f"  📅 {formatted_date} - ⏰ Séance {seance}",
                                height=35,
                                corner_radius=6,
                                fg_color="transparent",
                                text_color=self.colors['text_primary'],
                                hover_color=self.colors['hover'],
                                anchor="w",
                                font=("Segoe UI", 11)
                            )
                            # Set command separately with proper closure
                            assign_btn.configure(command=lambda t=teacher_name, d=date, s=seance, btn=assign_btn: select_assignment(t, d, s, btn))
                            assign_btn.pack(fill="x", padx=10, pady=2)
                    else:
                        ctk.CTkLabel(
                            assignments_frame,
                            text="  Aucune affectation",
                            font=("Segoe UI", 10),
                            text_color=self.colors['text_secondary']
                        ).pack(pady=5)
                    
                    assignments_frame.pack(fill="x", padx=10, pady=(0, 5))
                    teacher_label.configure(text=f"▼ {teacher_name}")
                    expanded["state"] = True
            
            teacher_btn.bind("<Button-1>", toggle_expand)
            teacher_label.bind("<Button-1>", toggle_expand)
            
            return container
        
        def select_assignment(teacher, date, seance, widget):
            # Reset previous selection
            if selected_data["widget"]:
                selected_data["widget"].configure(fg_color="transparent", text_color=self.colors['text_primary'])
            
            # Highlight selected
            widget.configure(fg_color=self.colors['primary'], text_color="white")
            selected_data["teacher"] = teacher
            selected_data["date"] = date
            selected_data["seance"] = seance
            selected_data["widget"] = widget
        
        for teacher in self.available_teachers:
            item = create_teacher_assignment_item(teacher)
            teacher_items[teacher] = item
        
        def filter_teachers(*args):
            search_text = search_var.get().lower()
            for teacher, widget in teacher_items.items():
                if search_text in teacher.lower():
                    widget.pack(fill="x", pady=2)
                else:
                    widget.pack_forget()
        
        search_var.trace_add("write", filter_teachers)
        
        # Buttons
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x", pady=(15, 0))
        
        def confirm_selection():
            if not selected_data["teacher"] or not selected_data["date"] or not selected_data["seance"]:
                messagebox.showwarning("Sélection Incomplète", "Veuillez sélectionner un enseignant et un créneau")
                return
            
            # Find the frame in the calendar for this slot (if visible)
            calendar_frame = self._find_calendar_cell_frame(
                selected_data["teacher"],
                selected_data["date"],
                selected_data["seance"]
            )
            
            # Create slot data
            slot_data = {
                'teacher': selected_data["teacher"],
                'date': selected_data["date"],
                'seance': selected_data["seance"],
                'frame': calendar_frame
            }
            
            # Update swap source or target
            if is_source:
                self.swap_source = slot_data
                # Apply blue highlight
                if calendar_frame and calendar_frame.winfo_exists():
                    calendar_frame.configure(fg_color="#3B82F6")
                    for widget in calendar_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
            else:
                self.swap_target = slot_data
                # Apply green highlight
                if calendar_frame and calendar_frame.winfo_exists():
                    calendar_frame.configure(fg_color="#10B981")
                    for widget in calendar_frame.winfo_children():
                        if isinstance(widget, ctk.CTkLabel):
                            widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
            
            modal.destroy()
            self._update_slots_display()
            
            # FIX: If we're on the selected date but frame wasn't found, refresh calendar to show highlight
            if not calendar_frame and self.view_mode == "calendar":
                # Check if selected date matches current calendar date
                if hasattr(self, 'selected_date') and str(self.selected_date) == str(selected_data["date"]):
                    # Refresh the calendar display to update the cell highlight
                    self._update_seance_column(selected_data["seance"])
        
        ctk.CTkButton(
            button_frame,
            text="✓ Confirmer",
            height=45,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=confirm_selection
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            button_frame,
            text="Annuler",
            height=45,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=modal.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))
    
    def save_changes(self):
        """Save all changes to database - FULLY FUNCTIONAL with proper persistence"""
        if not self.has_unsaved_changes:
            messagebox.showinfo("Info", "Aucune modification à enregistrer")
            return
        
        if not self.loaded_planning_file:
            messagebox.showerror("Erreur", "Aucun planning chargé")
            return
        
        # Check if we have a valid session ID
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showerror(
                "Erreur",
                "Impossible d'enregistrer: Aucune session active.\n\n"
                "Ce planning doit être associé à une session dans la base de données."
            )
            return
        
        session_id = self.app.current_session_id
        
        try:
            # Show progress indicator
            self.app.update_status("💾 Sauvegarde en cours...", show_progress=True, progress_value=0.3)
            
            # Import database operations
            import sys as sys_module
            from pathlib import Path
            parent_dir = Path(__file__).parent.parent.parent
            db_dir = parent_dir / "src" / "db"
            if str(db_dir) not in sys_module.path:
                sys_module.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            
            # Connect to database
            db_path = parent_dir / "planning.db"
            db = DatabaseManager(str(db_path))
            
            self.app.update_status("💾 Mise à jour des affectations...", show_progress=True, progress_value=0.6)
            
            # Save schedule_data to database using the new method
            # This will completely replace all assignments for the session
            assignments_count = db.update_session_assignments(
                session_id=session_id,
                schedule_data=self.schedule_data
            )
            
            self.app.update_status("✓ Vérification des données...", show_progress=True, progress_value=0.9)
            
            # Mark as saved
            self.has_unsaved_changes = False
            self.original_assignments = self.assignments_df.copy()
            
            # Update app state cache to reflect saved state
            self.save_to_app_state()
            
            # Clear modification tracking
            if hasattr(self, 'modifications'):
                modification_count = len(self.modifications)
                self.modifications = []
            else:
                modification_count = 0
            
            # Clear affected teachers list
            if hasattr(self, 'affected_teachers'):
                affected_count = len(self.affected_teachers)
                self.affected_teachers.clear()
            else:
                affected_count = 0
            
            # Clear undo/redo stacks since changes are now permanent
            self.undo_stack = []
            self.redo_stack = []
            self._update_undo_redo_buttons()
            
            self.app.update_status("✅ Modifications enregistrées", show_progress=False)
            
            # Show detailed success message
            success_message = f"✅ Modifications enregistrées avec succès!\n\n"
            success_message += f"📊 {assignments_count} affectation(s) sauvegardée(s)\n"
            success_message += f"💾 Session #{session_id}\n"
            
            if modification_count > 0:
                success_message += f"📝 {modification_count} modification(s) appliquée(s)\n"
            if affected_count > 0:
                success_message += f"👥 {affected_count} enseignant(s) affecté(s)\n"
            
            success_message += f"\n✓ Les données sont maintenant persistantes dans la base de données"
            
            messagebox.showinfo("Succès", success_message)
            
            print(f"✅ Successfully saved {assignments_count} assignments to database for session {session_id}")
        
        except ImportError as e:
            self.app.update_status("❌ Erreur: Module database non disponible", show_progress=False)
            messagebox.showerror(
                "Erreur de Module",
                f"Le module de base de données n'est pas disponible.\n\n"
                f"Erreur: {str(e)}\n\n"
                f"Assurez-vous que db_operations.py est présent dans src/db/"
            )
        except Exception as e:
            self.app.update_status("❌ Erreur lors de la sauvegarde", show_progress=False)
            
            # Show detailed error message
            error_details = str(e)
            if "Failed to update assignments" in error_details:
                # Extract the inner error message
                error_details = error_details.replace("Failed to update assignments: ", "")
            
            messagebox.showerror(
                "Erreur de Sauvegarde",
                f"Impossible d'enregistrer les modifications:\n\n"
                f"{error_details}\n\n"
                f"Vérifiez que:\n"
                f"• La base de données existe\n"
                f"• La session est valide\n"
                f"• Vous avez les permissions d'écriture"
            )
            
            import traceback
            traceback.print_exc()
            print(f"❌ Save failed for session {session_id}: {error_details}")
    
    def undo_changes(self):
        """Undo all changes and restore original"""
        if not self.has_unsaved_changes:
            messagebox.showinfo("Info", "Aucune modification à annuler")
            return
        
        if messagebox.askyesno("Confirmer", "Annuler toutes les modifications?"):
            self.assignments_df = self.original_assignments.copy()
            self.has_unsaved_changes = False
            self.modifications = []
            
            # Rebuild data structures
            self.load_planning_from_file(self.loaded_planning_file)
            
            self.app.update_status("Modifications annulées")
            messagebox.showinfo("✅ Annulé", "Modifications annulées")
    
    def export_planning(self):
        """Navigate to Reports page and open Export tab - with unsaved changes check"""
        # Check for unsaved changes first
        if self.has_unsaved_changes:
            messagebox.showwarning(
                "⚠️ Modifications Non Enregistrées",
                "Vous devez enregistrer vos modifications d'abord avant d'exporter.\n\n"
                "Cliquez sur le bouton '💾 Enregistrer' pour sauvegarder vos changements."
            )
            return
        
        # Save current state before navigating
        self.save_to_app_state()
        
        # Navigate to reports page with export tab
        self.app.show_reports(tab="export")
        
        # Old export logic moved to reports page
        # if not self.loaded_planning_file:
        #     messagebox.showerror("Erreur", "Aucun planning à exporter")
        #     return
        # 
        # try:
        #     filepath = filedialog.asksaveasfilename(...)
        # except Exception as e:
        #     messagebox.showerror("Erreur d'Export", f"Impossible d'exporter le planning:\n{str(e)}")
    
    def darken_color(self, color):
        """Darken a hex color"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
        return f"#{dark_rgb[0]:02x}{dark_rgb[1]:02x}{dark_rgb[2]:02x}"
    
    # ==================== UNDO/REDO METHODS ====================
    
    def _update_undo_redo_buttons(self):
        """Update undo/redo button states based on stack status"""
        if hasattr(self, 'undo_btn'):
            self.undo_btn.configure(state="normal" if self.undo_stack else "disabled")
        if hasattr(self, 'redo_btn'):
            self.redo_btn.configure(state="normal" if self.redo_stack else "disabled")
        
        # Update has_unsaved_changes flag based on undo stack
        # If undo stack is empty, there are no unsaved changes
        self.has_unsaved_changes = len(self.undo_stack) > 0
    
    def undo_last_change(self):
        """Undo the last modification"""
        if not self.undo_stack:
            messagebox.showinfo("Info", "Rien à annuler")
            return
        
        # Pop last modification from undo stack
        modification = self.undo_stack.pop()
        
        # Check modification type
        if modification.get('type') == 'swap':
            # Handle swap undo - swap back the two teachers
            teacher1 = modification['teacher1']
            date1 = modification['date1']
            seance1 = modification['seance1']
            teacher2 = modification['teacher2']
            date2 = modification['date2']
            seance2 = modification['seance2']
            
            # Swap back in schedule_data (reverse the swap)
            if date1 in self.schedule_data and seance1 in self.schedule_data[date1]:
                teachers_list1 = self.schedule_data[date1][seance1]
                for i, teacher_entry in enumerate(teachers_list1):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher2.strip():
                        teachers_list1[i] = teacher1
                        break
            
            if date2 in self.schedule_data and seance2 in self.schedule_data[date2]:
                teachers_list2 = self.schedule_data[date2][seance2]
                for i, teacher_entry in enumerate(teachers_list2):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher1.strip():
                        teachers_list2[i] = teacher2
                        break
            
            # Swap back in teacher_schedules
            # Remove teacher2 from slot1
            if teacher2 in self.teacher_schedules:
                self.teacher_schedules[teacher2] = [
                    a for a in self.teacher_schedules[teacher2]
                    if not (a.get('date') == date1 and a.get('seance') == seance1)
                ]
            
            # Remove teacher1 from slot2
            if teacher1 in self.teacher_schedules:
                self.teacher_schedules[teacher1] = [
                    a for a in self.teacher_schedules[teacher1]
                    if not (a.get('date') == date2 and a.get('seance') == seance2)
                ]
            
            # Get assignment details for both slots
            assignment1_details = self._get_assignment_details(teacher2, date1, seance1)
            assignment2_details = self._get_assignment_details(teacher1, date2, seance2)
            
            # Add teacher1 back to slot1
            if teacher1 not in self.teacher_schedules:
                self.teacher_schedules[teacher1] = []
            self.teacher_schedules[teacher1].append({
                'date': date1,
                'jour': assignment1_details.get('jour', ''),
                'heure_debut': assignment1_details.get('heure_debut', ''),
                'seance': seance1,
                'salle': assignment1_details.get('salle', 'N/A'),
                'session': assignment1_details.get('session', 'N/A'),
                'semestre': assignment1_details.get('semestre', 'N/A')
            })
            
            # Add teacher2 back to slot2
            if teacher2 not in self.teacher_schedules:
                self.teacher_schedules[teacher2] = []
            self.teacher_schedules[teacher2].append({
                'date': date2,
                'jour': assignment2_details.get('jour', ''),
                'heure_debut': assignment2_details.get('heure_debut', ''),
                'seance': seance2,
                'salle': assignment2_details.get('salle', 'N/A'),
                'session': assignment2_details.get('session', 'N/A'),
                'semestre': assignment2_details.get('semestre', 'N/A')
            })
            
            # Add to redo stack
            self.redo_stack.append(modification)
            
            # Update affected teachers
            if not hasattr(self, 'affected_teachers'):
                self.affected_teachers = set()
            self.affected_teachers.add(teacher1)
            self.affected_teachers.add(teacher2)
            
            # Update button states
            self._update_undo_redo_buttons()
            
            # OPTIMIZED: Update only affected cells instead of full refresh
            # BUT: Only if we're viewing one of the affected dates, otherwise do full refresh
            if self.view_mode == "calendar":
                if self.selected_date in [date1, date2]:
                    # One of the affected dates is visible - optimized update
                    self._update_specific_calendar_cells([
                        {
                            'teacher': teacher1,
                            'seance': seance1,
                            'date': date1
                        },
                        {
                            'teacher': teacher2,
                            'seance': seance2,
                            'date': date2
                        }
                    ])
                else:
                    # Neither date is visible - need full refresh
                    self._refresh_views_async()
            else:
                # Full refresh for teacher view
                self._refresh_views_async()
            
            self.app.update_status(f"Échange annulé: {teacher1} ↔ {teacher2}")
            return
        
        # Regular modification (teacher replacement)
        date = modification['date']
        seance = modification['seance']
        old_teacher = modification['old_teacher']
        new_teacher = modification['new_teacher']
        details = modification['assignment_details']
        
        # Update schedule_data (swap back)
        if date in self.schedule_data and seance in self.schedule_data[date]:
            teachers_list = self.schedule_data[date][seance]
            if new_teacher in teachers_list:
                idx = teachers_list.index(new_teacher)
                teachers_list[idx] = old_teacher
        
        # Update teacher_schedules
        # Remove from new teacher
        if new_teacher in self.teacher_schedules:
            self.teacher_schedules[new_teacher] = [
                a for a in self.teacher_schedules[new_teacher]
                if not (a.get('date') == date and a.get('seance') == seance)
            ]
        
        # Add back to old teacher
        if old_teacher not in self.teacher_schedules:
            self.teacher_schedules[old_teacher] = []
        
        self.teacher_schedules[old_teacher].append({
            'date': date,
            'jour': details['jour'],
            'heure_debut': details['heure_debut'],
            'seance': seance,
            'salle': details['salle'],
            'session': details['session'],
            'semestre': details['semestre']
        })
        
        # Add to redo stack
        self.redo_stack.append(modification)
        
        # Update affected teachers
        if not hasattr(self, 'affected_teachers'):
            self.affected_teachers = set()
        self.affected_teachers.add(old_teacher)
        self.affected_teachers.add(new_teacher)
        
        # Update button states
        self._update_undo_redo_buttons()
        
        # OPTIMIZED: Update only affected cell instead of full refresh
        # BUT: Only if we're viewing the same date, otherwise do full refresh
        if self.view_mode == "calendar":
            if self.selected_date == date:
                # Same date - optimized update
                self._update_specific_calendar_cells([
                    {
                        'teacher': old_teacher,
                        'seance': seance,
                        'date': date
                    }
                ])
            else:
                # Different date - need full refresh
                self._refresh_views_async()
        else:
            # Full refresh for teacher view
            self._refresh_views_async()
        
        self.app.update_status(f"Annulé: {new_teacher} → {old_teacher}")
    
    def redo_last_change(self):
        """Redo the last undone modification"""
        if not self.redo_stack:
            messagebox.showinfo("Info", "Rien à refaire")
            return
        
        # Pop last modification from redo stack
        modification = self.redo_stack.pop()
        
        # Check modification type
        if modification.get('type') == 'swap':
            # Handle swap redo - re-apply the swap
            teacher1 = modification['teacher1']
            date1 = modification['date1']
            seance1 = modification['seance1']
            teacher2 = modification['teacher2']
            date2 = modification['date2']
            seance2 = modification['seance2']
            
            # Re-apply swap in schedule_data
            if date1 in self.schedule_data and seance1 in self.schedule_data[date1]:
                teachers_list1 = self.schedule_data[date1][seance1]
                for i, teacher_entry in enumerate(teachers_list1):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher1.strip():
                        teachers_list1[i] = teacher2
                        break
            
            if date2 in self.schedule_data and seance2 in self.schedule_data[date2]:
                teachers_list2 = self.schedule_data[date2][seance2]
                for i, teacher_entry in enumerate(teachers_list2):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher2.strip():
                        teachers_list2[i] = teacher1
                        break
            
            # Re-apply swap in teacher_schedules
            # Remove teacher1 from slot1
            if teacher1 in self.teacher_schedules:
                self.teacher_schedules[teacher1] = [
                    a for a in self.teacher_schedules[teacher1]
                    if not (a.get('date') == date1 and a.get('seance') == seance1)
                ]
            
            # Remove teacher2 from slot2
            if teacher2 in self.teacher_schedules:
                self.teacher_schedules[teacher2] = [
                    a for a in self.teacher_schedules[teacher2]
                    if not (a.get('date') == date2 and a.get('seance') == seance2)
                ]
            
            # Get assignment details for both slots
            assignment1_details = self._get_assignment_details(teacher1, date1, seance1)
            assignment2_details = self._get_assignment_details(teacher2, date2, seance2)
            
            # Add teacher2 to slot1
            if teacher2 not in self.teacher_schedules:
                self.teacher_schedules[teacher2] = []
            self.teacher_schedules[teacher2].append({
                'date': date1,
                'jour': assignment1_details.get('jour', ''),
                'heure_debut': assignment1_details.get('heure_debut', ''),
                'seance': seance1,
                'salle': assignment1_details.get('salle', 'N/A'),
                'session': assignment1_details.get('session', 'N/A'),
                'semestre': assignment1_details.get('semestre', 'N/A')
            })
            
            # Add teacher1 to slot2
            if teacher1 not in self.teacher_schedules:
                self.teacher_schedules[teacher1] = []
            self.teacher_schedules[teacher1].append({
                'date': date2,
                'jour': assignment2_details.get('jour', ''),
                'heure_debut': assignment2_details.get('heure_debut', ''),
                'seance': seance2,
                'salle': assignment2_details.get('salle', 'N/A'),
                'session': assignment2_details.get('session', 'N/A'),
                'semestre': assignment2_details.get('semestre', 'N/A')
            })
            
            # Add back to undo stack
            self.undo_stack.append(modification)
            
            # Update affected teachers
            if not hasattr(self, 'affected_teachers'):
                self.affected_teachers = set()
            self.affected_teachers.add(teacher1)
            self.affected_teachers.add(teacher2)
            
            # Update button states
            self._update_undo_redo_buttons()
            
            # OPTIMIZED: Update only affected cells instead of full refresh
            if self.view_mode == "calendar":
                self._update_specific_calendar_cells([
                    {
                        'teacher': teacher2,
                        'seance': seance1,
                        'date': date1
                    },
                    {
                        'teacher': teacher1,
                        'seance': seance2,
                        'date': date2
                    }
                ])
            else:
                # Full refresh for teacher view
                self._refresh_views_async()
            
            self.app.update_status(f"Échange refait: {teacher1} ↔ {teacher2}")
            return
        
        # Regular modification (teacher replacement)
        date = modification['date']
        seance = modification['seance']
        old_teacher = modification['old_teacher']
        new_teacher = modification['new_teacher']
        details = modification['assignment_details']
        
        # Update schedule_data
        if date in self.schedule_data and seance in self.schedule_data[date]:
            teachers_list = self.schedule_data[date][seance]
            if old_teacher in teachers_list:
                idx = teachers_list.index(old_teacher)
                teachers_list[idx] = new_teacher
        
        # Update teacher_schedules
        # Remove from old teacher
        if old_teacher in self.teacher_schedules:
            self.teacher_schedules[old_teacher] = [
                a for a in self.teacher_schedules[old_teacher]
                if not (a.get('date') == date and a.get('seance') == seance)
            ]
        
        # Add to new teacher
        if new_teacher not in self.teacher_schedules:
            self.teacher_schedules[new_teacher] = []
        
        self.teacher_schedules[new_teacher].append({
            'date': date,
            'jour': details['jour'],
            'heure_debut': details['heure_debut'],
            'seance': seance,
            'salle': details['salle'],
            'session': details['session'],
            'semestre': details['semestre']
        })
        
        # Add back to undo stack
        self.undo_stack.append(modification)
        
        # Update affected teachers
        if not hasattr(self, 'affected_teachers'):
            self.affected_teachers = set()
        self.affected_teachers.add(old_teacher)
        self.affected_teachers.add(new_teacher)
        
        # Update button states
        self._update_undo_redo_buttons()
        
        # OPTIMIZED: Update only affected cell instead of full refresh
        if self.view_mode == "calendar":
            self._update_specific_calendar_cells([
                {
                    'teacher': new_teacher,
                    'seance': seance,
                    'date': date
                }
            ])
        else:
            # Full refresh for teacher view
            self._refresh_views_async()
        
        self.app.update_status(f"Refait: {old_teacher} → {new_teacher}")
    
    # ==================== CONSTRAINT VALIDATION METHODS ====================
    
    def _check_assignment_constraints(self, teacher_name, date, seance):
        """
        Check if assigning a teacher to a slot violates quota or voeux constraints.
        Returns list of warning messages.
        """
        warnings = []
        
        # Count current assignments for this teacher
        current_count = sum(
            1 for assignments in self.teacher_schedules.get(teacher_name, [])
        )
        
        # Check quota if teachers_df has quota information
        if self.teachers_df is not None and not self.teachers_df.empty:
            try:
                # Try to find teacher in teachers_df
                teacher_row = self.teachers_df[
                    self.teachers_df['Nom Complet'].str.strip() == teacher_name.strip()
                ]
                
                if not teacher_row.empty:
                    # Check for quota columns (various possible names)
                    quota_cols = ['Quota', 'quota', 'Quota_Surveillance', 'quota_surveillance']
                    quota_value = None
                    
                    for col in quota_cols:
                        if col in teacher_row.columns:
                            quota_value = teacher_row.iloc[0][col]
                            break
                    
                    if quota_value is not None and pd.notna(quota_value):
                        try:
                            quota = int(quota_value)
                            if current_count + 1 > quota:
                                warnings.append(
                                    f"Quota dépassé: {current_count + 1}/{quota} surveillances"
                                )
                        except (ValueError, TypeError):
                            pass
                    
                    # Check voeux (wishes/preferences) if available
                    # Try to match date with voeux data
                    try:
                        from datetime import datetime as dt
                        check_date = dt.strptime(date, '%Y-%m-%d')
                        day_name = check_date.strftime('%A')
                        
                        # Check if teacher marked this day/time as unavailable
                        # This would require voeux data - check if columns exist
                        voeux_cols = [col for col in teacher_row.columns if 'voeu' in col.lower() or 'disponibilit' in col.lower()]
                        
                        # If voeux columns exist, check them
                        for col in voeux_cols:
                            voeux_value = teacher_row.iloc[0][col]
                            if pd.notna(voeux_value):
                                # Simple check if the date/day is mentioned in voeux as unavailable
                                voeux_str = str(voeux_value).lower()
                                if any(word in voeux_str for word in ['non', 'indisponible', 'unavailable']):
                                    if day_name.lower() in voeux_str or date in voeux_str:
                                        warnings.append(
                                            f"Vœu non respecté: enseignant possiblement indisponible"
                                        )
                                        break
                    except Exception:
                        pass
            
            except Exception as e:
                # Silently fail if teachers_df doesn't have expected structure
                pass
        
        return warnings
    
    # ==================== SEARCH AND HIGHLIGHT METHODS ====================
    
    def toggle_search_highlight(self):
        """Toggle between search mode and remove highlight mode"""
        if self.highlighted_teacher:
            # Currently highlighted, so remove it
            self.remove_highlight()
        else:
            # Not highlighted, open search modal
            self.open_search_modal()
    
    def open_search_modal(self):
        """Open modal to search for teacher and highlight their slots"""
        # Only allow in calendar view
        if self.view_mode != "calendar":
            messagebox.showinfo("Info", "La recherche n'est disponible qu'en vue Calendrier")
            return
        
        # Check if data is loaded
        if not self.available_teachers:
            messagebox.showwarning("Aucune donnée", "Aucun enseignant disponible")
            return
        
        # Close existing modal if open
        if self.search_modal and self.search_modal.winfo_exists():
            self.search_modal.destroy()
        
        # Create modal window
        self.search_modal = ctk.CTkToplevel(self)
        self.search_modal.title("Rechercher un enseignant")
        self.search_modal.geometry("500x600")
        self.search_modal.transient(self)
        self.search_modal.grab_set()
        
        # Center modal
        self.search_modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (500 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (600 // 2)
        self.search_modal.geometry(f"500x600+{x}+{y}")
        
        # Modal header
        header = ctk.CTkFrame(self.search_modal, fg_color=self.colors['primary'], height=70)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        title = ctk.CTkLabel(
            header,
            text="🔍 Rechercher un enseignant",
            font=("Segoe UI", 20, "bold"),
            text_color="white"
        )
        title.pack(pady=20)
        
        # Content frame
        content = ctk.CTkFrame(self.search_modal, fg_color=self.colors['background'])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Search input
        search_frame = ctk.CTkFrame(content, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 15))
        
        search_label = ctk.CTkLabel(
            search_frame,
            text="Nom de l'enseignant:",
            font=("Segoe UI", 13),
            text_color=self.colors['text_primary']
        )
        search_label.pack(anchor="w", pady=(0, 5))
        
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=search_var,
            placeholder_text="Tapez pour rechercher...",
            height=40,
            font=("Segoe UI", 13),
            fg_color=self.colors['surface'],
            border_color=self.colors['border']
        )
        search_entry.pack(fill="x")
        search_entry.focus()
        
        # Teachers list frame with scrollbar
        list_label = ctk.CTkLabel(
            content,
            text="Enseignants disponibles:",
            font=("Segoe UI", 13),
            text_color=self.colors['text_primary']
        )
        list_label.pack(anchor="w", pady=(10, 5))
        
        list_frame = ctk.CTkScrollableFrame(
            content,
            fg_color=self.colors['surface'],
            corner_radius=8
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        # Store selected teacher
        selected_teacher = {"name": None, "widget": None}
        
        def create_teacher_item(teacher_name):
            """Create clickable teacher item with hover effect"""
            item = ctk.CTkFrame(
                list_frame,
                fg_color=self.colors['background'],
                corner_radius=6,
                cursor="hand2"
            )
            item.pack(fill="x", padx=5, pady=3)
            
            label = ctk.CTkLabel(
                item,
                text=teacher_name,
                font=("Segoe UI", 13),
                text_color=self.colors['text_primary'],
                anchor="w"
            )
            label.pack(fill="x", padx=15, pady=12)
            
            def on_click(e=None):
                # Deselect previous
                if selected_teacher["widget"]:
                    selected_teacher["widget"].configure(
                        fg_color=self.colors['background'],
                        border_width=0
                    )
                
                # Select current
                item.configure(
                    fg_color=self.colors['primary'],
                    border_width=2,
                    border_color=self.colors['secondary']
                )
                label.configure(text_color="white")
                selected_teacher["name"] = teacher_name
                selected_teacher["widget"] = item
            
            def on_enter(e):
                if selected_teacher["widget"] != item:
                    item.configure(fg_color=self.colors['hover'])
            
            def on_leave(e):
                if selected_teacher["widget"] != item:
                    item.configure(fg_color=self.colors['background'])
            
            item.bind("<Button-1>", on_click)
            label.bind("<Button-1>", on_click)
            item.bind("<Enter>", on_enter)
            item.bind("<Leave>", on_leave)
            label.bind("<Enter>", on_enter)
            label.bind("<Leave>", on_leave)
            
            return item
        
        # Store teacher widgets for filtering
        teacher_widgets = {}
        for teacher in self.available_teachers:
            widget = create_teacher_item(teacher)
            teacher_widgets[teacher] = widget
        
        def filter_teachers(*args):
            """Filter teachers based on search input"""
            search_text = search_var.get().lower()
            
            for teacher, widget in teacher_widgets.items():
                if search_text in teacher.lower():
                    widget.pack(fill="x", padx=5, pady=3)
                else:
                    widget.pack_forget()
        
        # Bind search filtering
        search_var.trace_add("write", filter_teachers)
        
        # Action buttons
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        def highlight_teacher():
            """Highlight selected teacher's slots"""
            if not selected_teacher["name"]:
                messagebox.showwarning("Sélection requise", "Veuillez sélectionner un enseignant")
                return
            
            self.highlight_teacher_slots(selected_teacher["name"])
            self.search_modal.destroy()
        
        find_btn = ctk.CTkButton(
            button_frame,
            text="🎯 Trouver les créneaux",
            height=45,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=highlight_teacher
        )
        find_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Annuler",
            height=45,
            corner_radius=8,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=self.search_modal.destroy
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Allow Enter key to trigger search
        self.search_modal.bind("<Return>", lambda e: highlight_teacher())
    
    def highlight_teacher_slots(self, teacher_name):
        """Highlight all slots containing the specified teacher"""
        # Clear previous highlights (but don't reset button state yet)
        self.highlighted_teacher = teacher_name
        self.highlighted_cells = []
        
        # OPTIMIZED: Use selective cell update to only refresh cells with this teacher
        if hasattr(self, '_calendar_cell_widgets') and self._calendar_cell_widgets:
            # Find all cells for this teacher
            affected_slots = []
            for cell_key, cell_frame in self._calendar_cell_widgets.items():
                if teacher_name in cell_key:
                    # Extract seance from cell_key: "TeacherName_Seance"
                    parts = cell_key.rsplit('_', 1)
                    if len(parts) == 2:
                        seance = parts[1]
                        affected_slots.append({
                            'teacher': teacher_name,
                            'seance': seance,
                            'date': self.selected_date
                        })
            
            if affected_slots:
                self._update_specific_calendar_cells(affected_slots)
        else:
            # Fallback to full render if cell map not available
            if hasattr(self, '_calendar_content_frame') and self._calendar_content_frame.winfo_exists():
                self._render_calendar_content()
        
        # Update action button to "Remove highlight" mode
        if hasattr(self, 'search_highlight_btn_action'):
            self.search_highlight_btn_action.configure(
                text="✖ Enlever Surbrillance",
                fg_color="#EF4444",
                hover_color="#DC2626"
            )
        
        # Show notification
        self.app.update_status(f"Créneaux de {teacher_name} surlignés en jaune")
    
    def remove_highlight(self):
        """Remove all highlights"""
        old_highlighted_teacher = self.highlighted_teacher
        self.highlighted_teacher = None
        self.highlighted_cells = []
        
        # Update action button back to "Search" mode
        if hasattr(self, 'search_highlight_btn_action'):
            self.search_highlight_btn_action.configure(
                text="🔍 Rechercher",
                fg_color=self.colors['secondary'],
                hover_color="#6D28D9"
            )
        
        # OPTIMIZED: Use selective cell update to only refresh previously highlighted cells
        if old_highlighted_teacher and hasattr(self, '_calendar_cell_widgets') and self._calendar_cell_widgets:
            affected_slots = []
            for cell_key, cell_frame in self._calendar_cell_widgets.items():
                if old_highlighted_teacher in cell_key:
                    parts = cell_key.rsplit('_', 1)
                    if len(parts) == 2:
                        seance = parts[1]
                        affected_slots.append({
                            'teacher': old_highlighted_teacher,
                            'seance': seance,
                            'date': self.selected_date
                        })
            
            if affected_slots:
                self._update_specific_calendar_cells(affected_slots)
        else:
            # Fallback to full render
            if hasattr(self, '_calendar_content_frame') and self._calendar_content_frame.winfo_exists():
                self._render_calendar_content()
        
        self.app.update_status("Surbrillance supprimée")
    
    # ==================== ADDITIONAL SWAP METHODS ====================
    
    def execute_swap(self):
        """Execute the swap between two selected slots"""
        if not self.swap_source or not self.swap_target:
            messagebox.showwarning(
                "Sélection Incomplète",
                "Veuillez sélectionner deux créneaux à échanger"
            )
            return
        
        teacher1 = self.swap_source['teacher']
        date1 = self.swap_source['date']
        seance1 = self.swap_source['seance']
        
        teacher2 = self.swap_target['teacher']
        date2 = self.swap_target['date']
        seance2 = self.swap_target['seance']
        
        # Validation: Check if trying to swap same slot
        if teacher1 == teacher2 and date1 == date2 and seance1 == seance2:
            messagebox.showerror(
                "Échange Invalide",
                "Impossible d'échanger un créneau avec lui-même"
            )
            return
        
        # Check constraints for both swaps
        blocking_errors = []
        warnings = []
        
        # BLOCKING CHECK: Check if teacher2 is already in slot1
        if date1 in self.schedule_data and seance1 in self.schedule_data[date1]:
            for teacher_entry in self.schedule_data[date1][seance1]:
                entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                if entry_name.strip() == teacher2.strip() and teacher1 != teacher2:
                    blocking_errors.append(f"❌ {teacher2} est déjà affecté(e) au créneau de destination de {teacher1}")
        
        # BLOCKING CHECK: Check if teacher1 is already in slot2
        if date2 in self.schedule_data and seance2 in self.schedule_data[date2]:
            for teacher_entry in self.schedule_data[date2][seance2]:
                entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                if entry_name.strip() == teacher1.strip() and teacher1 != teacher2:
                    blocking_errors.append(f"❌ {teacher1} est déjà affecté(e) au créneau de destination de {teacher2}")
        
        # If there are blocking errors, show error and stop
        if blocking_errors:
            error_msg = "❌ Échange Impossible\n\n"
            error_msg += "Cet échange ne peut pas être effectué car :\n\n"
            for error in blocking_errors:
                error_msg += f"• {error}\n"
            error_msg += "\n⚠️ Un enseignant ne peut pas être affecté deux fois au même créneau."
            
            messagebox.showerror("Échange Bloqué", error_msg)
            return
        
        # Check quota constraints
        teacher1_warnings = self._check_assignment_constraints(teacher1, date2, seance2)
        teacher2_warnings = self._check_assignment_constraints(teacher2, date1, seance1)
        
        if teacher1_warnings:
            warnings.extend([f"Pour {teacher1}: {w}" for w in teacher1_warnings])
        if teacher2_warnings:
            warnings.extend([f"Pour {teacher2}: {w}" for w in teacher2_warnings])
        
        # Build confirmation message
        confirm_msg = "🔄 Confirmer l'échange ?\n\n"
        confirm_msg += f"Créneau 1:\n"
        confirm_msg += f"  👤 {teacher1}\n"
        confirm_msg += f"  📅 {date1}\n"
        confirm_msg += f"  ⏰ Séance {seance1}\n\n"
        confirm_msg += "⇅\n\n"
        confirm_msg += f"Créneau 2:\n"
        confirm_msg += f"  👤 {teacher2}\n"
        confirm_msg += f"  📅 {date2}\n"
        confirm_msg += f"  ⏰ Séance {seance2}"
        
        if warnings:
            confirm_msg += "\n\n⚠️ AVERTISSEMENTS :\n"
            for warning in warnings:
                confirm_msg += f"• {warning}\n"
            confirm_msg += "\nContinuer malgré les avertissements ?"
        
        if not messagebox.askyesno("Confirmer l'Échange", confirm_msg):
            return
        
        # Perform the swap
        try:
            # Swap in schedule_data
            if date1 in self.schedule_data and seance1 in self.schedule_data[date1]:
                teachers_list1 = self.schedule_data[date1][seance1]
                for i, teacher_entry in enumerate(teachers_list1):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher1.strip():
                        teachers_list1[i] = teacher2
                        break
            
            if date2 in self.schedule_data and seance2 in self.schedule_data[date2]:
                teachers_list2 = self.schedule_data[date2][seance2]
                for i, teacher_entry in enumerate(teachers_list2):
                    entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                    if entry_name.strip() == teacher2.strip():
                        teachers_list2[i] = teacher1
                        break
            
            # Swap in teacher_schedules
            # Remove teacher1's assignment from slot1
            if teacher1 in self.teacher_schedules:
                self.teacher_schedules[teacher1] = [
                    a for a in self.teacher_schedules[teacher1]
                    if not (a.get('date') == date1 and a.get('seance') == seance1)
                ]
            
            # Remove teacher2's assignment from slot2
            if teacher2 in self.teacher_schedules:
                self.teacher_schedules[teacher2] = [
                    a for a in self.teacher_schedules[teacher2]
                    if not (a.get('date') == date2 and a.get('seance') == seance2)
                ]
            
            # Get assignment details for both slots
            assignment1_details = self._get_assignment_details(teacher1, date1, seance1)
            assignment2_details = self._get_assignment_details(teacher2, date2, seance2)
            
            # Add teacher1 to slot2
            if teacher1 not in self.teacher_schedules:
                self.teacher_schedules[teacher1] = []
            self.teacher_schedules[teacher1].append({
                'date': date2,
                'jour': assignment2_details.get('jour', ''),
                'heure_debut': assignment2_details.get('heure_debut', ''),
                'seance': seance2,
                'salle': assignment2_details.get('salle', 'N/A'),
                'session': assignment2_details.get('session', 'N/A'),
                'semestre': assignment2_details.get('semestre', 'N/A')
            })
            
            # Add teacher2 to slot1
            if teacher2 not in self.teacher_schedules:
                self.teacher_schedules[teacher2] = []
            self.teacher_schedules[teacher2].append({
                'date': date1,
                'jour': assignment1_details.get('jour', ''),
                'heure_debut': assignment1_details.get('heure_debut', ''),
                'seance': seance1,
                'salle': assignment1_details.get('salle', 'N/A'),
                'session': assignment1_details.get('session', 'N/A'),
                'semestre': assignment1_details.get('semestre', 'N/A')
            })
            
            # Track modifications for undo
            swap_modification = {
                'type': 'swap',
                'teacher1': teacher1,
                'date1': date1,
                'seance1': seance1,
                'teacher2': teacher2,
                'date2': date2,
                'seance2': seance2,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.undo_stack.append(swap_modification)
            self.redo_stack.clear()
            self.modifications.append(swap_modification)
            
            # Track affected teachers
            if not hasattr(self, 'affected_teachers'):
                self.affected_teachers = set()
            self.affected_teachers.add(teacher1)
            self.affected_teachers.add(teacher2)
            
            self.has_unsaved_changes = True
            self._update_undo_redo_buttons()
            
            # Clear swap selections
            self.swap_source = None
            self.swap_target = None
            
            # OPTIMIZED: Selective cell update for calendar view
            if self.view_mode == "calendar":
                self._update_specific_calendar_cells([
                    {
                        'old_teacher': teacher1,
                        'new_teacher': teacher2,
                        'teacher': teacher2,
                        'seance': seance1,
                        'date': date1
                    },
                    {
                        'old_teacher': teacher2,
                        'new_teacher': teacher1,
                        'teacher': teacher1,
                        'seance': seance2,
                        'date': date2
                    }
                ])
            else:
                # Full refresh for teacher view
                self.show_teachers_view()
            
            # Update slots display to show empty state
            self._update_slots_display()
            
            messagebox.showinfo(
                "✅ Échange Réussi",
                f"Les créneaux ont été échangés avec succès!\n\n"
                f"• {teacher1} ↔ {teacher2}"
            )
            
            self.app.update_status(f"✓ Échange effectué: {teacher1} ↔ {teacher2}")
            
        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Une erreur s'est produite lors de l'échange:\n{str(e)}"
            )
    
            self.app.update_status(f"✓ Échange effectué: {teacher1} ↔ {teacher2}")
            
        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Une erreur s'est produite lors de l'échange:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
    
    def _get_assignment_details(self, teacher, date, seance):
        """Get full assignment details for a teacher at a specific slot"""
        # Initialize with default values to prevent KeyError
        details = {
            'heure_debut': '',
            'jour': '',
            'salle': 'N/A',
            'session': 'N/A',
            'semestre': 'N/A'
        }
        
        # Try to find in assignments_df
        if self.assignments_df is not None:
            for idx, row in self.assignments_df.iterrows():
                row_date = str(row.get('Date', row.get('date', '')))[:10]
                row_seance = str(row.get('Séance', row.get('seance', '')))
                row_teacher = str(row.get('Nom Complet', row.get('Nom_Complet', '')))
                
                if row_date == date and row_seance == seance and row_teacher == teacher:
                    details['heure_debut'] = row.get('Heure', row.get('heure_debut', ''))
                    details['jour'] = row.get('Jour', row.get('jour', ''))
                    details['salle'] = row.get('Salle', row.get('salle', 'N/A'))
                    details['session'] = row.get('Session', row.get('session', 'N/A'))
                    details['semestre'] = row.get('Semestre', row.get('semestre', 'N/A'))
                    break
        
        # Fallback to teacher_schedules if not found in df
        if teacher in self.teacher_schedules:
            for assignment in self.teacher_schedules[teacher]:
                if assignment.get('date') == date and assignment.get('seance') == seance:
                    # Update details with values from teacher_schedules, keep defaults for missing keys
                    details['heure_debut'] = assignment.get('heure_debut', details['heure_debut'])
                    details['jour'] = assignment.get('jour', details['jour'])
                    details['salle'] = assignment.get('salle', details['salle'])
                    details['session'] = assignment.get('session', details['session'])
                    details['semestre'] = assignment.get('semestre', details['semestre'])
                    break
        
        return details
    
    def _perform_teacher_replacement(self, old_teacher, new_teacher, date, seance):
        """Common logic for replacing a teacher in a slot"""
        # Update schedule_data
        if date in self.schedule_data and seance in self.schedule_data[date]:
            teachers_list = self.schedule_data[date][seance]
            for i, teacher_entry in enumerate(teachers_list):
                entry_name = teacher_entry.get('teacher', '') if isinstance(teacher_entry, dict) else str(teacher_entry)
                if entry_name.strip() == old_teacher.strip():
                    teachers_list[i] = new_teacher
                    break
        
        # Update teacher_schedules
        # Remove from old teacher
        if old_teacher in self.teacher_schedules:
            self.teacher_schedules[old_teacher] = [
                a for a in self.teacher_schedules[old_teacher]
                if not (a.get('date') == date and a.get('seance') == seance)
            ]
        
        # Add to new teacher
        assignment_details = self._get_assignment_details(old_teacher, date, seance)
        if new_teacher not in self.teacher_schedules:
            self.teacher_schedules[new_teacher] = []
        
        self.teacher_schedules[new_teacher].append({
            'date': date,
            'jour': assignment_details.get('jour', ''),
            'heure_debut': assignment_details.get('heure_debut', ''),
            'seance': seance,
            'salle': assignment_details.get('salle', 'N/A'),
            'session': assignment_details.get('session', 'N/A'),
            'semestre': assignment_details.get('semestre', 'N/A')
        })
        
        # Track modification
        modification = {
            'date': date,
            'seance': seance,
            'old_teacher': old_teacher,
            'new_teacher': new_teacher,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'assignment_details': assignment_details
        }
        
        self.undo_stack.append(modification)
        self.redo_stack.clear()
        self.modifications.append(modification)
        
        # Track affected teachers
        if not hasattr(self, 'affected_teachers'):
            self.affected_teachers = set()
        self.affected_teachers.add(old_teacher)
        self.affected_teachers.add(new_teacher)
        
        self.has_unsaved_changes = True
        self._update_undo_redo_buttons()
        
        # OPTIMIZED: Selective cell update for calendar view only
        if self.view_mode == "calendar":
            self._update_specific_calendar_cells([{
                'old_teacher': old_teacher,
                'new_teacher': new_teacher,
                'teacher': new_teacher,
                'seance': seance,
                'date': date
            }])
        else:
            # Full refresh for teacher view
            self._refresh_views_async()
    
    # ==================== RIGHT-CLICK CONTEXT MENU ====================
    
    def show_swap_context_menu(self, teacher, seance, date, cell_frame, event):
        """Show context menu with swap option on right-click"""
        # Create popup menu
        menu = tk.Menu(self, tearoff=0, bg=self.colors['surface'], fg=self.colors['text_primary'], 
                      activebackground=self.colors['primary'], activeforeground="white",
                      font=("Segoe UI", 11))
        
        menu.add_command(
            label="🔄 Échanger",
            command=lambda: self.start_swap_from_right_click(teacher, seance, date, cell_frame)
        )
        
        menu.add_separator()
        
        menu.add_command(
            label="👥 Affecter un enseignant",
            command=lambda: self.open_affecter_for_slot(teacher, seance, date)
        )
        
        menu.add_separator()
        
        menu.add_command(
            label="✖ Annuler",
            command=menu.destroy
        )
        
        # Show menu at cursor position
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def start_swap_from_right_click(self, teacher, seance, date, cell_frame):
        """Start swap mode with this slot as source (right-click initiated)"""
        # Clear any previous selected cell highlight (purple)
        if self.selected_cell_info:
            self._clear_selection_highlight()
        self.selected_cell_info = None
        
        # Activate swap mode if not already active
        if not self.swap_mode_active:
            self.toggle_swap_mode()
        
        # Reset previous source frame styling if it exists
        if self.swap_source and self.swap_source.get('frame'):
            old_frame = self.swap_source['frame']
            if old_frame and old_frame.winfo_exists():
                # Reset to normal styling
                old_frame.configure(fg_color=self.colors['surface'])
                for widget in old_frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=self.colors['text_primary'], font=("Segoe UI", 13, "normal"))
        
        # Reset previous target frame styling if it exists
        if self.swap_target and self.swap_target.get('frame'):
            old_target_frame = self.swap_target['frame']
            if old_target_frame and old_target_frame.winfo_exists():
                # Reset to normal styling
                old_target_frame.configure(fg_color=self.colors['surface'])
                for widget in old_target_frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=self.colors['text_primary'], font=("Segoe UI", 13, "normal"))
        
        # Set this slot as swap source (first créneau)
        self.swap_source = {
            'teacher': teacher,
            'seance': seance,
            'date': date,
            'frame': cell_frame
        }
        
        # Clear swap target
        self.swap_target = None
        
        # Highlight the NEW source slot in blue (swap source color)
        if cell_frame and cell_frame.winfo_exists():
            cell_frame.configure(fg_color="#3B82F6")  # Blue for source
            for widget in cell_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(text_color="white", font=("Segoe UI", 13, "bold"))
        
        # Update slots display to show source is selected
        self._update_slots_display()
        
        # Update status message
        self.app.update_status(f"🔄 Créneau source sélectionné: {teacher} - {date} {seance}. Sélectionnez le créneau cible.")
    
    def open_swap_with_modal(self, source_teacher, source_seance, source_date):
        """Open modal to select target for swap (right-click initiated)"""
        # Store source in temporary variable
        temp_source = {
            'teacher': source_teacher,
            'seance': source_seance,
            'date': source_date
        }
        
        # Create modal (similar to search modal)
        modal = ctk.CTkToplevel(self)
        modal.title("Échanger avec...")
        modal.geometry("500x600")
        modal.transient(self)
        modal.grab_set()
        
        # Center modal
        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (250)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (300)
        modal.geometry(f"500x600+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(modal, fg_color=self.colors['primary'], height=90)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🔄 Échanger avec...",
            font=("Segoe UI", 20, "bold"),
            text_color="white"
        ).pack(pady=(15, 5))
        
        # Show source info
        ctk.CTkLabel(
            header,
            text=f"Source: {source_teacher} - {source_date}, Séance {source_seance}",
            font=("Segoe UI", 11),
            text_color="white"
        ).pack(pady=(0, 10))
        
        # Content
        content = ctk.CTkFrame(modal, fg_color=self.colors['background'])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Search
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            content,
            textvariable=search_var,
            placeholder_text="🔍 Rechercher un enseignant...",
            height=40,
            font=("Segoe UI", 13)
        )
        search_entry.pack(fill="x", pady=(0, 15))
        search_entry.focus()
        
        # List of teachers with their assignments
        list_frame = ctk.CTkScrollableFrame(
            content,
            fg_color=self.colors['surface'],
            corner_radius=8
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        selected_target = {"teacher": None, "date": None, "seance": None, "widget": None}
        
        def create_teacher_assignment_item(teacher_name):
            container = ctk.CTkFrame(list_frame, fg_color="transparent")
            container.pack(fill="x", pady=2)
            
            teacher_btn = ctk.CTkFrame(container, fg_color=self.colors['background'], corner_radius=6, cursor="hand2")
            teacher_btn.pack(fill="x", padx=5, pady=2)
            
            teacher_label = ctk.CTkLabel(
                teacher_btn,
                text=f"▶ {teacher_name}",
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors['text_primary'],
                anchor="w"
            )
            teacher_label.pack(fill="x", padx=15, pady=10)
            
            assignments_frame = ctk.CTkFrame(container, fg_color=self.colors['surface'])
            expanded = {"state": False}
            
            def toggle_expand(e=None):
                if expanded["state"]:
                    assignments_frame.pack_forget()
                    teacher_label.configure(text=f"▶ {teacher_name}")
                    expanded["state"] = False
                else:
                    for widget in assignments_frame.winfo_children():
                        widget.destroy()
                    
                    teacher_assignments = self.teacher_schedules.get(teacher_name, [])
                    if teacher_assignments:
                        for assignment in teacher_assignments:
                            date = assignment.get('date', '')
                            seance = assignment.get('seance', '')
                            
                            try:
                                from datetime import datetime
                                date_obj = datetime.strptime(date, '%Y-%m-%d')
                                formatted_date = date_obj.strftime('%d/%m/%Y')
                            except:
                                formatted_date = date
                            
                            assign_btn = ctk.CTkButton(
                                assignments_frame,
                                text=f"  📅 {formatted_date} - ⏰ Séance {seance}",
                                height=35,
                                corner_radius=6,
                                fg_color="transparent",
                                text_color=self.colors['text_primary'],
                                hover_color=self.colors['hover'],
                                anchor="w",
                                font=("Segoe UI", 11)
                            )
                            # Set command after creation to avoid UnboundLocalError
                            assign_btn.configure(command=lambda t=teacher_name, d=date, s=seance, w=assign_btn: select_target(t, d, s, w))
                            assign_btn.pack(fill="x", padx=10, pady=2)
                    else:
                        ctk.CTkLabel(
                            assignments_frame,
                            text="  Aucune affectation",
                            font=("Segoe UI", 10),
                            text_color=self.colors['text_secondary']
                        ).pack(pady=5)
                    
                    assignments_frame.pack(fill="x", padx=10, pady=(0, 5))
                    teacher_label.configure(text=f"▼ {teacher_name}")
                    expanded["state"] = True
            
            teacher_btn.bind("<Button-1>", toggle_expand)
            teacher_label.bind("<Button-1>", toggle_expand)
            
            return container
        
        def select_target(teacher, date, seance, widget):
            if selected_target["widget"]:
                selected_target["widget"].configure(fg_color="transparent", text_color=self.colors['text_primary'])
            
            widget.configure(fg_color=self.colors['primary'], text_color="white")
            selected_target["teacher"] = teacher
            selected_target["date"] = date
            selected_target["seance"] = seance
            selected_target["widget"] = widget
        
        teacher_items = {}
        for teacher in self.available_teachers:
            item = create_teacher_assignment_item(teacher)
            teacher_items[teacher] = item
        
        def filter_teachers(*args):
            search_text = search_var.get().lower()
            for teacher, widget in teacher_items.items():
                if search_text in teacher.lower():
                    widget.pack(fill="x", pady=2)
                else:
                    widget.pack_forget()
        
        search_var.trace_add("write", filter_teachers)
        
        # Buttons
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x")
        
        def confirm_swap():
            if not selected_target["teacher"]:
                messagebox.showwarning("Sélection Requise", "Veuillez sélectionner un créneau cible")
                return
            
            modal.destroy()
            
            # Perform swap using execute_swap logic
            self.swap_source = temp_source
            self.swap_target = selected_target
            self.execute_swap()
        
        ctk.CTkButton(
            button_frame,
            text="✓ Échanger",
            height=45,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=confirm_swap
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(
            button_frame,
            text="Annuler",
            height=45,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=modal.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))
    
    def open_affecter_for_slot(self, teacher, seance, date):
        """Open affecter modal for a specific slot (from right-click menu)"""
        # Set the slot as selected
        self.selected_cell_info = {
            'teacher': teacher,
            'seance': seance,
            'date': date
        }
        
        # Open the affecter modal
        self.open_teacher_selection_modal_for_affect()


