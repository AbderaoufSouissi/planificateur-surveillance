"""
Automated build script for ISI Exam Scheduler executable
Creates a standalone Windows .exe with all dependencies bundled
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller is installed")
        return True
    except ImportError:
        print("❌ PyInstaller not found")
        print("\nInstalling PyInstaller...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
        print("✅ PyInstaller installed successfully")
        return True

def clean_build():
    """Clean previous build artifacts"""
    print("\n🧹 Cleaning previous builds...")
    
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"  ✅ Removed {dir_name}/")
            except Exception as e:
                print(f"  ⚠️  Could not remove {dir_name}/: {e}")
    
    # Remove __pycache__ directories
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
            except:
                pass
    
    print("✅ Cleanup complete!")

def build_executable():
    """Build the executable using PyInstaller"""
    print("\n🔨 Building executable with PyInstaller...")
    print("   This may take a few minutes...\n")
    
    # Build command
    cmd = [
        sys.executable,
        '-m', 'PyInstaller',
        'ISI_Exam_Scheduler.spec',
        '--clean',
        '--noconfirm',
    ]
    
    # Run PyInstaller
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n✅ Build successful!")
        return True
    else:
        print("\n❌ Build failed!")
        return False

def copy_additional_files():
    """Copy additional files to dist folder"""
    print("\n📋 Copying additional resources...")
    
    dist_dir = Path('dist/ISI_Exam_Scheduler')
    
    if not dist_dir.exists():
        print("  ⚠️  Dist directory not found")
        return
    
    # Copy resources folder
    if os.path.exists('resources'):
        dest = dist_dir / 'resources'
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree('resources', dest)
        print(f"  ✅ Copied resources/ folder")
    
    # Copy logo
    if os.path.exists('tkinter-isi/isi.png'):
        dest_dir = dist_dir / 'tkinter-isi'
        dest_dir.mkdir(exist_ok=True)
        shutil.copy2('tkinter-isi/isi.png', dest_dir / 'isi.png')
        print(f"  ✅ Copied logo file")
    
    # Copy database if exists
    if os.path.exists('planning.db'):
        shutil.copy2('planning.db', dist_dir / 'planning.db')
        print(f"  ✅ Copied planning.db")
    
    # Create output directory
    output_dir = dist_dir / 'output'
    output_dir.mkdir(exist_ok=True)
    print(f"  ✅ Created output/ directory")
    
    print("✅ Additional files copied!")

def create_readme():
    """Create README for the executable distribution"""
    print("\n📝 Creating distribution README...")
    
    readme_content = """# ISI Exam Scheduler - Executable Distribution

## 🚀 Quick Start

1. **Run the application:**
   - Double-click `ISI_Exam_Scheduler.exe`
   
2. **First time:**
   - Import your Excel files (Teachers, Slots, Preferences)
   - Generate planning
   - Export documents

## 📁 What's Included

- `ISI_Exam_Scheduler.exe` - Main application
- `resources/` - Document templates and sample Excel files
- `planning.db` - Database (created automatically if missing)
- `output/` - Generated files will be saved here

## ⚙️ System Requirements

- Windows 10/11 (64-bit)
- 2GB RAM minimum
- 500MB disk space

## 🆘 Troubleshooting

**If Windows Defender blocks the app:**
- Click "More info" → "Run anyway"

**If templates are not found:**
- Ensure the `resources/` folder is in the same directory as the .exe

**For support:** Contact ISI IT Department

---

**Version:** 1.0.0  
**Institut Supérieur d'Informatique (ISI), Tunisia**
"""
    
    dist_dir = Path('dist/ISI_Exam_Scheduler')
    if dist_dir.exists():
        readme_path = dist_dir / 'README.txt'
        readme_path.write_text(readme_content, encoding='utf-8')
        print(f"  ✅ Created README.txt")

def main():
    """Main build process"""
    print_header("ISI EXAM SCHEDULER - EXECUTABLE BUILD")
    
    # Step 1: Check PyInstaller
    if not check_pyinstaller():
        print("❌ PyInstaller installation failed")
        sys.exit(1)
    
    # Step 2: Clean previous builds
    clean_build()
    
    # Step 3: Build executable
    if not build_executable():
        print("❌ Build failed. Check errors above.")
        sys.exit(1)
    
    # Step 4: Copy additional files
    copy_additional_files()
    
    # Step 5: Create distribution README
    create_readme()
    
    # Success!
    print_header("✅ BUILD COMPLETE!")
    print()
    print("📦 Executable location: dist/ISI_Exam_Scheduler/")
    print("🚀 Run: dist/ISI_Exam_Scheduler/ISI_Exam_Scheduler.exe")
    print()
    print("💡 To distribute:")
    print("   1. ZIP the entire 'dist/ISI_Exam_Scheduler' folder")
    print("   2. Users should extract all files before running")
    print("   3. Ensure resources/ folder stays with the .exe")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Build failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
