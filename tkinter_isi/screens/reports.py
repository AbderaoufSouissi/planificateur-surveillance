"""
Reports Screen - Generate and export reports
Includes tabs for scores, violations, and document exports
OPTIMIZED for better performance with lazy loading and caching
"""

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import sys
from pathlib import Path
import threading

# Import performance utilities
try:
    parent_dir = Path(__file__).parent.parent
    utils_dir = parent_dir / 'utils'
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from performance_utils import DataCache, batch_update
    HAS_PERF_UTILS = True
except ImportError:
    HAS_PERF_UTILS = False
    print("⚠️  Performance utilities not available")

# Import document generators
try:
    base_dir = Path(__file__).parent.parent.parent
    src_dir = base_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    from invite_generator import generate_convocations
    from teacher_schedule_generator import generate_planning
    HAS_GENERATORS = True
except ImportError as e:
    HAS_GENERATORS = False
    print(f"⚠️  Document generators not available: {e}")


class ReportsScreen(ctk.CTkFrame):
    """Reports screen - Export documents only (Satisfaction moved to separate screen)"""
    
    def __init__(self, parent, app, initial_tab=None):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Content
        self.grid_columnconfigure(0, weight=1)
        
        self.create_header()
        self.create_exports_content()
    
    def create_header(self):
        """Create page header"""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(15, 5))
        
        # Top row with back button and step indicator side by side
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
            command=self.app.show_edit_planning
        )
        back_btn.pack(side="left", padx=(0, 20))
        
        # Step indicator in the center
        from widgets.step_indicator import StepIndicator
        step_indicator = StepIndicator(top_row, current_step=3, colors=self.colors)
        step_indicator.pack(side="left", fill="x", expand=True)
    
    def create_exports_content(self):
        """Create exports content directly (no tabs)"""
        # Container for export content
        container = ctk.CTkFrame(self, fg_color=self.colors['surface'], corner_radius=12)
        container.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 40))
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Create the exports tab content directly
        self.create_exports_tab(container)
    
    def set_active_tab_button(self, tab_key):
        """Update the visual state of tab buttons"""
        for key, btn in self.tab_buttons.items():
            if key == tab_key:
                btn.configure(
                    fg_color=self.colors['primary'],
                    text_color="white",
                    border_color=self.colors['primary']
                )
                self.active_tab_button = btn
            else:
                btn.configure(
                    fg_color=self.colors['surface'],
                    text_color=self.colors['text_primary'],
                    border_color=self.colors['border']
                )
    
    def switch_tab(self, tab_key, tab_text):
        """Switch to a different tab"""
        # Update button styling
        self.set_active_tab_button(tab_key)
        
        # Switch the actual tab
        tab_mapping = {
            "satisfaction": "😊 Satisfaction Enseignants",
            "exports": "📄 Exports Documents"
        }
        self.tabview.set(tab_mapping[tab_key])
        
        # Trigger tab change logic
        self.on_tab_change()
    
    def create_reports_area(self):
        """Create main reports area with tabs - LAZY LOADING"""
        # Container for the tab buttons and content
        container = ctk.CTkFrame(self, fg_color=self.colors['surface'], corner_radius=12)
        container.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 40))
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Tab navigation buttons row - positioned at TOP CENTER
        tab_buttons_container = ctk.CTkFrame(container, fg_color="transparent", height=60)
        tab_buttons_container.grid(row=0, column=0, sticky="ew", pady=(0, 0))
        tab_buttons_container.grid_propagate(False)
        
        # Center frame for buttons using place to center them
        center_frame = ctk.CTkFrame(tab_buttons_container, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Store active button for styling
        self.active_tab_button = None
        
        # Create tab buttons - packed horizontally in center frame
        self.tab_buttons = {}
        tabs = [
            ("😊 Satisfaction Enseignants", "satisfaction"),
            ("📄 Exports Documents", "exports")
        ]
        
        for tab_text, tab_key in tabs:
            btn = ctk.CTkButton(
                center_frame,
                text=tab_text,
                width=200,
                height=38,
                corner_radius=10,
                fg_color=self.colors['surface'],
                hover_color=self.colors['hover'],
                text_color=self.colors['text_primary'],
                font=("Segoe UI", 13, "bold"),
                border_width=2,
                border_color=self.colors['border'],
                command=lambda key=tab_key, text=tab_text: self.switch_tab(key, text)
            )
            btn.pack(side="left", padx=5)
            self.tab_buttons[tab_key] = btn
        
        # Set initial active button based on initial_tab
        if self.initial_tab == "satisfaction":
            self.set_active_tab_button("satisfaction")
        else:
            # Default to exports documents
            self.set_active_tab_button("exports")
        
        # Tab view with modern styling (segmented buttons will be hidden)
        self.tabview = ctk.CTkTabview(
            container,
            corner_radius=12,
            fg_color=self.colors['surface'],
            segmented_button_fg_color=self.colors['surface'],
            segmented_button_selected_color=self.colors['primary'],
            segmented_button_selected_hover_color="#6D28D9",
            segmented_button_unselected_color=self.colors['surface'],
            segmented_button_unselected_hover_color=self.colors['hover'],
            text_color=self.colors['text_primary'],
            text_color_disabled=self.colors['text_secondary']
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 0))
        
        # Add tabs (removed Scores & Métriques and Violations)
        self.tabview.add("😊 Satisfaction Enseignants")
        self.tabview.add("📄 Exports Documents")
        
        # Hide the default segmented button bar
        try:
            self.tabview._segmented_button.grid_forget()
        except:
            pass
        
        # CRITICAL FIX: Remove ALL internal padding from CTkTabview
        try:
            # The CTkTabview has an internal _parent_frame that wraps tab content
            # This is where the massive padding comes from!
            if hasattr(self.tabview, '_parent_frame'):
                # Reconfigure the parent frame's grid to remove padding - SET TO 10px
                self.tabview._parent_frame.grid_configure(padx=0, pady=(10, 0))
            
            # Also configure each tab's grid to have minimal padding
            for tab_name in ["😊 Satisfaction Enseignants", "📄 Exports Documents"]:
                tab = self.tabview.tab(tab_name)
                # These tabs are placed in the parent frame, ensure minimal padding
                tab.grid_configure(padx=0, pady=0)
        except Exception as e:
            print(f"Warning: Could not remove tabview padding: {e}")
        
        # OPTIMIZATION: Only populate the initial tab
        # Other tabs will be populated when first accessed (lazy loading)
        if self.initial_tab == "satisfaction":
            self.tabview.set("😊 Satisfaction Enseignants")
            self.create_satisfaction_tab()
            self.tabs_initialized['satisfaction'] = True
        else:
            # Default to exports documents tab
            self.tabview.set("📄 Exports Documents")
            self.create_exports_tab()
            self.tabs_initialized['exports'] = True
    
    def on_tab_change(self):
        """Handle tab change events - LAZY LOAD CONTENT"""
        current_tab = self.tabview.get()
        
        # Initialize tab content on first access (lazy loading)
        if current_tab == "😊 Satisfaction Enseignants" and not self.tabs_initialized['satisfaction']:
            self.app.update_status("Chargement de la satisfaction...", show_progress=True, progress_value=0.3)
            self.after(10, lambda: self._load_satisfaction_tab())
            
        elif current_tab == "📄 Exports Documents" and not self.tabs_initialized['exports']:
            self.app.update_status("Chargement des exports...", show_progress=True, progress_value=0.3)
            self.after(10, lambda: self._load_exports_tab())
        
        # Refresh satisfaction data if already initialized
        elif current_tab == "😊 Satisfaction Enseignants" and self.tabs_initialized['satisfaction']:
            # Only refresh if cache is old or doesn't exist
            if self.cached_satisfaction_data is None:
                self.refresh_satisfaction_tab()
    
    def _load_satisfaction_tab(self):
        """Lazy load satisfaction tab"""
        self.create_satisfaction_tab()
        self.tabs_initialized['satisfaction'] = True
        self.app.update_status("Satisfaction chargée", show_progress=False)
    
    def _load_exports_tab(self):
        """Lazy load exports tab"""
        self.create_exports_tab()
        self.tabs_initialized['exports'] = True
        self.app.update_status("Exports chargés", show_progress=False)
    
    def _load_export_ops_tab(self):
        """Lazy load export operations tab"""
        self.create_export_operations_tab()
        self.tabs_initialized['export_ops'] = True
        self.app.update_status("Export prêt", show_progress=False)
    
    def refresh_satisfaction_tab(self):
        """Refresh the satisfaction tab with latest data"""
        try:
            # Clear and recreate the satisfaction tab
            tab = self.tabview.tab("😊 Satisfaction Enseignants")
            for widget in tab.winfo_children():
                widget.destroy()
            
            # Recreate tab content
            self.create_satisfaction_tab_content(tab)
        except Exception as e:
            print(f"⚠️  Error refreshing satisfaction tab: {e}")
            import traceback
            traceback.print_exc()
    
    def create_scores_tab(self):
        """Create scores and metrics tab"""
        tab = self.tabview.tab("📊 Scores & Métriques")
        
        # Configure grid
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        
        # Global metrics cards
        metrics_frame = ctk.CTkFrame(tab, fg_color="transparent")
        metrics_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=15)
        
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)
        
        metrics = [
            ("Score Global", "87 / 100", self.colors['success']),
            ("Taux de Satisfaction", "94%", self.colors['primary']),
            ("Contraintes Respectées", "118 / 120", self.colors['accent']),
            ("Équilibrage", "Excellent", self.colors['success'])
        ]
        
        for idx, (label, value, color) in enumerate(metrics):
            card = self.create_metric_card(metrics_frame, label, value, color)
            card.grid(row=0, column=idx, padx=8, pady=5, sticky="ew")
        
        # Left: Detailed scores table
        scores_frame = ctk.CTkFrame(tab, fg_color=self.colors['surface'], corner_radius=12, border_width=1, border_color=self.colors['border'])
        scores_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        
        scores_header = ctk.CTkLabel(
            scores_frame,
            text="Détail des Scores",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        scores_header.pack(fill="x", padx=20, pady=(20, 15))
        
        # Scores table
        self.create_scores_table(scores_frame)
        
        # Right: Charts
        charts_frame = ctk.CTkFrame(tab, fg_color=self.colors['surface'], corner_radius=12, border_width=1, border_color=self.colors['border'])
        charts_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        
        charts_header = ctk.CTkLabel(
            charts_frame,
            text="Visualisations",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        charts_header.pack(fill="x", padx=20, pady=(20, 15))
        
        # Chart placeholder (would use matplotlib in real implementation)
        chart_placeholder = ctk.CTkFrame(charts_frame, fg_color=self.colors['background'], corner_radius=8)
        chart_placeholder.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        chart_label = ctk.CTkLabel(
            chart_placeholder,
            text="📊\n\nHistogramme de Distribution\ndes Créneaux par Enseignant\n\n(Matplotlib Chart Area)",
            font=("Segoe UI", 14),
            text_color=self.colors['text_secondary'],
            justify="center"
        )
        chart_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Export button for charts
        export_chart_btn = ctk.CTkButton(
            charts_frame,
            text="Exporter le Graphique",
            height=38,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 13),
            command=self.export_chart
        )
        export_chart_btn.pack(pady=(0, 20), padx=20)
    
    def has_planning_data(self):
        """Check if planning data is available"""
        return hasattr(self.app, 'current_session_id') and self.app.current_session_id is not None
    
    def create_empty_state(self, parent, message_title="Aucune donnée disponible", message_subtitle="Générez un nouveau planning ou chargez-en un\npour accéder à cette fonctionnalité"):
        """Create empty state message with action buttons"""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icon
        icon_label = ctk.CTkLabel(
            container,
            text="📊",
            font=("Segoe UI", 72)
        )
        icon_label.pack(pady=(0, 20))
        
        # Message
        message = ctk.CTkLabel(
            container,
            text=message_title,
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['text_primary']
        )
        message.pack(pady=(0, 10))
        
        subtitle = ctk.CTkLabel(
            container,
            text=message_subtitle,
            font=("Segoe UI", 14),
            text_color=self.colors['text_secondary']
        )
        subtitle.pack(pady=(0, 30))
        
        # Buttons container
        buttons_frame = ctk.CTkFrame(container, fg_color="transparent")
        buttons_frame.pack()
        
        # Generate planning button - redirects to welcome and triggers new planning
        generate_btn = ctk.CTkButton(
            buttons_frame,
            text="Générer un Planning",
            height=45,
            width=200,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 14, "bold"),
            command=self.app.trigger_new_planning
        )
        generate_btn.pack(side="left", padx=10)
        
        # Load planning button - redirects to welcome and triggers open planning
        load_btn = ctk.CTkButton(
            buttons_frame,
            text="Charger un Planning",
            height=45,
            width=200,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['primary'],
            text_color=self.colors['primary'],
            font=("Segoe UI", 14, "bold"),
            command=self.app.trigger_open_planning
        )
        load_btn.pack(side="left", padx=10)
    
    def create_exports_tab(self, container):
        """Create exports content with two halves: Word exports (left) and Excel exports (right)"""
        
        # Check if data is available
        if not self.has_planning_data():
            self.create_empty_state(
                container, 
                "Aucun planning à exporter",
                "Chargez un planning pour exporter des documents"
            )
            return
        
        # Configure grid for two columns
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1, uniform="col")
        container.grid_columnconfigure(1, weight=1, uniform="col")
        
        # ========== LEFT HALF: Word Exports ==========
        left_frame = ctk.CTkFrame(container, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        
        # Left title
        left_title = ctk.CTkLabel(
            left_frame,
            text="📄 Exporter en Format Word",
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        left_title.pack(fill="x", padx=10, pady=(20, 15))
        
        # Scrollable area for word exports
        word_scroll = ctk.CTkScrollableFrame(
            left_frame,
            fg_color=self.colors['background'],
            corner_radius=10
        )
        word_scroll.pack(fill="both", expand=True)
        
        # Export cards for Word
        export_options_word = [
            {
                "icon": "📋",
                "title": "Convocations Individuelles",
                "description": "Générer les convocations pour chaque enseignant avec leurs créneaux assignés",
                "format": "Word",
                "action": self.export_convocations
            },
            {
                "icon": "📅",
                "title": "Planning Journalier par séance",
                "description": "Liste des surveillances par séance",
                "format": "Word",
                "action": self.export_daily_planning
            },
        ]
        
        for option in export_options_word:
            card = self.create_export_card(word_scroll, option)
            card.pack(fill="x", padx=10, pady=10)
        
        # ========== RIGHT HALF: Excel Exports ==========
        right_frame = ctk.CTkFrame(container, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        
        # Right title
        right_title = ctk.CTkLabel(
            right_frame,
            text="📊 Exporter en Format Excel",
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        right_title.pack(fill="x", padx=10, pady=(20, 15))
        
        # Scrollable area for excel exports
        excel_scroll = ctk.CTkScrollableFrame(
            right_frame,
            fg_color=self.colors['background'],
            corner_radius=10
        )
        excel_scroll.pack(fill="both", expand=True)
        
        # ========== CARD 1: Export Planning Consolidé - Tout ==========
        consolidated_all_card = ctk.CTkFrame(
            excel_scroll,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        consolidated_all_card.pack(fill="x", padx=10, pady=10)
        
        # Header with icon
        header_frame_1 = ctk.CTkFrame(consolidated_all_card, fg_color="transparent")
        header_frame_1.pack(fill="x", padx=20, pady=(18, 8))
        
        icon_label_1 = ctk.CTkLabel(
            header_frame_1,
            text="📋",
            font=("Segoe UI", 28)
        )
        icon_label_1.pack(side="left", padx=(0, 12))
        
        title_label_1 = ctk.CTkLabel(
            header_frame_1,
            text="Planning Consolidé Complet",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        title_label_1.pack(side="left", fill="x", expand=True)
        
        # Excel format badge
        format_badge_1 = ctk.CTkLabel(
            header_frame_1,
            text="Excel",
            font=("Segoe UI", 11, "bold"),
            text_color="white",
            fg_color=self.colors['success'],
            corner_radius=6,
            padx=12,
            pady=4
        )
        format_badge_1.pack(side="right")
        
        # Description
        desc_label_1 = ctk.CTkLabel(
            consolidated_all_card,
            text="Exporter toutes les données du planning consolidé en un seul fichier Excel",
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=380
        )
        desc_label_1.pack(fill="x", padx=20, pady=(0, 15))
        
        # Export button
        export_btn_1 = ctk.CTkButton(
            consolidated_all_card,
            text="Exporter Tout",
            height=42,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 13, "bold"),
            command=self.export_consolidated_all
        )
        export_btn_1.pack(fill="x", padx=20, pady=(0, 18))
        
        # ========== CARD 2: Export Plannings Enseignants - Tous ==========
        teachers_all_card = ctk.CTkFrame(
            excel_scroll,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        teachers_all_card.pack(fill="x", padx=10, pady=10)
        
        # Header with icon
        header_frame_2 = ctk.CTkFrame(teachers_all_card, fg_color="transparent")
        header_frame_2.pack(fill="x", padx=20, pady=(18, 8))
        
        icon_label_2 = ctk.CTkLabel(
            header_frame_2,
            text="📅",
            font=("Segoe UI", 28)
        )
        icon_label_2.pack(side="left", padx=(0, 12))
        
        title_label_2 = ctk.CTkLabel(
            header_frame_2,
            text="Plannings Tous les Enseignants",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        title_label_2.pack(side="left", fill="x", expand=True)
        
        # Excel format badge
        format_badge_2 = ctk.CTkLabel(
            header_frame_2,
            text="Excel",
            font=("Segoe UI", 11, "bold"),
            text_color="white",
            fg_color=self.colors['success'],
            corner_radius=6,
            padx=12,
            pady=4
        )
        format_badge_2.pack(side="right")
        
        # Description
        desc_label_2 = ctk.CTkLabel(
            teachers_all_card,
            text="Générer un fichier Excel individuel pour chaque enseignant",
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=380
        )
        desc_label_2.pack(fill="x", padx=20, pady=(0, 15))
        
        # Export button
        export_btn_2 = ctk.CTkButton(
            teachers_all_card,
            text="Exporter Tous les Enseignants",
            height=42,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 13, "bold"),
            command=self.export_all_teacher_plannings
        )
        export_btn_2.pack(fill="x", padx=20, pady=(0, 18))

    
    def create_export_card(self, parent, option):
        """Create an export option card"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        
        # Header with icon
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(18, 8))
        
        icon_label = ctk.CTkLabel(
            header_frame,
            text=option['icon'],
            font=("Segoe UI", 28)
        )
        icon_label.pack(side="left", padx=(0, 12))
        
        title_label = ctk.CTkLabel(
            header_frame,
            text=option['title'],
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        title_label.pack(side="left", fill="x", expand=True)
        
        # Format badge - using secondary color for Word (purple)
        badge_color = self.colors['secondary'] if option['format'] == "Word" else self.colors['success']
        format_badge = ctk.CTkLabel(
            header_frame,
            text=option['format'],
            font=("Segoe UI", 11, "bold"),
            text_color="white",
            fg_color=badge_color,
            corner_radius=6,
            padx=12,
            pady=4
        )
        format_badge.pack(side="right")
        
        # Description
        desc_label = ctk.CTkLabel(
            card,
            text=option['description'],
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=380
        )
        desc_label.pack(fill="x", padx=20, pady=(0, 15))
        
        # Export button - full width to match Excel tab
        export_btn = ctk.CTkButton(
            card,
            text="Générer",
            height=42,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 13, "bold"),
            command=option['action']
        )
        export_btn.pack(fill="x", padx=20, pady=(0, 18))
        
        return card
    
    def create_convocation_preview(self, parent):
        """Create a sample convocation preview"""
        # Header
        header_frame = ctk.CTkFrame(parent, fg_color=self.colors['primary'], corner_radius=8)
        header_frame.pack(fill="x", pady=(5, 15))
        
        title = ctk.CTkLabel(
            header_frame,
            text="CONVOCATION DE SURVEILLANCE\nInstitut Supérieur d'Informatique",
            font=("Segoe UI", 14, "bold"),
            text_color="white",
            justify="center"
        )
        title.pack(pady=15)
        
        # Teacher info
        info_frame = ctk.CTkFrame(parent, fg_color=self.colors['background'], corner_radius=6)
        info_frame.pack(fill="x", pady=(0, 10))
        
        teacher_label = ctk.CTkLabel(
            info_frame,
            text="Enseignant: M./Mme. DUPONT Jean\nGrade: Professeur\nDépartement: Informatique",
            font=("Segoe UI", 11),
            text_color=self.colors['text_primary'],
            anchor="w",
            justify="left"
        )
        teacher_label.pack(padx=15, pady=12)
        
        # Assignments table header
        table_header = ctk.CTkLabel(
            parent,
            text="Créneaux de Surveillance Assignés:",
            font=("Segoe UI", 12, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        table_header.pack(fill="x", pady=(10, 5))
        
        # Sample table
        table_data = [
            ("Date", "Heure", "Durée", "Salle", "Examen"),
            ("15/01/2025", "09:00", "1h30", "A1", "Algorithmique"),
            ("16/01/2025", "14:00", "2h00", "B2", "Base de Données"),
            ("18/01/2025", "09:00", "1h30", "A1", "Réseaux"),
        ]
        
        for row_idx, row_data in enumerate(table_data):
            row_frame = ctk.CTkFrame(
                parent,
                fg_color=self.colors['primary'] if row_idx == 0 else self.colors['surface'],
                corner_radius=0
            )
            row_frame.pack(fill="x", pady=1)
            
            for col_data in row_data:
                cell = ctk.CTkLabel(
                    row_frame,
                    text=col_data,
                    font=("Segoe UI", 10, "bold" if row_idx == 0 else "normal"),
                    text_color="white" if row_idx == 0 else self.colors['text_primary'],
                    width=100,
                    anchor="w"
                )
                cell.pack(side="left", padx=10, pady=8)
    
    def export_convocations(self):
        """Export individual convocations"""
        if not HAS_GENERATORS:
            messagebox.showerror(
                "Erreur",
                "Les générateurs de documents ne sont pas disponibles.\n\n"
                "Vérifiez que les modules invite_generator.py et teacher_schedule_generator.py sont présents."
            )
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé.\n\n"
                "Veuillez générer ou charger un planning d'abord."
            )
            return
        
        # Ask user where to save
        output_dir = filedialog.askdirectory(
            title="Sélectionner le dossier de destination pour les convocations"
        )
        
        if not output_dir:
            return  # User cancelled
        
        # Update status
        self.app.update_status("Génération des convocations individuelles en cours...", 
                              show_progress=True, progress_value=0.3)
        
        # Run generation in background thread to avoid freezing UI
        def generate_in_background():
            try:
                # Import database manager
                from pathlib import Path
                base_dir = Path(__file__).parent.parent.parent
                db_dir = base_dir / "src" / "db"
                if str(db_dir) not in sys.path:
                    sys.path.insert(0, str(db_dir))
                
                from db_operations import DatabaseManager
                
                # Get database instance
                db = DatabaseManager()
                session_id = self.app.current_session_id
                
                # Generate convocations
                result = generate_convocations(
                    session_id=session_id,
                    db_manager=db,
                    output_dir=output_dir
                )
                
                # Update UI on main thread
                self.after(0, lambda: self._show_generation_result(result, "Convocations"))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"Erreur lors de la génération: {str(e)}"
                self.after(0, lambda: self._show_error(error_msg))
        
        # Start background thread
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()
    
    def export_daily_planning(self):
        """Export daily planning"""
        if not HAS_GENERATORS:
            messagebox.showerror(
                "Erreur",
                "Les générateurs de documents ne sont pas disponibles.\n\n"
                "Vérifiez que les modules invite_generator.py et teacher_schedule_generator.py sont présents."
            )
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé.\n\n"
                "Veuillez générer ou charger un planning d'abord."
            )
            return
        
        # Ask user where to save
        output_dir = filedialog.askdirectory(
            title="Sélectionner le dossier de destination pour les plannings"
        )
        
        if not output_dir:
            return  # User cancelled
        
        # Update status
        self.app.update_status("Génération des plannings journaliers en cours...", 
                              show_progress=True, progress_value=0.3)
        
        # Run generation in background thread to avoid freezing UI
        def generate_in_background():
            try:
                # Import database manager
                from pathlib import Path
                base_dir = Path(__file__).parent.parent.parent
                db_dir = base_dir / "src" / "db"
                if str(db_dir) not in sys.path:
                    sys.path.insert(0, str(db_dir))
                
                from db_operations import DatabaseManager
                
                # Get database instance
                db = DatabaseManager()
                session_id = self.app.current_session_id
                
                # Generate planning
                result = generate_planning(
                    session_id=session_id,
                    db_manager=db,
                    output_dir=output_dir
                )
                
                # Update UI on main thread
                self.after(0, lambda: self._show_generation_result(result, "Plannings"))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"Erreur lors de la génération: {str(e)}"
                self.after(0, lambda: self._show_error(error_msg))
        
        # Start background thread
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()
    
    def _show_generation_result(self, result, doc_type):
        """Show generation result to user"""
        self.app.update_status("", show_progress=False)
        
        if result['success']:
            messagebox.showinfo(
                "Export",
                "Fichiers exportés avec succès!"
            )
        else:
            messagebox.showerror(
                "Erreur",
                f"{result['message']}"
            )
    
    def _show_error(self, error_msg):
        """Show error message"""
        self.app.update_status("", show_progress=False)
        messagebox.showerror("Erreur", error_msg)
    
    def export_summary(self):
        """Export summary table"""
        self.app.update_status("Génération du tableau récapitulatif...")
        messagebox.showinfo("Export", "Fichier exporté avec succès!")
    
    def export_signatures(self):
        """Export signature sheets"""
        self.app.update_status("Génération des feuilles d'émargement...")
        messagebox.showinfo("Export", "Fichiers exportés avec succès!")
    
    def export_by_teacher(self):
        """Export by teacher"""
        self.app.update_status("Génération des listes par enseignant...")
        messagebox.showinfo("Export", "Listes par enseignant exportées!")
    
    def export_by_room(self):
        """Export by room"""
        self.app.update_status("Génération des listes par salle...")
        messagebox.showinfo("Export", "Listes par salle exportées!")
    
    def export_all(self):
        """Export all documents - generates convocations and planning"""
        if not HAS_GENERATORS:
            messagebox.showerror(
                "Erreur",
                "Les générateurs de documents ne sont pas disponibles.\n\n"
                "Vérifiez que les modules sont présents."
            )
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé.\n\n"
                "Veuillez générer ou charger un planning d'abord."
            )
            return
        
        # Ask user where to save
        output_dir = filedialog.askdirectory(
            title="Sélectionner le dossier de destination pour tous les documents"
        )
        
        if not output_dir:
            return  # User cancelled
        
        # Update status
        self.app.update_status("Génération de tous les documents en cours...", 
                              show_progress=True, progress_value=0.1)
        
        # Run generation in background thread
        def generate_all_in_background():
            try:
                # Import database manager
                from pathlib import Path
                base_dir = Path(__file__).parent.parent.parent
                db_dir = base_dir / "src" / "db"
                if str(db_dir) not in sys.path:
                    sys.path.insert(0, str(db_dir))
                
                from db_operations import DatabaseManager
                
                # Get database instance
                db = DatabaseManager()
                session_id = self.app.current_session_id
                
                results = []
                
                # Generate convocations
                self.after(0, lambda: self.app.update_status(
                    "Génération des convocations...", 
                    show_progress=True, 
                    progress_value=0.3
                ))
                
                result1 = generate_convocations(
                    session_id=session_id,
                    db_manager=db,
                    output_dir=output_dir
                )
                results.append(('Convocations', result1))
                
                # Generate planning
                self.after(0, lambda: self.app.update_status(
                    "Génération des plannings...", 
                    show_progress=True, 
                    progress_value=0.6
                ))
                
                result2 = generate_planning(
                    session_id=session_id,
                    db_manager=db,
                    output_dir=output_dir
                )
                results.append(('Plannings', result2))
                
                # Update UI on main thread
                self.after(0, lambda: self._show_export_all_result(results, output_dir))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"Erreur lors de la génération: {str(e)}"
                self.after(0, lambda: self._show_error(error_msg))
        
        # Start background thread
        thread = threading.Thread(target=generate_all_in_background, daemon=True)
        thread.start()
    
    def _show_export_all_result(self, results, output_dir):
        """Show result of export all operation"""
        self.app.update_status("", show_progress=False)
        
        # Build message
        success_count = sum(1 for _, r in results if r['success'])
        total_files = sum(r['count'] for _, r in results if r['success'])
        
        if success_count == len(results):
            # All successful
            messagebox.showinfo(
                "Export",
                "Fichiers exportés avec succès!"
            )
        else:
            # Some failed
            messagebox.showwarning(
                "Export",
                "Certains exports ont échoué. Vérifiez les fichiers générés."
            )
    
    def complete_export_all(self, folder):
        """Complete bulk export"""
        self.app.update_status("Tous les documents ont été exportés!", show_progress=False)
        messagebox.showinfo(
            "✅ Export complet",
            f"Tous les documents ont été générés!\n\n📁 {folder}"
        )
    
    def export_chart(self):
        """Export chart"""
        self.app.update_status("Export du graphique...")
        messagebox.showinfo("Export", "Graphique exporté en PNG!")
    
    def create_export_operations_tab(self):
        """Create export operations tab for quick file exports"""
        tab = self.tabview.tab("📦 Export")
        
        # Check if data is available
        if not self.has_planning_data():
            self.create_empty_state(
                tab,
                "Aucun planning à exporter",
                "Chargez un planning pour effectuer des exports"
            )
            return
        
        # Configure grid
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        
        # Main container
        main_container = ctk.CTkScrollableFrame(
            tab,
            fg_color="transparent"
        )
        main_container.grid(row=0, column=0, sticky="nsew", padx=30, pady=20)
        
        # Section 1: Export Planning Consolidated
        self.create_export_section_header(main_container, "Export Planning Consolidé")
        
        consolidated_frame = ctk.CTkFrame(main_container, fg_color=self.colors['surface'], corner_radius=12, border_width=1, border_color=self.colors['border'])
        consolidated_frame.pack(fill="x", pady=(0, 25))
        
        consolidated_inner = ctk.CTkFrame(consolidated_frame, fg_color="transparent")
        consolidated_inner.pack(fill="x", padx=25, pady=20)
        
        # Export all button on the left
        export_all_planning_btn = ctk.CTkButton(
            consolidated_inner,
            text="Exporter Tout",
            width=160,
            height=42,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 14, "bold"),
            command=self.export_consolidated_all
        )
        export_all_planning_btn.pack(side="left", padx=(0, 20))
        
        # OR separator
        or_label = ctk.CTkLabel(
            consolidated_inner,
            text="OU",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_secondary']
        )
        or_label.pack(side="left", padx=15)
        
        # Inputs for specific period
        period_inputs = ctk.CTkFrame(consolidated_inner, fg_color="transparent")
        period_inputs.pack(side="left", fill="x", expand=True, padx=(15, 0))
        
        # First row: dates
        dates_row = ctk.CTkFrame(period_inputs, fg_color="transparent")
        dates_row.pack(fill="x", pady=(0, 10))
        
        # Start date with calendar button
        start_container = ctk.CTkFrame(dates_row, fg_color="transparent")
        start_container.pack(side="left", padx=(0, 12))
        
        start_label = ctk.CTkLabel(
            start_container,
            text="Date Début:",
            font=("Segoe UI", 11),
            text_color=self.colors['text_primary']
        )
        start_label.pack(anchor="w", pady=(0, 3))
        
        start_frame = ctk.CTkFrame(start_container, fg_color="transparent")
        start_frame.pack()
        
        self.start_date_entry = ctk.CTkEntry(
            start_frame,
            width=130,
            height=36,
            placeholder_text="DD/MM/YYYY",
            font=("Segoe UI", 11)
        )
        self.start_date_entry.pack(side="left", padx=(0, 3))
        
        start_cal_btn = ctk.CTkButton(
            start_frame,
            text="📅",
            width=36,
            height=36,
            corner_radius=6,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 14),
            command=lambda: self.open_date_picker(self.start_date_entry, "Date de début")
        )
        start_cal_btn.pack(side="left")
        
        # End date with calendar button
        end_container = ctk.CTkFrame(dates_row, fg_color="transparent")
        end_container.pack(side="left")
        
        end_label = ctk.CTkLabel(
            end_container,
            text="Date Fin:",
            font=("Segoe UI", 11),
            text_color=self.colors['text_primary']
        )
        end_label.pack(anchor="w", pady=(0, 3))
        
        end_frame = ctk.CTkFrame(end_container, fg_color="transparent")
        end_frame.pack()
        
        self.end_date_entry = ctk.CTkEntry(
            end_frame,
            width=130,
            height=36,
            placeholder_text="DD/MM/YYYY",
            font=("Segoe UI", 11)
        )
        self.end_date_entry.pack(side="left", padx=(0, 3))
        
        end_cal_btn = ctk.CTkButton(
            end_frame,
            text="📅",
            width=36,
            height=36,
            corner_radius=6,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 14),
            command=lambda: self.open_date_picker(self.end_date_entry, "Date de fin")
        )
        end_cal_btn.pack(side="left")
        
        # Second row: season selector
        season_row = ctk.CTkFrame(period_inputs, fg_color="transparent")
        season_row.pack(fill="x")
        
        season_label = ctk.CTkLabel(
            season_row,
            text="Séance:",
            font=("Segoe UI", 11),
            text_color=self.colors['text_primary']
        )
        season_label.pack(side="left", padx=(0, 8))
        
        self.season_selector = ctk.CTkOptionMenu(
            season_row,
            values=["Toutes", "S1", "S2", "S3", "S4"],
            width=120,
            height=36,
            fg_color=self.colors['surface'],
            button_color=self.colors['secondary'],
            button_hover_color="#6D28D9",
            font=("Segoe UI", 11)
        )
        self.season_selector.set("Toutes")
        self.season_selector.pack(side="left")
        
        # Export button for specific period
        export_period_btn = ctk.CTkButton(
            consolidated_inner,
            text="Exporter Période",
            width=160,
            height=42,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 13, "bold"),
            command=self.export_by_period
        )
        export_period_btn.pack(side="right", padx=(20, 0))
        
        # Section 2: Export Teacher Plannings
        self.create_export_section_header(main_container, "Export Plannings Enseignants")
        
        teacher_frame = ctk.CTkFrame(main_container, fg_color=self.colors['surface'], corner_radius=12, border_width=1, border_color=self.colors['border'])
        teacher_frame.pack(fill="x", pady=(0, 25))
        
        teacher_inner = ctk.CTkFrame(teacher_frame, fg_color="transparent")
        teacher_inner.pack(fill="x", padx=25, pady=20)
        
        # Export all teachers button on the left
        export_all_teachers_btn = ctk.CTkButton(
            teacher_inner,
            text="Exporter Tous",
            width=160,
            height=42,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=self.export_all_teacher_plannings
        )
        export_all_teachers_btn.pack(side="left", padx=(0, 20))
        
        # OR separator
        or_label2 = ctk.CTkLabel(
            teacher_inner,
            text="OU",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_secondary']
        )
        or_label2.pack(side="left", padx=15)
        
        # Teacher selector
        teacher_select_frame = ctk.CTkFrame(teacher_inner, fg_color="transparent")
        teacher_select_frame.pack(side="left", fill="x", expand=True, padx=(15, 0))
        
        # Get teacher names from app state if available
        teacher_names = self.get_available_teachers()
        
        self.teacher_selector = ctk.CTkOptionMenu(
            teacher_select_frame,
            values=teacher_names if teacher_names else ["Aucun enseignant"],
            width=300,
            height=42,
            fg_color=self.colors['surface'],
            button_color=self.colors['secondary'],
            button_hover_color="#6D28D9",
            font=("Segoe UI", 12)
        )
        if teacher_names:
            self.teacher_selector.set(teacher_names[0])
        self.teacher_selector.pack(side="left")
        
        # Export single teacher button
        export_teacher_btn = ctk.CTkButton(
            teacher_inner,
            text="Exporter",
            width=140,
            height=42,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 13, "bold"),
            command=self.export_selected_teacher,
            state="normal" if teacher_names else "disabled"
        )
        export_teacher_btn.pack(side="right", padx=(15, 0))
    
    def create_export_section_header(self, parent, text):
        """Create section header for export tab"""
        header = ctk.CTkLabel(
            parent,
            text=text,
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", pady=(0, 12))
    
    def create_export_section_header_compact(self, parent, text):
        """Create compact section header for export tab"""
        header = ctk.CTkLabel(
            parent,
            text=text,
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", padx=10, pady=(5, 10))
    
    def get_available_teachers(self):
        """Get list of available teachers from loaded planning"""
        if hasattr(self.app, 'loaded_planning_state') and self.app.loaded_planning_state:
            return sorted(self.app.loaded_planning_state['available_teachers'])
        return []
    
    def export_all_files(self):
        """Export all files (consolidated planning + all teacher plannings)"""
        folder = filedialog.askdirectory(title="Sélectionner le dossier de destination")
        if folder:
            self.app.update_status("Export de tous les fichiers en cours...")
            messagebox.showinfo(
                "Export",
                f"Exportation vers:\n{folder}\n\n(En cours de développement)"
            )
    
    def export_by_period(self):
        """Export planning for specific period"""
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        season = self.season_selector.get()
        
        if not start_date or not end_date:
            messagebox.showwarning("Dates Manquantes", "Veuillez saisir les dates de début et de fin")
            return
        
        # Validate date format (DD/MM/YYYY)
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, "%d/%m/%Y")
            end = datetime.strptime(end_date, "%d/%m/%Y")
            
            if end < start:
                messagebox.showwarning(
                    "Dates Invalides",
                    "La date de fin doit être postérieure à la date de début"
                )
                return
        except ValueError:
            messagebox.showwarning(
                "Format Invalide",
                "Format de date invalide. Utilisez le format: JJ/MM/AAAA"
            )
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé.\n\nVeuillez générer ou charger un planning d'abord."
            )
            return
        
        # Ask user where to save the file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        season_suffix = season.replace(" ", "_") if season != "Toutes" else "Toutes"
        default_filename = f"planning_periode_{start_date.replace('/', '-')}_{end_date.replace('/', '-')}_{season_suffix}_{timestamp}.xlsx"
        
        filepath = filedialog.asksaveasfilename(
            title="Enregistrer le planning de la période",
            defaultextension=".xlsx",
            initialfile=default_filename,
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ]
        )
        
        if not filepath:
            return  # User cancelled
        
        try:
            self.app.update_status("Chargement des données du planning...", show_progress=True, progress_value=0.2)
            
            # Import necessary modules
            import sys
            import os
            from pathlib import Path
            
            # Add src to path
            base_dir = Path(__file__).parent.parent.parent
            src_dir = base_dir / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            db_dir = base_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            from export import export_enhanced_planning
            import pandas as pd
            
            # Get database instance
            db = DatabaseManager()
            session_id = self.app.current_session_id
            
            self.app.update_status("Filtrage par période...", show_progress=True, progress_value=0.4)
            
            # Get all data and filter by date range
            assignments_data = db.get_assignments(session_id)
            
            if not assignments_data:
                messagebox.showwarning(
                    "Aucune Donnée",
                    "Aucune affectation trouvée pour cette session."
                )
                self.app.update_status("", show_progress=False)
                return
            
            # Filter assignments by date range
            filtered_assignments = []
            for asg in assignments_data:
                try:
                    # Parse the exam date
                    exam_date = datetime.strptime(asg['date_examen'], "%Y-%m-%d")
                    if start <= exam_date <= end:
                        filtered_assignments.append(asg)
                except:
                    # If date parsing fails, include it anyway
                    filtered_assignments.append(asg)
            
            if not filtered_assignments:
                messagebox.showwarning(
                    "Aucune Donnée",
                    f"Aucune affectation trouvée pour la période:\n{start_date} → {end_date}"
                )
                self.app.update_status("", show_progress=False)
                return
            
            # Get teachers and slots
            teachers_data = db.get_teachers(session_id, participating_only=False)
            slots_list = db.get_slots(session_id)
            
            # Filter slots by date range
            filtered_slots = []
            for slot in slots_list:
                try:
                    slot_date = datetime.strptime(slot['date_examen'], "%Y-%m-%d")
                    if start <= slot_date <= end:
                        filtered_slots.append(slot)
                except:
                    filtered_slots.append(slot)
            
            self.app.update_status("Préparation des données pour l'export...", show_progress=True, progress_value=0.6)
            
            # Time to session mapping
            TIME_TO_SEANCE = {
                '08:30:00': 'S1',
                '10:30:00': 'S2',
                '12:30:00': 'S3',
                '14:30:00': 'S4'
            }
            
            # Map dates to jour numbers
            unique_dates = sorted(set(slot['date_examen'] for slot in filtered_slots))
            date_to_jour = {date: idx + 1 for idx, date in enumerate(unique_dates)}
            
            # Convert to format expected by export function
            assignments = {}
            for asg in filtered_assignments:
                teacher_id = int(asg['enseignant_id'])  # Keep as integer for proper lookup
                if teacher_id not in assignments:
                    assignments[teacher_id] = {
                        'surveillant': [],
                        'reserviste': []
                    }
                
                # Derive jour and seance from date and time
                jour = date_to_jour.get(asg['date_examen'], '')
                seance = TIME_TO_SEANCE.get(asg['heure_debut'], '')
                
                slot_info = {
                    'date': asg['date_examen'],
                    'time': asg['heure_debut'],
                    'jour': jour,
                    'seance': seance,
                }
                
                if asg['role'] == 'Surveillant':
                    assignments[teacher_id]['surveillant'].append(slot_info)
                elif asg['role'] == 'Réserviste':
                    assignments[teacher_id]['reserviste'].append(slot_info)
            
            # Build teachers dataframe
            # IMPORTANT: Index by 'id' (database row ID), not 'code_smartexam_ens'
            # because assignments use database ID as keys
            if not teachers_data.empty:
                teachers_df = teachers_data.set_index('id')
            else:
                teachers_df = pd.DataFrame()
            
            # Build slot_info list with derived fields
            # Get supervisors per room from config (default 2)
            supervisors_per_room = 2  # You can load this from config if needed
            
            slot_info = []
            
            # Build code to ID mapping for responsible teachers
            code_to_id = {}
            if not teachers_data.empty:
                for _, teacher in teachers_data.iterrows():
                    code = teacher.get('code_smartexam_ens')
                    if pd.notna(code):
                        try:
                            code_str = str(int(code)) if isinstance(code, float) else str(code)
                            code_to_id[code_str] = teacher['id']
                        except (ValueError, TypeError):
                            pass
            
            for slot in filtered_slots:
                jour = date_to_jour.get(slot['date_examen'], '')
                seance = TIME_TO_SEANCE.get(slot['heure_debut'], '')
                # nb_surveillants in DB = number of rooms
                nb_salle = slot.get('nb_surveillants', 0)
                num_surveillants = nb_salle * supervisors_per_room
                
                # Resolve responsible teacher code to database ID
                responsible_teachers = []
                code_resp = slot.get('code_responsable')
                if pd.notna(code_resp) and code_resp:
                    codes = str(code_resp).split(',')
                    for code in codes:
                        code = code.strip()
                        if code in code_to_id:
                            responsible_teachers.append(code_to_id[code])
                        else:
                            # Try direct ID lookup
                            try:
                                tid = int(code)
                                if tid in teachers_data['id'].values:
                                    responsible_teachers.append(tid)
                            except (ValueError, TypeError):
                                pass
                
                slot_info.append({
                    'date': slot['date_examen'],
                    'time': slot['heure_debut'],
                    'jour': jour,
                    'seance': seance,
                    'num_salles': nb_salle,
                    'num_surveillants': num_surveillants,
                    'responsible_teachers': responsible_teachers
                })
            
            responsible_schedule = []
            
            # Get satisfaction report (for filtered period only)
            try:
                satisfaction_report = db.get_satisfaction_report(session_id)
                # Filter satisfaction to only include teachers in this period
                if satisfaction_report:
                    teacher_ids_in_period = set(assignments.keys())
                    satisfaction_report = [s for s in satisfaction_report if s.get('teacher_id') in teacher_ids_in_period]
            except:
                satisfaction_report = None
            
            self.app.update_status("Génération du fichier Excel...", show_progress=True, progress_value=0.8)
            
            # Build all_teachers_lookup from ALL teachers (including non-participating)
            # Key is the database ID, not the code_smartexam_ens
            all_teachers_lookup = {}
            if not teachers_data.empty:
                for _, teacher in teachers_data.iterrows():
                    teacher_id = int(teacher['id'])  # Use database ID as key
                    all_teachers_lookup[teacher_id] = {
                        'nom_ens': teacher['nom_ens'],
                        'prenom_ens': teacher['prenom_ens'],
                        'grade': teacher.get('grade', teacher.get('grade_code_ens', '')),
                        'email_ens': teacher.get('email_ens', '')
                    }
            
            # Export using the export function
            export_enhanced_planning(
                assignments=assignments,
                teachers_df=teachers_df,
                slot_info=slot_info,
                responsible_schedule=responsible_schedule,
                all_teachers_lookup=all_teachers_lookup,
                satisfaction_report=satisfaction_report,
                output_file=filepath
            )
            
            self.app.update_status("Export terminé!", show_progress=False)
            
            # Log export in database
            try:
                db.log_export(session_id, f'period_{start_date}_{end_date}', filepath)
            except:
                pass
            
            season_text = "Toutes les séances" if season == "Toutes" else f"Séance {season}"
            
            # Show success message
            messagebox.showinfo(
                "✅ Export Réussi",
                f"Le planning pour la période a été exporté avec succès!\n\n"
                f"📅 Période: {start_date} → {end_date}\n"
                f"📋 {season_text}\n"
                f"📁 Fichier: {os.path.basename(filepath)}\n"
                f"👥 Enseignants: {len(assignments)}\n"
                f"📝 Affectations: {len(filtered_assignments)}"
            )
            
        except Exception as e:
            self.app.update_status("Erreur lors de l'export", show_progress=False)
            import traceback
            error_details = traceback.format_exc()
            print(f"Export error: {error_details}")
            messagebox.showerror(
                "❌ Erreur d'Export",
                f"Une erreur est survenue lors de l'export:\n\n{str(e)}\n\n"
                f"Veuillez vérifier les logs pour plus de détails."
            )
    
    def export_selected_teacher(self):
        """Export planning for selected teacher"""
        teacher = self.teacher_selector.get()
        
        if teacher == "Aucun enseignant":
            messagebox.showwarning("Aucun Enseignant", "Aucun enseignant sélectionné")
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé."
            )
            return
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = teacher.replace(' ', '_').replace('/', '_').replace('\\', '_')
        
        filepath = filedialog.asksaveasfilename(
            title=f"Exporter le planning de {teacher}",
            defaultextension=".xlsx",
            initialfile=f"planning_{safe_name}_{timestamp}.xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            self.app.update_status(f"Export du planning de {teacher}...", show_progress=True, progress_value=0.3)
            
            # Import necessary modules
            import sys
            import os
            from pathlib import Path
            
            base_dir = Path(__file__).parent.parent.parent
            src_dir = base_dir / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            db_dir = base_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            import pandas as pd
            
            db = DatabaseManager()
            session_id = self.app.current_session_id
            
            # Get assignments for this specific teacher
            all_assignments = db.get_assignments(session_id)
            teacher_assignments = [a for a in all_assignments if f"{a['nom_ens']} {a['prenom_ens']}" == teacher]
            
            if not teacher_assignments:
                messagebox.showwarning(
                    "Aucune Affectation",
                    f"Aucune affectation trouvée pour {teacher}"
                )
                self.app.update_status("", show_progress=False)
                return
            
            self.app.update_status(f"Génération du fichier pour {teacher}...", show_progress=True, progress_value=0.7)
            
            # Get teacher info
            teacher_id = teacher_assignments[0]['enseignant_id']
            teacher_name = teacher
            teacher_grade = teacher_assignments[0]['grade']
            
            # Prepare schedule data
            schedule_rows = []
            for asg in sorted(teacher_assignments, key=lambda x: (x['date_examen'], x['heure_debut'])):
                schedule_rows.append({
                    'Date': asg['date_examen'],
                    'Heure Début': asg['heure_debut'],
                    'Rôle': asg['role'],
                    'Date Affectation': asg['date_affectation']
                })
            
            df_schedule = pd.DataFrame(schedule_rows)
            
            # Create summary section
            unique_dates = set(asg['date_examen'] for asg in teacher_assignments)
            surveillant_count = sum(1 for asg in teacher_assignments if asg['role'] == 'Surveillant')
            
            summary_data = [
                ['EMPLOI DU TEMPS - SURVEILLANCE DES EXAMENS', ''],
                ['', ''],
                ['Enseignant', teacher_name],
                ['Grade', teacher_grade],
                ['ID', teacher_id],
                ['', ''],
                ['Total Surveillances', surveillant_count],
                ['Jours Travaillés', len(unique_dates)],
                ['', ''],
                ['Dates Concernées', ', '.join(sorted(str(d)[:10] for d in unique_dates))],
                ['', ''],
                ['', '']
            ]
            
            df_summary_header = pd.DataFrame(summary_data, columns=['Champ', 'Valeur'])
            
            # Write to Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Summary section
                df_summary_header.to_excel(writer, sheet_name='Emploi du Temps', index=False, header=False, startrow=0)
                
                # Schedule table
                df_schedule.to_excel(writer, sheet_name='Emploi du Temps', index=False, startrow=len(summary_data) + 1)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Emploi du Temps']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value and len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 60)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Style the header
                from openpyxl.styles import Font, Alignment
                
                title_cell = worksheet['A1']
                title_cell.font = Font(size=14, bold=True)
                title_cell.alignment = Alignment(horizontal='left')
                
                for row in range(3, 13):
                    cell = worksheet[f'A{row}']
                    cell.font = Font(bold=True)
            
            self.app.update_status("Export terminé!", show_progress=False)
            
            # Log export
            try:
                db.log_export(session_id, f'teacher_{teacher_id}', filepath)
            except:
                pass
            
            messagebox.showinfo(
                "✅ Export Réussi",
                f"Le planning de {teacher} a été exporté!\n\n"
                f"📁 Fichier: {os.path.basename(filepath)}\n"
                f"📝 Surveillances: {surveillant_count}\n"
                f"📅 Jours: {len(unique_dates)}"
            )
            
        except Exception as e:
            self.app.update_status("Erreur lors de l'export", show_progress=False)
            import traceback
            print(f"Export error: {traceback.format_exc()}")
            messagebox.showerror(
                "❌ Erreur d'Export",
                f"Une erreur est survenue:\n\n{str(e)}"
            )
    
    def export_all_teacher_plannings(self):
        """Export all teacher plannings"""
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé."
            )
            return
        
        folder = filedialog.askdirectory(title="Sélectionner le dossier de destination")
        if not folder:
            return
        
        try:
            from datetime import datetime
            import sys
            import os
            from pathlib import Path
            
            base_dir = Path(__file__).parent.parent.parent
            src_dir = base_dir / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            db_dir = base_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            import pandas as pd
            
            db = DatabaseManager()
            session_id = self.app.current_session_id
            
            self.app.update_status("Chargement des données...", show_progress=True, progress_value=0.1)
            
            # Get all assignments
            all_assignments = db.get_assignments(session_id)
            
            if not all_assignments:
                messagebox.showwarning(
                    "Aucune Donnée",
                    "Aucune affectation trouvée"
                )
                self.app.update_status("", show_progress=False)
                return
            
            # Group assignments by teacher
            teachers_dict = {}
            for asg in all_assignments:
                teacher_key = (asg['enseignant_id'], f"{asg['nom_ens']} {asg['prenom_ens']}", asg['grade'])
                if teacher_key not in teachers_dict:
                    teachers_dict[teacher_key] = []
                teachers_dict[teacher_key].append(asg)
            
            total_teachers = len(teachers_dict)
            generated_files = []
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(folder, f"plannings_enseignants_{timestamp}")
            os.makedirs(output_dir, exist_ok=True)
            
            # Export each teacher
            for idx, (teacher_key, assignments) in enumerate(teachers_dict.items(), 1):
                teacher_id, teacher_name, teacher_grade = teacher_key
                
                progress = idx / total_teachers
                self.app.update_status(
                    f"Export {idx}/{total_teachers}: {teacher_name}",
                    show_progress=True,
                    progress_value=progress
                )
                
                # Prepare schedule data
                schedule_rows = []
                for asg in sorted(assignments, key=lambda x: (x['date_examen'], x['heure_debut'])):
                    schedule_rows.append({
                        'Date': asg['date_examen'],
                        'Heure Début': asg['heure_debut'],
                        'Rôle': asg['role'],
                        'Date Affectation': asg['date_affectation']
                    })
                
                df_schedule = pd.DataFrame(schedule_rows)
                
                # Create summary
                unique_dates = set(asg['date_examen'] for asg in assignments)
                surveillant_count = sum(1 for asg in assignments if asg['role'] == 'Surveillant')
                
                summary_data = [
                    ['EMPLOI DU TEMPS - SURVEILLANCE DES EXAMENS', ''],
                    ['', ''],
                    ['Enseignant', teacher_name],
                    ['Grade', teacher_grade],
                    ['ID', teacher_id],
                    ['', ''],
                    ['Total Surveillances', surveillant_count],
                    ['Jours Travaillés', len(unique_dates)],
                    ['', ''],
                    ['Dates Concernées', ', '.join(sorted(str(d)[:10] for d in unique_dates))],
                    ['', ''],
                    ['', '']
                ]
                
                df_summary_header = pd.DataFrame(summary_data, columns=['Champ', 'Valeur'])
                
                # Generate filename
                safe_name = teacher_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                filename = f"{safe_name}_{teacher_grade}_{teacher_id}.xlsx"
                filepath = os.path.join(output_dir, filename)
                
                # Write to Excel
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    df_summary_header.to_excel(writer, sheet_name='Emploi du Temps', index=False, header=False, startrow=0)
                    df_schedule.to_excel(writer, sheet_name='Emploi du Temps', index=False, startrow=len(summary_data) + 1)
                    
                    # Auto-adjust column widths
                    worksheet = writer.sheets['Emploi du Temps']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if cell.value and len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 60)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                    
                    # Style
                    from openpyxl.styles import Font, Alignment
                    title_cell = worksheet['A1']
                    title_cell.font = Font(size=14, bold=True)
                    title_cell.alignment = Alignment(horizontal='left')
                    
                    for row in range(3, 13):
                        cell = worksheet[f'A{row}']
                        cell.font = Font(bold=True)
                
                generated_files.append(filepath)
            
            self.app.update_status("Export terminé!", show_progress=False)
            
            # Log export
            try:
                db.log_export(session_id, 'all_teachers', output_dir)
            except:
                pass
            
            messagebox.showinfo(
                "Export",
                "Fichiers exportés avec succès!"
            )
            
        except Exception as e:
            self.app.update_status("Erreur lors de l'export", show_progress=False)
            import traceback
            print(f"Export error: {traceback.format_exc()}")
            messagebox.showerror(
                "❌ Erreur d'Export",
                f"Une erreur est survenue:\n\n{str(e)}"
            )
    
    def export_single_teacher_planning(self):
        """Export planning for a single selected teacher"""
        # Get selected teacher
        if not hasattr(self, 'teacher_selector'):
            messagebox.showwarning("Erreur", "Sélecteur d'enseignant non initialisé")
            return
        
        teacher_name = self.teacher_selector.get()
        if not teacher_name or teacher_name == "Aucun enseignant":
            messagebox.showwarning("Aucune Sélection", "Veuillez sélectionner un enseignant")
            return
        
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé."
            )
            return
        
        try:
            from datetime import datetime
            import sys
            import os
            from pathlib import Path
            
            base_dir = Path(__file__).parent.parent.parent
            src_dir = base_dir / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            db_dir = base_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            import pandas as pd
            
            db = DatabaseManager()
            session_id = self.app.current_session_id
            
            self.app.update_status(f"Export du planning de {teacher_name}...", show_progress=True, progress_value=0.3)
            
            # Get assignments for this teacher
            assignments = db.get_teacher_assignments(session_id, teacher_name)
            
            if not assignments:
                messagebox.showwarning(
                    "Aucune Donnée",
                    f"Aucune affectation trouvée pour {teacher_name}"
                )
                self.app.update_status("", show_progress=False)
                return
            
            # Ask where to save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = teacher_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            default_filename = f"planning_{safe_name}_{timestamp}.xlsx"
            
            filepath = filedialog.asksaveasfilename(
                title=f"Enregistrer le planning de {teacher_name}",
                defaultextension=".xlsx",
                initialfile=default_filename,
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if not filepath:
                self.app.update_status("", show_progress=False)
                return
            
            # Prepare schedule data
            schedule_rows = []
            for asg in sorted(assignments, key=lambda x: (x['date_examen'], x['heure_debut'])):
                schedule_rows.append({
                    'Date': asg['date_examen'],
                    'Heure Début': asg['heure_debut'],
                    'Rôle': asg['role'],
                    'Date Affectation': asg['date_affectation']
                })
            
            df_schedule = pd.DataFrame(schedule_rows)
            
            # Create summary
            unique_dates = set(asg['date_examen'] for asg in assignments)
            surveillant_count = sum(1 for asg in assignments if asg['role'] == 'Surveillant')
            teacher_id = assignments[0]['enseignant_id']
            teacher_grade = assignments[0].get('grade', 'N/A')
            
            summary_data = [
                ['EMPLOI DU TEMPS - SURVEILLANCE DES EXAMENS', ''],
                ['', ''],
                ['Enseignant', teacher_name],
                ['Grade', teacher_grade],
                ['ID', teacher_id],
                ['', ''],
                ['Total Surveillances', surveillant_count],
                ['Jours Travaillés', len(unique_dates)],
                ['', ''],
                ['Dates Concernées', ', '.join(sorted(str(d)[:10] for d in unique_dates))],
                ['', ''],
                ['', '']
            ]
            
            df_summary_header = pd.DataFrame(summary_data, columns=['Champ', 'Valeur'])
            
            # Write to Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_summary_header.to_excel(writer, sheet_name='Emploi du Temps', index=False, header=False, startrow=0)
                df_schedule.to_excel(writer, sheet_name='Emploi du Temps', index=False, startrow=len(summary_data) + 1)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Emploi du Temps']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value and len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 60)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Style
                from openpyxl.styles import Font, Alignment
                title_cell = worksheet['A1']
                title_cell.font = Font(size=14, bold=True)
                title_cell.alignment = Alignment(horizontal='left')
                
                for row in range(3, 13):
                    cell = worksheet[f'A{row}']
                    cell.font = Font(bold=True)
            
            self.app.update_status("Export terminé!", show_progress=False)
            
            # Log export
            try:
                db.log_export(session_id, 'single_teacher', filepath)
            except:
                pass
            
            messagebox.showinfo(
                "✅ Export Réussi",
                f"Planning exporté avec succès!\n\n"
                f"👤 Enseignant: {teacher_name}\n"
                f"📋 Surveillances: {surveillant_count}\n"
                f"📁 Fichier: {os.path.basename(filepath)}"
            )
            
        except Exception as e:
            self.app.update_status("Erreur lors de l'export", show_progress=False)
            import traceback
            print(f"Export error: {traceback.format_exc()}")
            messagebox.showerror(
                "❌ Erreur d'Export",
                f"Une erreur est survenue:\n\n{str(e)}"
            )
    
    def export_consolidated_all(self):
        """Export consolidated planning for all periods"""
        # Check if we have a current session
        if not hasattr(self.app, 'current_session_id') or not self.app.current_session_id:
            messagebox.showwarning(
                "Aucune Session Active",
                "Aucun planning n'est actuellement chargé.\n\nVeuillez générer ou charger un planning d'abord."
            )
            return
        
        # Ask user where to save the file
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"planning_consolidé_{timestamp}.xlsx"
        
        filepath = filedialog.asksaveasfilename(
            title="Enregistrer le planning consolidé",
            defaultextension=".xlsx",
            initialfile=default_filename,
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ]
        )
        
        if not filepath:
            return  # User cancelled
        
        try:
            self.app.update_status("Chargement des données du planning...", show_progress=True, progress_value=0.2)
            
            # Import necessary modules
            import sys
            import os
            from pathlib import Path
            
            # Add src to path
            base_dir = Path(__file__).parent.parent.parent
            src_dir = base_dir / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            db_dir = base_dir / "src" / "db"
            if str(db_dir) not in sys.path:
                sys.path.insert(0, str(db_dir))
            
            from db_operations import DatabaseManager
            from export import export_enhanced_planning
            import pandas as pd
            
            # Get database instance
            db = DatabaseManager()
            session_id = self.app.current_session_id
            
            self.app.update_status("Récupération des données de la base...", show_progress=True, progress_value=0.4)
            
            # Debug: Check session info
            print(f"🔍 Exporting for session_id: {session_id}")
            
            # Get all necessary data from database
            try:
                assignments_data = db.get_assignments(session_id)
                print(f"📋 Retrieved {len(assignments_data) if assignments_data else 0} assignments from database")
            except Exception as e:
                print(f"❌ Error getting assignments: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            if not assignments_data:
                # Try to get more info about the session
                try:
                    session = db.get_session(session_id)
                    slots = db.get_slots(session_id)
                    teachers = db.get_teachers(session_id, participating_only=False)
                    
                    debug_msg = f"Session: {session['nom'] if session else 'Not found'}\n"
                    debug_msg += f"Créneaux: {len(slots)}\n"
                    debug_msg += f"Enseignants: {len(teachers)}"
                    
                    print(f"🔍 Debug info:\n{debug_msg}")
                except:
                    pass
                
                # Check if there are generated Excel files we can use instead
                try:
                    import glob
                    output_dir = base_dir / "output"
                    if output_dir.exists():
                        # Look for recent consolidated planning files
                        pattern = str(output_dir / "planning_*" / "planning_*_consolidated_*.xlsx")
                        files = glob.glob(pattern)
                        if files:
                            latest_file = max(files, key=os.path.getmtime)
                            result = messagebox.askyesno(
                                "Utiliser Fichier Existant?",
                                f"Aucune donnée dans la base pour cette session.\n\n"
                                f"Mais un fichier de planning a été trouvé:\n"
                                f"{os.path.basename(latest_file)}\n\n"
                                f"Voulez-vous copier ce fichier vers un nouvel emplacement?"
                            )
                            if result:
                                import shutil
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                dest = filedialog.asksaveasfilename(
                                    title="Enregistrer le planning",
                                    defaultextension=".xlsx",
                                    initialfile=f"planning_consolidé_{timestamp}.xlsx",
                                    filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
                                )
                                if dest:
                                    shutil.copy2(latest_file, dest)
                                    messagebox.showinfo(
                                        "✅ Fichier Copié",
                                        f"Le planning a été copié vers:\n{dest}"
                                    )
                                    self.app.update_status("", show_progress=False)
                                    return
                except Exception as e:
                    print(f"Could not check for existing files: {e}")
                
                messagebox.showwarning(
                    "Aucune Donnée",
                    "Aucune affectation trouvée pour cette session.\n\n"
                    "Assurez-vous d'IMPORTER les données avant de générer un planning,\n"
                    "ou le planning doit être généré en utilisant la base de données."
                )
                self.app.update_status("", show_progress=False)
                return
            
            # Get teachers and slots
            teachers_data = db.get_teachers(session_id, participating_only=False)
            slots_list = db.get_slots(session_id)
            
            print(f"📊 Export data: {len(assignments_data)} assignments, {len(teachers_data)} teachers, {len(slots_list)} slots")
            
            self.app.update_status("Préparation des données pour l'export...", show_progress=True, progress_value=0.6)
            
            # Time to session mapping
            TIME_TO_SEANCE = {
                '08:30:00': 'S1',
                '10:30:00': 'S2',
                '12:30:00': 'S3',
                '14:30:00': 'S4'
            }
            
            # Map dates to jour numbers
            unique_dates = sorted(set(slot['date_examen'] for slot in slots_list))
            date_to_jour = {date: idx + 1 for idx, date in enumerate(unique_dates)}
            
            # Convert to format expected by export function
            # Build assignments dictionary
            assignments = {}
            for asg in assignments_data:
                teacher_id = int(asg['enseignant_id'])  # Keep as integer for proper lookup
                if teacher_id not in assignments:
                    assignments[teacher_id] = {
                        'surveillant': [],
                        'reserviste': []
                    }
                
                # Derive jour and seance from date and time
                jour = date_to_jour.get(asg['date_examen'], '')
                seance = TIME_TO_SEANCE.get(asg['heure_debut'], '')
                
                # Add to appropriate role
                slot_info = {
                    'date': asg['date_examen'],
                    'time': asg['heure_debut'],
                    'jour': jour,
                    'seance': seance,
                }
                
                if asg['role'] == 'Surveillant':
                    assignments[teacher_id]['surveillant'].append(slot_info)
                elif asg['role'] == 'Réserviste':
                    assignments[teacher_id]['reserviste'].append(slot_info)
            
            # Build teachers dataframe
            # IMPORTANT: Index by 'id' (database row ID), not 'code_smartexam_ens'
            # because assignments use database ID as keys
            if not teachers_data.empty:
                teachers_df = teachers_data.set_index('id')
            else:
                teachers_df = pd.DataFrame()
            
            # Build slot_info list with derived fields
            # Get supervisors per room from config (default 2)
            supervisors_per_room = 2
            
            # Build code to ID mapping for responsible teachers
            code_to_id = {}
            if not teachers_data.empty:
                for _, teacher in teachers_data.iterrows():
                    code = teacher.get('code_smartexam_ens')
                    if pd.notna(code):
                        try:
                            code_str = str(int(code)) if isinstance(code, float) else str(code)
                            code_to_id[code_str] = teacher['id']
                        except (ValueError, TypeError):
                            pass
            
            slot_info = []
            for slot in slots_list:
                jour = date_to_jour.get(slot['date_examen'], '')
                seance = TIME_TO_SEANCE.get(slot['heure_debut'], '')
                # nb_surveillants in DB = number of rooms
                nb_salle = slot.get('nb_surveillants', 0)
                num_surveillants = nb_salle * supervisors_per_room
                
                # Resolve responsible teacher code to database ID
                responsible_teachers = []
                code_resp = slot.get('code_responsable')
                if pd.notna(code_resp) and code_resp:
                    codes = str(code_resp).split(',')
                    for code in codes:
                        code = code.strip()
                        if code in code_to_id:
                            responsible_teachers.append(code_to_id[code])
                        else:
                            # Try direct ID lookup
                            try:
                                tid = int(code)
                                if tid in teachers_data['id'].values:
                                    responsible_teachers.append(tid)
                            except (ValueError, TypeError):
                                pass
                
                slot_info.append({
                    'date': slot['date_examen'],
                    'time': slot['heure_debut'],
                    'jour': jour,
                    'seance': seance,
                    'num_salles': nb_salle,
                    'num_surveillants': num_surveillants,
                    'responsible_teachers': responsible_teachers
                })
            
            # Get responsible schedule (empty for now, can be enhanced later)
            responsible_schedule = []
            
            # Get satisfaction report
            try:
                satisfaction_report = db.get_satisfaction_report(session_id)
            except Exception as e:
                print(f"⚠️  Could not load satisfaction report: {e}")
                satisfaction_report = None
            
            # Build all_teachers_lookup from ALL teachers (including non-participating)
            # Key is the database ID, not the code_smartexam_ens
            all_teachers_lookup = {}
            if not teachers_data.empty:
                for _, teacher in teachers_data.iterrows():
                    teacher_id = int(teacher['id'])  # Use database ID as key
                    all_teachers_lookup[teacher_id] = {
                        'nom_ens': teacher['nom_ens'],
                        'prenom_ens': teacher['prenom_ens'],
                        'grade': teacher.get('grade', teacher.get('grade_code_ens', '')),
                        'email_ens': teacher.get('email_ens', '')
                    }
            
            self.app.update_status("Génération du fichier Excel...", show_progress=True, progress_value=0.8)
            
            # Export using the export function
            export_enhanced_planning(
                assignments=assignments,
                teachers_df=teachers_df,
                slot_info=slot_info,
                responsible_schedule=responsible_schedule,
                all_teachers_lookup=all_teachers_lookup,
                satisfaction_report=satisfaction_report,
                output_file=filepath
            )
            
            self.app.update_status("Export terminé!", show_progress=False)
            
            # Log export in database
            try:
                db.log_export(session_id, 'consolidated', filepath)
            except:
                pass
            
            # Show success message
            messagebox.showinfo(
                "Export",
                "Fichiers exportés avec succès!"
            )
            
        except Exception as e:
            self.app.update_status("Erreur lors de l'export", show_progress=False)
            import traceback
            error_details = traceback.format_exc()
            print(f"Export error: {error_details}")
            messagebox.showerror(
                "❌ Erreur d'Export",
                f"Une erreur est survenue lors de l'export:\n\n{str(e)}\n\n"
                f"Veuillez vérifier les logs pour plus de détails."
            )
    
    def open_date_picker(self, entry_widget, title="Sélectionner une date"):
        """Open a calendar popup to select a date"""
        import tkinter as tk
        from datetime import datetime
        
        # Create popup window - BIGGER SIZE
        popup = tk.Toplevel(self.app)
        popup.title(title)
        popup.geometry("420x480")
        popup.resizable(False, False)
        popup.transient(self.app)
        popup.grab_set()
        
        # Center the popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (420 // 2)
        y = (popup.winfo_screenheight() // 2) - (480 // 2)
        popup.geometry(f"420x480+{x}+{y}")
        
        # Current date
        today = datetime.now()
        current_month = today.month
        current_year = today.year
        selected_day = [today.day]
        display_month = [current_month]
        display_year = [current_year]
        
        # Calendar frame
        cal_frame = ctk.CTkFrame(popup, fg_color=self.colors['background'])
        cal_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Month/Year navigation - BIGGER
        nav_frame = ctk.CTkFrame(cal_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        nav_frame.pack(fill="x", pady=(0, 15))
        
        def update_calendar():
            # Clear previous calendar
            for widget in day_frame.winfo_children():
                widget.destroy()
            
            # Month/Year label
            month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                          "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
            month_year_label.configure(text=f"{month_names[display_month[0]-1]} {display_year[0]}")
            
            # Day headers - BIGGER & CLEARER
            day_names = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            for i, day_name in enumerate(day_names):
                header = ctk.CTkLabel(
                    day_frame,
                    text=day_name,
                    font=("Segoe UI", 12, "bold"),
                    text_color=self.colors['text_secondary'],
                    width=50,
                    height=35
                )
                header.grid(row=0, column=i, padx=3, pady=(0, 8))
            
            # Calculate first day of month and number of days
            from calendar import monthrange
            first_weekday, num_days = monthrange(display_year[0], display_month[0])
            first_weekday = (first_weekday + 1) % 7  # Adjust to Monday = 0
            
            # Create day buttons - BIGGER & MORE VISUAL
            row = 1
            col = first_weekday
            for day in range(1, num_days + 1):
                def make_day_command(d):
                    return lambda: select_day(d)
                
                is_today = (day == today.day and 
                           display_month[0] == today.month and 
                           display_year[0] == today.year)
                
                is_selected = (selected_day[0] == day and 
                              display_month[0] == current_month and 
                              display_year[0] == current_year)
                
                # Determine button color
                if is_today:
                    btn_color = self.colors['primary']
                    text_color = "#FFFFFF"
                elif is_selected:
                    btn_color = self.colors['secondary']
                    text_color = "#FFFFFF"
                else:
                    btn_color = self.colors['surface']
                    text_color = self.colors['text_primary']
                
                day_btn = ctk.CTkButton(
                    day_frame,
                    text=str(day),
                    width=50,
                    height=45,
                    corner_radius=8,
                    fg_color=btn_color,
                    hover_color=self.colors['secondary'],
                    text_color=text_color,
                    font=("Segoe UI", 14, "bold" if is_today else "normal"),
                    border_width=2 if is_today else 0,
                    border_color="#FFFFFF" if is_today else None,
                    command=make_day_command(day)
                )
                day_btn.grid(row=row, column=col, padx=3, pady=3)
                
                col += 1
                if col > 6:
                    col = 0
                    row += 1
        
        def prev_month():
            if display_month[0] == 1:
                display_month[0] = 12
                display_year[0] -= 1
            else:
                display_month[0] -= 1
            update_calendar()
        
        def next_month():
            if display_month[0] == 12:
                display_month[0] = 1
                display_year[0] += 1
            else:
                display_month[0] += 1
            update_calendar()
        
        def select_day(day):
            selected_day[0] = day
            date_str = f"{day:02d}/{display_month[0]:02d}/{display_year[0]}"
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, date_str)
            popup.destroy()
        
        # Navigation buttons - BIGGER & CLEARER
        prev_btn = ctk.CTkButton(
            nav_frame,
            text="◀",
            width=55,
            height=48,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 18, "bold"),
            command=prev_month
        )
        prev_btn.pack(side="left", padx=12, pady=10)
        
        month_year_label = ctk.CTkLabel(
            nav_frame,
            text="",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary']
        )
        month_year_label.pack(side="left", expand=True, fill="x")
        
        next_btn = ctk.CTkButton(
            nav_frame,
            text="▶",
            width=55,
            height=48,
            corner_radius=8,
            fg_color=self.colors['secondary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 18, "bold"),
            command=next_month
        )
        next_btn.pack(side="right", padx=12, pady=10)
        
        # Days frame with border
        day_frame = ctk.CTkFrame(cal_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        day_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initial calendar render
        update_calendar()
        
        # Today button - BIGGER
        today_btn = ctk.CTkButton(
            cal_frame,
            text="📅 Aujourd'hui",
            height=48,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color=self.colors['hover_dark'],
            font=("Segoe UI", 14, "bold"),
            command=lambda: (
                (display_month.__setitem__(0, today.month),
                 display_year.__setitem__(0, today.year),
                 update_calendar(),
                 select_day(today.day))
            )
        )
        today_btn.pack(pady=(12, 0), fill="x", padx=5)
    
    def darken_color(self, color):
        """Darken a hex color"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
        return f"#{dark_rgb[0]:02x}{dark_rgb[1]:02x}{dark_rgb[2]:02x}"
