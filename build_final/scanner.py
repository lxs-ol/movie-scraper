import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class LocalSeries:
    path: str
    name: str
    year: Optional[str] = None
    title: Optional[str] = None
    media_type: str = 'tv'
    nfo_path: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    tmdb_id: Optional[int] = None
    overview: Optional[str] = None
    vote_average: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    matched: bool = False
    info: dict = field(default_factory=dict)
    seasons: List[Dict] = field(default_factory=list)

@dataclass
class LocalMovie:
    path: str
    name: str
    year: Optional[str] = None
    title: Optional[str] = None
    media_type: str = 'movie'
    nfo_path: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    tmdb_id: Optional[int] = None
    overview: Optional[str] = None
    vote_average: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    matched: bool = False
    info: dict = field(default_factory=dict)
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None

class LocalMovieScanner:
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.strm'}
    
    def __init__(self):
        self.movies: List[LocalMovie] = []
        self.series: List[LocalSeries] = []
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[LocalMovie]:
        self.movies = []
        directory = Path(directory)
        
        if not directory.exists():
            return []
        
        if recursive:
            self._scan_recursive(directory)
        else:
            self._scan_flat(directory)
        
        return self.movies
    
    def scan_series_directory(self, directory: str, recursive: bool = True) -> List[LocalSeries]:
        self.series = []
        directory = Path(directory)
        
        if not directory.exists():
            return []
        
        if recursive:
            self._scan_series_recursive(directory)
        else:
            self._scan_series_flat(directory)
        
        return self.series
    
    def scan_directory_iter(self, directory: str, recursive: bool = True):
        """迭代器版本的扫描方法，用于实时加载"""
        directory = Path(directory)
        
        if not directory.exists():
            return
        
        if recursive:
            for item in directory.iterdir():
                if item.is_dir():
                    movie = self._process_movie_folder_yield(item)
                    if movie:
                        yield movie
                elif item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                    movie = self._process_video_file_yield(item)
                    if movie:
                        yield movie
        else:
            for item in directory.iterdir():
                if item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                    movie = self._process_video_file_yield(item)
                    if movie:
                        yield movie
    
    def scan_series_directory_iter(self, directory: str, recursive: bool = True):
        """迭代器版本的扫描方法，用于实时加载"""
        directory = Path(directory)
        
        if not directory.exists():
            return
        
        if recursive:
            for item in directory.iterdir():
                if item.is_dir():
                    series = self._process_series_folder_yield(item)
                    if series:
                        yield series
        else:
            for item in directory.iterdir():
                if item.is_dir():
                    series = self._process_series_folder_yield(item)
                    if series:
                        yield series
    
    def _process_movie_folder_yield(self, directory: Path):
        """处理电影文件夹并返回电影对象"""
        video_files = []
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                video_files.append(item)
        
        if not video_files:
            return None
        
        main_video = video_files[0]
        return self._create_movie_from_video(main_video, directory)
    
    def _process_video_file_yield(self, video_file: Path):
        """处理视频文件并返回电影对象"""
        return self._create_movie_from_video(video_file, video_file.parent)
    
    def _create_movie_from_video(self, video_file: Path, directory: Path):
        """从视频文件创建电影对象"""
        movie = LocalMovie(
            path=str(video_file),
            name=video_file.stem
        )
        
        nfo_files = list(directory.glob("*.nfo"))
        if nfo_files:
            movie.nfo_path = str(nfo_files[0])
            self._parse_movie_nfo(movie, nfo_files[0])
        
        poster_files = list(directory.glob("poster.jpg")) + list(directory.glob("folder.jpg"))
        if poster_files:
            movie.poster_path = str(poster_files[0])
        
        backdrop_files = list(directory.glob("background.jpg")) + list(directory.glob("backdrop.jpg")) + list(directory.glob("fanart.jpg"))
        if backdrop_files:
            movie.backdrop_path = str(backdrop_files[0])
        
        return movie
    
    def _process_series_folder_yield(self, directory: Path):
        """处理电视剧文件夹并返回电视剧对象"""
        series = LocalSeries(
            path=str(directory),
            name=directory.name
        )
        
        nfo_files = list(directory.glob("*.nfo"))
        if nfo_files:
            series.nfo_path = str(nfo_files[0])
            self._parse_series_nfo(series, nfo_files[0])
        
        poster_files = list(directory.glob("poster.jpg")) + list(directory.glob("folder.jpg"))
        if poster_files:
            series.poster_path = str(poster_files[0])
        
        backdrop_files = list(directory.glob("background.jpg")) + list(directory.glob("backdrop.jpg")) + list(directory.glob("fanart.jpg"))
        if backdrop_files:
            series.backdrop_path = str(backdrop_files[0])
        
        self._process_series_directory_yield(directory, series)
        return series
    
    def _process_series_directory_yield(self, directory: Path, series: LocalSeries):
        """处理电视剧目录中的季和集"""
        season_pattern = re.compile(r'(?i)season\s*(\d+)|s(\d+)|第\s*(\d+)\s*季')
        
        for item in directory.iterdir():
            if item.is_dir():
                match = season_pattern.search(item.name)
                if match:
                    season_num = int(match.group(1) or match.group(2) or match.group(3))
                    season_data = {'season': season_num, 'episodes': []}
                    
                    for video_file in item.iterdir():
                        if video_file.is_file() and video_file.suffix.lower() in self.VIDEO_EXTENSIONS:
                            episode = self._parse_episode_file(video_file)
                            season_data['episodes'].append(episode)
                    
                    season_data['episodes'].sort(key=lambda x: x.get('episode', 0))
                    series.seasons.append(season_data)
            elif item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                episode = self._parse_episode_file(item)
                if episode:
                    if not series.seasons:
                        series.seasons.append({'season': 1, 'episodes': []})
                    series.seasons[0]['episodes'].append(episode)
        
        series.seasons.sort(key=lambda x: x.get('season', 0))
        for season in series.seasons:
            season['episodes'].sort(key=lambda x: x.get('episode', 0))
    
    def _parse_episode_file(self, video_file: Path):
        """解析剧集文件"""
        episode_pattern = re.compile(r'(?i)(?:e|episode|ep)\s*(\d+)')
        match = episode_pattern.search(video_file.stem)
        episode_num = int(match.group(1)) if match else 0
        
        return {
            'path': str(video_file),
            'name': video_file.stem,
            'episode': episode_num
        }
    
    def _parse_movie_nfo(self, movie: LocalMovie, nfo_file: Path):
        """解析电影NFO文件"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(nfo_file)
            root = tree.getroot()
            
            movie.title = root.findtext('title') or movie.name
            movie.overview = root.findtext('plot') or root.findtext('outline')
            movie.tmdb_id = int(root.findtext('tmdbid')) if root.findtext('tmdbid') else None
            movie.vote_average = float(root.findtext('rating')) if root.findtext('rating') else None
            movie.year = root.findtext('year') or root.findtext('premiered')
            
            genres = root.findall('genre')
            movie.genres = [g.text for g in genres if g.text]
            
            movie.info = {
                'title': movie.title,
                'overview': movie.overview,
                'tmdb_id': movie.tmdb_id,
                'vote_average': movie.vote_average,
                'year': movie.year,
                'genres': movie.genres
            }
        except Exception as e:
            print(f"解析电影NFO文件失败: {e}")
    
    def _parse_series_nfo(self, series: LocalSeries, nfo_file: Path):
        """解析电视剧NFO文件"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(nfo_file)
            root = tree.getroot()
            
            series.title = root.findtext('title') or series.name
            series.overview = root.findtext('plot') or root.findtext('outline')
            series.tmdb_id = int(root.findtext('tmdbid')) if root.findtext('tmdbid') else None
            series.vote_average = float(root.findtext('rating')) if root.findtext('rating') else None
            series.year = root.findtext('year') or root.findtext('premiered')
            
            genres = root.findall('genre')
            series.genres = [g.text for g in genres if g.text]
            
            series.info = {
                'title': series.title,
                'overview': series.overview,
                'tmdb_id': series.tmdb_id,
                'vote_average': series.vote_average,
                'year': series.year,
                'genres': series.genres
            }
        except Exception as e:
            print(f"解析电视剧NFO文件失败: {e}")
    
    def _scan_recursive(self, directory: Path):
        for item in directory.iterdir():
            if item.is_dir():
                self._process_movie_folder(item)
            elif item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                self._process_video_file(item)
    
    def _scan_flat(self, directory: Path):
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                self._process_video_file(item)
    
    def _scan_series_recursive(self, directory: Path):
        for item in directory.iterdir():
            if item.is_dir():
                # 检查当前目录是否是电视剧目录
                is_series_dir = False
                
                # 检查是否包含季节目录
                has_seasons = False
                for subitem in item.iterdir():
                    if subitem.is_dir():
                        # 更灵活的季节目录识别
                        if (subitem.name.lower().startswith('season') or 
                            '季' in subitem.name or 
                            'season' in subitem.name.lower() or
                            re.search(r'S\d+', subitem.name, re.IGNORECASE)):
                            has_seasons = True
                            break
                
                # 检查是否包含视频文件
                has_videos = False
                for subitem in item.iterdir():
                    if subitem.is_file() and subitem.suffix.lower() in self.VIDEO_EXTENSIONS:
                        has_videos = True
                        break
                
                # 检查是否包含嵌套的视频文件（递归检查一层）
                has_nested_videos = False
                if not has_videos:
                    for subitem in item.iterdir():
                        if subitem.is_dir():
                            for nested_item in subitem.iterdir():
                                if nested_item.is_file() and nested_item.suffix.lower() in self.VIDEO_EXTENSIONS:
                                    has_nested_videos = True
                                    break
                            if has_nested_videos:
                                break
                
                if has_seasons or has_videos or has_nested_videos:
                    self._process_series_directory(item)
                else:
                    # 继续递归扫描
                    self._scan_series_recursive(item)
    
    def _scan_series_flat(self, directory: Path):
        for item in directory.iterdir():
            if item.is_dir():
                self._process_series_directory(item)
    
    def _process_series_directory(self, series_dir: Path):
        series = LocalSeries(
            path=str(series_dir),
            name=series_dir.name
        )
        
        # 解析电视剧名称和年份
        self._parse_movie_name(series, series_dir.name)
        
        # 查找 NFO 文件
        nfo_file = None
        for ext in ['.nfo', '.NFO']:
            nfo_path = series_dir / f"{series_dir.name}{ext}"
            if nfo_path.exists():
                nfo_file = nfo_path
                break
        
        if not nfo_file:
            for item in series_dir.iterdir():
                if item.is_file() and item.suffix.lower() == '.nfo':
                    nfo_file = item
                    break
        
        if nfo_file and nfo_file.exists():
            series.nfo_path = str(nfo_file)
            self._load_nfo_info(series, nfo_file)
        
        # 查找海报文件
        poster_file = None
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            for name in ['poster', 'folder', 'cover', 'Series']:
                poster_path = series_dir / f"{name}{ext}"
                if poster_path.exists():
                    poster_file = poster_path
                    break
            if poster_file:
                break
        
        if poster_file:
            series.poster_path = str(poster_file)
        
        # 查找背景文件
        backdrop_file = None
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            for name in ['backdrop', 'fanart', 'banner']:
                backdrop_path = series_dir / f"{name}{ext}"
                if backdrop_path.exists():
                    backdrop_file = backdrop_path
                    break
            if backdrop_file:
                break
        
        if backdrop_file:
            series.backdrop_path = str(backdrop_file)
        
        seasons = []
        
        # 遍历目录，识别季和集
        for item in series_dir.iterdir():
            if item.is_dir():
                season_name = item.name
                season_number = self._extract_season_number(season_name)
                
                # 如果能够识别出季号
                if season_number is not None:
                    episodes = []
                    season_nfo_file = None
                    
                    # 查找季的nfo文件
                    for ext in ['.nfo', '.NFO']:
                        season_nfo_path = item / f"{item.name}{ext}"
                        if season_nfo_path.exists():
                            season_nfo_file = season_nfo_path
                            break
                    
                    if not season_nfo_file:
                        for subitem in item.iterdir():
                            if subitem.is_file() and subitem.suffix.lower() == '.nfo':
                                season_nfo_file = subitem
                                break
                    
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix.lower() in self.VIDEO_EXTENSIONS:
                            episode_number = self._extract_episode_number(subitem.name)
                            
                            # 查找集的nfo文件
                            episode_nfo_file = None
                            for ext in ['.nfo', '.NFO']:
                                episode_nfo_path = item / f"{subitem.stem}{ext}"
                                if episode_nfo_path.exists():
                                    episode_nfo_file = episode_nfo_path
                                    break
                            
                            episode_data = {
                                'path': str(subitem),
                                'name': subitem.name,
                                'episode': episode_number
                            }
                            
                            if episode_nfo_file:
                                episode_data['nfo_path'] = str(episode_nfo_file)
                            
                            episodes.append(episode_data)
                    
                    season_data = {
                        'season': season_number,
                        'name': season_name,
                        'episodes': episodes
                    }
                    
                    if season_nfo_file:
                        season_data['nfo_path'] = str(season_nfo_file)
                    
                    seasons.append(season_data)
                else:
                    # 检查是否是嵌套的季节目录（例如：Season 1\Episode 1）
                    # 或者直接包含视频文件的目录
                    nested_episodes = []
                    has_videos = False
                    nested_nfo_file = None
                    
                    # 查找嵌套目录的nfo文件
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix.lower() == '.nfo':
                            nested_nfo_file = subitem
                            break
                    
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix.lower() in self.VIDEO_EXTENSIONS:
                            episode_number = self._extract_episode_number(subitem.name)
                            
                            # 查找集的nfo文件
                            episode_nfo_file = None
                            for ext in ['.nfo', '.NFO']:
                                episode_nfo_path = item / f"{subitem.stem}{ext}"
                                if episode_nfo_path.exists():
                                    episode_nfo_file = episode_nfo_path
                                    break
                            
                            episode_data = {
                                'path': str(subitem),
                                'name': subitem.name,
                                'episode': episode_number
                            }
                            
                            if episode_nfo_file:
                                episode_data['nfo_path'] = str(episode_nfo_file)
                            
                            nested_episodes.append(episode_data)
                            has_videos = True
                    
                    if has_videos:
                        # 为嵌套目录分配默认季号
                        season_data = {
                            'season': len(seasons) + 1,  # 从1开始递增
                            'name': season_name,
                            'episodes': nested_episodes
                        }
                        
                        if nested_nfo_file:
                            season_data['nfo_path'] = str(nested_nfo_file)
                        
                        seasons.append(season_data)
        
        # 如果没有识别到季节目录，但直接包含视频文件
        if not seasons:
            root_episodes = []
            for item in series_dir.iterdir():
                if item.is_file() and item.suffix.lower() in self.VIDEO_EXTENSIONS:
                    episode_number = self._extract_episode_number(item.name)
                    
                    # 查找集的nfo文件
                    episode_nfo_file = None
                    for ext in ['.nfo', '.NFO']:
                        episode_nfo_path = series_dir / f"{item.stem}{ext}"
                        if episode_nfo_path.exists():
                            episode_nfo_file = episode_nfo_path
                            break
                    
                    episode_data = {
                        'path': str(item),
                        'name': item.name,
                        'episode': episode_number
                    }
                    
                    if episode_nfo_file:
                        episode_data['nfo_path'] = str(episode_nfo_file)
                    
                    root_episodes.append(episode_data)
            
            if root_episodes:
                seasons.append({
                    'season': 1,  # 默认第1季
                    'name': 'Season 1',
                    'episodes': root_episodes
                })
        
        series.seasons = seasons
        self.series.append(series)
    
    def _extract_season_number(self, name: str) -> Optional[int]:
        # 匹配 Season 1, 季 1, S01 等格式
        patterns = [
            r'Season\s*(\d+)',  # Season 1
            r'季\s*(\d+)',       # 季 1
            r'S(\d+)',           # S01
            r'第(\d+)季',        # 第1季
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_episode_number(self, name: str) -> Optional[int]:
        # 匹配 Episode 1, 第1集, S01E01 等格式
        patterns = [
            r'Episode\s*(\d+)',  # Episode 1
            r'第\s*(\d+)\s*集',   # 第1集
            r'S\d+E(\d+)',       # S01E01
            r'E(\d+)',            # E01
            r'第(\d+)集',         # 第1集
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def _process_movie_folder(self, folder: Path):
        video_files = []
        nfo_files = []
        poster_files = []
        backdrop_files = []
        
        try:
            items = list(folder.iterdir())
            
            for item in items:
                if item.is_file():
                    if item.suffix.lower() in self.VIDEO_EXTENSIONS:
                        video_files.append(item)
                    elif item.suffix.lower() == '.nfo':
                        nfo_files.append(item)
                    elif item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                        if item.stat().st_size > 0:
                            stem_lower = item.stem.lower()
                            if any(keyword in stem_lower for keyword in ['poster', 'folder', 'cover', 'front', 'coverart']):
                                poster_files.append(item)
                            elif any(keyword in stem_lower for keyword in ['backdrop', 'fanart', 'background', 'back']):
                                backdrop_files.append(item)
                            else:
                                poster_files.append(item)
        except Exception:
            pass
        
        if video_files:
            for video in video_files:
                video_nfo = None
                for nfo in nfo_files:
                    if nfo.stem == video.stem:
                        video_nfo = nfo
                        break
                
                if not video_nfo and nfo_files:
                    video_nfo = nfo_files[0]
                
                video_poster = None
                video_backdrop = None
                
                poster_names = ['poster', 'folder', 'cover', 'front', 'coverart']
                extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
                
                poster_candidates = []
                for name in poster_names:
                    for ext in extensions:
                        poster_path = folder / f"{name}{ext}"
                        if poster_path.exists() and poster_path.is_file() and poster_path.stat().st_size > 0:
                            poster_candidates.append((poster_path, name))
                
                if poster_candidates:
                    priority = {'poster': 1, 'folder': 2, 'cover': 3, 'front': 4, 'coverart': 5}
                    poster_candidates.sort(key=lambda x: priority.get(x[1].lower(), 999))
                    video_poster = poster_candidates[0][0]
                
                if not video_poster:
                    for ext in extensions:
                        poster_path = folder / f"{video.stem}{ext}"
                        if poster_path.exists() and poster_path.is_file() and poster_path.stat().st_size > 0:
                            video_poster = poster_path
                            break
                
                if not video_poster and poster_files:
                    for poster in poster_files:
                        if poster.stat().st_size > 0:
                            video_poster = poster
                            break
                
                if not video_poster:
                    for item in folder.iterdir():
                        if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp'] and item.stat().st_size > 0:
                            video_poster = item
                            break
                
                if backdrop_files:
                    valid_backdrops = [b for b in backdrop_files if b.stat().st_size > 0]
                    if valid_backdrops:
                        video_backdrop = valid_backdrops[0]
                
                movie = LocalMovie(
                    path=str(video),
                    name=video.stem,
                    nfo_path=str(video_nfo) if video_nfo else None,
                    poster_path=str(video_poster) if video_poster else None,
                    backdrop_path=str(video_backdrop) if video_backdrop else None
                )
                
                self._parse_movie_name(movie, folder.name)
                
                if video_nfo:
                    self._load_nfo_info(movie, video_nfo)
                
                self.movies.append(movie)
    
    def _process_video_file(self, video: Path):
        movie = LocalMovie(
            path=str(video),
            name=video.stem
        )
        
        parent = video.parent
        
        self._parse_movie_name(movie, video.stem)
        
        nfo_file = None
        
        for ext in ['.nfo', '.NFO']:
            nfo_path = parent / f"{video.stem}{ext}"
            if nfo_path.exists():
                nfo_file = nfo_path
                break
        
        if not nfo_file:
            for item in parent.iterdir():
                if item.is_file() and item.suffix.lower() == '.nfo':
                    nfo_file = item
                    break
        
        if nfo_file and nfo_file.exists():
            movie.nfo_path = str(nfo_file)
            self._load_nfo_info(movie, nfo_file)
        
        poster_file = None
        poster_names = ['poster', 'folder', 'cover', 'front', 'coverart']
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        
        poster_candidates = []
        for name in poster_names:
            for ext in extensions:
                poster_path = parent / f"{name}{ext}"
                if poster_path.exists() and poster_path.is_file() and poster_path.stat().st_size > 0:
                    poster_candidates.append((poster_path, name))
        
        if poster_candidates:
            priority = {'poster': 1, 'folder': 2, 'cover': 3, 'front': 4, 'coverart': 5}
            poster_candidates.sort(key=lambda x: priority.get(x[1].lower(), 999))
            poster_file = poster_candidates[0][0]
        
        if not poster_file:
            for ext in extensions:
                img_path = parent / f"{video.stem}{ext}"
                if img_path.exists() and img_path.is_file() and img_path.stat().st_size > 0:
                    poster_file = img_path
                    break
        
        if not poster_file:
            for item in parent.iterdir():
                if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp'] and item.stat().st_size > 0:
                    poster_file = item
                    break
        
        if poster_file:
            movie.poster_path = str(poster_file)
        
        backdrop_file = self._find_image(parent, video.stem, ['backdrop', 'fanart', 'background', 'back'])
        if backdrop_file:
            movie.backdrop_path = str(backdrop_file)
        
        self.movies.append(movie)
    
    def _find_image(self, directory: Path, base_name: str, alternatives: List[str]) -> Optional[Path]:
        for alt in alternatives:
            for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                img_path = directory / f"{alt}{ext}"
                if img_path.exists() and img_path.stat().st_size > 0:
                    return img_path
                img_path_upper_ext = directory / f"{alt}{ext.upper()}"
                if img_path_upper_ext.exists() and img_path_upper_ext.stat().st_size > 0:
                    return img_path_upper_ext
        
        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            img_path = directory / f"{base_name}{ext}"
            if img_path.exists() and img_path.stat().st_size > 0:
                return img_path
            img_path_upper_ext = directory / f"{base_name}{ext.upper()}"
            if img_path_upper_ext.exists() and img_path_upper_ext.stat().st_size > 0:
                return img_path_upper_ext
        
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp'] and item.stat().st_size > 0:
                if any(keyword in item.stem.lower() for keyword in ['poster', 'cover', 'folder', 'front']):
                    return item
        
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp'] and item.stat().st_size > 0:
                return item
        
        return None
    
    def _parse_movie_name(self, movie: LocalMovie, name: str):
        patterns = [
            r'^(.+?)[.\s\-_]+(\d{4})[.\s\-_]',
            r'^(.+?)\((\d{4})\)',
            r'^(.+?)\[(\d{4})\]',
            r'^(.+?)\{(\d{4})\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                movie.title = self._clean_name(match.group(1))
                movie.year = match.group(2)
                return
        
        movie.title = self._clean_name(name)
    
    def _clean_name(self, name: str) -> str:
        name = re.sub(r'[.\-_]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        remove_patterns = [
            r'\b(BluRay|BDRip|WEBRip|WEB-DL|HDTV|DVDRip|DVDScr|CAM|TS|R5|R6)\b',
            r'\b(1080p|720p|480p|360p|2160p|4K)\b',
            r'\b(x264|x265|H\.264|H\.265|HEVC|AVC)\b',
            r'\b(DTS|AC3|AAC|DD5\.1|DD7\.1|Atmos)\b',
            r'\b(REMUX|PROPER|REPACK|UNRATED|EXTENDED|DIRECTOR\'?S?\.?CUT)\b',
            r'\b(3D|SBS|HSBS)\b',
            r'\[(.+?)\]',
            r'\((.+?)\)',
        ]
        
        for pattern in remove_patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        name = re.sub(r'\s+', ' ', name)
        return name.strip()
    
    def _load_nfo_info(self, movie: LocalMovie, nfo_path: Path):
        try:
            try:
                with open(nfo_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(nfo_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            if content.strip().startswith('<?xml') or content.strip().startswith('<'):
                self._parse_xml_nfo(movie, content)
            else:
                self._parse_json_nfo(movie, content)
        except Exception:
            pass
    
    def _parse_xml_nfo(self, movie: LocalMovie, content: str):
        try:
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
            
            plot_elem = find_element_recursive(root, 'plot')
            if plot_elem is not None and plot_elem.text:
                movie.overview = plot_elem.text.strip()
            else:
                for tag in ['synopsis', 'description', 'summary', 'overview']:
                    elem = find_element_recursive(root, tag)
                    if elem is not None and elem.text:
                        movie.overview = elem.text.strip()
                        break
            
            mappings = {
                'title': 'title',
                'originaltitle': 'original_title',
                'year': 'year',
                'rating': 'vote_average',
                'tmdbid': 'tmdb_id',
                'id': 'tmdb_id',
                'tmdbcollectionid': 'collection_id',
                'collectionid': 'collection_id',
            }
            
            for xml_tag, attr in mappings.items():
                elem = find_element_recursive(root, xml_tag)
                if elem is not None and elem.text:
                    if attr == 'tmdb_id':
                        try:
                            movie.tmdb_id = int(elem.text)
                        except ValueError:
                            pass
                    elif attr == 'collection_id':
                        try:
                            movie.collection_id = int(elem.text)
                        except ValueError:
                            pass
                    elif attr == 'vote_average':
                        try:
                            movie.vote_average = float(elem.text)
                        except ValueError:
                            pass
                    else:
                        setattr(movie, attr, elem.text)
            
            def find_all_genres(element):
                genres = []
                for child in element:
                    if child.tag.lower() == 'genre' and child.text:
                        genres.append(child.text)
                    genres.extend(find_all_genres(child))
                return genres
            
            genres = find_all_genres(root)
            if genres:
                movie.genres = genres
            
            movie.matched = True
        except Exception:
            try:
                import re
                plot_match = re.search(r'<plot[^>]*>([\s\S]*?)</plot>', content, re.IGNORECASE)
                if plot_match:
                    movie.overview = plot_match.group(1).strip()
                else:
                    for tag in ['synopsis', 'description', 'summary', 'overview']:
                        match = re.search(rf'<{tag}[^>]*>([\s\S]*?)</{tag}>', content, re.IGNORECASE)
                        if match:
                            movie.overview = match.group(1).strip()
                            break
            except Exception:
                pass
    
    def _parse_json_nfo(self, movie: LocalMovie, content: str):
        try:
            data = json.loads(content)
            
            movie.title = data.get('title', movie.title)
            movie.year = str(data.get('year', movie.year or ''))
            overview_keys = ['overview', 'plot', 'synopsis', 'description', 'summary']
            for key in overview_keys:
                if key in data and data[key]:
                    movie.overview = data[key]
                    break
            movie.vote_average = data.get('vote_average') or data.get('rating', movie.vote_average)
            movie.tmdb_id = data.get('tmdb_id') or data.get('id', movie.tmdb_id)
            
            if 'genres' in data:
                movie.genres = data['genres'] if isinstance(data['genres'], list) else []
            
            movie.matched = True
        except Exception:
            pass
    
    def save_nfo(self, movie: LocalMovie, info: dict, directory: str = None):
        if directory is None:
            if movie.path:
                directory = os.path.dirname(movie.path)
            else:
                directory = os.getcwd()
        
        if movie.path:
            nfo_filename = f"{Path(movie.path).stem}.nfo"
        else:
            nfo_filename = f"{info.get('title', 'movie')}.nfo"
        
        nfo_path = os.path.join(directory, nfo_filename)
        
        collection_id = info.get('collection_id') or getattr(movie, 'collection_id', None)
        collection_name = info.get('collection_name') or getattr(movie, 'collection_name', None)
        
        nfo_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{info.get('title', movie.title or '')}</title>
    <originaltitle>{info.get('original_title', '')}</originaltitle>
    <year>{info.get('year', movie.year or '')}</year>
    <plot>{info.get('overview', '')}</plot>
    <rating>{info.get('vote_average', 0)}</rating>
    <tmdbid>{info.get('tmdb_id') or info.get('id', '')}</tmdbid>'''
        
        if collection_id:
            nfo_content += f'''
    <TmdbCollectionId>{collection_id}</TmdbCollectionId>'''
        
        if collection_name:
            nfo_content += f'''
    <collection>
        <name>{collection_name}</name>
    </collection>'''
        
        for genre in info.get('genres', []):
            nfo_content += f'''
    <genre>{genre}</genre>'''
        
        nfo_content += '''
</movie>
'''
        
        try:
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            movie.nfo_path = nfo_path
            movie.matched = True
            if collection_id:
                movie.collection_id = collection_id
            if collection_name:
                movie.collection_name = collection_name
            return nfo_path
        except Exception:
            return None