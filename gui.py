import os
import sys
import json
import shutil
import time
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QTabWidget,
    QLineEdit, QTextEdit, QComboBox, QFileDialog, QMessageBox,
    QSplitter, QFrame, QGroupBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QScrollArea, QGridLayout, QApplication,
    QProgressBar, QDialog, QDialogButtonBox, QInputDialog,
    QSizePolicy, QTreeWidget, QTreeWidgetItem, QMenu
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont, QImage
from typing import List, Optional, Dict
from api import TMDBAPI, MovieInfo
from scanner import LocalMovieScanner, LocalMovie, LocalSeries

class TVSeriesScrapeThread(QThread):
    progress_update = pyqtSignal(int, int, str)
    scrape_complete = pyqtSignal(list)
    
    def __init__(self, api: TMDBAPI, tmdb_id: int):
        super().__init__()
        self.api = api
        self.tmdb_id = tmdb_id
    
    def run(self):
        results = []
        
        try:
            self.progress_update.emit(1, 4, '正在刮削电视剧主页信息...')
            
            tv_details = self.api.get_tv_details(self.tmdb_id)
            
            if not tv_details:
                results.append({
                    'success': False,
                    'type': 'main',
                    'error': '未找到电视剧信息'
                })
                self.scrape_complete.emit(results)
                return
            
            results.append({
                'success': True,
                'type': 'main',
                'data': tv_details
            })
            
            seasons = tv_details.get('seasons', [])
            total_seasons = len(seasons)
            
            for i, season in enumerate(seasons, 1):
                season_num = season.get('season_number', 0)
                self.progress_update.emit(i + 1, 4, f'正在刮削第 {season_num} 季信息...')
                
                season_details = self.api.get_tv_season_details(self.tmdb_id, season_num)
                
                if season_details:
                    results.append({
                        'success': True,
                        'type': 'season',
                        'season': season_num,
                        'data': season_details
                    })
                    
                    episodes = season_details.get('episodes', [])
                    total_episodes = len(episodes)
                    
                    for j, episode in enumerate(episodes, 1):
                        episode_num = episode.get('episode_number', 0)
                        self.progress_update.emit(4 + j, 4 + total_episodes, f'正在刮削 S{season_num:02d}E{episode_num:02d}...')
                        
                        episode_details = self.api.get_tv_episode_details(self.tmdb_id, season_num, episode_num)
                        
                        if episode_details:
                            results.append({
                                'success': True,
                                'type': 'episode',
                                'season': season_num,
                                'episode': episode_num,
                                'data': episode_details
                            })
                        else:
                            results.append({
                                'success': False,
                                'type': 'episode',
                                'season': season_num,
                                'episode': episode_num,
                                'error': '未找到剧集信息'
                            })
                else:
                    results.append({
                        'success': False,
                        'type': 'season',
                        'season': season_num,
                        'error': '未找到季信息'
                    })
            
            self.scrape_complete.emit(results)
        except Exception as e:
            print(f"刮削电视剧失败: {e}")
            results.append({
                'success': False,
                'type': 'main',
                'error': str(e)
            })
            self.scrape_complete.emit(results)

class TVScrapeThread(QThread):
    progress_update = pyqtSignal(int, int, str)
    scrape_complete = pyqtSignal(list)
    
    def __init__(self, api: TMDBAPI, tmdb_id: int, episodes: list):
        super().__init__()
        self.api = api
        self.tmdb_id = tmdb_id
        self.episodes = episodes
        # 统计每个季的总集数
        self.season_episode_counts = {}
        for episode in episodes:
            season_num = episode.get('season', 0)
            if season_num not in self.season_episode_counts:
                self.season_episode_counts[season_num] = 0
            self.season_episode_counts[season_num] += 1
        # 记录每个季当前处理到第几集
        self.season_current_episode = {}
    
    def run(self):
        results = []
        total = len(self.episodes)
        
        for i, episode in enumerate(self.episodes, 1):
            try:
                season_num = episode.get('season', 0)
                episode_num = episode.get('episode', 0)
                
                # 更新当前季的集数计数
                if season_num not in self.season_current_episode:
                    self.season_current_episode[season_num] = 0
                self.season_current_episode[season_num] += 1
                
                # 获取该季的总集数
                season_total = self.season_episode_counts.get(season_num, 0)
                # 获取当前季的第几集
                current_in_season = self.season_current_episode[season_num]
                
                # 格式化进度信息：1/6-01季（1季总集6 第1集）
                progress_msg = f'{current_in_season}/{season_total}-{season_num:02d}季（{season_num}季总集{season_total} 第{current_in_season}集）'
                
                self.progress_update.emit(i, total, progress_msg)
                
                episode_info = self.api.get_tv_episode_details(self.tmdb_id, season_num, episode_num)
                
                if episode_info:
                    episode_path = episode.get('path', '')
                    nfo_path = os.path.splitext(episode_path)[0] + '.nfo'
                    
                    if nfo_path:
                        self._save_episode_nfo(nfo_path, episode_info, season_num, episode_num)
                    
                    results.append({
                        'success': True,
                        'season': season_num,
                        'episode': episode_num,
                        'path': episode_path
                    })
                else:
                    results.append({
                        'success': False,
                        'season': season_num,
                        'episode': episode_num,
                        'path': episode_path,
                        'error': '未找到剧集信息'
                    })
            except Exception as e:
                print(f"刮削剧集失败 S{episode.get('season', 0)}E{episode.get('episode', 0)}: {e}")
                results.append({
                    'success': False,
                    'season': episode.get('season', 0),
                    'episode': episode.get('episode', 0),
                    'path': episode.get('path', ''),
                    'error': str(e)
                })
        
        self.scrape_complete.emit(results)
    
    def _save_episode_nfo(self, nfo_path: str, episode_info: dict, season_num: int, episode_num: int):
        try:
            title = episode_info.get('name', '')
            overview = episode_info.get('overview', '')
            air_date = episode_info.get('air_date', '')
            vote_average = episode_info.get('vote_average', 0)
            still_path = episode_info.get('still_path', '')
            
            nfo_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<episodedetails>
    <title>{title}</title>
    <season>{season_num}</season>
    <episode>{episode_num}</episode>
    <aired>{air_date}</aired>
    <plot>{overview}</plot>
    <rating>{vote_average}</rating>
</episodedetails>
'''
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
        except Exception as e:
            print(f"保存NFO文件失败 {nfo_path}: {e}")

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
            import traceback
            traceback.print_exc()
            # 发送空结果，避免UI线程等待
            self.result_ready.emit([])

class ScanThread(QThread):
    progress_update = pyqtSignal(int, str)
    scan_complete = pyqtSignal(list, str)
    item_found = pyqtSignal(object, str)
    
    def __init__(self, scanner: LocalMovieScanner, directory: str, scan_type: str):
        super().__init__()
        self.scanner = scanner
        self.directory = directory
        self.scan_type = scan_type
        self.item_count = 0
    
    def run(self):
        try:
            if self.scan_type == '电影':
                self.progress_update.emit(0, f"开始扫描电影目录...")
                
                # 扫描目录并实时发送项目
                movies = []
                for movie in self.scanner.scan_directory_iter(self.directory):
                    movies.append(movie)
                    self.item_found.emit(movie, '电影')
                    self.item_count += 1
                    self.progress_update.emit(self.item_count, f"已加载 {self.item_count} 个电影")
                
                self.progress_update.emit(self.item_count, f"扫描完成，找到 {self.item_count} 个电影")
                self.scan_complete.emit(movies, '电影')
            else:
                self.progress_update.emit(0, f"开始扫描电视剧目录...")
                
                # 扫描目录并实时发送项目
                series_list = []
                for series in self.scanner.scan_series_directory_iter(self.directory):
                    series_list.append(series)
                    self.item_found.emit(series, '电视剧')
                    self.item_count += 1
                    self.progress_update.emit(self.item_count, f"已加载 {self.item_count} 个电视剧")
                
                self.progress_update.emit(self.item_count, f"扫描完成，找到 {self.item_count} 个电视剧")
                self.scan_complete.emit(series_list, '电视剧')
        except Exception as e:
            print(f"扫描错误: {e}")
            self.scan_complete.emit([], self.scan_type)

class ImageDownloadThread(QThread):
    progress_update = pyqtSignal(int, str)
    download_complete = pyqtSignal(bool, str)
    
    def __init__(self, api: TMDBAPI, media_item, directory: str):
        super().__init__()
        self.api = api
        self.media_item = media_item
        self.directory = directory
    
    def run(self):
        try:
            # 下载海报
            self.progress_update.emit(25, '正在下载海报...')
            poster_path = self.media_item.info.get('poster_path')
            if poster_path:
                poster_url = self.api.get_poster_url(poster_path, 'w500')
                if poster_url:
                    poster_save_path = os.path.join(self.directory, 'poster.jpg')
                    if self.api.download_image(poster_url, poster_save_path):
                        self.media_item.poster_path = poster_save_path
            
            # 下载背景图
            self.progress_update.emit(50, '正在下载背景图...')
            backdrop_path = self.media_item.info.get('backdrop_path')
            if backdrop_path:
                backdrop_url = self.api.get_backdrop_url(backdrop_path, 'w1280')
                if backdrop_url:
                    backdrop_save_path = os.path.join(self.directory, 'background.jpg')
                    self.api.download_image(backdrop_url, backdrop_save_path)
            
            # 下载logo
            self.progress_update.emit(75, '正在下载Logo...')
            logo_path = self.media_item.info.get('logo_path')
            if logo_path:
                logo_url = self.api.get_logo_url(logo_path, 'w500')
                if logo_url:
                    logo_save_path = os.path.join(self.directory, 'logo.png')
                    self.api.download_image(logo_url, logo_save_path)
            
            # 下载banner
            self.progress_update.emit(100, '正在下载Banner...')
            banner_path = self.media_item.info.get('banner_path')
            if banner_path:
                banner_url = self.api.get_banner_url(banner_path, 'w1280')
                if banner_url:
                    banner_save_path = os.path.join(self.directory, 'banner.jpg')
                    self.api.download_image(banner_url, banner_save_path)
            
            self.download_complete.emit(True, '图片下载完成')
        except Exception as e:
            print(f"下载图片错误: {e}")
            self.download_complete.emit(False, str(e))
    
    def _count_files(self, directory: str) -> int:
        """计算目录中的文件数量"""
        count = 0
        for root, dirs, files in os.walk(directory):
            count += len(files)
        return count

class EpisodeStillDownloadThread(QThread):
    """下载集剧照的线程"""
    progress_update = pyqtSignal(int, str)
    download_complete = pyqtSignal(bool, str)
    
    def __init__(self, api: TMDBAPI, series, base_directory: str):
        super().__init__()
        self.api = api
        self.series = series
        self.base_directory = base_directory
    
    def run(self):
        try:
            print("=== 开始下载集剧照 ===")
            
            if not hasattr(self.series, 'tmdb_id') or not self.series.tmdb_id:
                print("警告: 电视剧没有TMDB ID")
                self.download_complete.emit(False, '电视剧没有TMDB ID')
                return
            
            series_name = self.series.title or self.series.name
            tmdb_id = self.series.tmdb_id
            
            print(f"电视剧: {series_name}")
            print(f"TMDB ID: {tmdb_id}")
            
            # 获取所有季和集
            seasons = getattr(self.series, 'seasons', [])
            if not seasons:
                print("警告: 没有季信息")
                self.download_complete.emit(False, '没有季信息')
                return
            
            # 计算总集数
            total_episodes = 0
            for season in seasons:
                if isinstance(season, dict):
                    episodes = season.get('episodes', [])
                    total_episodes += len(episodes)
            
            print(f"总集数: {total_episodes}")
            
            if total_episodes == 0:
                print("警告: 没有集信息")
                self.download_complete.emit(False, '没有集信息')
                return
            
            # 下载每集的剧照
            downloaded_count = 0
            for season in seasons:
                if not isinstance(season, dict):
                    continue
                
                season_num = season.get('season', 0)
                episodes = season.get('episodes', [])
                
                print(f"\n处理第 {season_num} 季")
                
                for episode in episodes:
                    if not isinstance(episode, dict):
                        continue
                    
                    episode_num = episode.get('episode', 0)
                    episode_path = episode.get('path', '')
                    
                    if not episode_path:
                        print(f"  S{season_num:02d}E{episode_num:02d}: 没有集路径，跳过")
                        continue
                    
                    # 获取集目录
                    episode_dir = os.path.dirname(episode_path)
                    episode_base = os.path.splitext(os.path.basename(episode_path))[0]
                    
                    print(f"  S{season_num:02d}E{episode_num:02d}: {episode_base}")
                    
                    # 更新进度
                    progress = int((downloaded_count / total_episodes) * 100)
                    self.progress_update.emit(progress, f'正在下载 S{season_num:02d}E{episode_num:02d} 剧照...')
                    
                    # 获取集详细信息
                    try:
                        episode_details = self.api.get_episode_details(tmdb_id, season_num, episode_num)
                        
                        if episode_details and 'still_path' in episode_details:
                            still_path = episode_details['still_path']
                            
                            if still_path:
                                # 下载集剧照
                                still_url = self.api.get_still_url(still_path, 'w500')
                                
                                if still_url:
                                    # 保存为集缩略图 - 使用集文件名作为基础
                                    # 例如：幽遊白書_S01E01_第 1 集.STRM -> 幽遊白書_S01E01_第 1 集-thumb.jpg
                                    thumb_save_path = os.path.join(episode_dir, f"{episode_base}-thumb.jpg")
                                    
                                    print(f"    下载到: {thumb_save_path}")
                                    
                                    if self.api.download_image(still_url, thumb_save_path):
                                        print(f"    下载成功")
                                        downloaded_count += 1
                                    else:
                                        print(f"    下载失败")
                            else:
                                print(f"    没有集剧照")
                        else:
                            print(f"    无法获取集详情")
                    except Exception as e:
                        print(f"    获取集详情错误: {e}")
                    
                    # 短暂延迟，避免API请求过快
                    time.sleep(0.1)
            
            print(f"\n下载完成: {downloaded_count}/{total_episodes}")
            self.download_complete.emit(True, f'下载完成: {downloaded_count}/{total_episodes}')
        except Exception as e:
            print(f"下载集剧照错误: {e}")
            import traceback
            traceback.print_exc()
            self.download_complete.emit(False, str(e))

class SeriesCardWidget(QWidget):
    clicked = pyqtSignal(object)
    doubleClicked = pyqtSignal(object)
    
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
        
        # 点击和双击事件
        self.last_click_time = 0
        self.mousePressEvent = self._on_click
    
    def _on_click(self, event):
        current_time = event.timestamp()
        time_diff = current_time - self.last_click_time
        
        if time_diff < 500:  # 500ms内视为双击
            self.doubleClicked.emit(self.series)
        else:
            self.clicked.emit(self.series)
        
        self.last_click_time = current_time

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
        self.setWindowTitle('李先生ol-电影刮削器')
        
        # 设置窗口图标
        icon_path = self._get_resource_path('logo.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                self.setWindowIcon(icon)
        
        self._init_dpi_scaling()
        
        self.setStyleSheet(self.get_stylesheet())
        
        self.api = TMDBAPI()
        self.scanner = LocalMovieScanner()
        self.local_movies: List[LocalMovie] = []
        self.local_series: List[LocalSeries] = []
        self.filtered_movies: List[LocalMovie] = []
        self.filtered_series: List[LocalSeries] = []
        self.current_movie: Optional[LocalMovie] = None
        self.current_series: Optional[LocalSeries] = None
        self.current_scan_type: str = '电影'
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
    
    def _get_resource_path(self, relative_path: str) -> str:
        """获取资源文件路径，支持打包后的exe"""
        if hasattr(sys, 'frozen'):
            return os.path.join(os.path.dirname(sys.executable), relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
    
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
        
        # 扫描电影按钮
        scan_movie_btn = QPushButton('🎬 扫描电影')
        scan_movie_btn.clicked.connect(lambda: self.scan_directory('电影'))
        scan_movie_btn.setMaximumHeight(int(28 * self.scale_factor))
        scan_movie_btn.setMinimumHeight(int(28 * self.scale_factor))
        scan_movie_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(scan_movie_btn)
        
        # 扫描电视剧按钮
        scan_tv_btn = QPushButton('📺 扫描TV剧')
        scan_tv_btn.clicked.connect(lambda: self.scan_directory('电视剧'))
        scan_tv_btn.setMaximumHeight(int(28 * self.scale_factor))
        scan_tv_btn.setMinimumHeight(int(28 * self.scale_factor))
        scan_tv_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(scan_tv_btn)
        
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
        search_type.addItems(['全部', '电影', '电视剧', '合集'])
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
        
        header = QLabel('本地媒体列表')
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
        
        refresh_btn = QPushButton('🔄 刷新')
        refresh_btn.clicked.connect(self.refresh_movie_list)
        refresh_btn.setMaximumWidth(int(60 * self.scale_factor))
        search_layout.addWidget(refresh_btn)
        layout.addLayout(search_layout)
        
        # 当前目录添加新电影时间
        self.last_scan_time_label = QLabel('上次扫描: 未扫描')
        self.last_scan_time_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(self.last_scan_time_label)
        
        # 媒体列表 - 使用树形结构显示电视剧层级
        self.media_tree = QTreeWidget()
        self.media_tree.setHeaderLabels(['名称', '年份', '类型'])
        self.media_tree.setColumnWidth(0, 200)
        self.media_tree.setColumnWidth(1, 60)
        self.media_tree.setColumnWidth(2, 60)
        self.media_tree.setFrameShape(QFrame.NoFrame)
        self.media_tree.setExpandsOnDoubleClick(False)  # 禁用默认的双击展开行为
        self.media_tree.setSelectionMode(QTreeWidget.ExtendedSelection)  # 启用多选模式
        self.media_tree.itemClicked.connect(self.on_media_tree_clicked)
        self.media_tree.itemDoubleClicked.connect(self.on_media_tree_double_clicked)
        self.media_tree.itemSelectionChanged.connect(self.on_media_tree_selection_changed)  # 选择变化事件
        self.media_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.media_tree.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.media_tree)
        
        # 保留 movie_list 用于兼容性，但隐藏
        self.movie_list = QListWidget()
        self.movie_list.setVisible(False)
        
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
        rename_save_all_btn = QPushButton('改名保存全部')
        rename_save_all_btn.clicked.connect(self.rename_save_all)
        rename_save_all_btn.setMaximumHeight(int(26 * self.scale_factor))
        btn_layout.addWidget(rename_save_all_btn)
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
        
        # 图片显示区域
        images_label = QLabel('图片:')
        images_label.setFont(QFont('Microsoft YaHei', max(9, int(10 * self.scale_factor)), QFont.Bold))
        layout.addWidget(images_label)
        
        images_layout = QHBoxLayout()
        images_layout.setSpacing(int(10 * self.scale_factor))
        
        # 缩略图（第一显示）
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(int(150 * self.scale_factor), int(150 * self.scale_factor))
        self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.thumbnail_label.setToolTip('缩略图')
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(self.thumbnail_label)
        
        # 背景图片
        self.backdrop_label = QLabel()
        self.backdrop_label.setFixedSize(int(150 * self.scale_factor), int(150 * self.scale_factor))
        self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.backdrop_label.setToolTip('背景图片')
        self.backdrop_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(self.backdrop_label)
        
        # Banner图片
        self.banner_label = QLabel()
        self.banner_label.setFixedSize(int(150 * self.scale_factor), int(150 * self.scale_factor))
        self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.banner_label.setToolTip('Banner图片')
        self.banner_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(self.banner_label)
        
        # Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(int(150 * self.scale_factor), int(150 * self.scale_factor))
        self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.logo_label.setToolTip('Logo')
        self.logo_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(self.logo_label)
        
        images_layout.addStretch()
        layout.addLayout(images_layout)
        
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
    

    
    def scrape_tv_episodes(self):
        # 季集列表已移除，此方法通过树形列表选择剧集
        # 获取当前选中的树节点
        selected_items = self.media_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先选择要刮削的剧集')
            return
        
        episodes_to_scrape = []
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'episode':
                episode_data = data.get('data')
                if episode_data:
                    episodes_to_scrape.append(episode_data)
        
        if episodes_to_scrape:
            self.start_tv_scraping(episodes_to_scrape)
        else:
            QMessageBox.warning(self, '警告', '请先选择要刮削的剧集')
    
    def scrape_all_tv_episodes(self):
        if not self.current_series:
            QMessageBox.warning(self, '警告', '请先选择电视剧')
            return
        
        all_episodes = []
        for season in self.current_series.seasons:
            all_episodes.extend(season.get('episodes', []))
        
        if all_episodes:
            self.start_tv_scraping(all_episodes)
    
    def scrape_single_episode(self, season_num, episode_num):
        if not self.current_series or not self.current_series.tmdb_id:
            QMessageBox.warning(self, '警告', '请先搜索并匹配电视剧信息')
            return
        
        # 找到对应的剧集
        episode = None
        for season in self.current_series.seasons:
            if isinstance(season, dict) and season.get('season') == season_num:
                episodes = season.get('episodes', [])
                for ep in episodes:
                    if isinstance(ep, dict) and ep.get('episode') == episode_num:
                        episode = ep
                        break
                if episode:
                    break
        
        if episode:
            self.start_tv_scraping([episode])
        else:
            QMessageBox.information(self, '提示', '未找到指定剧集')
    
    def start_tv_scraping(self, episodes):
        if not self.current_series or not self.current_series.tmdb_id:
            QMessageBox.warning(self, '警告', '请先搜索并匹配电视剧信息')
            return
        
        self.scrape_tv_thread = TVScrapeThread(self.api, self.current_series.tmdb_id, episodes)
        self.scrape_tv_thread.progress_update.connect(self.on_tv_scrape_progress)
        self.scrape_tv_thread.scrape_complete.connect(self.on_tv_scrape_complete)
        self.scrape_tv_thread.start()
        
        self.show_progress_dialog('刮削中...', len(episodes))
    
    def scrape_series_details(self):
        if not self.current_series:
            QMessageBox.warning(self, '警告', '请先选择电视剧')
            return
        
        if not self.current_series.tmdb_id:
            QMessageBox.warning(self, '警告', '请先搜索并匹配电视剧信息')
            return
        
        self.scrape_series_thread = TVSeriesScrapeThread(self.api, self.current_series.tmdb_id)
        self.scrape_series_thread.progress_update.connect(self.on_series_scrape_progress)
        self.scrape_series_thread.scrape_complete.connect(self.on_series_scrape_complete)
        self.scrape_series_thread.start()
        
        self.show_progress_dialog('刮削电视剧信息...', 0)
    
    def on_series_scrape_progress(self, current, total, message):
        if self.progress_bar and self.progress_label:
            if total > 0:
                self.progress_bar.setValue(int((current / total) * 100))
            else:
                self.progress_bar.setValue(current)
            self.progress_label.setText(message)
    
    def on_series_scrape_complete(self, results):
        self.close_progress_dialog()
        
        success_count = sum(1 for r in results if r.get('success', False))
        total_count = len(results)
        
        QMessageBox.information(self, '完成', f'刮削完成！\n成功: {success_count}/{total_count}')
        
        if success_count > 0:
            self.show_tv_episodes(self.current_series)
    
    def on_tv_scrape_progress(self, current, total, message):
        if self.progress_bar and self.progress_label:
            self.progress_bar.setValue(int((current / total) * 100))
            self.progress_label.setText(message)
    
    def on_tv_scrape_complete(self, results):
        self.close_progress_dialog()
        
        success_count = sum(1 for r in results if r.get('success', False))
        total_count = len(results)
        
        QMessageBox.information(self, '完成', f'刮削完成！\n成功: {success_count}/{total_count}')
    
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
    
    def scan_directory(self, scan_type='电影'):
        directory = QFileDialog.getExistingDirectory(self, '选择目录')
        if not directory:
            return
        
        # 设置当前目录和扫描类型
        self.current_directory = directory
        self.current_scan_type = scan_type
        
        # 清空列表
        self.media_tree.clear()
        
        # 创建进度对话框
        progress_dialog = self._create_progress_dialog(f'正在扫描{scan_type}...')
        
        # 创建并启动扫描线程
        self.scan_thread = ScanThread(self.scanner, directory, scan_type)
        self.scan_thread.progress_update.connect(self._update_progress)
        self.scan_thread.item_found.connect(self._on_item_found)
        self.scan_thread.scan_complete.connect(self._scan_complete)
        self.scan_thread.start()
        
        # 显示进度对话框
        progress_dialog.exec_()
    
    def refresh_movie_list(self):
        """刷新电影列表"""
        if not self.current_directory:
            QMessageBox.warning(self, '警告', '请先选择一个目录')
            return
        
        # 清空列表
        self.media_tree.clear()
        
        # 创建进度对话框
        progress_dialog = self._create_progress_dialog('正在刷新列表...')
        
        # 创建并启动扫描线程
        # 根据当前扫描类型决定扫描类型
        scan_type = getattr(self, 'current_scan_type', '电影')
        self.scan_thread = ScanThread(self.scanner, self.current_directory, scan_type)
        self.scan_thread.progress_update.connect(self._update_progress)
        self.scan_thread.item_found.connect(self._on_item_found)
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
    
    def _on_item_found(self, item, scan_type):
        """处理实时发现的媒体项目"""
        if scan_type == '电影':
            self._add_movie_to_tree(item)
        else:
            self._add_series_to_tree(item)
    
    def _add_movie_to_tree(self, movie):
        """添加电影到树形列表"""
        item = QTreeWidgetItem(self.media_tree)
        # 显示格式：标题 (年份)
        title = movie.title or movie.name
        year = movie.year or ''
        if year:
            display_name = f"{title} ({year})"
        else:
            display_name = title
        item.setText(0, display_name)
        # 使用字典格式存储数据，与 on_media_tree_clicked 方法兼容
        item.setData(0, Qt.UserRole, {'type': 'movie', 'data': movie})
    
    def _add_series_to_tree(self, series):
        """添加电视剧到树形列表"""
        series_item = QTreeWidgetItem(self.media_tree)
        # 显示格式：标题 (年份)
        title = series.title or series.name
        year = series.year or ''
        if year:
            display_name = f"{title} ({year})"
        else:
            display_name = title
        series_item.setText(0, display_name)
        # 使用字典格式存储数据，与 on_media_tree_clicked 方法兼容
        series_item.setData(0, Qt.UserRole, {'type': 'series', 'data': series})
        
        # 添加季节点
        for season in series.seasons:
            if isinstance(season, dict):
                season_num = season.get('season', 0)
                season_item = QTreeWidgetItem(series_item)
                season_item.setText(0, f'第 {season_num} 季')
                # 使用字典格式存储数据，与 on_media_tree_clicked 方法兼容
                season_item.setData(0, Qt.UserRole, {'type': 'season', 'data': season, 'series': series})
                
                # 添加集节点
                episodes = season.get('episodes', [])
                for ep in episodes:
                    if isinstance(ep, dict):
                        ep_num = ep.get('episode', 0)
                        ep_name = ep.get('name', '')
                        ep_item = QTreeWidgetItem(season_item)
                        ep_item.setText(0, f'第 {ep_num} 集: {ep_name}')
                        # 使用字典格式存储数据，与 on_media_tree_clicked 方法兼容
                        ep_item.setData(0, Qt.UserRole, {'type': 'episode', 'data': ep, 'series': series})
    
    def _scan_complete(self, items: list, scan_type: str):
        """扫描完成处理"""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        # 更新当前扫描类型
        self.current_scan_type = scan_type
        
        # 更新上次扫描时间
        import datetime
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if hasattr(self, 'last_scan_time_label'):
            self.last_scan_time_label.setText(f'上次扫描: {current_time}')
        
        if scan_type == '电影':
            self.local_movies = items
            self.filtered_movies = self.local_movies
            self.selection_label.setText(f'共 {len(self.local_movies)} 个电影')
            QMessageBox.information(self, '扫描完成', f'找到 {len(self.local_movies)} 个视频文件')
        else:
            # 电视剧扫描
            self.local_series = items
            self.filtered_series = self.local_series
            self.selection_label.setText(f'共 {len(self.local_series)} 个电视剧')
            QMessageBox.information(self, '扫描完成', f'找到 {len(self.local_series)} 个电视剧')
    
    def add_movie_to_list(self, movie: LocalMovie):
        # 创建电影节点
        movie_item = QTreeWidgetItem(self.media_tree)
        movie_item.setText(0, movie.title or movie.name)
        movie_item.setText(1, movie.year or '')
        movie_item.setText(2, '电影')
        movie_item.setData(0, Qt.UserRole, {'type': 'movie', 'data': movie})
    
    def add_series_to_list(self, series):
        # 创建电视剧根节点
        series_item = QTreeWidgetItem(self.media_tree)
        series_item.setText(0, series.title or series.name)
        series_item.setText(1, series.year or '')
        series_item.setText(2, '电视剧')
        series_item.setData(0, Qt.UserRole, {'type': 'series', 'data': series})
        
        # 添加季和集
        for season in series.seasons:
            if isinstance(season, dict):
                season_num = season.get('season', 0)
                season_item = QTreeWidgetItem(series_item)
                season_item.setText(0, f'第 {season_num} 季')
                season_item.setText(1, '')
                season_item.setText(2, f'{len(season.get("episodes", []))} 集')
                season_item.setData(0, Qt.UserRole, {'type': 'season', 'data': season, 'series': series})
                
                # 添加集
                for episode in season.get('episodes', []):
                    if isinstance(episode, dict):
                        episode_num = episode.get('episode', 0)
                        episode_name = episode.get('name', '')
                        episode_item = QTreeWidgetItem(season_item)
                        episode_item.setText(0, f'第 {episode_num} 集')
                        episode_item.setText(1, '')
                        episode_item.setText(2, episode_name)
                        episode_item.setData(0, Qt.UserRole, {'type': 'episode', 'data': episode, 'series': series})
    
    def on_media_tree_clicked(self, item, column):
        """处理树形列表点击事件"""
        try:
            data = item.data(0, Qt.UserRole)
            if not data:
                return
            
            item_type = data.get('type')
            
            if item_type == 'movie':
                movie = data.get('data')
                if movie:
                    self.current_movie = movie
                    self.update_detail_view(movie)
            elif item_type == 'series':
                series = data.get('data')
                if series:
                    self.current_series = series
                    self.update_series_detail_view(series)
            elif item_type == 'season':
                season = data.get('data')
                series = data.get('series')
                if series:
                    self.current_series = series
                    self.update_season_detail_view(series, season)
            elif item_type == 'episode':
                episode = data.get('data')
                series = data.get('series')
                if series:
                    self.current_series = series
                    self.update_episode_detail_view(series, episode)
        except Exception as e:
            print(f"媒体树点击事件错误: {e}")
            import traceback
            traceback.print_exc()
    
    def on_media_tree_selection_changed(self):
        """处理选择变化事件"""
        try:
            selected_items = self.media_tree.selectedItems()
            count = len(selected_items)
            
            if count == 0:
                self.selection_label.setText('未选择')
            elif count == 1:
                item = selected_items[0]
                data = item.data(0, Qt.UserRole)
                if data:
                    item_type = data.get('type')
                    if item_type == 'movie':
                        self.selection_label.setText(f'已选择 1 个电影')
                    elif item_type == 'series':
                        self.selection_label.setText(f'已选择 1 个电视剧')
                    elif item_type == 'season':
                        self.selection_label.setText(f'已选择 1 个季')
                    elif item_type == 'episode':
                        self.selection_label.setText(f'已选择 1 个集')
                    else:
                        self.selection_label.setText(f'已选择 1 项')
                else:
                    self.selection_label.setText(f'已选择 1 项')
            else:
                # 统计不同类型的数量
                movie_count = 0
                series_count = 0
                season_count = 0
                episode_count = 0
                
                for item in selected_items:
                    data = item.data(0, Qt.UserRole)
                    if data:
                        item_type = data.get('type')
                        if item_type == 'movie':
                            movie_count += 1
                        elif item_type == 'series':
                            series_count += 1
                        elif item_type == 'season':
                            season_count += 1
                        elif item_type == 'episode':
                            episode_count += 1
                
                parts = []
                if movie_count > 0:
                    parts.append(f'{movie_count} 个电影')
                if series_count > 0:
                    parts.append(f'{series_count} 个电视剧')
                if season_count > 0:
                    parts.append(f'{season_count} 个季')
                if episode_count > 0:
                    parts.append(f'{episode_count} 个集')
                
                if parts:
                    self.selection_label.setText(f'已选择: {", ".join(parts)}')
                else:
                    self.selection_label.setText(f'已选择 {count} 项')
        except Exception as e:
            print(f"选择变化事件错误: {e}")
            import traceback
            traceback.print_exc()
    
    def on_media_tree_double_clicked(self, item, column):
        """处理树形列表双击事件 - 展开/折叠当前项"""
        try:
            if not item:
                return
            
            # 检查item是否有isExpanded方法
            if not hasattr(item, 'isExpanded') or not hasattr(item, 'setExpanded'):
                print("item没有isExpanded或setExpanded方法")
                return
            
            # 切换展开状态
            try:
                is_expanded = item.isExpanded()
                item.setExpanded(not is_expanded)
            except Exception as expand_error:
                print(f"展开/折叠操作错误: {expand_error}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"双击展开/折叠错误: {e}")
            import traceback
            traceback.print_exc()
    
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
        self.media_tree.clear()
        
        scan_type = getattr(self, 'current_scan_type', '电影')
        
        if scan_type == '电影':
            if not query:
                self.filtered_movies = self.local_movies
            else:
                self.filtered_movies = [m for m in self.local_movies if query in m.name.lower() or (m.title and query in m.title.lower())]
            
            for movie in self.filtered_movies:
                self.add_movie_to_list(movie)
            
            self.selection_label.setText(f'共 {len(self.filtered_movies)} 个电影')
        else:
            if not query:
                self.filtered_series = self.local_series
            else:
                self.filtered_series = [s for s in self.local_series if query in s.name.lower() or (s.title and query in s.title.lower())]
            
            for series in self.filtered_series:
                self._add_series_to_tree(series)
            
            self.selection_label.setText(f'共 {len(self.filtered_series)} 个电视剧')
    
    def clear_local_search(self):
        """清除搜索和列表"""
        # 清空搜索框
        self.local_search_input.clear()
        
        # 清空列表数据
        self.local_movies = []
        self.local_series = []
        self.filtered_movies = []
        self.filtered_series = []
        
        # 清空媒体树
        self.media_tree.clear()
        
        # 清空当前选择
        self.current_movie = None
        self.current_series = None
        
        # 更新选择标签
        self.selection_label.setText('未选择')
        
        # 清空详情视图
        self.reset_edit_form()
        
        print("已清除所有列表数据")
    
    def update_detail_view(self, movie: LocalMovie):
        # 尝试加载本地海报
        poster_loaded = False
        if movie.poster_path and os.path.exists(movie.poster_path):
            pixmap = QPixmap(movie.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_poster.setPixmap(scaled)
                poster_loaded = True
        
        # 如果本地没有海报，尝试从 TMDB 下载
        if not poster_loaded and movie.info.get('poster_path'):
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
                except Exception:
                    pass
        
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
        
        # 异步加载图片
        QTimer.singleShot(100, lambda: self._load_images(movie))
    
    def _load_images(self, media):
        """加载媒体的各种图片"""
        try:
            print("=== _load_images 被调用 ===")
            
            # 清空所有图片
            self.backdrop_label.clear()
            self.banner_label.clear()
            self.logo_label.clear()
            self.thumbnail_label.clear()
            
            # 设置默认背景
            self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
            self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
            self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
            self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
            
            # 检查media是否有path属性
            if not hasattr(media, 'path') or not media.path:
                print("警告: media没有path属性")
                return
            
            # 尝试从本地目录加载图片
            media_dir = os.path.dirname(media.path)
            print(f"媒体目录: {media_dir}")
            
            # 图片扩展名列表
            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            
            # 加载缩略图 - 优先使用 poster_path
            thumb_loaded = False
            if hasattr(media, 'poster_path') and media.poster_path and os.path.exists(media.poster_path):
                print(f"加载 poster_path 缩略图: {media.poster_path}")
                self._load_local_image(media.poster_path, self.thumbnail_label)
                thumb_loaded = True
            
            if not thumb_loaded:
                # 尝试多种缩略图命名格式
                thumb_names = ['thumb', 'poster', 'thumbnail', 'cover']
                for name in thumb_names:
                    for ext in image_extensions:
                        thumb_path = os.path.join(media_dir, f"{name}{ext}")
                        if os.path.exists(thumb_path):
                            print(f"加载本地缩略图: {thumb_path}")
                            self._load_local_image(thumb_path, self.thumbnail_label)
                            thumb_loaded = True
                            break
                    if thumb_loaded:
                        break
            
            if not thumb_loaded:
                print("本地缩略图不存在")
            
            # 加载背景图片 - 优先使用 backdrop_path
            backdrop_loaded = False
            if hasattr(media, 'backdrop_path') and media.backdrop_path and os.path.exists(media.backdrop_path):
                print(f"加载 backdrop_path 背景图片: {media.backdrop_path}")
                self._load_local_image(media.backdrop_path, self.backdrop_label)
                backdrop_loaded = True
            
            if not backdrop_loaded:
                # 尝试多种背景图命名格式
                backdrop_names = ['background', 'backdrop', 'fanart', 'bg']
                for name in backdrop_names:
                    for ext in image_extensions:
                        backdrop_path = os.path.join(media_dir, f"{name}{ext}")
                        if os.path.exists(backdrop_path):
                            print(f"加载本地背景图片: {backdrop_path}")
                            self._load_local_image(backdrop_path, self.backdrop_label)
                            backdrop_loaded = True
                            break
                    if backdrop_loaded:
                        break
            
            if not backdrop_loaded:
                print("本地背景图片不存在")
            
            # 加载Banner图片
            banner_loaded = False
            banner_names = ['banner']
            for name in banner_names:
                for ext in image_extensions:
                    banner_path = os.path.join(media_dir, f"{name}{ext}")
                    if os.path.exists(banner_path):
                        print(f"加载本地Banner图片: {banner_path}")
                        self._load_local_image(banner_path, self.banner_label)
                        banner_loaded = True
                        break
                if banner_loaded:
                    break
            
            if not banner_loaded:
                print("本地Banner图片不存在")
            
            # 加载Logo图片
            logo_loaded = False
            logo_names = ['logo', 'clearlogo']
            for name in logo_names:
                for ext in image_extensions:
                    logo_path = os.path.join(media_dir, f"{name}{ext}")
                    if os.path.exists(logo_path):
                        print(f"加载本地Logo图片: {logo_path}")
                        self._load_local_image(logo_path, self.logo_label)
                        logo_loaded = True
                        break
                if logo_loaded:
                    break
            
            if not logo_loaded:
                print("本地Logo图片不存在")
            
            print("图片加载完成")
        except Exception as e:
            print(f"加载图片错误: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_detail_view(self):
        """清空电影详情视图"""
        # 清空海报
        self.detail_poster.clear()
        self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 清空编辑组件
        self.edit_title.clear()
        self.edit_original_title.clear()
        self.edit_year.clear()
        self.edit_type.setCurrentIndex(0)
        self.edit_rating.setValue(0)
        self.edit_tmdb_id.clear()
        self.edit_genres.clear()
        self.edit_overview.clear()
        
        # 清空图片
        self.backdrop_label.clear()
        self.banner_label.clear()
        self.logo_label.clear()
        self.thumbnail_label.clear()
        
        # 设置默认背景
        self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
    
    def _load_local_image(self, image_path, label):
        """从本地加载图片到标签"""
        try:
            # 检查图片文件是否存在
            if not os.path.exists(image_path):
                return
            
            # 直接加载图片，不打印调试信息
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return
            
            # 获取标签尺寸
            label_width = label.width()
            label_height = label.height()
            
            # 如果标签尺寸为0，使用固定尺寸
            if label_width <= 0 or label_height <= 0:
                label_width = 120
                label_height = 80
            
            # 异步缩放图片
            scaled = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
            label.setStyleSheet("border-radius: 4px;")
        except Exception:
            # 静默处理异常
            pass
    
    def _load_image_from_url(self, path, label, size):
        """从URL加载图片到标签"""
        try:
            import requests
            image_url = self.api.get_poster_url(path, size)
            if image_url:
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        # 获取标签尺寸
                        label_width = label.width()
                        label_height = label.height()
                        
                        # 如果标签尺寸为0，使用固定尺寸
                        if label_width <= 0 or label_height <= 0:
                            label_width = 120
                            label_height = 80
                        
                        scaled = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        label.setPixmap(scaled)
                        label.setStyleSheet("border-radius: 4px;")
        except Exception:
            # 静默处理异常
            pass
    
    def _load_nfo_info(self, nfo_path):
        """加载NFO文件信息"""
        if not nfo_path or not os.path.exists(nfo_path):
            return None
        
        try:
            with open(nfo_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(nfo_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                return None
        except Exception:
            return None
        
        info = {}
        
        try:
            if content.strip().startswith('<?xml') or content.strip().startswith('<'):
                import xml.etree.ElementTree as ET
                root = ET.fromstring(content)
                
                def find_element_recursive(element, tag):
                    for child in element:
                        if child.tag.lower() == tag.lower():
                            return child
                    for child in element:
                        found = find_element_recursive(child, tag)
                        if found is not None:
                            return found
                    return None
                
                for tag in ['title', 'plot', 'overview', 'synopsis', 'rating', 'year', 'aired', 'season', 'episode']:
                    elem = find_element_recursive(root, tag)
                    if elem is not None and elem.text:
                        info[tag] = elem.text.strip()
            else:
                try:
                    data = json.loads(content)
                    info = data
                except Exception:
                    pass
        except Exception:
            pass
        
        return info if info else None
    
    def _load_season_images(self, series, season):
        """加载季的图片"""
        # 清空所有图片
        self.backdrop_label.clear()
        self.banner_label.clear()
        self.logo_label.clear()
        self.thumbnail_label.clear()
        
        # 设置默认背景
        self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        
        # 尝试从本地目录加载图片
        media_dir = os.path.dirname(series.path)
        season_num = season.get('season', 0)
        
        # 加载背景图片 - 只加载本地图片
        backdrop_path = os.path.join(media_dir, "background.jpg")
        if os.path.exists(backdrop_path):
            self._load_local_image(backdrop_path, self.backdrop_label)
        
        # 加载Banner图片 - 只加载本地图片
        banner_path = os.path.join(media_dir, "banner.jpg")
        if os.path.exists(banner_path):
            self._load_local_image(banner_path, self.banner_label)
        
        # 加载季主图 - 支持多种命名格式
        season_poster_loaded = False
        possible_extensions = ['.jpg', '.png', '.jpeg']
        
        # 尝试多种季图片命名格式
        season_formats = [
            f"season{season_num:02d}-poster.jpg",
            f"Season {season_num:02d}.jpg",
            f"season{season_num}.jpg",
            f"S{season_num:02d}.jpg",
            f"season_{season_num:02d}.jpg",
            f"season{season_num:02d}.jpg",
            f"Season{season_num}.jpg",
            f"season{season_num}.jpg",
        ]
        
        for format_name in season_formats:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, format_name.replace('.jpg', ext))
                if os.path.exists(season_poster_path):
                    self._load_local_image(season_poster_path, self.logo_label)
                    season_poster_loaded = True
                    break
            if season_poster_loaded:
                break
        
        # 如果没有找到季图片，尝试加载电视剧封面 - 只加载本地图片
        if not season_poster_loaded and series.poster_path and os.path.exists(series.poster_path):
            self._load_local_image(series.poster_path, self.logo_label)
        
        # 加载缩略图 - 只加载本地图片
        thumb_path = os.path.join(media_dir, "thumb.jpg")
        if os.path.exists(thumb_path):
            self._load_local_image(thumb_path, self.thumbnail_label)
    
    def _load_episode_images(self, series, episode):
        """加载集的图片"""
        # 清空所有图片
        self.backdrop_label.clear()
        self.banner_label.clear()
        self.logo_label.clear()
        self.thumbnail_label.clear()
        
        # 设置默认背景
        self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        
        # 尝试从本地目录加载图片
        media_dir = os.path.dirname(series.path)
        episode_path = episode.get('path', '')
        episode_dir = os.path.dirname(episode_path)
        episode_name = os.path.basename(episode_path)
        episode_base = os.path.splitext(episode_name)[0]
        series_name = series.title or series.name
        season_num = episode.get('season', 1)
        episode_num = episode.get('episode', 0)
        
        # 尝试加载集特定的缩略图
        possible_extensions = ['.jpg', '.png', '.jpeg']
        thumbnail_loaded = False
        
        # 尝试在季文件夹中查找集的缩略图
        print(f"\n=== 加载集缩略图 (S{season_num:02d}E{episode_num:02d}) ===")
        print(f"  集路径: {episode_path}")
        print(f"  集目录: {episode_dir}")
        print(f"  集文件名: {episode_name}")
        print(f"  集文件基名: {episode_base}")
        print(f"  电视剧名: {series_name}")
        
        # 尝试 集文件名.jpg 格式（优先尝试）
        for ext in possible_extensions:
            thumb_path = os.path.join(episode_dir, f"{episode_base}{ext}")
            print(f"  尝试: {thumb_path}")
            if os.path.exists(thumb_path):
                print(f"  加载成功: {thumb_path}")
                self._load_local_image(thumb_path, self.thumbnail_label)
                thumbnail_loaded = True
                break
        
        # 尝试 S01E01-thumb.jpg 格式
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"S{season_num:02d}E{episode_num:02d}-thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 电视剧名_S01E01_第 1 集-thumb.jpg 格式
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{series_name}_S{season_num:02d}E{episode_num:02d}_第 {episode_num} 集-thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 电视剧名 S01E01 第X集-thumb.jpg 格式（用户自定义格式）
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{series_name} S{season_num:02d}E{episode_num:02d} 第{episode_num}集-thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 电视剧名 S01E01 第一集-thumb.jpg 格式（中文数字）
        if not thumbnail_loaded:
            chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
            if episode_num <= 10:
                chinese_num = chinese_nums[episode_num]
            else:
                chinese_num = str(episode_num)
            
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{series_name} S{season_num:02d}E{episode_num:02d} 第{chinese_num}集-thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 S01E01.jpg 格式
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"S{season_num:02d}E{episode_num:02d}{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 集文件名-thumb.jpg 格式
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{episode_base}-thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 集文件名_thumb.jpg 格式（下划线）
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{episode_base}_thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 尝试 集文件名 thumb.jpg 格式（空格）
        if not thumbnail_loaded:
            for ext in possible_extensions:
                thumb_path = os.path.join(episode_dir, f"{episode_base} thumb{ext}")
                print(f"  尝试: {thumb_path}")
                if os.path.exists(thumb_path):
                    print(f"  加载成功: {thumb_path}")
                    self._load_local_image(thumb_path, self.thumbnail_label)
                    thumbnail_loaded = True
                    break
        
        # 加载背景图片 - 只加载本地图片
        backdrop_path = os.path.join(media_dir, "background.jpg")
        if os.path.exists(backdrop_path):
            self._load_local_image(backdrop_path, self.backdrop_label)
        
        # 加载Banner图片 - 只加载本地图片
        banner_path = os.path.join(media_dir, "banner.jpg")
        if os.path.exists(banner_path):
            self._load_local_image(banner_path, self.banner_label)
        
        # 加载Logo - 只加载本地图片
        logo_path = os.path.join(media_dir, "logo.png")
        if os.path.exists(logo_path):
            self._load_local_image(logo_path, self.logo_label)
    def update_series_detail_view(self, series):
        try:
            # 尝试加载本地海报
            poster_loaded = False
            if hasattr(series, 'poster_path') and series.poster_path and os.path.exists(series.poster_path):
                pixmap = QPixmap(series.poster_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.detail_poster.setPixmap(scaled)
                    poster_loaded = True
            
            if not poster_loaded:
                self.detail_poster.clear()
                self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
            
            # 更新编辑组件
            self.edit_title.setText(getattr(series, 'title', None) or getattr(series, 'name', ''))
            self.edit_original_title.setText(getattr(series, 'info', {}).get('original_title', ''))
            self.edit_year.setText(getattr(series, 'year', '') or '')
            self.edit_type.setCurrentIndex(1)  # 电视剧
            self.edit_rating.setValue(getattr(series, 'vote_average', None) or 0)
            self.edit_tmdb_id.setText(str(getattr(series, 'tmdb_id', None)) if getattr(series, 'tmdb_id', None) else '')
            self.edit_genres.setText(', '.join(getattr(series, 'genres', [])))
            
            # 电视剧简介
            overview = getattr(series, 'overview', None) or '暂无简介'
            # 添加季节信息
            seasons_info = f"\n\n【季节信息】\n"
            seasons = getattr(series, 'seasons', [])
            if seasons:
                for season in seasons:
                    if isinstance(season, dict):
                        season_num = season.get('season', 0)
                        episodes = season.get('episodes', [])
                        seasons_info += f"第 {season_num} 季: {len(episodes)} 集\n"
            
            self.edit_overview.setText(overview + seasons_info)
            
            # 异步加载图片
            QTimer.singleShot(100, lambda: self._load_images(series))
        except Exception as e:
            print(f"更新电视剧详情视图错误: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_series_detail_view(self):
        """清空电视剧详情视图"""
        # 清空海报
        self.detail_poster.clear()
        self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 清空编辑组件
        self.edit_title.clear()
        self.edit_original_title.clear()
        self.edit_year.clear()
        self.edit_type.setCurrentIndex(1)
        self.edit_rating.setValue(0)
        self.edit_tmdb_id.clear()
        self.edit_genres.clear()
        self.edit_overview.clear()
        
        # 清空图片
        self.backdrop_label.clear()
        self.banner_label.clear()
        self.logo_label.clear()
        self.thumbnail_label.clear()
        
        # 设置默认背景
        self.backdrop_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.banner_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.logo_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
        self.thumbnail_label.setStyleSheet("background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;")
    
    def update_season_detail_view(self, series, season):
        """显示季的详细信息"""
        # 尝试加载本地海报
        poster_loaded = False
        media_dir = os.path.dirname(series.path)
        season_num = season.get('season', 0)
        
        # 尝试加载季特定的封面 - 支持多种命名格式
        possible_extensions = ['.jpg', '.png', '.jpeg']
        
        # 尝试 season01-poster.jpg 格式
        for ext in possible_extensions:
            season_poster_path = os.path.join(media_dir, f"season{season_num:02d}-poster{ext}")
            if os.path.exists(season_poster_path):
                pixmap = QPixmap(season_poster_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.detail_poster.setPixmap(scaled)
                    poster_loaded = True
                    break
        
        # 尝试 season 1-poster.jpg 格式
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"season {season_num}-poster{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 尝试 season01-poster.jpg 格式（无连字符）
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"season{season_num:02d}poster{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 尝试 season 1 poster.jpg 格式（空格）
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"season {season_num} poster{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 尝试 S01-poster.jpg 格式
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"S{season_num:02d}-poster{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 尝试 S01poster.jpg 格式（无连字符）
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"S{season_num:02d}poster{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 尝试 season01.jpg 格式（直接使用季号）
        if not poster_loaded:
            for ext in possible_extensions:
                season_poster_path = os.path.join(media_dir, f"season{season_num:02d}{ext}")
                if os.path.exists(season_poster_path):
                    pixmap = QPixmap(season_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        break
        
        # 如果没有季封面，尝试加载电视剧封面
        if not poster_loaded and series.poster_path and os.path.exists(series.poster_path):
            pixmap = QPixmap(series.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_poster.setPixmap(scaled)
                poster_loaded = True
        
        if not poster_loaded:
            self.detail_poster.clear()
            self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 加载季的nfo信息
        season_nfo_info = None
        season_nfo_path = season.get('nfo_path')
        if season_nfo_path:
            season_nfo_info = self._load_nfo_info(season_nfo_path)
        
        # 更新编辑组件
        if season_nfo_info and season_nfo_info.get('title'):
            self.edit_title.setText(season_nfo_info.get('title', ''))
        else:
            self.edit_title.setText(f"{series.title or series.name} - 第 {season_num} 季")
        
        self.edit_original_title.setText(series.info.get('original_title', ''))
        self.edit_year.setText(series.year or '')
        self.edit_type.setCurrentIndex(1)  # 电视剧
        
        if season_nfo_info and season_nfo_info.get('rating'):
            try:
                self.edit_rating.setValue(float(season_nfo_info.get('rating', 0)))
            except:
                self.edit_rating.setValue(series.vote_average or 0)
        else:
            self.edit_rating.setValue(series.vote_average or 0)
        
        self.edit_tmdb_id.setText(str(series.tmdb_id) if series.tmdb_id else '')
        self.edit_genres.setText(', '.join(series.genres))
        
        # 季的详细信息
        episodes = season.get('episodes', [])
        overview = f"【第 {season_num} 季信息】\n\n"
        
        # 如果有nfo信息，显示nfo中的简介
        if season_nfo_info:
            if season_nfo_info.get('plot'):
                overview += f"简介: {season_nfo_info.get('plot', '')}\n\n"
            elif season_nfo_info.get('overview'):
                overview += f"简介: {season_nfo_info.get('overview', '')}\n\n"
        
        overview += f"集数: {len(episodes)} 集\n\n"
        overview += "剧集列表:\n"
        for i, ep in enumerate(episodes, 1):
            if isinstance(ep, dict):
                ep_num = ep.get('episode', i)
                ep_name = ep.get('name', '')
                overview += f"  第 {ep_num} 集: {ep_name}\n"
        
        self.edit_overview.setText(overview)
        
        # 加载图片
        self._load_season_images(series, season)
    
    def update_episode_detail_view(self, series, episode):
        """显示集的详细信息"""
        # 尝试加载本地海报
        poster_loaded = False
        media_dir = os.path.dirname(series.path)
        episode_path = episode.get('path', '')
        episode_name = os.path.basename(episode_path)
        episode_base = os.path.splitext(episode_name)[0]
        episode_dir = os.path.dirname(episode_path)
        
        # 打印调试信息
        print(f"=== 调试信息 ===")
        print(f"电视剧路径: {series.path}")
        print(f"集路径: {episode_path}")
        print(f"集目录: {episode_dir}")
        print(f"集文件名: {episode_name}")
        print(f"集文件基础名: {episode_base}")
        
        # 尝试加载集特定的封面 - 优先从集所在的季文件夹查找
        possible_extensions = ['.jpg', '.png', '.jpeg']
        
        # 尝试在季文件夹中查找 s01e01*.jpg 格式
        print("\n1. 尝试 s01e01*.jpg 格式")
        for ext in possible_extensions:
            pattern = os.path.join(episode_dir, f"s01e{episode.get('episode', 0):02d}*{ext}")
            print(f"  尝试: {pattern}")
            import glob
            matches = glob.glob(pattern)
            if matches:
                print(f"  找到: {matches}")
                ep_poster_path = matches[0]
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 S01E01*.jpg 格式（大写）
        if not poster_loaded:
            print("\n2. 尝试 S01E01*.jpg 格式（大写）")
            for ext in possible_extensions:
                pattern = os.path.join(episode_dir, f"S01E{episode.get('episode', 0):02d}*{ext}")
                print(f"  尝试: {pattern}")
                import glob
                matches = glob.glob(pattern)
                if matches:
                    print(f"  找到: {matches}")
                    ep_poster_path = matches[0]
                    if os.path.exists(ep_poster_path):
                        pixmap = QPixmap(ep_poster_path)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.detail_poster.setPixmap(scaled)
                            poster_loaded = True
                            print(f"  加载成功: {ep_poster_path}")
                            break
        
        # 尝试在季文件夹中查找 电影名字 - s01e01.jpg 格式
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n3. 尝试 {series_name} - s01e01.jpg 格式")
            for ext in possible_extensions:
                pattern = os.path.join(episode_dir, f"{series_name} - s01e{episode.get('episode', 0):02d}*{ext}")
                print(f"  尝试: {pattern}")
                import glob
                matches = glob.glob(pattern)
                if matches:
                    print(f"  找到: {matches}")
                    ep_poster_path = matches[0]
                    if os.path.exists(ep_poster_path):
                        pixmap = QPixmap(ep_poster_path)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.detail_poster.setPixmap(scaled)
                            poster_loaded = True
                            print(f"  加载成功: {ep_poster_path}")
                            break
        
        # 尝试在季文件夹中查找 电影名字 - S01E01.jpg 格式（大写）
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n4. 尝试 {series_name} - S01E01.jpg 格式（大写）")
            for ext in possible_extensions:
                pattern = os.path.join(episode_dir, f"{series_name} - S01E{episode.get('episode', 0):02d}*{ext}")
                print(f"  尝试: {pattern}")
                import glob
                matches = glob.glob(pattern)
                if matches:
                    print(f"  找到: {matches}")
                    ep_poster_path = matches[0]
                    if os.path.exists(ep_poster_path):
                        pixmap = QPixmap(ep_poster_path)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.detail_poster.setPixmap(scaled)
                            poster_loaded = True
                            print(f"  加载成功: {ep_poster_path}")
                            break
        
        # 尝试在季文件夹中查找 电影名字 - E01.jpg 格式
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n5. 尝试 {series_name} - E01.jpg 格式")
            for ext in possible_extensions:
                pattern = os.path.join(episode_dir, f"{series_name} - E{episode.get('episode', 0):02d}*{ext}")
                print(f"  尝试: {pattern}")
                import glob
                matches = glob.glob(pattern)
                if matches:
                    print(f"  找到: {matches}")
                    ep_poster_path = matches[0]
                    if os.path.exists(ep_poster_path):
                        pixmap = QPixmap(ep_poster_path)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.detail_poster.setPixmap(scaled)
                            poster_loaded = True
                            print(f"  加载成功: {ep_poster_path}")
                            break
        
        # 尝试在季文件夹中查找 电影名字 - 第 1 集.jpg 格式
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n6. 尝试 {series_name} - 第 1 集.jpg 格式")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"{series_name} - 第 {episode.get('episode', 0)} 集{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找集文件同名的jpg
        if not poster_loaded:
            print("\n7. 尝试集文件同名的jpg")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"{episode_base}{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 电视剧名_S01E01_第 1 集-thumb.jpg 格式
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n8. 尝试 {series_name}_S01E01_第 1 集-thumb.jpg 格式")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"{series_name}_S01E{episode.get('episode', 0):02d}_第 {episode.get('episode', 0)} 集-thumb{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 电视剧名_S01E01_第 1 集.jpg 格式（无thumb）
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n9. 尝试 {series_name}_S01E01_第 1 集.jpg 格式（无thumb）")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"{series_name}_S01E{episode.get('episode', 0):02d}_第 {episode.get('episode', 0)} 集{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 S01E01-thumb.jpg 格式
        if not poster_loaded:
            print("\n10. 尝试 S01E01-thumb.jpg 格式")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"S01E{episode.get('episode', 0):02d}-thumb{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 S01E01 thumb.jpg 格式（空格）
        if not poster_loaded:
            print("\n11. 尝试 S01E01 thumb.jpg 格式（空格）")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"S01E{episode.get('episode', 0):02d} thumb{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试在季文件夹中查找 E01-thumb.jpg 格式
        if not poster_loaded:
            print("\n12. 尝试 E01-thumb.jpg 格式")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(episode_dir, f"E{episode.get('episode', 0):02d}-thumb{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 尝试 电影名字 - s01e01.jpg 格式（在电视剧根目录）
        if not poster_loaded:
            series_name = series.title or series.name
            print(f"\n13. 尝试 {series_name} - s01e01.jpg 格式（在电视剧根目录）")
            for ext in possible_extensions:
                ep_poster_path = os.path.join(media_dir, f"{series_name} - {episode_base}{ext}")
                print(f"  尝试: {ep_poster_path}")
                if os.path.exists(ep_poster_path):
                    pixmap = QPixmap(ep_poster_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.detail_poster.setPixmap(scaled)
                        poster_loaded = True
                        print(f"  加载成功: {ep_poster_path}")
                        break
        
        # 如果没有集封面，尝试加载电视剧封面
        if not poster_loaded and series.poster_path and os.path.exists(series.poster_path):
            print(f"\n14. 尝试加载电视剧封面: {series.poster_path}")
            pixmap = QPixmap(series.poster_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_poster.setPixmap(scaled)
                poster_loaded = True
                print("  加载成功")
        
        if not poster_loaded:
            print("\n15. 没有找到任何封面")
            self.detail_poster.clear()
            self.detail_poster.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        
        # 加载集的nfo信息
        print("\n=== 加载NFO信息 ===")
        episode_nfo_info = None
        episode_nfo_path = episode.get('nfo_path')
        print(f"NFO路径: {episode_nfo_path}")
        
        if episode_nfo_path:
            if os.path.exists(episode_nfo_path):
                print(f"NFO文件存在: {episode_nfo_path}")
                episode_nfo_info = self._load_nfo_info(episode_nfo_path)
                print(f"NFO信息: {episode_nfo_info}")
            else:
                print(f"NFO文件不存在: {episode_nfo_path}")
        else:
            print("没有NFO路径")
        
        # 尝试在季文件夹中查找NFO文件
        if not episode_nfo_info:
            print("\n尝试在季文件夹中查找NFO文件")
            for ext in ['.nfo', '.NFO']:
                # 尝试与集文件同名的NFO
                nfo_path = os.path.join(episode_dir, f"{episode_base}{ext}")
                print(f"  尝试: {nfo_path}")
                if os.path.exists(nfo_path):
                    print(f"  找到NFO文件: {nfo_path}")
                    episode_nfo_info = self._load_nfo_info(nfo_path)
                    print(f"  NFO信息: {episode_nfo_info}")
                    break
                
                # 尝试 s01e01.nfo 格式
                nfo_path = os.path.join(episode_dir, f"s01e{episode.get('episode', 0):02d}{ext}")
                print(f"  尝试: {nfo_path}")
                if os.path.exists(nfo_path):
                    print(f"  找到NFO文件: {nfo_path}")
                    episode_nfo_info = self._load_nfo_info(nfo_path)
                    print(f"  NFO信息: {episode_nfo_info}")
                    break
                
                # 尝试 S01E01.nfo 格式
                nfo_path = os.path.join(episode_dir, f"S01E{episode.get('episode', 0):02d}{ext}")
                print(f"  尝试: {nfo_path}")
                if os.path.exists(nfo_path):
                    print(f"  找到NFO文件: {nfo_path}")
                    episode_nfo_info = self._load_nfo_info(nfo_path)
                    print(f"  NFO信息: {episode_nfo_info}")
                    break
        
        # 更新编辑组件
        episode_num = episode.get('episode', 0)
        episode_name = episode.get('name', '')
        episode_path = episode.get('path', '')
        
        if episode_nfo_info and episode_nfo_info.get('title'):
            self.edit_title.setText(episode_nfo_info.get('title', ''))
        else:
            self.edit_title.setText(f"{series.title or series.name} - 第 {episode_num} 集")
        
        self.edit_original_title.setText('')
        self.edit_year.setText(series.year or '')
        self.edit_type.setCurrentIndex(1)  # 电视剧
        
        if episode_nfo_info and episode_nfo_info.get('rating'):
            try:
                self.edit_rating.setValue(float(episode_nfo_info.get('rating', 0)))
            except:
                self.edit_rating.setValue(0)
        else:
            self.edit_rating.setValue(0)
        
        self.edit_tmdb_id.setText(str(series.tmdb_id) if series.tmdb_id else '')
        self.edit_genres.setText(', '.join(series.genres))
        
        # 集的详细信息
        overview = f"【第 {episode_num} 集信息】\n\n"
        
        # 如果有nfo信息，显示nfo中的简介
        if episode_nfo_info:
            if episode_nfo_info.get('plot'):
                overview += f"简介: {episode_nfo_info.get('plot', '')}\n\n"
            elif episode_nfo_info.get('overview'):
                overview += f"简介: {episode_nfo_info.get('overview', '')}\n\n"
            if episode_nfo_info.get('aired'):
                overview += f"播出日期: {episode_nfo_info.get('aired', '')}\n\n"
        
        overview += f"文件名: {episode_name}\n\n"
        overview += f"路径: {episode_path}\n\n"
        overview += f"所属电视剧: {series.title or series.name}\n"
        
        self.edit_overview.setText(overview)
        
        # 加载图片
        self._load_episode_images(series, episode)
    
    def search_tmdb(self):
        try:
            print("=== search_tmdb 被调用 ===")
            
            if not hasattr(self, 'search_input'):
                print("错误: search_input 不存在")
                return
            
            query = self.search_input.text().strip()
            print(f"搜索关键词: {query}")
            
            if not query:
                print("警告: 搜索关键词为空")
                QMessageBox.warning(self, '警告', '请输入搜索关键词')
                return
            
            if not hasattr(self, 'search_type_combo'):
                print("错误: search_type_combo 不存在")
                return
            
            search_type_map = {'全部': 'multi', '电影': 'movie', '电视剧': 'tv', '合集': 'collection'}
            search_type = search_type_map.get(self.search_type_combo.currentText(), 'multi')
            print(f"搜索类型: {search_type}")
            
            if not hasattr(self, 'api'):
                print("错误: api 不存在")
                return
            
            print(f"创建搜索线程: query={query}, type={search_type}")
            self.search_thread = SearchThread(self.api, query, search_type)
            self.search_thread.result_ready.connect(self.on_search_results)
            self.search_thread.start()
            
            print("切换到搜索结果标签页")
            self.tabs.setCurrentIndex(1)
        except Exception as e:
            print(f"搜索错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'搜索失败: {str(e)}')
    
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
        if not current_item:
            QMessageBox.warning(self, '警告', '请先选择一个搜索结果')
            return
        
        result: MovieInfo = current_item.data(Qt.UserRole)
        
        # 判断是电影还是电视剧
        if self.current_series:
            # 更新电视剧信息
            self.current_series.title = result.title
            self.current_series.year = result.year
            self.current_series.overview = result.overview
            self.current_series.vote_average = result.vote_average
            self.current_series.tmdb_id = result.id
            self.current_series.media_type = result.media_type
            self.current_series.info['poster_path'] = result.poster_path
            self.current_series.info['backdrop_path'] = result.backdrop_path
            self.current_series.info['original_title'] = result.original_title
            self.current_series.matched = True
            
            self.update_series_detail_view(self.current_series)
            QMessageBox.information(self, '成功', '已应用搜索结果到电视剧')
        elif self.current_movie:
            # 更新电影信息
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
            QMessageBox.information(self, '成功', '已应用搜索结果到电影')
        else:
            QMessageBox.warning(self, '警告', '请先选择一个本地电影或电视剧')
    
    def apply_search_result_and_save(self, item):
        try:
            result: MovieInfo = item.data(Qt.UserRole)
            
            # 判断是电影还是电视剧
            if self.current_series:
                # 显示进度对话框
                self.show_progress_dialog('正在处理...', 100)
                self.progress_label.setText('正在更新电视剧信息...')
                QApplication.processEvents()
                
                # 更新电视剧信息
                self.current_series.title = result.title
                self.current_series.year = result.year
                self.current_series.overview = result.overview
                self.current_series.vote_average = result.vote_average
                self.current_series.tmdb_id = result.id
                self.current_series.media_type = result.media_type
                self.current_series.info['poster_path'] = result.poster_path
                self.current_series.info['backdrop_path'] = result.backdrop_path
                self.current_series.info['original_title'] = result.original_title
                self.current_series.matched = True
                
                self.progress_label.setText('正在更新视图...')
                QApplication.processEvents()
                self.update_series_detail_view(self.current_series)
                
                info = {
                    'title': self.current_series.title,
                    'original_title': self.current_series.info.get('original_title', ''),
                    'year': self.current_series.year,
                    'overview': self.current_series.overview,
                    'vote_average': self.current_series.vote_average,
                    'tmdb_id': self.current_series.tmdb_id,
                    'media_type': self.current_series.media_type,
                    'genres': self.current_series.genres,
                    'poster_path': self.current_series.info.get('poster_path', ''),
                    'backdrop_path': self.current_series.info.get('backdrop_path', ''),
                }
                
                self.progress_label.setText('正在创建同名目录...')
                QApplication.processEvents()
                
                # 获取电影/电视剧文件所在目录
                base_directory = os.path.dirname(self.current_series.path) if self.current_series.path else os.getcwd()
                
                # 创建同名目录（电影名（年份））
                title = self.current_series.title or 'Unknown'
                year = f" ({self.current_series.year})" if self.current_series.year else ""
                folder_name = f"{title}{year}"
                image_directory = os.path.join(base_directory, folder_name)
                
                # 如果同名目录不存在，则创建
                if not os.path.exists(image_directory):
                    os.makedirs(image_directory)
                
                self.progress_label.setText('正在保存NFO文件...')
                QApplication.processEvents()
                
                # 保存NFO文件到同名目录
                nfo_path = self.scanner.save_nfo(self.current_series, info, image_directory)
                if nfo_path:
                    
                    self.progress_label.setText('正在下载图片...')
                    self.progress_bar.setValue(0)
                    QApplication.processEvents()
                    
                    # 启动图片下载线程
                    self.image_download_thread = ImageDownloadThread(self.api, self.current_series, image_directory)
                    self.image_download_thread.progress_update.connect(self.on_image_download_progress)
                    self.image_download_thread.download_complete.connect(lambda success, msg: self.on_image_download_complete(success, msg, 'series', nfo_path))
                    self.image_download_thread.start()
                else:
                    self.close_progress_dialog()
                    QMessageBox.warning(self, '失败', '保存 NFO 文件失败')
            elif self.current_movie:
                # 显示进度对话框
                self.show_progress_dialog('正在处理...', 100)
                self.progress_label.setText('正在更新电影信息...')
                QApplication.processEvents()
                
                # 更新电影信息
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
                
                self.progress_label.setText('正在更新视图...')
                QApplication.processEvents()
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
                
                self.progress_label.setText('正在创建同名目录...')
                QApplication.processEvents()
                
                # 获取电影/电视剧文件所在目录
                base_directory = os.path.dirname(self.current_movie.path) if self.current_movie.path else os.getcwd()
                
                # 创建同名目录（电影名（年份））
                title = self.current_movie.title or 'Unknown'
                year = f" ({self.current_movie.year})" if self.current_movie.year else ""
                folder_name = f"{title}{year}"
                image_directory = os.path.join(base_directory, folder_name)
                
                # 如果同名目录不存在，则创建
                if not os.path.exists(image_directory):
                    os.makedirs(image_directory)
                
                self.progress_label.setText('正在保存NFO文件...')
                QApplication.processEvents()
                
                # 保存NFO文件到同名目录
                nfo_path = self.scanner.save_nfo(self.current_movie, info, image_directory)
                if nfo_path:
                    
                    self.progress_label.setText('正在下载图片...')
                    self.progress_bar.setValue(0)
                    QApplication.processEvents()
                    
                    # 启动图片下载线程
                    self.image_download_thread = ImageDownloadThread(self.api, self.current_movie, image_directory)
                    self.image_download_thread.progress_update.connect(self.on_image_download_progress)
                    self.image_download_thread.download_complete.connect(lambda success, msg: self.on_image_download_complete(success, msg, 'movie', nfo_path))
                    self.image_download_thread.start()
                else:
                    self.close_progress_dialog()
                    QMessageBox.warning(self, '失败', '保存 NFO 文件失败')
            else:
                QMessageBox.warning(self, '警告', '请先选择一个本地电影或电视剧')
        except Exception as e:
            self.close_progress_dialog()
            print(f"应用搜索结果错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, '错误', f'应用搜索结果时发生错误:\n{str(e)}')
    
    def on_image_download_progress(self, progress: int, message: str):
        """图片下载进度更新"""
        try:
            if not hasattr(self, 'progress_dialog') or not self.progress_dialog:
                return
            
            if not self.progress_dialog.isVisible():
                return
                
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setValue(progress)
            if hasattr(self, 'progress_label') and self.progress_label:
                self.progress_label.setText(message)
            QApplication.processEvents()
        except Exception as e:
            print(f"更新进度条错误: {e}")
            import traceback
            traceback.print_exc()
    
    def on_image_download_complete(self, success: bool, message: str, media_type: str, nfo_path: str):
        """图片下载完成"""
        try:
            print("=== on_image_download_complete 被调用 ===")
            print(f"success: {success}, media_type: {media_type}")
            
            # 确保进度对话框已关闭
            try:
                if hasattr(self, 'close_progress_dialog'):
                    self.close_progress_dialog()
            except Exception as close_error:
                print(f"关闭进度对话框错误: {close_error}")
            
            if success:
                try:
                    if media_type == 'series':
                        # 电视剧图片下载完成，开始下载集剧照
                        print("电视剧图片下载完成，开始下载集剧照")
                        
                        if hasattr(self, 'current_series') and self.current_series:
                            # 显示进度对话框
                            self.show_progress_dialog('正在下载集剧照...', 100)
                            self.progress_label.setText('正在下载集剧照...')
                            QApplication.processEvents()
                            
                            # 获取电视剧文件所在目录
                            base_directory = os.path.dirname(self.current_series.path) if self.current_series.path else os.getcwd()
                            
                            # 启动集剧照下载线程
                            print("启动集剧照下载线程")
                            self.episode_still_thread = EpisodeStillDownloadThread(self.api, self.current_series, base_directory)
                            self.episode_still_thread.progress_update.connect(self.on_episode_still_progress)
                            self.episode_still_thread.download_complete.connect(lambda success, msg: self.on_episode_still_complete(success, msg, nfo_path))
                            self.episode_still_thread.start()
                    else:
                        # 电影图片下载完成
                        if hasattr(self, 'current_movie') and self.current_movie:
                            if hasattr(self, 'update_detail_view'):
                                self.update_detail_view(self.current_movie)
                        QMessageBox.information(self, '成功', f'已替换封面和NFO文件: {nfo_path}')
                except Exception as update_error:
                    print(f"更新视图错误: {update_error}")
                    QMessageBox.warning(self, '警告', f'更新视图时发生错误: {update_error}')
            else:
                QMessageBox.warning(self, '失败', f'下载图片失败: {message}')
        except Exception as e:
            print(f"图片下载完成处理错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'处理完成时发生错误: {str(e)}')
    
    def on_episode_still_progress(self, progress: int, message: str):
        """集剧照下载进度更新"""
        try:
            if not hasattr(self, 'progress_dialog') or not self.progress_dialog:
                return
            
            if not self.progress_dialog.isVisible():
                return
                
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setValue(progress)
            if hasattr(self, 'progress_label') and self.progress_label:
                self.progress_label.setText(message)
            QApplication.processEvents()
        except Exception as e:
            print(f"更新集剧照进度条错误: {e}")
            import traceback
            traceback.print_exc()
    
    def on_episode_still_complete(self, success: bool, message: str, nfo_path: str):
        """集剧照下载完成"""
        try:
            print("=== on_episode_still_complete 被调用 ===")
            
            # 确保进度对话框已关闭
            try:
                if hasattr(self, 'close_progress_dialog'):
                    self.close_progress_dialog()
            except Exception as close_error:
                print(f"关闭进度对话框错误: {close_error}")
            
            if success:
                try:
                    if hasattr(self, 'current_series') and self.current_series:
                        if hasattr(self, 'update_series_detail_view'):
                            self.update_series_detail_view(self.current_series)
                    QMessageBox.information(self, '成功', f'已替换封面、NFO文件和集剧照: {nfo_path}\n{message}')
                except Exception as update_error:
                    print(f"更新视图错误: {update_error}")
                    QMessageBox.warning(self, '警告', f'更新视图时发生错误: {update_error}')
            else:
                QMessageBox.warning(self, '失败', f'下载集剧照失败: {message}')
        except Exception as e:
            print(f"集剧照下载完成处理错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'处理完成时发生错误: {str(e)}')
    
    def show_context_menu(self, position):
        try:
            print("=== show_context_menu 被调用 ===")
            print(f"position: {position}")
            
            # 检查媒体树是否存在
            if not hasattr(self, 'media_tree') or not self.media_tree:
                print("错误: media_tree 不存在")
                return
                
            item = self.media_tree.itemAt(position)
            print(f"item: {item}")
            
            if not item:
                print("警告: 没有找到item")
                return
            
            data = item.data(0, Qt.UserRole)
            print(f"data: {data}")
            
            if not data:
                print("警告: item没有data")
                return
            
            print(f"data type: {data.get('type')}")
            
            try:
                menu = QMenu()
                print("菜单创建成功")
            except Exception as menu_error:
                print(f"创建菜单错误: {menu_error}")
                return
            
            action = None
            try:
                if data.get('type') == 'movie':
                    # 电影右键菜单
                    print("创建电影右键菜单")
                    scrape_action = menu.addAction('🔍 快捷刮削')
                    rename_save_action = menu.addAction('💾 改名保存')
                    delete_action = menu.addAction('🗑️ 删除')
                    action = menu.exec_(self.media_tree.viewport().mapToGlobal(position))
                    print(f"用户选择的action: {action}")
                    
                    if action == scrape_action:
                        print("用户选择了快捷刮削")
                        self.current_movie = data.get('data')
                        print(f"设置current_movie: {self.current_movie}")
                        print("准备调用search_current_movie")
                        self.search_current_movie()
                    elif action == rename_save_action:
                        print("用户选择了改名保存")
                        self.current_movie = data.get('data')
                        self.rename_save_current_movie()
                    elif action == delete_action:
                        print("用户选择了删除")
                        self.current_movie = data.get('data')
                        self.delete_current_movie()
                elif data.get('type') == 'series':
                    # 电视剧右键菜单
                    print("创建电视剧右键菜单")
                    scrape_action = menu.addAction('🔍 快捷刮削')
                    rename_save_action = menu.addAction('💾 改名保存')
                    delete_action = menu.addAction('🗑️ 删除')
                    action = menu.exec_(self.media_tree.viewport().mapToGlobal(position))
                    print(f"用户选择的action: {action}")
                    
                    if action == scrape_action:
                        print("用户选择了快捷刮削")
                        self.current_series = data.get('data')
                        print(f"设置current_series: {self.current_series}")
                        print("准备调用search_current_movie")
                        self.search_current_movie()
                    elif action == rename_save_action:
                        print("用户选择了改名保存")
                        self.current_series = data.get('data')
                        self.rename_save_current_series()
                    elif action == delete_action:
                        print("用户选择了删除")
                        self.current_series = data.get('data')
                        self.delete_current_series()
                elif data.get('type') == 'season':
                    # 季右键菜单
                    print("创建季右键菜单")
                    scrape_action = menu.addAction('🔍 快捷刮削')
                    action = menu.exec_(self.media_tree.viewport().mapToGlobal(position))
                    print(f"用户选择的action: {action}")
                    
                    if action == scrape_action:
                        print("用户选择了快捷刮削")
                        self.current_series = data.get('series')
                        print(f"设置current_series: {self.current_series}")
                        print("准备调用search_current_movie")
                        self.search_current_movie()
                elif data.get('type') == 'episode':
                    # 集右键菜单
                    print("创建集右键菜单")
                    scrape_action = menu.addAction('🔍 快捷刮削')
                    action = menu.exec_(self.media_tree.viewport().mapToGlobal(position))
                    print(f"用户选择的action: {action}")
                    
                    if action == scrape_action:
                        print("用户选择了快捷刮削")
                        self.current_series = data.get('series')
                        self.current_episode = data.get('data')
                        print(f"设置current_series: {self.current_series}")
                        print(f"设置current_episode: {self.current_episode}")
                        print("准备调用search_current_movie")
                        self.search_current_movie()
            except Exception as action_error:
                print(f"菜单操作错误: {action_error}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"右键菜单错误: {e}")
            import traceback
            traceback.print_exc()
            try:
                QMessageBox.warning(self, '错误', f'右键菜单出错: {e}')
            except:
                pass
    
    def rename_save_current_movie(self):
        if not hasattr(self, 'current_movie') or not self.current_movie:
            QMessageBox.warning(self, '警告', '请先选择一个电影')
            return
        
        # 生成标准名称
        standard_name = f"{self.current_movie.title} ({self.current_movie.year})"
        
        # 获取原文件路径
        original_path = self.current_movie.path
        if not original_path or not os.path.exists(original_path):
            QMessageBox.warning(self, '警告', '原文件不存在')
            return
        
        # 获取文件扩展名
        ext = os.path.splitext(original_path)[1]
        
        # 生成新路径
        new_path = os.path.join(os.path.dirname(original_path), f"{standard_name}{ext}")
        
        # 重命名文件
        try:
            os.rename(original_path, new_path)
            self.current_movie.path = new_path
            if hasattr(self, 'save_current_movie'):
                self.save_current_movie()
            QMessageBox.information(self, '成功', f'已重命名为: {standard_name}{ext}')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'重命名失败: {e}')
    
    def rename_save_current_series(self):
        if not hasattr(self, 'current_series') or not self.current_series:
            QMessageBox.warning(self, '警告', '请先选择一个电视剧')
            return
        
        # 生成标准名称
        standard_name = f"{self.current_series.title} ({self.current_series.year})"
        
        # 获取原文件路径
        original_path = self.current_series.path
        if not original_path or not os.path.exists(original_path):
            QMessageBox.warning(self, '警告', '原文件不存在')
            return
        
        # 生成新路径
        new_path = os.path.join(os.path.dirname(original_path), standard_name)
        
        # 重命名文件
        try:
            os.rename(original_path, new_path)
            self.current_series.path = new_path
            if hasattr(self, 'save_current_movie'):
                self.save_current_movie()
            QMessageBox.information(self, '成功', f'已重命名为: {standard_name}')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'重命名失败: {e}')
    
    def rename_save_all(self):
        if not self.local_movies:
            QMessageBox.warning(self, '警告', '没有电影可以重命名')
            return
        
        success_count = 0
        error_count = 0
        
        for movie in self.local_movies:
            if not movie.matched:
                continue
            
            # 生成标准名称
            standard_name = f"{movie.title} ({movie.year})"
            
            # 获取原文件路径
            original_path = movie.path
            if not original_path or not os.path.exists(original_path):
                error_count += 1
                continue
            
            # 获取文件扩展名
            ext = os.path.splitext(original_path)[1]
            
            # 生成新路径
            new_path = os.path.join(os.path.dirname(original_path), f"{standard_name}{ext}")
            
            # 重命名文件
            try:
                os.rename(original_path, new_path)
                movie.path = new_path
                success_count += 1
            except Exception as e:
                error_count += 1
        
        QMessageBox.information(self, '完成', f'成功重命名 {success_count} 个电影，失败 {error_count} 个')
    
    def delete_current_movie(self):
        if not self.current_movie:
            QMessageBox.warning(self, '警告', '请先选择一个电影')
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, 
            '确认删除', 
            f'确定要删除电影 "{self.current_movie.title}" 吗？\n\n将删除：\n1. 电影文件\n2. 同名文件夹（{self.current_movie.title} ({self.current_movie.year})）\n\n此操作不可恢复！',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            deleted_items = []
            
            # 删除电影文件
            if self.current_movie.path and os.path.exists(self.current_movie.path):
                os.remove(self.current_movie.path)
                deleted_items.append(f"电影文件: {os.path.basename(self.current_movie.path)}")
            
            # 删除同名文件夹
            if self.current_movie.path:
                base_directory = os.path.dirname(self.current_movie.path)
                title = self.current_movie.title or 'Unknown'
                year = f" ({self.current_movie.year})" if self.current_movie.year else ""
                folder_name = f"{title}{year}"
                folder_path = os.path.join(base_directory, folder_name)
                
                if os.path.exists(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)
                    deleted_items.append(f"同名文件夹: {folder_name}")
            
            # 删除NFO文件
            if self.current_movie.nfo_path and os.path.exists(self.current_movie.nfo_path):
                os.remove(self.current_movie.nfo_path)
                deleted_items.append(f"NFO文件: {os.path.basename(self.current_movie.nfo_path)}")
            
            # 从列表中移除
            if self.current_movie in self.local_movies:
                self.local_movies.remove(self.current_movie)
            
            # 刷新树视图
            self.refresh_media_tree()
            
            # 清空详情视图
            self.clear_detail_view()
            self.current_movie = None
            
            # 显示删除结果
            if deleted_items:
                message = "已删除以下项目：\n\n" + "\n".join(deleted_items)
                QMessageBox.information(self, '删除成功', message)
            else:
                QMessageBox.information(self, '删除完成', '没有找到需要删除的文件')
                
        except Exception as e:
            print(f"删除电影错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, '删除失败', f'删除电影时发生错误:\n{str(e)}')
    
    def delete_current_series(self):
        if not self.current_series:
            QMessageBox.warning(self, '警告', '请先选择一个电视剧')
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, 
            '确认删除', 
            f'确定要删除电视剧 "{self.current_series.title}" 吗？\n\n将删除：\n1. 电视剧文件夹\n2. 同名文件夹（{self.current_series.title} ({self.current_series.year})）\n\n此操作不可恢复！',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            deleted_items = []
            
            # 删除电视剧文件夹
            if self.current_series.path and os.path.exists(self.current_series.path):
                import shutil
                shutil.rmtree(self.current_series.path)
                deleted_items.append(f"电视剧文件夹: {os.path.basename(self.current_series.path)}")
            
            # 删除同名文件夹
            if self.current_series.path:
                base_directory = os.path.dirname(self.current_series.path)
                title = self.current_series.title or 'Unknown'
                year = f" ({self.current_series.year})" if self.current_series.year else ""
                folder_name = f"{title}{year}"
                folder_path = os.path.join(base_directory, folder_name)
                
                if os.path.exists(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)
                    deleted_items.append(f"同名文件夹: {folder_name}")
            
            # 从列表中移除
            if self.current_series in self.local_series:
                self.local_series.remove(self.current_series)
            
            # 刷新树视图
            self.refresh_media_tree()
            
            # 清空详情视图
            self.clear_series_detail_view()
            self.current_series = None
            
            # 显示删除结果
            if deleted_items:
                message = "已删除以下项目：\n\n" + "\n".join(deleted_items)
                QMessageBox.information(self, '删除成功', message)
            else:
                QMessageBox.information(self, '删除完成', '没有找到需要删除的文件')
                
        except Exception as e:
            print(f"删除电视剧错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, '删除失败', f'删除电视剧时发生错误:\n{str(e)}')
    
    def refresh_media_tree(self):
        self.media_tree.clear()
        
        # 重新添加电影
        for movie in self.local_movies:
            self._add_movie_to_tree(movie)
        
        # 重新添加电视剧
        for series in self.local_series:
            self._add_series_to_tree(series)
    
    def search_current_movie(self):
        try:
            print("=== search_current_movie 被调用 ===")
            print(f"current_series: {hasattr(self, 'current_series')} - {getattr(self, 'current_series', None)}")
            print(f"current_movie: {hasattr(self, 'current_movie')} - {getattr(self, 'current_movie', None)}")
            
            # 判断是电影还是电视剧
            if hasattr(self, 'current_series') and self.current_series:
                # 处理电视剧
                title = getattr(self.current_series, 'title', None) or getattr(self.current_series, 'name', '')
                print(f"电视剧标题: {title}")
                
                if hasattr(self, 'search_input') and self.search_input:
                    self.search_input.setText(title)
                    print(f"已设置搜索框文本: {title}")
                else:
                    print("警告: search_input 不存在")
                
                if hasattr(self, 'search_tmdb'):
                    print("调用 search_tmdb")
                    self.search_tmdb()
                else:
                    print("警告: search_tmdb 方法不存在")
                    
            elif hasattr(self, 'current_movie') and self.current_movie:
                # 处理电影
                title = getattr(self.current_movie, 'title', None) or getattr(self.current_movie, 'name', '')
                print(f"电影标题: {title}")
                
                if hasattr(self, 'search_input') and self.search_input:
                    self.search_input.setText(title)
                    print(f"已设置搜索框文本: {title}")
                else:
                    print("警告: search_input 不存在")
                
                if hasattr(self, 'search_tmdb'):
                    print("调用 search_tmdb")
                    self.search_tmdb()
                else:
                    print("警告: search_tmdb 方法不存在")
            else:
                print("警告: 没有选择电影或电视剧")
                QMessageBox.warning(self, '警告', '请先选择一个电影或电视剧')
        except Exception as e:
            print(f"搜索当前电影/电视剧错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'搜索失败: {str(e)}')
    
    def save_current_movie(self):
        try:
            print("=== save_current_movie 被调用 ===")
            
            if not hasattr(self, 'current_movie') or not self.current_movie:
                print("警告: current_movie 不存在")
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
            
            print(f"保存NFO文件: {self.current_movie.title}")
            nfo_path = self.scanner.save_nfo(self.current_movie, info)
            
            if nfo_path:
                print(f"NFO文件保存成功: {nfo_path}")
                
                # 获取电影文件所在目录
                base_directory = os.path.dirname(self.current_movie.path) if self.current_movie.path else os.getcwd()
                
                # 创建同名目录（电影名（年份））
                title = self.current_movie.title or 'Unknown'
                year = f" ({self.current_movie.year})" if self.current_movie.year else ""
                folder_name = f"{title}{year}"
                image_directory = os.path.join(base_directory, folder_name)
                
                # 如果同名目录不存在，则创建
                if not os.path.exists(image_directory):
                    os.makedirs(image_directory)
                    print(f"创建同名目录: {image_directory}")
                
                # 显示进度对话框
                self.show_progress_dialog('正在下载图片...', 100)
                self.progress_label.setText('正在下载图片...')
                QApplication.processEvents()
                
                # 启动图片下载线程
                print("启动图片下载线程")
                self.image_download_thread = ImageDownloadThread(self.api, self.current_movie, image_directory)
                self.image_download_thread.progress_update.connect(self.on_image_download_progress)
                self.image_download_thread.download_complete.connect(lambda success, msg: self.on_save_movie_complete(success, msg, nfo_path))
                self.image_download_thread.start()
            else:
                print("NFO文件保存失败")
                QMessageBox.warning(self, '失败', '保存 NFO 文件失败')
        except Exception as e:
            print(f"保存电影错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'保存失败: {str(e)}')
    
    def on_save_movie_complete(self, success: bool, message: str, nfo_path: str):
        """保存电影完成"""
        try:
            print("=== on_save_movie_complete 被调用 ===")
            
            # 确保进度对话框已关闭
            try:
                if hasattr(self, 'close_progress_dialog'):
                    self.close_progress_dialog()
            except Exception as close_error:
                print(f"关闭进度对话框错误: {close_error}")
            
            if success:
                try:
                    if hasattr(self, 'current_movie') and self.current_movie:
                        if hasattr(self, 'update_detail_view'):
                            self.update_detail_view(self.current_movie)
                    QMessageBox.information(self, '成功', f'NFO 文件和图片已保存: {nfo_path}')
                except Exception as update_error:
                    print(f"更新视图错误: {update_error}")
                    QMessageBox.warning(self, '警告', f'更新视图时发生错误: {update_error}')
            else:
                QMessageBox.warning(self, '失败', f'下载图片失败: {message}')
        except Exception as e:
            print(f"保存完成处理错误: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, '错误', f'处理完成时发生错误: {str(e)}')
    
    def save_edited_info(self):
        if not self.current_movie:
            return
        
        self.current_movie.title = self.edit_title.text()
        self.current_movie.info['original_title'] = self.edit_original_title.text()
        self.current_movie.year = self.edit_year.text()
        
        old_media_type = self.current_movie.media_type
        new_media_type = 'movie' if self.edit_type.currentIndex() == 0 else 'tv'
        self.current_movie.media_type = new_media_type
        
        self.current_movie.vote_average = self.edit_rating.value()
        self.current_movie.tmdb_id = int(self.edit_tmdb_id.text()) if self.edit_tmdb_id.text() else None
        self.current_movie.genres = [g.strip() for g in self.edit_genres.text().split(',') if g.strip()]
        self.current_movie.overview = self.edit_overview.toPlainText()
        
        # 更新树形列表中的显示
        if hasattr(self, 'media_tree') and self.media_tree:
            selected_items = self.media_tree.selectedItems()
            if selected_items:
                item = selected_items[0]
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'movie':
                    # 更新标题显示
                    title = self.current_movie.title or self.current_movie.name
                    year = self.current_movie.year or ''
                    if year:
                        display_name = f"{title} ({year})"
                    else:
                        display_name = title
                    item.setText(0, display_name)
                    item.setText(1, year)
                    
                    # 更新类型显示
                    if old_media_type != new_media_type:
                        if new_media_type == 'movie':
                            item.setText(2, '电影')
                        else:
                            item.setText(2, '电视剧')
        
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
        
        self.media_tree.clear()
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
        
        version = QLabel('版本: 1.1.0')
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
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
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
    
    def show_progress_dialog(self, title: str, total: int = 0):
        """显示进度对话框"""
        self._create_progress_dialog(title)
        if total > 0:
            self.progress_bar.setRange(0, 100)
        self.progress_dialog.show()
        QApplication.processEvents()
    
    def close_progress_dialog(self):
        """关闭进度对话框"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
    
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
        
        # 从媒体树获取当前选中的电影
        selected_items = self.media_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先在本地电影列表中选择电影')
            return
        
        movies_to_add = []
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'movie':
                movie = data.get('data')
                if movie and movie not in movies_to_add:
                    movies_to_add.append(movie)
        
        if not movies_to_add:
            QMessageBox.warning(self, '警告', '请选择电影类型的项目')
            return
        
        # 添加到分类
        existing_movies = self.categories[self.current_category]
        added_count = 0
        for movie in movies_to_add:
            if movie not in existing_movies:
                existing_movies.append(movie)
                added_count += 1
        
        # 更新电影列表
        self.on_category_selected(self.category_list.currentItem())
        
        if added_count > 0:
            QMessageBox.information(self, '成功', f'已添加 {added_count} 个电影到分类')
        else:
            QMessageBox.information(self, '提示', '选中的电影已在分类中')
    
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
                    
                    # 修改NFO文件内容
                    try:
                        with open(new_nfo_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        import re
                        
                        # 修改title标签内容，去掉 - S01EXX 后缀
                        pattern = r'(<title>)[^<]+(</title>)'
                        replacement = r'\1' + original_name + r'\2'
                        content = re.sub(pattern, replacement, content, count=1)
                        
                        # 将 <movie> 标签转换为 <episodedetails>
                        content = content.replace('<movie>', '<episodedetails>')
                        content = content.replace('</movie>', '</episodedetails>')
                        
                        # 在 <episodedetails> 后添加 season、episode 和 episode_groups 标签
                        episode_details_pattern = r'(<episodedetails>)'
                        season = 1
                        episode = i
                        
                        episode_groups_content = f'''    <season>{season}</season>
    <episode>{episode}</episode>
    <episode_groups>
        <group episode="{episode}" id="AIRED" name="" season="{season}"/>
    </episode_groups>
'''
                        
                        replacement = r'\1\n' + episode_groups_content
                        content = re.sub(episode_details_pattern, replacement, content)
                        
                        with open(new_nfo_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    except Exception as e:
                        print(f"修改NFO文件失败 {new_nfo_path}: {e}")
                    
                    # 保存第一个电影的nfo路径
                    if i == 1:
                        first_movie_nfo_path = new_nfo_path
                else:
                    # 如果原nfo文件不存在，创建一个新的
                    # 提取原nfo文件中的plot内容
                    plot_content = movie.overview or ''
                    # 创建基本的nfo结构，使用episodedetails标签
                    nfo_content = f'''
<?xml version="1.0" encoding="UTF-8"?>
<episodedetails>
    <title>{original_name}</title>
    <year>{movie.year or ''}</year>
    <plot>{plot_content}</plot>
    <season>1</season>
    <episode>{i}</episode>
    <episode_groups>
        <group episode="{i}" id="AIRED" name="" season="1"/>
    </episode_groups>
</episodedetails>
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
