"""
Modern Light Theme Stylesheet for Data Management App
Clean, professional design matching the reference image
"""

DARK_THEME = """
    /* ===== GLOBAL STYLES ===== */
    * {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
    }
    
    QMainWindow, QWidget {
        background-color: #f3f4f6;
        color: #1f2937;
    }
    
    /* ===== TOP NAVIGATION BAR ===== */
    QWidget#topNavBar {
        background-color: white;
        border-bottom: 1px solid #e5e7eb;
    }
    
    QLabel#navTitle {
        font-size: 20px;
        font-weight: 700;
        color: #1f2937;
    }
    
    QPushButton#navButton {
        background-color: transparent;
        color: #6b7280;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        min-height: 20px;
    }
    
    QPushButton#navButton:hover {
        background-color: #f3f4f6;
        color: #1f2937;
    }
    
    QPushButton#navButton:pressed {
        background-color: #e5e7eb;
    }
    
    /* ===== PRIMARY BUTTONS ===== */
    QPushButton#primaryButton {
        background-color: #3b82f6;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 15px;
        font-weight: 600;
        min-height: 20px;
    }
    
    QPushButton#primaryButton:hover {
        background-color: #2563eb;
    }
    
    QPushButton#primaryButton:pressed {
        background-color: #1d4ed8;
    }
    
    /* ===== SECONDARY BUTTONS ===== */
    QPushButton#secondaryButton {
        background-color: #e5e7eb;
        color: #374151;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 15px;
        font-weight: 600;
        min-height: 20px;
    }
    
    QPushButton#secondaryButton:hover {
        background-color: #d1d5db;
    }
    
    QPushButton#secondaryButton:pressed {
        background-color: #9ca3af;
    }
    
    /* ===== DROP ZONE ===== */
    QWidget#dropZone {
        background-color: #f9fafb;
        border: 3px dashed #d1d5db;
        border-radius: 16px;
    }
    
    /* ===== PAGE TITLES ===== */
    QLabel#pageTitle {
        font-size: 32px;
        font-weight: 700;
        color: #111827;
        padding: 0;
        margin: 0;
    }
    
    /* ===== SCROLLBAR ===== */
    QScrollBar:vertical {
        background-color: #f3f4f6;
        width: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #d1d5db;
        border-radius: 6px;
        min-height: 30px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #9ca3af;
    }
    
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: none;
    }
    
    QScrollBar:horizontal {
        background-color: #f3f4f6;
        height: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #d1d5db;
        border-radius: 6px;
        min-width: 30px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #9ca3af;
    }
    
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {
        background: none;
    }
    
    /* ===== TAB BUTTONS ===== */
    QPushButton#tabButtonActive {
        background-color: transparent;
        color: #3b82f6;
        border: none;
        border-bottom: 3px solid #3b82f6;
        border-radius: 0;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 600;
        min-height: 20px;
    }
    
    QPushButton#tabButton {
        background-color: transparent;
        color: #6b7280;
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        min-height: 20px;
    }
    
    QPushButton#tabButton:hover {
        color: #374151;
        border-bottom: 3px solid #d1d5db;
    }
"""


def get_dark_theme():
    """Return the theme stylesheet"""
    return DARK_THEME
