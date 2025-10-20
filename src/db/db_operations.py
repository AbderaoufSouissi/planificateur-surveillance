"""
Database operations for exam scheduler
Integrates the scheduling logic with the SQLite database
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any
import pandas as pd


class DatabaseManager:
    """Manages all database operations for the exam scheduling system"""
    
    def __init__(self, db_path="planning.db"):
        """Initialize database manager with path to SQLite database"""
        self.db_path = db_path
        self._ensure_database_exists()
        self._migrate_database()
    
    def _ensure_database_exists(self):
        """Ensure the database and tables exist"""
        import os
        if not os.path.exists(self.db_path):
            # Run db.py to create the database
            import sys
            db_script = os.path.join(os.path.dirname(__file__), 'db.py')
            if os.path.exists(db_script):
                exec(open(db_script).read())
    
    def _migrate_database(self):
        """Apply database migrations for schema updates"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if voeux_respected column exists in TeacherSatisfaction
            cursor.execute("PRAGMA table_info(TeacherSatisfaction)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Add missing columns if they don't exist
            if 'voeux_respected' not in columns:
                print("🔄 Migration: Adding voeux_respected column to TeacherSatisfaction...")
                cursor.execute("ALTER TABLE TeacherSatisfaction ADD COLUMN voeux_respected INTEGER DEFAULT 0")
                conn.commit()
                print("✅ Added voeux_respected column")
            
            if 'voeux_total' not in columns:
                print("🔄 Migration: Adding voeux_total column to TeacherSatisfaction...")
                cursor.execute("ALTER TABLE TeacherSatisfaction ADD COLUMN voeux_total INTEGER DEFAULT 0")
                conn.commit()
                print("✅ Added voeux_total column")
            
            if 'voeux_details' not in columns:
                print("🔄 Migration: Adding voeux_details column to TeacherSatisfaction...")
                cursor.execute("ALTER TABLE TeacherSatisfaction ADD COLUMN voeux_details TEXT")
                conn.commit()
                print("✅ Added voeux_details column")
            
            if 'gap_hours' not in columns:
                print("🔄 Migration: Adding gap_hours column to TeacherSatisfaction...")
                cursor.execute("ALTER TABLE TeacherSatisfaction ADD COLUMN gap_hours INTEGER DEFAULT 0")
                conn.commit()
                print("✅ Added gap_hours column")
                
        except Exception as e:
            print(f"⚠️ Migration warning: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_connection(self):
        """Get a database connection"""
        return sqlite3.connect(self.db_path)
    
    # ==================== SESSION MANAGEMENT ====================
    
    def create_session(self, nom: str, annee_academique: str, semestre: str) -> int:
        """
        Create a new scheduling session
        
        Args:
            nom: Session name (e.g., "Session Hiver 2024")
            annee_academique: Academic year (e.g., "2024-2025")
            semestre: Semester (e.g., "S1", "S2")
        
        Returns:
            session_id: ID of the created session
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Sessions (nom, annee_academique, semestre)
            VALUES (?, ?, ?)
        """, (nom, annee_academique, semestre))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def get_session(self, session_id: int) -> Dict:
        """Get session details by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, nom, annee_academique, semestre
            FROM Sessions
            WHERE id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'nom': row[1],
                'annee_academique': row[2],
                'semestre': row[3]
            }
        return None
    
    def list_sessions(self) -> List[Dict]:
        """List all sessions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, nom, annee_academique, semestre
            FROM Sessions
            ORDER BY id DESC
        """)
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row[0],
                'nom': row[1],
                'annee_academique': row[2],
                'semestre': row[3]
            })
        
        conn.close()
        return sessions
    
    def delete_session(self, session_id: int) -> bool:
        """
        Delete a session and all its related data (CASCADE delete)
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if successful, raises exception otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # SQLite has foreign keys with CASCADE DELETE configured
            # Deleting session will automatically delete related records
            cursor.execute("DELETE FROM Sessions WHERE id = ?", (session_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                raise ValueError(f"Session with id {session_id} not found")
            
            return True
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to delete session: {str(e)}")
        finally:
            conn.close()
    
    def get_session_stats(self, session_id: int) -> Dict:
        """
        Get statistics for a session
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with stats (teachers, slots, assignments, etc.)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Count teachers in this session
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Enseignants 
            WHERE session_id = ?
        """, (session_id,))
        stats['teachers'] = cursor.fetchone()[0] or 0
        
        # Count slots in this session
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Creneaux 
            WHERE session_id = ?
        """, (session_id,))
        stats['slots'] = cursor.fetchone()[0] or 0
        
        # Count total assignments for this session
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Affectations A
            JOIN Creneaux C ON A.creneau_id = C.id
            WHERE C.session_id = ?
        """, (session_id,))
        stats['assignments'] = cursor.fetchone()[0] or 0
        
        conn.close()
        return stats
    
    # ==================== CONFIGURATION MANAGEMENT ====================
    
    def save_config(self, session_id: int, surveillants_par_salle: int, 
                   quotas: Dict, poids_voeux: int = 100) -> int:
        """
        Save scheduling configuration for a session
        
        Args:
            session_id: Session ID
            surveillants_par_salle: Number of supervisors per room
            quotas: Dictionary of grade -> quota mappings
            poids_voeux: Weight for wishes/preferences
        
        Returns:
            config_id: ID of saved configuration
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        quotas_json = json.dumps(quotas)
        
        cursor.execute("""
            INSERT INTO Configs (session_id, surveillants_par_salle, quotas_json, poids_voeux)
            VALUES (?, ?, ?, ?)
        """, (session_id, surveillants_par_salle, quotas_json, poids_voeux))
        
        config_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return config_id
    
    def get_config(self, session_id: int) -> Dict:
        """Get configuration for a session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, surveillants_par_salle, quotas_json, poids_voeux
            FROM Configs
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'surveillants_par_salle': row[1],
                'quotas': json.loads(row[2]) if row[2] else {},
                'poids_voeux': row[3]
            }
        return None
    
    # ==================== TEACHER MANAGEMENT ====================
    
    def import_teachers_from_excel(self, session_id: int, teachers_df: pd.DataFrame) -> int:
        """
        Import teachers from DataFrame (loaded from Excel) into database
        
        Args:
            session_id: Session ID
            teachers_df: DataFrame with teacher information
        
        Returns:
            count: Number of teachers imported
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        count = 0
        for idx, row in teachers_df.iterrows():
            # Handle code_smartexam_ens - check both possible column names
            code_smartexam = None
            if pd.notna(row.get('code_smartex_ens')):
                code_smartexam = str(int(row.get('code_smartex_ens')))
            elif pd.notna(row.get('code_smartexam_ens')):
                code_smartexam = str(int(row.get('code_smartexam_ens')))
            else:
                code_smartexam = str(idx)
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO Enseignants 
                    (session_id, nom_ens, prenom_ens, email_ens, grade, 
                     code_smartexam_ens, participe_surveillance)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    row.get('nom_ens', ''),
                    row.get('prenom_ens', ''),
                    row.get('email_ens', ''),
                    row.get('grade_code_ens', ''),
                    code_smartexam,
                    bool(row.get('participe_surveillance', True))
                ))
                count += 1
            except Exception as e:
                print(f"Warning: Could not import teacher {row.get('nom_ens', 'Unknown')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        return count
    
    def get_teachers(self, session_id: int, participating_only: bool = True) -> pd.DataFrame:
        """
        Get teachers for a session as DataFrame
        
        Args:
            session_id: Session ID
            participating_only: If True, only return teachers who participate in surveillance
        
        Returns:
            DataFrame with teacher information including 'id' column
        """
        conn = self.get_connection()
        
        query = """
            SELECT id, nom_ens, prenom_ens, email_ens, grade as grade_code_ens, 
                   code_smartexam_ens, participe_surveillance
            FROM Enseignants
            WHERE session_id = ?
        """
        
        if participating_only:
            query += " AND participe_surveillance = 1"
        
        df = pd.read_sql_query(query, conn, params=(session_id,))
        conn.close()
        
        # Remove duplicates based on code_smartexam_ens (keep first occurrence)
        if not df.empty and 'code_smartexam_ens' in df.columns:
            df = df.drop_duplicates(subset=['code_smartexam_ens'], keep='first')
        
        return df
    
    # ==================== VOEUX (WISHES) MANAGEMENT ====================
    
    def import_voeux_from_excel(self, session_id: int, voeux_df: pd.DataFrame, 
                               teachers_df: pd.DataFrame) -> int:
        """
        Import wishes/preferences from DataFrame into database
        UPDATED for new format (October 2025)
        
        NEW FORMAT columns: ['Enseignant', 'Semestre', 'Session', 'Jour', 'Séances']
        where Séances is comma-separated: "S1,S2,S3,S4"
        
        Args:
            session_id: Session ID
            voeux_df: DataFrame with voeux information
            teachers_df: DataFrame with teacher information (for matching)
        
        Returns:
            count: Number of voeux imported
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create teacher mapping by abbreviation and full name
        teacher_codes = {}
        for idx, row in teachers_df.iterrows():
            code = row.get('code_smartex_ens')
            if pd.notna(code):
                teacher_id = int(code)
                # Map by abbreviation
                abbrev = str(row.get('abrv_ens', '')).strip()
                if abbrev:
                    teacher_codes[abbrev] = teacher_id
                # Also map by full name
                full_name = f"{row.get('prenom_ens', '').strip()} {row.get('nom_ens', '').strip()}"
                teacher_codes[full_name] = teacher_id
        
        count = 0
        for idx, row in voeux_df.iterrows():
            enseignant = str(row.get('Enseignant', '')).strip()
            jour = row.get('Jour', '')
            seances_str = str(row.get('Séances', ''))
            
            # Find teacher ID
            if enseignant in teacher_codes:
                enseignant_id = teacher_codes[enseignant]
                
                # Parse comma-separated séances: "S1,S2,S3,S4" -> ['S1', 'S2', 'S3', 'S4']
                seances = [s.strip() for s in seances_str.split(',') if s.strip()]
                
                # Insert each (jour, seance) pair
                for seance in seances:
                    try:
                        cursor.execute("""
                            INSERT INTO Voeux (session_id, enseignant_id, jour, seance, ordre_timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            session_id,
                            enseignant_id,
                            jour,
                            seance,
                            idx  # Use row index as timestamp order
                        ))
                        count += 1
                    except Exception as e:
                        print(f"Warning: Could not import voeu for {enseignant}, {jour}, {seance}: {e}")
        
        conn.commit()
        
        # IMPORTANT: Deduplicate voeux after import
        # This fixes the common issue of duplicate entries from Excel imports
        duplicates_removed = self._deduplicate_voeux_for_session(session_id, conn)
        if duplicates_removed > 0:
            print(f"⚠️  Removed {duplicates_removed} duplicate voeux entries")
        
        conn.close()
        
        return count
    
    def _deduplicate_voeux_for_session(self, session_id: int, conn=None) -> int:
        """
        Remove duplicate voeux entries for a session.
        Keeps only one entry per (enseignant_id, jour, seance) combination.
        
        Args:
            session_id: Session ID to deduplicate
            conn: Optional existing connection (to use within a transaction)
        
        Returns:
            Number of duplicate entries removed
        """
        close_conn = False
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        
        cursor = conn.cursor()
        
        # Create temporary table with unique voeux (keep the earliest one by id)
        cursor.execute("""
            CREATE TEMPORARY TABLE IF NOT EXISTS VoeuxUnique AS
            SELECT MIN(v.id) as id
            FROM Voeux v
            JOIN Enseignants t ON v.enseignant_id = t.code_smartexam_ens
            WHERE v.session_id = ? AND t.session_id = ?
            GROUP BY v.enseignant_id, v.jour, v.seance
        """, (session_id, session_id))
        
        # Count duplicates before deletion
        cursor.execute("""
            SELECT COUNT(*)
            FROM Voeux v
            JOIN Enseignants t ON v.enseignant_id = t.code_smartexam_ens
            WHERE v.session_id = ? AND t.session_id = ?
              AND v.id NOT IN (SELECT id FROM VoeuxUnique)
        """, (session_id, session_id))
        
        duplicates_count = cursor.fetchone()[0]
        
        # Delete duplicate voeux
        if duplicates_count > 0:
            cursor.execute("""
                DELETE FROM Voeux
                WHERE id IN (
                    SELECT v.id
                    FROM Voeux v
                    JOIN Enseignants t ON v.enseignant_id = t.code_smartexam_ens
                    WHERE v.session_id = ? AND t.session_id = ?
                      AND v.id NOT IN (SELECT id FROM VoeuxUnique)
                )
            """, (session_id, session_id))
            
            conn.commit()
        
        # Drop temporary table
        cursor.execute("DROP TABLE IF EXISTS VoeuxUnique")
        
        if close_conn:
            conn.close()
        
        return duplicates_count
    
    def deduplicate_voeux(self, session_id: int) -> int:
        """
        Public method to deduplicate voeux for a session.
        Can be called manually or before scheduling.
        
        Returns:
            Number of duplicates removed
        """
        return self._deduplicate_voeux_for_session(session_id)
    
    def get_voeux(self, session_id: int) -> Dict[int, List[Tuple[str, str]]]:
        """
        Get all voeux for a session, organized by teacher ID
        
        Returns:
            Dictionary mapping teacher_id -> [(jour, seance), ...]
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT V.enseignant_id, V.jour, V.seance
            FROM Voeux V
            JOIN Enseignants E ON V.enseignant_id = E.code_smartexam_ens
            WHERE V.session_id = ? AND E.session_id = ?
            ORDER BY V.enseignant_id, V.ordre_timestamp
        """, (session_id, session_id))
        
        voeux_by_id = {}
        for row in cursor.fetchall():
            enseignant_id = str(row[0])  # Convert to string to match code_smartexam_ens format
            jour_raw = row[1]
            seance = row[2]
            
            # Convert jour to int if it's a number (for day number format)
            try:
                jour = int(jour_raw)
            except (ValueError, TypeError):
                jour = jour_raw  # Keep as string if not a number (backward compatibility)
            
            if enseignant_id not in voeux_by_id:
                voeux_by_id[enseignant_id] = []
            voeux_by_id[enseignant_id].append((jour, seance))
        
        conn.close()
        return voeux_by_id
    
    # ==================== SLOTS (CRENEAUX) MANAGEMENT ====================
    
    def import_slots_from_excel(self, session_id: int, slots_df: pd.DataFrame, 
                               slot_info: List[Dict]) -> int:
        """
        Import exam slots from processed slot_info into database
        
        Args:
            session_id: Session ID
            slots_df: Raw slots DataFrame
            slot_info: Processed slot information
        
        Returns:
            count: Number of slots imported
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # First, check for duplicates and deduplicate slot_info by (date, time)
        seen = set()
        unique_slots = []
        for slot in slot_info:
            key = (str(slot['date']), slot['time'])
            if key not in seen:
                seen.add(key)
                unique_slots.append(slot)
        
        # Check if slots already exist in database to avoid re-importing
        cursor.execute("""
            SELECT DISTINCT date_examen, heure_debut
            FROM Creneaux
            WHERE session_id = ?
        """, (session_id,))
        existing_slots = set((row[0], row[1]) for row in cursor.fetchall())
        
        count = 0
        for slot in unique_slots:
            date_str = str(slot['date'])
            time_str = slot['time']
            
            # Skip if already exists
            if (date_str, time_str) in existing_slots:
                continue
            
            # Get responsible teacher code (first one if multiple)
            code_responsable = None
            if slot.get('responsible_teachers'):
                responsible_list = slot['responsible_teachers']
                if responsible_list:
                    code_responsable = str(responsible_list[0])
            
            cursor.execute("""
                INSERT INTO Creneaux 
                (session_id, date_examen, heure_debut, nb_surveillants, code_responsable)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                date_str,
                time_str,
                slot['num_surveillants'],
                code_responsable
            ))
            count += 1
        
        conn.commit()
        conn.close()
        
        return count
    
    def get_slots(self, session_id: int) -> List[Dict]:
        """Get all slots for a session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, date_examen, heure_debut, nb_surveillants, code_responsable
            FROM Creneaux
            WHERE session_id = ?
            ORDER BY date_examen, heure_debut
        """, (session_id,))
        
        slots = []
        for row in cursor.fetchall():
            slots.append({
                'slot_id': row[0],  # Add slot_id for compatibility
                'id': row[0],
                'date_examen': row[1],
                'heure_debut': row[2],
                'nb_surveillants': row[3],
                'code_responsable': row[4],
                'salle': '',  # Not in current schema
                'matiere': '',  # Not in current schema
            })
        
        conn.close()
        return slots
    
    # ==================== ASSIGNMENTS (AFFECTATIONS) MANAGEMENT ====================
    
    def save_assignments(self, session_id: int, assignments: Dict, 
                        slot_info: List[Dict], teachers_df: pd.DataFrame) -> int:
        """
        Save scheduling results to database
        
        Args:
            session_id: Session ID
            assignments: Assignment dictionary from scheduler
            slot_info: Slot information from scheduler
            teachers_df: Teacher DataFrame
        
        Returns:
            count: Number of assignments saved
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build mapping from (date, time) to list of creneau_ids
        # This handles cases where database has duplicate slots
        cursor.execute("""
            SELECT id, date_examen, heure_debut
            FROM Creneaux
            WHERE session_id = ?
            ORDER BY date_examen, heure_debut
        """, (session_id,))
        
        # Group creneaux by (date, time)
        from collections import defaultdict
        datetime_to_creneaux = defaultdict(list)
        for row in cursor.fetchall():
            creneau_id = row[0]
            date_examen = row[1]
            heure_debut = row[2]
            datetime_to_creneaux[(date_examen, heure_debut)].append(creneau_id)
        
        # Build slot_id to creneau_id mapping from slot_info
        slot_to_creneau = {}
        for slot in slot_info:
            slot_id = slot.get('slot_id')
            # First try to get creneau_id directly from slot_info
            creneau_id = slot.get('creneau_id')
            
            if creneau_id:
                # Direct mapping from slot_info
                slot_to_creneau[slot_id] = creneau_id
            elif slot_id is not None:
                # Fallback: try to match by date/time
                date = slot.get('date')
                time = slot.get('time')
                if date and time:
                    creneaux_list = datetime_to_creneaux.get((date, time), [])
                    if creneaux_list:
                        slot_to_creneau[slot_id] = creneaux_list[0]
        
        # Clear existing assignments for this session
        cursor.execute("""
            DELETE FROM Affectations 
            WHERE creneau_id IN (
                SELECT id FROM Creneaux WHERE session_id = ?
            )
        """, (session_id,))
        
        count = 0
        for teacher_id, roles in assignments.items():
            for slot_data in roles.get('surveillant', []):
                slot_id = slot_data.get('slot_id')
                creneau_id = slot_to_creneau.get(slot_id)
                
                if creneau_id:
                    cursor.execute("""
                        INSERT INTO Affectations (enseignant_id, creneau_id, role, date_affectation)
                        VALUES (?, ?, ?, ?)
                    """, (
                        teacher_id,
                        creneau_id,
                        'Surveillant',
                        datetime.now().isoformat()
                    ))
                    count += 1
        
        conn.commit()
        conn.close()
        
        return count
    
    def get_assignments(self, session_id: int) -> List[Dict]:
        """
        Get all assignments for a session
        
        Returns:
            List of assignment dictionaries
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                A.id,
                A.enseignant_id,
                E.nom_ens,
                E.prenom_ens,
                E.grade,
                C.date_examen,
                C.heure_debut,
                A.role,
                A.date_affectation
            FROM Affectations A
            JOIN Creneaux C ON A.creneau_id = C.id
            JOIN Enseignants E ON CAST(A.enseignant_id AS INTEGER) = E.id AND E.session_id = ?
            WHERE C.session_id = ?
            ORDER BY C.date_examen, C.heure_debut, E.nom_ens
        """, (session_id, session_id))
        
        assignments = []
        for row in cursor.fetchall():
            assignments.append({
                'id': row[0],
                'enseignant_id': row[1],
                'nom_ens': row[2],
                'prenom_ens': row[3],
                'grade': row[4],
                'date_examen': row[5],
                'heure_debut': row[6],
                'role': row[7],
                'date_affectation': row[8]
            })
        
        conn.close()
        return assignments
    
    def update_session_assignments(self, session_id: int, schedule_data: Dict, 
                                   teacher_name_to_id_map: Dict = None) -> int:
        """
        Update all assignments for a session based on schedule_data from edit screen.
        This completely replaces existing assignments with the current state.
        
        Args:
            session_id: Session ID to update
            schedule_data: Schedule data dict {date: {seance: [teachers]}}
            teacher_name_to_id_map: Optional mapping of teacher names to IDs
                                   If not provided, will be built from database
        
        Returns:
            count: Number of assignments saved
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Build teacher name to ID mapping if not provided
            if teacher_name_to_id_map is None:
                cursor.execute("""
                    SELECT id, nom_ens, prenom_ens
                    FROM Enseignants
                    WHERE session_id = ?
                """, (session_id,))
                
                teacher_name_to_id_map = {}
                for row in cursor.fetchall():
                    teacher_id = row[0]
                    nom = row[1].strip() if row[1] else ''
                    prenom = row[2].strip() if row[2] else ''
                    
                    # Map BOTH name formats to handle different sources
                    # Format 1: "FirstName LastName" (from database load)
                    full_name_format1 = f"{prenom} {nom}" if prenom else nom
                    teacher_name_to_id_map[full_name_format1] = teacher_id
                    
                    # Format 2: "LastName FirstName" (from Excel load)
                    full_name_format2 = f"{nom} {prenom}" if prenom else nom
                    teacher_name_to_id_map[full_name_format2] = teacher_id
                    
                    # Also map last name only for partial matches
                    teacher_name_to_id_map[nom] = teacher_id
            
            # Build mapping of (date, seance/heure) to creneau_id
            cursor.execute("""
                SELECT id, date_examen, heure_debut
                FROM Creneaux
                WHERE session_id = ?
            """, (session_id,))
            
            datetime_to_creneau = {}
            for row in cursor.fetchall():
                creneau_id = row[0]
                date = row[1]
                heure = row[2]
                # Map both by exact seance time and by date+heure
                datetime_to_creneau[(date, heure)] = creneau_id
                # Also allow matching by time only if date matches
                datetime_to_creneau[(date, str(heure))] = creneau_id
            
            # Delete all existing assignments for this session
            cursor.execute("""
                DELETE FROM Affectations 
                WHERE creneau_id IN (
                    SELECT id FROM Creneaux WHERE session_id = ?
                )
            """, (session_id,))
            
            # Insert new assignments from schedule_data
            count = 0
            missing_creneaux = set()
            missing_teachers = set()
            
            for date, seances in schedule_data.items():
                for seance, teachers in seances.items():
                    # Find matching creneau_id
                    creneau_id = datetime_to_creneau.get((date, seance))
                    
                    if not creneau_id:
                        missing_creneaux.add(f"{date} {seance}")
                        continue
                    
                    # Process each teacher assigned to this slot
                    for teacher_entry in teachers:
                        # Extract teacher name from dict or string
                        if isinstance(teacher_entry, dict):
                            teacher_name = teacher_entry.get('teacher', '')
                        else:
                            teacher_name = str(teacher_entry)
                        
                        teacher_name = teacher_name.strip()
                        if not teacher_name:
                            continue
                        
                        # Find teacher ID
                        teacher_id = teacher_name_to_id_map.get(teacher_name)
                        
                        if not teacher_id:
                            missing_teachers.add(teacher_name)
                            continue
                        
                        # Insert assignment
                        cursor.execute("""
                            INSERT INTO Affectations (enseignant_id, creneau_id, role, date_affectation)
                            VALUES (?, ?, ?, ?)
                        """, (
                            teacher_id,
                            creneau_id,
                            'Surveillant',
                            datetime.now().isoformat()
                        ))
                        count += 1
            
            conn.commit()
            
            # Log warnings if there were issues
            if missing_creneaux:
                print(f"⚠️  Warning: {len(missing_creneaux)} slots not found in database:")
                for mc in list(missing_creneaux)[:5]:  # Show first 5
                    print(f"    - {mc}")
            
            if missing_teachers:
                print(f"⚠️  Warning: {len(missing_teachers)} teachers not found in database:")
                for mt in list(missing_teachers)[:5]:  # Show first 5
                    print(f"    - {mt}")
            
            return count
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update assignments: {str(e)}")
        finally:
            conn.close()
    
    # ==================== AUDIT TRAIL ====================
    
    def log_audit(self, session_id: int, affectation_id: int = None, 
                 action: str = '', raison: str = ''):
        """Log an audit entry"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Audits (session_id, affectation_id, action, raison, cree_le)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, affectation_id, action, raison, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    # ==================== EXPORT MANAGEMENT ====================
    
    def log_export(self, session_id: int, export_type: str, file_path: str) -> int:
        """Log an export operation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Exports (session_id, type, chemin_fichier, cree_le)
            VALUES (?, ?, ?, ?)
        """, (session_id, export_type, file_path, datetime.now().isoformat()))
        
        export_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return export_id
    
    def get_exports(self, session_id: int) -> List[Dict]:
        """Get all exports for a session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, type, chemin_fichier, cree_le
            FROM Exports
            WHERE session_id = ?
            ORDER BY cree_le DESC
        """, (session_id,))
        
        exports = []
        for row in cursor.fetchall():
            exports.append({
                'id': row[0],
                'type': row[1],
                'chemin_fichier': row[2],
                'cree_le': row[3]
            })
        
        conn.close()
        return exports
    
    # ==================== DOCUMENT GENERATION HELPERS ====================
    
    def get_teacher_assignments(self, session_id: int, teacher_name: str) -> List[Dict]:
        """
        Get all assignments for a specific teacher
        
        Args:
            session_id: Session ID
            teacher_name: Teacher's full name
            
        Returns:
            List of assignment dictionaries with date, time, duration info
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                C.date_examen,
                C.heure_debut,
                C.nb_surveillants,
                C.id
            FROM Affectations A
            JOIN Creneaux C ON A.creneau_id = C.id
            JOIN Enseignants E ON A.enseignant_id = E.id AND E.session_id = ?
            WHERE C.session_id = ? 
            AND (E.nom_ens || ' ' || E.prenom_ens = ? OR E.nom_ens = ?)
            ORDER BY C.date_examen, C.heure_debut
        """, (session_id, session_id, teacher_name, teacher_name))
        
        assignments = []
        for row in cursor.fetchall():
            # Default duration is 1.5 hours
            duree_str = "1.5H"
            
            assignments.append({
                'date': row[0],
                'heure': row[1],
                'duree': duree_str,
                'salle': '',  # Not in current schema
                'examen': '',  # Not in current schema
                'niveau': ''  # Not in current schema
            })
        
        conn.close()
        return assignments
    
    def get_slot_assignments(self, session_id: int, slot_id: int) -> List[Dict]:
        """
        Get all assignments for a specific slot
        
        Args:
            session_id: Session ID
            slot_id: Slot ID
            
        Returns:
            List of assignment dictionaries with teacher info
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                E.nom_ens,
                E.prenom_ens,
                E.grade
            FROM Affectations A
            JOIN Enseignants E ON A.enseignant_id = E.id AND E.session_id = ?
            WHERE A.creneau_id = ?
            ORDER BY E.nom_ens
        """, (session_id, slot_id))
        
        assignments = []
        for row in cursor.fetchall():
            full_name = f"{row[0]} {row[1]}" if row[1] else row[0]
            assignments.append({
                'nom_enseignant': full_name,
                'grade': row[2] if row[2] else '',
                'quota': ''  # Quota is in Configs.quotas_json, not in Enseignants
            })
        
        conn.close()
        return assignments
    
    def get_session_info(self, session_id: int) -> Dict:
        """
        Get session information
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session information
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT nom, annee_academique, semestre
            FROM Sessions
            WHERE id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'nom': row[0],
                'annee_academique': row[1],
                'semestre': row[2],
                'type_session': 'Principale'  # Default, could be in DB
            }
        return {}
    
    # ==================== END DOCUMENT GENERATION HELPERS ====================

    
    # ==================== SATISFACTION MANAGEMENT ====================
    
    def save_satisfaction_report(self, session_id: int, satisfaction_report: List[Dict]) -> int:
        """
        Save teacher satisfaction analysis to database
        
        Args:
            session_id: Session ID
            satisfaction_report: List of satisfaction dictionaries from analyze_teacher_satisfaction
        
        Returns:
            count: Number of records saved
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete existing satisfaction data for this session
            cursor.execute('DELETE FROM TeacherSatisfaction WHERE session_id = ?', (session_id,))
            
            # Insert new satisfaction data
            count = 0
            for teacher in satisfaction_report:
                cursor.execute('''
                    INSERT INTO TeacherSatisfaction 
                    (session_id, teacher_id, name, grade, satisfaction_score, 
                     total_assignments, quota, quota_excess, working_days,
                     consecutive_days, isolated_days, gap_days, 
                     voeux_respected, voeux_total, voeux_details, gap_hours,
                     schedule_pattern, issues_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    teacher.get('teacher_id', ''),
                    teacher['name'],
                    teacher['grade'],
                    teacher['satisfaction_score'],
                    teacher['total_assignments'],
                    teacher['quota'],
                    teacher['quota_excess'],
                    teacher['working_days'],
                    teacher.get('consecutive_days', 0),
                    teacher['isolated_days'],
                    teacher['gap_days'],
                    teacher.get('voeux_respected', 0),
                    teacher.get('voeux_total', 0),
                    teacher.get('voeux_details', ''),
                    teacher.get('gap_hours', 0),
                    teacher['schedule_pattern'],
                    json.dumps(teacher['issues'])
                ))
                count += 1
            
            conn.commit()
            return count
        except Exception as e:
            conn.rollback()
            print(f"Error saving satisfaction report: {e}")
            raise
        finally:
            conn.close()
    
    def get_satisfaction_report(self, session_id: int) -> List[Dict]:
        """
        Load teacher satisfaction analysis from database
        
        Args:
            session_id: Session ID
        
        Returns:
            satisfaction_report: List of satisfaction dictionaries
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT teacher_id, name, grade, satisfaction_score, 
                       total_assignments, quota, quota_excess, working_days,
                       consecutive_days, isolated_days, gap_days, 
                       voeux_respected, voeux_total, voeux_details, gap_hours,
                       schedule_pattern, issues_json
                FROM TeacherSatisfaction 
                WHERE session_id = ?
                ORDER BY satisfaction_score ASC
            ''', (session_id,))
            
            rows = cursor.fetchall()
            
            satisfaction_report = []
            for row in rows:
                teacher = {
                    'teacher_id': row[0],
                    'name': row[1],
                    'grade': row[2],
                    'satisfaction_score': row[3],
                    'total_assignments': row[4],
                    'quota': row[5],
                    'quota_excess': row[6],
                    'working_days': row[7],
                    'consecutive_days': row[8],
                    'isolated_days': row[9],
                    'gap_days': row[10],
                    'voeux_respected': row[11],
                    'voeux_total': row[12],
                    'voeux_details': row[13],
                    'gap_hours': row[14],
                    'schedule_pattern': row[15],
                    'issues': json.loads(row[16]) if row[16] else []
                }
                satisfaction_report.append(teacher)
            
            return satisfaction_report
        except Exception as e:
            print(f"Error loading satisfaction report: {e}")
            return []
        finally:
            conn.close()
    
    def get_satisfaction_stats(self, session_id: int) -> Dict:
        """
        Get satisfaction statistics for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            stats: Dictionary with overall satisfaction statistics
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    AVG(satisfaction_score) as avg_score,
                    COUNT(*) as total_teachers,
                    SUM(CASE WHEN satisfaction_score >= 80 THEN 1 ELSE 0 END) as highly_satisfied,
                    SUM(CASE WHEN satisfaction_score >= 60 AND satisfaction_score < 80 THEN 1 ELSE 0 END) as satisfied,
                    SUM(CASE WHEN satisfaction_score >= 40 AND satisfaction_score < 60 THEN 1 ELSE 0 END) as neutral,
                    SUM(CASE WHEN satisfaction_score < 40 THEN 1 ELSE 0 END) as dissatisfied
                FROM TeacherSatisfaction 
                WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            
            if row and row[1] > 0:  # If we have teachers
                return {
                    'avg_score': round(row[0], 1) if row[0] else 0,
                    'total_teachers': row[1],
                    'highly_satisfied': row[2],
                    'satisfied': row[3],
                    'neutral': row[4],
                    'dissatisfied': row[5]
                }
            else:
                return {
                    'avg_score': 0,
                    'total_teachers': 0,
                    'highly_satisfied': 0,
                    'satisfied': 0,
                    'neutral': 0,
                    'dissatisfied': 0
                }
        except Exception as e:
            print(f"Error getting satisfaction stats: {e}")
            return {
                'avg_score': 0,
                'total_teachers': 0,
                'highly_satisfied': 0,
                'satisfied': 0,
                'neutral': 0,
                'dissatisfied': 0
            }
        finally:
            conn.close()
    
    def compute_satisfaction_from_db(self, session_id: int) -> int:
        """
        Compute and save satisfaction data from existing assignments in database.
        NEW SCORING SYSTEM (Optimized for Performance):
        1. Voeux Respected (40 pts)
        2. Isolated Days (25 pts)
        3. Schedule Compactness (20 pts)
        4. Gap Between Hours (15 pts)
        
        Args:
            session_id: Session ID to compute satisfaction for
        
        Returns:
            Number of teacher satisfaction records saved
        """
        from collections import defaultdict
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get configuration with quotas
            config = self.get_config(session_id)
            if not config:
                print(f"No config found for session {session_id}")
                return 0
            
            quotas = config.get('quotas', {})
            
            # Get teachers
            teachers_df = self.get_teachers(session_id, participating_only=True)
            if teachers_df.empty:
                print(f"No teachers found for session {session_id}")
                return 0
            
            # Build teacher lookup by id and code
            teacher_lookup = {}
            teacher_id_to_code = {}
            for idx, row in teachers_df.iterrows():
                teacher_id = row['id']
                code = row.get('code_smartexam_ens', '')
                teacher_lookup[teacher_id] = {
                    'code': code,
                    'nom': row.get('nom_ens', ''),
                    'prenom': row.get('prenom_ens', ''),
                    'grade': row.get('grade_code_ens', '')
                }
                teacher_id_to_code[teacher_id] = code
            
            # Get voeux for this session
            voeux_by_teacher = self.get_voeux(session_id)
            
            # Get all assignments with slot information
            cursor.execute("""
                SELECT 
                    E.id,
                    E.code_smartexam_ens,
                    E.nom_ens,
                    E.prenom_ens,
                    E.grade,
                    C.date_examen,
                    C.heure_debut
                FROM Affectations A
                JOIN Creneaux C ON A.creneau_id = C.id
                JOIN Enseignants E ON CAST(A.enseignant_id AS TEXT) = CAST(E.id AS TEXT)
                WHERE C.session_id = ? AND E.session_id = ?
                ORDER BY E.id, C.date_examen, C.heure_debut
            """, (session_id, session_id))
            
            assignments_raw = cursor.fetchall()
            
            if not assignments_raw:
                print(f"No assignments found for session {session_id}")
                return 0
            
            # Group by teacher
            assignments_by_teacher = defaultdict(list)
            for row in assignments_raw:
                teacher_id = row[0]
                assignments_by_teacher[teacher_id].append({
                    'date': row[5],
                    'time': row[6]
                })
            
            # Map time to seance
            TIME_TO_SEANCE = {
                '08:30:00': 'S1', '08:30': 'S1',
                '10:30:00': 'S2', '10:30': 'S2',
                '14:00:00': 'S3', '14:00': 'S3',
                '16:00:00': 'S4', '16:00': 'S4'
            }
            
            # Map time to hours for gap calculation
            TIME_TO_HOURS = {
                'S1': 8.5, '08:30': 8.5, '08:30:00': 8.5,
                'S2': 10.5, '10:30': 10.5, '10:30:00': 10.5,
                'S3': 14.0, '14:00': 14.0, '14:00:00': 14.0,
                'S4': 16.0, '16:00': 16.0, '16:00:00': 16.0
            }
            
            # Compute satisfaction for each teacher
            satisfaction_data = []
            
            for teacher_id, slots in assignments_by_teacher.items():
                if teacher_id not in teacher_lookup:
                    continue
                
                teacher_info = teacher_lookup[teacher_id]
                teacher_code = teacher_info['code']
                nom = teacher_info['nom']
                prenom = teacher_info['prenom']
                grade = teacher_info['grade']
                teacher_name = f"{prenom} {nom}" if prenom else nom
                
                total_assignments = len(slots)
                quota = quotas.get(grade, 5)
                quota_excess = max(0, total_assignments - quota)
                
                # Calculate working days
                working_dates = set(slot['date'] for slot in slots)
                working_days = len(working_dates)
                
                # Calculate sessions by date and time period (for isolated days)
                sessions_by_date = defaultdict(lambda: {'morning': 0, 'afternoon': 0, 'times': []})
                for slot in slots:
                    time = slot['time']
                    seance = TIME_TO_SEANCE.get(time, 'unknown')
                    hour = TIME_TO_HOURS.get(time, TIME_TO_HOURS.get(seance, 0))
                    
                    sessions_by_date[slot['date']]['times'].append(hour)
                    # Morning: S1, S2 | Afternoon: S3, S4
                    if '08:' in time or '10:' in time or seance in ['S1', 'S2']:
                        sessions_by_date[slot['date']]['morning'] += 1
                    else:
                        sessions_by_date[slot['date']]['afternoon'] += 1
                
                # Count isolated days (only morning OR afternoon, not both)
                isolated_days = sum(
                    1 for sessions in sessions_by_date.values()
                    if (sessions['morning'] > 0) != (sessions['afternoon'] > 0)
                )
                
                # Calculate gap days between working dates
                gap_days = 0
                if working_days > 1:
                    try:
                        sorted_dates = sorted([pd.to_datetime(d) for d in working_dates])
                        for i in range(len(sorted_dates) - 1):
                            gap = (sorted_dates[i + 1] - sorted_dates[i]).days - 1
                            gap_days += max(0, gap)
                    except:
                        gap_days = 0
                
                # Calculate gap hours (max gap within same day)
                max_gap_hours = 0
                for date, info in sessions_by_date.items():
                    times = sorted(info['times'])
                    if len(times) > 1:
                        for i in range(len(times) - 1):
                            gap = times[i + 1] - times[i]
                            max_gap_hours = max(max_gap_hours, gap)
                
                # Check voeux respected
                teacher_voeux = voeux_by_teacher.get(str(teacher_code), [])
                voeux_total = len(teacher_voeux)
                voeux_respected = voeux_total  # Start with all voeux respected
                voeux_violations = []
                voeux_details = []
                
                if teacher_voeux:
                    # Check each assignment against voeux (unavailability)
                    for slot in slots:
                        slot_date = slot['date']
                        slot_time = slot['time']
                        slot_seance = TIME_TO_SEANCE.get(slot_time, '')
                        
                        # Try to match by date/seance
                        try:
                            slot_date_obj = pd.to_datetime(slot_date)
                            slot_jour = slot_date_obj.dayofweek + 1  # Monday = 1
                            
                            # Check if this assignment violates a voeu
                            for voeu_jour, voeu_seance in teacher_voeux:
                                # Check if jour is a date or day number
                                if isinstance(voeu_jour, int):
                                    voeu_jour_normalized = voeu_jour
                                else:
                                    try:
                                        voeu_date_obj = pd.to_datetime(voeu_jour)
                                        voeu_jour_normalized = voeu_date_obj.dayofweek + 1
                                    except:
                                        voeu_jour_normalized = voeu_jour
                                
                                # If assigned to unavailable slot = VIOLATION
                                if (voeu_jour_normalized == slot_jour and voeu_seance == slot_seance):
                                    voeux_respected -= 1  # One voeu violated
                                    voeux_violations.append(f"{slot_date} ({slot_jour}) {slot_seance}")
                                    break  # Don't double-count same violation
                        except Exception as e:
                            continue
                    
                    # Ensure voeux_respected doesn't go negative
                    voeux_respected = max(0, voeux_respected)
                    voeux_details = voeux_violations if voeux_violations else []
                
                # ==== NEW SATISFACTION SCORE CALCULATION (0-100) ====
                score = 100.0
                issues = []
                
                # 1. VOEUX RESPECTED (40 points)
                if voeux_total > 0:
                    voeux_ratio = voeux_respected / voeux_total
                    voeux_score = voeux_ratio * 40
                    penalty = 40 - voeux_score
                    score -= penalty
                    if voeux_ratio < 0.5:
                        issues.append(f"Only {voeux_respected}/{voeux_total} voeux respected ({voeux_ratio*100:.0f}%)")
                else:
                    # No voeux = neutral (no penalty)
                    pass
                
                # 2. ISOLATED DAYS (25 points)
                if isolated_days > 0:
                    # Penalty: -8.33 points per isolated day (max 3 days = 25 pts)
                    penalty = min(25, isolated_days * 8.33)
                    score -= penalty
                    issues.append(f"{isolated_days} isolated day(s)")
                
                # 3. COMPACTNESS (20 points)
                ideal_days = max(1, (total_assignments + 1) // 2)
                extra_days = working_days - ideal_days
                if extra_days > 0:
                    # Penalty: -6.67 points per extra day (max 3 days = 20 pts)
                    penalty = min(20, extra_days * 6.67)
                    score -= penalty
                    issues.append(f"Spread across {extra_days} extra day(s)")
                
                # 4. GAP BETWEEN HOURS (15 points)
                if max_gap_hours > 2:  # More than 2 hours gap
                    # Penalty: -3 points per hour over 2 (max 5 hours = 15 pts)
                    excess_gap = max_gap_hours - 2
                    penalty = min(15, excess_gap * 3)
                    score -= penalty
                    issues.append(f"{max_gap_hours:.1f}h gap between sessions")
                
                score = max(0, score)
                
                if not issues:
                    issues.append("No issues")
                
                # Simplified schedule pattern (for performance)
                pattern = f"{working_days} day(s), {total_assignments} session(s)"
                
                satisfaction_data.append({
                    'teacher_id': teacher_code,
                    'name': teacher_name,
                    'grade': grade,
                    'satisfaction_score': score,
                    'total_assignments': total_assignments,
                    'quota': quota,
                    'quota_excess': quota_excess,
                    'working_days': working_days,
                    'consecutive_days': 0,  # Not used in new scoring
                    'isolated_days': isolated_days,
                    'gap_days': gap_days,
                    'voeux_respected': voeux_respected,
                    'voeux_total': voeux_total,
                    'voeux_details': ','.join(voeux_details) if voeux_details else '',
                    'gap_hours': int(max_gap_hours),
                    'schedule_pattern': pattern,
                    'issues': issues
                })
            
            conn.close()
            
            # Save to database
            if satisfaction_data:
                return self.save_satisfaction_report(session_id, satisfaction_data)
            
            return 0
            
        except Exception as e:
            print(f"Error computing satisfaction: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return 0
    
    def recommend_quotas(self, session_id: int, overprovisioning_rate: float = 1.15) -> Dict[str, Any]:
        """
        Recommend optimal quotas based on session data and needs.
        
        Based on director feedback: Quotas are indicative guidelines with overprovisioning
        to handle unexpected absences.
        
        Args:
            session_id: Session ID to analyze
            overprovisioning_rate: Safety margin (1.15 = 15% extra capacity)
        
        Returns:
            Dictionary containing:
            - current_quotas: Current quota configuration
            - recommended_quotas: Recommended quotas
            - scenarios: Different overprovisioning scenarios
            - analysis: Capacity analysis
        """
        from collections import Counter
        
        # Get data
        teachers_df = self.get_teachers(session_id, participating_only=True)
        slots = self.get_slots(session_id)
        
        if not slots:
            return {'error': 'No exam slots found'}
        
        # Calculate needs
        total_needed = sum(slot['nb_surveillants'] for slot in slots)
        grade_counts = Counter(teachers_df['grade_code_ens'])
        
        # Current quotas
        CURRENT_QUOTAS = {
            'PR': 4, 'MC': 4, 'MA': 7, 'AS': 8, 'AC': 9,
            'PTC': 9, 'PES': 9, 'EX': 3, 'V': 4
        }
        
        # Grade weights for recommendations
        grade_weights = {
            'PR': 0.8, 'MC': 0.9, 'MA': 1.0, 'AS': 1.1, 'AC': 1.2,
            'PTC': 1.0, 'PES': 1.0, 'EX': 0.7, 'V': 0.8
        }
        
        # Calculate target capacity with safety margin
        target_capacity = int(total_needed * overprovisioning_rate)
        
        # Calculate weighted teacher capacity
        total_weighted = sum(
            grade_counts.get(grade, 0) * grade_weights.get(grade, 1.0)
            for grade in grade_weights.keys()
        )
        
        if total_weighted == 0:
            return {'error': 'No participating teachers'}
        
        # Calculate recommended quotas
        base_quota = target_capacity / total_weighted
        recommended = {}
        
        for grade in sorted(grade_weights.keys()):
            count = grade_counts.get(grade, 0)
            if count == 0:
                continue
            
            weight = grade_weights.get(grade, 1.0)
            quota = base_quota * weight
            quota_rounded = max(3, round(quota))
            recommended[grade] = quota_rounded
        
        # Calculate capacities
        current_capacity = sum(
            grade_counts.get(grade, 0) * CURRENT_QUOTAS.get(grade, 0)
            for grade in CURRENT_QUOTAS.keys()
        )
        
        recommended_capacity = sum(
            grade_counts.get(grade, 0) * quota
            for grade, quota in recommended.items()
        )
        
        # Generate scenarios
        scenarios = {}
        for scenario_name, rate in [('conservative', 1.05), ('balanced', 1.15), ('safe', 1.25)]:
            scenario_target = int(total_needed * rate)
            scenario_base = scenario_target / total_weighted
            
            scenario_quotas = {}
            for grade in sorted(grade_weights.keys()):
                count = grade_counts.get(grade, 0)
                if count > 0:
                    weight = grade_weights.get(grade, 1.0)
                    quota = max(3, round(scenario_base * weight))
                    scenario_quotas[grade] = quota
            
            scenario_capacity = sum(
                grade_counts.get(grade, 0) * quota
                for grade, quota in scenario_quotas.items()
            )
            
            scenarios[scenario_name] = {
                'quotas': scenario_quotas,
                'capacity': scenario_capacity,
                'overprovision': ((scenario_capacity - total_needed) / total_needed * 100) if total_needed > 0 else 0
            }
        
        return {
            'session_id': session_id,
            'total_teachers': len(teachers_df),
            'total_needed': total_needed,
            'current_quotas': CURRENT_QUOTAS,
            'current_capacity': current_capacity,
            'current_overprovision': ((current_capacity - total_needed) / total_needed * 100) if total_needed > 0 else 0,
            'recommended_quotas': recommended,
            'recommended_capacity': recommended_capacity,
            'recommended_overprovision': ((recommended_capacity - total_needed) / total_needed * 100) if total_needed > 0 else 0,
            'scenarios': scenarios,
            'grade_distribution': dict(grade_counts)
        }


# ==================== INTEGRATION FUNCTIONS ====================

def import_excel_data_to_db(session_id: int, teachers_file: str, 
                           voeux_file: str, slots_file: str, 
                           db_path: str = "planning.db"):
    """
    Import all data from Excel files into database for a session
    
    Args:
        session_id: Session ID to import data for
        teachers_file: Path to Enseignants.xlsx
        voeux_file: Path to Souhaits.xlsx
        slots_file: Path to Repartitions.xlsx
        db_path: Path to SQLite database
    
    Returns:
        Dictionary with import statistics
    """
    import sys
    import os
    
    # Add parent directory to path to import data_loader
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import data_loader
    
    db = DatabaseManager(db_path)
    
    # Load data using existing data_loader
    teachers_df, min_quotas, voeux_by_id, voeux_timestamps, slots_df, slot_info, all_teachers_lookup = \
        data_loader.load_enhanced_data(teachers_file, voeux_file, slots_file)
    
    # Import teachers
    # Need to prepare the full teachers DataFrame (including non-participants)
    full_teachers_df = pd.read_excel(teachers_file)
    teachers_count = db.import_teachers_from_excel(session_id, full_teachers_df)
    
    # Import voeux
    voeux_df = pd.read_excel(voeux_file)
    voeux_count = db.import_voeux_from_excel(session_id, voeux_df, full_teachers_df)
    
    # Import slots
    slots_count = db.import_slots_from_excel(session_id, slots_df, slot_info)
    
    # Save configuration with CORRECT quotas from official table
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
    config_id = db.save_config(session_id, surveillants_par_salle=2, quotas=quota_per_grade)
    
    return {
        'teachers_imported': teachers_count,
        'voeux_imported': voeux_count,
        'slots_imported': slots_count,
        'config_id': config_id
    }


def run_scheduler_from_db(session_id: int, db_path: str = "planning.db", 
                         supervisors_per_room: int = 2,
                         compactness_weight: int = 10,
                         max_sessions_per_day: int = 3,
                         gap_penalty_weight: int = 50,
                         max_solve_time: float = 120.0):
    """
    Run the exam scheduler using data from the database
    
    Args:
        session_id: Session ID to schedule
        db_path: Path to SQLite database
        supervisors_per_room: Number of supervisors per room
        compactness_weight: Weight for schedule compactness
        max_sessions_per_day: Max sessions per day per teacher
        gap_penalty_weight: Weight for gap penalty
        max_solve_time: Maximum solving time in seconds
    
    Returns:
        assignments: Assignment dictionary
        stats: Statistics about the scheduling
    """
    import sys
    import os
    
    # This would require modifying exam_scheduler.py to accept DataFrames/dicts
    # instead of file paths. For now, this is a placeholder showing the integration pattern.
    
    db = DatabaseManager(db_path)
    
    # Get data from database
    teachers_df = db.get_teachers(session_id, participating_only=True)
    voeux_by_id = db.get_voeux(session_id)
    slots = db.get_slots(session_id)
    config = db.get_config(session_id)
    
    print(f"Loaded from database:")
    print(f"  - {len(teachers_df)} teachers")
    print(f"  - {sum(len(v) for v in voeux_by_id.values())} voeux")
    print(f"  - {len(slots)} slots")
    
    # TODO: Adapt exam_scheduler.py to work with database data
    # For now, this demonstrates the integration pattern
    
    return None, None


if __name__ == '__main__':
    # Example usage
    db = DatabaseManager("planning.db")
    
    # Create a test session
    session_id = db.create_session(
        nom="Session Hiver 2025",
        annee_academique="2024-2025",
        semestre="S1"
    )
    
    print(f"✅ Created session with ID: {session_id}")
    
    # List all sessions
    sessions = db.list_sessions()
    print(f"\n📋 All sessions:")
    for s in sessions:
        print(f"  - ID {s['id']}: {s['nom']} ({s['annee_academique']} - {s['semestre']})")
