import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import LocalMovieScanner

def debug_poster():
    """调试海报加载问题"""
    print("=" * 80)
    print("海报加载问题调试")
    print("=" * 80)
    
    # 获取用户的电影目录
    print("请输入您的电影目录路径:")
    movie_dir = input().strip()
    
    if not movie_dir:
        print("错误: 请输入有效的目录路径")
        return
    
    movie_path = Path(movie_dir)
    if not movie_path.exists() or not movie_path.is_dir():
        print(f"错误: 目录不存在或不是有效目录: {movie_dir}")
        return
    
    print(f"\n正在分析目录: {movie_path}")
    print("-" * 80)
    
    # 扫描电影
    scanner = LocalMovieScanner()
    movies = scanner.scan_directory(str(movie_path), recursive=True)
    
    print(f"找到 {len(movies)} 个电影")
    print("\n详细分析:")
    print("-" * 80)
    
    # 分析每个电影
    for i, movie in enumerate(movies, 1):
        print(f"\n电影 {i}: {movie.title or movie.name}")
        print("-" * 60)
        print(f"路径: {movie.path}")
        print(f"海报路径: {movie.poster_path}")
        
        # 检查海报路径
        if movie.poster_path:
            poster_path = Path(movie.poster_path)
            print(f"海报路径是否绝对路径: {poster_path.is_absolute()}")
            print(f"海报路径是否存在: {poster_path.exists()}")
            print(f"海报路径是否是文件: {poster_path.is_file() if poster_path.exists() else 'N/A'}")
            
            if poster_path.exists():
                print(f"海报文件大小: {poster_path.stat().st_size} 字节")
                print(f"海报文件扩展名: {poster_path.suffix.lower()}")
                print(f"海报文件可读: {os.access(movie.poster_path, os.R_OK)}")
            else:
                print("错误: 海报文件不存在")
        else:
            print("错误: 未设置海报路径")
        
        # 列出目录中的所有文件
        parent_dir = Path(movie.path).parent
        print("\n目录中的所有文件:")
        all_files = []
        for item in parent_dir.iterdir():
            if item.is_file():
                size = item.stat().st_size
                all_files.append((item.name, size))
                print(f"  {item.name} ({size} 字节)")
        
        # 分析图片文件
        image_files = [(f, s) for f, s in all_files if Path(f).suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']]
        valid_images = [(f, s) for f, s in image_files if s > 0]
        
        print(f"\n图片文件分析:")
        print(f"总图片文件: {len(image_files)}")
        print(f"有效图片: {len(valid_images)}")
        
        for img_name, img_size in valid_images:
            print(f"  ✓ {img_name} ({img_size} 字节)")
        
        print("-" * 60)
    
    print("\n" + "=" * 80)
    print("调试完成")
    print("=" * 80)
    print("\n按 Enter 键退出...")
    input()

if __name__ == "__main__":
    debug_poster()
