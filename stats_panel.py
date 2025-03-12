import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel
from utils import safe_numeric_filter

class StatsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.init_ui()
        
    def init_ui(self):
        self.layout = QGridLayout(self)
        
        # Header
        self.header_label = QLabel("Daten-Statistik")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(self.header_label, 0, 0, 1, 3, alignment=Qt.AlignCenter)
        
        # Stats boxes will be added dynamically
        self.stats_boxes = {}
        
    def add_stats_box(self, column_name, file_name=None):
        key = f"{column_name}_{file_name}" if file_name else column_name
        
        # Remove if exists
        if key in self.stats_boxes:
            self.remove_stats_box(key)
            
        row = len(self.stats_boxes) + 1
        
        # Create frame for stats box
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Box)
        stats_frame.setLineWidth(2)
        
        # Create layout for the frame
        box_layout = QGridLayout(stats_frame)
        
        # Data description (title)
        title_label = QLabel(column_name)
        if file_name:
            title_label.setText(f"{column_name} - {file_name}")
        title_label.setStyleSheet("font-weight: bold;")
        box_layout.addWidget(title_label, 0, 0, 1, 3, alignment=Qt.AlignCenter)
        
        # Average value
        avg_value = QLabel("--")
        avg_value.setStyleSheet("font-size: 24px;")
        box_layout.addWidget(avg_value, 2, 0, 1, 3, alignment=Qt.AlignCenter)
        
        # Min and Max
        min_value = QLabel("--")
        box_layout.addWidget(min_value, 4, 0, alignment=Qt.AlignLeft)
        
        max_value = QLabel("--")
        box_layout.addWidget(max_value, 4, 2, alignment=Qt.AlignRight)
        
        # Add to main layout
        self.layout.addWidget(stats_frame, row, 0, 1, 3)
        
        # Store references
        self.stats_boxes[key] = {
            'frame': stats_frame,
            'avg': avg_value,
            'min': min_value,
            'max': max_value
        }
        
    def remove_stats_box(self, key):
        if key in self.stats_boxes:
            # Remove from layout and delete
            self.layout.removeWidget(self.stats_boxes[key]['frame'])
            self.stats_boxes[key]['frame'].deleteLater()
            del self.stats_boxes[key]
            
    def update_stats(self, column_name, df, x_column, file_name=None, x_min=None, x_max=None):
        key = f"{column_name}_{file_name}" if file_name else column_name
        
        if key not in self.stats_boxes:
            self.add_stats_box(column_name, file_name)
        
        filtered_df = df
        
        if x_min is not None and x_max is not None:
            try:
                # Handle timestamp specifically
                if x_column == 'timestamp_numeric' and 'timestamp' in df.columns:
                    # Filter using timestamp_numeric but keep the display format
                    filtered_df = safe_numeric_filter(df, x_column, x_min, x_max)
                elif x_column == 'time_of_day_numeric' and 'time_of_day' in df.columns:
                    # Filter using time_of_day_numeric but keep the display format
                    filtered_df = safe_numeric_filter(df, x_column, x_min, x_max)
                else:
                    # Standard numeric filtering
                    filtered_df = safe_numeric_filter(df, x_column, x_min, x_max)
            except Exception as e:
                # Fall back to all data on error
                print(f"Fehler beim Filtern der Daten: {e}")
                filtered_df = df
            
        if len(filtered_df) > 0 and column_name in filtered_df.columns:
            avg_val = filtered_df[column_name].mean()
            min_val = filtered_df[column_name].min()
            max_val = filtered_df[column_name].max()
            
            # Format values based on type
            if isinstance(avg_val, (int, np.integer)):
                avg_str = f"{avg_val:.0f}"
                min_str = f"{min_val:.0f}"
                max_str = f"{max_val:.0f}"
            else:
                avg_str = f"{avg_val:.2f}"
                min_str = f"{min_val:.2f}"
                max_str = f"{max_val:.2f}"
                
            self.stats_boxes[key]['avg'].setText(avg_str)
            self.stats_boxes[key]['min'].setText(min_str)
            self.stats_boxes[key]['max'].setText(max_str)
        else:
            self.stats_boxes[key]['avg'].setText("--")
            self.stats_boxes[key]['min'].setText("--")
            self.stats_boxes[key]['max'].setText("--")