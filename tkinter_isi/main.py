"""
Application DESKTOP de Gestion et de Génération des Créneaux de Surveillance des Enseignants
Institut Supérieur d'Informatique (ISI), Tunisia

A professional desktop application for managing exam surveillance slot assignments.
Built with CustomTkinter for a modern, institutional interface.
"""

import sys
import os

# Setup import paths for both development and PyInstaller environments
def setup_paths():
    """Setup Python paths for imports"""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        bundle_dir = sys._MEIPASS
    else:
        # Running in development
        bundle_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add necessary directories to path
    paths_to_add = [
        bundle_dir,
        os.path.join(bundle_dir, 'src'),
        os.path.join(bundle_dir, 'src', 'db'),
        os.path.join(bundle_dir, 'tkinter_isi'),
    ]
    
    for path in paths_to_add:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

# Call setup before any other imports
setup_paths()

import customtkinter as ctk
from tkinter import ttk, messagebox
from splash_screen import show_splash_screen

# Fix for Windows DPI scaling issues - must be done before any window creation
if sys.platform == "win32":
    try:
        from ctypes import windll
        # Tell Windows we're DPI aware to prevent automatic scaling
        windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception as e:
        print(f"⚠️  Could not set DPI awareness: {e}")

# Try to import TkinterDnD2 for drag-and-drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("⚠️  TkinterDnD2 not available - drag-and-drop will be disabled")

# Application Configuration
ctk.set_appearance_mode("light")  # Professional light theme
ctk.set_default_color_theme("blue")  # Institutional blue

# Disable CustomTkinter's DPI scaling tracker to prevent errors with Python 3.13
try:
    ctk.deactivate_automatic_dpi_awareness()
except:
    pass  # Method may not exist in all versions

# Monkey patch to fix missing block_update_dimensions_event method in tkinter
import tkinter as tk
if not hasattr(tk.Tk, 'block_update_dimensions_event'):
    def _dummy_block_update(*args, **kwargs):
        pass
    tk.Tk.block_update_dimensions_event = _dummy_block_update
    tk.Tk.unblock_update_dimensions_event = _dummy_block_update

# Create base class with or without DnD support
if HAS_DND:
    BaseWindowClass = TkinterDnD.Tk
else:
    BaseWindowClass = ctk.CTk

class SurveillanceApp(BaseWindowClass):
    """Main application window with responsive layout"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Application de Gestion des Créneaux de Surveillance - ISI")
        self.after(0, lambda: self.state("zoomed"))
        
        # Set window size to screen size minus taskbar
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        # Subtract taskbar height (typically 40-60 pixels on Windows)
        taskbar_height = 60
        window_height = screen_height - taskbar_height
        
        self.geometry(f"{screen_width}x{window_height}+0+0")
        self.minsize(1000, 700)
        
        # Set up window close handler to check for unsaved changes
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Application state
        self.current_screen = None
        self.current_screen_name = None  # Track which screen we're on
        self.sidebar_visible = True
        self.current_session_id = None  # Store session ID for database operations
        self.last_generated_planning = None  # Store path to last generated planning for auto-load
        self.imported_files = {  # Store imported file paths to persist across screens
            'teachers': None,
            'slots': None,
            'preferences': None
        }
        self.files_validated = False  # Track if files have been validated
        
        
        
        # PERFORMANCE: Add data cache
        self.cached_planning_data = {}  # Cache for loaded planning data
        self.cached_teacher_data = {}   # Cache for teacher data
        self.cache_timestamps = {}      # Track when data was cached
        
        # Color scheme - Modern Purple palette matching reference design
        self.colors = {
            'primary': '#7C3AED',      # Vibrant purple - main actions, highlights, buttons
            'secondary': '#A78BFA',    # Light purple - secondary elements
            'accent': '#8B5CF6',       # Medium purple for accents
            'background': '#F3F4F6',   # Light gray background
            'surface': '#FFFFFF',      # White surface/cards
            'text_primary': '#1F2937', # Dark gray text (main text)
            'text_secondary': '#6B7280', # Medium gray text (subtext)
            'success': '#7C3AED',      # Purple (no green)
            'warning': '#F59E0B',      # Amber/Orange
            'error': '#DC2626',        # Red
            'border': '#E5E7EB',       # Subtle borders
            'hover': '#EDE9FE',        # Light purple hover background
            'hover_dark': '#6D28D9'    # Darker purple for button hover
        }
        
        # Configure window grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Create UI components
        self.create_sidebar()
        self.create_main_area()
        self.create_status_bar()
        
        # Show welcome screen on startup
        self.show_welcome_screen()
        
        # Bind resize event
        self.bind('<Configure>', self.on_window_resize)
    
    
    def create_sidebar(self):
        """Create modern minimalist sidebar for navigation"""
        self.sidebar_frame = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=self.colors['surface'])
        self.sidebar_frame.grid(row=0, column=0, sticky="nsw", padx=0, pady=0)
        self.sidebar_frame.grid_propagate(False)
        
        # Logo/Header section
        header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=80)
        header_frame.pack(fill="x", padx=0, pady=0)
        
        logo_label = ctk.CTkLabel(
            header_frame,
            text="ISI SURVEILLANCE",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors['text_primary']
        )
        logo_label.pack(pady=25)
        
        # Navigation buttons - Updated workflow with Statistiques after Export
        nav_items = [
            ("🏠 Accueil", self.show_welcome_screen, "welcome"),
            ("⚙️ Importer & Générer", self.show_import_and_generate, "generate"),
            ("✏️ Éditer Planning", self.show_edit_planning, "edit"),
            ("📄 Exporter", self.show_reports, "reports"),
            ("😊 Statistiques", self.show_satisfaction, "satisfaction")
        ]
        
        self.nav_buttons = {}
        for text, command, key in nav_items:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=text,
                width=160,
                height=42,
                corner_radius=8,
                fg_color="transparent",
                text_color=self.colors['text_secondary'],
                hover_color=self.colors['hover'],
                anchor="w",
                font=("Segoe UI", 13),
                command=command,
                border_width=0,
                border_spacing=0
            )
            btn.pack(pady=5, padx=10)
            self.nav_buttons[key] = btn
        
        # Initially disable "Générer Planning" button until files are imported
        self.update_generate_button_state()
        
        # Spacer
        spacer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        spacer.pack(expand=True, fill="both")
    
    def create_main_area(self):
        """Create central content area"""
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors['background'])
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
    
    def create_status_bar(self):
        """Create bottom status bar (hidden by default)"""
        self.status_frame = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color=self.colors['surface'])
        # Don't grid the status bar - it will remain hidden
        # Uncomment the line below to show status bar:
        # self.status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_frame.grid_propagate(False)
        
        # Status message
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Prêt",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        self.status_label.pack(side="left", padx=15)
        
        # Progress bar (hidden by default)
        self.status_progress = ctk.CTkProgressBar(
            self.status_frame,
            width=200,
            height=15,
            corner_radius=7
        )
        self.status_progress.set(0)
        # Don't pack initially - show when needed
        
        # Right side info
        self.status_right = ctk.CTkLabel(
            self.status_frame,
            text="ISI Tunisia | Application v1.0.0",
            font=("Segoe UI", 9),
            text_color=self.colors['text_secondary']
        )
        self.status_right.pack(side="right", padx=15)
    
    def clear_main_area(self):
        """Clear the main content area"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
    
    def ensure_sidebar_state(self):
        """Ensure sidebar state matches current screen - called after any state change"""
        if self.current_screen_name == "welcome":
            # Force sidebar hidden on welcome screen
            if self.sidebar_visible or self.sidebar_frame.winfo_ismapped():
                self.sidebar_frame.grid_forget()
                self.sidebar_visible = False
        else:
            # Ensure sidebar is visible on other screens (if window is wide enough)
            width = self.winfo_width()
            if width >= 1100 and not self.sidebar_visible:
                self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
                self.sidebar_visible = True
    
    def update_generate_button_state(self):
        """Enable/disable Generate Planning button based on imported files"""
        # No longer needed since generate screen includes file upload
        # Keep method for backward compatibility
        pass
    
    def highlight_nav_button(self, key):
        """Highlight the active navigation button with teal accent"""
        for btn_key, btn in self.nav_buttons.items():
            if btn_key == key:
                # Active: teal filled background with white text, no hover effect
                btn.configure(
                    fg_color=self.colors['primary'],
                    text_color="white",
                    hover_color=self.colors['primary'],  # Same as fg_color to disable hover
                    border_width=0
                )
            else:
                # Inactive: transparent with gray text, with hover effect
                btn.configure(
                    fg_color="transparent",
                    text_color=self.colors['text_secondary'],
                    hover_color=self.colors['hover'],  # Enable hover for inactive buttons
                    border_width=0
                )
    
    def update_status(self, message, show_progress=False, progress_value=0):
        """Update status bar message and progress"""
        self.status_label.configure(text=message)
        if show_progress:
            self.status_progress.pack(side="left", padx=10)
            self.status_progress.set(progress_value)
        else:
            self.status_progress.pack_forget()
    
    def on_window_resize(self, event):
        """Handle window resize for responsive behavior"""
        if event.widget == self:
            width = self.winfo_width()
            # Only manage sidebar visibility for non-welcome screens
            # Welcome screen always has sidebar hidden
            if self.current_screen_name == "welcome":
                # Force sidebar to stay hidden on welcome screen
                if self.sidebar_visible:
                    self.sidebar_frame.grid_forget()
                    self.sidebar_visible = False
            else:
                # For other screens, handle responsive behavior
                if width < 1100 and self.sidebar_visible:
                    self.sidebar_frame.grid_forget()
                    self.sidebar_visible = False
                elif width >= 1100 and not self.sidebar_visible:
                    self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
                    self.sidebar_visible = True
    
    # PERFORMANCE: Cache management methods
    def cache_data(self, key, data):
        """Cache data for performance"""
        import time
        self.cached_planning_data[key] = data
        self.cache_timestamps[key] = time.time()
    
    def get_cached_data(self, key, max_age_seconds=300):
        """Get cached data if still valid (default 5 min expiry)"""
        import time
        if key not in self.cached_planning_data:
            return None
        
        # Check age
        age = time.time() - self.cache_timestamps.get(key, 0)
        if age > max_age_seconds:
            # Cache expired
            self.cached_planning_data.pop(key, None)
            self.cache_timestamps.pop(key, None)
            return None
        
        return self.cached_planning_data[key]
    
    def clear_cache(self, key=None):
        """Clear cache (specific key or all)"""
        if key:
            self.cached_planning_data.pop(key, None)
            self.cache_timestamps.pop(key, None)
        else:
            self.cached_planning_data.clear()
            self.cache_timestamps.clear()
    
    # Navigation methods - implemented in separate files
    def show_welcome_screen(self):
        """Show Welcome screen"""
        self.clear_main_area()
        self.current_screen_name = "welcome"
        # Hide sidebar on welcome screen
        self.sidebar_frame.grid_forget()
        self.sidebar_visible = False
        # Don't highlight any nav button on welcome screen
        for btn_key, btn in self.nav_buttons.items():
            btn.configure(
                fg_color="transparent",
                text_color=self.colors['text_secondary'],
                border_width=0
            )
        from screens.welcome_screen import WelcomeScreen
        screen = WelcomeScreen(self.main_frame, self)
        screen.pack(fill="both", expand=True)
        self.current_screen = screen
        self.update_status("Bienvenue - Sélectionnez une option pour commencer")
        # Continuously ensure sidebar stays hidden while on welcome screen
        self._check_welcome_sidebar()
    
    def _check_welcome_sidebar(self):
        """Continuously check and enforce sidebar hidden state on welcome screen"""
        if self.current_screen_name == "welcome":
            # Force hide if somehow visible
            if self.sidebar_visible or self.sidebar_frame.winfo_ismapped():
                self.sidebar_frame.grid_forget()
                self.sidebar_visible = False
            # Schedule next check
            self.after(100, self._check_welcome_sidebar)
    
    def show_import_data(self):
        """Show Import Data screen (legacy - redirects to combined screen)"""
        self.show_import_and_generate()
    
    def show_generate_planning(self):
        """Show Generate Planning screen (legacy - redirects to combined screen)"""
        self.show_import_and_generate()
    
    def show_import_and_generate(self):
        """Show Import and Generate combined screen"""
        # Only show warning if we're NOT coming from a new session creation
        # Check if session already has generated planning (assignments)
        if hasattr(self, 'current_session_id') and self.current_session_id:
            # Check if this session has any assignments (generated planning)
            try:
                from pathlib import Path
                from db_operations import DatabaseManager
                
                db_path = Path(__file__).parent.parent / "planning.db"
                db = DatabaseManager(str(db_path))
                stats = db.get_session_stats(self.current_session_id)
                
                # Only block if session has assignments (planning already generated)
                if stats.get('assignments', 0) > 0:
                    messagebox.showwarning(
                        "⚠️ Planning Déjà Généré",
                        "Impossible d'accéder à l'importation et génération.\n\n"
                        "Cette session a déjà un planning généré.\n"
                        "Vous ne pouvez pas régénérer le planning pour une session existante.\n\n"
                        "💡 Pour importer un nouveau planning:\n"
                        "   • Retournez à l'écran d'accueil\n"
                        "   • Créez une nouvelle session\n"
                        "   • Puis importez vos fichiers Excel"
                    )
                    return
            except:
                # If we can't check, allow navigation (likely new empty session)
                pass
        
        self.clear_main_area()
        self.current_screen_name = "import"
        # Show sidebar if hidden
        if not self.sidebar_visible:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
            self.sidebar_visible = True
        self.highlight_nav_button("generate")
        from screens.import_and_generate import ImportAndGenerateScreen
        screen = ImportAndGenerateScreen(self.main_frame, self)
        screen.pack(fill="both", expand=True)
        self.current_screen = screen
        self.update_status("Importer et Générer le planning")
    
    def show_edit_planning(self):
        """Show Edit Planning screen"""
        self.clear_main_area()
        self.current_screen_name = "edit"
        # Show sidebar if hidden
        if not self.sidebar_visible:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
            self.sidebar_visible = True
        self.highlight_nav_button("edit")
        from screens.edit_planning import EditPlanningScreen
        screen = EditPlanningScreen(self.main_frame, self)
        screen.pack(fill="both", expand=True)
        self.current_screen = screen
        self.update_status("Éditeur de planning")
    
    def show_reports(self, tab=None):
        """Show Reports screen - with unsaved changes check"""
        # Check if we're coming from edit_planning screen with unsaved changes
        if (hasattr(self, 'current_screen') and 
            hasattr(self.current_screen, 'has_unsaved_changes') and 
            self.current_screen.has_unsaved_changes):
            messagebox.showwarning(
                "⚠️ Modifications Non Enregistrées",
                "Vous devez enregistrer vos modifications d'abord avant d'exporter.\n\n"
                "Cliquez sur le bouton '💾 Enregistrer' pour sauvegarder vos changements."
            )
            return
        
        self.clear_main_area()
        self.current_screen_name = "reports"
        # Show sidebar if hidden
        if not self.sidebar_visible:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
            self.sidebar_visible = True
        self.highlight_nav_button("reports")
        from screens.reports import ReportsScreen
        screen = ReportsScreen(self.main_frame, self, initial_tab=tab)
        screen.pack(fill="both", expand=True)
        self.current_screen = screen
        self.update_status("Génération de rapports")
    
    def show_satisfaction(self):
        """Display the statistics and satisfaction analysis screen"""
        self.clear_main_area()
        self.current_screen_name = "satisfaction"
        # Show sidebar if hidden
        if not self.sidebar_visible:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
            self.sidebar_visible = True
        self.highlight_nav_button("satisfaction")
        from screens.statistiques import StatistiquesScreen
        screen = StatistiquesScreen(self.main_frame, self)
        screen.pack(fill="both", expand=True)
        self.current_screen = screen
        self.update_status("Statistiques et analyse")
    
    def trigger_new_planning(self):
        """Navigate to welcome screen and trigger new planning creation"""
        self.show_welcome_screen()
        # Wait for the screen to be created, then trigger the action
        self.after(100, lambda: self.current_screen.start_new_schedule() if hasattr(self.current_screen, 'start_new_schedule') else None)
    
    def trigger_open_planning(self):
        """Navigate to welcome screen and trigger open planning dialog"""
        self.show_welcome_screen()
        # Wait for the screen to be created, then trigger the action
        self.after(100, lambda: self.current_screen.show_load_dialog() if hasattr(self.current_screen, 'show_load_dialog') else None)
    
    def on_closing(self):
        """Handle window close event - check for unsaved changes"""
        # Check if we're on edit planning screen with unsaved changes
        if (hasattr(self, 'current_screen') and 
            hasattr(self.current_screen, 'has_unsaved_changes') and 
            self.current_screen.has_unsaved_changes):
            
            # Count modifications
            modification_count = len(self.current_screen.modifications) if hasattr(self.current_screen, 'modifications') else 0
            
            # Show confirmation dialog
            from tkinter import messagebox
            response = messagebox.askyesnocancel(
                "⚠️ Modifications Non Enregistrées",
                f"Vous avez {modification_count} modification(s) non enregistrée(s).\n\n"
                "Voulez-vous enregistrer avant de quitter?\n\n"
                "• OUI - Enregistrer et quitter\n"
                "• NON - Quitter sans enregistrer\n"
                "• ANNULER - Continuer à travailler"
            )
            
            if response is None:  # Cancel
                return  # Don't close
            elif response:  # Yes - save
                try:
                    self.current_screen.save_changes()
                    self.destroy()
                except Exception as e:
                    messagebox.showerror("Erreur de Sauvegarde", f"Impossible d'enregistrer: {str(e)}")
                    return  # Don't close if save failed
            else:  # No - quit without saving
                self.destroy()
        else:
            # No unsaved changes, close normally
            self.destroy()


def main():
    """Application entry point"""
    # Show splash screen first
    show_splash_screen(duration=3.0)
    
    # Then start main application
    app = SurveillanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
