import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import LocalMovieScanner

def main():
    """海报加载问题诊断工具"""
    print("=" * 80)
    print("海报加载问题诊断工具")
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
    print("\n详细诊断结果:")
    print("-" * 80)
    
    # 分析每个电影
    for i, movie in enumerate(movies, 1):
        print(f"\n电影 {i}: {movie.title or movie.name}")
        print("-" * 60)
        print(f"路径: {movie.path}")
        print(f"海报路径: {movie.poster_path}")
        
        # 检查海报文件
        poster_found = False
        if movie.poster_path:
            poster_file = Path(movie.poster_path)
            exists = poster_file.exists()
            is_file = poster_file.is_file() if exists else False
            size = poster_file.stat().st_size if exists and is_file else 0
            
            print(f"海报文件存在: {exists}")
            print(f"是文件: {is_file}")
            print(f"文件大小: {size} 字节")
            
            if exists and is_file and size > 0:
                poster_found = True
                print("✓ 海报文件有效")
            else:
                print("✗ 海报文件无效")
        else:
            print("✗ 未设置海报路径")
        
        # 列出目录中的所有图片文件
        parent_dir = Path(movie.path).parent
        print("\n目录中的图片文件:")
        image_files = []
        for item in parent_dir.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                size = item.stat().st_size
                image_files.append((item.name, size))
                status = "✓" if size > 0 else "✗"
                print(f"  {status} {item.name} ({size} 字节)")
        
        # 分析图片文件
        valid_images = [f for f, s in image_files if s > 0]
        empty_images = [f for f, s in image_files if s == 0]
        
        print(f"\n统计:")
        print(f"总图片文件: {len(image_files)}")
        print(f"有效图片: {len(valid_images)}")
        print(f"空图片: {len(empty_images)}")
        
        if empty_images:
            print("\n警告: 发现空图片文件:")
            for img in empty_images:
                print(f"  - {img}")
        
        if not poster_found and valid_images:
            print("\n建议: 目录中存在有效图片，但未被设置为海报")
            print("请确保图片文件命名为以下格式之一:")
            print("  - poster.jpg/png")
            print("  - folder.jpg/png")
            print("  - cover.jpg/png")
            print("  - front.jpg/png")
            print("  - coverart.jpg/png")
            print("  或与视频文件同名的图片")
        
        print("-" * 60)
    
    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)
    print("\n如果问题仍然存在，请检查:")
    print("1. 图片文件是否存在且大小大于0字节")
    print("2. 图片文件是否使用支持的命名格式")
    print("3. 图片文件是否位于电影文件所在的目录中")
    print("\n按 Enter 键退出...")
    input()

if __name__ == "__main__":
    main()
