"""
Data I/O utility functions for saving and loading pipeline data using pandas.
"""

import os
import pandas as pd
import numpy as np
import pyarrow as pa
from typing import Dict, Any, List, Optional
from datetime import datetime
from hivetracered.models.base_model import Model
from hivetracered.attacks.base_attack import BaseAttack

def get_filename_timestamp() -> str:
    """Get a timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def is_parquet_serializable(value) -> bool:
    """Check if a value can be serialized to Parquet."""
    try:
        # Try to infer the PyArrow type
        pa.infer_type([value])
        return True
    except (pa.ArrowInvalid, pa.ArrowTypeError, TypeError, ValueError):
        return False

def make_parquet_compatible(value):
    # Check for basic Parquet-compatible types
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    # Recursively process lists
    elif isinstance(value, list) or isinstance(value, np.ndarray):
        return [make_parquet_compatible(item) for item in value]
    # Recursively process tuples
    elif isinstance(value, tuple):
        return tuple(make_parquet_compatible(item) for item in value)
    # Recursively process sets
    elif isinstance(value, set):
        return set(make_parquet_compatible(item) for item in value)
    # Recursively process dictionaries
    if isinstance(value, Model):
        return value.get_params()
    elif isinstance(value, BaseAttack):
        return value.get_params()
    elif isinstance(value, dict):
        res = {}
        for k, v in value.items():
            # If the value is an empty dictionary, skip it
            if isinstance(v, dict) and not v:
                res[k] = None
            else:
                converted = make_parquet_compatible(v)
                # Only add if the converted value is serializable
                if is_parquet_serializable(converted):
                    res[k] = converted
        return res
    # Convert any other type to its string representation
    else:
        name = value.__class__.__name__
        args = value.__dict__
        res_args = {}
        for k, v in args.items():
            if not k.startswith("_"):
                converted = make_parquet_compatible(v)
                # Only add if the converted value is serializable
                if is_parquet_serializable(converted):
                    res_args[k] = converted
        return {name: res_args} if res_args else str(value)
    
def save_to_parquet(data: Dict[str, Any], output_dir: str, filename: str) -> str:
    """
    Save data to a parquet file using pandas.
    
    Args:
        data: Dictionary data to save
        output_dir: Directory to save the file
        filename: Base filename (without extension)
        
    Returns:
        Path to the saved file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure filename has timestamp
    if not any(c.isdigit() for c in filename):
        timestamp = get_filename_timestamp()
        filename = f"{filename}_{timestamp}"
    
    # Remove .parquet if present
    if filename.endswith('.parquet'):
        filename = filename[:-8]
        
    file_path = os.path.join(output_dir, f"{filename}.parquet")
    
    # Convert data to Parquet-compatible format
    data_parquet_compatible = make_parquet_compatible(data)
    
    try:
        # Convert to DataFrame if it's a list of dictionaries
        if isinstance(data_parquet_compatible, list) and all(isinstance(item, dict) for item in data_parquet_compatible):
            df = pd.DataFrame(data_parquet_compatible)
        elif isinstance(data_parquet_compatible, dict):
            # Handle nested data structures
            # For simple dictionaries, convert to DataFrame
            if all(not isinstance(v, (dict, list)) for v in data_parquet_compatible.values()):
                df = pd.DataFrame([data_parquet_compatible])
            else:
                # For complex nested dictionaries, serialize to pandas Series
                df = pd.Series(data_parquet_compatible).to_frame('data')
        else:
            # Fallback for other types
            df = pd.DataFrame({'data': [data_parquet_compatible]})
            
        df.to_parquet(file_path, index=False)
        print(f"Data saved to parquet: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving to parquet: {str(e)}")
        return ""

def load_from_parquet(file_path: str) -> Dict[str, Any]:
    """
    Load data from a parquet file.
    
    Args:
        file_path: Path to the parquet file
        
    Returns:
        Dictionary with loaded data
    """
    try:
        df = pd.read_parquet(file_path)
        
        # Convert DataFrame to dictionary or list depending on structure
        if len(df.columns) == 1 and 'data' in df.columns:
            # It was likely a complex nested structure serialized as a Series
            data = df['data'].iloc[0]
        elif len(df) == 1:
            # Single row DataFrame, convert to dict
            data = df.iloc[0].to_dict()
        else:
            # Multiple rows, convert to list of dicts
            data = df.to_dict(orient='records')
            
        print(f"Data loaded from parquet: {file_path}")
        return data
    except Exception as e:
        print(f"Error loading from parquet: {str(e)}")
        return {}

def save_to_json(data: Dict[str, Any], output_dir: str, filename: str) -> str:
    """
    Save data to a JSON file using pandas.
    
    Args:
        data: Dictionary data to save
        output_dir: Directory to save the file
        filename: Base filename (without extension)
        
    Returns:
        Path to the saved file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure filename has timestamp
    if not any(c.isdigit() for c in filename):
        timestamp = get_filename_timestamp()
        filename = f"{filename}_{timestamp}"
    
    # Remove .json if present
    if filename.endswith('.json'):
        filename = filename[:-5]
        
    file_path = os.path.join(output_dir, f"{filename}.json")
    data_parquet_compatible = make_parquet_compatible(data)

    try:
        # Convert to DataFrame if it's a list of dictionaries
        if isinstance(data_parquet_compatible, list) and all(isinstance(item, dict) for item in data_parquet_compatible):
            df = pd.DataFrame(data_parquet_compatible)
            df.to_json(file_path, orient='records', indent=2, force_ascii=False)
        elif isinstance(data_parquet_compatible, dict):
            # Use pandas Series for dictionaries with potential nested structures
            pd.Series(data_parquet_compatible).to_json(file_path, indent=2, force_ascii=False)
        else:
            # Fallback for other types
            pd.Series({'data': data_parquet_compatible}).to_json(file_path, indent=2, force_ascii=False)
            
        print(f"Data saved to JSON: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving to JSON: {str(e)}")
        return ""

def load_from_json(file_path: str) -> Dict[str, Any]:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary with loaded data
    """
    try:
        # Try to read as records first, which is common for data frames
        try:
            df = pd.read_json(file_path, orient='records')
            data = df.to_dict(orient='records')
        except:
            # If that fails, try reading as a general object
            data = pd.read_json(file_path, typ='series').to_dict()
        
        print(f"Data loaded from JSON: {file_path}")
        return data
    except Exception as e:
        print(f"Error loading from JSON: {str(e)}")
        return {}

def save_pipeline_results(data: Dict[str, Any], output_dir: str, stage: str) -> Dict[str, str]:
    """
    Save pipeline results to both parquet and JSON formats.
    
    Args:
        data: Pipeline data to save
        output_dir: Directory to save the files
        stage: Pipeline stage name
        
    Returns:
        Dictionary with saved file paths
    """
    timestamp = get_filename_timestamp()
    filename = f"{stage}_results_{timestamp}"
    
    # Save to both formats
    try:
        path = save_to_parquet(data, output_dir, filename)
    except Exception as e:
        print(f"Error saving to parquet: {str(e)}")
        path = save_to_json(data, output_dir, filename)
    
    return {
        "path": path,
        "timestamp": timestamp
    } 