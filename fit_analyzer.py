import fitdecode
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QFileDialog
from training_plot_window import TrainingPlotWindow

class FitAnalyzer:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.file_paths = []
        self.dataframes = []
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(None, 'Wähle eine FIT-Datei', 
                                                str(Path.home()), 'FIT Dateien (*.fit)')
        if file_path:
            self.file_paths.append(file_path)
            return file_path
        return None
    
    def parse_fit_file(self, file_path):
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
            # Format time as HH:MM:SS for display
            df['time_of_day'] = df['timestamp'].dt.strftime('%H:%M:%S')

            if 'heart_rate' in df.columns:
                self.calculate_hr_zones(df)
        
        # Add file path as an identifier for this dataset
        df['file_source'] = Path(file_path).stem
        
        # Add to dataframes list
        self.dataframes.append(df)
        return df
    
    def calculate_hr_zones(self, df, max_hr=None):
        if not max_hr:
            if 'heart_rate' in df.columns:
                max_hr = df['heart_rate'].max()
            else:
                return
                
        zone_boundaries = [0.6, 0.7, 0.8, 0.9, 1.0]
        df['hr_zone'] = 0
        
        for i, boundary in enumerate(zone_boundaries):
            df.loc[df['heart_rate'] >= boundary * max_hr, 'hr_zone'] = i + 1
    
    def run(self):
        if self.select_file():
            df = self.parse_fit_file(self.file_paths[0])
            if df is not None:
                window = TrainingPlotWindow(self.dataframes)
                window.show()
                return self.app.exec_()
            else:
                print("Fehler beim Parsen der Datei.")
                return 1
        else:
            print("Keine Datei ausgewählt.")
            return 1
