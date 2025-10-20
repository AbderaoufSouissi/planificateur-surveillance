"""
Import helper for ISI Exam Scheduler
Handles imports for both development and PyInstaller bundled environments
"""

import sys
import os

def get_database_manager():
    """Import and return DatabaseManager class"""
    try:
        # PyInstaller/bundled environment
        from src.db.db_operations import DatabaseManager
        return DatabaseManager
    except ImportError:
        try:
            # Development environment - add paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            src_dir = os.path.join(parent_dir, 'src')
            db_dir = os.path.join(src_dir, 'db')
            
            for path in [parent_dir, src_dir, db_dir]:
                if path not in sys.path:
                    sys.path.insert(0, path)
            
            from db_operations import DatabaseManager
            return DatabaseManager
        except ImportError as e:
            raise ImportError(f"Could not import DatabaseManager: {e}")

def get_import_excel():
    """Import and return import_excel_data_to_db function"""
    try:
        from src.db.db_operations import import_excel_data_to_db
        return import_excel_data_to_db
    except ImportError:
        from db_operations import import_excel_data_to_db
        return import_excel_data_to_db

def get_scheduler_db():
    """Import and return scheduler functions"""
    try:
        from src.exam_scheduler_db import generate_planning_from_db
        return generate_planning_from_db
    except ImportError:
        from exam_scheduler_db import generate_planning_from_db
        return generate_planning_from_db

def get_decision_support():
    """Import and return DecisionSupportSystem"""
    try:
        from src.decision_support import DecisionSupportSystem
        return DecisionSupportSystem
    except ImportError:
        from decision_support import DecisionSupportSystem
        return DecisionSupportSystem

# Pre-import commonly used classes for convenience
try:
    DatabaseManager = get_database_manager()
    HAS_DATABASE = True
except ImportError:
    DatabaseManager = None
    HAS_DATABASE = False
