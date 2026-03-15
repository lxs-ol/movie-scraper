import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import LocalMovieScanner

def diagnose_poster_issue():
    """诊断海报加载问题"""
    print("Diagnosing poster loading issue")
    print("=" * 80)
    
    # 让用户输入电影目录
    print("Please enter the path to your movie directory:")
    movie_dir_path = input().strip()
    
    if not movie_dir_path:
        print("No directory entered. Exiting.")
        return
    
    movie_dir = Path(movie_dir_path)
    if not movie_dir.exists() or not movie_dir.is_dir():
        print(f"Invalid directory: {movie_dir_path}")
        return
    
    print(f"Analyzing directory: {movie_dir}")
    print("-" * 60)
    
    # 扫描电影
    scanner = LocalMovieScanner()
    movies = scanner.scan_directory(str(movie_dir), recursive=True)
    
    print(f"Found {len(movies)} movies:")
    
    for i, movie in enumerate(movies, 1):
        print(f"\nMovie {i}:")
        print(f"  Title: {movie.title or movie.name}")
        print(f"  Path: {movie.path}")
        print(f"  Poster path: {movie.poster_path}")
        
        # 检查海报文件是否存在
        if movie.poster_path:
            poster_path = Path(movie.poster_path)
            poster_exists = poster_path.exists()
            print(f"  Poster exists: {poster_exists}")
            if poster_exists:
                print(f"  Poster size: {poster_path.stat().st_size} bytes")
                print(f"  Poster is file: {poster_path.is_file()}")
                print(f"  Poster path length: {len(movie.poster_path)}")
                print(f"  Poster path contains non-ASCII: {any(ord(c) > 127 for c in movie.poster_path)}")
            else:
                print(f"  Poster file not found at: {movie.poster_path}")
        else:
            print("  No poster path set")
        
        # 列出目录中的所有图片文件
        print(f"  Image files in directory:")
        movie_dir_path = Path(movie.path).parent
        image_files = []
        for item in movie_dir_path.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                image_files.append((item.name, item.stat().st_size))
                print(f"    - {item.name} ({item.stat().st_size} bytes)")
        
        if not image_files:
            print("    - No image files found")
        else:
            # 检查是否有有效的图片文件
            valid_images = [f for f, size in image_files if size > 0]
            print(f"  Valid image files (size > 0): {len(valid_images)}")
            for img in valid_images:
                print(f"    - {img}")
    
    print("=" * 80)
    print("Diagnosis completed.")
    print("\nIf you see 'No poster path set' for movies that have image files,")
    print("please check if the image files are valid (size > 0 bytes).")

if __name__ == "__main__":
    diagnose_poster_issue()
