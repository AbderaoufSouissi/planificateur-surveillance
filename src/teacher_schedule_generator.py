import os
import pandas as pd
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from pathlib import Path
import traceback
from datetime import datetime


def generate_planning(session_id=None, db_manager=None, output_dir=None):
    """
    Generate daily planning documents for all sessions
    
    Args:
        session_id: The planning session ID to generate documents for
        db_manager: DatabaseManager instance to fetch data
        output_dir: Directory to save generated files (optional)
        
    Returns:
        dict with 'success', 'count', 'output_dir', and 'message' keys
    """
    try:
        # Build absolute paths
        base_dir = Path(__file__).parent
        template_path = base_dir / ".." / "resources" / "template affectation des surveillance enseignants par jour.docx"
        
        if not template_path.exists():
            return {
                'success': False,
                'count': 0,
                'message': f"Template non trouvé: {template_path}"
            }
        
        # Set output directory
        if output_dir is None:
            output_dir = base_dir / ".." / "output" / "planning"
        else:
            output_dir = Path(output_dir) / "planning"
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # If no database manager or session_id, generate sample
        if db_manager is None or session_id is None:
            return generate_sample_planning(template_path, output_dir)
        
        # Get all slots for the session
        slots = db_manager.get_slots(session_id)
        
        if not slots:
            return {
                'success': False,
                'count': 0,
                'message': "Aucun créneau trouvé pour cette session"
            }
        
        # Get session info
        session_info = db_manager.get_session_info(session_id)
        
        # Time to session mapping
        TIME_TO_SEANCE = {
            '08:30:00': 'S1',
            '10:30:00': 'S2',
            '12:30:00': 'S3',
            '14:30:00': 'S4'
        }
        
        # Group slots by date and time (session)
        slot_groups = {}
        for slot in slots:
            key = (slot['date_examen'], slot['heure_debut'])
            if key not in slot_groups:
                slot_groups[key] = []
            slot_groups[key].append(slot)
        
        generated_count = 0
        
        # Generate a document for each date+session combination
        for (date, time), group_slots in slot_groups.items():
            # Get assignments for these slots
            assignments_for_slots = []
            
            for slot in group_slots:
                assignments = db_manager.get_slot_assignments(session_id, slot['slot_id'])
                for assignment in assignments:
                    assignments_for_slots.append({
                        'enseignant': assignment.get('nom_enseignant', ''),
                        'salle': slot.get('salle', ''),
                        'examen': slot.get('matiere', ''),
                        'quota': assignment.get('quota', '')
                    })
            
            if not assignments_for_slots:
                continue
            
            # Prepare dataframe
            surveillances_df = pd.DataFrame(assignments_for_slots)
            
            # Load template
            doc = DocxTemplate(str(template_path))
            
            # Parse date
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d/%m/%Y")
            except:
                formatted_date = date
            
            # Get seance from time
            seance = TIME_TO_SEANCE.get(time, 'S1')
            
            # Rendering context
            context = {
                'semestre': session_info.get('semestre', 'SEMESTRE 1') if session_info else 'SEMESTRE 1',
                'session': session_info.get('type_session', 'Principale') if session_info else 'Principale',
                'date': formatted_date,
                'seance': seance,
                'surveillances': surveillances_df.to_dict(orient='records'),
            }
            
            # Generate safe filename
            safe_date = date.replace('-', '_')
            output_path = output_dir / f"planning_{safe_date}_{seance}.docx"
            
            # Render and save
            doc.render(context)
            doc.save(str(output_path))
            
            generated_count += 1
        
        return {
            'success': True,
            'count': generated_count,
            'output_dir': str(output_dir),
            'message': f"{generated_count} planning(s) journalier(s) généré(s) avec succès!"
        }
        
    except Exception as e:
        print(f"❌ Error generating planning: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'count': 0,
            'message': f"Erreur: {str(e)}"
        }


def generate_sample_planning(template_path, output_dir):
    """Generate a sample planning for testing"""
    try:
        # Example data
        surveillances_df = pd.DataFrame({
            'enseignant': ['tes1', 'tes2', 'tes3', 'tes4', 'tes5', 'tes6', 'tes7', 'tes8', 'tes9', 'tes10'],
            'salle': ['B203', 'A408','A408', 'B203', 'A408', 'B203', 'A408', 'B203', 'A408', 'B203'],
        })
        
        # Load template
        doc = DocxTemplate(str(template_path))
        
        # Rendering context
        context = {
            'semestre': 'SEMESTRE 1',
            'session': 'Principale',
            'date': '15/12/2025',
            'seance': 'S2',
            'surveillances': surveillances_df.to_dict(orient='records'),
        }
        
        output_path = output_dir / "planning_sample.docx"
        
        # Render and save
        doc.render(context)
        doc.save(str(output_path))
        
        print(f"✅ Sample planning saved at: {output_path}")
        
        return {
            'success': True,
            'count': 1,
            'output_dir': str(output_dir),
            'message': "Planning d'exemple généré avec succès!"
        }
        
    except Exception as e:
        print(f"❌ Error generating sample: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'count': 0,
            'message': f"Erreur: {str(e)}"
        }


# For backward compatibility - run as script
if __name__ == "__main__":
    result = generate_planning()
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"📁 Output directory: {result['output_dir']}")
    else:
        print(f"❌ {result['message']}")
