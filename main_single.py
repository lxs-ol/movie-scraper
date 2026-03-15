import sys
import os

# 设置Qt插件路径
if hasattr(sys, 'frozen'):
    # 如果是打包后的exe
    base_path = os.path.dirname(sys.executable)
else:
    # 如果是开发环境
    base_path = os.path.dirname(os.path.abspath(__file__))

# 添加Qt插件路径
qt_plugins_path = os.path.join(base_path, 'plugins')
if os.path.exists(qt_plugins_path):
    os.environ['QT_PLUGIN_PATH'] = qt_plugins_path

# 添加imageformats路径
imageformats_path = os.path.join(base_path, 'imageformats')
if os.path.exists(imageformats_path):
    os.environ['QT_PLUGIN_PATH'] = os.pathsep.join([os.environ.get('QT_PLUGIN_PATH', ''), imageformats_path])

# 导入主程序
from gui import MovieScraper
from PyQt5.QtWidgets import QApplication
import sys

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MovieScraper()
    window.show()
    sys.exit(app.exec_())
