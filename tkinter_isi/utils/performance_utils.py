"""
Performance utilities for the application
Includes helpers for async loading, caching, and UI optimization
"""

import threading
import functools
from tkinter import ttk
import time


class LoadingIndicator:
    """Show a loading indicator while performing operations"""
    
    def __init__(self, parent, message="Chargement en cours..."):
        self.parent = parent
        self.message = message
        self.window = None
        
    def show(self):
        """Show loading indicator"""
        try:
            import customtkinter as ctk
            self.window = ctk.CTkToplevel(self.parent)
            self.window.title("")
            self.window.geometry("300x100")
            self.window.resizable(False, False)
            
            # Center on parent
            self.window.transient(self.parent)
            self.window.grab_set()
            
            # Content
            label = ctk.CTkLabel(
                self.window,
                text=self.message,
                font=("Segoe UI", 14)
            )
            label.pack(pady=(20, 10))
            
            progress = ctk.CTkProgressBar(self.window, mode='indeterminate')
            progress.pack(pady=10, padx=20, fill='x')
            progress.start()
            
            self.window.update()
        except:
            pass
    
    def hide(self):
        """Hide loading indicator"""
        if self.window:
            try:
                self.window.grab_release()
                self.window.destroy()
            except:
                pass


def run_in_thread(func):
    """Decorator to run a function in a background thread"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    return wrapper


def debounce(wait_time):
    """
    Decorator that will debounce a function so that it is called after wait_time seconds
    If it is called multiple times, it will only execute once after the last call.
    """
    def decorator(func):
        timer = None
        
        @functools.wraps(func)
        def debounced(*args, **kwargs):
            nonlocal timer
            
            def call_func():
                nonlocal timer
                timer = None
                func(*args, **kwargs)
            
            if timer is not None:
                timer.cancel()
            
            timer = threading.Timer(wait_time, call_func)
            timer.start()
        
        return debounced
    return decorator


def batch_update(widget, items, batch_size=100, delay_ms=10):
    """
    Insert items into a widget in batches to avoid UI freeze
    
    Args:
        widget: Tkinter widget (Treeview, Listbox, etc.)
        items: List of items to insert
        batch_size: Number of items per batch
        delay_ms: Delay between batches in milliseconds
    """
    def insert_batch(start_idx):
        end_idx = min(start_idx + batch_size, len(items))
        
        for i in range(start_idx, end_idx):
            item = items[i]
            if hasattr(widget, 'insert'):
                if isinstance(item, tuple):
                    widget.insert('', 'end', values=item)
                else:
                    widget.insert('', 'end', text=item)
        
        # Schedule next batch
        if end_idx < len(items):
            widget.after(delay_ms, lambda: insert_batch(end_idx))
    
    # Start first batch
    if items:
        insert_batch(0)


class DataCache:
    """Simple in-memory cache for loaded data"""
    
    _cache = {}
    
    @classmethod
    def set(cls, key, value):
        """Store value in cache"""
        cls._cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    @classmethod
    def get(cls, key, max_age_seconds=None):
        """Get value from cache if exists and not expired"""
        if key not in cls._cache:
            return None
        
        cached = cls._cache[key]
        
        if max_age_seconds:
            age = time.time() - cached['timestamp']
            if age > max_age_seconds:
                del cls._cache[key]
                return None
        
        return cached['value']
    
    @classmethod
    def clear(cls, key=None):
        """Clear cache (specific key or all)"""
        if key:
            cls._cache.pop(key, None)
        else:
            cls._cache.clear()
    
    @classmethod
    def has(cls, key):
        """Check if key exists in cache"""
        return key in cls._cache


def optimize_treeview(treeview):
    """Apply performance optimizations to a Treeview widget"""
    # Disable visual updates during bulk operations
    treeview.config(selectmode='none')  # Temporarily disable selection
    
    # Use a faster rendering mode
    style = ttk.Style()
    style.configure("Fast.Treeview", rowheight=25)
    treeview.configure(style="Fast.Treeview")
    
    return treeview


def virtual_scroll_treeview(treeview, data, visible_rows=50):
    """
    Implement virtual scrolling for large datasets in Treeview
    Only renders visible rows for better performance
    
    Args:
        treeview: ttk.Treeview widget
        data: List of data items
        visible_rows: Number of rows to keep rendered
    """
    total_rows = len(data)
    current_view_start = [0]  # Use list to make it mutable in nested function
    
    def update_view():
        """Update visible rows based on scroll position"""
        # Clear current items
        treeview.delete(*treeview.get_children())
        
        # Calculate visible range
        start = current_view_start[0]
        end = min(start + visible_rows, total_rows)
        
        # Insert visible rows
        for i in range(start, end):
            item = data[i]
            if isinstance(item, (list, tuple)):
                treeview.insert('', 'end', values=item)
            else:
                treeview.insert('', 'end', text=str(item))
    
    def on_scroll(*args):
        """Handle scroll events"""
        # Get scroll position (0.0 to 1.0)
        scroll_pos = float(args[0])
        
        # Calculate new start position
        new_start = int(scroll_pos * max(0, total_rows - visible_rows))
        
        if new_start != current_view_start[0]:
            current_view_start[0] = new_start
            update_view()
    
    # Set up scrollbar
    if hasattr(treeview, 'yview'):
        treeview.configure(yscrollcommand=on_scroll)
    
    # Initial render
    update_view()
