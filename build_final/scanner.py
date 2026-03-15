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
                has_seasons = False
                has_videos = False
                
                for subitem in item.iterdir():
                    if subitem.is_dir() and (subitem.name.lower().startswith('season') or '季' in subitem.name):
                        has_seasons = True
                    elif subitem.is_file() and subitem.suffix.lower() in self.VIDEO_EXTENSIONS:
                        has_videos = True
                
                if has_seasons or has_videos:
                    self._process_series_directory(item)
                else:
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
        
        self._parse_movie_name(series, series_dir.name)
        
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
        for item in series_dir.iterdir():
            if item.is_dir():
                season_name = item.name
                season_number = self._extract_season_number(season_name)
                if season_number is not None:
                    episodes = []
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix.lower() in self.VIDEO_EXTENSIONS:
                            episode_number = self._extract_episode_number(subitem.name)
                            episodes.append({
                                'path': str(subitem),
                                'name': subitem.name,
                                'episode': episode_number
                            })
                    seasons.append({
                        'season': season_number,
                        'name': season_name,
                        'episodes': episodes
                    })
        
        series.seasons = seasons
        self.series.append(series)
    
    def _extract_season_number(self, name: str) -> Optional[int]:
        match = re.search(r'Season\s*(\d+)|季\s*(\d+)', name, re.IGNORECASE)
        if match:
            return int(match.group(1) or match.group(2))
        return None
    
    def _extract_episode_number(self, name: str) -> Optional[int]:
        match = re.search(r'Episode\s*(\d+)|第\s*(\d+)\s*集', name, re.IGNORECASE)
        if match:
            return int(match.group(1) or match.group(2))
        match = re.search(r'S(\d+)E(\d+)', name, re.IGNORECASE)
        if match:
            return int(match.group(2))
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
        
        collection_id = info.get('collection_id') or movie.collection_id
        collection_name = info.get('collection_name') or movie.collection_name
        
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