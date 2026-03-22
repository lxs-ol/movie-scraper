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
    (os.path.join(current_dir, "updater.py"), "updater.py"),
    (os.path.join(current_dir, "ai_helper.py"), "ai_helper.py"),
    (platforms_dir, "platforms"),
    (imageformats_dir, "imageformats"),
]

# 添加图标文件
if os.path.exists(os.path.join(current_dir, "logo.ico")):
    include_files.append((os.path.join(current_dir, "logo.ico"), "logo.ico"))
if os.path.exists(os.path.join(current_dir, "logo.png")):
    include_files.append((os.path.join(current_dir, "logo.png"), "logo.png"))
if os.path.exists(os.path.join(current_dir, "李先生ol.png")):
    include_files.append((os.path.join(current_dir, "李先生ol.png"), "李先生ol.png"))

# 检查文件是否存在
for source, target in include_files:
    if not os.path.exists(source):
        print(f"Warning: Source file not found: {source}")
    else:
        print(f"Including: {source} -> {target}")

# 获取 Python 标准库路径
import site
import distutils.sysconfig
stdlib_path = distutils.sysconfig.get_python_lib(standard_lib=True)

# 添加 Python 标准库中的必要文件
include_files.extend([
    # 添加 Python 核心 DLL
    (os.path.join(os.path.dirname(sys.executable), "python3.dll"), "python3.dll"),
    (os.path.join(os.path.dirname(sys.executable), "python314.dll"), "python314.dll"),
    # 添加 PyQt5.uic.widget-plugins
    (os.path.join(pyqt5_path, "uic", "widget-plugins"), "lib/PyQt5/uic/widget-plugins"),
])

# 排除 email 模块，避免 Python 3.14 兼容性问题
excludes = [
    "email",
    "email.*",
    "urllib3.contrib.pyopenssl",
]

# 添加更多必要的模块
packages = [
    "encodings", 
    "encodings.utf_8", 
    "encodings.latin_1",
    "encodings.ascii",
    "encodings.cp1252",
    "PyQt5", 
    "PyQt5.QtCore",
    "PyQt5.QtGui", 
    "PyQt5.QtWidgets",
    "PyQt5.sip",
    "requests", 
    "json", 
    "os", 
    "sys", 
    "time", 
    "logging", 
    "re", 
    "pathlib", 
    "typing", 
    "dataclasses", 
    "functools", 
    "xml", 
    "xml.etree",
    "xml.etree.ElementTree",
    "collections", 
    "copy",
    "urllib3",
    "charset_normalizer",
    "idna",
    "certifi",
    "http",
    "http.client",
]

setup(
    name="Movie Scraper",
    version="1.1.6",
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
            "packages": packages,
            "include_files": include_files,
            "build_exe": "build_single_exe",
            "optimize": 0,
            "zip_include_packages": [],
            "zip_exclude_packages": ["*"],
            "silent_level": 0,
            "excludes": excludes
        },
        "bdist_msi": {}
    }
)
