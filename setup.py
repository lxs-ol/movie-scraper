from cx_Freeze import setup, Executable
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))

pyqt5_path = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages", "PyQt5")
if not os.path.exists(pyqt5_path):
    import PyQt5
    pyqt5_path = os.path.dirname(PyQt5.__file__)

plugins_path = os.path.join(pyqt5_path, "Qt5", "plugins")

# 确保 platforms 目录存在
platforms_dir = os.path.join(plugins_path, "platforms")
if not os.path.exists(platforms_dir):
    print(f"Error: Platforms directory not found at {platforms_dir}")
    sys.exit(1)

# 确保 imageformats 目录存在
imageformats_dir = os.path.join(plugins_path, "imageformats")
if not os.path.exists(imageformats_dir):
    print(f"Error: Imageformats directory not found at {imageformats_dir}")
    sys.exit(1)

include_files = [
    (os.path.join(current_dir, "api.py"), "api.py"),
    (os.path.join(current_dir, "scanner.py"), "scanner.py"),
    (os.path.join(current_dir, "gui.py"), "gui.py"),
    (os.path.join(current_dir, "李先生ol.png"), "李先生ol.png"),
    (platforms_dir, "platforms"),
    (imageformats_dir, "imageformats"),
]

# 检查文件是否存在
for source, target in include_files:
    if not os.path.exists(source):
        print(f"Warning: Source file not found: {source}")
    else:
        print(f"Including: {source} -> {target}")

setup(
    name="Movie Scraper",
    version="1.0",
    description="本地电影刮削工具",
    executables=[
        Executable(
            "main.py",
            base="gui",
            target_name="Movie Scraper.exe",
            icon="logo.ico" if os.path.exists("logo.ico") else None
        )
    ],
    options={
        "build_exe": {
            "packages": ["encodings", "PyQt5", "requests", "json", "os", "sys", "time", "logging", "re", "pathlib", "typing", "dataclasses", "functools", "xml", "collections", "copy"],
            "include_files": include_files,
            "build_exe": "build_single_exe",
            "optimize": 2,
            "zip_include_packages": ["*"],
            "zip_exclude_packages": [],
            "silent_level": 0
        },
        "bdist_msi": {}
    }
)
