import sys
import os
import encodings
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication, QLibraryInfo

def setup_qt_paths():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        plugins_dir = os.path.join(app_dir, 'lib', 'PyQt5', 'Qt5', 'plugins')
        if os.path.exists(plugins_dir):
            os.environ['QT_PLUGIN_PATH'] = plugins_dir
            QCoreApplication.addLibraryPath(plugins_dir)
    else:
        # 非冻结状态下，直接使用PyQt5安装目录中的plugins文件夹
        pyqt5_dir = os.path.dirname(__import__('PyQt5').__file__)
        plugins_dir = os.path.join(pyqt5_dir, 'Qt5', 'plugins')
        if os.path.exists(plugins_dir):
            os.environ['QT_PLUGIN_PATH'] = plugins_dir
            QCoreApplication.addLibraryPath(plugins_dir)
        else:
            # 如果上面的路径不存在，尝试使用QLibraryInfo
            plugins_dir = QLibraryInfo.location(QLibraryInfo.PluginsPath)
            if os.path.exists(plugins_dir):
                os.environ['QT_PLUGIN_PATH'] = plugins_dir
                QCoreApplication.addLibraryPath(plugins_dir)

if __name__ == '__main__':
    setup_qt_paths()
    
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    from gui import MovieScraperGUI
    window = MovieScraperGUI()
    window.show()
    sys.exit(app.exec_())
