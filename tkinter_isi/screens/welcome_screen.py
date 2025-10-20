"""
Welcome Screen - Choose between new schedule or load existing
Enhanced UI with modern design and smooth interactions
"""

import customtkinter as ctk
from tkinter import messagebox
import sys
from pathlib import Path

# Add src/db to path
parent_dir = Path(__file__).parent.parent.parent
db_dir = parent_dir / "src" / "db"
if str(db_dir) not in sys.path:
    sys.path.insert(0, str(db_dir))


class WelcomeScreen(ctk.CTkFrame):
    """Welcome screen for choosing workflow"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.create_welcome_content()
    
    def create_welcome_content(self):
        """Create welcome screen content - Modern animated design"""
        # Main container with gradient background effect
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0)
        
        # Animated hero section with larger logo
        hero_section = ctk.CTkFrame(main_container, fg_color="transparent")
        hero_section.pack(pady=(40, 20))
        
        # Large logo with shadow effect
        logo_container = ctk.CTkFrame(
            hero_section,
            fg_color=self.colors['primary'],
            corner_radius=25,
            width=120,
            height=120
        )
        logo_container.pack()
        logo_container.pack_propagate(False)
        
        icon_label = ctk.CTkLabel(
            logo_container,
            text="📅",
            font=("Segoe UI", 60)
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Animated title with gradient effect
        title_container = ctk.CTkFrame(main_container, fg_color="transparent")
        title_container.pack(pady=(0, 5))
        
        title_label = ctk.CTkLabel(
            title_container,
            text="Gestion des Créneaux",
            font=("Segoe UI", 32, "bold"),
            text_color=self.colors['text_primary']
        )
        title_label.pack()
        
        title_label2 = ctk.CTkLabel(
            title_container,
            text="de Surveillance",
            font=("Segoe UI", 32, "bold"),
            text_color=self.colors['primary']
        )
        title_label2.pack()
        
        # Modern subtitle with icon
        subtitle_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        subtitle_frame.pack(pady=(5, 30))
        
        subtitle_label = ctk.CTkLabel(
            subtitle_frame,
            text="🎓 Institut Supérieur d'Informatique",
            font=("Segoe UI", 14),
            text_color=self.colors['text_secondary']
        )
        subtitle_label.pack()
        
        # Modern divider
        divider = ctk.CTkFrame(
            main_container,
            fg_color=self.colors['border'],
            height=2,
            width=60
        )
        divider.pack(pady=(0, 25))
        
        # Modern cards container with better spacing
        options_container = ctk.CTkFrame(main_container, fg_color="transparent")
        options_container.pack(pady=0)
        
        options_container.grid_columnconfigure(0, weight=1, minsize=360)
        options_container.grid_columnconfigure(1, weight=1, minsize=360)
        
        # Option 1: New Schedule - Enhanced card
        new_card = self.create_modern_action_card(
            options_container,
            "✨",
            "Nouveau Planning",
            "Créer un nouveau planning de surveillance\navec l'assistant intelligent",
            self.colors['primary'],
            self.start_new_schedule,
            "Commencer"
        )
        new_card.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        
        # Option 2: Load Existing - Enhanced card
        load_card = self.create_modern_action_card(
            options_container,
            "📂",
            "Ouvrir un Planning",
            "Charger et modifier un planning existant\ndepuis la base de données",
            self.colors['secondary'],
            self.show_load_dialog,
            "Parcourir"
        )
        load_card.grid(row=0, column=1, padx=20, pady=10, sticky="nsew")
        
        # Modern footer with features
        footer_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        footer_frame.pack(pady=(30, 25))
        
        
        
    
    def create_modern_action_card(self, parent, icon, title, description, color, command, button_text):
        """Create a modern action card with enhanced visuals and animations"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=16,
            border_width=2,
            border_color=self.colors['border'],
            width=340,
            height=340
        )
        card.pack_propagate(False)
        
        # Hover state tracking
        card.hover_state = False
        
        def on_enter(e):
            if not card.hover_state:
                card.hover_state = True
                card.configure(
                    border_color=color,
                    border_width=3,
                    cursor="hand2"
                )
                # Animate icon size
                icon_label.configure(font=("Segoe UI", 52))
        
        def on_leave(e):
            if card.hover_state:
                card.hover_state = False
                card.configure(
                    border_color=self.colors['border'],
                    border_width=2,
                    cursor=""
                )
                # Reset icon size
                icon_label.configure(font=("Segoe UI", 48))
        
        def on_click(e=None):
            command()
        
        # Bind events to card
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        card.bind("<Button-1>", on_click)
        
        # Content container - centered in card
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icon with modern gradient background - centered
        icon_bg = ctk.CTkFrame(
            content_frame,
            fg_color=color,
            corner_radius=50,
            width=100,
            height=100
        )
        icon_bg.pack(pady=(0, 20))
        icon_bg.pack_propagate(False)
        
        icon_label = ctk.CTkLabel(
            icon_bg,
            text=icon,
            font=("Segoe UI", 48)
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title with better typography and more space
        title_label = ctk.CTkLabel(
            content_frame,
            text=title,
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors['text_primary']
        )
        title_label.pack(pady=(0, 8))
        
        # Description with better line height and spacing
        desc_label = ctk.CTkLabel(
            content_frame,
            text=description,
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary'],
            justify="center",
            wraplength=280
        )
        desc_label.pack(pady=(0, 0))
        
        # Bind all child widgets to propagate hover and click
        def bind_recursive(widget):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)
            for child in widget.winfo_children():
                bind_recursive(child)
        
        # Bind content frame and all its children (NOW includes title and description)
        bind_recursive(content_frame)
        
        return card
    
    def start_new_schedule(self):
        """Start new schedule workflow - Create a NEW session"""
        # Show dialog to create a new session
        self.show_create_session_dialog()
    
    def show_create_session_dialog(self):
        """Show dialog to create a new session"""
        from datetime import datetime
        
        # Create dialog window
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Créer une Nouvelle Session")
        
        # Prevent the dialog from triggering main window resize
        dialog.transient(self.app)
        
        # Set fixed size first - taller to accommodate all content and buttons
        dialog.geometry("600x600")
        dialog.resizable(False, False)
        
        # Prevent focus issues and DPI scaling problems
        dialog.update_idletasks()
        
        # Center dialog on screen (not relative to parent to avoid resize triggers)
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"600x600+{x}+{y}")
        
        # Grab focus after geometry is set
        dialog.grab_set()
        dialog.focus_set()
        
        # Configure background
        dialog.configure(fg_color=self.colors['background'])
        
        # Header
        header_frame = ctk.CTkFrame(
            dialog,
            fg_color=self.colors['primary'],
            corner_radius=0,
            height=80
        )
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(
            header_frame,
            text="🆕 Créer une Nouvelle Session",
            font=("Segoe UI", 24, "bold"),
            text_color="white"
        )
        header_label.pack(expand=True)
        
        # Content frame
        content_frame = ctk.CTkFrame(dialog, fg_color=self.colors['background'])
        content_frame.pack(fill="both", expand=True, padx=40, pady=30)
        
        # Instructions
        instructions = ctk.CTkLabel(
            content_frame,
            text="Créez une nouvelle session de planning de surveillance.\nVous pourrez importer les données ensuite.",
            font=("Segoe UI", 13),
            text_color=self.colors['text_secondary'],
            justify="center"
        )
        instructions.pack(pady=(0, 25))
        
        # Session Name
        name_label = ctk.CTkLabel(
            content_frame,
            text="Nom de la Session",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        name_label.pack(fill="x", pady=(10, 5))
        
        default_name = f"Session {datetime.now().strftime('%B %Y')}"
        name_entry = ctk.CTkEntry(
            content_frame,
            height=45,
            font=("Segoe UI", 13),
            corner_radius=10,
            border_width=2,
            border_color=self.colors['border']
        )
        name_entry.pack(fill="x", pady=(0, 15))
        name_entry.insert(0, default_name)
        
        # Academic Year
        year_label = ctk.CTkLabel(
            content_frame,
            text="Année Académique",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        year_label.pack(fill="x", pady=(10, 5))
        
        current_year = datetime.now().year
        default_year = f"{current_year}-{current_year + 1}"
        year_entry = ctk.CTkEntry(
            content_frame,
            height=45,
            font=("Segoe UI", 13),
            corner_radius=10,
            border_width=2,
            border_color=self.colors['border']
        )
        year_entry.pack(fill="x", pady=(0, 15))
        year_entry.insert(0, default_year)
        
        # Semester
        semester_label = ctk.CTkLabel(
            content_frame,
            text="Semestre",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        semester_label.pack(fill="x", pady=(10, 5))
        
        semester_var = ctk.StringVar(value="S1")
        semester_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        semester_frame.pack(fill="x", pady=(0, 20))
        
        s1_radio = ctk.CTkRadioButton(
            semester_frame,
            text="Semestre 1",
            variable=semester_var,
            value="S1",
            font=("Segoe UI", 13),
            fg_color=self.colors['primary'],
            hover_color=self.darken_color(self.colors['primary'])
        )
        s1_radio.pack(side="left", padx=(0, 20))
        
        s2_radio = ctk.CTkRadioButton(
            semester_frame,
            text="Semestre 2",
            variable=semester_var,
            value="S2",
            font=("Segoe UI", 13),
            fg_color=self.colors['primary'],
            hover_color=self.darken_color(self.colors['primary'])
        )
        s2_radio.pack(side="left")
        
        # Bottom buttons
        button_frame = ctk.CTkFrame(dialog, fg_color=self.colors['surface'], height=90)
        button_frame.pack(fill="x", side="bottom")
        button_frame.pack_propagate(False)
        
        button_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        button_container.pack(expand=True, fill="both", padx=40, pady=20)
        
        cancel_btn = ctk.CTkButton(
            button_container,
            text="Annuler",
            width=150,
            height=45,
            corner_radius=10,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=dialog.destroy
        )
        cancel_btn.pack(side="left")
        
        def create_session():
            """Create the new session in database"""
            try:
                from db_operations import DatabaseManager
                
                session_name = name_entry.get().strip()
                academic_year = year_entry.get().strip()
                semester = semester_var.get()
                
                if not session_name:
                    messagebox.showwarning(
                        "Nom Requis",
                        "Veuillez entrer un nom pour la session.",
                        parent=dialog
                    )
                    return
                
                # Create database if it doesn't exist
                db_path = parent_dir / "planning.db"
                db = DatabaseManager(str(db_path))
                
                # Create the session
                session_id = db.create_session(
                    nom=session_name,
                    annee_academique=academic_year,
                    semestre=semester
                )
                
                # Set as current session
                self.app.current_session_id = session_id
                self.app.last_generated_planning = None
                
                # Close dialog
                dialog.destroy()
                
                # Show success message
                messagebox.showinfo(
                    "✅ Session Créée",
                    f"Session '{session_name}' créée avec succès!\n\n"
                    f"📅 {academic_year} - {semester}\n\n"
                    f"Vous pouvez maintenant importer vos données."
                )
                
                # Update status
                self.app.update_status(f"Session créée: {session_name}")
                
                # Navigate to import and generate screen
                self.app.show_import_and_generate()
                
            except Exception as e:
                messagebox.showerror(
                    "Erreur",
                    f"Erreur lors de la création de la session:\n\n{str(e)}",
                    parent=dialog
                )
                import traceback
                traceback.print_exc()
        
        create_btn = ctk.CTkButton(
            button_container,
            text="Créer et Continuer",
            width=220,
            height=45,
            corner_radius=10,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=create_session
        )
        create_btn.pack(side="right")
        
        # Bind Enter key to create session
        def on_enter_key(event):
            create_session()
        
        dialog.bind('<Return>', on_enter_key)
        dialog.bind('<KP_Enter>', on_enter_key)  # Numpad Enter
        
        # Focus on name entry
        name_entry.focus()
        name_entry.select_range(0, 'end')  # Select all text for easy editing
    
    def show_load_dialog(self):
        """Show dialog to load existing schedule"""
        # Prevent multiple dialog openings
        if hasattr(self, '_load_dialog_open') and self._load_dialog_open:
            return
        
        self._load_dialog_open = True
        
        try:
            from db_operations import DatabaseManager
            
            # Get database path
            db_path = parent_dir / "planning.db"
            
            if not db_path.exists():
                messagebox.showwarning(
                    "Aucune Base de Données",
                    "Aucune base de données trouvée.\n\n"
                    "Veuillez d'abord créer un nouveau planning."
                )
                self._load_dialog_open = False
                return
            
            # Load sessions from database
            db = DatabaseManager(str(db_path))
            sessions = db.list_sessions()
            
            if not sessions:
                messagebox.showinfo(
                    "Aucun Planning",
                    "Aucun planning trouvé dans la base de données.\n\n"
                    "Veuillez créer un nouveau planning."
                )
                self._load_dialog_open = False
                return
            
            # Show modern session selection dialog
            self.show_modern_session_dialog(sessions, db)
            
        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Erreur lors du chargement des plannings:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
        finally:
            self._load_dialog_open = False
    
    def show_modern_session_dialog(self, sessions, db):
        """Show modern dialog to select a session"""
        # Create dialog window
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Charger un Planning")
        
        # Prevent the dialog from triggering main window resize
        dialog.transient(self.app)
        
        # Set fixed size first
        dialog.geometry("800x600")
        dialog.resizable(False, False)
        
        # Prevent focus issues and DPI scaling problems
        dialog.update_idletasks()
        
        # Center dialog on screen
        x = (dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"800x600+{x}+{y}")
        
        # Grab focus after geometry is set
        dialog.grab_set()
        dialog.focus_set()
        
        # Configure background
        dialog.configure(fg_color=self.colors['background'])
        
        # Header with gradient effect
        header_frame = ctk.CTkFrame(
            dialog,
            fg_color=self.colors['primary'],
            corner_radius=0,
            height=100
        )
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        header_content = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_content.pack(expand=True, fill="both", padx=40, pady=20)
        
        header_label = ctk.CTkLabel(
            header_content,
            text="📂 Sélectionner un Planning",
            font=("Segoe UI", 26, "bold"),
            text_color="white",
            anchor="w"
        )
        header_label.pack(side="left")
        
        count_label = ctk.CTkLabel(
            header_content,
            text=f"{len(sessions)} planning{'s' if len(sessions) > 1 else ''}",
            font=("Segoe UI", 14),
            text_color="white",
            anchor="e"
        )
        count_label.pack(side="right")
        
        # Main content
        content_frame = ctk.CTkFrame(dialog, fg_color=self.colors['background'])
        content_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Search bar
        search_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=40, pady=(25, 15))
        
        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Rechercher un planning...",
            height=45,
            font=("Segoe UI", 13),
            corner_radius=10,
            border_width=2,
            border_color=self.colors['border']
        )
        search_entry.pack(fill="x")
        
        # Sessions container with scrollbar
        sessions_container = ctk.CTkFrame(content_frame, fg_color="transparent")
        sessions_container.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        
        sessions_scroll = ctk.CTkScrollableFrame(
            sessions_container,
            fg_color="transparent",
            scrollbar_button_color=self.colors['primary'],
            scrollbar_button_hover_color=self.darken_color(self.colors['primary'])
        )
        sessions_scroll.pack(fill="both", expand=True)
        
        # Selected session tracking
        selected_session = {'value': None}
        session_widgets = []
        
        # Create session cards
        for session in sessions:
            card_widget = self.create_modern_session_card(
                sessions_scroll,
                session,
                db,
                selected_session,
                session_widgets
            )
            card_widget.pack(fill="x", pady=8)
            session_widgets.append(card_widget)
        
        # Search functionality
        def filter_sessions(*args):
            search_text = search_entry.get().lower()
            for i, widget in enumerate(session_widgets):
                session = sessions[i]
                if (search_text in session['nom'].lower() or 
                    search_text in session['annee_academique'].lower() or
                    search_text in session['semestre'].lower()):
                    widget.pack(fill="x", pady=8)
                else:
                    widget.pack_forget()
        
        search_entry.bind('<KeyRelease>', filter_sessions)
        
        # Bottom button bar
        button_bar = ctk.CTkFrame(
            content_frame,
            fg_color=self.colors['surface'],
            height=90
        )
        button_bar.pack(fill="x", side="bottom")
        button_bar.pack_propagate(False)
        
        button_container = ctk.CTkFrame(button_bar, fg_color="transparent")
        button_container.pack(expand=True, fill="both", padx=40, pady=20)
        
        cancel_btn = ctk.CTkButton(
            button_container,
            text="Annuler",
            width=150,
            height=45,
            corner_radius=10,
            fg_color="transparent",
            border_width=2,
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            hover_color=self.colors['hover'],
            font=("Segoe UI", 14),
            command=dialog.destroy
        )
        cancel_btn.pack(side="left")
        
        load_btn = ctk.CTkButton(
            button_container,
            text="Charger ce Planning",
            width=220,
            height=45,
            corner_radius=10,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=lambda: self.load_selected_session(selected_session['value'], dialog)
        )
        load_btn.pack(side="right")
    
    def create_modern_session_card(self, parent, session, db, selected_session, session_widgets):
        """Create a modern session card with smooth selection"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=2,
            border_color=self.colors['border'],
            height=90
        )
        card.pack_propagate(False)
        
        # Selection state
        card.is_selected = False
        
        def select_this_card(e=None):
            # Deselect all other cards
            for other_card in session_widgets:
                if other_card != card:
                    other_card.is_selected = False
                    other_card.configure(
                        border_color=self.colors['border'],
                        border_width=2,
                        fg_color=self.colors['surface']
                    )
            
            # Select this card
            card.is_selected = True
            selected_session['value'] = session
            card.configure(
                border_color=self.colors['primary'],
                border_width=3,
                fg_color=self.lighten_color(self.colors['primary'])
            )
        
        def on_enter(e):
            if not card.is_selected:
                card.configure(
                    border_color=self.colors['primary'],
                    cursor="hand2"
                )
        
        def on_leave(e):
            if not card.is_selected:
                card.configure(
                    border_color=self.colors['border']
                )
        
        # Bind events to card
        card.bind("<Button-1>", select_this_card)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        
        # Inner content
        inner_frame = ctk.CTkFrame(card, fg_color="transparent")
        inner_frame.pack(fill="both", expand=True, padx=25, pady=18)
        
        # Left side - Icon and info
        left_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        
        # Icon
        icon_frame = ctk.CTkFrame(
            left_frame,
            fg_color=self.colors['primary'],
            corner_radius=8,
            width=50,
            height=50
        )
        icon_frame.pack(side="left", padx=(0, 18))
        icon_frame.pack_propagate(False)
        
        icon = ctk.CTkLabel(
            icon_frame,
            text="📋",
            font=("Segoe UI", 24)
        )
        icon.place(relx=0.5, rely=0.5, anchor="center")
        
        # Info frame
        info_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)
        
        # Session name
        name_label = ctk.CTkLabel(
            info_frame,
            text=session['nom'],
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        name_label.pack(anchor="w", fill="x")
        
        # Academic info
        info_text = f"{session['annee_academique']} • {session['semestre']}"
        info_label = ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        info_label.pack(anchor="w", pady=(2, 0))
        
        # Right side - Stats badges and delete button
        right_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        right_frame.pack(side="right", padx=(15, 0))
        
        try:
            stats = db.get_session_stats(session['id'])
            
            # Teachers badge
            teachers_badge = ctk.CTkFrame(
                right_frame,
                fg_color=self.lighten_color(self.colors['primary']),
                corner_radius=8,
                height=32
            )
            teachers_badge.pack(side="left", padx=4)
            
            teachers_label = ctk.CTkLabel(
                teachers_badge,
                text=f"👥 {stats.get('teachers', 0)}",
                font=("Segoe UI", 11, "bold"),
                text_color=self.colors['primary']
            )
            teachers_label.pack(padx=12, pady=6)
            
            # Slots badge
            slots_badge = ctk.CTkFrame(
                right_frame,
                fg_color=self.lighten_color(self.colors['secondary']),
                corner_radius=8,
                height=32
            )
            slots_badge.pack(side="left", padx=4)
            
            slots_label = ctk.CTkLabel(
                slots_badge,
                text=f"📅 {stats.get('slots', 0)}",
                font=("Segoe UI", 11, "bold"),
                text_color=self.colors['secondary']
            )
            slots_label.pack(padx=12, pady=6)
            
        except:
            pass
        
        # Delete button
        delete_in_progress = {'active': False}  # Flag to track if delete dialog is open
        
        def delete_session(e):
            # Prevent multiple clicks - check if already showing dialog
            if delete_in_progress['active']:
                return  # Ignore additional clicks
            
            try:
                delete_in_progress['active'] = True  # Mark as active immediately
                e.stopPropagation() if hasattr(e, 'stopPropagation') else None
                
                result = messagebox.askyesno(
                    "Confirmer la Suppression",
                    f"Voulez-vous vraiment supprimer le planning:\n\n"
                    f"📋 {session['nom']}\n"
                    f"📚 {session['annee_academique']} - {session['semestre']}\n\n"
                    "Cette action est irréversible!",
                    icon='warning',
                    parent=card.winfo_toplevel()  # Make modal relative to dialog window
                )
                
                if result:
                    try:
                        db.delete_session(session['id'])
                        card.destroy()
                        session_widgets.remove(card)
                        messagebox.showinfo(
                            "✅ Suppression Réussie",
                            f"Le planning '{session['nom']}' a été supprimé.",
                            parent=card.winfo_toplevel()
                        )
                    except Exception as ex:
                        delete_in_progress['active'] = False  # Reset on error
                        messagebox.showerror(
                            "Erreur",
                            f"Erreur lors de la suppression:\n{str(ex)}",
                            parent=card.winfo_toplevel()
                        )
                else:
                    # User cancelled
                    delete_in_progress['active'] = False
            except Exception as ex:
                # Any error, reset flag
                delete_in_progress['active'] = False
                print(f"Error in delete_session: {ex}")
        
        delete_btn = ctk.CTkButton(
            right_frame,
            text="🗑️",
            width=40,
            height=32,
            corner_radius=8,
            fg_color="#EF4444",
            hover_color="#DC2626",
            text_color="white",
            font=("Segoe UI", 16),
            anchor="center"  # Center the icon
        )
        delete_btn.pack(side="left", padx=(8, 0))
        
        # Prevent delete button clicks from propagating to parent card
        def stop_propagation(e):
            delete_session(e)
            return "break"  # Critical: stop event propagation
        
        # Bind event handler - must use add='+' for CustomTkinter
        delete_btn.bind("<Button-1>", stop_propagation, add='+')
        
        # Override command to use our handler
        delete_btn.configure(command=lambda: delete_session(None))
        
        # Store reference to delete button to exclude from recursive binding
        card._delete_btn = delete_btn
        
        # Bind all child widgets to propagate hover and click events (EXCEPT delete button)
        def bind_recursive(widget):
            # Skip the delete button and its children
            if widget == delete_btn or (hasattr(card, '_delete_btn') and 
                                        str(widget).startswith(str(card._delete_btn))):
                return
            
            widget.bind("<Button-1>", select_this_card)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            for child in widget.winfo_children():
                bind_recursive(child)
        
        # Bind all children of the card
        for child in card.winfo_children():
            bind_recursive(child)
        
        return card
    
    def load_selected_session(self, session, dialog):
        """Load the selected session"""
        if not session:
            messagebox.showwarning(
                "Aucune Sélection",
                "Veuillez sélectionner un planning à charger."
            )
            return
        
        try:
            from db_operations import DatabaseManager
            
            # Set the session ID in the app
            self.app.current_session_id = session['id']
            
            # Set flag to load from database
            self.app.should_load_from_db = True
            
            # Close dialog
            dialog.destroy()
            
            # Check if session has any assignments
            db_path = parent_dir / "planning.db"
            db = DatabaseManager(str(db_path))
            stats = db.get_session_stats(session['id'])
            
            # Show success message
            self.app.update_status(f"Planning chargé: {session['nom']}")
            
            # If no assignments, go to import & generate screen
            if stats.get('assignments', 0) == 0:
                messagebox.showinfo(
                    "Session Sans Affectations",
                    f"La session '{session['nom']}' n'a pas encore d'affectations.\n\n"
                    f"Vous serez redirigé vers l'écran d'importation et génération."
                )
                self.app.show_import_and_generate()
            else:
                # Navigate to edit screen - it will auto-load from database
                self.app.show_edit_planning()
            
        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Erreur lors du chargement du planning:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
    
    def darken_color(self, color):
        """Darken a hex color by 20%"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(max(0, int(c * 0.75)) for c in rgb)
        return f"#{dark_rgb[0]:02x}{dark_rgb[1]:02x}{dark_rgb[2]:02x}"
    
    def lighten_color(self, color):
        """Lighten a hex color by adding transparency effect"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        light_rgb = tuple(min(255, int(c + (255 - c) * 0.85)) for c in rgb)
        return f"#{light_rgb[0]:02x}{light_rgb[1]:02x}{light_rgb[2]:02x}"