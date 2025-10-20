"""
PyInstaller runtime hook for ISI Exam Scheduler
Ensures src directory is in sys.path for imports
"""

import sys
import os

# Get the directory where the executable is running
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle
    bundle_dir = sys._MEIPASS
else:
    # Running in development
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Add src directory to Python path
src_dir = os.path.join(bundle_dir, 'src')
if os.path.exists(src_dir) and src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Add src/db directory to Python path
db_dir = os.path.join(src_dir, 'db')
if os.path.exists(db_dir) and db_dir not in sys.path:
    sys.path.insert(0, db_dir)

# Add tkinter_isi directory
tkinter_dir = os.path.join(bundle_dir, 'tkinter_isi')
if os.path.exists(tkinter_dir) and tkinter_dir not in sys.path:
    sys.path.insert(0, tkinter_dir)
