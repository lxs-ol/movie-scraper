import os
import sys
import json
import time
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from functools import lru_cache

@dataclass
class MovieInfo:
    id: int
    title: str
    original_title: str
    year: str
    overview: str
    poster_path: str
    backdrop_path: str
    vote_average: float
    media_type: str
    genre_ids: List[int]
    popularity: float

class TMDBAPI:
    def __init__(self, api_key: str = None, proxy_config: dict = None):
        self.api_key = api_key or ''
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p"
        self.session = requests.Session()
        self.proxy_config = proxy_config
        
        self._setup_logging()
        
        if proxy_config:
            self._setup_proxy(proxy_config)
    
    def _setup_logging(self):
        if hasattr(sys, 'frozen'):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
        
        log_file = os.path.join(log_dir, 'movie_scraper.log')
        
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'
        )
        logging.info("TMDB API 初始化")
    
    def _setup_proxy(self, proxy_config: dict):
        try:
            if not proxy_config:
                logging.warning("代理配置为空，跳过代理设置")
                return
            
            proxy_type = proxy_config.get('type', 'http')
            host = proxy_config.get('host', '')
            port = proxy_config.get('port', '')
            username = proxy_config.get('username', '')
            password = proxy_config.get('password', '')
            
            logging.info(f"设置代理: type={proxy_type}, host={host}, port={port}")
            
            if not host or not port:
                logging.warning("代理主机或端口为空，跳过代理设置")
                return
            
            if username and password:
                proxy_url = f"{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{host}:{port}"
            
            if proxy_type == 'socks5':
                proxies = {
                    'http': f'socks5://{proxy_url}',
                    'https': f'socks5://{proxy_url}'
                }
            else:
                # HTTP代理：http和https都使用http://前缀
                # requests会自动使用CONNECT方法建立HTTPS隧道
                proxies = {
                    'http': f'http://{proxy_url}',
                    'https': f'http://{proxy_url}'
                }
            
            # 清除之前的代理设置
            self.session.proxies.clear()
            self.session.proxies.update(proxies)
            logging.info(f"代理设置完成: {proxies}")
            logging.info(f"当前session代理: {self.session.proxies}")
        except Exception as e:
            logging.error(f"代理设置失败: {e}")
            # 发生错误时清除代理设置，避免影响后续请求
            try:
                self.session.proxies.clear()
                logging.info("已清除代理设置")
            except:
                pass
    
    def set_api_key(self, api_key: str):
        self.api_key = api_key
        logging.info("API Key 已更新")
    
    def set_proxy(self, proxy_config: dict):
        self.proxy_config = proxy_config
        self._setup_proxy(proxy_config)
    
    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.api_key:
            logging.error("API Key 未设置")
            return None
        
        url = f"{self.base_url}/{endpoint}"
        default_params = {'api_key': self.api_key, 'language': 'zh-CN'}
        if params:
            default_params.update(params)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 尝试HTTPS请求
                response = self.session.get(url, params=default_params, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.SSLError as ssl_e:
                logging.warning(f"SSL错误，尝试跳过验证: {ssl_e}")
                try:
                    # SSL错误时尝试跳过验证
                    response = self.session.get(url, params=default_params, timeout=15, verify=False)
                    response.raise_for_status()
                    return response.json()
                except Exception as e2:
                    logging.error(f"API 请求失败(跳过SSL验证后): {e2}")
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(1)
            except requests.exceptions.ProxyError as proxy_e:
                logging.error(f"代理错误: {proxy_e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2)
            except requests.exceptions.RequestException as e:
                logging.error(f"API 请求失败: {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(1)
        return None
    
    def search_movie(self, query: str, page: int = 1) -> List[MovieInfo]:
        logging.info(f"搜索电影: {query}")
        data = self._make_request('search/movie', {'query': query, 'page': page})
        
        if not data or 'results' not in data:
            return []
        
        results = []
        for item in data['results']:
            results.append(MovieInfo(
                id=item.get('id', 0),
                title=item.get('title', ''),
                original_title=item.get('original_title', ''),
                year=item.get('release_date', '')[:4] if item.get('release_date') else '',
                overview=item.get('overview', ''),
                poster_path=item.get('poster_path', ''),
                backdrop_path=item.get('backdrop_path', ''),
                vote_average=item.get('vote_average', 0),
                media_type='movie',
                genre_ids=item.get('genre_ids', []),
                popularity=item.get('popularity', 0)
            ))
        
        logging.info(f"找到 {len(results)} 个电影结果")
        return results
    
    def search_tv(self, query: str, page: int = 1) -> List[MovieInfo]:
        logging.info(f"搜索TV: {query}")
        data = self._make_request('search/tv', {'query': query, 'page': page})
        
        if not data or 'results' not in data:
            return []
        
        results = []
        for item in data['results']:
            results.append(MovieInfo(
                id=item.get('id', 0),
                title=item.get('name', ''),
                original_title=item.get('original_name', ''),
                year=item.get('first_air_date', '')[:4] if item.get('first_air_date') else '',
                overview=item.get('overview', ''),
                poster_path=item.get('poster_path', ''),
                backdrop_path=item.get('backdrop_path', ''),
                vote_average=item.get('vote_average', 0),
                media_type='tv',
                genre_ids=item.get('genre_ids', []),
                popularity=item.get('popularity', 0)
            ))
        
        logging.info(f"找到 {len(results)} 个TV结果")
        return results
    
    def search_multi(self, query: str, page: int = 1) -> List[MovieInfo]:
        logging.info(f"多类型搜索: {query}")
        data = self._make_request('search/multi', {'query': query, 'page': page})
        
        if not data or 'results' not in data:
            return []
        
        results = []
        for item in data['results']:
            media_type = item.get('media_type', 'movie')
            if media_type not in ['movie', 'tv']:
                continue
            
            results.append(MovieInfo(
                id=item.get('id', 0),
                title=item.get('title') or item.get('name', ''),
                original_title=item.get('original_title') or item.get('original_name', ''),
                year=(item.get('release_date') or item.get('first_air_date', ''))[:4],
                overview=item.get('overview', ''),
                poster_path=item.get('poster_path', ''),
                backdrop_path=item.get('backdrop_path', ''),
                vote_average=item.get('vote_average', 0),
                media_type=media_type,
                genre_ids=item.get('genre_ids', []),
                popularity=item.get('popularity', 0)
            ))
        
        logging.info(f"找到 {len(results)} 个结果")
        return results
    
    def get_movie_details(self, movie_id: int) -> Optional[dict]:
        logging.info(f"获取电影详情: {movie_id}")
        return self._make_request(f'movie/{movie_id}')
    
    def get_tv_details(self, tv_id: int) -> Optional[dict]:
        logging.info(f"获取TV详情: {tv_id}")
        return self._make_request(f'tv/{tv_id}')
    
    def get_episode_details(self, tv_id: int, season_number: int, episode_number: int) -> Optional[dict]:
        """获取集详细信息"""
        logging.info(f"获取集详情: TV ID={tv_id}, S{season_number:02d}E{episode_number:02d}")
        return self._make_request(f'tv/{tv_id}/season/{season_number}/episode/{episode_number}')
    
    def get_still_url(self, still_path: str, size: str = 'w500') -> str:
        """获取集剧照URL"""
        if not still_path:
            return ''
        return f"{self.image_base_url}/{size}{still_path}"
    
    def get_poster_url(self, poster_path: str, size: str = 'w500') -> str:
        if not poster_path:
            return ''
        return f"{self.image_base_url}/{size}{poster_path}"
    
    def get_backdrop_url(self, backdrop_path: str, size: str = 'w1280') -> str:
        if not backdrop_path:
            return ''
        return f"{self.image_base_url}/{size}{backdrop_path}"
    
    def get_logo_url(self, logo_path: str, size: str = 'w500') -> str:
        if not logo_path:
            return ''
        return f"{self.image_base_url}/{size}{logo_path}"
    
    def get_banner_url(self, banner_path: str, size: str = 'w1280') -> str:
        if not banner_path:
            return ''
        return f"{self.image_base_url}/{size}{banner_path}"
    
    def download_image(self, url: str, save_path: str) -> bool:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logging.info(f"图片下载成功: {save_path}")
            return True
        except Exception as e:
            logging.error(f"图片下载失败: {e}")
            return False
    
    def test_api_key(self) -> tuple:
        """测试API Key，返回(是否成功, 错误信息)"""
        if not self.api_key:
            logging.error("API Key 未设置")
            return False, "API Key 未设置"
        
        try:
            logging.info(f"开始测试 API Key: {self.api_key[:10]}...")
            logging.info(f"当前代理配置: {self.proxy_config}")
            logging.info(f"当前session代理: {self.session.proxies}")
            
            url = f"{self.base_url}/configuration"
            params = {'api_key': self.api_key}
            
            logging.info(f"请求URL: {url}")
            response = self.session.get(url, params=params, timeout=15)
            logging.info(f"响应状态码: {response.status_code}")
            logging.info(f"响应内容: {response.text[:200]}")
            
            if response.status_code == 200:
                logging.info("API Key 测试成功")
                return True, "成功"
            elif response.status_code == 401:
                logging.error("API Key 无效 (401)")
                return False, "API Key 无效"
            else:
                logging.error(f"API Key 测试失败: HTTP {response.status_code}")
                return False, f"HTTP错误: {response.status_code}"
        except requests.exceptions.ProxyError as e:
            logging.error(f"代理错误: {e}")
            return False, f"代理错误: {str(e)}"
        except requests.exceptions.ConnectTimeout:
            logging.error("连接超时")
            return False, "连接超时"
        except requests.exceptions.SSLError as e:
            logging.error(f"SSL错误: {e}")
            return False, f"SSL错误: {str(e)}"
        except Exception as e:
            logging.error(f"API Key 测试异常: {e}")
            return False, f"异常: {str(e)}"
    
    def search_collection(self, query: str, page: int = 1) -> List[dict]:
        logging.info(f"搜索合集: {query}")
        data = self._make_request('search/collection', {'query': query, 'page': page})
        
        if not data or 'results' not in data:
            return []
        
        results = []
        for item in data['results']:
            results.append({
                'id': item.get('id', 0),
                'name': item.get('name', ''),
                'original_name': item.get('original_name', ''),
                'overview': item.get('overview', ''),
                'poster_path': item.get('poster_path', ''),
                'backdrop_path': item.get('backdrop_path', ''),
            })
        
        logging.info(f"找到 {len(results)} 个合集结果")
        return results
    
    def get_collection_details(self, collection_id: int) -> Optional[dict]:
        logging.info(f"获取合集详情: {collection_id}")
        return self._make_request(f'collection/{collection_id}')
    
    def get_tv_episode_details(self, tv_id: int, season_num: int, episode_num: int) -> Optional[dict]:
        logging.info(f"获取TV剧集详情: {tv_id} S{season_num}E{episode_num}")
        return self._make_request(f'tv/{tv_id}/season/{season_num}/episode/{episode_num}')
    
    def get_tv_season_details(self, tv_id: int, season_num: int) -> Optional[dict]:
        logging.info(f"获取TV季详情: {tv_id} S{season_num}")
        return self._make_request(f'tv/{tv_id}/season/{season_num}')
