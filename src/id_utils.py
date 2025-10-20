"""
ID Management Utilities - Single Source of Truth
=================================================

This module provides centralized functions for handling teacher IDs consistently
across the entire application.

RULE: All internal operations use Enseignants.id (database row ID)
"""

def ensure_teacher_id(value):
    """
    Convert any teacher ID representation to standard database ID (int).
    
    Args:
        value: Teacher ID in any format (int, str, float)
    
    Returns:
        int: Standardized database ID
    
    Raises:
        ValueError: If value cannot be converted to valid ID
    """
    if value is None:
        raise ValueError("Teacher ID cannot be None")
    
    try:
        # Handle float (from pandas)
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            else:
                raise ValueError(f"Invalid teacher ID (non-integer float): {value}")
        
        # Handle string
        if isinstance(value, str):
            return int(value)
        
        # Handle int
        if isinstance(value, int):
            return value
        
        # Unknown type
        raise ValueError(f"Unsupported teacher ID type: {type(value)}")
        
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Cannot convert '{value}' to valid teacher ID: {e}")


def normalize_assignments_keys(assignments):
    """
    Normalize all teacher IDs in assignments dictionary to integers.
    
    Args:
        assignments: Dictionary with teacher IDs as keys
    
    Returns:
        dict: New dictionary with normalized integer keys
    """
    normalized = {}
    for tid, data in assignments.items():
        try:
            normalized_id = ensure_teacher_id(tid)
            normalized[normalized_id] = data
        except ValueError as e:
            print(f"⚠️  Skipping invalid teacher ID '{tid}': {e}")
            continue
    
    return normalized


def safe_teacher_lookup(teachers_df, teacher_id, default=None):
    """
    Safely lookup teacher in DataFrame by ID.
    
    Args:
        teachers_df: DataFrame indexed by teacher ID
        teacher_id: Teacher ID to lookup (any format)
        default: Value to return if not found (None = raise exception)
    
    Returns:
        pandas.Series: Teacher data
    
    Raises:
        KeyError: If teacher not found and default is None
    """
    try:
        tid = ensure_teacher_id(teacher_id)
        
        if tid in teachers_df.index:
            return teachers_df.loc[tid]
        elif default is not None:
            return default
        else:
            raise KeyError(f"Teacher {tid} not found in DataFrame")
            
    except ValueError as e:
        if default is not None:
            return default
        else:
            raise KeyError(f"Invalid teacher ID '{teacher_id}': {e}")


def validate_teacher_df_index(teachers_df):
    """
    Validate that teachers DataFrame is properly indexed.
    
    Args:
        teachers_df: DataFrame to validate
    
    Returns:
        bool: True if valid
    
    Raises:
        ValueError: If DataFrame is not properly indexed
    """
    if teachers_df.empty:
        raise ValueError("Teachers DataFrame is empty")
    
    if teachers_df.index.name not in ['id', 'teacher_id']:
        print(f"⚠️  Warning: Teachers DataFrame index name is '{teachers_df.index.name}', expected 'id' or 'teacher_id'")
    
    # Check if index contains integers
    if not all(isinstance(idx, (int, np.integer)) for idx in teachers_df.index[:5]):
        raise ValueError(
            f"Teachers DataFrame index must contain integers (database IDs), "
            f"found types: {[type(idx).__name__ for idx in teachers_df.index[:5]]}"
        )
    
    # Check for 'id' column (should be same as index)
    if 'id' not in teachers_df.columns:
        print("⚠️  Warning: Teachers DataFrame missing 'id' column")
    
    return True


def prepare_teachers_df_for_export(teachers_df):
    """
    Prepare teachers DataFrame for export functions.
    
    Ensures:
    - Indexed by database ID (integer)
    - Has all required columns
    - No NULL critical fields
    
    Args:
        teachers_df: Raw teachers DataFrame
    
    Returns:
        pandas.DataFrame: Prepared DataFrame
    """
    import pandas as pd
    
    # Make a copy to avoid modifying original
    df = teachers_df.copy()
    
    # Ensure 'id' column exists and is integer
    if 'id' not in df.columns:
        raise ValueError("Teachers DataFrame must have 'id' column")
    
    df['id'] = df['id'].astype(int)
    
    # Set index to 'id' if not already
    if df.index.name != 'id':
        df = df.set_index('id', drop=False)
    
    # Ensure required columns exist
    required_cols = ['nom_ens', 'prenom_ens', 'grade_code_ens']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        raise ValueError(f"Teachers DataFrame missing required columns: {missing_cols}")
    
    # Fill NaN values in optional columns
    if 'email_ens' not in df.columns:
        df['email_ens'] = ''
    else:
        df['email_ens'] = df['email_ens'].fillna('')
    
    # Validate no NULLs in critical columns
    for col in required_cols:
        if df[col].isna().any():
            null_count = df[col].isna().sum()
            print(f"⚠️  Warning: {null_count} teachers have NULL {col}")
    
    return df


# For backwards compatibility
def teacher_id_to_int(tid):
    """Alias for ensure_teacher_id (deprecated, use ensure_teacher_id)."""
    return ensure_teacher_id(tid)


# NumPy import (for type checking)
try:
    import numpy as np
except ImportError:
    # Fallback if numpy not available
    class np:
        integer = int
