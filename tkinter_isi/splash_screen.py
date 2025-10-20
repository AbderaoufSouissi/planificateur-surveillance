"""
Modern Splash Screen for ISI Surveillance Application
Displays during application initialization with smooth animations
"""

import customtkinter as ctk
from tkinter import Canvas
from PIL import Image
import time
import os
import math


class ModernSplashScreen:
    """
    Beautiful modern splash screen with ISI branding
    Features: Logo, app description, animated progress, decorative elements
    """
    
    def __init__(self, duration=3.0):
        """
        Initialize splash screen
        
        Parameters:
        -----------
        duration : float
            How long to display the splash screen (seconds)
        """
        self.duration = duration
        self.progress = 0
        self.is_loading = True
        
        # Create splash window
        self.window = ctk.CTk()
        self.window.withdraw()
        
        # Modern Color Scheme - Purple palette matching app design
        self.colors = {
            'primary': '#7C3AED',           # Vibrant purple
            'primary_light': '#A78BFA',     # Light purple
            'accent': '#8B5CF6',            # Medium purple
            'accent_light': '#C4B5FD',      # Very light purple
            'background': '#F3F4F6',        # Light gray
            'surface': '#FFFFFF',           # White
            'text_primary': '#1F2937',      # Dark gray
            'text_secondary': '#6B7280',    # Medium gray
            'decoration': '#EDE9FE',        # Purple 100
            'decoration2': '#DDD6FE',       # Purple 200
        }
        
        # Window configuration
        self.setup_window()
        
        # Create UI elements
        self.create_ui()
        
    def setup_window(self):
        """Configure splash window appearance"""
        width = 750
        height = 550
        
        # Center on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.overrideredirect(True)
        self.window.configure(fg_color=self.colors['background'])
        self.window.attributes('-topmost', True)
        
    def create_ui(self):
        """Create all UI elements with modern design"""
        # Background decorative elements
        self.create_background_decorations()
        
        # Main card with shadow effect
        card = ctk.CTkFrame(
            self.window,
            fg_color=self.colors['surface'],
            corner_radius=28,
            border_width=0
        )
        card.pack(fill="both", expand=True, padx=25, pady=25)
        
        # Content container
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=50, pady=45)
        
        # Top spacer
        ctk.CTkFrame(content, fg_color="transparent", height=20).pack()
        
        # Logo with decorative background
        self.create_logo_section(content)
        
        # Spacer
        ctk.CTkFrame(content, fg_color="transparent", height=35).pack()
        
        # App description with modern styling
        self.create_description_section(content)
        
        # Spacer
        ctk.CTkFrame(content, fg_color="transparent", height=45).pack()
        
        # Modern loading section
        self.create_loading_section(content)
        
        # Spacer to push footer down
        ctk.CTkFrame(content, fg_color="transparent", height=1).pack(expand=True)
        
        # Modern footer
        self.create_footer(content)
        
    def create_background_decorations(self):
        """Create decorative background elements"""
        # Decorative circle - top right
        decoration1 = ctk.CTkFrame(
            self.window,
            width=200,
            height=200,
            corner_radius=100,
            fg_color=self.colors['decoration'],
            border_width=0
        )
        decoration1.place(x=600, y=-50)
        
        # Decorative circle - bottom left
        decoration2 = ctk.CTkFrame(
            self.window,
            width=150,
            height=150,
            corner_radius=75,
            fg_color=self.colors['decoration2'],
            border_width=0
        )
        decoration2.place(x=-40, y=420)
        
        # Small accent circle - top left
        decoration3 = ctk.CTkFrame(
            self.window,
            width=80,
            height=80,
            corner_radius=40,
            fg_color=self.colors['primary_light'],
            border_width=0
        )
        decoration3.place(x=30, y=40)
        decoration3.attributes = {'alpha': 0.3}
        
    def create_logo_section(self, parent):
        """Display logo with modern card background"""
        logo_container = ctk.CTkFrame(parent, fg_color="transparent")
        logo_container.pack()
        
        # Subtle background card for logo
        logo_bg = ctk.CTkFrame(
            logo_container,
            fg_color=self.colors['background'],
            corner_radius=24,
            border_width=0
        )
        logo_bg.pack(padx=10, pady=10)
        
        # Load logo
        logo_path = os.path.join(os.path.dirname(__file__), "isi.png")
        
        try:
            if os.path.exists(logo_path):
                logo_pil = Image.open(logo_path)
                self.logo_photo = ctk.CTkImage(
                    light_image=logo_pil,
                    dark_image=logo_pil,
                    size=(200, 200)
                )
                
                logo_label = ctk.CTkLabel(
                    logo_bg,
                    image=self.logo_photo,
                    text=""
                )
                logo_label.pack(padx=25, pady=25)
            else:
                # Fallback
                error_label = ctk.CTkLabel(
                    logo_bg,
                    text="Logo not found",
                    font=("Segoe UI", 14),
                    text_color=self.colors['text_secondary']
                )
                error_label.pack(padx=25, pady=25)
        except Exception as e:
            error_label = ctk.CTkLabel(
                logo_bg,
                text="Error loading logo",
                font=("Segoe UI", 14),
                text_color=self.colors['text_secondary']
            )
            error_label.pack(padx=25, pady=25)
    
    def create_description_section(self, parent):
        """Create app description with modern badge"""
        desc_container = ctk.CTkFrame(parent, fg_color="transparent")
        desc_container.pack()
        
        # Modern badge background
        badge = ctk.CTkFrame(
            desc_container,
            fg_color=self.colors['primary'],
            corner_radius=16,
            border_width=0
        )
        badge.pack()
        
        # Description text
        desc_label = ctk.CTkLabel(
            badge,
            text="Système de Gestion des Créneaux de Surveillance",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors['surface']
        )
        desc_label.pack(padx=30, pady=14)
        
    def create_loading_section(self, parent):
        """Create modern loading indicator"""
        loading_frame = ctk.CTkFrame(parent, fg_color="transparent")
        loading_frame.pack()
        
        # Loading text
        self.loading_label = ctk.CTkLabel(
            loading_frame,
            text="Initialisation",
            font=("Segoe UI", 13),
            text_color=self.colors['text_secondary']
        )
        self.loading_label.pack(pady=(0, 18))
        
        # Modern progress bar container
        progress_container = ctk.CTkFrame(
            loading_frame,
            fg_color=self.colors['background'],
            corner_radius=12,
            border_width=0
        )
        progress_container.pack()
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            progress_container,
            width=350,
            height=8,
            corner_radius=4,
            progress_color=self.colors['primary'],
            fg_color=self.colors['surface']
        )
        self.progress_bar.pack(padx=8, pady=8)
        self.progress_bar.set(0)
        
        # Start animations
        self.animate_dots()
        self.animate_progress()
    
    def create_footer(self, parent):
        """Create modern footer with badge style"""
        footer_frame = ctk.CTkFrame(parent, fg_color="transparent")
        footer_frame.pack(side="bottom", pady=10)
        
        # Version badge
        version_badge = ctk.CTkFrame(
            footer_frame,
            fg_color=self.colors['background'],
            corner_radius=14,
            border_width=0
        )
        version_badge.pack()
        
        version_label = ctk.CTkLabel(
            version_badge,
            text="v1.0.0  •  ISI Tunisia © 2025",
            font=("Segoe UI", 10),
            text_color=self.colors['text_secondary']
        )
        version_label.pack(padx=18, pady=7)
    
    def animate_dots(self):
        """Animate loading dots"""
        if self.is_loading:
            self.dot_count = (self.dot_count + 1) % 4 if hasattr(self, 'dot_count') else 1
            dots = "." * self.dot_count
            spaces = " " * (3 - self.dot_count)
            self.loading_label.configure(text=f"Initialisation{dots}{spaces}")
            self.window.after(500, self.animate_dots)
    
    def animate_progress(self):
        """Animate progress bar with smooth easing"""
        if self.is_loading and self.progress < 1.0:
            # Ease-in-out animation
            self.progress += 0.015
            self.progress_bar.set(min(self.progress, 1.0))
            self.window.after(50, self.animate_progress)
    
    def fade_out(self):
        """Smooth fade out effect"""
        for alpha in [1.0, 0.8, 0.6, 0.35, 0.1, 0.0]:
            self.window.attributes('-alpha', alpha)
            self.window.update()
            time.sleep(0.05)
    
    def finish_loading(self):
        """Called when loading is complete"""
        if self.is_loading:
            self.is_loading = False
            self.progress_bar.set(1.0)
            
            # Change to success color
            self.loading_label.configure(
                text="Prêt ! ✓",
                text_color=self.colors['accent']
            )
            self.window.update()
            
            time.sleep(0.4)
            self.fade_out()
            self.window.quit()
    
    def show(self):
        """Display splash screen with smooth animations"""
        # Smooth fade in
        self.window.attributes('-alpha', 0.0)
        self.window.deiconify()
        
        for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
            self.window.attributes('-alpha', alpha)
            self.window.update()
            time.sleep(0.05)
        
        # Schedule finish
        self.window.after(int(self.duration * 1000), self.finish_loading)
        
        # Run mainloop
        self.window.mainloop()
        
        # Cleanup
        try:
            self.window.destroy()
        except:
            pass
    
    def close(self):
        """Close splash screen immediately"""
        self.is_loading = False
        try:
            self.window.destroy()
        except:
            pass


def show_splash_screen(duration=2.0):
    """
    Convenience function to show splash screen
    
    Parameters:
    -----------
    duration : float
        Display duration in seconds
    """
    splash = ModernSplashScreen(duration=duration)
    splash.show()


if __name__ == "__main__":
    # Test splash screen
    show_splash_screen(duration=2.0)