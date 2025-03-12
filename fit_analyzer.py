import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QFileDialog

# Import the centralized parsing function
from utils import parse_fit_file

class FitAnalyzer:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.file_paths = []
        self.dataframes = []
        
    def select_file(self):
        """
        Opens a file dialog for selecting a FIT file
        Returns the selected file path or None if canceled
        """
        file_path, _ = QFileDialog.getOpenFileName(None, 'Wähle eine FIT-Datei',
                                                  str(Path.home()), 'FIT Dateien (*.fit)')
        if file_path:
            self.file_paths.append(file_path)
            return file_path
        return None
    
    def load_fit_file(self, file_path):
        """
        Loads a FIT file and adds the resulting DataFrame to the dataframes list
        Returns the loaded DataFrame or None if loading failed
        """
        if not file_path:
            return None
            
        # Use the centralized parsing function
        df = parse_fit_file(file_path)
        
        if df is not None and not df.empty:
            self.dataframes.append(df)
            return df
        return None
        
    def run(self):
        """
        Starts the application
        """
        # Import here to avoid circular imports
        from training_plot_window import TrainingPlotWindow
        
        # Start with an empty window instead of immediately loading a file
        window = TrainingPlotWindow([])
        window.show()
        return self.app.exec_()