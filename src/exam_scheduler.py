"""
Simplified Exam Scheduler - Supervisor Assignment Only

HARD CONSTRAINTS:
1. Minimum supervisors per room (configurable, default: 2 per room)
2. Minimum grade quotas (each teacher must meet at least their quota)
3. Teacher cannot work when they have a wish/preference (voeux)

SOFT CONSTRAINTS (optimized for quality):
4. Minimize exceeding quotas (keep assignments close to target)
5. Optimize teacher schedules (time-clustered, minimize idle hours)

OPTIMIZATION FEATURES:
- No reserves - only supervisors
- Responsible teachers tracked separately (don't need to supervise)
- Fast solving with intelligent hinting
- Configurable parameters for flexibility
"""

from ortools.sat.python import cp_model
import data_loader
import os
import pandas as pd
from datetime import datetime
from collections import defaultdict
import random


def analyze_teacher_satisfaction(assignments, teachers_df, min_quotas, slot_info, slots_by_date):
    """
    Analyze teacher satisfaction based on scheduling quality metrics
    
    Scoring Factors (100 points total):
    - Quota Fairness (30 pts): Penalty for exceeding quota
    - Schedule Compactness (25 pts): Reward for clustered days
    - Consecutive Sessions (20 pts): Bonus for morning+afternoon same day
    - Isolated Sessions (15 pts): Penalty for single-session days
    - Gap Penalties (10 pts): Penalty for gaps between working days
    
    Returns:
    --------
    List of dicts with satisfaction analysis per teacher
    """
    satisfaction_report = []
    teacher_ids = list(assignments.keys())
    
    for tid in teacher_ids:
        if tid not in assignments or not assignments[tid]['surveillant']:
            continue
        
        teacher_name = f"{teachers_df.loc[tid, 'nom_ens']} {teachers_df.loc[tid, 'prenom_ens']}"
        grade = teachers_df.loc[tid, 'grade_code_ens']
        teacher_slots = assignments[tid]['surveillant']
        total_assignments = len(teacher_slots)
        quota = min_quotas[tid]
        
        # Initialize score (start at 100, deduct penalties)
        score = 100.0
        issues = []
        
        # ========================================
        # 1. QUOTA FAIRNESS (30 points max penalty)
        # ========================================
        quota_excess = max(0, total_assignments - quota)
        if quota_excess > 0:
            # Penalty: -5 points per excess assignment
            penalty = min(30, quota_excess * 5)
            score -= penalty
            issues.append(f"Quota exceeded by {quota_excess} ({penalty:.0f}pts penalty)")
        
        # ========================================
        # 2. SCHEDULE COMPACTNESS (25 points)
        # ========================================
        # Get working days
        working_dates = set()
        for slot in teacher_slots:
            working_dates.add(slot['date'])
        
        num_working_days = len(working_dates)
        
        # Ideal: minimum days needed (assignments / 2, assuming 2 sessions per day max)
        ideal_days = max(1, (total_assignments + 1) // 2)
        extra_days = num_working_days - ideal_days
        
        if extra_days > 0:
            # Penalty: -5 points per extra day
            penalty = min(25, extra_days * 5)
            score -= penalty
            issues.append(f"Spread across {extra_days} extra days ({penalty:.0f}pts penalty)")
        
        # ========================================
        # 3. CONSECUTIVE SESSIONS (20 points)
        # ========================================
        # Count days with both morning AND afternoon sessions
        sessions_by_date = defaultdict(lambda: {'Matin': 0, 'Apres-midi': 0})
        for slot in teacher_slots:
            seance = slot['seance']
            if seance in ['Matin', 'Apres-midi']:
                sessions_by_date[slot['date']][seance] += 1
        
        consecutive_days = sum(
            1 for date, sessions in sessions_by_date.items()
            if sessions['Matin'] > 0 and sessions['Apres-midi'] > 0
        )
        
        # Bonus calculation: max 20 points if ALL working days are consecutive
        if num_working_days > 0:
            consecutive_ratio = consecutive_days / num_working_days
            bonus = consecutive_ratio * 20
            # This is a bonus, so we DON'T subtract (it's already at 100)
            # But if ratio is low, we penalize
            if consecutive_ratio < 0.5:
                penalty = (0.5 - consecutive_ratio) * 20
                score -= penalty
                issues.append(f"Only {consecutive_days}/{num_working_days} days with consecutive sessions ({penalty:.0f}pts penalty)")
        
        # ========================================
        # 4. ISOLATED SESSIONS (15 points max penalty)
        # ========================================
        isolated_days = sum(
            1 for date, sessions in sessions_by_date.items()
            if (sessions['Matin'] + sessions['Apres-midi']) == 1
        )
        
        if isolated_days > 0:
            # Penalty: -7.5 points per isolated day
            penalty = min(15, isolated_days * 7.5)
            score -= penalty
            issues.append(f"{isolated_days} single-session days (commute waste, {penalty:.0f}pts penalty)")
        
        # ========================================
        # 5. GAP PENALTIES (10 points max penalty)
        # ========================================
        gaps = []
        if num_working_days > 1:
            # Calculate gaps between working days
            # Convert to datetime objects if they're strings
            date_objects = []
            for date in working_dates:
                if isinstance(date, str):
                    # Try to parse string dates
                    try:
                        date_obj = pd.to_datetime(date)
                        date_objects.append(date_obj)
                    except:
                        continue
                else:
                    date_objects.append(date)
            
            sorted_dates = sorted(date_objects)
            
            for i in range(len(sorted_dates) - 1):
                # Count days between consecutive working days
                gap_days = (sorted_dates[i + 1] - sorted_dates[i]).days - 1
                if gap_days > 0:
                    gaps.append(gap_days)
            
            total_gap_days = sum(gaps)
            if total_gap_days > 0:
                # Penalty: -2 points per gap day
                penalty = min(10, total_gap_days * 2)
                score -= penalty
                issues.append(f"{total_gap_days} idle days between work ({penalty:.0f}pts penalty)")
        
        # ========================================
        # 6. SCHEDULE PATTERN DESCRIPTION
        # ========================================
        if num_working_days == 1:
            pattern = f"Single day ({total_assignments} sessions)"
        elif consecutive_days == num_working_days:
            pattern = f"Perfect: {num_working_days} days, all consecutive sessions"
        elif isolated_days == num_working_days:
            pattern = f"Worst: {num_working_days} days, all isolated sessions"
        else:
            pattern = f"{num_working_days} days: {consecutive_days} consecutive, {isolated_days} isolated"
        
        # Ensure score doesn't go negative
        score = max(0, score)
        
        # Add to report
        satisfaction_report.append({
            'teacher_id': tid,
            'name': teacher_name,
            'grade': grade,
            'total_assignments': total_assignments,
            'quota': quota,
            'quota_excess': quota_excess,
            'working_days': num_working_days,
            'consecutive_days': consecutive_days,
            'isolated_days': isolated_days,
            'gap_days': sum(gaps) if num_working_days > 1 else 0,
            'satisfaction_score': round(score, 1),
            'issues': issues if issues else ['No major issues'],
            'schedule_pattern': pattern
        })
    
    return satisfaction_report


def generate_enhanced_planning(teachers_file, voeux_file, slots_file, 
                                supervisors_per_room=2,
                                compactness_weight=10,
                                max_sessions_per_day=3,
                                gap_penalty_weight=50,
                                max_solve_time=120.0,
                                consecutive_bonus_weight=15,
                                avoid_isolated_weight=25):
    """
    Generate simplified exam supervision planning - supervisors only
    
    Parameters:
    -----------
    supervisors_per_room : int, default=2
        Number of supervisors required per exam room
        
    compactness_weight : int, default=10
        Weight for schedule compactness (clustering sessions on same day)
        
    max_sessions_per_day : int, default=3
        Maximum number of supervision sessions a teacher can have per day
        
    gap_penalty_weight : int, default=50
        Weight for penalizing gaps between working days
        
    max_solve_time : float, default=120.0
        Maximum solving time in seconds
        
    consecutive_bonus_weight : int, default=15
        Bonus weight for teachers working both morning and afternoon same day
        
    avoid_isolated_weight : int, default=25
        Penalty weight for single-session days (isolated work days)
        
    Returns:
    --------
    assignments : dict
        Dictionary mapping teacher_id to their assigned slots
        Structure: {teacher_id: {'surveillant': [...]}}
        
    teachers_df : DataFrame
        DataFrame containing teacher information
        
    slot_info : list
        List of dictionaries containing slot metadata
        
    responsible_schedule : list
        List of dicts showing when responsible teachers need to be available
        
    Notes:
    ------
    - No reserves - only supervisor assignments
    - Responsible teachers are tracked separately and don't need to supervise
    - Grade quotas are minimum requirements
    - Wishes/preferences are HARD constraints (cannot violate)
    - Schedule optimization minimizes total working days per teacher
    """
    
    # Load data
    teachers_df, min_quotas, voeux_by_id, voeux_timestamps, slots_df, slot_info, all_teachers_lookup = \
        data_loader.load_enhanced_data(teachers_file, voeux_file, slots_file)
    
    teacher_ids = teachers_df.index.tolist()
    # Randomize teacher order to avoid alphabetical bias
    random.shuffle(teacher_ids)
    num_teachers = len(teacher_ids)
    num_slots = len(slot_info)
    
    # Update slot_info with configurable supervisors per room (NO RESERVES)
    for slot in slot_info:
        slot['num_surveillants'] = slot['num_salles'] * supervisors_per_room
    
    # Calculate total demand (SUPERVISORS ONLY)
    total_surveillant_needed = sum(s['num_surveillants'] for s in slot_info)
    total_quota_supply = sum(min_quotas.values())
    
    print(f"\n{'='*80}")
    print(f"SIMPLIFIED EXAM SCHEDULING - Supervisors Only")
    print(f"{'='*80}")
    print(f"\n📊 PROBLEM SIZE:")
    print(f"  • Teachers available: {num_teachers}")
    print(f"  • Exam sessions: {num_slots}")
    print(f"  • Total rooms: {sum(s['num_salles'] for s in slot_info)}")
    print(f"\n👥 SUPERVISION REQUIREMENTS:")
    print(f"  • Supervisors per room: {supervisors_per_room}")
    print(f"  • Total supervisors needed: {total_surveillant_needed}")
    print(f"\n⚖️ WORKLOAD BALANCE:")
    print(f"  • Total teacher capacity (min quotas): {total_quota_supply}")
    print(f"  • Balance (capacity - demand): {total_quota_supply - total_surveillant_needed}")
    if total_quota_supply < total_surveillant_needed:
        print(f"  ⚠️  WARNING: Insufficient capacity! Need {total_surveillant_needed - total_quota_supply} more assignments")
    print(f"\n🎯 OPTIMIZATION:")
    print(f"  • Schedule compactness: {compactness_weight}")
    print(f"  • Minimize quota excess: 100")
    print(f"  • Max sessions per day: {max_sessions_per_day}")
    print(f"  • Gap penalty weight: {gap_penalty_weight}")
    print(f"  • Consecutive session bonus: {consecutive_bonus_weight}")
    print(f"  • Avoid isolated sessions: {avoid_isolated_weight}")
    print(f"\n⏱️  SOLVER SETTINGS:")
    print(f"  • Max solving time: {max_solve_time}s")
    print(f"  • Parallel workers: 8")
    print(f"{'='*80}")
    
    # Create model
    model = cp_model.CpModel()
    
    # VARIABLES - Only supervisors (NO RESERVES)
    # x_surv[t, s] = 1 if teacher t is surveillant at slot s
    x_surv = {}
    
    for t_idx, tid in enumerate(teacher_ids):
        for s in range(num_slots):
            x_surv[t_idx, s] = model.NewBoolVar(f'surveillant_{t_idx}_{s}')
    
    # HARD CONSTRAINT 1: Exact number of surveillants per slot
    for s in range(num_slots):
        num_needed = slot_info[s]['num_surveillants']
        model.Add(sum(x_surv[t, s] for t in range(num_teachers)) == num_needed)
    
    # HARD CONSTRAINT 2: Minimum quota per teacher
    # Each teacher must reach AT LEAST their quota (can go slightly over if needed)
    quota_vars = {}
    for t_idx, tid in enumerate(teacher_ids):
        min_quota = min_quotas[tid]
        total_assignments = sum(x_surv[t_idx, s] for s in range(num_slots))
        
        # Minimum constraint: must do at least the quota
        model.Add(total_assignments >= min_quota)
        
        # Track how much over the quota (for objective function)
        over_quota = model.NewIntVar(0, num_slots, f'over_quota_{t_idx}')
        model.Add(over_quota == total_assignments - min_quota)
        quota_vars[t_idx] = over_quota
    
    # HARD CONSTRAINT 3: Respect voeux (teacher CANNOT work when they have preferences/wishes)
    voeux_violations = 0
    for t_idx, tid in enumerate(teacher_ids):
        voeux_list = voeux_by_id[tid]
        for s in range(num_slots):
            slot_key = (slot_info[s]['jour'], slot_info[s]['seance'])
            if slot_key in voeux_list:
                # Teacher has a wish/preference for this time - CANNOT be assigned
                model.Add(x_surv[t_idx, s] == 0)
                voeux_violations += 1
    
    if voeux_violations > 0:
        print(f"\n🔒 PROTECTED SLOTS: {voeux_violations} teacher-slot combinations blocked by preferences")
    
    # HARD CONSTRAINT 4: Maximum sessions per day
    # Prevent teachers from being overloaded on a single day
    slots_by_date = defaultdict(list)
    for s in range(num_slots):
        slots_by_date[slot_info[s]['date']].append(s)
    
    for t_idx in range(num_teachers):
        for date, date_slots in slots_by_date.items():
            # Sum of assignments on this date must not exceed max_sessions_per_day
            model.Add(sum(x_surv[t_idx, s] for s in date_slots) <= max_sessions_per_day)
    
    print(f"\n⚖️  MAX SESSIONS PER DAY: Limited to {max_sessions_per_day} sessions/day per teacher")
    
    # NO CONSTRAINT for subject teacher presence - they're tracked separately
    # Responsible teachers DON'T need to supervise - just be available
    
    # SOFT CONSTRAINTS - Enhanced objective function
    print(f"\n🎯 Building optimization objective...")
    
    # Schedule compactness - minimize number of working days
    slots_by_date = defaultdict(list)
    for s in range(num_slots):
        slots_by_date[slot_info[s]['date']].append(s)
    
    # Count active days for each teacher
    unique_dates = list(slots_by_date.keys())
    total_active_days_vars = []
    active_day_vars = {}  # Store for gap calculation
    
    for t_idx in range(num_teachers):
        active_day_vars[t_idx] = []
        for date_idx, date in enumerate(unique_dates):
            is_active = model.NewBoolVar(f'active_{t_idx}_{date_idx}')
            date_slots = slots_by_date[date]
            # Active if assigned to any slot on this date
            model.AddMaxEquality(is_active, [x_surv[t_idx, s] for s in date_slots])
            total_active_days_vars.append(is_active)
            active_day_vars[t_idx].append(is_active)
    
    # Gap penalty - penalize gaps between first and last working day
    gap_penalty_vars = []
    for t_idx in range(num_teachers):
        if len(active_day_vars[t_idx]) > 1:
            # For each teacher, calculate the span from first to last working day
            # Penalty = (last_active_day - first_active_day) - (num_active_days - 1)
            # This gives us the number of idle days in between
            
            for i in range(len(active_day_vars[t_idx])):
                for j in range(i + 1, len(active_day_vars[t_idx])):
                    # If both day i and day j are active, penalize the gap
                    both_active = model.NewBoolVar(f'gap_{t_idx}_{i}_{j}')
                    model.AddMultiplicationEquality(both_active, [active_day_vars[t_idx][i], active_day_vars[t_idx][j]])
                    
                    # Gap size is (j - i - 1) idle days between active days i and j
                    gap_size = j - i - 1
                    if gap_size > 0:
                        # Only penalize if there's actually a gap
                        gap_contribution = model.NewIntVar(0, gap_size, f'gap_contrib_{t_idx}_{i}_{j}')
                        model.Add(gap_contribution == both_active * gap_size)
                        gap_penalty_vars.append(gap_contribution)
    
    # OBJECTIVE: Minimize exceeding quotas, minimize working days, and minimize gaps
    objective_terms = []
    
    # Penalty for exceeding quota (weight: 100) - keep everyone close to their target
    for t_idx in range(num_teachers):
        objective_terms.append(quota_vars[t_idx] * 100)
    
    # Penalty for spreading across many days (weight: compactness_weight)
    objective_terms.extend([v * compactness_weight for v in total_active_days_vars])
    
    # Penalty for gaps between working days (weight: gap_penalty_weight)
    objective_terms.extend([v * gap_penalty_weight for v in gap_penalty_vars])
    
    # ========================================
    # CONSECUTIVE SESSION BONUS
    # ========================================
    print(f"  • Adding consecutive session bonus...")
    
    consecutive_bonuses = []
    slots_by_date_session = defaultdict(lambda: {'Matin': [], 'Apres-midi': []})
    
    for s in range(num_slots):
        date = slot_info[s]['date']
        seance = slot_info[s]['seance']
        if seance in ['Matin', 'Apres-midi']:
            slots_by_date_session[date][seance].append(s)
    
    for t_idx in range(num_teachers):
        for date, sessions in slots_by_date_session.items():
            morning_slots = sessions.get('Matin', [])
            afternoon_slots = sessions.get('Apres-midi', [])
            
            if morning_slots and afternoon_slots:
                # Check if teacher works BOTH morning AND afternoon
                works_morning = model.NewBoolVar(f'morning_{t_idx}_{date}')
                works_afternoon = model.NewBoolVar(f'afternoon_{t_idx}_{date}')
                
                model.AddMaxEquality(works_morning, [x_surv[t_idx, s] for s in morning_slots])
                model.AddMaxEquality(works_afternoon, [x_surv[t_idx, s] for s in afternoon_slots])
                
                # Reward for working both (single commute for full day)
                consecutive_day = model.NewBoolVar(f'consecutive_{t_idx}_{date}')
                model.AddMultiplicationEquality(consecutive_day, [works_morning, works_afternoon])
                
                # Negative value = bonus (reduces objective function)
                consecutive_bonuses.append(consecutive_day * (-consecutive_bonus_weight))
    
    print(f"    ✓ {len(consecutive_bonuses)} potential consecutive session bonuses")
    
    # Add to objective
    objective_terms.extend(consecutive_bonuses)
    
    # ========================================
    # AVOID ISOLATED SESSIONS
    # ========================================
    print(f"  • Adding isolated session penalty...")
    
    isolation_penalties = []
    
    for t_idx in range(num_teachers):
        for date, date_slots in slots_by_date.items():
            if len(date_slots) <= 1:
                # Skip dates with only 1 slot total (can't avoid isolation)
                continue
            
            # Count number of sessions this teacher works on this date
            num_sessions_this_day = model.NewIntVar(0, len(date_slots), f'sessions_{t_idx}_{date}')
            model.Add(num_sessions_this_day == sum(x_surv[t_idx, s] for s in date_slots))
            
            # Check if teacher works this day
            works_this_day = model.NewBoolVar(f'works_{t_idx}_{date}')
            model.AddMaxEquality(works_this_day, [x_surv[t_idx, s] for s in date_slots])
            
            # Is this a single-session day? (works exactly 1 session)
            is_isolated = model.NewBoolVar(f'isolated_{t_idx}_{date}')
            model.Add(num_sessions_this_day == 1).OnlyEnforceIf(is_isolated)
            model.Add(num_sessions_this_day != 1).OnlyEnforceIf(is_isolated.Not())
            
            # Heavy penalty for isolated days (teacher commutes for just 1 session)
            isolation_penalties.append(is_isolated * avoid_isolated_weight)
    
    print(f"    ✓ {len(isolation_penalties)} potential single-session days to avoid")
    
    # Add to objective
    objective_terms.extend(isolation_penalties)
    
    # ========================================
    # RANDOM TIE-BREAKER WEIGHTS
    # ========================================
    # Add tiny random weights to break ties and avoid systematic bias
    # This ensures different teachers get priority in each run
    print(f"  • Adding randomization to break solver bias...")
    
    tie_breaker_terms = []
    for t_idx in range(num_teachers):
        for s in range(num_slots):
            # Very small random integer weight (1 to 3) - won't significantly affect main optimization
            # but will randomize tie-breaking decisions by the solver
            random_weight = random.randint(1, 3)
            tie_breaker_terms.append(x_surv[t_idx, s] * random_weight)
    
    objective_terms.extend(tie_breaker_terms)
    print(f"    ✓ Added {len(tie_breaker_terms)} randomized tie-breakers")
    
    model.Minimize(sum(objective_terms))
    
    # HINTING: Help the solver find good solutions faster
    # Hint: Assign teachers with fewer preferences first
    teachers_with_few_prefs = sorted(range(num_teachers), 
                                     key=lambda t: len(voeux_by_id[teacher_ids[t]]))
    
    # Pre-assign some easy cases (teachers with no preferences to early slots)
    # hint_count = 0
    # for t_idx in teachers_with_few_prefs[:min(5, num_teachers)]:
    #     if not voeux_by_id[teacher_ids[t_idx]]:  # No preferences
    #         for s in range(min(2, num_slots)):  # Hint first 2 slots
    #             if hint_count < 10:  # Limit hints
    #                 model.AddHint(x_surv[t_idx, s], 0)
    #                 hint_count += 1
    
    # SOLVE - Optimized settings
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solve_time
    solver.parameters.num_search_workers = 8  # Use multiple cores
    solver.parameters.log_search_progress = False  # Reduce output overhead
    solver.parameters.cp_model_presolve = True  # Enable presolve
    solver.parameters.linearization_level = 2  # More aggressive linearization
    solver.parameters.symmetry_level = 2  # Break symmetries
    # Add random seed to ensure different solutions each run
    solver.parameters.random_seed = random.randint(0, 999999)
    
    print(f"\n{'='*80}")
    print("SOLVING...")
    print(f"{'='*80}")
    
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        solution_type = 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'
        print(f"\n{'='*80}")
        print(f"✓ {solution_type} SOLUTION FOUND!")
        print(f"{'='*80}")
        print(f"  Objective value: {solver.ObjectiveValue():.2f}")
        print(f"  Solve time: {solver.WallTime():.2f}s")
        print(f"  Branches explored: {solver.NumBranches()}")
        
        # Extract assignments (SUPERVISORS ONLY)
        assignments = defaultdict(lambda: {'surveillant': []})
        
        for t_idx, tid in enumerate(teacher_ids):
            for s in range(num_slots):
                if solver.Value(x_surv[t_idx, s]) == 1:
                    slot_data = slot_info[s].copy()
                    slot_data['role'] = 'Surveillant'
                    assignments[tid]['surveillant'].append(slot_data)
        
        # Extract responsible teacher schedule (who needs to be available)
        responsible_schedule = []
        for s in range(num_slots):
            responsible_ids = slot_info[s]['responsible_teachers']
            if responsible_ids:
                for resp_id in responsible_ids:
                    resp_id_int = int(resp_id)
                    
                    # Find teacher name from ALL teachers lookup (includes non-participants)
                    if resp_id_int in all_teachers_lookup:
                        teacher_info = all_teachers_lookup[resp_id_int]
                        teacher_name = f"{teacher_info['nom_ens']} {teacher_info['prenom_ens']}"
                        grade = teacher_info['grade_code_ens']
                        email = teacher_info['email_ens']
                    else:
                        # Teacher ID not found in Enseignants.xlsx at all
                        teacher_name = str(resp_id)
                        grade = 'N/A'
                        email = 'N/A'
                    
                    responsible_schedule.append({
                        'teacher_id': resp_id_int,
                        'teacher_name': teacher_name,
                        'grade': grade,
                        'email': email,
                        'date': slot_info[s]['date'],
                        'time': slot_info[s]['time'],
                        'jour': slot_info[s]['jour'],
                        'seance': slot_info[s]['seance'],
                        'slot_id': s
                    })
        
        # Validate solution
        print(f"\n📋 SOLUTION VALIDATION:")
        total_surv = sum(len(a['surveillant']) for a in assignments.values())
        print(f"  • Total supervisors assigned: {total_surv} (required: {total_surveillant_needed})")
        print(f"  • Teachers with assignments: {len(assignments)}/{num_teachers}")
        print(f"  • Responsible teachers to be available: {len(responsible_schedule)} slots")
        
        # Check quota achievement
        quota_stats = {'exact': 0, 'over': 0, 'total_over': 0}
        for t_idx, tid in enumerate(teacher_ids):
            target = min_quotas[tid]
            actual = len(assignments[tid]['surveillant'])
            if actual == target:
                quota_stats['exact'] += 1
            elif actual > target:
                quota_stats['over'] += 1
                quota_stats['total_over'] += (actual - target)
        
        print(f"  • Quota achievement:")
        print(f"    - {quota_stats['exact']}/{num_teachers} teachers met quota exactly")
        if quota_stats['over'] > 0:
            print(f"    - {quota_stats['over']} teachers exceeded quota (total excess: {quota_stats['total_over']})")
        
        # Check grade quotas
        grade_counts = defaultdict(int)
        for tid, roles in assignments.items():
            grade = teachers_df.loc[tid]['grade_code_ens']
            grade_counts[grade] += len(roles['surveillant'])
        
        print(f"  • Grades represented: {len(grade_counts)}")
        
        # ========================================
        # TEACHER SATISFACTION ANALYSIS
        # ========================================
        satisfaction_report = analyze_teacher_satisfaction(
            assignments, teachers_df, min_quotas, slot_info, slots_by_date
        )
        
        print(f"\n{'='*80}")
        print(f"📊 TEACHER SATISFACTION ANALYSIS")
        print(f"{'='*80}")
        
        # Overall statistics
        avg_score = sum(t['satisfaction_score'] for t in satisfaction_report) / len(satisfaction_report)
        print(f"\n📈 OVERALL SATISFACTION:")
        print(f"  • Average Score: {avg_score:.1f}/100")
        print(f"  • Highly Satisfied (80+): {sum(1 for t in satisfaction_report if t['satisfaction_score'] >= 80)}")
        print(f"  • Satisfied (60-79): {sum(1 for t in satisfaction_report if 60 <= t['satisfaction_score'] < 80)}")
        print(f"  • Neutral (40-59): {sum(1 for t in satisfaction_report if 40 <= t['satisfaction_score'] < 60)}")
        print(f"  • Dissatisfied (20-39): {sum(1 for t in satisfaction_report if 20 <= t['satisfaction_score'] < 40)}")
        print(f"  • Very Dissatisfied (<20): {sum(1 for t in satisfaction_report if t['satisfaction_score'] < 20)}")
        
        # Top 10 most dissatisfied teachers
        most_dissatisfied = sorted(satisfaction_report, key=lambda x: x['satisfaction_score'])[:10]
        
        print(f"\n⚠️  TOP 10 MOST DISSATISFIED TEACHERS:")
        print(f"{'─'*80}")
        print(f"{'Rank':<6}{'Teacher':<30}{'Score':<10}{'Main Issues'}")
        print(f"{'─'*80}")
        
        for rank, teacher in enumerate(most_dissatisfied, 1):
            issues = ', '.join(teacher['issues'][:2])  # Show top 2 issues
            print(f"{rank:<6}{teacher['name']:<30}{teacher['satisfaction_score']:<10.1f}{issues}")
        
        print(f"{'─'*80}")
        
        # Detailed breakdown for worst 3
        print(f"\n🔍 DETAILED ANALYSIS - WORST 3 CASES:")
        for i, teacher in enumerate(most_dissatisfied[:3], 1):
            print(f"\n{i}. {teacher['name']} (Score: {teacher['satisfaction_score']:.1f}/100)")
            print(f"   Grade: {teacher['grade']} | Assignments: {teacher['total_assignments']}")
            print(f"   Issues:")
            for issue in teacher['issues']:
                print(f"     • {issue}")
            print(f"   Schedule Pattern: {teacher['schedule_pattern']}")
        
        print(f"\n{'='*80}\n")
        
        return dict(assignments), teachers_df, slot_info, responsible_schedule, all_teachers_lookup
    else:
        error_messages = {
            cp_model.INFEASIBLE: "No feasible solution exists with current constraints",
            cp_model.MODEL_INVALID: "Model is invalid - check constraint definitions",
            cp_model.UNKNOWN: "Solver status unknown - may need more time"
        }
        error_msg = error_messages.get(status, f"Unexpected status: {status}")
        
        print(f"\n{'='*80}")
        print(f"✗ SOLVING FAILED")
        print(f"{'='*80}")
        print(f"Status: {error_msg}")
        print(f"\n💡 SUGGESTIONS:")
        print(f"  1. Increase max_solve_time (current: {max_solve_time}s)")
        print(f"  2. Reduce supervisors_per_room (current: {supervisors_per_room})")
        print(f"  3. Check that grade quotas are not too restrictive")
        print(f"  4. Review voeux conflicts")
        print(f"{'='*80}\n")
        
        raise ValueError(f"No feasible solution found. {error_msg}")


if __name__ == '__main__':
    
    BASE_DIR = os.path.dirname(__file__)
    teachers_file = os.path.join(BASE_DIR, "../resources/Enseignants.xlsx")
    voeux_file = os.path.join(BASE_DIR, "../resources/Souhaits.xlsx")
    slots_file = os.path.join(BASE_DIR, "../resources/Repartitions.xlsx")
    
    # Simplified configuration - supervisors only
    assignments, teachers_df, slot_info, responsible_schedule, all_teachers_lookup = generate_enhanced_planning(
        teachers_file,
        voeux_file,
        slots_file,
        supervisors_per_room=2,        # 2 supervisors per room
        compactness_weight=8,          # Schedule optimization
        max_sessions_per_day=2,         # Max 3 sessions per day per teacher
        gap_penalty_weight=80,          # Penalize gaps between working days
        max_solve_time=120.0,           # 120 seconds solving time
        consecutive_bonus_weight=25,    # Bonus for morning+afternoon same day
        avoid_isolated_weight=40        # Penalty for single-session days
    )
    
    print(f"\n{'='*80}")
    print("📊 FINAL ASSIGNMENT SUMMARY")
    print(f"{'='*80}")
    
    # Detailed summary
    total_surveillant = sum(len(a['surveillant']) for a in assignments.values())
    
    print(f"\n✓ Assignments generated successfully!")
    print(f"  • Total supervisor assignments: {total_surveillant}")
    print(f"  • Teachers assigned: {len(assignments)}")
    print(f"  • Responsible teacher availability slots: {len(responsible_schedule)}")
    
    # Summary by grade
    from collections import defaultdict
    grade_summary = defaultdict(lambda: {'teachers': 0, 'surveillant': 0})
    for tid, roles in assignments.items():
        grade = teachers_df.loc[tid]['grade_code_ens']
        grade_summary[grade]['teachers'] += 1
        grade_summary[grade]['surveillant'] += len(roles['surveillant'])
    
    print(f"\n📊 By Grade:")
    for grade in sorted(grade_summary.keys()):
        stats = grade_summary[grade]
        avg = stats['surveillant'] / stats['teachers'] if stats['teachers'] > 0 else 0
        print(f"  {grade}: {stats['teachers']} teachers, "
              f"{stats['surveillant']} supervisors, "
              f"avg {avg:.1f} per teacher")
    
    print(f"{'='*80}\n")

