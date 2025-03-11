import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QWidget,
                            QPushButton, QHBoxLayout, QLabel, QCheckBox, QMenu, QAction,
                            QFileDialog, QSizePolicy)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import SpanSelector

from stats_panel import StatsPanel
from utils import parse_fit_file, get_axis_color, get_line_style, calculate_hr_zones

class TrainingPlotWindow(QMainWindow):
    def __init__(self, dataframes):
        super().__init__()
        self.dataframes = dataframes  # List of dataframes
        self.selected_y_columns = []
        self.span_start = None
        self.span_end = None
        self.axes = {}  # Store axes for each data series
        self.file_checkboxes = {}  # Store checkboxes for each file
        self.x_column = 'elapsed_time'  # Default x column
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("FIT-Datei Analysetool")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        self.menu_button = QPushButton("Menü")
        self.menu = QMenu(self)
        self.menu.setTearOffEnabled(True)
        
        self.y_axis_menu = QMenu("Y-Achse wählen", self)
        self.x_axis_menu = QMenu("X-Achse wählen", self)
        self.menu.addMenu(self.y_axis_menu)
        self.menu.addMenu(self.x_axis_menu)
        
        self.menu_button.setMenu(self.menu)
        controls_layout.addWidget(self.menu_button)
        
        # Add button to load additional FIT files
        self.add_file_btn = QPushButton("Weitere FIT-Datei laden")
        self.add_file_btn.clicked.connect(self.add_file)
        controls_layout.addWidget(self.add_file_btn)
        
        self.reset_selection_btn = QPushButton("Auswahl zurücksetzen")
        self.reset_selection_btn.clicked.connect(self.reset_selection)
        self.reset_selection_btn.setEnabled(False)
        controls_layout.addWidget(self.reset_selection_btn)
        
        # Add exit button
        self.exit_btn = QPushButton("Beenden")
        self.exit_btn.clicked.connect(self.close)
        controls_layout.addWidget(self.exit_btn)
        
        controls_layout.addStretch(1)
        
        main_layout.addLayout(controls_layout)
        
        # File selection checkboxes
        self.file_controls_layout = QHBoxLayout()
        main_layout.addLayout(self.file_controls_layout)
        self.update_file_controls()
        
        # Main content area with plot and stats panel
        content_layout = QHBoxLayout()
        
        # Plot area
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        
        self.figure, self.ax1 = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)
        
        self.toolbar = NavigationToolbar(self.canvas, self)
        plot_layout.addWidget(self.toolbar)
        
        content_layout.addWidget(plot_widget, 7)
        
        # Stats panel
        self.stats_panel = StatsPanel()
        content_layout.addWidget(self.stats_panel, 3)
        
        main_layout.addLayout(content_layout)
        
        self.populate_menus()
        self.setup_span_selector()
    
    def update_file_controls(self):
        # Clear existing controls
        while self.file_controls_layout.count():
            item = self.file_controls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create new file selection controls
        if self.dataframes:
            file_label = QLabel("Dateien:")
            self.file_controls_layout.addWidget(file_label)
            
            for i, df in enumerate(self.dataframes):
                if 'file_source' in df.columns and not df.empty:
                    file_name = df['file_source'].iloc[0]
                    checkbox = QCheckBox(file_name)
                    checkbox.setChecked(True)
                    checkbox.stateChanged.connect(self.plot_data)
                    self.file_checkboxes[file_name] = checkbox
                    self.file_controls_layout.addWidget(checkbox)
            
            self.file_controls_layout.addStretch(1)
    
    def add_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, 'Wähle eine FIT-Datei', 
                                                    str(Path.home()), 'FIT Dateien (*.fit)')
            if not file_path:
                return
            
            df = parse_fit_file(file_path)
            
            if df is not None and not df.empty:
                # Add to dataframes list
                self.dataframes.append(df)
                
                # Update UI
                self.update_file_controls()
                self.populate_menus()
                self.plot_data()
        except Exception as e:
            print(f"Fehler beim Laden der Datei: {e}")
    
    def populate_menus(self):
        # Clear existing menus
        self.y_axis_menu.clear()
        self.x_axis_menu.clear()
        
        # Get all numeric columns across all dataframes
        all_numeric_cols = set()
        for df in self.dataframes:
            all_numeric_cols.update(df.select_dtypes(include=['number']).columns.tolist())
        
        # Remove file_source from the options
        if 'file_source' in all_numeric_cols:
            all_numeric_cols.remove('file_source')
        
        # Add numeric columns to Y-axis menu
        for col in sorted(all_numeric_cols):
            y_action = QAction(col, self, checkable=True)
            # Check if it was previously selected
            if col in self.selected_y_columns:
                y_action.setChecked(True)
            y_action.triggered.connect(lambda checked, c=col: self.toggle_y_column(checked, c))
            self.y_axis_menu.addAction(y_action)
        
        # Add timestamp columns to X-axis options
        time_cols = ['elapsed_time', 'timestamp', 'time_of_day']
        numeric_and_time_cols = list(set(all_numeric_cols).union([col for col in time_cols if any(col in df.columns for df in self.dataframes)]))
        
        for col in sorted(numeric_and_time_cols):
            x_action = QAction(col, self, checkable=True)
            x_action.setChecked(col == self.x_column)
            x_action.triggered.connect(lambda checked, c=col: self.set_x_column(checked, c))
            self.x_axis_menu.addAction(x_action)
    
    def toggle_y_column(self, checked, column):
        if checked and column not in self.selected_y_columns:
            self.selected_y_columns.append(column)
            # Add stats box for each file
            for df in self.dataframes:
                if column in df.columns:
                    if 'file_source' in df.columns and not df.empty:
                        file_name = df['file_source'].iloc[0]
                        self.stats_panel.add_stats_box(column, file_name)
        elif not checked and column in self.selected_y_columns:
            self.selected_y_columns.remove(column)
            # Remove stats boxes for all files
            for df in self.dataframes:
                if column in df.columns and 'file_source' in df.columns and not df.empty:
                    file_name = df['file_source'].iloc[0]
                    self.stats_panel.remove_stats_box(f"{column}_{file_name}")
            if column in self.axes:
                del self.axes[column]
        self.plot_data()
    
    def set_x_column(self, checked, column):
        if checked:
            self.x_column = column
            for action in self.x_axis_menu.actions():
                if action.text() != column:
                    action.setChecked(False)
            self.plot_data()
            self.setup_span_selector()
    
    def setup_span_selector(self):
        self.span = SpanSelector(
            self.ax1,
            self.on_select,
            'horizontal',
            useblit=True,
            props=dict(alpha=0.2, facecolor='blue'),
            interactive=True
        )
    
    def on_select(self, xmin, xmax):
        self.span_start = xmin
        self.span_end = xmax
        self.reset_selection_btn.setEnabled(True)
        self.update_stats()
    
    def reset_selection(self):
        self.span_start = None
        self.span_end = None
        self.reset_selection_btn.setEnabled(False)
        self.update_stats()
    
    def update_stats(self):
        # Update stats for each selected column and each file
        for column in self.selected_y_columns:
            for df in self.dataframes:
                if column in df.columns and 'file_source' in df.columns and not df.empty:
                    file_name = df['file_source'].iloc[0]
                    # Only update if file checkbox is checked
                    if file_name in self.file_checkboxes and self.file_checkboxes[file_name].isChecked():
                        self.stats_panel.update_stats(
                            column, 
                            df, 
                            self.x_column,
                            file_name,
                            self.span_start, 
                            self.span_end
                        )
    
    def plot_data(self):
        if not self.selected_y_columns or not self.dataframes:
            return
            
        self.figure.clear()
        self.axes = {}
        
        # Create the main axis
        self.ax1 = self.figure.add_subplot(111)
        
        # Store the right-side y-axes we create
        right_axes = []
        
        # Create a y-axis for each selected column
        for i, y_column in enumerate(self.selected_y_columns):
            color = get_axis_color(i)
            
            if i == 0:
                # First dataset uses the main left y-axis
                ax = self.ax1
                ax.set_ylabel(y_column, color=color)
                ax.tick_params(axis='y', labelcolor=color)
            else:
                # Create a new y-axis on the right for each additional dataset
                ax = self.ax1.twinx()
                
                # Offset each additional axis to prevent overlap
                if right_axes:
                    offset = 60 * (len(right_axes))
                    ax.spines['right'].set_position(('outward', offset))
                
                ax.set_ylabel(y_column, color=color)
                ax.tick_params(axis='y', labelcolor=color)
                right_axes.append(ax)
            
            # Store the axis for this column
            self.axes[y_column] = ax
            
            # Plot data from each file for this column
            for file_idx, df in enumerate(self.dataframes):
                if df.empty or 'file_source' not in df.columns:
                    continue
                    
                file_name = df['file_source'].iloc[0]
                
                # Skip if file checkbox is unchecked
                if file_name in self.file_checkboxes and not self.file_checkboxes[file_name].isChecked():
                    continue
                
                # Skip if column not in this dataframe
                if y_column not in df.columns or self.x_column not in df.columns:
                    continue
                
                line_style = get_line_style(file_idx)
                label = f"{y_column} - {file_name}"
                
                # Plot the data using the appropriate axis and formatting
                try:
                    if self.x_column == 'timestamp':
                        # Format timestamps on x-axis
                        ax.plot(df[self.x_column], df[y_column], label=label, color=color, linestyle=line_style)
                        self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        self.ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
                        self.figure.autofmt_xdate()  # Auto-rotate date labels
                    elif self.x_column == 'time_of_day':
                        # Plot using indices but show time labels
                        ax.plot(range(len(df)), df[y_column], label=label, color=color, linestyle=line_style)
                        # Set custom tick positions and labels
                        tick_step = max(1, len(df) // 10)  # Limit to about 10 ticks
                        self.ax1.set_xticks(range(0, len(df), tick_step))
                        self.ax1.set_xticklabels(df['time_of_day'].iloc[::tick_step])
                        self.figure.autofmt_xdate()  # Auto-rotate time labels
                    else:
                        # Regular numeric x-axis
                        ax.plot(df[self.x_column], df[y_column], label=label, color=color, linestyle=line_style)
                except Exception as e:
                    print(f"Fehler beim Plotten von {y_column} für {file_name}: {e}")
        
        # Set x-label based on the selected x column
        if self.x_column == 'elapsed_time':
            self.ax1.set_xlabel("Zeit (Minuten)")
        elif self.x_column == 'timestamp' or self.x_column == 'time_of_day':
            self.ax1.set_xlabel("Uhrzeit")
        else:
            self.ax1.set_xlabel(self.x_column)
            
        self.ax1.set_title('Trainingsdaten')
        self.ax1.grid(True)
        
        # Add legend
        handles, labels = [], []
        for ax in [self.ax1] + right_axes:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)
        
        if handles:
            self.ax1.legend(handles, labels, loc='upper left', bbox_to_anchor=(0, -0.15), ncol=3)
        
        # Highlight selected region if any
        if self.span_start is not None and self.span_end is not None:
            self.ax1.axvspan(self.span_start, self.span_end, alpha=0.2, color='blue')
        
        self.figure.tight_layout()
        self.canvas.draw()
        
        # Update statistics based on current selection
        self.update_stats()
        
        # Update the span selector to use the new axis
        self.setup_span_selector()
