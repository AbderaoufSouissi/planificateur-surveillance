"""
Dashboard Screen - Overview page shown on launch
Displays key statistics, quick actions, and upcoming exam calendar
"""

import customtkinter as ctk
from datetime import datetime


class DashboardScreen(ctk.CTkFrame):
    """Dashboard with stats, quick actions, and calendar"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # Configure grid for responsive layout
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=0)  # Stats
        self.grid_rowconfigure(2, weight=0)  # Quick actions
        self.grid_rowconfigure(3, weight=1)  # Calendar and info
        self.grid_columnconfigure(0, weight=1)
        
        self.create_header()
        self.create_stats_section()
        self.create_quick_actions()
        self.create_calendar_section()
    
    def create_header(self):
        """Create page header"""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 10))
        
        title = ctk.CTkLabel(
            header_frame,
            text="Tableau de Bord",
            font=("Segoe UI", 28, "bold"),
            text_color=self.colors['text_primary']
        )
        title.pack(side="left")
        
        # Date/time
        date_label = ctk.CTkLabel(
            header_frame,
            text=datetime.now().strftime("%d/%m/%Y - %H:%M"),
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary']
        )
        date_label.pack(side="right", padx=10)
    
    def create_stats_section(self):
        """Create statistics cards in a responsive grid"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=10)
        
        # Configure grid for stats cards (4 columns)
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1, uniform="stats")
        
        # Stats data (icon, value, label, color)
        stats_data = [
            ("👥", "45", "Enseignants", self.colors['primary']),
            ("📅", "120", "Créneaux Disponibles", self.colors['accent']),
            ("📝", "38", "Voeux en Attente", self.colors['warning']),
            ("✓", "82", "Créneaux Attribués", self.colors['success'])
        ]
        
        self.stat_cards = []
        for idx, (icon, value, label, color) in enumerate(stats_data):
            card = self.create_stat_card(stats_frame, icon, value, label, color)
            card.grid(row=0, column=idx, padx=10, pady=10, sticky="ew")
            self.stat_cards.append(card)
    
    def create_stat_card(self, parent, icon, value, label, color):
        """Create a single statistics card"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        
        # Icon (using text since we want professional look)
        icon_label = ctk.CTkLabel(
            card,
            text=icon,
            font=("Segoe UI", 32),
        )
        icon_label.pack(pady=(20, 5))
        
        # Value
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=("Segoe UI", 32, "bold"),
            text_color=color
        )
        value_label.pack()
        
        # Label
        text_label = ctk.CTkLabel(
            card,
            text=label,
            font=("Segoe UI", 12),
            text_color=self.colors['text_secondary']
        )
        text_label.pack(pady=(5, 20))
        
        return card
    
    def create_quick_actions(self):
        """Create quick action buttons"""
        actions_frame = ctk.CTkFrame(self, fg_color=self.colors['surface'], corner_radius=10)
        actions_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=10)
        
        # Header
        header = ctk.CTkLabel(
            actions_frame,
            text="Actions Rapides",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        # Buttons container
        btn_container = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=20, pady=(0, 15))
        
        actions = [
            ("Nouvelle Session", self.new_session, self.colors['primary']),
            ("Charger Planning", self.load_planning, self.colors['accent']),
            ("Importer Données", self.app.show_import_data, self.colors['secondary']),
            ("Générer Planning", self.app.show_generate_planning, self.colors['success'])
        ]
        
        for text, command, color in actions:
            btn = ctk.CTkButton(
                btn_container,
                text=text,
                width=180,
                height=45,
                corner_radius=8,
                fg_color=color,
                hover_color=self.darken_color(color),
                font=("Segoe UI", 13, "bold"),
                command=command
            )
            btn.pack(side="left", padx=8, pady=5)
    
    def create_calendar_section(self):
        """Create calendar and information sections"""
        calendar_frame = ctk.CTkFrame(self, fg_color="transparent")
        calendar_frame.grid(row=3, column=0, sticky="nsew", padx=30, pady=10)
        
        # Configure grid
        calendar_frame.grid_rowconfigure(0, weight=1)
        calendar_frame.grid_columnconfigure(0, weight=2)
        calendar_frame.grid_columnconfigure(1, weight=1)
        
        # Left: Calendar
        self.create_calendar_widget(calendar_frame)
        
        # Right: Recent activities
        self.create_activities_widget(calendar_frame)
    
    def create_calendar_widget(self, parent):
        """Create calendar showing upcoming exam dates"""
        cal_frame = ctk.CTkFrame(parent, fg_color=self.colors['surface'], corner_radius=10)
        cal_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Header
        header = ctk.CTkLabel(
            cal_frame,
            text="📅 Examens à Venir",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        # Calendar content (scrollable)
        scroll_frame = ctk.CTkScrollableFrame(
            cal_frame,
            fg_color="transparent"
        )
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Sample exam dates
        exam_dates = [
            ("15/01/2025", "09:00", "Algorithmique", "Salle A1-A2"),
            ("15/01/2025", "14:00", "Base de Données", "Salle B1-B2"),
            ("16/01/2025", "09:00", "Réseaux Informatiques", "Salle A1-A3"),
            ("16/01/2025", "14:00", "Systèmes d'Exploitation", "Salle C1-C2"),
            ("17/01/2025", "09:00", "Programmation Web", "Salle A1-A2"),
            ("17/01/2025", "14:00", "Intelligence Artificielle", "Salle B1-B3"),
            ("18/01/2025", "09:00", "Génie Logiciel", "Salle A1-A2"),
        ]
        
        for date, time, subject, room in exam_dates:
            exam_card = self.create_exam_card(scroll_frame, date, time, subject, room)
            exam_card.pack(fill="x", pady=5)
    
    def create_exam_card(self, parent, date, time, subject, room):
        """Create a card for an exam entry"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['background'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        
        # Date badge
        date_badge = ctk.CTkFrame(card, fg_color=self.colors['primary'], corner_radius=5)
        date_badge.pack(side="left", padx=10, pady=10)
        
        date_label = ctk.CTkLabel(
            date_badge,
            text=date.split('/')[0] + "\n" + date.split('/')[1],
            font=("Segoe UI", 11, "bold"),
            text_color="white"
        )
        date_label.pack(padx=10, pady=5)
        
        # Info container
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        subject_label = ctk.CTkLabel(
            info_frame,
            text=subject,
            font=("Segoe UI", 12, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        subject_label.pack(fill="x")
        
        details_label = ctk.CTkLabel(
            info_frame,
            text=f"🕐 {time}  |  📍 {room}",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        details_label.pack(fill="x")
        
        return card
    
    def create_activities_widget(self, parent):
        """Create recent activities panel"""
        activity_frame = ctk.CTkFrame(parent, fg_color=self.colors['surface'], corner_radius=10)
        activity_frame.grid(row=0, column=1, sticky="nsew")
        
        # Header
        header = ctk.CTkLabel(
            activity_frame,
            text="📋 Activités Récentes",
            font=("Segoe UI", 16, "bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        # Activities list (scrollable)
        scroll_frame = ctk.CTkScrollableFrame(
            activity_frame,
            fg_color="transparent"
        )
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Sample activities
        activities = [
            ("14/10/2025 15:30", "Planning généré avec succès", self.colors['success']),
            ("14/10/2025 14:20", "Données importées: 45 enseignants", self.colors['primary']),
            ("14/10/2025 10:15", "Modification manuelle: Salle A1", self.colors['warning']),
            ("13/10/2025 16:45", "Rapport PDF exporté", self.colors['accent']),
            ("13/10/2025 11:00", "Nouvelle session créée", self.colors['primary']),
        ]
        
        for timestamp, message, color in activities:
            activity_item = self.create_activity_item(scroll_frame, timestamp, message, color)
            activity_item.pack(fill="x", pady=5)
        
        # View all button
        view_all_btn = ctk.CTkButton(
            activity_frame,
            text="Voir Tout",
            width=120,
            height=35,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self.colors['border'],
            text_color=self.colors['primary'],
            hover_color=self.colors['background'],
            font=("Segoe UI", 11)
        )
        view_all_btn.pack(pady=(5, 15))
    
    def create_activity_item(self, parent, timestamp, message, color):
        """Create a single activity item"""
        item = ctk.CTkFrame(
            parent,
            fg_color=self.colors['background'],
            corner_radius=8
        )
        
        # Color indicator
        indicator = ctk.CTkFrame(item, width=4, fg_color=color, corner_radius=2)
        indicator.pack(side="left", fill="y", padx=(5, 10), pady=5)
        
        # Content
        content = ctk.CTkFrame(item, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, pady=8, padx=(0, 10))
        
        time_label = ctk.CTkLabel(
            content,
            text=timestamp,
            font=("Segoe UI", 9),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        time_label.pack(fill="x")
        
        msg_label = ctk.CTkLabel(
            content,
            text=message,
            font=("Segoe UI", 11),
            text_color=self.colors['text_primary'],
            anchor="w",
            wraplength=200
        )
        msg_label.pack(fill="x")
        
        return item
    
    def darken_color(self, color):
        """Darken a hex color for hover effects"""
        # Simple darkening by reducing RGB values
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        dark_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
        return f"#{dark_rgb[0]:02x}{dark_rgb[1]:02x}{dark_rgb[2]:02x}"
    
    def new_session(self):
        """Start a new session"""
        self.app.update_status("Création d'une nouvelle session...")
    
    def load_planning(self):
        """Load existing planning"""
        self.app.update_status("Chargement du planning...")
