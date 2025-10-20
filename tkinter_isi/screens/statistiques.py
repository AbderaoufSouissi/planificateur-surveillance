"""
Statistiques Screen - Teacher statistics and satisfaction analysis
Shows detailed satisfaction metrics and teacher-specific information
"""
import sys
import customtkinter as ctk
from pathlib import Path

class StatistiquesScreen(ctk.CTkFrame):
    """Teacher statistics and satisfaction analysis screen - OPTIMIZED"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.colors['background'])
        self.app = app
        self.colors = app.colors
        
        # Cache data to avoid reloading
        self.cached_satisfaction_data = None
        
        # Debounce timer for search
        self.search_debounce_timer = None
        
        # Prevent rerendering on focus events
        self._is_loaded = False
        self._prevent_reload = False
        
        # Virtual scrolling state
        self.visible_rows = []  # Currently visible row widgets
        self.row_height = 80  # Height of each teacher row
        
        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Content
        self.grid_columnconfigure(0, weight=1)
        
        # Bind focus events to prevent unnecessary rerendering
        self.bind("<Visibility>", self._on_visibility_change, add="+")
        
        self.create_header()
        self.create_satisfaction_content()
        
        self._is_loaded = True
    
    def _on_visibility_change(self, event):
        """Prevent rerendering when window visibility changes (alt-tab)"""
        # Don't do anything on visibility change - data is already loaded
        pass
    
    def refresh_data(self):
        """Refresh satisfaction data - clears cache and reloads"""
        # Clear cached data
        self.cached_satisfaction_data = None
        
        # Clear app-level cache
        cache_key = f"satisfaction_{getattr(self.app, 'current_session_id', 'none')}"
        if hasattr(self.app, 'clear_cached_data'):
            self.app.clear_cached_data(cache_key)
        
        # Destroy existing content and recreate
        for widget in self.winfo_children():
            if widget != self.winfo_children()[0]:  # Keep header
                widget.destroy()
        
        # Recreate content
        self.create_satisfaction_content()
    
    def create_header(self):
        """Create page header with back button"""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(15, 10))
        
        # Back button - go back to Edit Planning
        back_btn = ctk.CTkButton(
            header_frame,
            text="← Retour",
            width=100,
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.colors['hover'],
            text_color=self.colors['text_primary'],
            font=("Segoe UI", 14),
            command=self.app.show_edit_planning
        )
        back_btn.pack(side="left")
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="Statistiques de Satisfaction des Enseignants",
            font=("Segoe UI", 24, "bold"),
            text_color=self.colors['text_primary']
        )
        title_label.pack(side="left", padx=20)
    
    def create_satisfaction_content(self):
        """Create the main satisfaction content"""
        # Container
        container = ctk.CTkFrame(self, fg_color=self.colors['surface'], corner_radius=12)
        container.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 30))
        
        # Get satisfaction data
        satisfaction_data = self.get_satisfaction_data()
        
        # Check if data is available
        if satisfaction_data.get('no_data', False) or len(satisfaction_data.get('teachers', [])) == 0:
            self.create_empty_state(container)
            return
        
        # Configure grid for content
        container.grid_rowconfigure(0, weight=0)  # Stats bar
        container.grid_rowconfigure(1, weight=1)  # Main content
        container.grid_columnconfigure(0, weight=1, uniform="col")
        container.grid_columnconfigure(1, weight=1, uniform="col")
        
        # ===== COMPACT STATS BAR =====
        stats_container = ctk.CTkFrame(container, fg_color=self.colors['surface'], corner_radius=8, height=70)
        stats_container.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 10))
        stats_container.grid_propagate(False)
        
        stats_inner = ctk.CTkFrame(stats_container, fg_color="transparent")
        stats_inner.pack(fill="both", expand=True, padx=10, pady=8)
        
        stats = [
            ("Score Moyen", f"{satisfaction_data['avg_score']:.1f}/100", self.get_score_color(satisfaction_data['avg_score'])),
            ("Très Satisfaits", str(satisfaction_data['highly_satisfied']), self.colors['success']),
            ("Satisfaits", str(satisfaction_data['satisfied']), self.colors['primary']),
            ("Neutres", str(satisfaction_data['neutral']), self.colors['warning']),
            ("Mécontents", str(satisfaction_data['dissatisfied']), self.colors['error'])
        ]
        
        for idx, (label, value, color) in enumerate(stats):
            stat_frame = ctk.CTkFrame(stats_inner, fg_color="transparent")
            stat_frame.pack(side="left", fill="both", expand=True, padx=8)
            
            val_label = ctk.CTkLabel(stat_frame, text=value, font=("Segoe UI", 20, "bold"), text_color=color)
            val_label.pack()
            
            txt_label = ctk.CTkLabel(stat_frame, text=label, font=("Segoe UI", 10), text_color=self.colors['text_secondary'])
            txt_label.pack()
        
        # ===== LEFT: Teacher List =====
        teachers_frame = ctk.CTkFrame(container, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        teachers_frame.grid(row=1, column=0, sticky="nsew", padx=(15, 8), pady=(0, 15))
        teachers_frame.grid_rowconfigure(1, weight=1)  # Make list area expandable
        teachers_frame.grid_columnconfigure(0, weight=1)
        
        # Header with filters (Row 0 - Fixed)
        header_search_frame = ctk.CTkFrame(teachers_frame, fg_color="transparent")
        header_search_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 10))
        
        teachers_header = ctk.CTkLabel(header_search_frame, text="Satisfaction par Enseignant", 
                                       font=("Segoe UI", 14, "bold"), text_color=self.colors['text_primary'])
        teachers_header.pack(side="left")
        
        # Filters container with better styling
        filters_frame = ctk.CTkFrame(header_search_frame, fg_color="transparent")
        filters_frame.pack(side="right")
        
        # Grade filter with label
        grade_container = ctk.CTkFrame(filters_frame, fg_color="transparent")
        grade_container.pack(side="left", padx=(0, 8))
        
        grade_label = ctk.CTkLabel(
            grade_container,
            text="Grade:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_secondary']
        )
        grade_label.pack(side="left", padx=(0, 5))
        
        self.grade_filter = ctk.CTkOptionMenu(
            grade_container,
            values=["Tous", "PR", "MC", "MA", "AS", "AC", "PTC", "PES", "EX", "V"],
            width=80,
            height=32,
            fg_color="white",
            button_color=self.colors['primary'],
            button_hover_color=self.colors['hover_dark'],
            dropdown_fg_color="white",
            dropdown_hover_color=self.colors['hover'],
            font=("Segoe UI", 11),
            dropdown_font=("Segoe UI", 11),
            corner_radius=8,
            command=lambda _: self.filter_teachers()
        )
        self.grade_filter.set("Tous")
        self.grade_filter.pack(side="left")
        
        # Search field with label
        search_container = ctk.CTkFrame(filters_frame, fg_color="transparent")
        search_container.pack(side="left")
        
        search_label = ctk.CTkLabel(
            search_container,
            text="🔍",
            font=("Segoe UI", 13),
            text_color=self.colors['text_secondary']
        )
        search_label.pack(side="left", padx=(0, 5))
        
        self.search_entry = ctk.CTkEntry(
            search_container,
            placeholder_text="Rechercher...",
            width=180,
            height=32,
            font=("Segoe UI", 11),
            fg_color="white",
            border_color=self.colors['border'],
            border_width=1,
            corner_radius=8
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_teachers())
        
        # Reset filters button
        reset_btn = ctk.CTkButton(
            filters_frame,
            text="🔄",
            width=32,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.colors['hover'],
            border_width=1,
            border_color=self.colors['border'],
            font=("Segoe UI", 14),
            command=self.reset_filters
        )
        reset_btn.pack(side="left", padx=(8, 0))
        
        # Store data and container reference
        self.all_teachers_data = satisfaction_data['teachers']
        self.filtered_teachers_data = self.all_teachers_data.copy()
        self.teachers_list_container = teachers_frame  # Store frame reference
        
        # Show loading indicator first, then load data asynchronously
        self.show_loading_indicator(teachers_frame)
        
        # Load teachers list asynchronously (after UI is rendered)
        self.after(50, lambda: self._load_teachers_async(teachers_frame, satisfaction_data['teachers']))
        
        # ===== RIGHT: Details Panel =====
        details_frame = ctk.CTkFrame(container, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        details_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 15), pady=(0, 15))
        
        details_header = ctk.CTkLabel(details_frame, text="Détails de Satisfaction", 
                                      font=("Segoe UI", 14, "bold"), text_color=self.colors['text_primary'])
        details_header.pack(fill="x", padx=12, pady=(10, 8))
        
        self.create_satisfaction_details(details_frame, satisfaction_data['teachers'])
    
    def create_empty_state(self, parent):
        """Create empty state message"""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        icon_label = ctk.CTkLabel(container, text="📊", font=("Segoe UI", 72))
        icon_label.pack(pady=(0, 20))
        
        message = ctk.CTkLabel(container, text="Aucune donnée disponible", 
                              font=("Segoe UI", 20, "bold"), text_color=self.colors['text_primary'])
        message.pack(pady=(0, 10))
        
        subtitle = ctk.CTkLabel(container, text="Générez un nouveau planning ou chargez-en un\npour accéder à cette fonctionnalité",
                               font=("Segoe UI", 14), text_color=self.colors['text_secondary'])
        subtitle.pack(pady=(0, 30))
        
        # Buttons
        buttons_frame = ctk.CTkFrame(container, fg_color="transparent")
        buttons_frame.pack()
        
        generate_btn = ctk.CTkButton(buttons_frame, text="Générer un Planning", height=45, width=200,
                                     corner_radius=8, fg_color=self.colors['primary'], hover_color="#6D28D9",
                                     font=("Segoe UI", 14, "bold"), command=self.app.trigger_new_planning)
        generate_btn.pack(side="left", padx=10)
        
        load_btn = ctk.CTkButton(buttons_frame, text="Charger un Planning", height=45, width=200,
                                corner_radius=8, fg_color="transparent", hover_color=self.colors['hover'],
                                border_width=2, border_color=self.colors['primary'], text_color=self.colors['primary'],
                                font=("Segoe UI", 14, "bold"), command=self.app.trigger_open_planning)
        load_btn.pack(side="left", padx=10)
    
    def get_satisfaction_data(self):
        """Get satisfaction data from database - OPTIMIZED with caching"""
        # Return cached data if available and not forcing reload
        if self.cached_satisfaction_data is not None and not self._prevent_reload:
            return self.cached_satisfaction_data
        
        # Check app-level cache
        cache_key = f"satisfaction_{getattr(self.app, 'current_session_id', 'none')}"
        if hasattr(self.app, 'get_cached_data') and not self._prevent_reload:
            cached = self.app.get_cached_data(cache_key)
            if cached:
                self.cached_satisfaction_data = cached
                return cached
        
        # Import database
        base_dir = Path(__file__).parent.parent.parent
        db_dir = base_dir / "src" / "db"
        if str(db_dir) not in sys.path:
            sys.path.insert(0, str(db_dir))
        
        try:
            from db_operations import DatabaseManager
            db = DatabaseManager()
            
            # Get current session
            session_id = getattr(self.app, 'current_session_id', None)
            if not session_id:
                raise Exception("No active session")
            
            # Get satisfaction data using the correct methods
            teachers = db.get_satisfaction_report(session_id)
            
            # If no satisfaction data exists, compute it from assignments
            if not teachers:
                print(f"📊 Computing satisfaction data for session {session_id}...")
                count = db.compute_satisfaction_from_db(session_id)
                if count > 0:
                    print(f"✅ Computed satisfaction for {count} teachers")
                    # Reload the data
                    teachers = db.get_satisfaction_report(session_id)
                else:
                    print("⚠️ No assignments found to compute satisfaction")
            
            stats = db.get_satisfaction_stats(session_id)
            
            # Combine stats and teachers
            result = {
                'avg_score': stats['avg_score'],
                'highly_satisfied': stats['highly_satisfied'],
                'satisfied': stats['satisfied'],
                'neutral': stats['neutral'],
                'dissatisfied': stats['dissatisfied'],
                'teachers': teachers,
                'no_data': False
            }
            
            # Cache the result
            self.cached_satisfaction_data = result
            if hasattr(self.app, 'cache_data'):
                self.app.cache_data(cache_key, result)
            
            self._prevent_reload = False  # Reset flag
            return result
            
        except Exception as e:
            print(f"Error loading satisfaction data: {e}")
            import traceback
            traceback.print_exc()
        
        return {'avg_score': 0, 'highly_satisfied': 0, 'satisfied': 0, 'neutral': 0, 'dissatisfied': 0, 'teachers': [], 'no_data': True}
    
    def navigate_to_teacher_planning(self, teacher):
        """Navigate to the edit planning screen in Enseignants view"""
        try:
            # Set initial view mode before navigation to prevent flicker
            self.app.initial_planning_view = 'teachers'
            
            # Navigate to edit planning screen
            self.app.show_edit_planning()
            
        except Exception as e:
            print(f"Error navigating to planning: {e}")
    
    def get_score_color(self, score):
        """Get color based on score"""
        if score >= 80:
            return self.colors['success']
        elif score >= 60:
            return self.colors['primary']
        elif score >= 40:
            return self.colors['warning']
        else:
            return self.colors['error']
    
    def show_loading_indicator(self, parent):
        """Show animated loading indicator in the teachers list area"""
        # Create loading container
        loading_frame = ctk.CTkFrame(parent, fg_color="transparent")
        loading_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Center content
        loading_content = ctk.CTkFrame(loading_frame, fg_color="transparent")
        loading_content.place(relx=0.5, rely=0.5, anchor="center")
        
        # Animated spinner (using rotating emoji)
        self.loading_label = ctk.CTkLabel(
            loading_content, 
            text="⏳", 
            font=("Segoe UI", 48),
            text_color=self.colors['primary']
        )
        self.loading_label.pack(pady=(0, 15))
        
        # Loading text
        loading_text = ctk.CTkLabel(
            loading_content,
            text="Chargement des enseignants...",
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors['text_primary']
        )
        loading_text.pack(pady=(0, 5))
        
        # Count subtext (if we have the data)
        if hasattr(self, 'filtered_teachers_data'):
            count_text = f"{len(self.filtered_teachers_data)} enseignant(s) à charger"
        else:
            count_text = "Veuillez patienter"
        
        self.loading_count_label = ctk.CTkLabel(
            loading_content,
            text=count_text,
            font=("Segoe UI", 11),
            text_color=self.colors['text_secondary']
        )
        self.loading_count_label.pack()
        
        # Store reference to remove later
        self.loading_frame = loading_frame
        
        # Start spinner animation
        self._animate_loading_spinner()
    
    def _animate_loading_spinner(self):
        """Animate the loading spinner"""
        if not hasattr(self, 'loading_label') or not self.loading_label.winfo_exists():
            return
        
        # Rotate through spinner characters
        spinners = ["⏳", "⌛", "⏳", "⌛"]
        if not hasattr(self, '_spinner_index'):
            self._spinner_index = 0
        
        self.loading_label.configure(text=spinners[self._spinner_index])
        self._spinner_index = (self._spinner_index + 1) % len(spinners)
        
        # Continue animation
        if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
            self.after(200, self._animate_loading_spinner)
    
    def _load_teachers_async(self, parent, teachers):
        """Load teachers list asynchronously after UI is rendered - OPTIMIZED with batching"""
        # Remove loading indicator
        if hasattr(self, 'loading_frame'):
            try:
                self.loading_frame.destroy()
                delattr(self, 'loading_frame')
                delattr(self, 'loading_label')
                delattr(self, '_spinner_index')
            except:
                pass
        
        # Create the actual teachers list with LAZY LOADING
        # Only render visible items initially, add more as needed
        self.create_teachers_satisfaction_list(parent, teachers, lazy_load=True)
    
    def filter_teachers(self):
        """Filter teachers by search and grade - OPTIMIZED with better debounce"""
        # Cancel previous debounce timer
        if self.search_debounce_timer:
            self.after_cancel(self.search_debounce_timer)
        
        # Schedule filter application after 500ms of inactivity (increased from 300ms for better performance)
        self.search_debounce_timer = self.after(500, self._apply_filter)
    
    def _apply_filter(self):
        """Actually apply the filter after debounce delay - OPTIMIZED"""
        search_query = self.search_entry.get().lower().strip()
        grade_filter = self.grade_filter.get()
        
        # Use cached all_teachers_data
        filtered = self.all_teachers_data.copy() if search_query or grade_filter != "Tous" else self.all_teachers_data
        
        # Apply filters only if needed
        if search_query:
            filtered = [t for t in filtered if search_query in t['name'].lower()]
        
        if grade_filter != "Grade" and grade_filter != "Tous":
            filtered = [t for t in (filtered if search_query else self.all_teachers_data) if t['grade'] == grade_filter]
        
        self.filtered_teachers_data = filtered
        self.search_debounce_timer = None
        
        # Only refresh if there's actually a change (FIX: compare integers properly)
        last_count = getattr(self, '_last_filtered_count', -1)
        if len(filtered) != last_count:
            self._last_filtered_count = len(filtered)
            self.refresh_teachers_list()
        else:
            # Just update the count without full refresh if possible
            self._last_filtered_count = len(filtered)
    
    def reset_filters(self):
        """Reset all filters to default state"""
        # Reset search entry
        self.search_entry.delete(0, 'end')
        
        # Reset grade filter
        self.grade_filter.set("Tous")
        
        # Reset filtered data to all teachers
        self.filtered_teachers_data = self.all_teachers_data.copy()
        
        # Refresh the list
        self.refresh_teachers_list()
    
    def refresh_teachers_list(self):
        """Refresh teachers list - optimized for fast filtering with loading indicator"""
        # Show loading indicator for filters
        if hasattr(self, 'teachers_list_scroll') and self.teachers_list_scroll.winfo_exists():
            # Clear all widgets from scrollable frame
            for widget in self.teachers_list_scroll.winfo_children():
                widget.destroy()
        
        # Clear visible rows tracking
        if hasattr(self, 'visible_row_frames'):
            self.visible_row_frames.clear()
        
        # Find and destroy grid slaves
        for widget in self.teachers_list_container.grid_slaves(row=1):
            widget.destroy()
        
        # Show loading indicator
        self.show_loading_indicator(self.teachers_list_container)
        
        # Recreate the list with new filtered data asynchronously
        self.after(50, lambda: self._load_teachers_async(
            self.teachers_list_container, 
            self.filtered_teachers_data
        ))
    
    def create_teachers_satisfaction_list(self, parent, teachers, lazy_load=True):
        """Create list with OPTIMIZED lazy loading"""
        # Use CTkScrollableFrame but with virtual rendering
        scroll_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Store references
        self.teachers_list_scroll = scroll_frame
        self.current_scroll_frame = scroll_frame
        self.teachers_container = scroll_frame
        
        if not teachers:
            empty_label = ctk.CTkLabel(scroll_frame, text="Aucun enseignant trouvé", 
                                      font=("Segoe UI", 14), text_color=self.colors['text_secondary'])
            empty_label.pack(pady=50)
            return
        
        # Store teachers data
        self.current_teachers_data = teachers
        
        # OPTIMIZATION: Render in batches
        if lazy_load and len(teachers) > 30:
            # Render first 30 items immediately
            self._setup_lazy_loading(scroll_frame, teachers, batch_size=30)
        else:
            # Render all items for small lists
            self._setup_efficient_scrolling(scroll_frame, teachers)
    
    def _setup_lazy_loading(self, container, teachers, batch_size=30):
        """Setup lazy loading - render in batches for large lists"""
        self.visible_row_frames = {}
        self._lazy_load_index = 0
        self._lazy_load_teachers = teachers
        self._lazy_load_container = container
        self._lazy_load_batch_size = batch_size
        self._is_loading_batch = False
        
        # Render first batch immediately
        self._load_next_batch()
        
        # Setup scroll monitoring for lazy loading
        def check_scroll_position():
            if self._is_loading_batch:
                return
            
            try:
                # Get the canvas from CTkScrollableFrame
                canvas = container._parent_canvas
                # Check if scrolled near bottom (70% threshold for smoother loading)
                scroll_position = canvas.yview()
                
                if scroll_position[1] > 0.7 and self._lazy_load_index < len(self._lazy_load_teachers):
                    self._load_next_batch()
                    
            except Exception as e:
                pass
            
            # Continue monitoring if not all loaded
            if self._lazy_load_index < len(self._lazy_load_teachers):
                container.after(200, check_scroll_position)  # Check every 200ms
        
        # Start monitoring after a short delay
        container.after(100, check_scroll_position)
    
    def _load_next_batch(self):
        """Load next batch of teachers"""
        if self._lazy_load_index >= len(self._lazy_load_teachers):
            return  # All loaded
        
        # Set loading flag to prevent concurrent batch loading
        self._is_loading_batch = True
        
        try:
            end_index = min(self._lazy_load_index + self._lazy_load_batch_size, len(self._lazy_load_teachers))
            
            # Render batch
            for i in range(self._lazy_load_index, end_index):
                self._create_packed_teacher_row(self._lazy_load_container, self._lazy_load_teachers[i], i)
            
            self._lazy_load_index = end_index
            
            # Update display
            self._lazy_load_container.update_idletasks()
            
            # Debug info
            print(f"📊 Loaded batch: {end_index}/{len(self._lazy_load_teachers)} teachers")
            
        finally:
            self._is_loading_batch = False
    
    def _setup_efficient_scrolling(self, container, teachers):
        """Setup efficient scrolling - render all items immediately with optimizations"""
        # Track visible rows
        self.visible_row_frames = {}
        
        # Temporarily disable updates for faster rendering
        container.update_idletasks()
        
        # Render ALL items immediately - no batching delays
        # This is fast because:
        # 1. We're using efficient widget creation
        # 2. No artificial delays
        # 3. CustomTkinter handles it well
        for i in range(len(teachers)):
            self._create_packed_teacher_row(container, teachers[i], i)
        
        # Force update after all items created
        container.update_idletasks()
    
    def _create_packed_teacher_row(self, parent, teacher, index):
        """Create teacher row using pack geometry - OPTIMIZED with reduced nesting"""
        row = ctk.CTkFrame(parent, fg_color=self.colors['surface'], corner_radius=6, 
                          border_width=1, border_color=self.colors['border'], height=70)
        row.pack(fill="x", pady=2, padx=5)
        row.pack_propagate(False)
        
        # Use grid layout directly on row (more efficient than nested frames)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=0)
        
        # Left side: teacher info
        info_container = ctk.CTkFrame(row, fg_color="transparent")
        info_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=6)
        
        # Name and grade on one line
        name_text = f"{teacher['name']}  •  {teacher['grade']} • {teacher['total_assignments']} créneaux"
        name_label = ctk.CTkLabel(info_container, text=name_text, 
                                  font=("Segoe UI", 12, "bold"), text_color=self.colors['text_primary'],
                                  anchor="w")
        name_label.pack(fill="x", pady=(0, 4))
        
        # Progress bar container (flatter structure)
        score_container = ctk.CTkFrame(info_container, fg_color="transparent")
        score_container.pack(fill="x")
        
        score_color = self.get_score_color(teacher['satisfaction_score'])
        
        progress = ctk.CTkProgressBar(score_container, height=4, corner_radius=2, 
                                      fg_color=self.colors['background'], progress_color=score_color)
        progress.set(teacher['satisfaction_score'] / 100)
        progress.pack(fill="x", side="left", expand=True, padx=(0, 8))
        
        score_label = ctk.CTkLabel(score_container, text=f"{teacher['satisfaction_score']:.0f}", 
                                   font=("Segoe UI", 12, "bold"), text_color=score_color, width=30)
        score_label.pack(side="right")
        
        # Right side: button
        view_btn = ctk.CTkButton(row, text="Détails", width=70, height=28, corner_radius=6, 
                                 fg_color=self.colors['primary'], hover_color=self.colors['hover_dark'], 
                                 font=("Segoe UI", 11, "bold"), 
                                 command=lambda t=teacher: self.show_teacher_details(t))
        view_btn.grid(row=0, column=1, padx=(0, 10), sticky="ns")
        
        self.visible_row_frames[index] = row
        return row
    
    def create_teacher_satisfaction_row(self, parent, teacher):
        """Legacy method for compatibility"""
        return self._create_packed_teacher_row(parent, teacher, 0)
    
    def create_satisfaction_details(self, parent, teachers):
        """Create details panel with centered placeholder"""
        # Use a regular frame for the details area to enable proper centering
        details_container = ctk.CTkFrame(parent, fg_color="transparent")
        details_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Create scrollable frame that will be shown when details are displayed
        self.details_scroll = ctk.CTkScrollableFrame(details_container, fg_color="transparent")
        
        # Create placeholder frame (centered)
        self.placeholder_frame = ctk.CTkFrame(details_container, fg_color="transparent")
        self.placeholder_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        icon_label = ctk.CTkLabel(self.placeholder_frame, text="👤", font=("Segoe UI", 64))
        icon_label.pack(pady=(0, 15))
        
        placeholder = ctk.CTkLabel(self.placeholder_frame, text="Sélectionnez un enseignant\npour voir les détails",
                                  font=("Segoe UI", 15), text_color=self.colors['text_secondary'], justify="center")
        placeholder.pack()
    
    def show_teacher_details(self, teacher):
        """Show teacher details - optimized layout"""
        # Hide placeholder and show scroll frame
        if hasattr(self, 'placeholder_frame'):
            self.placeholder_frame.place_forget()
        
        # Show and populate details scroll
        self.details_scroll.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Clear existing content
        for widget in self.details_scroll.winfo_children():
            widget.destroy()
        
        # Compact Header with score
        header_frame = ctk.CTkFrame(self.details_scroll, fg_color=self.get_score_color(teacher['satisfaction_score']), 
                                    corner_radius=10, height=90)
        header_frame.pack(fill="x", pady=(0, 12))
        header_frame.pack_propagate(False)
        
        header_content = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=15, pady=12)
        
        name_label = ctk.CTkLabel(header_content, text=teacher['name'], 
                                 font=("Segoe UI", 18, "bold"), text_color="white")
        name_label.pack(anchor="w")
        
        info_row = ctk.CTkFrame(header_content, fg_color="transparent")
        info_row.pack(fill="x", pady=(5, 0))
        
        score_label = ctk.CTkLabel(info_row, text=f"Score: {teacher['satisfaction_score']:.0f}/100",
                                   font=("Segoe UI", 22, "bold"), text_color="white")
        score_label.pack(side="left")
        
        grade_label = ctk.CTkLabel(info_row, text=f"  •  {teacher['grade']}",
                                  font=("Segoe UI", 14), text_color="white")
        grade_label.pack(side="left", padx=(10, 0))
        
        # NEW: "Voir le Planning" button
        planning_btn_frame = ctk.CTkFrame(self.details_scroll, fg_color="transparent")
        planning_btn_frame.pack(fill="x", pady=(0, 12))
        
        planning_btn = ctk.CTkButton(
            planning_btn_frame,
            text="📅 Voir le Planning de cet Enseignant",
            height=40,
            corner_radius=8,
            fg_color=self.colors['primary'],
            hover_color="#6D28D9",
            font=("Segoe UI", 13, "bold"),
            command=lambda: self.navigate_to_teacher_planning(teacher)
        )
        planning_btn.pack(fill="x", padx=4)
        
        # Compact Metrics Grid - 3 columns for better space usage (OPTIMIZED - REMOVED UNNECESSARY METRICS)
        metrics_frame = ctk.CTkFrame(self.details_scroll, fg_color="transparent")
        metrics_frame.pack(fill="x", pady=(0, 12))
        
        for i in range(3):
            metrics_frame.grid_columnconfigure(i, weight=1)
        
        # NEW OPTIMIZED METRICS (removed "Jours Optimaux" and will remove "Modèle d'Emploi")
        voeux_text = f"{teacher.get('voeux_respected', 0)}/{teacher.get('voeux_total', 0)}" if teacher.get('voeux_total', 0) > 0 else "N/A"
        gap_hours_text = f"{teacher.get('gap_hours', 0)}h"
        
        metrics = [
            ("📚", "Assignations", f"{teacher['total_assignments']}"),
            ("📅", "Jours Travaillés", str(teacher['working_days'])),
            ("❤️", "Voeux Respectés", voeux_text),
            ("❌", "Jours Isolés", str(teacher['isolated_days'])),
            
            
        ]
        
        for idx, (icon, label, value) in enumerate(metrics):
            card = ctk.CTkFrame(metrics_frame, fg_color=self.colors['background'], corner_radius=8, height=70)
            card.grid(row=idx // 3, column=idx % 3, padx=4, pady=4, sticky="ew")
            card.grid_propagate(False)
            
            card_content = ctk.CTkFrame(card, fg_color="transparent")
            card_content.pack(fill="both", expand=True, padx=10, pady=8)
            
            # Icon and label on same line
            top_row = ctk.CTkFrame(card_content, fg_color="transparent")
            top_row.pack(fill="x")
            
            icon_label = ctk.CTkLabel(top_row, text=icon, font=("Segoe UI", 14))
            icon_label.pack(side="left")
            
            label_widget = ctk.CTkLabel(top_row, text=label, font=("Segoe UI", 10), 
                                       text_color=self.colors['text_secondary'], anchor="w")
            label_widget.pack(side="left", padx=(5, 0))
            
            value_widget = ctk.CTkLabel(card_content, text=value, font=("Segoe UI", 16, "bold"), 
                                       text_color=self.colors['primary'], anchor="w")
            value_widget.pack(fill="x", pady=(4, 0))
        
       
