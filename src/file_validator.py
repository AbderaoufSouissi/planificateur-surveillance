"""
Excel File Structure Validator
Validates that uploaded Excel files match the expected structure
"""

import pandas as pd
from typing import Dict, List, Tuple


class FileValidator:
    """Validates Excel file structure before import"""
    
    # Expected columns for each file type
    EXPECTED_STRUCTURES = {
        'teachers': {
            'required_columns': [
                'nom_ens',
                'prenom_ens',
                'grade_code_ens',
                'code_smartex_ens',
                'participe_surveillance'
            ],
            'optional_columns': [
                'email_ens'
            ],
            'column_types': {
                'nom_ens': 'string',
                'prenom_ens': 'string',
                'grade_code_ens': 'string',
                'code_smartex_ens': 'numeric',
                'participe_surveillance': 'boolean',
                'email_ens': 'string'
            },
            'min_rows': 1,
            'description': 'Enseignants.xlsx'
        },
        'voeux': {
            'required_columns': [
                'semestre_code.libelle',
                'session.libelle',
                'enseignant_uuid.nom_ens',
                'enseignant_uuid.prenom_ens',
                'jour',
                'seance'
            ],
            'optional_columns': [],
            'column_types': {
                'semestre_code.libelle': 'string',
                'session.libelle': 'string',
                'enseignant_uuid.nom_ens': 'string',
                'enseignant_uuid.prenom_ens': 'string',
                'jour': 'string',
                'seance': 'string'
            },
            'min_rows': 0,  # Can be empty (no preferences)
            'description': 'Souhaits.xlsx (Voeux)',
            'valid_values': {
                'seance': ['S1', 'S2', 'S3', 'S4']
            }
        },
        'slots': {
            'required_columns': [
                'dateExam',
                'h_debut',
                'h_fin',
                'cod_salle'
            ],
            'optional_columns': [
                'enseignant'
            ],
            'column_types': {
                'dateExam': 'date',
                'h_debut': 'time',
                'h_fin': 'time',
                'cod_salle': 'string',
                'enseignant': 'numeric',
                'matiere': 'string'
            },
            'min_rows': 1,
            'description': 'Repartitions.xlsx (Créneaux)'
        }
    }
    
    # Valid grade codes
    VALID_GRADES = ['PR', 'MA', 'MC', 'PTC', 'AC', 'V','VA','AS', 'EX', 'PES']
    
    @staticmethod
    def validate_file(file_path: str, file_type: str) -> Tuple[bool, List[str], Dict]:
        """
        Validate an Excel file structure
        
        Args:
            file_path: Path to Excel file
            file_type: Type of file ('teachers', 'voeux', 'slots')
        
        Returns:
            Tuple of (is_valid, error_messages, file_info)
        """
        errors = []
        warnings = []
        file_info = {}
        
        try:
            # Load the file
            df = pd.read_excel(file_path)
            file_info['rows'] = len(df)
            file_info['columns'] = len(df.columns)
            
            if file_type not in FileValidator.EXPECTED_STRUCTURES:
                errors.append(f"Type de fichier inconnu: {file_type}")
                return False, errors, file_info
            
            expected = FileValidator.EXPECTED_STRUCTURES[file_type]
            
            # Check minimum rows
            if len(df) < expected['min_rows']:
                errors.append(
                    f"Fichier vide ou insuffisant. "
                    f"Minimum {expected['min_rows']} ligne(s) requise(s), "
                    f"trouvé {len(df)}"
                )
            
            # Check required columns
            missing_columns = []
            for col in expected['required_columns']:
                if col not in df.columns:
                    missing_columns.append(col)
            
            if missing_columns:
                errors.append(
                    f"Colonnes obligatoires manquantes: {', '.join(missing_columns)}\n"
                    f"Colonnes attendues: {', '.join(expected['required_columns'])}\n"
                    f"Colonnes trouvées: {', '.join(df.columns.tolist())}"
                )
                return False, errors, file_info
            
            # Check optional columns (warnings only)
            for col in expected['optional_columns']:
                if col not in df.columns:
                    warnings.append(f"Colonne optionnelle manquante: {col}")
            
            # Validate data types and values
            if file_type == 'teachers':
                validation_errors = FileValidator._validate_teachers(df)
                errors.extend(validation_errors)
            elif file_type == 'voeux':
                validation_errors = FileValidator._validate_voeux(df)
                errors.extend(validation_errors)
            elif file_type == 'slots':
                validation_errors = FileValidator._validate_slots(df)
                errors.extend(validation_errors)
            
            # Add warnings to info
            if warnings:
                file_info['warnings'] = warnings
            
            # File is valid if no errors
            is_valid = len(errors) == 0
            
            return is_valid, errors, file_info
            
        except Exception as e:
            errors.append(f"Erreur lors de la lecture du fichier: {str(e)}")
            return False, errors, file_info
    
    @staticmethod
    def _validate_teachers(df: pd.DataFrame) -> List[str]:
        """Validate teachers file structure and data"""
        errors = []
        
        # Check for empty required fields
        required_fields = ['nom_ens', 'prenom_ens', 'grade_code_ens', 'code_smartex_ens']
        for field in required_fields:
            null_count = df[field].isna().sum()
            if null_count > 0:
                errors.append(
                    f"⚠️  {null_count} ligne(s) avec '{field}' vide. "
                    f"Toutes les lignes doivent avoir cette valeur."
                )
        
        # Validate grade codes
        if 'grade_code_ens' in df.columns:
            invalid_grades = df[~df['grade_code_ens'].isin(FileValidator.VALID_GRADES + [pd.NA, None])]
            if len(invalid_grades) > 0:
                unique_invalid = invalid_grades['grade_code_ens'].unique().tolist()
                errors.append(
                    f"⚠️  Codes de grade invalides trouvés: {', '.join(map(str, unique_invalid))}\n"
                    f"Codes valides: {', '.join(FileValidator.VALID_GRADES)}"
                )
        
        # Validate code_smartex_ens (should be numeric)
        if 'code_smartex_ens' in df.columns:
            try:
                non_numeric = df[df['code_smartex_ens'].notna() & 
                              ~df['code_smartex_ens'].astype(str).str.match(r'^\d+$')]
                if len(non_numeric) > 0:
                    errors.append(
                        f"⚠️  {len(non_numeric)} code(s) enseignant non-numérique(s). "
                        f"'code_smartex_ens' doit être un nombre."
                    )
            except:
                pass
        
        # Check for duplicate codes
        if 'code_smartex_ens' in df.columns:
            codes = df['code_smartex_ens'].dropna()
            duplicates = codes[codes.duplicated()].unique()
            if len(duplicates) > 0:
                errors.append(
                    f"⚠️  Codes enseignant dupliqués: {', '.join(map(str, duplicates))}\n"
                    f"Chaque enseignant doit avoir un code unique."
                )
        
        # Validate participe_surveillance (should be boolean/0/1)
        if 'participe_surveillance' in df.columns:
            valid_values = [True, False, 1, 0, '1', '0', 'True', 'False', 'true', 'false']
            invalid = df[~df['participe_surveillance'].isin(valid_values + [pd.NA, None])]
            if len(invalid) > 0:
                errors.append(
                    f"⚠️  {len(invalid)} valeur(s) invalide(s) pour 'participe_surveillance'. "
                    f"Valeurs acceptées: True/False, 1/0"
                )
        
        return errors
    
    @staticmethod
    def _validate_voeux(df: pd.DataFrame) -> List[str]:
        """Validate voeux file structure and data"""
        errors = []
        
        # Check for empty required fields
        required_fields = [
            'semestre_code.libelle',
            'session.libelle', 
            'enseignant_uuid.nom_ens', 
            'enseignant_uuid.prenom_ens', 
            'jour', 
            'seance'
        ]
        for field in required_fields:
            if field in df.columns:
                null_count = df[field].isna().sum()
                if null_count > 0:
                    errors.append(
                        f"⚠️  {null_count} ligne(s) avec '{field}' vide. "
                        f"Chaque voeu doit avoir toutes les informations requises."
                    )
        
        # Validate seance values
        if 'seance' in df.columns:
            valid_seances = ['S1', 'S2', 'S3', 'S4']
            invalid_seances = df[~df['seance'].isin(valid_seances + [pd.NA, None])]
            if len(invalid_seances) > 0:
                unique_invalid = invalid_seances['seance'].unique().tolist()
                errors.append(
                    f"⚠️  Valeurs de séance invalides: {', '.join(map(str, unique_invalid))}\n"
                    f"Valeurs valides: {', '.join(valid_seances)}"
                )
        
        # Check jour format (should be numeric representing day number)
        if 'jour' in df.columns:
            try:
                non_numeric = df[df['jour'].notna() & 
                              ~df['jour'].astype(str).str.match(r'^\d+$')]
                if len(non_numeric) > 0:
                    errors.append(
                        f"⚠️  {len(non_numeric)} valeur(s) de 'jour' non-numérique(s). "
                        f"'jour' doit être un numéro de jour (1, 2, 3, etc.)"
                    )
            except:
                pass
        
        return errors
    
    @staticmethod
    def _validate_slots(df: pd.DataFrame) -> List[str]:
        """Validate slots file structure and data"""
        errors = []
        
        # Check for empty required fields
        required_fields = ['dateExam', 'h_debut', 'h_fin', 'cod_salle']
        for field in required_fields:
            if field in df.columns:
                null_count = df[field].isna().sum()
                if null_count > 0:
                    errors.append(
                        f"⚠️  {null_count} ligne(s) avec '{field}' vide. "
                        f"Chaque créneau doit avoir une date, heures et salle."
                    )
        
        # Validate date format
        if 'dateExam' in df.columns:
            try:
                # Try to parse dates
                pd.to_datetime(df['dateExam'], errors='coerce')
            except Exception as e:
                errors.append(
                    f"⚠️  Erreur de format de date dans 'dateExam': {str(e)}"
                )
        
        # Validate time format (accepts both datetime and time-only formats)
        for time_col in ['h_debut', 'h_fin']:
            if time_col in df.columns:
                try:
                    # Check if times are parseable (accept datetime format like 30/12/1999 10:30:00)
                    invalid_times = []
                    for idx, val in df[time_col].items():
                        if pd.notna(val):
                            try:
                                # Try parsing as datetime first (handles Excel datetime format)
                                if isinstance(val, str):
                                    # Try common formats
                                    formats = [
                                        '%d/%m/%Y %H:%M:%S',  # 30/12/1999 10:30:00
                                        '%Y-%m-%d %H:%M:%S',  # 1999-12-30 10:30:00
                                        '%H:%M:%S',           # 10:30:00
                                        '%H:%M'               # 10:30
                                    ]
                                    parsed = False
                                    for fmt in formats:
                                        try:
                                            pd.to_datetime(val, format=fmt, errors='raise')
                                            parsed = True
                                            break
                                        except:
                                            continue
                                    if not parsed:
                                        invalid_times.append(idx)
                                # If it's already a datetime/time object, it's valid
                                elif not isinstance(val, (pd.Timestamp, pd.Timedelta)):
                                    # Try to convert to datetime anyway
                                    pd.to_datetime(val, errors='raise')
                            except:
                                invalid_times.append(idx)
                    
                    if invalid_times and len(invalid_times) > 5:
                        errors.append(
                            f"⚠️  {len(invalid_times)} valeur(s) de temps invalide(s) dans '{time_col}'. "
                            f"Formats acceptés: DD/MM/YYYY HH:MM:SS, HH:MM:SS, HH:MM (ex: 30/12/1999 10:30:00 ou 10:30:00)"
                        )
                except:
                    pass
        
        # Check that h_debut < h_fin (handle both datetime and time-only formats)
        if 'h_debut' in df.columns and 'h_fin' in df.columns:
            try:
                df_copy = df.copy()
                
                # Parse times with multiple format support
                def parse_time_flexible(time_val):
                    """Parse time from various formats"""
                    if pd.isna(time_val):
                        return pd.NaT
                    
                    # If already a Timestamp, return it
                    if isinstance(time_val, pd.Timestamp):
                        return time_val
                    
                    # If string, try different formats
                    if isinstance(time_val, str):
                        formats = [
                            '%d/%m/%Y %H:%M:%S',  # 30/12/1999 10:30:00
                            '%Y-%m-%d %H:%M:%S',  # 1999-12-30 10:30:00
                            '%H:%M:%S',           # 10:30:00
                            '%H:%M'               # 10:30
                        ]
                        for fmt in formats:
                            try:
                                return pd.to_datetime(time_val, format=fmt)
                            except:
                                continue
                    
                    # Last resort: let pandas infer
                    try:
                        return pd.to_datetime(time_val, errors='coerce')
                    except:
                        return pd.NaT
                
                df_copy['h_debut_dt'] = df_copy['h_debut'].apply(parse_time_flexible)
                df_copy['h_fin_dt'] = df_copy['h_fin'].apply(parse_time_flexible)
                
                # Compare only the time components (ignore date part)
                invalid = df_copy[
                    (df_copy['h_debut_dt'].notna()) & 
                    (df_copy['h_fin_dt'].notna()) &
                    (df_copy['h_debut_dt'].dt.time >= df_copy['h_fin_dt'].dt.time)
                ]
                
                if len(invalid) > 0:
                    errors.append(
                        f"⚠️  {len(invalid)} créneau(x) où h_debut >= h_fin. "
                        f"L'heure de début doit être avant l'heure de fin."
                    )
            except Exception as e:
                # Don't fail validation on comparison errors, just skip
                pass
        
        # Validate enseignant codes if present (should be numeric)
        if 'enseignant' in df.columns:
            try:
                non_numeric = df[df['enseignant'].notna() & 
                              ~df['enseignant'].astype(str).str.match(r'^\d+$')]
                if len(non_numeric) > 0:
                    errors.append(
                        f"⚠️  {len(non_numeric)} code(s) enseignant responsable non-numérique(s). "
                        f"'enseignant' doit être un code numérique."
                    )
            except:
                pass
        
        return errors
    
    @staticmethod
    def get_file_summary(file_path: str) -> Dict:
        """Get summary statistics of an Excel file"""
        try:
            df = pd.read_excel(file_path)
            
            summary = {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': df.columns.tolist(),
                'null_counts': df.isnull().sum().to_dict(),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()}
            }
            
            return summary
        except Exception as e:
            return {'error': str(e)}


def validate_all_files(teachers_file: str, voeux_file: str, slots_file: str) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Validate all three required files
    
    Returns:
        Tuple of (all_valid, errors_by_file)
    """
    results = {}
    all_valid = True
    
    files = {
        'teachers': teachers_file,
        'voeux': voeux_file,
        'slots': slots_file
    }
    
    for file_type, file_path in files.items():
        is_valid, errors, info = FileValidator.validate_file(file_path, file_type)
        
        results[file_type] = {
            'valid': is_valid,
            'errors': errors,
            'info': info
        }
        
        if not is_valid:
            all_valid = False
    
    return all_valid, results


if __name__ == '__main__':
    # Test the validator
    import sys
    import os
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    teachers_file = os.path.join(base_dir, 'resources', 'Enseignants.xlsx')
    voeux_file = os.path.join(base_dir, 'resources', 'Souhaits.xlsx')
    slots_file = os.path.join(base_dir, 'resources', 'Repartitions.xlsx')
    
    print("="*80)
    print("VALIDATION DES FICHIERS EXCEL")
    print("="*80)
    
    all_valid, results = validate_all_files(teachers_file, voeux_file, slots_file)
    
    for file_type, result in results.items():
        print(f"\n📄 {FileValidator.EXPECTED_STRUCTURES[file_type]['description']}")
        print("-" * 80)
        
        if result['valid']:
            print("✅ VALIDE")
            print(f"   {result['info']['rows']} lignes, {result['info']['columns']} colonnes")
        else:
            print("❌ INVALIDE")
            for error in result['errors']:
                print(f"   • {error}")
        
        if 'warnings' in result['info']:
            for warning in result['info']['warnings']:
                print(f"   ⚠️  {warning}")
    
    print("\n" + "="*80)
    if all_valid:
        print("✅ TOUS LES FICHIERS SONT VALIDES")
    else:
        print("❌ CERTAINS FICHIERS CONTIENNENT DES ERREURS")
    print("="*80)
