"""
Export simplified planning to structured Excel file
Supervisors only (no reserves) + Responsible teachers availability
"""
import pandas as pd
from collections import defaultdict
import os
from datetime import datetime


def export_enhanced_planning(assignments, teachers_df, slot_info, responsible_schedule, all_teachers_lookup=None, satisfaction_report=None, output_file='planning_enhanced.xlsx'):
    """
    Export planning to Excel with multiple views
    
    Sheets:
    1. Planning Détaillé - All assignments
    2. Résumé Enseignants - Summary by teacher
    3. Planning par Séance - Grid view by exam session
    4. Disponibilité Responsables - Responsible teachers availability
    5. Statistiques - Overall statistics
    
    Args:
        all_teachers_lookup: Dictionary mapping teacher IDs to their info (includes non-surveillance participants)
    """
    
    # ===== SHEET 1: Detailed Planning (SUPERVISORS ONLY) =====
    detailed_rows = []
    for tid, roles in assignments.items():
        # Safely get teacher info
        # tid can be string or int - convert to int for lookup
        try:
            tid_int = int(tid) if isinstance(tid, str) else tid
            teacher_row = teachers_df.loc[tid_int]
            teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
            grade = teacher_row['grade_code_ens']
            email = teacher_row.get('email_ens', '')
        except (KeyError, ValueError) as e:
            # Teacher not found in dataframe, skip
            print(f"⚠️  Teacher {tid} not found in teachers_df, skipping...")
            continue
        
        # Surveillant assignments
        for slot in roles['surveillant']:
            detailed_rows.append({
                'ID Enseignant': tid,
                'Nom Complet': teacher_name,
                'Grade': grade,
                'Email': email,
                'Date': slot['date'],
                'Heure': slot['time'],
                'Jour': slot['jour'],
                'Séance': slot['seance'],
                
            })
    
    df_detailed = pd.DataFrame(detailed_rows)
    df_detailed = df_detailed.sort_values(['Date', 'Heure', 'Nom Complet'])
    
    # ===== SHEET 2: Summary by Teacher (SUPERVISORS ONLY) =====
    summary_rows = []
    for tid, roles in assignments.items():
        # Safely get teacher info
        # tid can be string or int - convert to int for lookup
        try:
            tid_int = int(tid) if isinstance(tid, str) else tid
            teacher_row = teachers_df.loc[tid_int]
            teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
            grade = teacher_row['grade_code_ens']
            email = teacher_row.get('email_ens', '')
        except (KeyError, ValueError) as e:
            print(f"⚠️  Teacher {tid} not found in teachers_df for summary, skipping...")
            continue
        
        num_surveillant = len(roles['surveillant'])
        
        # Unique dates
        unique_dates = set(slot['date'] for slot in roles['surveillant'])
        
        # Get all dates sorted
        all_dates = sorted(set(slot['date'] for slot in roles['surveillant']))
        dates_str = ', '.join(str(d)[:10] for d in all_dates[:5])  # First 5 dates
        if len(all_dates) > 5:
            dates_str += '...'
        
        summary_rows.append({
            'ID Enseignant': tid,
            'Nom Complet': teacher_name,
            'Grade': grade,
            'Email': email,
            'Nombre de Surveillances': num_surveillant,
            'Jours Travaillés': len(unique_dates),
            'Dates': dates_str
        })
    
    df_summary = pd.DataFrame(summary_rows)
    df_summary = df_summary.sort_values('Nom Complet')
    
    # ===== SHEET 3: Planning Grid by Session (SUPERVISORS ONLY) =====
    sessions = []
    for slot in slot_info:
        # Get responsible teachers for this slot
        responsible_teachers = slot.get('responsible_teachers', [])
        responsible_names = []
        
        if responsible_teachers:
            for resp_id in responsible_teachers:
                teacher_found = False
                try:
                    resp_id_int = int(resp_id)
                    
                    # Try all_teachers_lookup first (includes ALL teachers)
                    if all_teachers_lookup and resp_id_int in all_teachers_lookup:
                        teacher_info = all_teachers_lookup[resp_id_int]
                        responsible_names.append(f"{teacher_info['nom_ens']} {teacher_info['prenom_ens']}")
                        teacher_found = True
                    # Try teachers_df (surveillance participants)
                    elif resp_id_int in teachers_df.index:
                        teacher_row = teachers_df.loc[resp_id_int]
                        responsible_names.append(f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}")
                        teacher_found = True
                    
                    # Last resort: query database directly
                    if not teacher_found and 'db' in locals():
                        # This shouldn't happen if all_teachers_lookup is properly populated
                        responsible_names.append(f"ID:{resp_id}")
                    elif not teacher_found:
                        responsible_names.append(f"ID:{resp_id}")
                        
                except (ValueError, KeyError, Exception) as e:
                    # If conversion or lookup fails
                    responsible_names.append(f"ID:{resp_id}")
        
        sessions.append({
            'Date': slot['date'],
            'Heure': slot['time'],
            'Séance': slot['seance'],
            'Jour': slot['jour'],
            'Salles': slot['num_salles'],
            'Surveillants Requis': slot['num_surveillants'],
            'Responsables Matière': ', '.join(responsible_names) if responsible_names else 'N/A'
        })
    
    df_sessions = pd.DataFrame(sessions)
    df_sessions = df_sessions.sort_values(['Date', 'Heure'])
    
    # Add assigned teachers to sessions
    session_assignments = defaultdict(list)
    
    for tid, roles in assignments.items():
        try:
            tid_int = int(tid) if isinstance(tid, str) else tid
            teacher_row = teachers_df.loc[tid_int]
            teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
        except (KeyError, ValueError):
            teacher_name = f"Teacher {tid}"  # Fallback name
        
        for slot in roles['surveillant']:
            key = (slot['date'], slot['time'])
            session_assignments[key].append(teacher_name)
    
    # Add to sessions dataframe
    df_sessions['Surveillants Assignés'] = df_sessions.apply(
        lambda row: len(session_assignments[(row['Date'], row['Heure'])]),
        axis=1
    )
    df_sessions['Noms Surveillants'] = df_sessions.apply(
        lambda row: '; '.join(session_assignments[(row['Date'], row['Heure'])]),
        axis=1
    )
    
    # ===== SHEET 4: Responsible Teachers Availability =====
    responsible_rows = []
    for entry in responsible_schedule:
        teacher_id = entry['teacher_id']
        teacher_name = entry['teacher_name']
        # Use the grade and email that were already looked up in exam_scheduler.py
        # (which includes ALL teachers, not just surveillance participants)
        grade = entry.get('grade', 'N/A')
        email = entry.get('email', 'N/A')
        
        responsible_rows.append({
            'ID Enseignant': teacher_id,
            'Nom Complet': teacher_name,
            'Grade': grade,
            'Email': email,
            'Date': entry['date'],
            'Heure': entry['time'],
            'Séance': entry['seance'],
            'Jour': entry['jour']
        })
    
    df_responsible = pd.DataFrame(responsible_rows)
    if not df_responsible.empty:
        df_responsible = df_responsible.sort_values(['Date', 'Heure', 'Nom Complet'])
    
    # ===== SHEET 5: Statistics =====
    # Overall stats
    total_teachers = len(assignments)
    total_surveillant = sum(len(a['surveillant']) for a in assignments.values())
    total_sessions = len(slot_info)
    total_responsible_slots = len(responsible_schedule) if responsible_schedule else 0
    
    stats_overview = pd.DataFrame([
        ['Nombre total d\'enseignants', total_teachers],
        ['Nombre total de séances d\'examen', total_sessions],
        ['Total assignations surveillant', total_surveillant],
        ['Créneaux disponibilité responsables', total_responsible_slots],
        ['Moyenne surveillances par enseignant', f"{total_surveillant/total_teachers:.2f}"]
    ], columns=['Statistique', 'Valeur'])
    
    # Stats by grade
    grade_stats = defaultdict(lambda: {'teachers': 0, 'surveillant': 0})
    for tid, roles in assignments.items():
        try:
            tid_int = int(tid) if isinstance(tid, str) else tid
            grade = teachers_df.loc[tid_int]['grade_code_ens']
        except (KeyError, ValueError):
            grade = 'Unknown'
        grade_stats[grade]['teachers'] += 1
        grade_stats[grade]['surveillant'] += len(roles['surveillant'])
    
    grade_rows = []
    for grade in sorted(grade_stats.keys()):
        stats = grade_stats[grade]
        avg = stats['surveillant'] / stats['teachers'] if stats['teachers'] > 0 else 0
        grade_rows.append({
            'Grade': grade,
            'Enseignants': stats['teachers'],
            'Surveillances': stats['surveillant'],
            'Moyenne/Enseignant': f"{avg:.1f}"
        })
    
    df_grade_stats = pd.DataFrame(grade_rows)
    
    # ===== Write to Excel =====
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_detailed.to_excel(writer, sheet_name='Planning Détaillé', index=False)
        df_summary.to_excel(writer, sheet_name='Résumé Enseignants', index=False)
        df_sessions.to_excel(writer, sheet_name='Planning par Séance', index=False)
        if not df_responsible.empty:
            df_responsible.to_excel(writer, sheet_name='Disponibilité Responsables', index=False)
        
        # Statistics sheet with two tables
        stats_overview.to_excel(writer, sheet_name='Statistiques', index=False, startrow=0)
        df_grade_stats.to_excel(writer, sheet_name='Statistiques', index=False, startrow=len(stats_overview) + 3)
        
        # ===== SHEET 6: Teacher Satisfaction Report =====
        if satisfaction_report and len(satisfaction_report) > 0:
            try:
                # Convert issues list to string for DataFrame compatibility
                satisfaction_data = []
                for teacher in satisfaction_report:
                    teacher_data = teacher.copy()
                    # Convert issues list to comma-separated string
                    if isinstance(teacher_data.get('issues'), list):
                        teacher_data['issues'] = '; '.join(teacher_data['issues'])
                    satisfaction_data.append(teacher_data)
                
                df_satisfaction = pd.DataFrame(satisfaction_data)
                
                # Reorder columns for better readability
                column_order = [
                    'name', 'grade', 'satisfaction_score', 'total_assignments', 'quota', 
                    'quota_excess', 'working_days', 'consecutive_days', 'isolated_days', 
                    'gap_days', 'schedule_pattern', 'issues'
                ]
                df_satisfaction = df_satisfaction[[col for col in column_order if col in df_satisfaction.columns]]
                
                # Rename columns for French display
                df_satisfaction.columns = [
                    'Enseignant', 'Grade', 'Score Satisfaction (/100)', 'Total Assignations', 
                    'Quota', 'Dépassement Quota', 'Jours Travaillés', 'Jours Consécutifs', 
                    'Jours Isolés', 'Jours Gaps', 'Pattern Horaire', 'Problèmes'
                ]
                
                # Sort by satisfaction score (worst first)
                df_satisfaction = df_satisfaction.sort_values('Score Satisfaction (/100)')
                
                df_satisfaction.to_excel(writer, sheet_name='Satisfaction Enseignants', index=False)
                print(f"✅ Satisfaction sheet exported with {len(satisfaction_data)} teachers")
            except Exception as e:
                print(f"⚠️  Warning: Could not export satisfaction sheet: {e}")
                import traceback
                traceback.print_exc()
        
        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 60)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    print(f"\n{'='*80}")
    print(f"✓ Planning exporté vers: {output_file}")
    print(f"{'='*80}")
    print(f"  Sheet 1: Planning Détaillé - Toutes les assignations surveillants")
    print(f"  Sheet 2: Résumé Enseignants - Vue par enseignant")
    print(f"  Sheet 3: Planning par Séance - Vue par séance d'examen")
    print(f"  Sheet 4: Disponibilité Responsables - Enseignants responsables à être disponibles")
    print(f"  Sheet 5: Statistiques - Statistiques globales")
    if satisfaction_report and len(satisfaction_report) > 0:
        print(f"  Sheet 6: Satisfaction Enseignants - Analyse de satisfaction (⚠️  Enseignants insatisfaits en haut)")
    print(f"{'='*80}\n")
    
    return output_file


def export_individual_teacher_schedules(assignments, teachers_df, slot_info, all_teachers_lookup=None, output_dir='teacher_schedules'):
    """
    Export individual schedule for each teacher as separate Excel files
    
    Parameters:
    -----------
    assignments : dict
        Dictionary mapping teacher_id to their assigned slots
    teachers_df : DataFrame
        DataFrame containing teacher information
    slot_info : list
        List of dictionaries containing slot metadata
    all_teachers_lookup : dict, optional
        Dictionary mapping teacher IDs to their info (includes non-surveillance participants)
    output_dir : str
        Directory to save individual teacher schedules (default: 'teacher_schedules')
    
    Returns:
    --------
    list of str : Paths to generated files
    """
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    generated_files = []
    
    print(f"\n{'='*80}")
    print(f"EXPORTING INDIVIDUAL TEACHER SCHEDULES")
    print(f"{'='*80}")
    print(f"Output directory: {os.path.abspath(output_dir)}\n")
    
    for tid, roles in assignments.items():
        try:
            tid_int = int(tid) if isinstance(tid, str) else tid
            teacher_row = teachers_df.loc[tid_int]
            teacher_name = f"{teacher_row['nom_ens']} {teacher_row['prenom_ens']}"
            grade = teacher_row['grade_code_ens']
        except (KeyError, ValueError):
            print(f"⚠️  Teacher {tid} not found, skipping individual export")
            continue
        
        # Skip if no assignments
        if not roles['surveillant']:
            continue
        
        # Prepare teacher's schedule data (SUPERVISORS ONLY)
        schedule_rows = []
        
        # Add surveillant assignments
        for slot in sorted(roles['surveillant'], key=lambda x: (x['date'], x['time'])):
            # Get responsible teachers for this slot
            responsible_teachers = slot.get('responsible_teachers', [])
            responsible_names = []
            for resp_id in responsible_teachers:
                try:
                    resp_id_int = int(resp_id)
                    # Use all_teachers_lookup if available (includes non-surveillance participants)
                    if all_teachers_lookup and resp_id_int in all_teachers_lookup:
                        teacher_info = all_teachers_lookup[resp_id_int]
                        responsible_names.append(f"{teacher_info['nom_ens']} {teacher_info['prenom_ens']}")
                    elif resp_id in teachers_df.index:
                        teacher_row_resp = teachers_df.loc[resp_id]
                        responsible_names.append(f"{teacher_row_resp['nom_ens']} {teacher_row_resp['prenom_ens']}")
                    else:
                        responsible_names.append(str(resp_id))
                except (ValueError, KeyError, Exception):
                    responsible_names.append(str(resp_id))
            
            schedule_rows.append({
                'Date': slot['date'],
                'Jour': slot['jour'],
                'Heure Début': slot['time'],
                'Séance': slot['seance'],
                
            })
        
        df_schedule = pd.DataFrame(schedule_rows)
        df_schedule = df_schedule.sort_values(['Date', 'Heure Début'])
        
        # Create summary section
        num_surveillant = len(roles['surveillant'])
        unique_dates = set(slot['date'] for slot in roles['surveillant'])
        
        summary_data = [
            ['EMPLOI DU TEMPS - SURVEILLANCE DES EXAMENS', ''],
            ['', ''],
            ['Enseignant', teacher_name],
            ['Grade', grade],
            ['ID', tid],
            ['Email', teacher_row.get('email_ens', 'N/A')],
            ['', ''],
            ['Total Surveillances', num_surveillant],
            ['Jours Travaillés', len(unique_dates)],
            ['', ''],
            ['Dates Concernées', ', '.join(sorted(str(d)[:10] for d in unique_dates))],
            ['', ''],
            ['', '']
        ]
        
        df_summary_header = pd.DataFrame(summary_data, columns=['Champ', 'Valeur'])
        
        # Generate filename (safe for filesystem)
        safe_name = teacher_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"{safe_name}_{grade}_{tid}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        # Write to Excel
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Summary section
            df_summary_header.to_excel(writer, sheet_name='Emploi du Temps', index=False, header=False, startrow=0)
            
            # Schedule table
            df_schedule.to_excel(writer, sheet_name='Emploi du Temps', index=False, startrow=len(summary_data) + 1)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Emploi du Temps']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 60)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Style the header
            from openpyxl.styles import Font, Alignment, PatternFill
            
            # Title
            title_cell = worksheet['A1']
            title_cell.font = Font(size=14, bold=True)
            title_cell.alignment = Alignment(horizontal='left')
            
            # Summary section
            for row in range(3, 13):
                cell = worksheet[f'A{row}']
                cell.font = Font(bold=True)
        
        generated_files.append(filepath)
        print(f"✓ {teacher_name} ({grade})")
    
    print(f"\n{'='*80}")
    print(f"✓ INDIVIDUAL SCHEDULES EXPORTED")
    print(f"{'='*80}")
    print(f"Total files generated: {len(generated_files)}")
    print(f"Location: {os.path.abspath(output_dir)}")
    print(f"{'='*80}\n")
    
    return generated_files


def export_all_formats(assignments, teachers_df, slot_info, responsible_schedule, all_teachers_lookup=None, satisfaction_report=None, base_output_path='planning'):
    """
    Export planning in all available formats:
    1. Main consolidated Excel file
    2. Individual teacher schedules (separate files)
    
    Parameters:
    -----------
    assignments : dict
        Dictionary mapping teacher_id to their assigned slots
    teachers_df : DataFrame
        DataFrame containing teacher information
    slot_info : list
        List of dictionaries containing slot metadata
    responsible_schedule : list
        List of responsible teacher availability slots
    all_teachers_lookup : dict, optional
        Dictionary mapping teacher IDs to their info (includes non-surveillance participants)
    base_output_path : str
        Base path for output files (without extension)
    
    Returns:
    --------
    dict : Dictionary with paths to all generated files
    """
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Calculate satisfaction report if not provided
    if satisfaction_report is None:
        # Try to calculate it
        try:
            from exam_scheduler import analyze_teacher_satisfaction
            from collections import defaultdict
            
            print("  ℹ️  Calculating satisfaction report...")
            
            # Prepare slots_by_date
            slots_by_date = defaultdict(list)
            for s_idx, slot in enumerate(slot_info):
                slots_by_date[slot['date']].append(s_idx)
            
            # Get min_quotas from teachers_df
            min_quotas = {}
            for tid in teachers_df.index:
                try:
                    tid_int = int(tid) if isinstance(tid, str) else tid
                    min_quotas[tid_int] = teachers_df.loc[tid].get('min_quota', 4)
                except (KeyError, ValueError):
                    min_quotas[tid if isinstance(tid, int) else int(tid)] = 4  # Default quota
            
            satisfaction_report = analyze_teacher_satisfaction(
                assignments, teachers_df, min_quotas, slot_info, slots_by_date
            )
            
            print(f"  ✓ Satisfaction report calculated: {len(satisfaction_report)} teachers")
            
        except Exception as e:
            print(f"  ⚠️  Could not calculate satisfaction report: {e}")
            import traceback
            traceback.print_exc()
            satisfaction_report = None
    
    # 1. Export main consolidated file
    main_file = f"{base_output_path}_consolidated_{timestamp}.xlsx"
    print(f"\n{'='*80}")
    print(f"STEP 1: Exporting Consolidated Planning")
    print(f"{'='*80}")
    export_enhanced_planning(assignments, teachers_df, slot_info, responsible_schedule, all_teachers_lookup, satisfaction_report, main_file)
    
    # 2. Export individual teacher schedules
    teacher_dir = f"{base_output_path}_teachers_{timestamp}"
    print(f"\n{'='*80}")
    print(f"STEP 2: Exporting Individual Teacher Schedules")
    print(f"{'='*80}")
    teacher_files = export_individual_teacher_schedules(assignments, teachers_df, slot_info, all_teachers_lookup, teacher_dir)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"✓ ALL EXPORTS COMPLETED")
    print(f"{'='*80}")
    print(f"\n📄 Files Generated:")
    print(f"  1. Consolidated planning: {os.path.abspath(main_file)}")
    print(f"  2. Individual schedules: {len(teacher_files)} files in {os.path.abspath(teacher_dir)}/")
    print(f"\n{'='*80}\n")
    
    return {
        'consolidated': main_file,
        'teacher_schedules_dir': teacher_dir,
        'teacher_schedules': teacher_files
    }


if __name__ == '__main__':
    import os
    from exam_scheduler import generate_enhanced_planning
    from datetime import datetime as dt
    
    # Get paths
    BASE_DIR = os.path.dirname(__file__)
    teachers_file = os.path.join(BASE_DIR, "../resources/Enseignants.xlsx")
    voeux_file = os.path.join(BASE_DIR, "../resources/Souhaits.xlsx")
    slots_file = os.path.join(BASE_DIR, "../resources/Repartitions.xlsx")
    
    print("Starting planning generation...")
    
    try:
        # Generate planning with enhanced parameters
        assignments, teachers_df, slot_info = generate_enhanced_planning(
            teachers_file,
            voeux_file,
            slots_file,
            supervisors_per_room=2,        # 2 supervisors per room
            reserve_percentage=0.15,        # 15% reserves
            require_subject_teacher=True,   # Enforce subject teacher presence
            voeux_weight=100,
            responsible_weight=50,
            compactness_weight=10,
            max_solve_time=60.0
        )
        
        # Export to Excel with absolute path
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.abspath(os.path.join(BASE_DIR, f'../planning_surveillance_{timestamp}.xlsx'))
        
        print(f"\n{'='*80}")
        print(f"Exporting to: {output_file}")
        print(f"{'='*80}\n")
        
        # Option 1: Export consolidated only
        # export_enhanced_planning(assignments, teachers_df, slot_info, output_file)
        
        # Option 2: Export everything (consolidated + individual teacher schedules)
        base_path = os.path.abspath(os.path.join(BASE_DIR, f'../planning_{timestamp}'))
        export_all_formats(assignments, teachers_df, slot_info, base_path)
        
        print(f"\n{'='*80}")
        print(f"✓ SUCCESS!")
        print(f"{'='*80}")
        print(f"\n� Check the output directory for all files")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"✗ ERROR OCCURRED")
        print(f"{'='*80}")
        print(f"\nError: {str(e)}\n")
        import traceback
        traceback.print_exc()
        print(f"\n{'='*80}\n")
