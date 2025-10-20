"""
Enhanced data loader with detailed information for the improved scheduler
"""
import os
import pandas as pd
from datetime import datetime

def load_enhanced_data(teachers_file, voeux_file, slots_file):
    """
    Load all necessary data for the enhanced scheduler
    UPDATED for new file structure (October 2025)
    
    NEW FORMATS:
    - Enseignants.xlsx: columns ['nom_ens', 'prenom_ens', 'abrv_ens', 'email_ens', 
                                  'grade_code_ens', 'code_smartex_ens', 'participe_surveillance']
    - Souhaits.xlsx: columns ['Enseignant', 'Semestre', 'Session', 'Jour', 'Séances']
      * Séances format: "S1,S2,S3,S4" (comma-separated)
    - Repartitions.xlsx: columns ['dateExam', 'h_debut', 'h_fin', 'session', 
                                   'type ex', 'semestre', 'enseignant', 'cod_salle']
    
    Returns:
        - teachers_df: DataFrame with teacher information
        - quotas: dict {teacher_id: target_quota} - maximum quota each teacher should reach
        - voeux_by_id: dict {teacher_id: [(jour, seance)]}
        - voeux_timestamps: dict {teacher_id: [(jour, seance, timestamp)]} for FCFS
        - slots_df: DataFrame with slot details including responsible teachers
        - slot_info: list of dicts with slot metadata
        - all_teachers_lookup: dict with ALL teachers (including non-participating)
    """
    
    # Load ALL teachers first (for name lookup of responsible teachers)
    df_teachers = pd.read_excel(teachers_file)
    
    # Create a lookup dictionary for ALL teachers (including non-participants)
    all_teachers_lookup = {}
    if 'code_smartex_ens' in df_teachers.columns:
        for idx, row in df_teachers.iterrows():
            if pd.notna(row['code_smartex_ens']):
                teacher_id = int(row['code_smartex_ens'])
                all_teachers_lookup[teacher_id] = {
                    'nom_ens': row['nom_ens'],
                    'prenom_ens': row['prenom_ens'],
                    'email_ens': row.get('email_ens', 'N/A'),
                    'grade_code_ens': row.get('grade_code_ens', 'N/A'),
                    'participe_surveillance': row.get('participe_surveillance', False)
                }
    
    # Now filter to only teachers who participate in surveillance
    teachers = df_teachers[df_teachers['participe_surveillance'] == True].copy()
    
    # Use 'code_smartex_ens' as the teacher_id
    if 'code_smartex_ens' in teachers.columns:
        teachers = teachers[teachers['code_smartex_ens'].notna()].copy()
        teachers['teacher_id'] = teachers['code_smartex_ens'].astype(int)
        teachers = teachers.set_index('code_smartex_ens', drop=False)
        teachers.index = teachers.index.astype(int)
    else:
        teachers['teacher_id'] = teachers.index
    
    # UPDATED QUOTAS (October 2025)
    quota_per_grade = {
        'PR': 4,    # Professeur
        'MC': 4,    # Maître de conférences
        'MA': 7,    # Maître Assistant
        'AS': 8,    # Assistant
        'AC': 9,    # Assistant Contractuel
        'PTC': 9,   # Professeur Tronc Commun
        'PES': 9,   # Professeur d'enseignement secondaire
        'EX': 3,    # Expert
        'V': 4      # Vacataire
    }
    
    # Maximum quotas (target quotas to reach)
    min_quotas = {tid: quota_per_grade.get(row['grade_code_ens'], 5) 
                  for tid, row in teachers.iterrows()}
    
    # Load voeux - NEW FORMAT
    df_voeux = pd.read_excel(voeux_file)
    # NEW columns: ['Enseignant', 'Semestre', 'Session', 'Jour', 'Séances']
    # Séances is comma-separated: "S1,S2,S3,S4"
    
    df_voeux['timestamp_order'] = df_voeux.index
    
    voeux_by_id = {}
    voeux_timestamps = {}
    
    for tid, row in teachers.iterrows():
        # Try to match teacher by abbreviation or full name
        teacher_abbrev = row.get('abrv_ens', '').strip()
        teacher_full_name = f"{row['prenom_ens'].strip()} {row['nom_ens'].strip()}"
        
        # Match by abbreviation (preferred) or by enseignant column
        teacher_voeux = df_voeux[
            (df_voeux['Enseignant'].str.strip() == teacher_abbrev) |
            (df_voeux['Enseignant'].str.strip() == teacher_full_name)
        ]
        
        # Parse voeux: expand comma-separated séances
        voeux_list = []
        voeux_ts_list = []
        
        for _, v in teacher_voeux.iterrows():
            jour = v['Jour']
            seances_str = str(v['Séances'])
            timestamp = v['timestamp_order']
            
            # Split séances: "S1,S2,S3,S4" or "S4,S3" etc.
            seances = [s.strip() for s in seances_str.split(',') if s.strip()]
            
            for seance in seances:
                voeux_list.append((jour, seance))
                voeux_ts_list.append((jour, seance, timestamp))
        
        voeux_by_id[tid] = voeux_list
        voeux_timestamps[tid] = voeux_ts_list
    
    # Load slots - handle new time format
    df_slots = pd.read_excel(slots_file)
    # NEW columns: ['dateExam', 'h_debut', 'h_fin', 'session', 'type ex', 'semestre', 'enseignant', 'cod_salle']
    
    def parse_time(t):
        """Parse time from various formats including '30/12/1999 08:30:00'"""
        if isinstance(t, datetime):
            return t.strftime('%H:%M:%S')
        str_t = str(t)
        if ' ' in str_t:
            # Extract time part after space: "30/12/1999 08:30:00" -> "08:30:00"
            time_part = str_t.split(' ')[-1]
            return time_part
        return str_t
    
    df_slots['h_debut_str'] = df_slots['h_debut'].apply(parse_time)
    df_slots['h_fin_str'] = df_slots['h_fin'].apply(parse_time)
    
    # Parse dateExam - handle "DD/MM/YYYY" format
    def parse_date(d):
        if isinstance(d, datetime):
            return d.strftime('%Y-%m-%d')
        str_d = str(d)
        if '/' in str_d:
            # "27/10/2025" -> "2025-10-27"
            parts = str_d.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        return str_d
    
    df_slots['dateExam_parsed'] = df_slots['dateExam'].apply(parse_date)
    
    # Create slot mapping
    unique_dates = sorted(df_slots['dateExam_parsed'].unique())
    date_to_jour = {date: idx + 1 for idx, date in enumerate(unique_dates)}
    
    # Map times to seance numbers (1, 2, 3, 4)
    time_to_seance = {
        '08:30:00': '1',
        '10:30:00': '2', 
        '12:30:00': '3',
        '14:30:00': '4',
        '08:30': '1',
        '10:30': '2',
        '12:30': '3',
        '14:30': '4'
    }
    
    # Group by date and time to get unique exam sessions
    grouped = df_slots.groupby(['dateExam_parsed', 'h_debut_str'])
    
    slot_info = []
    for (date, time), group in grouped:
        num_salles = group['cod_salle'].nunique()
        
        jour = date_to_jour[date]
        seance = time_to_seance.get(time, time)  # Fallback to time if not found
        
        # Get responsible teacher(s) for this exam session
        responsible_teachers = group['enseignant'].dropna().unique().tolist()
        # Convert to int if possible
        responsible_teachers = [int(t) if pd.notna(t) and str(t).replace('.', '').isdigit() else t 
                               for t in responsible_teachers]
        
        slot_info.append({
            'slot_id': len(slot_info),
            'date': date,
            'time': time,
            'jour': jour,
            'seance': seance,
            'num_salles': num_salles,
            'num_surveillants': num_salles,  # Will be multiplied by supervisors_per_room in scheduler
            'responsible_teachers': responsible_teachers,
            'salles': group['cod_salle'].tolist()
        })
    
    return teachers, min_quotas, voeux_by_id, voeux_timestamps, df_slots, slot_info, all_teachers_lookup


if __name__ == '__main__':
    BASE_DIR = os.path.dirname(__file__)  # directory of data_loader.py

    teachers_file = os.path.join(BASE_DIR, "../resources/Enseignants.xlsx")
    voeux_file = os.path.join(BASE_DIR, "../resources/Souhaits.xlsx")
    slots_file = os.path.join(BASE_DIR, "../resources/Repartitions.xlsx")

    teachers, quotas, voeux, voeux_ts, slots_df, slot_info = load_enhanced_data(
        teachers_file,
        voeux_file,
        slots_file
    )
    
    # General summary
    print(f"Loaded {len(teachers)} teachers")
    print(f"Loaded {len(slot_info)} exam slots\n")
    
    # Detailed information about each file and processed data
    print("=== Teachers File Details ===")
    print("Sample of teacher data (first 5 rows):")
    print(teachers.head().to_string(index=False))
    print(f"Total eligible teachers: {len(teachers)}")
    print(f"Example quotas: {dict(list(quotas.items())[:5])}...\n")  # First 5 quotas
    
    print("=== Voeux File Details ===")
    print("Sample of voeux by ID (first 3 teachers with voeux):")
    for tid, prefs in list(voeux.items())[:3]:
        if prefs:  # Only print if voeux exist
            teacher_name = teachers.loc[tid, ['nom_ens', 'prenom_ens']].values
            print(f"Teacher {teacher_name[0]} {teacher_name[1]} (ID {tid}): {prefs}")
    print(f"Total teachers with voeux: {sum(1 for v in voeux.values() if v)}")
    print("Sample voeux with timestamps (first 3 entries):")
    for tid, prefs_ts in list(voeux_ts.items())[:3]:
        if prefs_ts:
            teacher_name = teachers.loc[tid, ['nom_ens', 'prenom_ens']].values
            print(f"Teacher {teacher_name[0]} {teacher_name[1]} (ID {tid}): {prefs_ts[:2]}...")  # First 2
    print("\n")
    
    print("=== Slots/Creneaux File Details ===")
    print("Sample of raw slots DataFrame (first 5 rows):")
    print(slots_df.head().to_string())
    print(f"Total rows in slots file: {len(slots_df)}")
    
    
    print("=== Processed Slot Info ===")
    print("Example slot info (first 3 slots):")
    for slot in slot_info[:3]:
        print(f"  Slot ID {slot['slot_id']}: {slot['date']} {slot['time']} "
              f"({slot['jour']}, {slot['seance']}) - {slot['num_salles']} salles, "
              f"need {slot['num_surveillants']} surveillants, "
              f"responsibles: {slot['responsible_teachers']}")
