import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QWidget,
                            QPushButton, QHBoxLayout, QLabel, QCheckBox, QMenu, QAction,
                            QFileDialog, QSizePolicy, QMessageBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import SpanSelector

from stats_panel import StatsPanel
# Use only the centralized functions from utils
from utils import parse_fit_file, get_axis_color, get_line_style, safe_numeric_filter

# Custom menu class that doesn't close on action trigger
class PersistentMenu(QMenu):
    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        if action and action.isEnabled() and action.isCheckable():
            action.trigger()
            # Don't close the menu for checkable actions
            return
        super().mouseReleaseEvent(event)

class TrainingPlotWindow(QMainWindow):
    def __init__(self, dataframes):
        super().__init__()
        self.dataframes = dataframes  # List of dataframes
        self.selected_y_columns = {}  # Dictionary of selected y columns per file
        self.span_start = None
        self.span_end = None
        self.axes = {}  # Store axes for each data series
        self.file_buttons = {}  # Store buttons for each file
        self.file_menus = {}  # Store menus for each file
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
        
        # Main menu button in the upper left corner
        self.menu_button = QPushButton("Menü")
        self.menu = QMenu(self)
        
        # Add file action
        self.import_action = QAction("FIT-Datei laden", self)
        self.import_action.triggered.connect(self.add_file)
        self.menu.addAction(self.import_action)
        
        # X-axis submenu
        self.x_axis_menu = PersistentMenu("X-Achse wählen", self)
        self.menu.addMenu(self.x_axis_menu)
        
        # Add separator and exit action
        self.menu.addSeparator()
        self.exit_action = QAction("Beenden", self)
        self.exit_action.triggered.connect(self.close)
        self.menu.addAction(self.exit_action)
        
        self.menu_button.setMenu(self.menu)
        controls_layout.addWidget(self.menu_button)
        
        # Add reset selection button
        self.reset_selection_btn = QPushButton("Auswahl zurücksetzen")
        self.reset_selection_btn.clicked.connect(self.reset_selection)
        self.reset_selection_btn.setEnabled(False)
        controls_layout.addWidget(self.reset_selection_btn)
        
        controls_layout.addStretch(1)
        
        main_layout.addLayout(controls_layout)
        
        # File buttons layout - one button per file
        self.file_buttons_layout = QHBoxLayout()
        main_layout.addLayout(self.file_buttons_layout)
        
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
        
        self.populate_x_axis_menu()
        self.update_file_buttons()
        self.setup_span_selector()
    
    def update_file_buttons(self):
        # Clear existing buttons
        while self.file_buttons_layout.count():
            item = self.file_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.file_buttons = {}
        self.file_menus = {}
        
        # Create a button for each file
        if self.dataframes:
            for i, df in enumerate(self.dataframes):
                if 'file_source' in df.columns and not df.empty:
                    file_name = df['file_source'].iloc[0]
                    
                    # Create button for this file
                    file_button = QPushButton(file_name)
                    
                    # Create menu for this file
                    file_menu = QMenu(self)
                    
                    # Add Y-axis selection submenu
                    y_axis_menu = PersistentMenu("Y-Achse wählen", self)
                    
                    # Populate with available columns
                    self.populate_y_axis_menu(df, y_axis_menu, file_name)
                    
                    file_menu.addMenu(y_axis_menu)
                    
                    # Add remove file option
                    remove_action = QAction("Datei entfernen", self)
                    remove_action.triggered.connect(lambda checked, fn=file_name: self.remove_file(fn))
                    file_menu.addAction(remove_action)
                    
                    # Set menu to button
                    file_button.setMenu(file_menu)
                    
                    # Add to layout
                    self.file_buttons_layout.addWidget(file_button)
                    
                    # Store references
                    self.file_buttons[file_name] = file_button
                    self.file_menus[file_name] = file_menu
                    
                    # Initialize selected columns for this file if not already present
                    if file_name not in self.selected_y_columns:
                        self.selected_y_columns[file_name] = []
            
            self.file_buttons_layout.addStretch(1)
    
    def populate_y_axis_menu(self, df, menu, file_name):
        # Clear existing menu
        menu.clear()
        
        # Find numeric columns
        numeric_cols = [col for col in df.columns if col != 'file_source' and 
                       pd.api.types.is_numeric_dtype(df[col])]
        
        # Add actions for each column
        for col in sorted(numeric_cols):
            y_action = QAction(col, self, checkable=True)
            # Check if it was previously selected for this file
            if file_name in self.selected_y_columns and col in self.selected_y_columns[file_name]:
                y_action.setChecked(True)
            y_action.triggered.connect(lambda checked, c=col, fn=file_name: self.toggle_y_column(checked, c, fn))
            menu.addAction(y_action)
    
    def populate_x_axis_menu(self):
        # Clear existing menu
        self.x_axis_menu.clear()
        
        # Get all numeric columns across all dataframes
        all_numeric_cols = set()
        for df in self.dataframes:
            # Use only truly numeric columns
            numeric_cols = [col for col in df.columns if col != 'file_source' and 
                           pd.api.types.is_numeric_dtype(df[col])]
            all_numeric_cols.update(numeric_cols)
        
        # Find all available X-axis columns
        x_axis_options = []
        time_cols = ['elapsed_time', 'timestamp_numeric', 'time_of_day_numeric']
        
        # Add time columns first
        for col in time_cols:
            if any(col in df.columns for df in self.dataframes):
                x_axis_options.append(col)
        
        # Then add regular numeric columns
        for col in sorted(all_numeric_cols):
            if col not in x_axis_options:
                x_axis_options.append(col)
        
        # Add X-axis options
        for col in x_axis_options:
            x_action = QAction(col, self, checkable=True)
            
            # Check if it's the default X column
            if col == self.x_column:
                x_action.setChecked(True)
            # If standard column doesn't exist, select the first available column
            elif self.x_column not in x_axis_options and x_axis_options.index(col) == 0:
                self.x_column = col
                x_action.setChecked(True)
                
            x_action.triggered.connect(lambda checked, c=col: self.set_x_column(checked, c))
            self.x_axis_menu.addAction(x_action)
    
    def toggle_y_column(self, checked, column, file_name):
        # Initialize if not exists
        if file_name not in self.selected_y_columns:
            self.selected_y_columns[file_name] = []
            
        if checked and column not in self.selected_y_columns[file_name]:
            self.selected_y_columns[file_name].append(column)
            # Add stats box
            self.stats_panel.add_stats_box(column, file_name)
        elif not checked and column in self.selected_y_columns[file_name]:
            self.selected_y_columns[file_name].remove(column)
            # Remove stats box
            self.stats_panel.remove_stats_box(f"{column}_{file_name}")
        
        self.plot_data()
    
    def set_x_column(self, checked, column):
        if checked:
            # Reset selection first, then change X-axis
            # This prevents scaling problems when switching X-axis
            self.reset_selection()
            
            # Then change the X-axis
            old_x_column = self.x_column
            self.x_column = column
            
            # Deactivate all other X-axis menu items
            for action in self.x_axis_menu.actions():
                if action.text() != column:
                    action.setChecked(False)
            
            # Replot data
            self.plot_data()
            self.setup_span_selector()
    
    def add_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, 'Wähle eine FIT-Datei', 
                                                     str(Path.home()), 'FIT Dateien (*.fit)')
            if not file_path:
                return
            
            # Use the centralized parsing function
            df = parse_fit_file(file_path)
            
            if df is not None and not df.empty:
                # Add to dataframes list
                self.dataframes.append(df)
                
                # Update UI
                self.update_file_buttons()
                self.populate_x_axis_menu()
                self.plot_data()
            else:
                QMessageBox.warning(self, "Warnung", f"Die Datei {file_path} konnte nicht verarbeitet werden oder enthält keine Daten.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Laden der Datei: {e}")

    def remove_file(self, file_name):
        # Confirm with user
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setText(f"Möchtest du die Datei '{file_name}' entfernen?")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        
        if msg_box.exec_() == QMessageBox.Yes:
            # Remove dataframe
            self.dataframes = [df for df in self.dataframes 
                             if 'file_source' not in df.columns or 
                             df['file_source'].iloc[0] != file_name]
            
            # Remove stats boxes
            if file_name in self.selected_y_columns:
                for col in self.selected_y_columns[file_name]:
                    self.stats_panel.remove_stats_box(f"{col}_{file_name}")
                del self.selected_y_columns[file_name]
            
            # Update UI
            self.update_file_buttons()
            self.populate_x_axis_menu()
            self.plot_data()
    
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
        for file_name, columns in self.selected_y_columns.items():
            # Find the dataframe for this file
            df_list = [df for df in self.dataframes 
                     if 'file_source' in df.columns and 
                     not df.empty and 
                     df['file_source'].iloc[0] == file_name]
            
            if not df_list:
                continue
                
            df = df_list[0]
            
            for column in columns:
                if column in df.columns:
                    self.stats_panel.update_stats(
                        column, 
                        df, 
                        self.x_column,
                        file_name,
                        self.span_start, 
                        self.span_end
                    )
    
    def get_display_column(self, df, column):
        """
        Returns the correct display column based on the selected column
        """
        # For timestamp_numeric return original timestamp
        if column == 'timestamp_numeric' and 'timestamp' in df.columns:
            return 'timestamp'
        # For time_of_day_numeric return original time_of_day
        elif column == 'time_of_day_numeric' and 'time_of_day' in df.columns:
            return 'time_of_day'
        return column
    
    def plot_data(self):
        # Check if we have data to plot
        has_data_to_plot = False
        for file_name, columns in self.selected_y_columns.items():
            if columns:  # If there are selected columns for this file
                has_data_to_plot = True
                break
        
        if not has_data_to_plot or not self.dataframes:
            # Clear the plot if no data to display
            self.figure.clear()
            self.ax1 = self.figure.add_subplot(111)
            self.ax1.set_title('Keine Daten zum Anzeigen')
            self.canvas.draw()
            return
            
        self.figure.clear()
        self.axes = {}
        
        # Create the main axis
        self.ax1 = self.figure.add_subplot(111)
        
        # Store the right-side y-axes we create
        right_axes = []
        
        # Track all columns across all files
        all_columns = []
        for file_name, columns in self.selected_y_columns.items():
            for column in columns:
                if column not in all_columns:
                    all_columns.append(column)
        
        # Create a y-axis for each unique column
        for i, y_column in enumerate(all_columns):
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
            
            # Plot data from each file that has this column selected
            for file_idx, df in enumerate(self.dataframes):
                if df.empty or 'file_source' not in df.columns:
                    continue
                    
                file_name = df['file_source'].iloc[0]
                
                # Skip if column not selected for this file
                if (file_name not in self.selected_y_columns or 
                    y_column not in self.selected_y_columns[file_name]):
                    continue
                
                # Skip if column not in this dataframe
                if y_column not in df.columns:
                    continue
                    
                # Use correct display column for X-axis
                display_x_column = self.get_display_column(df, self.x_column)
                
                # Check if X column exists
                if display_x_column not in df.columns and self.x_column not in df.columns:
                    continue
                
                line_style = get_line_style(file_idx)
                label = f"{y_column} - {file_name}"
                
                # Plot the data using the appropriate axis and formatting
                try:
                    if display_x_column == 'timestamp' and 'timestamp_numeric' in df.columns:
                        # Plot with timestamp as X-axis
                        ax.plot(df[display_x_column], df[y_column], label=label, color=color, linestyle=line_style)
                        self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        self.ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
                        self.figure.autofmt_xdate()  # Auto-rotate date labels
                        
                        # Store the numerical values for span selection
                        self.x_display_to_numeric = {
                            ts.timestamp(): num for ts, num in zip(df['timestamp'], df['timestamp_numeric'])
                        }
                        
                    elif display_x_column == 'time_of_day' and 'time_of_day_numeric' in df.columns:
                        # Plot with time_of_day as X-axis using the numeric values for positioning
                        ax.plot(df['time_of_day_numeric'], df[y_column], label=label, color=color, linestyle=line_style)
                        
                        # Create custom formatter to show time_of_day strings
                        def format_time_of_day(x, pos):
                            # Find the closest time_of_day value
                            idx = np.abs(df['time_of_day_numeric'].values - x).argmin()
                            if idx < len(df):
                                return df['time_of_day'].iloc[idx]
                            return ''
                        
                        self.ax1.xaxis.set_major_formatter(plt.FuncFormatter(format_time_of_day))
                        # Use about 5-10 ticks depending on data size
                        num_ticks = min(10, max(5, len(df) // 100))
                        self.ax1.xaxis.set_major_locator(plt.MaxNLocator(num_ticks))
                        self.figure.autofmt_xdate()  # Auto-rotate time labels
                    else:
                        # Regular numeric x-axis
                        plot_column = self.x_column if self.x_column in df.columns else display_x_column
                        ax.plot(df[plot_column], df[y_column], label=label, color=color, linestyle=line_style)
                except Exception as e:
                    print(f"Fehler beim Plotten von {y_column} für {file_name}: {e}")
        
        # Set x-label based on the selected x column
        if self.x_column == 'elapsed_time':
            self.ax1.set_xlabel("Zeit (Minuten)")
        elif self.x_column == 'timestamp_numeric':
            self.ax1.set_xlabel("Uhrzeit")
        elif self.x_column == 'time_of_day_numeric':
            self.ax1.set_xlabel("Tageszeit")
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