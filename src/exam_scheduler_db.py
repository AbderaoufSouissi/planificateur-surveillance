"""
Database-integrated Exam Scheduler - Grade Equality & Soft Voeux Version
========================================================================
Key Features:
- HARD constraint: Grade quota equality (all MA teachers get same assignments)
- SOFT constraint: Voeux respect (penalized but not blocked)
- Enhanced debugging and progress reporting
"""

import os
import sys
import argparse
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from datetime import datetime
from ortools.sat.python import cp_model

# Database operations import
try:
    # PyInstaller/bundled environment
    from src.db.db_operations import DatabaseManager
except ImportError:
    try:
        # Development environment - relative import
        from db.db_operations import DatabaseManager
    except ImportError:
        # Fallback - add to path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_dir = os.path.join(current_dir, 'db')
        if db_dir not in sys.path:
            sys.path.insert(0, db_dir)
        from db_operations import DatabaseManager

try:
    from exam_scheduler import analyze_teacher_satisfaction
except ImportError:
    print("⚠️  Warning: analyze_teacher_satisfaction not available")
    analyze_teacher_satisfaction = None


class SchedulerDefaults:
    """Default values and constants."""
    
    # Scheduling constraints
    MIN_SUPERVISORS_PER_ROOM = 2
    MAX_SUPERVISORS_PER_ROOM = 3
    SUPERVISORS_PER_ROOM = 2
    MAX_SESSIONS_PER_DAY = 4
    MAX_SOLVE_TIME_SECONDS = 300.0
    NUM_SEARCH_WORKERS = 8
    
    # Gap constraints
    MAX_GAP_DAYS_STRICT = 1
    MAX_GAP_DAYS_RELAXED = 2
    
    # Grade quota flexibility levels
    FLEXIBILITY_STRICT = 0
    FLEXIBILITY_ABSENCES = 1
    FLEXIBILITY_RELAXED = 2
    
    # Penalty weights
    PENALTY_QUOTA_DEVIATION = 1000000
    PENALTY_ISOLATED_DAY = 15000
    PENALTY_VOEUX_VIOLATION = 10000
    PENALTY_FULL_DAY_VIOLATION = 8000
    PENALTY_GAP_DAYS = 5000
    PENALTY_ACTIVE_DAY = 100
    PENALTY_EXTRA_SUPERVISOR = 200
    BONUS_MULTI_SESSION = -500
    BONUS_CONSECUTIVE = -300   


@dataclass
class SchedulerConfig:
    """Configuration for exam scheduler."""
    min_supervisors_per_room: int = SchedulerDefaults.MIN_SUPERVISORS_PER_ROOM
    max_supervisors_per_room: int = SchedulerDefaults.MAX_SUPERVISORS_PER_ROOM
    supervisors_per_room: int = SchedulerDefaults.SUPERVISORS_PER_ROOM
    max_sessions_per_day: int = SchedulerDefaults.MAX_SESSIONS_PER_DAY
    max_solve_time: float = SchedulerDefaults.MAX_SOLVE_TIME_SECONDS
    num_search_workers: int = SchedulerDefaults.NUM_SEARCH_WORKERS
    random_seed: Optional[int] = None
    
    quota_deviation_penalty: int = SchedulerDefaults.PENALTY_QUOTA_DEVIATION
    voeux_penalty_weight: int = SchedulerDefaults.PENALTY_VOEUX_VIOLATION
    full_day_penalty_weight: int = SchedulerDefaults.PENALTY_FULL_DAY_VIOLATION
    isolated_day_penalty: int = SchedulerDefaults.PENALTY_ISOLATED_DAY
    gap_penalty: int = SchedulerDefaults.PENALTY_GAP_DAYS
    active_day_penalty: int = SchedulerDefaults.PENALTY_ACTIVE_DAY
    extra_supervisor_penalty: int = SchedulerDefaults.PENALTY_EXTRA_SUPERVISOR
    multi_session_bonus: int = SchedulerDefaults.BONUS_MULTI_SESSION
    consecutive_bonus: int = SchedulerDefaults.BONUS_CONSECUTIVE
    
    grade_quota_flexibility: int = SchedulerDefaults.FLEXIBILITY_STRICT
    auto_relax_if_infeasible: bool = True
    max_gap_days: int = SchedulerDefaults.MAX_GAP_DAYS_STRICT
    
    use_custom_quotas: bool = False
    custom_quotas: Optional[Dict[str, int]] = None


DEFAULT_QUOTAS = {
    'PR': 4, 'MC': 4, 'MA': 7, 'AS': 8, 'AC': 9,
    'PTC': 9, 'PES': 9, 'EX': 3, 'V': 4
}

TIME_TO_SEANCE = {
    '08:30:00': 'S1', '10:30:00': 'S2',
    '14:00:00': 'S3', '16:00:00': 'S4',
    '08:30': 'S1', '10:30': 'S2',
    '14:00': 'S3', '16:00': 'S4'
}

JOUR_NAMES = {
    1: 'Lundi', 2: 'Mardi', 3: 'Mercredi',
    4: 'Jeudi', 5: 'Vendredi', 6: 'Samedi'
}


@dataclass
class SlotInfo:
    """Information about an exam slot."""
    slot_id: int
    creneau_id: int
    jour: int
    seance: str
    date: str
    time: str
    nb_rooms: int
    
    @property
    def display_name(self) -> str:
        """Human-readable slot name."""
        jour_name = JOUR_NAMES.get(self.jour, f'Jour {self.jour}')
        return f"{jour_name} {self.seance} ({self.date})"
    
    def requires_supervisors(self, supervisors_per_room: int) -> int:
        """Calculate required supervisors."""
        return self.nb_rooms * supervisors_per_room


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def date_to_jour(date_str: str) -> int:
    """Convert date string to jour number (1-6)."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.weekday() + 1
    except Exception as e:
        print(f"⚠️  Error converting date '{date_str}': {e}")
        return 1


def time_to_seance(time_str: str) -> str:
    """Convert time string to seance (S1-S4)."""
    return TIME_TO_SEANCE.get(time_str, 'S1')


def progress_report(callback, message: str, progress: float):
    """Safely report progress."""
    if callback:
        try:
            callback(message, progress)
        except Exception as e:
            print(f"⚠️  Progress callback error: {e}")
    print(f"[{progress:5.1f}%] {message}")


class DataLoader:
    """Handles loading data from database."""
    
    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)
        print(f"✓ Database connected: {db_path}")
    
    def load_teachers(self, session_id: int) -> pd.DataFrame:
        """Load and validate teacher data."""
        print(f"\nLoading teachers for session {session_id}...")
        
        teachers_df = self.db.get_teachers(session_id)
        
        if teachers_df.empty:
            raise ValueError(f"❌ No teachers found for session {session_id}")
        
        # Map database column names to expected names
        column_mapping = {
            'nom_ens': 'nom',
            'prenom_ens': 'prenom',
            'grade_code_ens': 'grade',
            'email_ens': 'email',
            'code_smartexam_ens': 'code_smartexam'
        }
        
        # Rename columns if they exist
        for old_col, new_col in column_mapping.items():
            if old_col in teachers_df.columns:
                teachers_df.rename(columns={old_col: new_col}, inplace=True)
        
        # Validate required columns after mapping
        required_cols = ['id', 'nom', 'prenom', 'grade']
        missing = [col for col in required_cols if col not in teachers_df.columns]
        if missing:
            print(f"Available columns: {list(teachers_df.columns)}")
            raise ValueError(f"❌ Missing columns in teachers: {missing}")
        
        teachers_df['teacher_id'] = teachers_df['id']
        teachers_df.set_index('teacher_id', inplace=True, drop=False)
        
        # Count by grade
        grade_counts = teachers_df['grade'].value_counts().to_dict()
        
        print(f"\n✓ Loaded {len(teachers_df)} teachers:")
        for grade in sorted(grade_counts.keys()):
            print(f"  {grade:5s}: {grade_counts[grade]:3d} teachers")
        
        return teachers_df
    
    def load_slots(self, session_id: int) -> pd.DataFrame:
        """Load and validate exam slots."""
        print(f"\nLoading exam slots for session {session_id}...")
        
        conn = self.db.get_connection()
        
        # Updated query to match actual database schema (Creneaux table only)
        query = """
        SELECT 
            c.id as creneau_id,
            c.date_examen as date,
            c.heure_debut as time,
            c.nb_surveillants as nb_salle,
            c.code_responsable
        FROM Creneaux c
        WHERE c.session_id = ?
        ORDER BY c.date_examen, c.heure_debut
        """
        
        slots_df = pd.read_sql_query(query, conn, params=(session_id,))
        conn.close()
        
        if slots_df.empty:
            raise ValueError(f"❌ No slots found for session {session_id}")
        
        # Process slots
        slots_df['jour'] = slots_df['date'].apply(date_to_jour)
        slots_df['seance'] = slots_df['time'].apply(time_to_seance)
        slots_df['slot_id'] = range(len(slots_df))
        
        print(f"\n✓ Loaded {len(slots_df)} exam slots:")
        
        # Group by day
        slots_by_day = slots_df.groupby('jour').agg({
            'slot_id': 'count',
            'nb_salle': 'sum'
        }).rename(columns={'slot_id': 'num_slots', 'nb_salle': 'total_rooms'})
        
        for jour, row in slots_by_day.iterrows():
            jour_name = JOUR_NAMES.get(jour, f'Jour {jour}')
            print(f"  {jour_name:10s}: {row['num_slots']:2d} slots, "
                  f"{row['total_rooms']:3d} rooms")
        
        return slots_df
    
    def load_voeux(self, session_id: int) -> Dict[int, List[Tuple[int, str]]]:
        """Load teacher preferences (unavailability)."""
        print(f"\nLoading voeux (preferences) for session {session_id}...")
        
        conn = self.db.get_connection()
        
        # All entries in Voeux table represent unavailability (no disponible column)
        query = """
        SELECT 
            v.enseignant_id as teacher_id,
            v.jour,
            v.seance
        FROM Voeux v
        WHERE v.session_id = ?
        ORDER BY v.enseignant_id, v.jour, v.seance
        """
        
        voeux_df = pd.read_sql_query(query, conn, params=(session_id,))
        conn.close()
        
        if voeux_df.empty:
            print(f"\n⚠️  No voeux found for session {session_id}")
            return {}
        
        voeux_by_id = defaultdict(list)
        for _, row in voeux_df.iterrows():
            # Convert jour to int (database stores as TEXT)
            try:
                jour_int = int(row['jour']) if pd.notna(row['jour']) else None
                seance_str = str(row['seance']) if pd.notna(row['seance']) else None
                
                if jour_int is not None and seance_str is not None and seance_str != 'nan':
                    voeux_by_id[row['teacher_id']].append((jour_int, seance_str))
            except (ValueError, TypeError) as e:
                print(f"⚠️  Skipping invalid voeux: jour={row['jour']}, seance={row['seance']}, error={e}")
        
        print(f"\n✓ Loaded voeux for {len(voeux_by_id)} teachers:")
        
        total_unavailable = sum(len(v) for v in voeux_by_id.values())
        print(f"  Total unavailable slots: {total_unavailable}")
        
        # Show top 5 teachers with most unavailabilities
        top_voeux = sorted(voeux_by_id.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        if top_voeux:
            print(f"\n  Top teachers by unavailability:")
            for tid, slots in top_voeux:
                print(f"    Teacher {tid}: {len(slots)} unavailable slots")
        
        return dict(voeux_by_id)
    
    def load_configuration(self, session_id: int, config: SchedulerConfig) -> Tuple[int, Dict]:
        """Load session configuration and calculate total needed."""
        print(f"\n{'='*70}")
        print(f"SESSION CONFIGURATION")
        print(f"{'='*70}")
        
        print(f"\n  Supervisors per room:     {config.supervisors_per_room}")
        print(f"  Max sessions per day:     {config.max_sessions_per_day}")
        print(f"  Max solve time:           {config.max_solve_time}s")
        print(f"  Voeux penalty weight:     {config.voeux_penalty_weight}")
        print(f"  Grade quota flexibility:  ±{config.grade_quota_flexibility}")
        print(f"  Search workers:           {config.num_search_workers}")
        
        return config


class ConstraintBuilder:
    """Builds optimization model constraints."""
    
    def __init__(self, model: cp_model.CpModel, config: SchedulerConfig):
        self.model = model
        self.config = config
        self.x_surv = {}
        self.constraint_counts = defaultdict(int)
    
    def create_variables(self, num_teachers: int, num_slots: int):
        """Create decision variables."""
        print(f"\nCreating decision variables...")
        
        for t in range(num_teachers):
            for s in range(num_slots):
                self.x_surv[t, s] = self.model.NewBoolVar(f'x_t{t}_s{s}')
        
        total_vars = num_teachers * num_slots
        print(f"✓ Created {total_vars:,} variables ({num_teachers} teachers × {num_slots} slots)")
    
    def add_coverage_constraints(
        self,
        slots_df: pd.DataFrame,
        num_teachers: int,
        min_supervisors: int,
        max_supervisors: int
    ):
        """Ensure each slot has required supervisors (flexible 2-3 per room)."""
        print(f"\nAdding flexible coverage constraints (HARD)...")
        
        total_min = 0
        total_max = 0
        
        self.extra_supervisors = {}
        
        for s_idx, slot in slots_df.iterrows():
            nb_rooms = int(slot['nb_salle'])
            min_required = nb_rooms * min_supervisors
            max_allowed = nb_rooms * max_supervisors
            
            total_min += min_required
            total_max += max_allowed
            
            assigned_teachers = [
                self.x_surv[t, s_idx] 
                for t in range(num_teachers)
            ]
            
            self.model.Add(sum(assigned_teachers) >= min_required)
            self.model.Add(sum(assigned_teachers) <= max_allowed)
            self.constraint_counts['coverage'] += 2
            
            extra = self.model.NewIntVar(0, max_allowed - min_required, f'extra_s{s_idx}')
            self.model.Add(extra == sum(assigned_teachers) - min_required)
            self.extra_supervisors[s_idx] = extra
        
        print(f"✓ Added {self.constraint_counts['coverage']} coverage constraints")
        print(f"  Range per slot: {min_required}-{max_allowed} supervisors")
        print(f"  Total range: {total_min}-{total_max} supervisors")
        
        return total_min
    
    def add_minimum_assignment(self, num_teachers: int, num_slots: int):
        """Ensure every teacher gets at least one assignment."""
        print(f"\nAdding minimum assignment constraints (HARD)...")
        
        for t in range(num_teachers):
            teacher_assignments = [
                self.x_surv[t, s] 
                for s in range(num_slots)
            ]
            
            self.model.Add(sum(teacher_assignments) >= 1)
            self.constraint_counts['minimum'] += 1
        
        print(f"✓ Added {self.constraint_counts['minimum']} minimum assignment constraints")
    
    def add_daily_limit(
        self,
        teacher_ids: List[int],
        slots_df: pd.DataFrame
    ) -> Dict[int, List[int]]:
        """Limit sessions per day."""
        print(f"\nAdding daily limit constraints...")
        
        slots_by_jour = defaultdict(list)
        for s_idx, slot in slots_df.iterrows():
            jour = slot['jour']
            slots_by_jour[jour].append(s_idx)
        
        for t_idx in range(len(teacher_ids)):
            for jour, slot_indices in slots_by_jour.items():
                daily_assignments = [
                    self.x_surv[t_idx, s_idx] 
                    for s_idx in slot_indices
                ]
                
                self.model.Add(
                    sum(daily_assignments) <= self.config.max_sessions_per_day
                )
                self.constraint_counts['daily_limit'] += 1
        
        print(f"✓ Added {self.constraint_counts['daily_limit']} daily limit constraints "
              f"(max {self.config.max_sessions_per_day}/day)")
        
        return dict(slots_by_jour)
    
    
    
    def add_maximum_gap_constraint(
        self,
        teacher_ids: List[int],
        slots_by_jour: Dict[int, List[int]],
        max_gap_days: int = 2
    ):
        """Prevent large gaps between working days."""
        print(f"\nAdding max gap constraint (max_gap={max_gap_days})...")
        
        num_teachers = len(teacher_ids)
        sorted_jours = sorted(slots_by_jour.keys())
        
        constraints_added = 0
        
        for t_idx in range(num_teachers):
            # Track which days this teacher works
            working_days = {}
            for jour in sorted_jours:
                day_var = self.model.NewBoolVar(f'works_t{t_idx}_j{jour}')
                slot_indices = slots_by_jour[jour]
                daily_assignments = [self.x_surv[t_idx, s_idx] for s_idx in slot_indices]
                
                # day_var = 1 if teacher works on this day
                self.model.AddMaxEquality(day_var, daily_assignments)
                working_days[jour] = day_var
            
            # Check gaps between working days
            for i in range(len(sorted_jours) - 1):
                jour1 = sorted_jours[i]
                jour2 = sorted_jours[i + 1]
                gap = jour2 - jour1 - 1
                
                if gap > max_gap_days:
                    # HARD constraint: Cannot work on jour1 and jour2 with this gap
                    # If works on jour1, then cannot work on jour2 (and vice versa)
                    self.model.AddBoolOr([
                        working_days[jour1].Not(),
                        working_days[jour2].Not()
                    ])
                    constraints_added += 1
        
        print(f"  Max gap constraints added: {constraints_added}")
        print(f"  Effect: Teachers cannot work on days separated by >{max_gap_days} days")
        print(f"{'='*70}")
        
        self.constraint_counts['max_gap'] = constraints_added
    
    def add_grade_quota_equality(
        self,
        teacher_ids: List[int],
        teachers_df: pd.DataFrame,
        num_slots: int,
        total_needed: int,
        adjusted_quotas: Dict[int, int] = None  # NEW: Accept pre-calculated quotas
    ) -> Dict[str, Any]:
        """
        HARD constraint: All teachers of same grade get equal assignments.
        """
        print(f"\nAdding grade quota equality constraints (HARD)...")
        
        # Group teachers by grade
        teachers_by_grade = defaultdict(list)
        for tid in teacher_ids:
            grade = teachers_df.loc[tid, 'grade']
            teachers_by_grade[grade].append(tid)
        
        grade_quotas = {}
        total_teachers = len(teacher_ids)
        
        print(f"\nCalculating grade quotas (total needed: {total_needed}):")
        
        # Calculate target quota per grade
        grade_targets = {}
        
        if adjusted_quotas:
            # Use adjusted quotas - calculate average per grade
            print(f"\nUsing adjusted quotas from capacity analysis:")
            for grade, grade_teachers in sorted(teachers_by_grade.items()):
                # Get quotas for all teachers in this grade
                teacher_quotas = [adjusted_quotas.get(tid, 0) for tid in grade_teachers]
                # They should all be the same (or very close), take the average
                avg_quota = sum(teacher_quotas) / len(teacher_quotas) if teacher_quotas else 0
                grade_targets[grade] = round(avg_quota)
                
                num_in_grade = len(grade_teachers)
                total_for_grade = grade_targets[grade] * num_in_grade
                
                print(f"  {grade:5s}: {num_in_grade:3d} teachers × {grade_targets[grade]:2d} = "
                    f"{total_for_grade:3d} surveillances (from adjusted quotas)")
        else:
            # Fallback: proportional distribution
            print(f"\nNo adjusted quotas - using proportional distribution:")
            for grade, grade_teachers in sorted(teachers_by_grade.items()):
                num_in_grade = len(grade_teachers)
                grade_share = num_in_grade / total_teachers
                ideal_quota_total = total_needed * grade_share
                ideal_quota = int(round(ideal_quota_total / num_in_grade))
                grade_targets[grade] = ideal_quota
                
                print(f"  {grade:5s}: {num_in_grade:3d} teachers × {ideal_quota:2d} = "
                    f"{num_in_grade * ideal_quota:3d} surveillances (proportional)")
        
        # Verify total matches needed
        total_from_quotas = sum(
            grade_targets[grade] * len(teachers_by_grade[grade]) 
            for grade in teachers_by_grade.keys()
        )
        
        # Create constraints with adjusted targets
        for grade, grade_teachers in sorted(teachers_by_grade.items()):
            num_in_grade = len(grade_teachers)
            target = grade_targets[grade]
            
            # Create quota variable with tight bounds around target
            min_quota = max(1, target - self.config.grade_quota_flexibility)
            max_quota = min(num_slots, target + self.config.grade_quota_flexibility)
            
            quota_var = self.model.NewIntVar(
                min_quota,
                max_quota,
                f'quota_grade_{grade}'
            )
            
            grade_quotas[grade] = {
                'quota_var': quota_var,
                'ideal': target,
                'num_teachers': num_in_grade,
                'teacher_ids': grade_teachers,
                'total_contribution': quota_var * num_in_grade
            }
            
            print(f"  {grade:5s}: {num_in_grade:3d} teachers × {target} = "
                f"{num_in_grade * target} surveillances")
            print(f"           Range: [{min_quota}, {max_quota}] per teacher")
            
            # HARD CONSTRAINT: Every teacher in this grade gets EXACTLY the same quota
            # Create one quota_var for the entire grade, then force all teachers to match it
            for tid in grade_teachers:
                t_idx = teacher_ids.index(tid)
                
                teacher_assignments = [
                    self.x_surv[t_idx, s] 
                    for s in range(num_slots)
                ]
                
                # CRITICAL: All teachers in grade must get EXACTLY quota_var
                # No flexibility - they all get the same number
                self.model.Add(sum(teacher_assignments) == quota_var)
                
                self.constraint_counts['grade_equality'] += 1
        
        # CRITICAL: Ensure total assignments match total needed
        total_assignment_expr = []
        for grade, info in grade_quotas.items():
            total_assignment_expr.append(info['total_contribution'])
        
        self.model.Add(sum(total_assignment_expr) == total_needed)
        self.constraint_counts['total_match'] += 1
        
        print(f"\n✓ Added {self.constraint_counts['grade_equality']} grade equality constraints")
        print(f"✓ Added {self.constraint_counts['total_match']} total match constraint")
        
        return grade_quotas
    
    def add_voeux_soft_penalties(
        self,
        teacher_ids: List[int],
        slots_df: pd.DataFrame,
        voeux_by_id: Dict[int, List[Tuple[int, str]]]
    ) -> Dict[int, List]:
        """
        Soft voeux: Allow but penalize assignments to unavailable slots.
        CRITICAL: Detect and MASSIVELY penalize FULL DAY unavailability violations.
        """
        print(f"\nAdding voeux soft penalties with FULL DAY detection...")
        
        voeux_violations = []
        full_day_violations = []
        teachers_with_voeux = 0
        
        # First, detect which teachers have FULL DAY unavailability
        full_day_unavailable = {}  # {teacher_id: set of jours}
        for tid, unavailable_slots in voeux_by_id.items():
            # Group by jour
            slots_by_jour = defaultdict(set)
            for jour, seance in unavailable_slots:
                slots_by_jour[jour].add(seance)
            
            # Check if any jour has ALL 4 sessions marked unavailable
            full_days = set()
            for jour, seances in slots_by_jour.items():
                if len(seances) >= 4 or seances == {'S1', 'S2', 'S3', 'S4'}:
                    full_days.add(jour)
            
            if full_days:
                full_day_unavailable[tid] = full_days
                teacher_name = f"Teacher {tid}"
                # Try to get name from teachers_df if available
                print(f"  ⚠️  {teacher_name} requested FULL DAY unavailability: Jours {sorted(full_days)}")
        
        for t_idx, tid in enumerate(teacher_ids):
            if tid not in voeux_by_id:
                continue
            
            teachers_with_voeux += 1
            unavailable_slots = voeux_by_id[tid]
            teacher_full_days = full_day_unavailable.get(tid, set())
            
            for s_idx, slot in slots_df.iterrows():
                # Convert numpy.int64 to regular int for matching
                slot_key = (int(slot['jour']), slot['seance'])
                slot_jour = int(slot['jour'])
                
                if slot_key in unavailable_slots:
                    # Create violation variable
                    violation = self.model.NewBoolVar(
                        f'voeux_violation_t{t_idx}_s{s_idx}'
                    )
                    
                    # violation = 1 if teacher assigned to unavailable slot
                    self.model.Add(
                        violation == self.x_surv[t_idx, s_idx]
                    )
                    
                    # Check if this is part of a FULL DAY violation
                    is_full_day = slot_jour in teacher_full_days
                    
                    violation_info = {
                        'teacher_idx': t_idx,
                        'teacher_id': tid,
                        'slot_idx': s_idx,
                        'jour': slot['jour'],
                        'seance': slot['seance'],
                        'violation_var': violation,
                        'is_full_day': is_full_day
                    }
                    
                    if is_full_day:
                        full_day_violations.append(violation_info)
                    else:
                        voeux_violations.append(violation_info)
                    
                    self.constraint_counts['voeux_soft'] += 1
        
        print(f"\n✓ Created {len(voeux_violations)} regular voeux violation variables")
        print(f"✓ Created {len(full_day_violations)} FULL DAY violation variables")
        print(f"  Teachers with voeux: {teachers_with_voeux}")
        print(f"  Teachers with FULL DAY requests: {len(full_day_unavailable)}")
        print(f"  Regular penalty: {self.config.voeux_penalty_weight} per violation")
        print(f"  FULL DAY penalty: {self.config.full_day_penalty_weight} per violation (5X higher!)")
        print(f"  ⚠️  Solver will TRY to avoid but may violate if needed for coverage")
        
        return {
            'violations': voeux_violations,
            'full_day_violations': full_day_violations
        }
    
    def add_quality_objectives(
        self,
        teacher_ids: List[int],
        slots_by_jour: Dict[int, List[int]],
        slots_df: pd.DataFrame
    ) -> Dict[str, List]:
        """Add schedule quality objectives."""
        print(f"\nAdding quality objectives...")
        
        quality_vars = {
            'active_days': [],
            'gaps': [],
            'isolated_days': [],
            'multi_session_days': [],
            'consecutive': []
        }
        
        num_teachers = len(teacher_ids)
        
        # 1. Active days
        for t_idx in range(num_teachers):
            for jour, slot_indices in slots_by_jour.items():
                works_on_day = self.model.NewBoolVar(f'works_t{t_idx}_j{jour}')
                
                daily_assignments = [self.x_surv[t_idx, s_idx] for s_idx in slot_indices]
                
                # works_on_day = 1 if any assignment on this day
                self.model.AddMaxEquality(works_on_day, daily_assignments)
                
                quality_vars['active_days'].append(works_on_day)
        
        # 2. Gaps between working days
        sorted_jours = sorted(slots_by_jour.keys())
        for t_idx in range(num_teachers):
            for i in range(1, len(sorted_jours) - 1):
                prev_jour = sorted_jours[i - 1]
                curr_jour = sorted_jours[i]
                next_jour = sorted_jours[i + 1]
                
                gap_var = self.model.NewBoolVar(f'gap_t{t_idx}_j{curr_jour}')
                
                # Gap = works before AND after, but NOT on current day
                works_prev = [self.x_surv[t_idx, s] for s in slots_by_jour[prev_jour]]
                works_curr = [self.x_surv[t_idx, s] for s in slots_by_jour[curr_jour]]
                works_next = [self.x_surv[t_idx, s] for s in slots_by_jour[next_jour]]
                
                has_prev = self.model.NewBoolVar(f'hasprev_t{t_idx}_j{curr_jour}')
                has_curr = self.model.NewBoolVar(f'hascurr_t{t_idx}_j{curr_jour}')
                has_next = self.model.NewBoolVar(f'hasnext_t{t_idx}_j{curr_jour}')
                
                self.model.AddMaxEquality(has_prev, works_prev)
                self.model.AddMaxEquality(has_curr, works_curr)
                self.model.AddMaxEquality(has_next, works_next)
                
                # gap = has_prev AND (NOT has_curr) AND has_next
                self.model.AddBoolAnd([has_prev, has_next, has_curr.Not()]).OnlyEnforceIf(gap_var)
                self.model.AddBoolOr([has_prev.Not(), has_next.Not(), has_curr]).OnlyEnforceIf(gap_var.Not())
                
                quality_vars['gaps'].append(gap_var)
        
        # 3. Isolated days (single session on a day)
        for t_idx in range(num_teachers):
            for jour, slot_indices in slots_by_jour.items():
                isolated = self.model.NewBoolVar(f'isolated_t{t_idx}_j{jour}')
                
                daily_assignments = [self.x_surv[t_idx, s_idx] for s_idx in slot_indices]
                daily_sum = sum(daily_assignments)
                
                # isolated = 1 if exactly 1 session on this day
                self.model.Add(daily_sum == 1).OnlyEnforceIf(isolated)
                self.model.Add(daily_sum != 1).OnlyEnforceIf(isolated.Not())
                
                quality_vars['isolated_days'].append(isolated)
        
        # 4. Multi-session days (2+ sessions)
        for t_idx in range(num_teachers):
            for jour, slot_indices in slots_by_jour.items():
                multi = self.model.NewBoolVar(f'multi_t{t_idx}_j{jour}')
                
                daily_assignments = [self.x_surv[t_idx, s_idx] for s_idx in slot_indices]
                daily_sum = sum(daily_assignments)
                
                # multi = 1 if 2+ sessions on this day
                self.model.Add(daily_sum >= 2).OnlyEnforceIf(multi)
                self.model.Add(daily_sum < 2).OnlyEnforceIf(multi.Not())
                
                quality_vars['multi_session_days'].append(multi)
        
        # 5. Consecutive sessions
        seance_order = ['S1', 'S2', 'S3', 'S4']
        
        for t_idx in range(num_teachers):
            for jour, slot_indices in slots_by_jour.items():
                jour_slots = slots_df.loc[slot_indices].copy()
                jour_slots = jour_slots.sort_values('seance')
                
                for i in range(len(jour_slots) - 1):
                    curr_slot = jour_slots.iloc[i]
                    next_slot = jour_slots.iloc[i + 1]
                    
                    curr_seance_idx = seance_order.index(curr_slot['seance'])
                    next_seance_idx = seance_order.index(next_slot['seance'])
                    
                    if next_seance_idx == curr_seance_idx + 1:
                        consecutive = self.model.NewBoolVar(
                            f'consec_t{t_idx}_j{jour}_s{i}'
                        )
                        
                        # consecutive = 1 if both assigned
                        self.model.AddBoolAnd([
                            self.x_surv[t_idx, curr_slot.name],
                            self.x_surv[t_idx, next_slot.name]
                        ]).OnlyEnforceIf(consecutive)
                        
                        self.model.AddBoolOr([
                            self.x_surv[t_idx, curr_slot.name].Not(),
                            self.x_surv[t_idx, next_slot.name].Not()
                        ]).OnlyEnforceIf(consecutive.Not())
                        
                        quality_vars['consecutive'].append(consecutive)
        
        print(f"✓ Quality objectives configured (active days, gaps, isolated days, multi-session, consecutive)")
        
        return quality_vars
    
    def build_all_constraints(
        self,
        teachers_df: pd.DataFrame,
        slots_df: pd.DataFrame,
        voeux_by_id: Dict[int, List[Tuple[int, str]]],
        total_needed: int,
        adjusted_quotas: Dict[int, int] = None  # NEW: Pass adjusted quotas
    ) -> Dict:
        """Build all constraints."""
        teacher_ids = teachers_df.index.tolist()
        num_teachers = len(teacher_ids)
        num_slots = len(slots_df)
        
        # 1. Create variables
        self.create_variables(num_teachers, num_slots)
        
        # 2. HARD: Coverage with flexible supervisors
        actual_total = self.add_coverage_constraints(
            slots_df, num_teachers, 
            self.config.min_supervisors_per_room,
            self.config.max_supervisors_per_room
        )
        
        # 3. Daily limit
        slots_by_jour = self.add_daily_limit(teacher_ids, slots_df)
        
        # 4. Maximum gap between working days
        self.add_maximum_gap_constraint(teacher_ids, slots_by_jour, max_gap_days=self.config.max_gap_days)
        
        # 5. Grade quota equality
        grade_quotas = self.add_grade_quota_equality(
            teacher_ids, teachers_df, num_slots, actual_total, adjusted_quotas
        )
        
        # 6. Voeux penalties
        print(f"\nAdding soft constraints...")
        voeux_penalties = self.add_voeux_soft_penalties(
            teacher_ids, slots_df, voeux_by_id
        )
        
        # 7. Quality objectives
        quality_vars = self.add_quality_objectives(
            teacher_ids, slots_by_jour, slots_df
        )
        
        print(f"\nConstraint summary:")
        for ctype, count in sorted(self.constraint_counts.items()):
            print(f"  {ctype}: {count:,}")
        
        return {
            'grade_quotas': grade_quotas,
            'voeux_penalties': voeux_penalties,
            'quality_vars': quality_vars,
            'slots_by_jour': slots_by_jour,
            'total_needed': actual_total
        }


class ExamScheduler:
    """Main scheduler class."""
    
    def __init__(self, db_path: str, config: SchedulerConfig):
        self.db_path = db_path
        self.config = config
        self.loader = DataLoader(db_path)
        print(f"\n{'='*70}")
        print(f"EXAM SCHEDULER INITIALIZED")
        print(f"{'='*70}")
        print(f"Mode: GRADE EQUALITY + SOFT VOEUX")
        print(f"{'='*70}\n")
    
    def _validate_feasibility(
        self, teachers_df, slots_df, teacher_ids, total_needed
    ):
        """Pre-solve validation to catch infeasible problems early."""
        print(f"\n{'='*70}")
        print(f"PRE-SOLVE FEASIBILITY VALIDATION")
        print(f"{'='*70}")
        
        num_teachers = len(teacher_ids)
        num_slots = len(slots_df)
        
        # Check 1: Basic capacity
        max_capacity = num_teachers * self.config.max_sessions_per_day * len(
            slots_df.groupby('jour')
        )
        
        print(f"\n1. Capacity Check:")
        print(f"   Total needed:     {total_needed}")
        print(f"   Max capacity:     {max_capacity}")
        print(f"   Utilization:      {total_needed / max_capacity * 100:.1f}%")
        
        if total_needed > max_capacity:
            raise ValueError(
                f"❌ INFEASIBLE: Need {total_needed} but max capacity is only {max_capacity}. "
                f"Reduce supervisors_per_room or increase max_sessions_per_day."
            )
        print(f"   ✓ Capacity sufficient")
        
        # Check 2: Grade distribution
        teachers_by_grade = defaultdict(list)
        for tid in teacher_ids:
            grade = teachers_df.loc[tid, 'grade']
            teachers_by_grade[grade].append(tid)
        
        print(f"\n2. Grade Distribution:")
        single_teacher_grades = []
        for grade, tids in sorted(teachers_by_grade.items()):
            print(f"   {grade:5s}: {len(tids):3d} teachers")
            if len(tids) == 1:
                single_teacher_grades.append(grade)
        
        if single_teacher_grades:
            print(f"\n   ⚠️  Warning: Grades with single teacher: {', '.join(single_teacher_grades)}")
            print(f"   → These teachers cannot be replaced if absent")
        
        # Check 3: Minimum vs needed
        min_assignments_per_teacher = max(1, total_needed // num_teachers)
        print(f"\n3. Assignment Requirements:")
        print(f"   Average needed:   {total_needed / num_teachers:.2f} per teacher")
        print(f"   Minimum per teacher: {min_assignments_per_teacher}")
        
        if min_assignments_per_teacher > self.config.max_sessions_per_day * num_slots // num_teachers:
            print(f"   ⚠️  Warning: Very tight scheduling - may be difficult to satisfy all constraints")
        
        print(f"\n✓ Pre-solve validation passed")
        print(f"{'='*70}")
    
    def generate_planning(
        self,
        session_id: int,
        progress_callback=None
    ) -> Tuple[Dict, pd.DataFrame, List[Dict], Dict]:
        """Generate optimal exam supervision planning."""
        
        progress_report(progress_callback, "Loading data from database...", 0)
        
        # Load data
        teachers_df = self.loader.load_teachers(session_id)
        slots_df = self.loader.load_slots(session_id)
        voeux_by_id = self.loader.load_voeux(session_id)
        self.loader.load_configuration(session_id, self.config)
        
        teacher_ids = teachers_df.index.tolist()
        num_teachers = len(teacher_ids)
        num_slots = len(slots_df)
        
        # Calculate total needed
        total_needed = sum(
            int(row['nb_salle']) * self.config.supervisors_per_room
            for _, row in slots_df.iterrows()
        )
        
        # Validate feasibility
        progress_report(progress_callback, "Validating problem feasibility...", 10)
        self._validate_feasibility(teachers_df, slots_df, teacher_ids, total_needed)
        
        print(f"\n{'='*70}")
        print(f"CAPACITY ANALYSIS")
        print(f"{'='*70}")
        print(f"Total surveillances needed: {total_needed}")
        
        # Calculate adjusted quotas or use custom quotas
        progress_report(progress_callback, "Calculating quotas...", 15)
        
        if self.config.use_custom_quotas and self.config.custom_quotas:
            print(f"\n📌 Using CUSTOM quotas (user-defined):")
            adjusted_quotas = self._create_teacher_quotas(
                self.config.custom_quotas,
                self._group_teachers_by_grade(teachers_df, teacher_ids)
            )
            # Display custom quotas
            for grade, quota in sorted(self.config.custom_quotas.items()):
                teachers_by_grade = self._group_teachers_by_grade(teachers_df, teacher_ids)
                count = len(teachers_by_grade.get(grade, []))
                total = quota * count
                print(f"   {grade:5s}: {quota:2d} surveillances × {count:3d} enseignants = {total:4d} total")
        else:
            print(f"\n⚙️  Calculating ADJUSTED quotas (proportional allocation):")
            adjusted_quotas = self._calculate_adjusted_quotas(
                teachers_df, total_needed, teacher_ids
            )
        
        print(f"\n✅ Buffer for absences:")
        print(f"   Grade equality flexibility: ±{self.config.grade_quota_flexibility}")
        print(f"   This allows {self.config.grade_quota_flexibility} substitution(s) within each grade if teachers are absent")
        
        # Try solving with current flexibility, retry with relaxation if infeasible
        max_attempts = 3
        current_flexibility = self.config.grade_quota_flexibility
        
        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"\n⚠️  Attempt {attempt + 1}: Relaxing constraints (flexibility = ±{current_flexibility})")
            
            progress_report(progress_callback, f"Building constraint model (attempt {attempt + 1})...", 20)
            
            # Build model
            model = cp_model.CpModel()
            builder = ConstraintBuilder(model, self.config)
            
            # Pass adjusted quotas to constraint builder
            constraint_vars = builder.build_all_constraints(
                teachers_df, slots_df, voeux_by_id, total_needed, adjusted_quotas
            )
            
            progress_report(progress_callback, "Building objective function...", 40)
            
            # Build objective
            objective_info = self._build_objective(
                model, builder,
                constraint_vars['grade_quotas'],
                constraint_vars['voeux_penalties'],
                constraint_vars['quality_vars'],
                teacher_ids, teachers_df, num_slots
            )
            
            progress_report(progress_callback, f"Solving optimization problem (attempt {attempt + 1})...", 50)
            
            # Solve
            result = self._solve(model, builder.x_surv, teacher_ids, slots_df, progress_callback)
            
            # Check if successful
            if result['status'] in ['OPTIMAL', 'FEASIBLE']:
                progress_report(progress_callback, "Analyzing solution quality...", 85)
                
                # Report objective breakdown
                if 'solver' in result:
                    self._report_objective_breakdown(
                        result['solver'], builder, objective_info, teachers_df, teacher_ids
                    )
                
                progress_report(progress_callback, "Extracting solution...", 90)
                
                assignments, report = self._extract_results(
                    result['assignments'],
                    teachers_df,
                    constraint_vars['grade_quotas'],
                    objective_info,
                    slots_df,
                    self.config.supervisors_per_room,
                    session_id
                )
                
                # ========================================
                # COMPREHENSIVE GRADE EQUALITY VERIFICATION
                # ========================================
                print(f"\n{'='*70}")
                print(f"GRADE EQUALITY VERIFICATION (uniform scaling)")
                print(f"{'='*70}")
                
                # Group assignments by grade
                grade_assignment_details = defaultdict(list)
                for tid in teacher_ids:
                    grade = teachers_df.loc[tid, 'grade']
                    num_assignments = len(result['assignments'].get(tid, []))
                    grade_assignment_details[grade].append({
                        'teacher_id': tid,
                        'count': num_assignments
                    })
                
                all_perfect_equality = True
                total_actual_assignments = 0
                
                for grade in sorted(grade_assignment_details.keys()):
                    teachers_in_grade = grade_assignment_details[grade]
                    counts = [t['count'] for t in teachers_in_grade]
                    
                    target_quota = adjusted_quotas[teachers_in_grade[0]['teacher_id']] if adjusted_quotas else 0
                    
                    min_count = min(counts)
                    max_count = max(counts)
                    avg_count = sum(counts) / len(counts)
                    total_count = sum(counts)
                    
                    total_actual_assignments += total_count
                    
                    # Check perfect equality
                    is_equal = (min_count == max_count)
                    status_icon = "✅" if is_equal else "❌"
                    
                    if not is_equal:
                        all_perfect_equality = False
                    
                    print(f"\n{status_icon} Grade {grade}:")
                    print(f"   Teachers: {len(teachers_in_grade)}")
                    print(f"   Target quota: {target_quota} per teacher (from uniform scaling)")
                    print(f"   Flexibility: ±{self.config.grade_quota_flexibility} for substitutions")
                    print(f"   Actual: Min={min_count}, Max={max_count}, Avg={avg_count:.2f}")
                    print(f"   Total for grade: {total_count} (target: {target_quota * len(teachers_in_grade)})")
                    
                    if not is_equal:
                        print(f"   ⚠️  NOT EQUAL! Variation: {max_count - min_count}")
                        # Show distribution
                        count_dist = defaultdict(int)
                        for c in counts:
                            count_dist[c] += 1
                        print(f"   Distribution: {dict(count_dist)}")
                
                print(f"\n{'='*70}")
                print(f"SUMMARY:")
                print(f"  Total surveillances assigned: {total_actual_assignments}")
                print(f"  Total required: {total_needed}")
                print(f"  Grade equality flexibility: ±{self.config.grade_quota_flexibility}")
                
                if all_perfect_equality:
                    print(f"\n✅ PERFECT GRADE EQUALITY ACHIEVED!")
                    print(f"   All teachers within each grade have identical assignments")
                    print(f"   Uniform scaling factor applied to all grades")
                    print(f"   ±{self.config.grade_quota_flexibility} flexibility allows substitutions for absences")
                else:
                    print(f"\n❌ GRADE EQUALITY VIOLATED!")
                    print(f"   Some grades have unequal distribution")
                    print(f"   This may indicate a constraint or solver issue")
                print(f"{'='*70}")
                
                progress_report(progress_callback, "Saving to database...", 95)
                
                self._save_results(session_id, assignments, teachers_df, slots_df)
                
                progress_report(progress_callback, "Planning completed!", 100)
                
                # Prepare slot info
                slot_info = []
                for _, slot in slots_df.iterrows():
                    slot_info.append({
                        'slot_id': slot['slot_id'],
                        'creneau_id': slot['creneau_id'],
                        'jour': slot['jour'],
                        'seance': slot['seance'],
                        'date': slot['date'],
                        'time': slot['time'],
                        'nb_rooms': int(slot['nb_salle'])
                    })
                
                return assignments, teachers_df, slot_info, report
            
            # If infeasible and auto-relax is enabled, try again with more flexibility
            if result['status'] == 'INFEASIBLE' and self.config.auto_relax_if_infeasible and attempt < max_attempts - 1:
                current_flexibility += 1
                self.config.grade_quota_flexibility = current_flexibility
                print(f"\n⚠️  Problem INFEASIBLE. Retrying with flexibility ±{current_flexibility}...")
                continue
            
            # If we've exhausted attempts or it's not infeasible, break
            break
        
        # If we get here, all attempts failed
        print(f"\n❌ SOLVER FAILED: {result['status']}")
        print(f"   Try adjusting parameters or check data consistency")
        return None

    def _group_teachers_by_grade(
        self, 
        teachers_df: pd.DataFrame, 
        teacher_ids: List[int]
    ) -> Dict[str, List[int]]:
        """Group teachers by grade."""
        teachers_by_grade = defaultdict(list)
        for tid in teacher_ids:
            grade = teachers_df.loc[tid, 'grade']
            teachers_by_grade[grade].append(tid)
        return dict(teachers_by_grade)
    
    def _calculate_original_capacity(
        self, 
        teachers_by_grade: Dict[str, List[int]]
    ) -> Tuple[int, Dict[str, Dict]]:
        """Calculate original capacity from base quotas."""
        original_capacity = 0
        grade_info = {}
        
        print(f"\n  ORIGINAL CAPACITY (from direction quotas):")
        for grade in sorted(teachers_by_grade.keys()):
            num_teachers = len(teachers_by_grade[grade])
            base_quota = DEFAULT_QUOTAS.get(grade, 5)
            capacity = base_quota * num_teachers
            original_capacity += capacity
            
            grade_info[grade] = {
                'num_teachers': num_teachers,
                'base_quota': base_quota,
                'capacity': capacity
            }
            
            print(f"    {grade:5s}: {num_teachers:3d} teachers × {base_quota:2d} = {capacity:3d}")
        
        print(f"  Total original capacity: {original_capacity}")
        return original_capacity, grade_info
    
    def _apply_scaling(
        self, 
        grade_info: Dict[str, Dict], 
        scaling_factor: float
    ) -> Dict[str, float]:
        """Apply proportional scaling to base quotas."""
        print(f"\n  SCALED QUOTAS (proportional):")
        grade_quotas_float = {}
        
        for grade in sorted(grade_info.keys()):
            base_quota = grade_info[grade]['base_quota']
            scaled_quota = base_quota * scaling_factor
            grade_quotas_float[grade] = scaled_quota
            print(f"    {grade:5s}: {base_quota:2d} × {scaling_factor:.4f} = {scaled_quota:.2f}")
        
        return grade_quotas_float
    
    def _round_with_largest_remainder(
        self, 
        grade_quotas_float: Dict[str, float], 
        grade_info: Dict[str, Dict], 
        total_needed: int
    ) -> Dict[str, int]:
        """
        Round quotas using Hamilton method (Largest Remainder Method).
        Ensures fair distribution and exact total match.
        
        CRITICAL: Distributes surplus ONE surveillance at a time to preserve proportions!
        """
        grade_quotas = {}
        floored_total = 0
        remainders = []
        
        print(f"\n  ROUNDING WITH LARGEST REMAINDER METHOD:")
        print(f"  {'='*66}")
        
        # Step 1: Floor all quotas
        for grade in sorted(grade_info.keys()):
            quota_float = grade_quotas_float[grade]
            quota_floor = int(quota_float)
            remainder = quota_float - quota_floor
            
            grade_quotas[grade] = quota_floor
            num_teachers = grade_info[grade]['num_teachers']
            floored_total += quota_floor * num_teachers
            
            remainders.append((grade, num_teachers, remainder))
            print(f"    {grade:5s}: {quota_float:.2f} → {quota_floor} per teacher "
                  f"(remainder: {remainder:.3f})")
        
        print(f"\n  Floored total: {floored_total} × all teachers = {floored_total}")
        print(f"  Target total: {total_needed}")
        
        # Step 2: Distribute surplus ONE AT A TIME by largest remainder
        surplus = total_needed - floored_total
        
        if surplus > 0:
            print(f"\n  Distributing {surplus} extra surveillances:")
            print(f"  (Giving +1 to ALL teachers in grades with highest remainders)")
            
            # Sort by remainder descending
            remainders.sort(key=lambda x: x[2], reverse=True)
            
            distributed = 0
            for grade, num_teachers, remainder in remainders:
                if distributed >= surplus:
                    break
                
                # Can we give +1 to ALL teachers in this grade?
                if distributed + num_teachers <= surplus:
                    grade_quotas[grade] += 1
                    distributed += num_teachers
                    print(f"    {grade:5s}: +1 per teacher (all {num_teachers} teachers) "
                          f"= +{num_teachers} total | Remainder was {remainder:.3f}")
                else:
                    # Not enough surplus for whole grade - skip to preserve equality
                    remaining = surplus - distributed
                    print(f"    {grade:5s}: SKIPPED (need {num_teachers}, only {remaining} left) "
                          f"| Remainder: {remainder:.3f}")
            
            if distributed == surplus:
                print(f"\n  ✅ Perfect distribution: {distributed} = {surplus}")
            else:
                print(f"\n  ⚠️  Distributed {distributed}/{surplus} (some grades skipped to maintain equality)")
        
        elif surplus < 0:
            print(f"\n  ⚠️  WARNING: Over-allocated by {-surplus}!")
        
        # Step 3: Verify final result
        final_total = sum(grade_quotas[g] * grade_info[g]['num_teachers'] 
                         for g in grade_quotas.keys())
        print(f"\n  FINAL RESULT:")
        print(f"  {'='*66}")
        for grade in sorted(grade_quotas.keys()):
            quota = grade_quotas[grade]
            num_teachers = grade_info[grade]['num_teachers']
            total = quota * num_teachers
            print(f"    {grade:5s}: {quota:2d} per teacher × {num_teachers:3d} = {total:3d} total")
        
        print(f"\n  Final total: {final_total} (target: {total_needed})")
        if final_total == total_needed:
            print(f"  ✅ EXACT MATCH!")
        else:
            print(f"  ⚠️  Off by {final_total - total_needed:+d}")
        print(f"  {'='*66}")
        
        return grade_quotas
    
    def _create_teacher_quotas(
        self, 
        grade_quotas: Dict[str, int], 
        teachers_by_grade: Dict[str, List[int]]
    ) -> Dict[int, int]:
        """Create per-teacher quota dictionary."""
        adjusted_quotas = {}
        for grade, tids in teachers_by_grade.items():
            quota = grade_quotas[grade]
            for tid in tids:
                adjusted_quotas[tid] = quota
        return adjusted_quotas
    
    def _calculate_adjusted_quotas(
    self, 
    teachers_df: pd.DataFrame, 
    total_needed: int,
    teacher_ids: List[int]
) -> Dict[int, int]:
        """
        Calculate adjusted quotas with PROPORTIONAL scaling from DEFAULT_QUOTAS.
        Maintains grade hierarchy by scaling all quotas proportionally.
        """
        print(f"\n{'='*70}")
        print(f"QUOTA CALCULATION - PROPORTIONAL SCALING (Grade Hierarchy)")
        print(f"{'='*70}")
        print(f"  Target total: {total_needed} surveillances")
        print(f"  Total teachers: {len(teacher_ids)}")
        print(f"  Average: {total_needed / len(teacher_ids):.2f} per teacher")
        
        # Step 1: Group teachers by grade
        teachers_by_grade = self._group_teachers_by_grade(teachers_df, teacher_ids)
        
        # Step 2: Calculate original capacity from DEFAULT_QUOTAS
        original_total = 0
        grade_info = {}
        
        print(f"\n  Base quotas from DEFAULT_QUOTAS:")
        for grade, tids in sorted(teachers_by_grade.items()):
            base_quota = DEFAULT_QUOTAS.get(grade, 5)
            num_teachers = len(tids)
            grade_capacity = base_quota * num_teachers
            original_total += grade_capacity
            
            grade_info[grade] = {
                'num_teachers': num_teachers,
                'base_quota': base_quota,
                'base_capacity': grade_capacity
            }
            
            print(f"    {grade:5s}: {num_teachers:3d} teachers × {base_quota} = {grade_capacity} capacity")
        
        print(f"\n  Total base capacity: {original_total}")
        print(f"  Total needed: {total_needed}")
        
        # Step 3: Calculate uniform scaling factor
        scaling_factor = total_needed / original_total
        print(f"  Scaling factor: {scaling_factor:.4f} ({(1-scaling_factor)*100:.1f}% reduction)")
        
        # Step 4: Scale each grade's quota proportionally (FLOAT values)
        grade_quotas_float = {}
        
        print(f"\n  Scaled quotas (maintaining grade hierarchy):")
        for grade, info in sorted(grade_info.items()):
            scaled_quota = info['base_quota'] * scaling_factor
            grade_quotas_float[grade] = scaled_quota
            
            scaled_total = scaled_quota * info['num_teachers']
            reduction_pct = (1 - scaling_factor) * 100
            
            print(f"    {grade:5s}: {info['base_quota']:2d} → {scaled_quota:.1f} "
                f"(-{reduction_pct:.0f}%) | {info['num_teachers']:3d} ens. | "
                f"Total: {scaled_total:.0f}")
        
        # Step 5: Round quotas using Largest Remainder Method (Hamilton method)
        # This ensures we hit the exact total while maintaining fairness
        grade_quotas_rounded = self._round_with_largest_remainder(
            grade_quotas_float, grade_info, total_needed
        )
        
        # Step 6: Create per-teacher quotas (all teachers in same grade get same quota)
        adjusted_quotas = {}
        
        print(f"\n  Final integer quotas (after rounding):")
        final_total = 0
        
        for grade, quota in sorted(grade_quotas_rounded.items()):
            num_teachers = grade_info[grade]['num_teachers']
            grade_total = quota * num_teachers
            final_total += grade_total
            
            # Assign to all teachers in this grade
            for tid in teachers_by_grade[grade]:
                adjusted_quotas[tid] = quota
            
            print(f"    {grade:5s}: {quota:2d} per teacher × {num_teachers:3d} = {grade_total:3d} total")
        
        print(f"\n  Final total: {final_total} (target: {total_needed})")
        
        if final_total == total_needed:
            print(f"  ✅ EXACT MATCH!")
        else:
            diff = final_total - total_needed
            print(f"  ⚠️  Off by {diff:+d} (will adjust in next iteration)")
        
        print(f"{'='*70}")
        
        return adjusted_quotas
    
    def _build_objective(
        self, model, builder, grade_quotas, voeux_penalties,
        quality_vars, teacher_ids, teachers_df, num_slots
    ):
        """Build multi-objective function with optimized weights."""
        print(f"\n{'='*70}")
        print(f"BUILDING MULTI-OBJECTIVE FUNCTION")
        print(f"{'='*70}")
        
        objective_terms = []
        
        print(f"\n0. Grade quota deviations (weight: {self.config.quota_deviation_penalty})")
        
        quota_deviation_vars = []
        for grade, info in grade_quotas.items():
            quota_var = info['quota_var']
            target = info['ideal']
            
            # Create deviation variable: |actual - target|
            deviation_var = model.NewIntVar(0, num_slots, f'quota_dev_{grade}')
            
            # deviation = max(quota - target, target - quota, 0)
            # This ensures deviation is always non-negative
            model.AddMaxEquality(deviation_var, [
                quota_var - target,
                target - quota_var,
                0
            ])
            
            quota_deviation_vars.append(deviation_var)
        
        if quota_deviation_vars:
            quota_deviation_penalty = sum(quota_deviation_vars) * self.config.quota_deviation_penalty
            objective_terms.append(quota_deviation_penalty)
            print(f"   ✓ Added {len(quota_deviation_vars)} quota deviation penalties")
        
        print(f"\n1. Voeux violations:")
        
        # Regular voeux violations (single session unavailability)
        voeux_violations = voeux_penalties.get('violations', [])
        if voeux_violations:
            voeux_penalty_sum = sum(v['violation_var'] for v in voeux_violations)
            objective_terms.append(voeux_penalty_sum * self.config.voeux_penalty_weight)
            print(f"   ✓ Regular violations: {len(voeux_violations)} (weight: {self.config.voeux_penalty_weight:,})")
        else:
            print(f"   ℹ️  No regular voeux violations to track")
        
        full_day_violations = voeux_penalties.get('full_day_violations', [])
        if full_day_violations:
            full_day_penalty_sum = sum(v['violation_var'] for v in full_day_violations)
            objective_terms.append(full_day_penalty_sum * self.config.full_day_penalty_weight)
            print(f"   ✓ Full day violations: {len(full_day_violations)} (weight: {self.config.full_day_penalty_weight:,})")
        
        print(f"\n2. Schedule quality:")
        
        isolated_vars = quality_vars.get('isolated_days', [])
        if isolated_vars:
            isolated_penalty = sum(isolated_vars) * self.config.isolated_day_penalty
            objective_terms.append(isolated_penalty)
            print(f"   a) Isolated days (weight: {self.config.isolated_day_penalty})")
        
        gap_vars = quality_vars.get('gaps', [])
        if gap_vars:
            gap_penalty = sum(gap_vars) * self.config.gap_penalty
            objective_terms.append(gap_penalty)
            print(f"   b) Gaps (weight: {self.config.gap_penalty})")
        
        active_vars = quality_vars.get('active_days', [])
        if active_vars:
            active_penalty = sum(active_vars) * self.config.active_day_penalty
            objective_terms.append(active_penalty)
            print(f"   c) Active days (weight: {self.config.active_day_penalty})")
        
        if hasattr(self, 'extra_supervisors') and self.extra_supervisors:
            extra_penalty = sum(self.extra_supervisors.values()) * self.config.extra_supervisor_penalty
            objective_terms.append(extra_penalty)
            print(f"   d) Extra supervisors (weight: {self.config.extra_supervisor_penalty})")
        
        multi_vars = quality_vars.get('multi_session_days', [])
        if multi_vars:
            multi_bonus = sum(multi_vars) * self.config.multi_session_bonus
            objective_terms.append(multi_bonus)
            print(f"   e) Multi-session bonus: {self.config.multi_session_bonus}")
        
        consecutive_vars = quality_vars.get('consecutive', [])
        if consecutive_vars:
            consecutive_bonus = sum(consecutive_vars) * self.config.consecutive_bonus
            objective_terms.append(consecutive_bonus)
            print(f"   f) Consecutive bonus: {self.config.consecutive_bonus}")
        if objective_terms:
            model.Minimize(sum(objective_terms))
            print(f"\n{'='*70}")
            print(f"✅ OBJECTIVE FUNCTION BUILT")
            print(f"{'='*70}")
            print(f"  Total objective terms: {len(objective_terms)}")
            print(f"\n  Optimization hierarchy (by penalty weight):")
            print(f"    0. Quota deviations    (weight: {self.config.quota_deviation_penalty:,}) ← HIGHEST PRIORITY")
            print(f"    1. Avoid isolated days (weight: {self.config.isolated_day_penalty:,})")
            print(f"    2. Voeux respect       (weight: {self.config.voeux_penalty_weight:,})")
            print(f"    3. Minimize gaps       (weight: {self.config.gap_penalty:,})")
            print(f"    4. Minimize active days(weight: {self.config.active_day_penalty:,})")
            print(f"    5. Reward multi-session(bonus: {self.config.multi_session_bonus:,})")
            print(f"    6. Reward consecutive  (bonus: {self.config.consecutive_bonus:,})")
            print(f"{'='*70}")
        else:
            # Fallback: minimize total assignments
            total_assignments = []
            for t_idx in range(len(teacher_ids)):
                for s_idx in range(num_slots):
                    if (t_idx, s_idx) in builder.x_surv:
                        total_assignments.append(builder.x_surv[t_idx, s_idx])
            
            if total_assignments:
                model.Minimize(sum(total_assignments))
            else:
                model.Minimize(0)
            
            print(f"\n⚠️  No soft objectives - using feasibility objective")
        
        return {
            'voeux_violations': voeux_violations,
            'full_day_violations': voeux_penalties.get('full_day_violations', []),
            'quality_metrics': quality_vars,
            'grade_quotas': grade_quotas
        }
    
    def _report_objective_breakdown(
        self, solver, builder, objective_info, teachers_df, teacher_ids
    ):
        """Report which objective terms contribute most to final objective value."""
        print(f"\n{'='*70}")
        print(f"OBJECTIVE BREAKDOWN")
        print(f"{'='*70}")
        
        breakdown = []
        total_objective = solver.ObjectiveValue()
        
        # 1. Calculate quota deviations
        grade_quotas = objective_info.get('grade_quotas', {})
        if grade_quotas:
            total_quota_penalty = 0
            print(f"\n1. Grade Quota Deviations:")
            for grade, info in sorted(grade_quotas.items()):
                quota_var = info['quota_var']
                target = info['ideal']
                actual = solver.Value(quota_var)
                deviation = abs(actual - target)
                penalty = deviation * self.config.quota_deviation_penalty
                total_quota_penalty += penalty
                
                if deviation > 0:
                    print(f"   {grade:5s}: actual={actual}, target={target}, deviation={deviation:+d}, penalty={penalty:,}")
            
            if total_quota_penalty == 0:
                print(f"   ✓ Perfect quota compliance!")
            else:
                print(f"   Total quota penalty: {total_quota_penalty:,}")
            breakdown.append(('Quota Deviations', total_quota_penalty))
        
        # 2. Calculate voeux violations
        voeux_violations = objective_info.get('voeux_violations', [])
        full_day_violations = objective_info.get('full_day_violations', [])
        
        if voeux_violations or full_day_violations:
            # Regular violations
            regular_voeux_penalty = 0
            num_regular = 0
            if voeux_violations:
                num_regular = sum(solver.Value(v['violation_var']) for v in voeux_violations)
                regular_voeux_penalty = num_regular * self.config.voeux_penalty_weight
            
            # Full day violations
            full_day_voeux_penalty = 0
            num_full_day = 0
            if full_day_violations:
                num_full_day = sum(solver.Value(v['violation_var']) for v in full_day_violations)
                full_day_voeux_penalty = num_full_day * self.config.full_day_penalty_weight
            
            total_voeux_penalty = regular_voeux_penalty + full_day_voeux_penalty
            
            print(f"\n2. Voeux Violations:")
            if num_regular > 0:
                print(f"   Regular: {num_regular} violations, penalty={regular_voeux_penalty:,}")
            if num_full_day > 0:
                print(f"   FULL DAY: {num_full_day} violations, penalty={full_day_voeux_penalty:,}")
                print(f"   ⚠️  CRITICAL: Teachers assigned on days they requested completely off!")
            
            print(f"   Total voeux penalty: {total_voeux_penalty:,}")
            breakdown.append(('Voeux Violations', total_voeux_penalty))
        
        # 3. Calculate quality metrics
        quality_vars = objective_info.get('quality_metrics', {})
        
        isolated_vars = quality_vars.get('isolated_days', [])
        if isolated_vars:
            num_isolated = sum(solver.Value(v) for v in isolated_vars)
            isolated_penalty = num_isolated * self.config.isolated_day_penalty
            print(f"\n3. Isolated Days: {num_isolated} days, penalty={isolated_penalty:,}")
            breakdown.append(('Isolated Days', isolated_penalty))
        
        gap_vars = quality_vars.get('gaps', [])
        if gap_vars:
            num_gaps = sum(solver.Value(v) for v in gap_vars)
            gap_penalty = num_gaps * self.config.gap_penalty
            print(f"\n4. Day Gaps: {num_gaps} gaps, penalty={gap_penalty:,}")
            breakdown.append(('Day Gaps', gap_penalty))
        
        active_vars = quality_vars.get('active_days', [])
        if active_vars:
            num_active = sum(solver.Value(v) for v in active_vars)
            active_penalty = num_active * self.config.active_day_penalty
            print(f"\n5. Active Days: {num_active} days, penalty={active_penalty:,}")
            breakdown.append(('Active Days', active_penalty))
        
        multi_vars = quality_vars.get('multi_session_days', [])
        if multi_vars:
            num_multi = sum(solver.Value(v) for v in multi_vars)
            multi_bonus = num_multi * self.config.multi_session_bonus
            print(f"\n6. Multi-Session Days: {num_multi} days, bonus={multi_bonus:,}")
            breakdown.append(('Multi-Session Bonus', multi_bonus))
        
        consecutive_vars = quality_vars.get('consecutive', [])
        if consecutive_vars:
            num_consecutive = sum(solver.Value(v) for v in consecutive_vars)
            consecutive_bonus = num_consecutive * self.config.consecutive_bonus
            print(f"\n7. Consecutive Sessions: {num_consecutive} pairs, bonus={consecutive_bonus:,}")
            breakdown.append(('Consecutive Bonus', consecutive_bonus))
        
        # Summary
        print(f"\n{'='*70}")
        print(f"OBJECTIVE SUMMARY:")
        print(f"{'='*70}")
        
        for name, value in breakdown:
            pct = (abs(value) / total_objective * 100) if total_objective != 0 else 0
            print(f"  {name:25s}: {value:15,.0f} ({pct:5.1f}%)")
        
        print(f"  {'─'*44}")
        print(f"  {'Total Objective':25s}: {total_objective:15,.0f}")
        print(f"{'='*70}")
    
    def _solve(self, model, x_surv, teacher_ids, slots_df, progress_callback=None):
        """Solve the optimization model."""
        print(f"\n{'='*70}")
        print(f"SOLVING OPTIMIZATION MODEL")
        print(f"{'='*70}")
        
        # Configure solver for optimal solution
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.max_solve_time
        solver.parameters.num_search_workers = self.config.num_search_workers

        # NEW: Optimize for best solution quality
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True  # Enable preprocessing
        solver.parameters.linearization_level = 2    # Aggressive linearization
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH  # Try multiple strategies

        # NEW: Focus on finding optimal solution
        solver.parameters.optimize_with_core = True  # Use core-guided optimization
        solver.parameters.stop_after_first_solution = False  # Don't stop early

        print(f"\n{'='*70}")
        print(f"SOLVER CONFIGURATION (OPTIMIZED)")
        print(f"{'='*70}")
        print(f"  Max time: {self.config.max_solve_time}s")
        print(f"  Workers: {self.config.num_search_workers}")
        print(f"  Strategy: Portfolio (tries multiple approaches)")
        print(f"  Presolve: Enabled (reduces problem size)")
        print(f"  Linearization: Level 2 (aggressive)")
        print(f"  Core-guided: Enabled (better optimal solutions)")
        print(f"{'='*70}")
        
        
        print(f"\nStarting solver... (this may take several minutes)")
        print(f"{'='*70}\n")
        
        start_time = datetime.now()
        status = solver.Solve(model)
        end_time = datetime.now()
        
        solve_time = (end_time - start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"SOLVER RESULTS")
        print(f"{'='*70}")
        
        status_names = {
            cp_model.OPTIMAL: 'OPTIMAL',
            cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE',
            cp_model.MODEL_INVALID: 'MODEL_INVALID',
            cp_model.UNKNOWN: 'UNKNOWN'
        }
        
        status_name = status_names.get(status, f'UNKNOWN({status})')
        
        print(f"  Status:          {status_name}")
        print(f"  Solve time:      {solve_time:.2f}s")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(f"  Objective value: {solver.ObjectiveValue():.0f}")
            print(f"  Branches:        {solver.NumBranches():,}")
            print(f"  Conflicts:       {solver.NumConflicts():,}")
            
            if status == cp_model.OPTIMAL:
                print(f"\n✓ Found OPTIMAL solution!")
            else:
                print(f"\n✓ Found FEASIBLE solution (may not be optimal)")
            
            # Extract assignments
            assignments = {}
            for t_idx, tid in enumerate(teacher_ids):
                teacher_slots = []
                for s_idx, _ in slots_df.iterrows():
                    if solver.Value(x_surv[t_idx, s_idx]) == 1:
                        teacher_slots.append(s_idx)
                
                if teacher_slots:
                    assignments[tid] = teacher_slots
            
            print(f"\nAssignments extracted for {len(assignments)} teachers")
            
            return {
                'status': status_name,
                'solve_time': solve_time,
                'objective': solver.ObjectiveValue(),
                'assignments': assignments,
                'solver': solver
            }
        
        else:
            print(f"\n❌ Solver did not find a solution")
            
            if status == cp_model.INFEASIBLE:
                print(f"\n  Possible causes:")
                print(f"    - Grade quotas too rigid for available slots")
                print(f"    - Coverage requirements impossible to meet")
                print(f"    - Too many voeux conflicts")
                print(f"\n  Suggestions:")
                print(f"    - Increase grade_quota_flexibility")
                print(f"    - Reduce supervisors_per_room")
                print(f"    - Check data consistency")
            
            return {
                'status': status_name,
                'solve_time': solve_time,
                'assignments': None
            }
    
    def _extract_results(
        self, assignments, teachers_df, grade_quotas,
        objective_info, slots_df, supervisors_per_room, session_id
    ):
        """Extract and analyze results with detailed quality metrics."""
        print(f"\n{'='*70}")
        print(f"EXTRACTING SOLUTION RESULTS")
        print(f"{'='*70}")
        
        # Calculate assignments per teacher
        assignments_per_teacher = {}
        for tid, slot_indices in assignments.items():
            assignments_per_teacher[tid] = len(slot_indices)
        
        # Group by grade
        grade_stats = defaultdict(list)
        for tid in teachers_df.index:
            grade = teachers_df.loc[tid, 'grade']
            count = assignments_per_teacher.get(tid, 0)
            grade_stats[grade].append(count)
        
        print(f"\n{'='*70}")
        print(f"GRADE QUOTA ACHIEVEMENT")
        print(f"{'='*70}")
        print(f"{'Grade':<6} {'Teachers':<10} {'Min':<6} {'Max':<6} {'Avg':<8} {'Target':<8} {'Status':<10}")
        print(f"{'-'*70}")
        
        for grade in sorted(grade_stats.keys()):
            counts = grade_stats[grade]
            min_c = min(counts)
            max_c = max(counts)
            avg_c = sum(counts) / len(counts)
            target = grade_quotas[grade]['ideal']
            
            # Check equality
            if min_c == max_c:
                status = "✓ EQUAL"
            elif max_c - min_c <= 1:
                status = "≈ CLOSE"
            else:
                status = f"✗ VARIED"
            
            print(f"{grade:<6} {len(counts):<10} {min_c:<6} {max_c:<6} "
                  f"{avg_c:<8.2f} {target:<8} {status:<10}")
        
        print(f"{'-'*70}")
        
        # ========================================
        # QUALITY METRICS ANALYSIS
        # ========================================
        print(f"\n{'='*70}")
        print(f"SCHEDULE QUALITY ANALYSIS")
        print(f"{'='*70}")
        
        # Analyze each teacher's schedule
        quality_stats = {
            'isolated_days': 0,
            'multi_session_days': 0,
            'consecutive_pairs': 0,
            'gaps': 0,
            'total_active_days': 0
        }
        
        teacher_quality_details = []
        
        for tid, slot_indices in assignments.items():
            if not slot_indices:
                continue
            
            # Group slots by day
            slots_by_day = defaultdict(list)
            for s_idx in slot_indices:
                slot = slots_df.loc[s_idx]
                jour = slot['jour']
                seance = slot['seance']
                slots_by_day[jour].append((s_idx, seance))
            
            # Calculate metrics for this teacher
            active_days = len(slots_by_day)
            isolated = sum(1 for slots in slots_by_day.values() if len(slots) == 1)
            multi_session = sum(1 for slots in slots_by_day.values() if len(slots) >= 2)
            
            # Count consecutive sessions
            consecutive = 0
            for jour, day_slots in slots_by_day.items():
                seances = sorted([s[1] for s in day_slots])
                seance_order = ['S1', 'S2', 'S3', 'S4']
                for i in range(len(seances) - 1):
                    try:
                        curr_idx = seance_order.index(seances[i])
                        next_idx = seance_order.index(seances[i + 1])
                        if next_idx == curr_idx + 1:
                            consecutive += 1
                    except ValueError:
                        continue
            
            # Count gaps (days between first and last working day with no work)
            if active_days > 1:
                working_jours = sorted(slots_by_day.keys())
                gaps = 0
                for i in range(1, len(working_jours)):
                    gap_size = working_jours[i] - working_jours[i-1] - 1
                    if gap_size > 0:
                        gaps += 1
            else:
                gaps = 0
            
            quality_stats['isolated_days'] += isolated
            quality_stats['multi_session_days'] += multi_session
            quality_stats['consecutive_pairs'] += consecutive
            quality_stats['gaps'] += gaps
            quality_stats['total_active_days'] += active_days
            
            teacher_quality_details.append({
                'teacher_id': tid,
                'active_days': active_days,
                'isolated': isolated,
                'multi_session': multi_session,
                'consecutive': consecutive,
                'gaps': gaps
            })
        
        # Display summary
        num_teachers_with_assignments = len([t for t in teacher_quality_details if t['active_days'] > 0])
        
        if num_teachers_with_assignments > 0:
            print(f"\nQuality Metrics Summary:")
            print(f"  Teachers with assignments: {num_teachers_with_assignments}")
            print(f"  Average active days: {quality_stats['total_active_days'] / num_teachers_with_assignments:.2f}")
            print(f"\n  ✓ Multi-session days:   {quality_stats['multi_session_days']:4d} (GOOD - sessions grouped)")
            print(f"  ✓ Consecutive pairs:    {quality_stats['consecutive_pairs']:4d} (GOOD - S1→S2, S3→S4)")
            print(f"  ⚠️  Isolated days:        {quality_stats['isolated_days']:4d} (BAD - single session days)")
            print(f"  ⚠️  Gaps between days:    {quality_stats['gaps']:4d} (BAD - non-consecutive)")
            
            # Show best schedules
            sorted_by_quality = sorted(
                teacher_quality_details,
                key=lambda x: (x['isolated'], x['gaps'], -x['multi_session'], -x['consecutive'])
            )
            
            print(f"\n  🏆 Best schedules (most compact):")
            for t in sorted_by_quality[:3]:
                if t['active_days'] > 0:
                    grade = teachers_df.loc[t['teacher_id'], 'grade']
                    print(f"    Teacher {t['teacher_id']} ({grade}): "
                          f"{t['active_days']} days, {t['multi_session']} multi, "
                          f"{t['consecutive']} consec, {t['isolated']} isolated, {t['gaps']} gaps")
        
        # Voeux violations
        voeux_violations = objective_info.get('voeux_violations', [])
        
        print(f"\n{'='*70}")
        print(f"VOEUX VIOLATIONS")
        print(f"{'='*70}")
        print(f"  Potential violations tracked: {len(voeux_violations)}")
        print(f"  (Actual violations would need solver variable values)")
        
        # Prepare enhanced report
        report = {
            'session_id': session_id,
            'total_teachers': len(teachers_df),
            'total_slots': len(slots_df),
            'total_assignments': sum(assignments_per_teacher.values()),
            'grade_stats': {
                grade: {
                    'teachers': len(counts),
                    'min': min(counts),
                    'max': max(counts),
                    'avg': sum(counts) / len(counts),
                    'target': grade_quotas[grade]['ideal']
                }
                for grade, counts in grade_stats.items()
            },
            'quality_stats': quality_stats if num_teachers_with_assignments > 0 else {},
            'voeux_tracked': len(voeux_violations)
        }
        
        print(f"\n✓ Results extracted successfully")
        
        return assignments, report
    
    def _save_results(self, session_id, assignments, teachers_df, slots_df):
        """Save results to database."""
        print(f"\n{'='*70}")
        print(f"SAVING RESULTS TO DATABASE")
        print(f"{'='*70}")
        
        try:
            db = DatabaseManager(self.db_path)
            
            # Convert assignments format from {teacher_id: [slot_indices]} 
            # to {teacher_id: {'surveillant': [{'slot_id': ...}]}} for save_assignments
            formatted_assignments = {}
            for teacher_id, slot_indices in assignments.items():
                formatted_assignments[teacher_id] = {
                    'surveillant': [{'slot_id': slot_idx} for slot_idx in slot_indices]
                }
            
            # Build slot_info from slots_df
            slot_info = []
            for idx, slot in slots_df.iterrows():
                slot_info.append({
                    'slot_id': slot['slot_id'],
                    'creneau_id': int(slot['creneau_id']),
                    'date': slot['date'],
                    'time': slot['time'],
                    'jour': slot['jour'],
                    'seance': slot['seance'],
                    'nb_rooms': int(slot['nb_salle'])
                })
            
            # Use the existing save_assignments method which handles clearing and saving
            print(f"\nSaving {sum(len(slots) for slots in assignments.values())} assignments...")
            saved_count = db.save_assignments(session_id, formatted_assignments, slot_info, teachers_df)
            
            print(f"✓ Saved {saved_count} surveillances to database")
            
            # Calculate satisfaction if available
            if analyze_teacher_satisfaction:
                print(f"\nCalculating teacher satisfaction...")
                try:
                    # This would need the full implementation
                    print(f"  (Satisfaction analysis would run here)")
                except Exception as e:
                    print(f"  ⚠️  Satisfaction calculation failed: {e}")
            
            print(f"\n✓ Database save completed")
            
        except Exception as e:
            print(f"\n❌ Error saving to database: {e}")
            raise


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_planning_from_db(
    session_id: int,
    db_path: str = "planning.db",
    min_supervisors_per_room: int = 2,
    max_supervisors_per_room: int = 3,
    supervisors_per_room: int = 2,
    max_sessions_per_day: int = 4,
    max_solve_time: float = 300.0,
    voeux_penalty_weight: int = 10000,
    grade_quota_flexibility: int = 0,
    isolated_day_penalty: int = 15000,
    gap_penalty: int = 8000,
    active_day_penalty: int = 100,
    extra_supervisor_penalty: int = 200,
    multi_session_bonus: int = -500,
    consecutive_bonus: int = -300,
    max_gap_days: int = 1,
    use_custom_quotas: bool = False,
    custom_quotas: Optional[Dict[str, int]] = None,
    progress_callback=None,
    **kwargs
) -> Optional[Tuple[Dict, pd.DataFrame, List[Dict], Dict]]:
    """
    
    """
    config = SchedulerConfig(
        min_supervisors_per_room=min_supervisors_per_room,
        max_supervisors_per_room=max_supervisors_per_room,
        supervisors_per_room=supervisors_per_room,
        max_sessions_per_day=max_sessions_per_day,
        max_solve_time=max_solve_time,
        voeux_penalty_weight=voeux_penalty_weight,
        grade_quota_flexibility=grade_quota_flexibility,
        isolated_day_penalty=isolated_day_penalty,
        gap_penalty=gap_penalty,
        active_day_penalty=active_day_penalty,
        extra_supervisor_penalty=extra_supervisor_penalty,
        multi_session_bonus=multi_session_bonus,
        consecutive_bonus=consecutive_bonus,
        max_gap_days=max_gap_days,
        use_custom_quotas=use_custom_quotas,
        custom_quotas=custom_quotas
    )
    
    scheduler = ExamScheduler(db_path, config)
    
    try:
        result = scheduler.generate_planning(session_id, progress_callback)
        
        if result:
            print(f"\n{'='*70}")
            print(f"PLANNING GENERATION SUCCESSFUL")
            print(f"{'='*70}")
            print(f"✓ Check database for saved assignments")
            print(f"✓ Review voeux violations if any")
            print(f"✓ Verify grade quota equality")
            print(f"{'='*70}\n")
        
        return result
        
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"ERROR DURING PLANNING GENERATION")
        print(f"{'='*70}")
        print(f"❌ {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*70}\n")
        return None


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Command-line interface."""
    
    parser = argparse.ArgumentParser(
        description='Generate exam supervision planning with grade equality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

        """
    )
    
    parser.add_argument(
        '--session', type=int, required=True,
        help='Session ID'
    )
    parser.add_argument(
        '--time', type=float, default=300.0,
        help='Max solve time in seconds (default: 300)'
    )
    parser.add_argument(
        '--db', type=str, default='planning.db',
        help='Database path (default: planning.db)'
    )
    parser.add_argument(
        '--supervisors', type=int, default=2,
        help='Supervisors per room (default: 2)'
    )
    parser.add_argument(
        '--max-daily', type=int, default=4,
        help='Max sessions per day (default: 4)'
    )
    parser.add_argument(
        '--voeux-weight', type=int, default=1000,
        help='Penalty weight for voeux violations (default: 1000)'
    )
    parser.add_argument(
        '--grade-flex', type=int, default=0,
        help='Grade quota flexibility ±N (default: 0 = strict equality)'
    )
    parser.add_argument(
        '--workers', type=int, default=8,
        help='Number of search workers (default: 8)'
    )
    
    args = parser.parse_args()
    
    print(f"""
{'='*70}
EXAM SCHEDULER - GRADE EQUALITY MODE
{'='*70}
Session:              {args.session}
Database:             {args.db}
Supervisors/room:     {args.supervisors}
Max daily sessions:   {args.max_daily}
Voeux penalty:        {args.voeux_weight}
Grade flexibility:    ±{args.grade_flex}
Max solve time:       {args.time}s
Workers:              {args.workers}
{'='*70}
""")
    
    result = generate_planning_from_db(
        session_id=args.session,
        db_path=args.db,
        supervisors_per_room=args.supervisors,
        max_sessions_per_day=args.max_daily,
        max_solve_time=args.time,
        voeux_penalty_weight=args.voeux_weight,
        grade_quota_flexibility=args.grade_flex
    )
    
    if result:
        assignments, teachers_df, slot_info, report = result
        
        print(f"\n{'='*70}")
        print(f"FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"  Total teachers:    {report['total_teachers']}")
        print(f"  Total slots:       {report['total_slots']}")
        print(f"  Total assignments: {report['total_assignments']}")
        print(f"\n  Grade quotas:")
        for grade, stats in sorted(report['grade_stats'].items()):
            print(f"    {grade}: {stats['min']}-{stats['max']} "
                  f"(avg: {stats['avg']:.1f}, target: {stats['target']})")
        print(f"{'='*70}\n")
        
        sys.exit(0)
    else:
        print(f"\n❌ Planning generation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()