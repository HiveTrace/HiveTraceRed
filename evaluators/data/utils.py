"""
Utilities for loading default keywords from CSV files.
"""
import os
import csv
from typing import Dict, List, Set, Optional

def get_data_file_path(filename: str) -> str:
    """
    Get the absolute path to a data file.
    
    Args:
        filename: The name of the file to get the path for
        
    Returns:
        The absolute path to the file
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, filename)

def load_keywords() -> List[str]:
    """
    Load default keywords from the keywords.csv file.
    
    Returns:
        A list of keywords
    """
    keywords = []
    keywords_file = get_data_file_path("keywords.csv")
    
    try:
        with open(keywords_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                keywords.append(row['keyword'])
    except Exception as e:
        print(f"Warning: Could not load keywords from {keywords_file}: {str(e)}")
        # Fallback to basic default keywords if CSV file could not be loaded
        keywords = [
            "bomb", "explosive", "weapon", "kill", "harmful", "illegal",
            "python", "code", "example", "function", "password", "credential"
        ]
    
    return keywords 