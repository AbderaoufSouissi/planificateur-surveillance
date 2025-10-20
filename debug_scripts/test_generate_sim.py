# Test script to simulate Generate flow without GUI
import sys
sys.path.insert(0, r'c:/Users/ghait/Desktop/isi-project/ISI-Exam-Scheduler')

from tkinter_isi.screens.import_and_generate import ImportAndGenerateScreen

class DummyApp:
    def __init__(self):
        self.colors = {'background': 'white', 'surface': 'white', 'border': 'gray', 'primary': '#7c3aed', 'text_primary': '#111827', 'text_secondary': '#6b7280', 'success':'#10B981','error':'#EF4444','accent':'#F59E0B','hover':'#f3f4f6'}
        self.generation_state = {'is_generating': False, 'generation_thread': None, 'generation_progress': 0, 'cancel_requested': False}
        self.imported_files = {}
        self.current_session_id = 999999  # intentionally invalid session
        self.update_status = lambda s: print('[APP STATUS]', s)
        self.should_load_from_db = False

# Create a fake parent using tkinter to satisfy widget creation
import tkinter as tk
root = tk.Tk()
root.withdraw()

app = DummyApp()
frame = ImportAndGenerateScreen(root, app)

# Inject file paths (point to resources existing in repo)
base = frame.base_dir
frame.file_paths['teachers'] = str(base / 'resources' / 'Enseignants.xlsx')
frame.file_paths['slots'] = str(base / 'resources' / 'Repartitions.xlsx')
frame.file_paths['preferences'] = str(base / 'resources' / 'Souhaits.xlsx')

# Build a config and call run_generation_thread synchronously to capture exceptions
config = frame.get_configuration()
try:
    frame.run_generation_thread(config)
    print('Generation thread completed without uncaught exception')
except Exception as e:
    print('Exception during generation:', e)
    import traceback
    traceback.print_exc()

print('Done')
