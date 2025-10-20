"""
Decision Support System for Exam Scheduling
============================================
Analyzes uploaded files and provides recommendations before generating planning.
"""

import pandas as pd
from typing import Dict, List, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DecisionReport:
    """Container for decision support analysis results."""
    status: str  # 'excellent', 'good', 'warning', 'critical'
    feasibility_score: float  # 0-100
    recommendations: List[str]
    warnings: List[str]
    statistics: Dict[str, Any]
    quota_analysis: Dict[str, Any]
    capacity_analysis: Dict[str, Any]
    risk_factors: List[Dict[str, Any]]
    using_custom_quotas: bool = False  # Whether custom quotas were provided
    custom_quotas_feasible: bool = True  # Whether custom quotas are feasible
    suggested_quotas: Dict[str, int] = None  # Suggested adjusted quotas


class DecisionSupportSystem:
    """Analyzes scheduling feasibility and provides recommendations."""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.default_quotas = {
            'PR': 4, 'MC': 4, 'MA': 7, 'AS': 8, 'AC': 9,
            'PTC': 9, 'PES': 9, 'EX': 3, 'V': 4
        }
    
    def analyze_session(
        self,
        session_id: int,
        supervisors_per_room: int = 2,
        custom_quotas: Dict[str, int] = None
    ) -> DecisionReport:
        """
        Comprehensive analysis of session feasibility.
        
        Args:
            session_id: Session ID to analyze
            supervisors_per_room: Number of supervisors per room
            custom_quotas: Optional custom quotas dict (e.g., {'PR': 4, 'MC': 4, ...})
        
        Returns DecisionReport with recommendations and warnings.
        """
        # Use custom quotas if provided, otherwise use defaults
        using_custom_quotas = custom_quotas is not None
        quotas_to_use = custom_quotas if custom_quotas else self.default_quotas
        
        # Load data
        teachers_df = self.db.get_teachers(session_id, participating_only=True)
        slots = self.db.get_slots(session_id)
        voeux_dict = self.db.get_voeux(session_id)
        
        if teachers_df.empty:
            return self._create_error_report("Aucun enseignant trouvé")
        
        if not slots:
            return self._create_error_report("Aucun créneau d'examen trouvé")
        
        # Standardize column names for teachers
        if 'grade_code_ens' in teachers_df.columns and 'grade' not in teachers_df.columns:
            teachers_df['grade'] = teachers_df['grade_code_ens']
        
        # Calculate basic metrics
        total_teachers = len(teachers_df)
        total_slots = len(slots)
        total_rooms = sum(slot.get('nb_surveillants', 0) for slot in slots)
        total_needed = total_rooms * supervisors_per_room
        
        # Analyze capacity
        capacity_analysis = self._analyze_capacity(
            teachers_df, slots, voeux_dict, total_needed, supervisors_per_room, quotas_to_use
        )
        
        # Analyze quotas
        quota_analysis = self._analyze_quotas(
            teachers_df, total_needed, quotas_to_use
        )
        
        # Identify risk factors
        risk_factors = self._identify_risks(
            teachers_df, slots, voeux_dict, capacity_analysis, quota_analysis
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            capacity_analysis, quota_analysis, risk_factors
        )
        
        # Generate warnings
        warnings = self._generate_warnings(risk_factors)
        
        # Calculate feasibility score
        feasibility_score = self._calculate_feasibility_score(
            capacity_analysis, risk_factors
        )
        
        # Determine overall status
        status = self._determine_status(feasibility_score, risk_factors)
        
        # Compile statistics
        teachers_with_voeux = len([v for v in voeux_dict.values() if v])
        statistics = {
            'total_teachers': total_teachers,
            'total_slots': total_slots,
            'total_rooms': total_rooms,
            'total_surveillances_needed': total_needed,
            'avg_surveillances_per_teacher': round(total_needed / total_teachers, 1) if total_teachers > 0 else 0,
            'teachers_with_voeux': teachers_with_voeux,
            'voeux_percentage': round(teachers_with_voeux / total_teachers * 100, 1) if total_teachers > 0 else 0
        }
        
        # Calculate suggested quotas (proportionally adjusted)
        suggested_quotas = self._calculate_suggested_quotas(quota_analysis)
        
        # Check if custom quotas are feasible
        # Quotas are feasible if base capacity >= total needed
        custom_quotas_feasible = True
        if using_custom_quotas:
            base_capacity = capacity_analysis.get('base_capacity', 0)
            custom_quotas_feasible = base_capacity >= total_needed
            
            # Also check if significantly different from suggested
            if custom_quotas_feasible and suggested_quotas:
                # Check if custom quotas are very different from optimal
                total_custom = sum(quotas_to_use.get(g, 0) * capacity_analysis['grade_capacity'].get(g, {}).get('count', 0)
                                 for g in quotas_to_use.keys() if g in capacity_analysis['grade_capacity'])
                total_suggested = quota_analysis.get('total_adjusted', 0)
                
                # If custom quotas result in >50% excess or any shortage, mark as suboptimal
                if total_custom < total_needed:
                    custom_quotas_feasible = False
        
        return DecisionReport(
            status=status,
            feasibility_score=feasibility_score,
            recommendations=recommendations,
            warnings=warnings,
            statistics=statistics,
            quota_analysis=quota_analysis,
            capacity_analysis=capacity_analysis,
            risk_factors=risk_factors,
            using_custom_quotas=using_custom_quotas,
            custom_quotas_feasible=custom_quotas_feasible,
            suggested_quotas=suggested_quotas
        )
    
    def _analyze_capacity(
        self,
        teachers_df: pd.DataFrame,
        slots: List[Dict],
        voeux_dict: Dict,
        total_needed: int,
        supervisors_per_room: int,
        quotas: Dict[str, int]
    ) -> Dict[str, Any]:
        """Analyze available capacity vs requirements."""
        
        # Calculate base capacity (using provided quotas)
        base_capacity = 0
        grade_capacity = {}
        
        for _, teacher in teachers_df.iterrows():
            # Get grade - check multiple possible column names
            grade = None
            for col in ['grade', 'grade_code_ens', 'grade_ens']:
                if col in teacher.index:
                    grade = teacher.get(col)
                    if grade is not None and str(grade).strip() and str(grade).lower() != 'nan':
                        break
            
            # Clean up grade value
            if pd.isna(grade) or grade is None or str(grade).strip() == '' or str(grade).lower() == 'nan':
                grade = 'Unknown'
            else:
                grade = str(grade).strip().upper()
            
            quota = quotas.get(grade, 4)
            base_capacity += quota
            
            if grade not in grade_capacity:
                grade_capacity[grade] = {'count': 0, 'capacity': 0}
            grade_capacity[grade]['count'] += 1
            grade_capacity[grade]['capacity'] += quota
        
        # Calculate available capacity (after voeux)
        available_capacity = 0
        blocked_slots = 0
        
        for _, teacher in teachers_df.iterrows():
            # Get teacher code - try multiple column names
            teacher_code = None
            for col in ['code_smartexam', 'code_smartexam_ens', 'id']:
                if col in teacher.index:
                    teacher_code = str(teacher.get(col, ''))
                    if teacher_code and teacher_code != 'nan':
                        break
            
            if not teacher_code or teacher_code == 'nan':
                teacher_code = str(teacher.get('id', ''))
            
            # Get voeux for this teacher (voeux_dict uses teacher_id as key)
            teacher_voeux = voeux_dict.get(teacher_code, [])
            if not isinstance(teacher_voeux, list):
                teacher_voeux = []
            
            available_slots = len(slots) - len(teacher_voeux)
            available_capacity += available_slots
            blocked_slots += len(teacher_voeux)
        
        # Calculate buffer (not used for quotas, only for capacity check)
        buffer_15_pct = int(total_needed * 0.15)
        target_with_buffer = total_needed + buffer_15_pct
        
        # Utilization rates
        base_utilization = (total_needed / base_capacity * 100) if base_capacity > 0 else 0
        available_utilization = (total_needed / available_capacity * 100) if available_capacity > 0 else 0
        
        return {
            'base_capacity': base_capacity,
            'available_capacity': available_capacity,
            'total_needed': total_needed,
            'buffer_amount': buffer_15_pct,
            'target_with_buffer': target_with_buffer,
            'base_utilization_pct': round(base_utilization, 1),
            'available_utilization_pct': round(available_utilization, 1),
            'over_capacity': base_capacity - total_needed,
            'over_capacity_pct': round((base_capacity - total_needed) / total_needed * 100, 1) if total_needed > 0 else 0,
            'blocked_slots': blocked_slots,
            'grade_capacity': grade_capacity,
            'is_sufficient': available_capacity >= total_needed  # Changed to use total_needed directly
        }
    
    def _analyze_quotas(
        self,
        teachers_df: pd.DataFrame,
        total_needed: int,
        quotas: Dict[str, int]
    ) -> Dict[str, Any]:
        """Analyze quota distribution and fairness."""
        
        grade_distribution = {}
        total_weight = 0
        
        for _, teacher in teachers_df.iterrows():
            # Get grade - check multiple possible column names
            grade = None
            for col in ['grade', 'grade_code_ens', 'grade_ens']:
                if col in teacher.index:
                    grade = teacher.get(col)
                    if grade is not None and str(grade).strip() and str(grade).lower() != 'nan':
                        break
            
            # Clean up grade value
            if pd.isna(grade) or grade is None or str(grade).strip() == '' or str(grade).lower() == 'nan':
                grade = 'Unknown'
            else:
                grade = str(grade).strip().upper()
            
            base_quota = quotas.get(grade, 4)
            
            if grade not in grade_distribution:
                grade_distribution[grade] = {
                    'count': 0,
                    'base_quota': base_quota,
                    'total_base': 0,
                    'adjusted_quota': 0,
                    'total_adjusted': 0
                }
            
            grade_distribution[grade]['count'] += 1
            grade_distribution[grade]['total_base'] += base_quota
            total_weight += base_quota
        
        # Calculate adjusted quotas (using proportional allocation)
        # This matches the scheduler's _calculate_adjusted_quotas method
        for grade in grade_distribution:
            grade_weight = grade_distribution[grade]['total_base']
            # Use proportional allocation based on weight
            if total_weight > 0:
                adjusted_total = int((grade_weight / total_weight) * total_needed + 0.5)
            else:
                adjusted_total = 0
            
            grade_distribution[grade]['total_adjusted'] = adjusted_total
            
            if grade_distribution[grade]['count'] > 0:
                grade_distribution[grade]['adjusted_quota'] = round(
                    adjusted_total / grade_distribution[grade]['count'], 1
                )
            else:
                grade_distribution[grade]['adjusted_quota'] = 0
                
            if grade_distribution[grade]['total_base'] > 0:
                grade_distribution[grade]['reduction_pct'] = round(
                    (grade_distribution[grade]['total_base'] - adjusted_total) / 
                    grade_distribution[grade]['total_base'] * 100, 1
                )
            else:
                grade_distribution[grade]['reduction_pct'] = 0
        
        total_adjusted = sum(g['total_adjusted'] for g in grade_distribution.values())
        total_base = sum(g['total_base'] for g in grade_distribution.values())
        
        return {
            'distribution': grade_distribution,
            'total_base': total_base,
            'total_adjusted': total_adjusted,
            'overall_reduction_pct': round(
                (total_base - total_needed) / total_base * 100, 1
            ) if total_base > 0 else 0
        }
    
    def _calculate_suggested_quotas(self, quota_analysis: Dict) -> Dict[str, int]:
        """Extract suggested quotas from quota analysis."""
        suggested = {}
        if quota_analysis and 'distribution' in quota_analysis:
            for grade, info in quota_analysis['distribution'].items():
                # Use the adjusted quota rounded to nearest integer
                suggested[grade] = max(1, int(info['adjusted_quota'] + 0.5))
        return suggested
    
    def _identify_risks(
        self,
        teachers_df: pd.DataFrame,
        slots: List[Dict],
        voeux_dict: Dict,
        capacity_analysis: Dict,
        quota_analysis: Dict
    ) -> List[Dict[str, Any]]:
        """Identify potential risk factors."""
        
        risks = []
        
        # Risk 0: Insufficient quota capacity (base capacity < needed)
        base_capacity = capacity_analysis.get('base_capacity', 0)
        total_needed = capacity_analysis.get('total_needed', 0)
        if base_capacity < total_needed:
            shortage = total_needed - base_capacity
            risks.append({
                'level': 'critical',
                'category': 'quotas',
                'title': 'Quotas insuffisants',
                'description': f"Les quotas actuels donnent {base_capacity} surveillances, mais {total_needed} sont nécessaires (manque: {shortage})",
                'impact': 'Impossible de générer un planning avec ces quotas',
                'score': -40
            })
        
        # Risk 1: Insufficient capacity
        if not capacity_analysis['is_sufficient']:
            shortage = capacity_analysis['total_needed'] - capacity_analysis['available_capacity']
            risks.append({
                'level': 'critical',
                'category': 'capacity',
                'title': 'Capacité insuffisante',
                'description': f"Manque de {shortage} créneaux disponibles",
                'impact': 'Impossible de générer un planning complet',
                'score': -30
            })
        
        # Risk 2: Very high utilization (>85%)
        elif capacity_analysis['available_utilization_pct'] > 85:
            risks.append({
                'level': 'warning',
                'category': 'capacity',
                'title': 'Utilisation très élevée',
                'description': f"Taux d'utilisation: {capacity_analysis['available_utilization_pct']:.1f}%",
                'impact': 'Peu de flexibilité pour l\'optimisation',
                'score': -15
            })
        
        # Risk 3: Too many voeux
        voeux_pct = (capacity_analysis['blocked_slots'] / (len(teachers_df) * len(slots)) * 100) if len(teachers_df) > 0 and len(slots) > 0 else 0
        if voeux_pct > 40:
            risks.append({
                'level': 'warning',
                'category': 'constraints',
                'title': 'Beaucoup de voeux',
                'description': f"{voeux_pct:.1f}% des créneaux bloqués par les voeux",
                'impact': 'Réduit les possibilités d\'optimisation',
                'score': -10
            })
        
        # Risk 4: Unbalanced grade distribution
        grade_counts = {}
        for _, teacher in teachers_df.iterrows():
            # Get grade - check multiple possible column names
            grade = None
            for col in ['grade', 'grade_code_ens', 'grade_ens']:
                if col in teacher.index:
                    grade = teacher.get(col)
                    if grade is not None and str(grade).strip() and str(grade).lower() != 'nan':
                        break
            
            # Clean up grade value
            if pd.isna(grade) or grade is None or str(grade).strip() == '' or str(grade).lower() == 'nan':
                grade = 'Unknown'
            else:
                grade = str(grade).strip().upper()
            
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        
        # Check if most teachers have Unknown grade (data quality issue)
        unknown_count = grade_counts.get('Unknown', 0)
        if unknown_count > len(teachers_df) * 0.5:
            risks.append({
                'level': 'warning',
                'category': 'data_quality',
                'title': 'Données de grades manquantes',
                'description': f"{unknown_count}/{len(teachers_df)} enseignants sans grade défini",
                'impact': 'Impossible d\'ajuster les quotas par grade. Quotas par défaut utilisés (4 surveillances).',
                'score': -5,
                'suggestion': 'Vérifiez que la colonne "grade" existe dans le fichier Excel des enseignants et contient des valeurs valides (PR, MC, MA, AS, AC, PTC, PES, EX, V).'
            })
        
        if len(grade_counts) < 3:
            risks.append({
                'level': 'info',
                'category': 'distribution',
                'title': 'Distribution de grades limitée',
                'description': f"Seulement {len(grade_counts)} grades différents",
                'impact': 'Moins de diversité dans les affectations',
                'score': -5
            })
        
        # Risk 5: Few teachers relative to needs
        teachers_per_slot = len(teachers_df) / len(slots) if len(slots) > 0 else 0
        if teachers_per_slot < 3:
            risks.append({
                'level': 'warning',
                'category': 'capacity',
                'title': 'Peu d\'enseignants disponibles',
                'description': f"Ratio: {teachers_per_slot:.1f} enseignants par créneau",
                'impact': 'Options limitées pour chaque créneau',
                'score': -10
            })
        
        # Risk 6: Very high over-capacity (waste)
        if capacity_analysis['over_capacity_pct'] > 70:
            risks.append({
                'level': 'info',
                'category': 'efficiency',
                'title': 'Sur-capacité importante',
                'description': f"Capacité excédentaire: {capacity_analysis['over_capacity_pct']:.1f}%",
                'impact': 'Les quotas de base sont trop élevés',
                'score': 0  # Not a real risk, just inefficiency
            })
        
        return risks
    
    def _generate_recommendations(
        self,
        capacity_analysis: Dict,
        quota_analysis: Dict,
        risk_factors: List[Dict]
    ) -> List[str]:
        """Generate actionable recommendations."""
        
        recommendations = []
        
        # Based on capacity
        if not capacity_analysis['is_sufficient']:
            recommendations.append(
                "❌ CRITIQUE: Ajoutez des enseignants ou réduisez les voeux pour atteindre la capacité nécessaire"
            )
            recommendations.append(
                f"   → Besoin: {capacity_analysis['total_needed']}, Disponible: {capacity_analysis['available_capacity']}"
            )
        elif capacity_analysis['available_utilization_pct'] > 85:
            recommendations.append(
                "⚠️  Capacité limite: Considérez ajouter quelques enseignants pour plus de flexibilité"
            )
        else:
            recommendations.append(
                "✅ Capacité suffisante pour générer un planning optimal"
            )
        
        # Based on quotas
        if quota_analysis['overall_reduction_pct'] > 30:
            recommendations.append(
                f"💡 Les quotas seront ajustés (réduction de {quota_analysis['overall_reduction_pct']:.0f}%) pour correspondre aux besoins réels"
            )
            recommendations.append(
                "   L'algorithme utilise l'allocation proportionnelle pour garantir l'équité entre grades"
            )
        
        # Based on risks
        critical_risks = [r for r in risk_factors if r['level'] == 'critical']
        if critical_risks:
            recommendations.append(
                "🔴 Résolvez les problèmes critiques avant de générer le planning"
            )
        
        warning_risks = [r for r in risk_factors if r['level'] == 'warning']
        if warning_risks and not critical_risks:
            recommendations.append(
                "🟡 Le planning peut être généré mais avec des contraintes importantes"
            )
        
        # Compactness advice
        if capacity_analysis['available_utilization_pct'] < 70:
            recommendations.append(
                "💡 Utilisation modérée: L'algorithme pourra optimiser la compacité des horaires"
            )
        
        # Algorithm information
        recommendations.append(
            "ℹ️  L'algorithme utilise:"
        )
        recommendations.append(
            "   • Contraintes DURES: Couverture, quotas par grade (égalité stricte), limites journalières"
        )
        recommendations.append(
            "   • Contraintes DOUCES: Respect des voeux (pénalisé mais pas bloquant), qualité d'horaire"
        )
        
        # Grade-specific recommendations
        for grade, info in quota_analysis['distribution'].items():
            if info['reduction_pct'] > 50:
                recommendations.append(
                    f"📊 Grade {grade}: Quota ajusté de {info['base_quota']} → {info['adjusted_quota']:.1f} surveillances"
                )
        
        return recommendations
    
    def _generate_warnings(self, risk_factors: List[Dict]) -> List[str]:
        """Generate warning messages from risk factors."""
        
        warnings = []
        
        critical = [r for r in risk_factors if r['level'] == 'critical']
        warning_level = [r for r in risk_factors if r['level'] == 'warning']
        
        for risk in critical:
            msg = f"🔴 {risk['title']}: {risk['description']}"
            if 'suggestion' in risk:
                msg += f"\n   💡 {risk['suggestion']}"
            warnings.append(msg)
        
        for risk in warning_level:
            msg = f"🟡 {risk['title']}: {risk['description']}"
            if 'suggestion' in risk:
                msg += f"\n   💡 {risk['suggestion']}"
            warnings.append(msg)
        
        return warnings
    
    def _calculate_feasibility_score(
        self,
        capacity_analysis: Dict,
        risk_factors: List[Dict]
    ) -> float:
        """Calculate overall feasibility score (0-100)."""
        
        score = 100.0
        
        # Deduct for risks
        for risk in risk_factors:
            score += risk['score']
        
        # Adjust based on utilization
        utilization = capacity_analysis['available_utilization_pct']
        if utilization > 95:
            score -= 15
        elif utilization > 85:
            score -= 5
        elif utilization < 50:
            score += 5  # Bonus for low utilization (more flexibility)
        
        # Ensure score is between 0 and 100
        return max(0.0, min(100.0, score))
    
    def _determine_status(
        self,
        feasibility_score: float,
        risk_factors: List[Dict]
    ) -> str:
        """Determine overall status based on score and risks."""
        
        has_critical = any(r['level'] == 'critical' for r in risk_factors)
        
        if has_critical or feasibility_score < 50:
            return 'critical'
        elif feasibility_score < 70:
            return 'warning'
        elif feasibility_score < 85:
            return 'good'
        else:
            return 'excellent'
    
    def _create_error_report(self, message: str) -> DecisionReport:
        """Create an error report when data is missing."""
        
        return DecisionReport(
            status='critical',
            feasibility_score=0.0,
            recommendations=[f"❌ {message}"],
            warnings=[message],
            statistics={},
            quota_analysis={},
            capacity_analysis={},
            risk_factors=[{
                'level': 'critical',
                'category': 'data',
                'title': 'Données manquantes',
                'description': message,
                'impact': 'Impossible de générer un planning',
                'score': -100
            }]
        )
    
    def format_report_text(self, report: DecisionReport) -> str:
        """Format report as readable text."""
        
        status_icons = {
            'excellent': '🟢',
            'good': '🟢',
            'warning': '🟡',
            'critical': '🔴'
        }
        
        status_names = {
            'excellent': 'EXCELLENT',
            'good': 'BON',
            'warning': 'ATTENTION',
            'critical': 'CRITIQUE'
        }
        
        lines = []
        lines.append("=" * 70)
        lines.append("ANALYSE DE FAISABILITÉ - SUPPORT À LA DÉCISION")
        lines.append("=" * 70)
        lines.append("")
        
        # Status
        icon = status_icons.get(report.status, '⚪')
        status_name = status_names.get(report.status, 'INCONNU')
        lines.append(f"{icon} STATUT: {status_name} (Score: {report.feasibility_score:.0f}/100)")
        lines.append("")
        
        # Statistics
        if report.statistics:
            lines.append("📊 STATISTIQUES:")
            lines.append(f"  • Enseignants participants: {report.statistics.get('total_teachers', 0)}")
            lines.append(f"  • Créneaux d'examen: {report.statistics.get('total_slots', 0)}")
            lines.append(f"  • Salles totales: {report.statistics.get('total_rooms', 0)}")
            lines.append(f"  • Surveillances nécessaires: {report.statistics.get('total_surveillances_needed', 0)}")
            lines.append(f"  • Moyenne par enseignant: {report.statistics.get('avg_surveillances_per_teacher', 0):.1f}")
            lines.append(f"  • Enseignants avec voeux: {report.statistics.get('teachers_with_voeux', 0)} ({report.statistics.get('voeux_percentage', 0):.1f}%)")
            lines.append("")
        
        # Capacity
        if report.capacity_analysis:
            cap = report.capacity_analysis
            lines.append("💪 ANALYSE DE CAPACITÉ:")
            lines.append(f"  • Capacité de base (quotas par défaut): {cap.get('base_capacity', 0)}")
           
            lines.append(f"  • Besoin total exact: {cap.get('total_needed', 0)}")
            lines.append(f"  • Taux d'utilisation: {cap.get('available_utilization_pct', 0):.1f}%")
            
            if cap.get('is_sufficient'):
                lines.append(f"  ✅ Capacité suffisante")
            else:
                shortage = cap.get('total_needed', 0) - cap.get('available_capacity', 0)
                lines.append(f"  ❌ Capacité insuffisante (manque: {shortage})")
            lines.append("")
        
        # Warnings
        if report.warnings:
            lines.append("⚠️  AVERTISSEMENTS:")
            for warning in report.warnings:
                lines.append(f"  {warning}")
            lines.append("")
        
        # Recommendations
        if report.recommendations:
            lines.append("💡 RECOMMANDATIONS:")
            for rec in report.recommendations:
                lines.append(f"  {rec}")
            lines.append("")
        
        # Grade breakdown
        if report.capacity_analysis and report.capacity_analysis.get('grade_capacity'):
            lines.append("👥 RÉPARTITION PAR GRADE:")
            grade_cap = report.capacity_analysis['grade_capacity']
            
            # Sort by count (descending)
            sorted_grades = sorted(grade_cap.items(), key=lambda x: x[1]['count'], reverse=True)
            
            total_teachers = sum(info['count'] for _, info in sorted_grades)
            
            for grade, info in sorted_grades:
                percentage = (info['count'] / total_teachers * 100) if total_teachers > 0 else 0
                quota = self.default_quotas.get(grade, 4)
                lines.append(
                    f"  • {grade:8s}: {info['count']:3d} enseignants ({percentage:5.1f}%) | "
                    f"Quota: {quota} | Capacité: {info['capacity']}"
                )
            lines.append("")
        
        # Quota analysis summary
        if report.quota_analysis and report.quota_analysis.get('distribution'):
            lines.append("📋 AJUSTEMENT DES QUOTAS PAR GRADE:")
            lines.append("  (Allocation proportionnelle pour égalité stricte)")
            lines.append("")
            
            dist = report.quota_analysis['distribution']
            
            # Sort by grade name
            sorted_dist = sorted(dist.items())
            
            for grade, info in sorted_dist:
                reduction = info['reduction_pct']
                sign = "-" if reduction > 0 else "+"
                reduction_abs = abs(reduction)
                
                lines.append(
                    f"  • {grade:8s}: {info['base_quota']} → {info['adjusted_quota']:.1f} "
                    f"({sign}{reduction_abs:.0f}%) | {info['count']} ens. | Total: {info['total_adjusted']}"
                )
            
            lines.append("")
            lines.append(f"  💡 Ajustement global: {report.quota_analysis.get('overall_reduction_pct', 0):.0f}%")
            lines.append(f"  💡 Total ajusté: {report.quota_analysis.get('total_adjusted', 0)} surveillances")
            lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
