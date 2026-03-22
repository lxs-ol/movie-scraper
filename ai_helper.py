import requests
import json
import re
from typing import Optional, Tuple

class AIHelper:
    def __init__(self, api_key: str = "", base_url: str = "https://api.siliconflow.cn/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "Qwen/Qwen2.5-7B-Instruct"
    
    def set_api_key(self, api_key: str):
        self.api_key = api_key
    
    def set_base_url(self, base_url: str):
        if base_url:
            self.base_url = base_url
    
    def set_model(self, model: str):
        if model:
            self.model = model
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def _call_api(self, prompt: str) -> Tuple[Optional[str], Optional[int]]:
        if not self.is_configured():
            return None, None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 100
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    parsed = json.loads(json_match.group())
                    title = parsed.get("title", "").strip()
                    year = parsed.get("year")
                    
                    if title:
                        if isinstance(year, int):
                            return title, year
                        elif year:
                            try:
                                return title, int(year)
                            except:
                                return title, None
                        return title, None
            
            return None, None
            
        except Exception as e:
            print(f"AI识别失败: {e}")
            return None, None
    
    def identify_movie_name(self, filename: str) -> Tuple[Optional[str], Optional[int]]:
        prompt = f"""你是一个电影名称识别专家。请从以下文件名中识别出正确的电影名称和年份。

文件名: {filename}

请分析这个文件名，提取出：
1. 电影的真实名称（中文或英文原名）
2. 上映年份（如果有）

注意：
- 忽略文件名中的画质信息（如1080p, 4K, BluRay, REMUX, WEB-DL等）
- 忽略编码信息（如x264, x265, HEVC, AAC, DTS等）
- 忽略发布组信息（如-XXX, [XXX]等）
- 忽略语言标识（如CN, EN, JAP等）
- 如果是系列电影，保留系列名称
- 年份通常是4位数字，在括号中或单独出现

请只返回JSON格式，不要其他内容：
{{"title": "电影名称", "year": 年份或null}}"""

        return self._call_api(prompt)
    
    def identify_series_name(self, filename: str) -> Tuple[Optional[str], Optional[int]]:
        prompt = f"""你是一个电视剧名称识别专家。请从以下文件名中识别出正确的电视剧名称和年份。

文件名: {filename}

请分析这个文件名，提取出：
1. 电视剧的真实名称（中文或英文原名）
2. 首播年份（如果有）

注意：
- 忽略文件名中的季集信息（如S01E01, 第1集, EP01等）
- 忽略画质信息（如1080p, 4K, BluRay等）
- 忽略编码信息（如x264, HEVC等）
- 忽略发布组信息

请只返回JSON格式，不要其他内容：
{{"title": "电视剧名称", "year": 年份或null}}"""

        return self._call_api(prompt)
