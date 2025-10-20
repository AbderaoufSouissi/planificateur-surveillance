"""
Enhanced PDF generation for convocations and planning schedules
Generates individual convocation PDFs per teacher and daily/session-based planning PDFs
"""

import os
import pandas as pd
from datetime import datetime
from docxtpl import DocxTemplate
from collections import defaultdict
import platform
import subprocess
import sys


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Convert DOCX to PDF using platform-specific methods
    
    Args:
        docx_path: Path to source DOCX file
        pdf_path: Path to output PDF file
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        # Try using docx2pdf library first (Windows-optimized)
        if platform.system() == 'Windows':
            try:
                from docx2pdf import convert
                convert(docx_path, pdf_path)
                return True
            except ImportError:
                print("⚠️  docx2pdf not available, trying alternative methods...")
            except Exception as e:
                print(f"⚠️  docx2pdf conversion failed: {e}")
        
        # Fallback: Try LibreOffice/soffice command line (cross-platform)
        try:
            output_dir = os.path.dirname(pdf_path)
            if platform.system() == 'Windows':
                # Common LibreOffice paths on Windows
                soffice_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
                ]
            else:
                soffice_paths = ['/usr/bin/soffice', '/usr/local/bin/soffice']
            
            soffice_cmd = None
            for path in soffice_paths:
                if os.path.exists(path):
                    soffice_cmd = path
                    break
            
            if soffice_cmd:
                subprocess.run([
                    soffice_cmd,
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', output_dir,
                    docx_path
                ], check=True, capture_output=True)
                return True
            else:
                print("⚠️  LibreOffice not found, PDF conversion unavailable")
                return False
                
        except Exception as e:
            print(f"⚠️  LibreOffice conversion failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ PDF conversion error: {e}")
        return False


def generate_teacher_convocations(assignments, teachers_df, slot_info, session_info, output_base_dir):
    """
    Generate individual convocation PDF for each teacher
    
    Args:
        assignments: dict mapping teacher_id to their assigned slots
        teachers_df: DataFrame with teacher information
        slot_info: list of slot dictionaries
        session_info: dict with session details (nom, annee_academique, semestre)
        output_base_dir: base output directory path
    
    Returns:
        dict: Statistics about generated files
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "../resources/template de convocation de surveillance.docx")
    
    # Check if template exists
    if not os.path.exists(template_path):
        print(f"❌ Template not found: {template_path}")
        return {'success': False, 'error': 'Template not found'}
    
    # Create output directories
    convocations_dir = os.path.join(output_base_dir, "convocations")
    os.makedirs(convocations_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"📄 GENERATING TEACHER CONVOCATIONS")
    print(f"{'='*80}")
    print(f"Template: {template_path}")
    print(f"Output directory: {convocations_dir}\n")
    
    generated_files = []
    
    for tid, roles in assignments.items():
        try:
            teacher_row = teachers_df.loc[tid]
            teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
            grade = teacher_row['grade_code_ens']
            email = teacher_row.get('email_ens', 'N/A')
            
            # Prepare surveillance data
            surveillances_data = []
            for slot in sorted(roles['surveillant'], key=lambda x: (x['date'], x['time'])):
                # Format date nicely
                try:
                    date_obj = datetime.strptime(slot['date'], '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d/%m/%Y')
                except:
                    formatted_date = slot['date']
                
                # Format time
                try:
                    time_str = slot['time']
                    if len(time_str) == 8:  # HH:MM:SS
                        formatted_time = time_str[:5]  # HH:MM
                    else:
                        formatted_time = time_str
                except:
                    formatted_time = slot['time']
                
                surveillances_data.append({
                    'date': formatted_date,
                    'heure': formatted_time,
                    'duree': '1.5H',  # Default duration
                    'seance': slot['seance']
                })
            
            # Skip if no surveillances
            if not surveillances_data:
                continue
            
            # Load template
            doc = DocxTemplate(template_path)
            
            # Prepare context
            context = {
                'teacher_name': teacher_name,
                'grade': grade,
                'email': email,
                'session_name': session_info.get('nom', 'Session'),
                'annee_academique': session_info.get('annee_academique', '2024-2025'),
                'semestre': session_info.get('semestre', 'S1'),
                'surveillances': surveillances_data,
                'total_surveillances': len(surveillances_data)
            }
            
            # Render document
            doc.render(context)
            
            # Save as Word document (no PDF conversion)
            safe_name = teacher_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            docx_filename = f"convocation_{safe_name}.docx"
            
            docx_path = os.path.join(convocations_dir, docx_filename)
            
            doc.save(docx_path)
            generated_files.append(docx_path)
            print(f"✓ {teacher_name} → {docx_filename}")
                
        except Exception as e:
            print(f"❌ Error generating convocation for teacher {tid}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*80}")
    print(f"✓ CONVOCATION GENERATION COMPLETED")
    print(f"{'='*80}")
    print(f"Total convocations generated: {len(generated_files)}")
    print(f"Format: Word (.docx)")
    print(f"Location: {os.path.abspath(convocations_dir)}")
    print(f"{'='*80}\n")
    
    return {
        'success': True,
        'total_files': len(generated_files),
        'files': generated_files,
        'conversion_failures': [],
        'output_dir': convocations_dir
    }


def generate_daily_session_planning(assignments, teachers_df, slot_info, session_info, output_base_dir):
    """
    Generate daily and session-based planning PDFs
    Groups schedules by date and session (morning/afternoon)
    
    Args:
        assignments: dict mapping teacher_id to their assigned slots
        teachers_df: DataFrame with teacher information
        slot_info: list of slot dictionaries
        session_info: dict with session details
        output_base_dir: base output directory path
    
    Returns:
        dict: Statistics about generated files
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "../resources/template affectation des surveillance enseignants par jour.docx")
    
    # Check if template exists
    if not os.path.exists(template_path):
        print(f"❌ Template not found: {template_path}")
        return {'success': False, 'error': 'Template not found'}
    
    # Create output directories
    planning_dir = os.path.join(output_base_dir, "planning")
    os.makedirs(planning_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"📅 GENERATING DAILY/SESSION PLANNING")
    print(f"{'='*80}")
    print(f"Template: {template_path}")
    print(f"Output directory: {planning_dir}\n")
    
    # Group slots by date and session
    slots_by_date_session = defaultdict(list)
    for slot_idx, slot in enumerate(slot_info):
        date = slot['date']
        seance = slot['seance']
        slots_by_date_session[(date, seance)].append((slot_idx, slot))
    
    # Group assignments by slot
    assignments_by_slot = defaultdict(list)
    for tid, roles in assignments.items():
        teacher_row = teachers_df.loc[tid]
        teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
        
        for slot in roles['surveillant']:
            # Find matching slot index
            for slot_idx, slot_data in enumerate(slot_info):
                if (slot_data['date'] == slot['date'] and 
                    slot_data['time'] == slot['time'] and
                    slot_data['seance'] == slot['seance']):
                    
                    assignments_by_slot[slot_idx].append({
                        'enseignant': teacher_name,
                        'teacher_id': tid,
                        'grade': teacher_row['grade_code_ens'],
                        'email': teacher_row.get('email_ens', 'N/A')
                    })
                    break
    
    generated_files = []
    
    # Generate planning for each date/session combination
    for (date, seance), slot_list in sorted(slots_by_date_session.items()):
        try:
            # Format date
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
                date_safe = date_obj.strftime('%Y%m%d')
            except:
                # Date might be in DD/MM/YYYY format or other format
                formatted_date = date
                date_safe = date.replace('-', '').replace('/', '_')
            
            # Get all teachers assigned to any slot in this date/session
            teachers_for_session = []
            seen_teachers = set()
            
            for slot_idx, slot in slot_list:
                if slot_idx in assignments_by_slot:
                    for assignment in assignments_by_slot[slot_idx]:
                        teacher_id = assignment['teacher_id']
                        if teacher_id not in seen_teachers:
                            teachers_for_session.append({
                                'enseignant': assignment['enseignant'],
                                'grade': assignment['grade']
                            })
                            seen_teachers.add(teacher_id)
            
            # Skip if no teachers assigned
            if not teachers_for_session:
                continue
            
            # Get time from first slot
            first_slot = slot_list[0][1]
            time_str = first_slot['time']
            try:
                if len(time_str) == 8:
                    formatted_time = time_str[:5]
                else:
                    formatted_time = time_str
            except:
                formatted_time = time_str
            
            # Load template
            doc = DocxTemplate(template_path)
            
            # Prepare context
            context = {
                'semestre': session_info.get('semestre', 'S1'),
                'session': session_info.get('nom', 'Session Principale'),
                'annee_academique': session_info.get('annee_academique', '2024-2025'),
                'date': formatted_date,
                'seance': seance,
                'heure': formatted_time,
                'surveillances': teachers_for_session,
                'total_surveillants': len(teachers_for_session),
                'nb_salles': sum(s[1]['num_salles'] for s in slot_list)
            }
            
            # Render document
            doc.render(context)
            
            # Save as Word document (no PDF conversion)
            docx_filename = f"planning_{date_safe}_{seance}.docx"
            docx_path = os.path.join(planning_dir, docx_filename)

            doc.save(docx_path)
            generated_files.append(docx_path)
            print(f"✓ {formatted_date} {seance} → {docx_filename}")
                
        except Exception as e:
            print(f"❌ Error generating planning for {date} {seance}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*80}")
    print(f"✓ DAILY/SESSION PLANNING GENERATION COMPLETED")
    print(f"{'='*80}")
    print(f"Total planning files generated: {len(generated_files)}")
    print(f"Format: Word (.docx)")
    print(f"Location: {os.path.abspath(planning_dir)}")
    print(f"{'='*80}\n")
    
    return {
        'success': True,
        'total_files': len(generated_files),
        'files': generated_files,
        'conversion_failures': [],
        'output_dir': planning_dir
    }


def generate_all_pdfs(assignments, teachers_df, slot_info, session_info, output_base_dir):
    """
    Generate all PDF documents: convocations and planning
    
    Args:
        assignments: dict mapping teacher_id to their assigned slots
        teachers_df: DataFrame with teacher information
        slot_info: list of slot dictionaries
        session_info: dict with session details (nom, annee_academique, semestre)
        output_base_dir: base output directory path
    
    Returns:
        dict: Combined statistics from all generators
    """
    print(f"\n{'='*80}")
    print(f"🚀 STARTING PDF GENERATION FOR SESSION: {session_info.get('nom', 'Unknown')}")
    print(f"{'='*80}")
    print(f"Academic Year: {session_info.get('annee_academique', 'N/A')}")
    print(f"Semester: {session_info.get('semestre', 'N/A')}")
    print(f"Output directory: {output_base_dir}")
    print(f"{'='*80}\n")
    
    results = {}
    
    # Generate convocations
    results['convocations'] = generate_teacher_convocations(
        assignments, teachers_df, slot_info, session_info, output_base_dir
    )
    
    # Generate daily/session planning
    results['planning'] = generate_daily_session_planning(
        assignments, teachers_df, slot_info, session_info, output_base_dir
    )
    
    # Summary
    total_files = 0
    if results['convocations']['success']:
        total_files += results['convocations']['total_files']
    if results['planning']['success']:
        total_files += results['planning']['total_files']
    
    print(f"\n{'='*80}")
    print(f"✅ ALL PDF GENERATION COMPLETED")
    print(f"{'='*80}")
    print(f"Total files generated: {total_files}")
    print(f"  • Convocations: {results['convocations'].get('total_files', 0)}")
    print(f"  • Planning files: {results['planning'].get('total_files', 0)}")
    print(f"\nOutput location: {os.path.abspath(output_base_dir)}")
    print(f"{'='*80}\n")
    
    return results


if __name__ == '__main__':
    print("This module should be imported and used by exam_scheduler_db.py")
    print("Run exam_scheduler_db.py or the main application to generate PDFs")
