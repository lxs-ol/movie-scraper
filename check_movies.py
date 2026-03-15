import os
import sys
from pathlib import Path

# 测试脚本：检查电影文件夹结构和海报文件
def check_movie_folders(base_path):
    base_path = Path(base_path)
    if not base_path.exists():
        print(f"路径不存在: {base_path}")
        return
    
    print(f"检查路径: {base_path}")
    
    # 遍历所有子文件夹
    for movie_folder in base_path.iterdir():
        if not movie_folder.is_dir():
            continue
        
        print(f"\n检查电影文件夹: {movie_folder.name}")
        
        # 检查是否有视频文件
        video_files = []
        for file in movie_folder.iterdir():
            if file.is_file() and file.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
                video_files.append(file)
        
        if video_files:
            print(f"找到视频文件: {len(video_files)}个")
            for video in video_files[:3]:  # 只显示前3个
                print(f"  - {video.name}")
        else:
            print("未找到视频文件")
        
        # 检查是否有海报文件
        poster_files = []
        for file in movie_folder.iterdir():
            if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                poster_files.append(file)
        
        if poster_files:
            print(f"找到图片文件: {len(poster_files)}个")
            for poster in poster_files:
                print(f"  - {poster.name}")
                print(f"    大小: {poster.stat().st_size / 1024:.2f} KB")
                print(f"    存在: {poster.exists()}")
        else:
            print("未找到图片文件")
        
        # 检查是否有NFO文件
        nfo_files = []
        for file in movie_folder.iterdir():
            if file.is_file() and file.suffix.lower() == '.nfo':
                nfo_files.append(file)
        
        if nfo_files:
            print(f"找到NFO文件: {len(nfo_files)}个")
            for nfo in nfo_files:
                print(f"  - {nfo.name}")
        else:
            print("未找到NFO文件")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python check_movies.py <电影文件夹路径>")
        sys.exit(1)
    
    check_movie_folders(sys.argv[1])