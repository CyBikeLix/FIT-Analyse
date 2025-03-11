import pandas as pd
import numpy as np
import fitdecode
from pathlib import Path

def parse_fit_file(file_path):
    """
    Parse a FIT file and return a DataFrame
    """
    if not file_path:
        return None
    
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
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values(by='timestamp')
        
        if 'distance' in df.columns and 'speed' in df.columns:
            df['pace'] = np.where(df['speed'] > 0, 16.6666667 / df['speed'], 0)
        
        df['elapsed_time'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds() / 60
        df['time_of_day'] = df['timestamp'].dt.strftime('%H:%M:%S')

        if 'heart_rate' in df.columns:
            calculate_hr_zones(df)
    
    # Add file path as an identifier for this dataset
    df['file_source'] = Path(file_path).stem
    
    return df

def calculate_hr_zones(df, max_hr=None):
    """
    Calculate heart rate zones and add to DataFrame
    """
    if not max_hr:
        if 'heart_rate' in df.columns:
            max_hr = df['heart_rate'].max()
        else:
            return
            
    zone_boundaries = [0.6, 0.7, 0.8, 0.9, 1.0]
    df['hr_zone'] = 0
    
    for i, boundary in enumerate(zone_boundaries):
        df.loc[df['heart_rate'] >= boundary * max_hr, 'hr_zone'] = i + 1

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
