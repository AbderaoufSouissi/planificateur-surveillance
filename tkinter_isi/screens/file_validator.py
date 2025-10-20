"""
File Validator - Validates Excel files for the surveillance planning system
Checks file structure and required columns
"""

import pandas as pd
from pathlib import Path


class FileValidator:
    """Validator for Excel files used in surveillance planning
    UPDATED for new file format (October 2025)
    """
    
    # Expected column structures - UPDATED for new format
    EXPECTED_STRUCTURES = {
        'teachers': {
            'description': 'Liste des Enseignants',
            'required_columns': [
                'nom_ens',
                'prenom_ens',
                'abrv_ens',
                'email_ens',
                'grade_code_ens',
                'code_smartex_ens',
                'participe_surveillance'
            ],
            'optional_columns': []
        },
        'slots': {
            'description': 'Créneaux de Surveillance (Répartition)',
            'required_columns': [
                'dateExam',
                'h_debut',
                'h_fin',
                'session',
                'type ex',
                'semestre',
                'enseignant',
                'cod_salle'
            ],
            'optional_columns': []
        },
        'voeux': {
            'description': 'Voeux des Enseignants (Souhaits)',
            'required_columns': [
                'Enseignant',
                'Semestre',
                'Session',
                'Jour',
                'Séances'
            ],
            'optional_columns': []
        }
    }
    
    @staticmethod
    def validate_file(file_path, file_type):
        """
        Validate an Excel file against expected structure
        
        Args:
            file_path: Path to the Excel file
            file_type: Type of file ('teachers', 'slots', 'voeux', 'preferences')
            
        Returns:
            tuple: (is_valid, errors, file_info)
        """
        errors = []
        file_info = {}
        
        # Check if file exists
        if not Path(file_path).exists():
            errors.append(f"Le fichier n'existe pas: {file_path}")
            return False, errors, file_info
        
        # Check file extension
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            errors.append("Le fichier doit être au format Excel (.xlsx ou .xls)")
            return False, errors, file_info
        
        # Get expected structure
        if file_type not in FileValidator.EXPECTED_STRUCTURES:
            errors.append(f"Type de fichier inconnu: {file_type}")
            return False, errors, file_info
        
        expected = FileValidator.EXPECTED_STRUCTURES[file_type]
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            file_info['rows'] = len(df)
            file_info['columns'] = len(df.columns)
            file_info['column_names'] = list(df.columns)
            
            # Check if file is empty
            if df.empty:
                errors.append("Le fichier est vide (aucune ligne de données)")
                return False, errors, file_info
            
            # Normalize column names (strip whitespace and make case-insensitive comparison)
            df.columns = df.columns.str.strip()
            actual_columns = set(df.columns)
            
            # Check required columns (exact match)
            required_columns = set(expected['required_columns'])
            missing_columns = required_columns - actual_columns
            
            # Check for wrong file type by comparing column patterns
            if missing_columns:
                # Check if this looks like a different file type
                for other_type, other_struct in FileValidator.EXPECTED_STRUCTURES.items():
                    if other_type != file_type:
                        other_required = set(other_struct['required_columns'])
                        # If actual columns match another file type better
                        if len(actual_columns & other_required) > len(actual_columns & required_columns):
                            errors.append(
                                f"⚠️ Ce fichier semble être du type '{other_struct['description']}' au lieu de '{expected['description']}'"
                            )
                            errors.append(
                                f"Veuillez vérifier que vous avez sélectionné le bon fichier."
                            )
                            break
                
                errors.append(
                    f"Colonnes manquantes: {', '.join(sorted(missing_columns))}"
                )
                errors.append(
                    f"Colonnes requises: {', '.join(sorted(required_columns))}"
                )
                errors.append(
                    f"Colonnes trouvées: {', '.join(sorted(actual_columns))}"
                )
            
            # Check for extra columns (warnings, not errors)
            extra_columns = actual_columns - required_columns - set(expected.get('optional_columns', []))
            if extra_columns:
                file_info['warnings'] = [
                    f"Colonnes supplémentaires (seront ignorées): {', '.join(sorted(extra_columns))}"
                ]
            
            # Validate data types and content for specific columns
            if not errors:
                # Teachers file specific validations
                if file_type == 'teachers':
                    # Check for empty required fields
                    for col in ['nom_ens', 'prenom_ens']:
                        empty_count = df[col].isna().sum()
                        if empty_count > 0:
                            errors.append(f"La colonne '{col}' contient {empty_count} valeur(s) vide(s)")
                    
                    # Validate email format (basic check)
                    if 'email_ens' in df.columns:
                        invalid_emails = df[~df['email_ens'].str.contains('@', na=False)]
                        if len(invalid_emails) > 0:
                            file_info.setdefault('warnings', []).append(
                                f"{len(invalid_emails)} email(s) potentiellement invalide(s)"
                            )
                
                # Slots file specific validations
                elif file_type == 'slots':
                    # Check for empty dates
                    if df['dateExam'].isna().sum() > 0:
                        errors.append(f"La colonne 'dateExam' contient des valeurs vides")
                    
                    # Check time format
                    for col in ['h_debut', 'h_fin']:
                        if col in df.columns and df[col].isna().sum() > 0:
                            errors.append(f"La colonne '{col}' contient des valeurs vides")
                
                # Voeux file specific validations
                elif file_type in ['voeux', 'preferences']:
                    # NEW FORMAT: Check for Enseignant, Jour, Séances columns
                    for col in ['Enseignant', 'Jour']:
                        if col in df.columns and df[col].isna().sum() > 0:
                            errors.append(f"La colonne '{col}' contient des valeurs vides")
                    
                    # Check Séances format (should be comma-separated like "S1,S2,S3")
                    if 'Séances' in df.columns:
                        # Verify it contains comma-separated values
                        sample_seances = df['Séances'].dropna().iloc[0] if len(df['Séances'].dropna()) > 0 else None
                        if sample_seances and ',' not in str(sample_seances):
                            file_info.setdefault('warnings', []).append(
                                "La colonne 'Séances' devrait contenir des valeurs séparées par des virgules (ex: 'S1,S2,S3')"
                            )
            
            # Determine if validation passed
            is_valid = len(errors) == 0
            
            return is_valid, errors, file_info
            
        except Exception as e:
            errors.append(f"Erreur lors de la lecture du fichier: {str(e)}")
            return False, errors, file_info
    
    @staticmethod
    def get_file_summary(file_path):
        """Get a quick summary of an Excel file"""
        try:
            df = pd.read_excel(file_path)
            return {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns)
            }
        except Exception as e:
            return {'error': str(e)}
