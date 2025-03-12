import pandas as pd
import numpy as np
import fitdecode
from pathlib import Path
from datetime import datetime

def parse_fit_file(file_path):
    """
    Parse a FIT file and return a DataFrame with proper numeric columns for filtering
    
    Args:
        file_path: Path to the FIT file
        
    Returns:
        DataFrame containing all data from the FIT file or None if parsing fails
    """
    if not file_path:
        return None
    
    try:
        data = []
        with fitdecode.FitReader(file_path) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.records.FitDataMessage) and frame.name == "record":
                    record = {field.name: field.value for field in frame.fields}
                    data.append(record)
        
        if not data:
            print(f"Keine Datensätze in der FIT-Datei gefunden: {file_path}")
            return None
            
        df = pd.DataFrame(data)
        
        # Timestamp-Verarbeitung
        if 'timestamp' in df.columns:
            # Ensure timestamp is a datetime object
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df = df.sort_values(by='timestamp')
            
            # Create numeric version for filtering - convert to Unix timestamp
            df['timestamp_numeric'] = df['timestamp'].astype(np.int64) // 10**9
            
            # Add time_of_day column - formatted time string
            df['time_of_day'] = df['timestamp'].dt.strftime('%H:%M:%S')
            
            # Calculate seconds since midnight for numeric representation
            df['time_of_day_numeric'] = (df['timestamp'].dt.hour * 3600 + 
                                         df['timestamp'].dt.minute * 60 + 
                                         df['timestamp'].dt.second)
            
            # Calculate elapsed time in minutes
            df['elapsed_time'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds() / 60
        
        # Add file path as an identifier for this dataset
        df['file_source'] = Path(file_path).stem
        
        return df
    except Exception as e:
        print(f"Fehler beim Parsen der FIT-Datei {file_path}: {e}")
        return None


def get_axis_color(index):
    """
    Return a color for the given axis index
    """
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    return colors[index % len(colors)]

def get_line_style(file_index):
    """
    Return a line style for the given file index
    """
    styles = ['-', '--', '-.', ':']
    return styles[file_index % len(styles)]

def safe_numeric_filter(df, column, min_val=None, max_val=None):
    """
    Safely filter a dataframe column, handling both numeric and non-numeric types
    
    Args:
        df: DataFrame to filter
        column: Column name to filter
        min_val: Minimum value for filtering (inclusive)
        max_val: Maximum value for filtering (inclusive)
    
    Returns:
        Filtered DataFrame
    """
    if column not in df.columns:
        return df
        
    # Check if the column is numeric
    if pd.api.types.is_numeric_dtype(df[column]):
        # Numeric column, normal filtering
        filtered_df = df.copy()
        if min_val is not None:
            filtered_df = filtered_df[filtered_df[column] >= min_val]
        if max_val is not None:
            filtered_df = filtered_df[filtered_df[column] <= max_val]
        return filtered_df
    else:
        # Non-numeric column, look for numeric alternative
        numeric_column = f"{column}_numeric"
        
        if numeric_column in df.columns:
            # Use the numeric column version
            filtered_df = df.copy()
            if min_val is not None:
                filtered_df = filtered_df[filtered_df[numeric_column] >= min_val]
            if max_val is not None:
                filtered_df = filtered_df[filtered_df[numeric_column] <= max_val]
            return filtered_df
        else:
            print(f"Warnung: Nicht-numerische Spalte '{column}' kann nicht gefiltert werden und hat keine numerische Alternative.")
            return df