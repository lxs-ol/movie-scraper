import os
import sys
import json
import shutil
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QTabWidget,
    QLineEdit, QTextEdit, QComboBox, QFileDialog, QMessageBox,
    QSplitter, QFrame, QGroupBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QScrollArea, QGridLayout, QApplication,
    QProgressBar, QDialog, QDialogButtonBox, QInputDialog,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont, QImage
from typing import List, Optional, Dict
from api import TMDBAPI, MovieInfo
from scanner import LocalMovieScanner, LocalMovie, LocalSeries

class SearchThread(QThread):
    result_ready = pyqtSignal(list)
    
    def __init__(self, api: TMDBAPI, query: str, search_type: str = 'multi'):
        super().__init__()
        self.api = api
        self.query = query
        self.search_type = search_type
    
    def run(self):
        try:
            if self.search_type == 'movie':
                results = self.api.search_movie(self.query)
            elif self.search_type == 'tv':
                results = self.api.search_tv(self.query)
            elif self.search_type == 'collection':
                collection_results = self.api.search_collection(self.query)
                # 转换合集结果为MovieInfo格式
                results = []
                for collection in collection_results:
                    # 创建一个模拟的MovieInfo对象来显示合集
                    info = MovieInfo(
                        id=collection.get('id', 0),
                        title=collection.get('name', ''),
                        original_title=collection.get('original_name', ''),
                        year='',  # 合集没有年份
                        overview=collection.get('overview', ''),
                        poster_path=collection.get('poster_path', ''),
                        backdrop_path=collection.get('backdrop_path', ''),
                        vote_average=0,  # 合集没有评分
                        media_type='collection',
                        genre_ids=[],
                        popularity=0
                    )
                    results.append(info)
            else:
                results = self.api.search_multi(self.query)
            self.result_ready.emit(results)
        except Exception as e:
            print(f"搜索错误: {e}")
            self.result_ready.emit([])

class ScanThread(QThread):
    progress_update = pyqtSignal(int, str)
    scan_complete = pyqtSignal(list, str)
    
    def __init__(self, scanner: LocalMovieScanner, directory: str, scan_type: str):
        super().__init__()
        self.scanner = scanner
        self.directory = directory
        self.scan_type = scan_type
    
    def run(self):
        try:
            if self.scan_type == '电影':
                # 先计算总文件数
                total_files = self._count_files(self.directory)
                self.progress_update.emit(0, f"开始扫描电影目录...")
                
                # 扫描目录
                movies = self.scanner.scan_directory(self.directory)
                self.progress_update.emit(100, f"扫描完成，找到 {len(movies)} 个电影")
                self.scan_complete.emit(movies, '电影')
            else:
                # 电视剧扫描
                total_files = self._count_files(self.directory)
                self.progress_update.emit(0, f"开始扫描电视剧目录...")
                
                series = self.scanner.scan_series_directory(self.directory)
                self.progress_update.emit(100, f"扫描完成，找到 {len(series)} 个电视剧")
                self.scan_complete.emit(series, '电视剧')
        except Exception as e:
            print(f"扫描错误: {e}")
            self.scan_complete.emit([], self.scan_type)
    
    def _count_files(self, directory: str) -> int:
        """计算目录中的文件数量"""
        count = 0
        for root, dirs, files in os.walk(directory):
            count += len(files)
        return count

class SeriesCardWidget(QWidget):
    clicked = pyqtSignal(object)
    
    def __init__(self, series, api: TMDBAPI):
        super().__init__()
        self.series = series
        self.api = api
        self._init_scale_factor()
        self.setup_ui()
    
    def _init_scale_factor(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.scale_factor = screen.logicalDotsPerInch() / 96.0
        else:
            self.scale_factor = 1.0
    
    def setup_ui(self):
        poster_w = int(60 * self.scale_factor)
        poster_h = int(90 * self.scale_factor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(int(5 * self.scale_factor), int(5 * self.scale_factor), 
                                   int(5 * self.scale_factor), int(5 * self.scale_factor))
        
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(poster_w, poster_h)
        self.poster_label.setStyleSheet("background-color: #2a2a2a; border-radius: 5px;")
        
        poster_loaded = False
        if self.series.poster_path and os.path.exists(self.series.poster_path):
            pixmap = QPixmap(self.series.poster_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(poster_w, poster_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.poster_label.setPixmap(scaled_pixmap)
                poster_loaded = True
        
        if not poster_loaded:
            self.poster_label.setText('📺')
            self.poster_label.setAlignment(Qt.AlignCenter)
            self.poster_label.setStyleSheet("background-color: #2a2a2a; border-radius: 5px; font-size: 24px;")
        
        layout.addWidget(self.poster_label)
        
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(int(8 * self.scale_factor), 0, 0, 0)
        info_layout.setSpacing(0)
        
        title = QLabel(self.series.title or self.series.name)
        title.setFont(QFont('Microsoft YaHei', max(9, int(10 * self.scale_factor)), QFont.Bold))
        title.setStyleSheet("color: #ffffff;")
        title.setMaximumWidth(int(200 * self.scale_factor))
        title.setWordWrap(True)
        info_layout.addWidget(title)
        
        year = QLabel(f"{self.series.year or '未知年份'} | 电视剧")
        year.setFont(QFont('Microsoft YaHei', max(8, int(9 * self.scale_factor))))
        year.setStyleSheet("color: #aaaaaa;")
        info_layout.addWidget(year)
        
        seasons_info = QLabel(f"共 {len(self.series.seasons)} 季")
        seasons_info.setFont(QFont('Microsoft YaHei', max(8, int(8 * self.scale_factor))))
        seasons_info.setStyleSheet("color: #888888;")
        info_layout.addWidget(seasons_info)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        self.setStyleSheet("QWidget { background-color: #1e1e1e; border-radius: 6px; }")
        self.setFixedHeight(int(100 * self.scale_factor))
        
        # 点击事件
        self.mousePressEvent = self._on_click
    
    def _on_click(self, event):
        self.clicked.emit(self.series)

class MovieCardWidget(QWidget):
    clicked = pyqtSignal(object)
    
    def __init__(self, movie: LocalMovie, api: TMDBAPI):
        super().__init__()
        self.movie = movie
        self.api = api
        self._init_scale_factor()
        self.setup_ui()
    
    def _init_scale_factor(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.scale_factor = screen.logicalDotsPerInch() / 96.0
        else:
            self.scale_factor = 1.0
    
    def setup_ui(self):
        poster_w = int(60 * self.scale_factor)
        poster_h = int(90 * self.scale_factor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(int(5 * self.scale_factor), int(5 * self.scale_factor), 
                                   int(5 * self.scale_factor), int(5 * self.scale_factor))
        
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(poster_w, poster_h)
        self.poster_label.setStyleSheet("background-color: #2a2a2a; border-radius: 5px;")
        
        poster_loaded = False
        if self.movie.poster_path and os.path.exists(self.movie.poster_path):
            print(f"Loading poster from: {self.movie.poster_path}")
            pixmap = QPixmap(self.movie.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(poster_w, poster_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.poster_label.setPixmap(scaled)
                poster_loaded = True
                print(f"Poster loaded successfully")
            else:
                print(f"Failed to load poster: pixmap is null")
        else:
            print(f"No local poster found, poster_path={self.movie.poster_path}")
        
        if not poster_loaded and self.movie.info.get('poster_path'):
            print(f"Trying to download poster from TMDB")
            poster_url = self.api.get_poster_url(self.movie.info['poster_path'], 'w185')
            if poster_url:
                try:
                    import requests
                    response = requests.get(poster_url, timeout=5)
                    if response.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(response.content)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(poster_w, poster_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.poster_label.setPixmap(scaled)
                            poster_loaded = True
                            print(f"Poster downloaded successfully")
                except Exception as e:
                    print(f"Failed to download poster: {e}")
        
        layout.addWidget(self.poster_label)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(int(2 * self.scale_factor))
        
        title_font_size = max(9, int(11 * self.scale_factor))
        title_label = QLabel(self.movie.title or self.movie.name)
        title_label.setFont(QFont('Microsoft YaHei', title_font_size, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        info_layout.addWidget(title_label)
        
        year_type = f"{self.movie.year or '未知年份'} | {'电影' if self.movie.media_type == 'movie' else '电视剧'}"
        year_label = QLabel(year_type)
        year_label.setStyleSheet(f"color: #666666; font-size: {max(8, int(10 * self.scale_factor))}px;")
        info_layout.addWidget(year_label)
        
        if self.movie.overview:
            overview = self.movie.overview[:100] + '...' if len(self.movie.overview) > 100 else self.movie.overview
            overview_label = QLabel(overview)
            overview_label.setStyleSheet(f"color: #888888; font-size: {max(7, int(9 * self.scale_factor))}px;")
            overview_label.setWordWrap(True)
            info_layout.addWidget(overview_label)
        
        status_text = "已匹配" if self.movie.matched else "未匹配"
        status_color = "#4CAF50" if self.movie.matched else "#FF5722"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-size: {max(8, int(10 * self.scale_factor))}px; font-weight: bold;")
        info_layout.addWidget(status_label)
        
        layout.addLayout(info_layout, 1)
        
        self.setStyleSheet("""
            MovieCardWidget {
                background-color: #ffffff;
                border-radius: 8px;
                margin: 3px;
                border: 1px solid #e0e0e0;
                box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            }
            MovieCardWidget:hover {
                background-color: #f8f9fa;
                border: 1px solid #4a9eff;
                box-shadow: 0 2px 8px rgba(74, 158, 255, 0.2);
                transform: translateY(-1px);
            }
        """)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.movie)
        # 获取父列表并设置选中状态
        parent_list = self.parent()
        while parent_list and not isinstance(parent_list, QListWidget):
            parent_list = parent_list.parent()
        
        if parent_list:
            # 找到对应的item
            for i in range(parent_list.count()):
                item = parent_list.item(i)
                if parent_list.itemWidget(item) == self:
                    # Ctrl+点击多选，Shift+点击范围选，普通点击单选
                    if event.modifiers() == Qt.ControlModifier:
                        item.setSelected(not item.isSelected())
                    elif event.modifiers() == Qt.ShiftModifier:
                        # 范围选择逻辑
                        item.setSelected(True)
                    else:
                        parent_list.clearSelection()
                        item.setSelected(True)
                    break

class MovieScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('本地电影刮削工具')
        
        self._init_dpi_scaling()
        
        self.setStyleSheet(self.get_stylesheet())
        
        self.api = TMDBAPI()
        self.scanner = LocalMovieScanner()
        self.local_movies: List[LocalMovie] = []
        self.local_series: List[LocalSeries] = []
        self.current_movie: Optional[LocalMovie] = None
        self.current_series: Optional[LocalSeries] = None
        self.search_thread: Optional[SearchThread] = None
        self.scan_thread: Optional[ScanThread] = None
        self.progress_dialog: Optional[QDialog] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.progress_label: Optional[QLabel] = None
        
        self.config_file = self.get_config_path()
        self.load_config()
        
        self.setup_ui()
    
    def _init_dpi_scaling(self):
        screen = QApplication.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            self.scale_factor = dpi / 96.0
        else:
            self.scale_factor = 1.0
        
        base_width = 1000
        base_height = 700
        scaled_width = int(base_width * self.scale_factor)
        scaled_height = int(base_height * self.scale_factor)
        
        self.setGeometry(100, 100, scaled_width, scaled_height)
        self.setMinimumSize(int(800 * self.scale_factor), int(500 * self.scale_factor))
    
    def scale_size(self, size: int) -> int:
        return int(size * self.scale_factor)
    
    def get_config_path(self) -> str:
        if hasattr(sys, 'frozen'):
            return os.path.join(os.path.dirname(sys.executable), 'config.json')
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    
    def get_stylesheet(self) -> str:
        s = self.scale_factor
        return f"""QMainWindow {{background-color: #f8f9fa;}}
QWidget {{background-color: #f8f9fa; color: #333333;}}
QTabWidget::pane {{border: 1px solid #e0e0e0; background-color: #ffffff; border-radius: {int(6 * s)}px;}}
QTabBar::tab {{background-color: #ffffff; color: #666666; padding: {int(6 * s)}px {int(16 * s)}px; border-top-left-radius: {int(6 * s)}px; border-top-right-radius: {int(6 * s)}px; margin-right: {int(2 * s)}px; border: 1px solid #e0e0e0; border-bottom: none; font-size: {max(9, int(11 * s))}px;}}
QTabBar::tab:selected {{background-color: #ffffff; color: #4a9eff; border-bottom: 2px solid #4a9eff;}}
QTabBar::tab:hover {{background-color: #f0f4f8;}}
QPushButton {{background-color: #4a9eff; color: #ffffff; border: none; padding: {int(4 * s)}px {int(10 * s)}px; border-radius: {int(4 * s)}px; font-weight: bold; max-height: {int(26 * s)}px; font-size: {max(9, int(11 * s))}px;}}
QPushButton:hover {{background-color: #3a8eef;}}
QPushButton:pressed {{background-color: #2a7edf;}}
QPushButton:disabled {{background-color: #e0e0e0; color: #999999;}}
QLineEdit {{background-color: #ffffff; border: 1px solid #e0e0e0; padding: {int(5 * s)}px {int(8 * s)}px; border-radius: {int(4 * s)}px; color: #333333; font-size: {max(9, int(12 * s))}px;}}
QLineEdit:focus {{border: 2px solid #4a9eff;}}
QTextEdit {{background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: {int(4 * s)}px; color: #333333; padding: {int(6 * s)}px; font-size: {max(9, int(12 * s))}px;}}
QTextEdit:focus {{border: 2px solid #4a9eff;}}
QListWidget {{background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: {int(4 * s)}px;}}
QListWidget::item {{padding: {int(6 * s)}px; border-radius: {int(4 * s)}px; margin: {int(2 * s)}px; border: 1px solid transparent;}}
QListWidget::item:selected {{background-color: #e6f2ff; border: 1px solid #4a9eff; color: #4a9eff;}}
QListWidget::item:hover {{background-color: #f0f4f8; border: 1px solid #e0e0e0;}}
QComboBox {{background-color: #ffffff; border: 1px solid #e0e0e0; padding: {int(5 * s)}px {int(8 * s)}px; border-radius: {int(4 * s)}px; color: #333333; font-size: {max(9, int(12 * s))}px;}}
QComboBox:hover {{border: 1px solid #4a9eff;}}
QComboBox::drop-down {{border: none;}}
QComboBox QAbstractItemView {{background-color: #ffffff; color: #333333; selection-background-color: #e6f2ff; selection-color: #4a9eff; border: 1px solid #e0e0e0; border-radius: {int(4 * s)}px; padding: {int(4 * s)}px;}}
QLabel {{color: #333333; font-size: {max(9, int(12 * s))}px;}}
QGroupBox {{border: 1px solid #e0e0e0; border-radius: {int(6 * s)}px; margin-top: {int(10 * s)}px; padding: {int(10 * s)}px; font-weight: bold; background-color: #ffffff;}}
QGroupBox::title {{subcontrol-origin: margin; left: {int(10 * s)}px; padding: 0 {int(4 * s)}px; color: #4a9eff; font-size: {max(9, int(12 * s))}px;}}
QSplitter::handle {{background-color: #e0e0e0; border-radius: {int(2 * s)}px; margin: {int(1 * s)}px;}}
QSplitter::handle:hover {{background-color: #4a9eff;}}
QScrollBar:vertical {{background-color: #f0f0f0; width: {int(10 * s)}px; border-radius: {int(5 * s)}px; margin: {int(1 * s)}px 0;}}
QScrollBar::handle:vertical {{background-color: #c0c0c0; border-radius: {int(5 * s)}px; min-height: {int(20 * s)}px;}}
QScrollBar::handle:vertical:hover {{background-color: #4a9eff;}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height: 0px;}}
QScrollBar:horizontal {{background-color: #f0f0f0; height: {int(10 * s)}px; border-radius: {int(5 * s)}px; margin: 0 {int(1 * s)}px;}}
QScrollBar::handle:horizontal {{background-color: #c0c0c0; border-radius: {int(5 * s)}px; min-width: {int(20 * s)}px;}}
QScrollBar::handle:horizontal:hover {{background-color: #4a9eff;}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{width: 0px;}}"""
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 1000])
        main_layout.addWidget(splitter)
    
    def create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(8 * self.scale_factor))
        
        scan_btn = QPushButton('📁 扫描目录')
        scan_btn.clicked.connect(self.scan_directory)
        scan_btn.setMaximumHeight(int(28 * self.scale_factor))
        scan_btn.setMinimumHeight(int(28 * self.scale_factor))
        scan_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(scan_btn)
        
        # 扫描类型选择
        scan_type = QComboBox()
        scan_type.addItems(['电影', '电视剧'])
        scan_type.setMaximumHeight(int(28 * self.scale_factor))
        scan_type.setMinimumHeight(int(28 * self.scale_factor))
        scan_type.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.scan_type_combo = scan_type
        layout.addWidget(scan_type)
        
        layout.addStretch()
        
        search_input = QLineEdit()
        search_input.setPlaceholderText('搜索电影或电视剧...')
        search_input.setMinimumWidth(int(250 * self.scale_factor))
        search_input.setMaximumHeight(int(28 * self.scale_factor))
        search_input.setMinimumHeight(int(28 * self.scale_factor))
        search_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        search_input.returnPressed.connect(self.search_tmdb)
        self.search_input = search_input
        layout.addWidget(search_input)
        
        search_type = QComboBox()
        search_type.addItems(['电影', '电视剧', '合集'])
        search_type.setMaximumHeight(int(28 * self.scale_factor))
        search_type.setMinimumHeight(int(28 * self.scale_factor))
        search_type.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.search_type_combo = search_type
        layout.addWidget(search_type)
        
        search_btn = QPushButton('🔍 搜索')
        search_btn.clicked.connect(self.search_tmdb)
        search_btn.setMaximumHeight(int(28 * self.scale_factor))
        search_btn.setMinimumHeight(int(28 * self.scale_factor))
        search_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(search_btn)
        
        layout.addStretch()
        
        about_btn = QPushButton('ℹ️ 关于')
        about_btn.clicked.connect(self.show_about)
        about_btn.setMaximumHeight(int(28 * self.scale_factor))
        about_btn.setMinimumHeight(int(28 * self.scale_factor))
        about_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(about_btn)
        
        settings_btn = QPushButton('⚙️ 设置')
        settings_btn.clicked.connect(self.show_settings)
        settings_btn.setMaximumHeight(int(28 * self.scale_factor))
        settings_btn.setMinimumHeight(int(28 * self.scale_factor))
        settings_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(settings_btn)
        
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setMaximumHeight(int(32 * self.scale_factor))
        
        return toolbar
    
    def create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(4 * self.scale_factor))
        
        header = QLabel('本地电影列表')
        header.setFont(QFont('Microsoft YaHei', max(9, int(11 * self.scale_factor)), QFont.Bold))
        layout.addWidget(header)
        
        # 搜索框
        search_layout = QHBoxLayout()
        self.local_search_input = QLineEdit()
        self.local_search_input.setPlaceholderText('搜索本地电影...')
        self.local_search_input.returnPressed.connect(self.filter_local_movies)
        search_layout.addWidget(self.local_search_input)
        
        clear_btn = QPushButton('清除')
        clear_btn.clicked.connect(self.clear_local_search)
        clear_btn.setMaximumWidth(int(50 * self.scale_factor))
        search_layout.addWidget(clear_btn)
        layout.addLayout(search_layout)
        
        # 电影列表 - 启用多选
        self.movie_list = QListWidget()
        self.movie_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.movie_list.setSpacing(0)
        self.movie_list.setFrameShape(QFrame.NoFrame)
        self.movie_list.itemSelectionChanged.connect(self.on_movie_selection_changed)
        layout.addWidget(self.movie_list)
        
        # 选中数量显示
        self.selection_label = QLabel('未选择')
        self.selection_label.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(self.selection_label)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(int(4 * self.scale_factor))
        auto_match_btn = QPushButton('自动匹配')
        auto_match_btn.clicked.connect(self.auto_match_all)
        auto_match_btn.setMaximumHeight(int(26 * self.scale_factor))
        btn_layout.addWidget(auto_match_btn)
        save_all_btn = QPushButton('保存全部')
        save_all_btn.clicked.connect(self.save_all_movies)
        save_all_btn.setMaximumHeight(int(26 * self.scale_factor))
        btn_layout.addWidget(save_all_btn)
        layout.addLayout(btn_layout)
        return panel
    
    def create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setStyleSheet("QTabWidget { border: none; }")
        
        detail_tab = self.create_detail_tab()
        self.tabs.addTab(detail_tab, '详情')
        
        search_tab = self.create_search_tab()
        self.tabs.addTab(search_tab, '搜索结果')
        
        collection_tab = self.create_collection_tab()
        self.tabs.addTab(collection_tab, '电影集')
        
        tv_convert_tab = self.create_tv_convert_tab()
        self.tabs.addTab(tv_convert_tab, 'Movie转TV')
        
        layout.addWidget(self.tabs)
        panel.setContentsMargins(0, 0, 0, 0)
        return panel
    
    def create_detail_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(int(4 * self.scale_factor))
        
        # 顶部布局：左侧封面，右侧编辑信息
        header_layout = QHBoxLayout()
        header_layout.setSpacing(int(8 * self.scale_factor))
        
        # 封面显示在左上角
        poster_w = int(150 * self.scale_factor)
        poster_h = int(225 * self.scale_factor)
        self.detail_poster = QLabel()
        self.detail_poster.setFixedSize(poster_w, poster_h)
        self.detail_poster.setStyleSheet("background-color: #f0f0f0; border-radius: 6px;")
        header_layout.addWidget(self.detail_poster)
        
        # 右侧编辑信息
        edit_layout = QVBoxLayout()
        edit_layout.setSpacing(int(4 * self.scale_factor))
        
        form_layout = QGridLayout()
        form_layout.setSpacing(int(4 * self.scale_factor))
        
        form_layout.addWidget(QLabel('标题:'), 0, 0)
        self.edit_title = QLineEdit()
        form_layout.addWidget(self.edit_title, 0, 1)
        
        form_layout.addWidget(QLabel('原标题:'), 1, 0)
        self.edit_original_title = QLineEdit()
        form_layout.addWidget(self.edit_original_title, 1, 1)
        
        form_layout.addWidget(QLabel('年份:'), 2, 0)
        self.edit_year = QLineEdit()
        form_layout.addWidget(self.edit_year, 2, 1)
        
        form_layout.addWidget(QLabel('类型:'), 3, 0)
        self.edit_type = QComboBox()
        self.edit_type.addItems(['电影 (Movie)', '电视剧 (TV)'])
        form_layout.addWidget(self.edit_type, 3, 1)
        
        form_layout.addWidget(QLabel('评分:'), 4, 0)
        self.edit_rating = QDoubleSpinBox()
        self.edit_rating.setRange(0, 10)
        self.edit_rating.setSingleStep(0.1)
        form_layout.addWidget(self.edit_rating, 4, 1)
        
        form_layout.addWidget(QLabel('TMDB ID:'), 5, 0)
        self.edit_tmdb_id = QLineEdit()
        form_layout.addWidget(self.edit_tmdb_id, 5, 1)
        
        form_layout.addWidget(QLabel('类型标签:'), 6, 0)
        self.edit_genres = QLineEdit()
        self.edit_genres.setPlaceholderText('用逗号分隔')
        form_layout.addWidget(self.edit_genres, 6, 1)
        
        edit_layout.addLayout(form_layout)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(int(4 * self.scale_factor))
        search_btn = QPushButton('🔍 重新搜索')
        search_btn.clicked.connect(self.search_current_movie)
        btn_layout.addWidget(search_btn)
        save_btn = QPushButton('💾 保存修改')
        save_btn.clicked.connect(self.save_edited_info)
        btn_layout.addWidget(save_btn)
        reset_btn = QPushButton('🔄 重置')
        reset_btn.clicked.connect(self.reset_edit_form)
        btn_layout.addWidget(reset_btn)
        
        edit_layout.addLayout(btn_layout)
        header_layout.addLayout(edit_layout, 1)
        layout.addLayout(header_layout)
        
        # 下方显示简介
        overview_label = QLabel('简介:')
        overview_label.setFont(QFont('Microsoft YaHei', max(9, int(10 * self.scale_factor)), QFont.Bold))
        layout.addWidget(overview_label)
        self.edit_overview = QTextEdit()
        layout.addWidget(self.edit_overview)
        
        return tab
    
    def create_search_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(int(4 * self.scale_factor))
        self.search_results = QListWidget()
        self.search_results.setSpacing(int(2 * self.scale_factor))
        self.search_results.itemClicked.connect(self.on_search_result_selected)
        self.search_results.itemDoubleClicked.connect(self.apply_search_result_and_save)
        layout.addWidget(self.search_results)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(int(4 * self.scale_factor))
        apply_btn = QPushButton('✅ 应用选择')
        apply_btn.clicked.connect(self.apply_search_result)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)
        
        return tab
    
    def create_collection_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel('合集功能 - 为电影设置TMDB合集ID')
        info_label.setFont(QFont('Microsoft YaHei', 11, QFont.Bold))
        layout.addWidget(info_label)
        
        search_layout = QHBoxLayout()
        self.collection_search_input = QLineEdit()
        self.collection_search_input.setPlaceholderText('输入合集名称搜索TMDB...')
        self.collection_search_input.returnPressed.connect(self.search_collection)
        search_layout.addWidget(self.collection_search_input)
        
        search_btn = QPushButton('� 搜索合集')
        search_btn.clicked.connect(self.search_collection)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        self.collection_result_list = QListWidget()
        self.collection_result_list.itemClicked.connect(self.on_collection_result_clicked)
        layout.addWidget(self.collection_result_list)
        
        selected_label = QLabel('已选合集:')
        layout.addWidget(selected_label)
        
        self.selected_collection_label = QLabel('未选择')
        self.selected_collection_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        layout.addWidget(self.selected_collection_label)
        
        btn_layout = QHBoxLayout()
        
        set_btn = QPushButton('📝 设置合集ID')
        set_btn.clicked.connect(self.set_collection_to_movie)
        btn_layout.addWidget(set_btn)
        
        remove_btn = QPushButton('�️ 清除合集ID')
        remove_btn.clicked.connect(self.clear_collection_from_movie)
        btn_layout.addWidget(remove_btn)
        
        layout.addLayout(btn_layout)
        
        self.current_collection = None
        
        return tab
    
    def create_tv_convert_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel('Movie转TV功能 - 将电影系列转换为电视剧格式')
        info_label.setFont(QFont('Microsoft YaHei', 11, QFont.Bold))
        layout.addWidget(info_label)
        
        # 分类管理区域
        category_layout = QVBoxLayout()
        category_header = QHBoxLayout()
        
        self.category_name_input = QLineEdit()
        self.category_name_input.setPlaceholderText('输入分类名称')
        category_header.addWidget(self.category_name_input)
        
        add_category_btn = QPushButton('添加分类')
        add_category_btn.clicked.connect(self.add_category)
        category_header.addWidget(add_category_btn)
        
        category_layout.addLayout(category_header)
        
        self.category_list = QListWidget()
        self.category_list.itemClicked.connect(self.on_category_selected)
        category_layout.addWidget(self.category_list)
        
        category_buttons = QHBoxLayout()
        edit_category_btn = QPushButton('编辑分类')
        edit_category_btn.clicked.connect(self.edit_category)
        category_buttons.addWidget(edit_category_btn)
        
        delete_category_btn = QPushButton('删除分类')
        delete_category_btn.clicked.connect(self.delete_category)
        category_buttons.addWidget(delete_category_btn)
        
        category_layout.addLayout(category_buttons)
        layout.addLayout(category_layout)
        
        # 电影列表区域
        movies_layout = QVBoxLayout()
        movies_header = QHBoxLayout()
        
        add_movies_btn = QPushButton('添加选中电影')
        add_movies_btn.clicked.connect(self.add_movies_to_category)
        movies_header.addWidget(add_movies_btn)
        
        remove_movies_btn = QPushButton('移除选中电影')
        remove_movies_btn.clicked.connect(self.remove_movies_from_category)
        movies_header.addWidget(remove_movies_btn)
        
        movies_layout.addLayout(movies_header)
        
        self.category_movies_list = QListWidget()
        self.category_movies_list.setSelectionMode(QListWidget.ExtendedSelection)
        movies_layout.addWidget(self.category_movies_list)
        
        layout.addLayout(movies_layout)
        
        # 生成按钮
        generate_btn = QPushButton('生成TV格式')
        generate_btn.clicked.connect(self.generate_tv_format)
        generate_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        layout.addWidget(generate_btn)
        
        # 初始化分类数据
        self.categories = {}
        self.current_category = None
        
        return tab
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if 'api_key' in config:
                    self.api.set_api_key(config['api_key'])
                
                if 'proxy' in config:
                    self.api.set_proxy(config['proxy'])
            except Exception as e:
                print(f"加载配置失败: {e}")
    
    def save_config(self, config: dict):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def scan_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择目录')
        if not directory:
            return
        
        scan_type = self.scan_type_combo.currentText()
        
        # 清空列表
        self.movie_list.clear()
        
        # 创建进度对话框
        progress_dialog = self._create_progress_dialog(f'正在扫描{scan_type}...')
        
        # 创建并启动扫描线程
        self.scan_thread = ScanThread(self.scanner, directory, scan_type)
        self.scan_thread.progress_update.connect(self._update_progress)
        self.scan_thread.scan_complete.connect(self._scan_complete)
        self.scan_thread.start()
        
        # 显示进度对话框
        progress_dialog.exec_()
    
    def _update_progress(self, value: int, message: str):
        """更新进度条"""
        if self.progress_bar:
            self.progress_bar.setValue(value)
        if self.progress_label:
            self.progress_label.setText(message)
        QApplication.processEvents()
    
    def _scan_complete(self, items: list, scan_type: str):
        """扫描完成处理"""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        if scan_type == '电影':
            self.local_movies = items
            self.filtered_movies = self.local_movies
            
            # 批量添加电影到列表
            for movie in self.local_movies:
                self.add_movie_to_list(movie)
            
            self.selection_label.setText(f'共 {len(self.local_movies)} 个电影')
            QMessageBox.information(self, '扫描完成', f'找到 {len(self.local_movies)} 个视频文件')
        else:
            # 电视剧扫描
            self.local_series = items
            self.filtered_series = self.local_series
            
            # 批量添加电视剧到列表
            for series in self.local_series:
                self.add_series_to_list(series)
            
            self.selection_label.setText(f'共 {len(self.local_series)} 个电视剧')
            QMessageBox.information(self, '扫描完成', f'找到 {len(self.local_series)} 个电视剧')
    
    def add_movie_to_list(self, movie: LocalMovie):
        item = QListWidgetItem()
        widget = MovieCardWidget(movie, self.api)
        widget.clicked.connect(self.on_movie_card_clicked)
        item.setSizeHint(widget.sizeHint())
        self.movie_list.addItem(item)
        self.movie_list.setItemWidget(item, widget)
    
    def add_series_to_list(self, series):
        item = QListWidgetItem()
        widget = SeriesCardWidget(series, self.api)
        widget.clicked.connect(self.on_series_card_clicked)
        item.setSizeHint(widget.sizeHint())
        self.movie_list.addItem(item)
        self.movie_list.setItemWidget(item, widget)
    
    def on_movie_card_clicked(self, movie: LocalMovie):
        self.current_movie = movie
        self.update_detail_view(movie)
    
    def on_series_card_clicked(self, series):
        self.current_series = series
        self.update_series_detail_view(series)
    
    def on_movie_selection_changed(self):
        selected_items = self.movie_list.selectedItems()
        count = len(selected_items)
        
        if count == 0:
            self.selection_label.setText(f'共 {len(self.filtered_movies)} 个电影')
            self.current_movie = None
        elif count == 1:
            self.selection_label.setText(f'已选择 1 个电影')
            # 从widget获取movie对象
            widget = self.movie_list.itemWidget(selected_items[0])
            if widget and hasattr(widget, 'movie'):
                self.current_movie = widget.movie
                self.update_detail_view(self.current_movie)
        else:
            self.selection_label.setText(f'已选择 {count} 个电影')
            # 多选时只显示第一个的详情
            widget = self.movie_list.itemWidget(selected_items[0])
            if widget and hasattr(widget, 'movie'):
                self.current_movie = widget.movie
                self.update_detail_view(self.current_movie)
    
    def filter_local_movies(self):
        query = self.local_search_input.text().strip().lower()
        self.movie_list.clear()
        
        if not query:
            self.filtered_movies = self.local_movies
        else:
            self.filtered_movies = [m for m in self.local_movies if query in m.name.lower() or (m.title and query in m.title.lower())]
        
        for movie in self.filtered_movies:
            self.add_movie_to_list(movie)
        
        self.selection_label.setText(f'共 {len(self.filtered_movies)} 个电影')
    
    def clear_local_search(self):
        self.local_search_input.clear()
        self.filter_local_movies()
    
    def update_detail_view(self, movie: LocalMovie):
        # 尝试加载本地海报
        poster_loaded = False
        if movie.poster_path and os.path.exists(movie.poster_path):
            print(f"Loading detail poster from: {movie.poster_path}")
            pixmap = QPixmap(movie.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_poster.setPixmap(scaled)
                poster_loaded = True
                print(f"Detail poster loaded successfully")
            else:
                print(f"Failed to load detail poster: pixmap is null")
        else:
            print(f"No local detail poster found, poster_path={movie.poster_path}")
        
        # 如果本地没有海报，尝试从 TMDB 下载
        if not poster_loaded and movie.info.get('poster_path'):
            print(f"Trying to download detail poster from TMDB")
            poster_url = self.api.get_poster_url(movie.info['poster_path'], 'w500')
            if poster_url:
                try:
                    import requests
                    response = requests.get(poster_url, timeout=10)
                    if response.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(response.content)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.detail_poster.setPixmap(scaled)
                            poster_loaded = True
                            print(f"Detail poster downloaded successfully")
                except Exception as e:
                    print(f"下载海报失败: {e}")
        
        if not poster_loaded:
            self.detail_poster.clear()
            self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 更新编辑组件
        self.edit_title.setText(movie.title or movie.name)
        self.edit_original_title.setText(movie.info.get('original_title', ''))
        self.edit_year.setText(movie.year or '')
        self.edit_type.setCurrentIndex(0 if movie.media_type == 'movie' else 1)
        self.edit_rating.setValue(movie.vote_average or 0)
        self.edit_tmdb_id.setText(str(movie.tmdb_id) if movie.tmdb_id else '')
        self.edit_genres.setText(', '.join(movie.genres))
        self.edit_overview.setText(movie.overview or '暂无简介')
    
    def update_series_detail_view(self, series):
        # 尝试加载本地海报
        poster_loaded = False
        if series.poster_path and os.path.exists(series.poster_path):
            print(f"Loading series poster from: {series.poster_path}")
            pixmap = QPixmap(series.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_poster.setPixmap(scaled)
                poster_loaded = True
                print(f"Series poster loaded successfully")
            else:
                print(f"Failed to load series poster: pixmap is null")
        else:
            print(f"No local series poster found, poster_path={series.poster_path}")
        
        if not poster_loaded:
            self.detail_poster.clear()
            self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 更新编辑组件
        self.edit_title.setText(series.title or series.name)
        self.edit_original_title.setText(series.info.get('original_title', ''))
        self.edit_year.setText(series.year or '')
        self.edit_type.setCurrentIndex(1)  # 电视剧
        self.edit_rating.setValue(series.vote_average or 0)
        self.edit_tmdb_id.setText(str(series.tmdb_id) if series.tmdb_id else '')
        self.edit_genres.setText(', '.join(series.genres))
        
        # 电视剧简介
        overview = series.overview or '暂无简介'
        # 添加季节信息
        seasons_info = f"\n\n【季节信息】\n"
        for season in series.seasons:
            seasons_info += f"第 {season['season']} 季: {len(season['episodes'])} 集\n"
        
        self.edit_overview.setText(overview + seasons_info)
    
    def search_tmdb(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        search_type_map = {'电影': 'movie', '电视剧': 'tv', '合集': 'collection'}
        search_type = search_type_map.get(self.search_type_combo.currentText(), 'movie')
        
        self.search_thread = SearchThread(self.api, query, search_type)
        self.search_thread.result_ready.connect(self.on_search_results)
        self.search_thread.start()
        
        self.tabs.setCurrentIndex(1)
    
    def on_search_results(self, results: List[MovieInfo]):
        self.search_results.clear()
        
        for result in results:
            item = QListWidgetItem()
            if result.media_type == 'collection':
                item.setText(f"{result.title} - 合集")
            else:
                item.setText(f"{result.title} ({result.year}) - {'电影' if result.media_type == 'movie' else '电视剧'}")
            item.setData(Qt.UserRole, result)
            self.search_results.addItem(item)
    
    def on_search_result_selected(self, item):
        pass
    
    def apply_search_result(self):
        current_item = self.search_results.currentItem()
        if not current_item or not self.current_movie:
            QMessageBox.warning(self, '警告', '请先选择一个搜索结果')
            return
        
        result: MovieInfo = current_item.data(Qt.UserRole)
        
        self.current_movie.title = result.title
        self.current_movie.year = result.year
        self.current_movie.overview = result.overview
        self.current_movie.vote_average = result.vote_average
        self.current_movie.tmdb_id = result.id
        self.current_movie.media_type = result.media_type
        self.current_movie.info['poster_path'] = result.poster_path
        self.current_movie.info['backdrop_path'] = result.backdrop_path
        self.current_movie.info['original_title'] = result.original_title
        self.current_movie.matched = True
        
        self.update_detail_view(self.current_movie)
        QMessageBox.information(self, '成功', '已应用搜索结果')
    
    def apply_search_result_and_save(self, item):
        if not self.current_movie:
            QMessageBox.warning(self, '警告', '请先选择一个本地电影')
            return
        
        result: MovieInfo = item.data(Qt.UserRole)
        
        self.current_movie.title = result.title
        self.current_movie.year = result.year
        self.current_movie.overview = result.overview
        self.current_movie.vote_average = result.vote_average
        self.current_movie.tmdb_id = result.id
        self.current_movie.media_type = result.media_type
        self.current_movie.info['poster_path'] = result.poster_path
        self.current_movie.info['backdrop_path'] = result.backdrop_path
        self.current_movie.info['original_title'] = result.original_title
        self.current_movie.matched = True
        
        self.update_detail_view(self.current_movie)
        
        info = {
            'title': self.current_movie.title,
            'original_title': self.current_movie.info.get('original_title', ''),
            'year': self.current_movie.year,
            'overview': self.current_movie.overview,
            'vote_average': self.current_movie.vote_average,
            'tmdb_id': self.current_movie.tmdb_id,
            'media_type': self.current_movie.media_type,
            'genres': self.current_movie.genres,
            'poster_path': self.current_movie.info.get('poster_path', ''),
            'backdrop_path': self.current_movie.info.get('backdrop_path', ''),
        }
        
        nfo_path = self.scanner.save_nfo(self.current_movie, info)
        if nfo_path:
            poster_path = self.current_movie.info.get('poster_path')
            if poster_path:
                poster_url = self.api.get_poster_url(poster_path, 'w500')
                if poster_url:
                    directory = os.path.dirname(nfo_path)
                    poster_save_path = os.path.join(directory, 'poster.jpg')
                    if self.api.download_image(poster_url, poster_save_path):
                        self.current_movie.poster_path = poster_save_path
            
            self.update_detail_view(self.current_movie)
            QMessageBox.information(self, '成功', f'已替换封面和NFO文件: {nfo_path}')
        else:
            QMessageBox.warning(self, '失败', '保存 NFO 文件失败')
    
    def search_current_movie(self):
        if not self.current_movie:
            return
        
        self.search_input.setText(self.current_movie.title or self.current_movie.name)
        self.search_tmdb()
    
    def save_current_movie(self):
        if not self.current_movie:
            return
        
        info = {
            'title': self.current_movie.title,
            'original_title': self.current_movie.info.get('original_title', ''),
            'year': self.current_movie.year,
            'overview': self.current_movie.overview,
            'vote_average': self.current_movie.vote_average,
            'tmdb_id': self.current_movie.tmdb_id,
            'media_type': self.current_movie.media_type,
            'genres': self.current_movie.genres,
            'poster_path': self.current_movie.info.get('poster_path', ''),
            'backdrop_path': self.current_movie.info.get('backdrop_path', ''),
        }
        
        nfo_path = self.scanner.save_nfo(self.current_movie, info)
        if nfo_path:
            # 下载并保存海报图片
            poster_path = self.current_movie.info.get('poster_path')
            if poster_path:
                poster_url = self.api.get_poster_url(poster_path, 'w500')
                if poster_url:
                    directory = os.path.dirname(nfo_path)
                    poster_save_path = os.path.join(directory, 'poster.jpg')
                    if self.api.download_image(poster_url, poster_save_path):
                        self.current_movie.poster_path = poster_save_path
            
            QMessageBox.information(self, '成功', f'NFO 文件和海报已保存: {nfo_path}')
        else:
            QMessageBox.warning(self, '失败', '保存 NFO 文件失败')
    
    def save_edited_info(self):
        if not self.current_movie:
            return
        
        self.current_movie.title = self.edit_title.text()
        self.current_movie.info['original_title'] = self.edit_original_title.text()
        self.current_movie.year = self.edit_year.text()
        self.current_movie.media_type = 'movie' if self.edit_type.currentIndex() == 0 else 'tv'
        self.current_movie.vote_average = self.edit_rating.value()
        self.current_movie.tmdb_id = int(self.edit_tmdb_id.text()) if self.edit_tmdb_id.text() else None
        self.current_movie.genres = [g.strip() for g in self.edit_genres.text().split(',') if g.strip()]
        self.current_movie.overview = self.edit_overview.toPlainText()
        
        self.update_detail_view(self.current_movie)
        self.save_current_movie()
    
    def reset_edit_form(self):
        if self.current_movie:
            self.update_detail_view(self.current_movie)
    
    def auto_match_all(self):
        if not self.local_movies:
            QMessageBox.warning(self, '警告', '请先扫描目录')
            return
        
        for movie in self.local_movies:
            if not movie.matched and movie.title:
                results = self.api.search_multi(movie.title)
                if results:
                    best_match = results[0]
                    movie.title = best_match.title
                    movie.year = best_match.year
                    movie.overview = best_match.overview
                    movie.vote_average = best_match.vote_average
                    movie.tmdb_id = best_match.id
                    movie.media_type = best_match.media_type
                    movie.matched = True
        
        self.movie_list.clear()
        for movie in self.local_movies:
            self.add_movie_to_list(movie)
        
        QMessageBox.information(self, '完成', '自动匹配完成')
    
    def save_all_movies(self):
        for movie in self.local_movies:
            if movie.matched:
                info = {
                    'title': movie.title,
                    'original_title': movie.info.get('original_title', ''),
                    'year': movie.year,
                    'overview': movie.overview,
                    'vote_average': movie.vote_average,
                    'tmdb_id': movie.tmdb_id,
                    'media_type': movie.media_type,
                    'genres': movie.genres,
                }
                self.scanner.save_nfo(movie, info)
        
        QMessageBox.information(self, '完成', '所有已匹配的电影信息已保存')
    
    def search_collection(self):
        query = self.collection_search_input.text().strip()
        if not query:
            QMessageBox.warning(self, '警告', '请输入合集名称')
            return
        
        results = self.api.search_collection(query)
        self.collection_result_list.clear()
        
        if not results:
            QMessageBox.information(self, '提示', '未找到合集')
            return
        
        for result in results:
            item = QListWidgetItem(f"📁 {result['name']} (ID: {result['id']})")
            item.setData(Qt.UserRole, result)
            self.collection_result_list.addItem(item)
    
    def on_collection_result_clicked(self, item):
        collection = item.data(Qt.UserRole)
        self.current_collection = collection
        self.selected_collection_label.setText(f"{collection['name']} (ID: {collection['id']})")
    
    def set_collection_to_movie(self):
        if not self.current_movie:
            QMessageBox.warning(self, '警告', '请先在本地电影列表中选择一个电影')
            return
        
        if not self.current_collection:
            QMessageBox.warning(self, '警告', '请先搜索并选择一个合集')
            return
        
        self.current_movie.collection_id = self.current_collection['id']
        self.current_movie.collection_name = self.current_collection['name']
        
        info = {
            'title': self.current_movie.title,
            'original_title': self.current_movie.info.get('original_title', ''),
            'year': self.current_movie.year,
            'overview': self.current_movie.overview,
            'vote_average': self.current_movie.vote_average,
            'tmdb_id': self.current_movie.tmdb_id,
            'collection_id': self.current_collection['id'],
            'collection_name': self.current_collection['name'],
            'genres': self.current_movie.genres,
        }
        
        nfo_path = self.scanner.save_nfo(self.current_movie, info)
        
        if nfo_path:
            QMessageBox.information(self, '成功', f'已为 "{self.current_movie.title}" 设置合集ID: {self.current_collection["id"]}\n\nNFO文件已更新: {nfo_path}')
        else:
            QMessageBox.warning(self, '失败', '保存NFO文件失败')
    
    def clear_collection_from_movie(self):
        if not self.current_movie:
            QMessageBox.warning(self, '警告', '请先在本地电影列表中选择一个电影')
            return
        
        self.current_movie.collection_id = None
        self.current_movie.collection_name = None
        
        info = {
            'title': self.current_movie.title,
            'original_title': self.current_movie.info.get('original_title', ''),
            'year': self.current_movie.year,
            'overview': self.current_movie.overview,
            'vote_average': self.current_movie.vote_average,
            'tmdb_id': self.current_movie.tmdb_id,
            'collection_id': None,
            'collection_name': None,
            'genres': self.current_movie.genres,
        }
        
        nfo_path = self.scanner.save_nfo(self.current_movie, info)
        
        if nfo_path:
            QMessageBox.information(self, '成功', f'已清除 "{self.current_movie.title}" 的合集ID\n\nNFO文件已更新: {nfo_path}')
        else:
            QMessageBox.warning(self, '失败', '保存NFO文件失败')

    def show_settings(self):
        dialog = SettingsDialog(self, self.api, self.config_file)
        dialog.exec_()
    
    def show_about(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle('关于')
        about_dialog.setMinimumWidth(int(450 * self.scale_factor))
        
        main_layout = QVBoxLayout(about_dialog)
        
        # 顶部区域：左侧logo，右侧信息
        top_layout = QHBoxLayout()
        
        # 左侧：应用logo
        app_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '李先生ol.png')
        if os.path.exists(app_logo_path):
            app_logo = QLabel()
            app_logo.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(app_logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(int(120 * self.scale_factor), int(120 * self.scale_factor), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                app_logo.setPixmap(scaled_pixmap)
            top_layout.addWidget(app_logo)
        
        # 右侧：应用信息
        info_layout = QVBoxLayout()
        
        app_name = QLabel('Movie Scraper')
        app_name.setFont(QFont('Microsoft YaHei', int(16 * self.scale_factor), QFont.Bold))
        info_layout.addWidget(app_name)
        
        version = QLabel('版本: 1.0.0')
        version.setStyleSheet("color: #666666;")
        info_layout.addWidget(version)
        
        info_layout.addStretch()
        top_layout.addLayout(info_layout)
        main_layout.addLayout(top_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # 描述
        description = QLabel('一个功能强大的电影元数据管理工具\n\n- 扫描本地电影\n- 自动匹配TMDB元数据\n- 管理电影封面和简介\n- 支持NFO文件解析\n- 批量操作功能\n- 支持电视剧扫描')
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        main_layout.addWidget(description)
        
        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line2)
        
        # 版权信息
        copyright = QLabel('© 2026 Movie Scraper')
        copyright.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(copyright)
        
        # 作者信息
        author = QLabel('作者：李先生OL')
        author.setAlignment(Qt.AlignCenter)
        author.setStyleSheet("color: #888888;")
        main_layout.addWidget(author)
        
        # 按钮
        button = QPushButton('确定')
        button.clicked.connect(about_dialog.accept)
        button.setMaximumWidth(int(100 * self.scale_factor))
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        about_dialog.exec_()
    
    def _create_progress_dialog(self, title: str):
        """创建进度对话框"""
        self.progress_dialog = QDialog(self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setMinimumWidth(int(400 * self.scale_factor))
        self.progress_dialog.setModal(True)
        
        layout = QVBoxLayout(self.progress_dialog)
        
        self.progress_label = QLabel('准备开始...')
        self.progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self._cancel_scan)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        return self.progress_dialog
    
    def _cancel_scan(self):
        """取消扫描操作"""
        if self.scan_thread:
            self.scan_thread.terminate()
            self.scan_thread.wait()
        if self.progress_dialog:
            self.progress_dialog.close()
    
    def add_category(self):
        category_name = self.category_name_input.text().strip()
        if not category_name:
            QMessageBox.warning(self, '警告', '请输入分类名称')
            return
        
        if category_name in self.categories:
            QMessageBox.warning(self, '警告', '分类名称已存在')
            return
        
        self.categories[category_name] = []
        self.category_list.addItem(category_name)
        self.category_name_input.clear()
    
    def on_category_selected(self, item):
        self.current_category = item.text()
        self.category_movies_list.clear()
        
        if self.current_category in self.categories:
            for movie in self.categories[self.current_category]:
                title = movie.title or movie.name
                year = f" ({movie.year})" if movie.year else ""
                list_item = QListWidgetItem(f"{title}{year}")
                list_item.setData(Qt.UserRole, movie)
                self.category_movies_list.addItem(list_item)
    
    def edit_category(self):
        if not self.current_category:
            QMessageBox.warning(self, '警告', '请先选择要编辑的分类')
            return
        
        new_name, ok = QInputDialog.getText(self, '编辑分类', '请输入新的分类名称:', text=self.current_category)
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name != self.current_category:
                if new_name in self.categories:
                    QMessageBox.warning(self, '警告', '分类名称已存在')
                    return
                
                # 重命名分类
                movies = self.categories.pop(self.current_category)
                self.categories[new_name] = movies
                
                # 更新列表
                for i in range(self.category_list.count()):
                    if self.category_list.item(i).text() == self.current_category:
                        self.category_list.item(i).setText(new_name)
                        break
                
                self.current_category = new_name
    
    def delete_category(self):
        if not self.current_category:
            QMessageBox.warning(self, '警告', '请先选择要删除的分类')
            return
        
        reply = QMessageBox.question(self, '确认删除', f'确定要删除分类 "{self.current_category}" 吗？',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.categories[self.current_category]
            
            # 从列表中移除
            for i in range(self.category_list.count()):
                if self.category_list.item(i).text() == self.current_category:
                    self.category_list.takeItem(i)
                    break
            
            self.current_category = None
            self.category_movies_list.clear()
    
    def add_movies_to_category(self):
        if not self.current_category:
            QMessageBox.warning(self, '警告', '请先选择分类')
            return
        
        # 获取当前选中的电影
        selected_items = self.movie_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先在本地电影列表中选择电影')
            return
        
        movies_to_add = []
        for item in selected_items:
            widget = self.movie_list.itemWidget(item)
            if widget and hasattr(widget, 'movie'):
                movies_to_add.append(widget.movie)
        
        # 添加到分类
        existing_movies = self.categories[self.current_category]
        for movie in movies_to_add:
            if movie not in existing_movies:
                existing_movies.append(movie)
        
        # 更新电影列表
        self.on_category_selected(self.category_list.currentItem())
        QMessageBox.information(self, '成功', f'已添加 {len(movies_to_add)} 个电影到分类')
    
    def remove_movies_from_category(self):
        if not self.current_category:
            QMessageBox.warning(self, '警告', '请先选择分类')
            return
        
        # 获取当前选中的电影
        selected_items = self.category_movies_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先在分类电影列表中选择电影')
            return
        
        movies_to_remove = []
        for item in selected_items:
            movie = item.data(Qt.UserRole)
            if movie:
                movies_to_remove.append(movie)
        
        # 从分类中移除
        existing_movies = self.categories[self.current_category]
        for movie in movies_to_remove:
            if movie in existing_movies:
                existing_movies.remove(movie)
        
        # 更新电影列表
        self.on_category_selected(self.category_list.currentItem())
        QMessageBox.information(self, '成功', f'已移除 {len(movies_to_remove)} 个电影')
    
    def generate_tv_format(self):
        if not self.current_category:
            QMessageBox.warning(self, '警告', '请先选择分类')
            return
        
        movies = self.categories[self.current_category]
        if not movies:
            QMessageBox.warning(self, '警告', '分类中没有电影')
            return
        
        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(self, '选择输出目录')
        if not output_dir:
            return
        
        # 按年份排序（最老的在前）
        def get_year(movie):
            try:
                return int(movie.year) if movie.year else 9999
            except:
                return 9999
        
        sorted_movies = sorted(movies, key=get_year)
        
        # 创建系列文件夹
        series_dir = os.path.join(output_dir, self.current_category)
        if not os.path.exists(series_dir):
            os.makedirs(series_dir)
        
        # 创建season 1文件夹
        season_dir = os.path.join(series_dir, "season 1")
        if not os.path.exists(season_dir):
            os.makedirs(season_dir)
        
        # 复制并改名
        try:
            first_movie_poster_path = None
            first_movie_nfo_path = None
            
            for i, movie in enumerate(sorted_movies, 1):
                # 获取原电影名
                original_name = movie.title or movie.name
                
                # 复制视频文件
                if os.path.exists(movie.path):
                    ext = os.path.splitext(movie.path)[1]
                    new_name = f"{original_name} - S01E{i:02d}{ext}"
                    new_path = os.path.join(season_dir, new_name)
                    shutil.copy2(movie.path, new_path)
                
                # 处理nfo文件
                nfo_path = os.path.splitext(movie.path)[0] + '.nfo'
                new_nfo_name = f"{original_name} - S01E{i:02d}.nfo"
                new_nfo_path = os.path.join(season_dir, new_nfo_name)
                
                if os.path.exists(nfo_path):
                    # 复制原nfo文件
                    shutil.copy2(nfo_path, new_nfo_path)
                    
                    # 保存第一个电影的nfo路径
                    if i == 1:
                        first_movie_nfo_path = new_nfo_path
                else:
                    # 如果原nfo文件不存在，创建一个新的
                    # 提取原nfo文件中的plot内容
                    plot_content = movie.overview or ''
                    # 创建基本的nfo结构
                    nfo_content = f'''
<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>{original_name}</title>
    <year>{movie.year or ''}</year>
    <plot>{plot_content}</plot>
</movie>
'''
                    with open(new_nfo_path, 'w', encoding='utf-8') as f:
                        f.write(nfo_content)
                    
                    # 保存第一个电影的nfo路径
                    if i == 1:
                        first_movie_nfo_path = new_nfo_path
                
                # 复制海报
                poster_path = os.path.join(os.path.dirname(movie.path), 'poster.jpg')
                if os.path.exists(poster_path):
                    new_poster_name = f"{original_name} - S01E{i:02d}.jpg"
                    new_poster_path = os.path.join(season_dir, new_poster_name)
                    shutil.copy2(poster_path, new_poster_path)
                    
                    # 保存第一个电影的海报路径
                    if i == 1:
                        first_movie_poster_path = new_poster_path
            
            # 复制第一个电影的文件到分类文件夹
            if first_movie_nfo_path and os.path.exists(first_movie_nfo_path):
                tvshow_nfo_path = os.path.join(series_dir, 'tvshow.nfo')
                shutil.copy2(first_movie_nfo_path, tvshow_nfo_path)
            
            if first_movie_poster_path and os.path.exists(first_movie_poster_path):
                poster_jpg_path = os.path.join(series_dir, 'poster.jpg')
                shutil.copy2(first_movie_poster_path, poster_jpg_path)
                
                # 复制第一个电影的海报到分类文件夹，改名为season01-poster.jpg
                season01_poster_path = os.path.join(series_dir, 'season01-poster.jpg')
                shutil.copy2(first_movie_poster_path, season01_poster_path)
            
            # 修改所有NFO文件中的title标签
            for i, movie in enumerate(sorted_movies, 1):
                original_name = movie.title or movie.name
                nfo_file_path = os.path.join(season_dir, f"{original_name} - S01E{i:02d}.nfo")
                
                if os.path.exists(nfo_file_path):
                    try:
                        with open(nfo_file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 修改title标签内容，去掉 - S01EXX 后缀
                        import re
                        # 匹配 <title>原电影名 - S01E01</title> 改为 <title>原电影名</title>
                        pattern = r'(<title>)[^<]+(</title>)'
                        replacement = r'\1' + original_name + r'\2'
                        content = re.sub(pattern, replacement, content, count=1)
                        
                        with open(nfo_file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    except Exception as e:
                        print(f"修改NFO文件失败 {nfo_file_path}: {e}")
            
            QMessageBox.information(self, '成功', f'已生成TV格式到 {series_dir}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成失败: {str(e)}')

class SettingsDialog(QDialog):
    def __init__(self, parent, api: TMDBAPI, config_file: str):
        super().__init__(parent)
        self.api = api
        self.config_file = config_file
        
        screen = QApplication.primaryScreen()
        if screen:
            self.scale_factor = screen.logicalDotsPerInch() / 96.0
        else:
            self.scale_factor = 1.0
        
        self.setWindowTitle('设置')
        self.setMinimumWidth(int(500 * self.scale_factor))
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        api_group = QGroupBox('TMDB API 设置')
        api_layout = QVBoxLayout(api_group)
        
        api_layout.addWidget(QLabel('API Key:'))
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.api.api_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_input)
        
        test_btn = QPushButton('测试 API Key')
        test_btn.clicked.connect(self.test_api_key)
        api_layout.addWidget(test_btn)
        
        layout.addWidget(api_group)
        
        proxy_group = QGroupBox('代理设置')
        proxy_layout = QGridLayout(proxy_group)
        
        proxy_layout.addWidget(QLabel('代理类型:'), 0, 0)
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(['无代理', 'HTTP', 'SOCKS5'])
        proxy_layout.addWidget(self.proxy_type, 0, 1)
        
        proxy_layout.addWidget(QLabel('代理地址:'), 1, 0)
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText('例如: 127.0.0.1')
        proxy_layout.addWidget(self.proxy_host, 1, 1)
        
        proxy_layout.addWidget(QLabel('端口:'), 2, 0)
        self.proxy_port = QLineEdit()
        self.proxy_port.setPlaceholderText('例如: 7890')
        proxy_layout.addWidget(self.proxy_port, 2, 1)
        
        proxy_layout.addWidget(QLabel('用户名:'), 3, 0)
        self.proxy_user = QLineEdit()
        self.proxy_user.setPlaceholderText('可选')
        proxy_layout.addWidget(self.proxy_user, 3, 1)
        
        proxy_layout.addWidget(QLabel('密码:'), 4, 0)
        self.proxy_pass = QLineEdit()
        self.proxy_pass.setPlaceholderText('可选')
        self.proxy_pass.setEchoMode(QLineEdit.Password)
        proxy_layout.addWidget(self.proxy_pass, 4, 1)
        
        test_proxy_btn = QPushButton('测试代理连接')
        test_proxy_btn.clicked.connect(self.test_proxy)
        proxy_layout.addWidget(test_proxy_btn, 5, 0, 1, 2)
        
        if hasattr(self.api, 'proxy_config') and self.api.proxy_config:
            proxy = self.api.proxy_config
            if proxy.get('type') == 'http':
                self.proxy_type.setCurrentIndex(1)
            elif proxy.get('type') == 'socks5':
                self.proxy_type.setCurrentIndex(2)
            else:
                self.proxy_type.setCurrentIndex(0)
            
            self.proxy_host.setText(proxy.get('host', ''))
            self.proxy_port.setText(proxy.get('port', ''))
            self.proxy_user.setText(proxy.get('username', ''))
            self.proxy_pass.setText(proxy.get('password', ''))
        
        layout.addWidget(proxy_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def test_proxy(self):
        proxy_type_idx = self.proxy_type.currentIndex()
        if proxy_type_idx == 0:
            QMessageBox.warning(self, '警告', '请先选择代理类型')
            return
        
        host = self.proxy_host.text().strip()
        port = self.proxy_port.text().strip()
        if not host or not port:
            QMessageBox.warning(self, '警告', '请填写代理地址和端口')
            return
        
        proxy_type = 'http' if proxy_type_idx == 1 else 'socks5'
        
        QApplication.processEvents()
        
        try:
            import requests
            
            if proxy_type == 'socks5':
                try:
                    import socks
                except ImportError:
                    QMessageBox.critical(self, '缺少依赖', '使用SOCKS5代理需要安装PySocks库\n\n请在命令行运行:\npip install PySocks')
                    return
            
            session = requests.Session()
            
            proxy_url = f"{host}:{port}"
            
            if proxy_type == 'socks5':
                proxies = {
                    'http': f'socks5://{proxy_url}',
                    'https': f'socks5://{proxy_url}'
                }
            else:
                # HTTP代理：http和https都使用http://前缀
                proxies = {
                    'http': f'http://{proxy_url}',
                    'https': f'http://{proxy_url}'
                }
            
            session.proxies.update(proxies)
            print(f"测试代理: {proxy_type}://{proxy_url}")
            print(f"Proxies: {proxies}")
            
            # 先测试HTTP连接
            try:
                response = session.get('http://api.themoviedb.org/3/configuration?api_key=test', timeout=15, verify=False)
                print(f"HTTP响应状态码: {response.status_code}")
                if response.status_code in [200, 401, 403, 301, 302]:
                    QMessageBox.information(self, '成功', f'代理连接成功\n\n代理类型: {proxy_type}\n地址: {host}:{port}')
                    return
            except Exception as http_e:
                print(f"HTTP测试失败: {http_e}")
            
            # 再测试HTTPS连接
            try:
                response = session.get('https://api.themoviedb.org/3/configuration?api_key=test', timeout=15)
                print(f"HTTPS响应状态码: {response.status_code}")
                if response.status_code in [200, 401, 403]:
                    QMessageBox.information(self, '成功', f'代理连接成功\n\n代理类型: {proxy_type}\n地址: {host}:{port}')
                    return
            except Exception as https_e:
                print(f"HTTPS测试失败: {https_e}")
                raise https_e
        except requests.exceptions.ProxyError as e:
            print(f"代理错误: {e}")
            QMessageBox.critical(self, '代理错误', f'无法连接到代理服务器\n\n请检查:\n1. 代理地址: {host}\n2. 端口: {port}\n3. 代理类型: {proxy_type}\n4. 代理服务是否已启动\n\n错误: {str(e)}')
        except requests.exceptions.ConnectTimeout:
            QMessageBox.critical(self, '连接超时', '代理连接超时，请检查代理服务是否正常')
        except requests.exceptions.SSLError as e:
            QMessageBox.critical(self, 'SSL错误', f'SSL证书验证失败\n\n错误: {str(e)}')
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, '错误', f'测试失败: {str(e)}')
    
    def test_api_key(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, '警告', '请输入 API Key')
            return
        
        proxy_config = None
        proxy_type_idx = self.proxy_type.currentIndex()
        if proxy_type_idx > 0:
            host = self.proxy_host.text().strip()
            port = self.proxy_port.text().strip()
            if not host or not port:
                QMessageBox.warning(self, '警告', '请填写代理地址和端口')
                return
            proxy_config = {
                'type': 'http' if proxy_type_idx == 1 else 'socks5',
                'host': host,
                'port': port,
                'username': self.proxy_user.text().strip(),
                'password': self.proxy_pass.text(),
            }
        
        QApplication.processEvents()
        
        try:
            print(f"测试API Key: {api_key[:10]}...")
            print(f"代理配置: {proxy_config}")
            temp_api = TMDBAPI(api_key, proxy_config)
            success, message = temp_api.test_api_key()
            print(f"API Key测试结果: {success}, {message}")
            if success:
                QMessageBox.information(self, '成功', 'API Key 有效')
            else:
                QMessageBox.warning(self, '失败', f'API Key 测试失败\n\n错误: {message}\n\n请检查:\n1. API Key是否正确\n2. 代理设置是否正确\n3. 网络是否通畅\n\n请查看 movie_scraper.log 文件获取详细日志')
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, '错误', f'测试失败: {str(e)}')
    
    def save_settings(self):
        config = {
            'api_key': self.api_key_input.text().strip(),
            'proxy': {
                'type': self.proxy_type.currentText().lower() if self.proxy_type.currentIndex() > 0 else '',
                'host': self.proxy_host.text().strip(),
                'port': self.proxy_port.text().strip(),
                'username': self.proxy_user.text().strip(),
                'password': self.proxy_pass.text(),
            }
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            self.api.set_api_key(config['api_key'])
            if config['proxy']['type']:
                self.api.set_proxy(config['proxy'])
            
            QMessageBox.information(self, '成功', '设置已保存')
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, '失败', f'保存设置失败: {e}')
