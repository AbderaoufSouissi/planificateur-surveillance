# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for ISI Exam Scheduler
Bundles all dependencies, data files, and resources into a single executable
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all customtkinter theme files
customtkinter_datas = collect_data_files('customtkinter')

# Additional data files to include
added_files = [
    # Assets
    ('tkinter_isi/assets', 'assets'),
    ('tkinter_isi/isi.png', '.'),
    
    # Resources folder (Excel templates, etc.)
    ('resources', 'resources'),
    
    # Styles
    ('styles', 'styles'),
    
    # Source modules
    ('src', 'src'),
    
    # Database (if exists)
    ('planning.db', '.'),
]

# Hidden imports that PyInstaller might miss
hidden_imports = [
    # CustomTkinter dependencies
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    
    # Tkinter components
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    
    # Application screens
    'screens.welcome_screen',
    'screens.dashboard',
    'screens.import_and_generate',
    'screens.edit_planning',
    'screens.reports',
    'screens.statistiques',
    'screens.file_validator',
    
    # Utilities
    'utils.performance_utils',
    'utils.scroll_fix',
    
    # Widgets
    'widgets.step_indicator',
    
    # Core dependencies
    'pandas',
    'openpyxl',
    'numpy',
    
    # OR-Tools (constraint solver)
    'ortools',
    'ortools.sat',
    'ortools.sat.python',
    'ortools.sat.python.cp_model',
    
    # Database
    'sqlite3',
    
    # Source modules
    'src.exam_scheduler_db',
    'src.data_loader',
    'src.export',
    'src.file_validator',
    'src.db.db_operations',
    'src.db.db',
    'src.teacher_schedule_generator',
    'src.pdf_generators',
    'src.invite_generator',
    'src.id_utils',
    'src.decision_support',
    
    # Document generation
    'docx',
    'docxtpl',
    'python_docx',
    'jinja2',
    
    # Other utilities
    'datetime',
    'collections',
    'dataclasses',
]

# Collect all OR-Tools data files
try:
    ortools_datas = collect_data_files('ortools')
except:
    ortools_datas = []

a = Analysis(
    ['tkinter_isi/main.py'],
    pathex=['.', 'src', 'src/db', 'tkinter_isi'],
    binaries=[],
    datas=added_files + customtkinter_datas + ortools_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'matplotlib',
        'scipy',
        'pytest',
        'IPython',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ISI_Exam_Scheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ISI_Exam_Scheduler',
)
