"""
Modern Step Indicator Widget
Shows visual progress through the 3-step workflow with modern design
Matches the exact design from the reference image
"""

import customtkinter as ctk


class StepIndicator(ctk.CTkFrame):
    """Modern centered step indicator matching the reference image exactly"""
    
    def __init__(self, parent, current_step, colors, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.colors = colors
        self.current_step = current_step
        self.steps = [
            {"number": 1, "label": "Import & Générer"},
            {"number": 2, "label": "Éditer Planning"},
            {"number": 3, "label": "Exporter"}
        ]
        
        self.create_indicator()
    
    def create_indicator(self):
        """Create the step indicator UI matching the reference image exactly"""
        # Main container with fixed height - reduced spacing
        container = ctk.CTkFrame(self, fg_color="transparent", height=60)
        container.pack(fill="x", pady=(0, 5))
        container.pack_propagate(False)
        
        # Center frame to hold all steps horizontally in one row
        center_frame = ctk.CTkFrame(container, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        for idx, step in enumerate(self.steps):
            step_num = step["number"]
            is_active = step_num == self.current_step
            is_completed = step_num < self.current_step
            
            # Determine colors and styling based on state
            if is_completed:
                # Completed: purple hollow circle, purple number and text, purple line
                circle_border_color = self.colors['primary']
                circle_bg = "transparent"
                number_color = self.colors['primary']
                label_color = self.colors['primary']
                label_weight = "bold"
                border_width = 3
            elif is_active:
                # Active: primary color hollow circle, primary number and text
                circle_border_color = self.colors['primary']
                circle_bg = "transparent"
                number_color = self.colors['primary']
                label_color = self.colors['primary']
                label_weight = "bold"
                border_width = 3
            else:
                # Inactive: gray hollow circle, gray text
                circle_border_color = "#D1D5DB"
                circle_bg = "transparent"
                number_color = "#9CA3AF"
                label_color = "#9CA3AF"
                label_weight = "normal"
                border_width = 2
            
            # Step container (holds circle and label horizontally - SIDE BY SIDE)
            step_container = ctk.CTkFrame(center_frame, fg_color="transparent")
            step_container.pack(side="left", padx=(0, 0))
            
            # Hollow Circle (outline only - fixed size: 48x48px)
            circle_size = 48
            circle = ctk.CTkFrame(
                step_container,
                fg_color=circle_bg,
                border_color=circle_border_color,
                border_width=border_width,
                corner_radius=circle_size // 2,
                width=circle_size,
                height=circle_size
            )
            circle.pack_propagate(False)
            circle.pack(side="left")
            
            # Number inside hollow circle
            number_label = ctk.CTkLabel(
                circle,
                text=str(step_num),
                font=("Segoe UI", 18, "bold"),
                text_color=number_color
            )
            number_label.place(relx=0.5, rely=0.5, anchor="center")
            
            # Step label to the RIGHT of circle (side by side, not below)
            label = ctk.CTkLabel(
                step_container,
                text=step["label"],
                font=("Segoe UI", 14, label_weight),
                text_color=label_color
            )
            label.pack(side="left", padx=(12, 0))  # 12px spacing from circle
            
            # Connector line between steps (except after last step)
            if idx < len(self.steps) - 1:
                # Line color: purple for completed steps, gray for upcoming
                if is_completed:
                    line_color = self.colors['primary']  # Purple for completed
                else:
                    line_color = "#D1D5DB"  # Gray for upcoming steps
                
                line_width = 80  # Distance between steps
                line_height = 4  # Thicker line for better visibility
                
                # Line positioned horizontally between steps
                line = ctk.CTkFrame(
                    center_frame,
                    fg_color=line_color,
                    height=line_height,
                    width=line_width
                )
                line.pack(side="left", padx=20)  # Spacing on both sides of line
