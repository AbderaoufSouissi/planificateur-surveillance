import os
import pandas as pd
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from pathlib import Path
import traceback


def generate_convocations(session_id=None, db_manager=None, output_dir=None):
    """
    Generate individual convocations for all teachers
    
    Args:
        session_id: The planning session ID to generate convocations for
        db_manager: DatabaseManager instance to fetch data
        output_dir: Directory to save generated files (optional)
        
    Returns:
        dict with 'success', 'count', 'output_dir', and 'message' keys
    """
    try:
        # Build absolute paths
        base_dir = Path(__file__).parent
        template_path = base_dir / ".." / "resources" / "Template de convocation de surveillance.docx"
        
        if not template_path.exists():
            return {
                'success': False,
                'count': 0,
                'message': f"Template non trouvé: {template_path}"
            }
        
        # Set output directory
        if output_dir is None:
            output_dir = base_dir / ".." / "output" / "convocations"
        else:
            output_dir = Path(output_dir) / "convocations"
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # If no database manager or session_id, generate sample
        if db_manager is None or session_id is None:
            return generate_sample_convocation(template_path, output_dir)
        
        # Get teachers with assignments
        teachers_data = db_manager.get_teachers(session_id, participating_only=True)
        
        # Check if DataFrame is empty (correct way to check)
        if teachers_data.empty:
            return {
                'success': False,
                'count': 0,
                'message': "Aucun enseignant avec affectations trouvé"
            }
        
        generated_count = 0
        
        # Convert DataFrame to list of dictionaries for iteration
        teachers_list = teachers_data.to_dict('records')
        
        for teacher in teachers_list:
            # Get teacher's first name and last name
            nom = teacher.get('nom_ens', teacher.get('nom', ''))
            prenom = teacher.get('prenom_ens', teacher.get('prenom', ''))
            
            # Build full name for display and filename
            if prenom and nom:
                teacher_name = f"{nom} {prenom}"
                filename_base = f"{nom}_{prenom}"
            elif nom:
                teacher_name = nom
                filename_base = nom
            else:
                continue  # Skip if no name available
            
            # Get teacher's assignments
            assignments = db_manager.get_teacher_assignments(session_id, teacher_name)
            
            if not assignments:
                continue
            
            # Prepare surveillances data - already in correct format from DB
            surveillances_list = assignments
            
            # Load template
            doc = DocxTemplate(str(template_path))
            
            # Rendering context
            context = {
                'teacher_name': teacher_name,
                'grade': teacher.get('grade_code_ens', teacher.get('grade', '')),
                'department': teacher.get('departement', 'Informatique'),
                'surveillances': surveillances_list,
            }
            
            # Generate safe filename with first name and last name
            safe_name = filename_base.replace(' ', '_').replace('/', '_').replace('\\', '_')
            output_path = output_dir / f"convocation_{safe_name}.docx"
            
            # Render and save
            doc.render(context)
            doc.save(str(output_path))
            
            generated_count += 1
            print(f"✅ Generated convocation for {teacher_name}")
        
        return {
            'success': True,
            'count': generated_count,
            'output_dir': str(output_dir),
            'message': f"{generated_count} convocation(s) générée(s) avec succès!"
        }
        
    except Exception as e:
        print(f"❌ Error generating convocations: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'count': 0,
            'message': f"Erreur: {str(e)}"
        }


def generate_sample_convocation(template_path, output_dir):
    """Generate a sample convocation for testing"""
    try:
        # Example data
        surveillances_df = pd.DataFrame({
            'date': ['2025-10-15', '2025-10-16', '2025-10-17'],
            'heure': ['09:00:00', '10:30:00', '12:00:00'],
            'duree': ['1.5H', '1.5H', '1.5H'],
        })
        
        # Load template
        doc = DocxTemplate(str(template_path))
        
        # Rendering context
        context = {
            'teacher_name': 'Zahreddine Hammemi',
            'grade': 'Professeur',
            'department': 'Informatique',
            'surveillances': surveillances_df.to_dict(orient='records'),
        }
        
        output_path = output_dir / "convocation_sample.docx"
        
        # Render and save
        doc.render(context)
        doc.save(str(output_path))
        
        print(f"✅ Sample convocation saved at: {output_path}")
        
        return {
            'success': True,
            'count': 1,
            'output_dir': str(output_dir),
            'message': "Convocation d'exemple générée avec succès!"
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
    result = generate_convocations()
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"📁 Output directory: {result['output_dir']}")
    else:
        print(f"❌ {result['message']}")
