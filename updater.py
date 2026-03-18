import os
import sys
import json
import requests
import subprocess
import tempfile
from typing import Optional, Tuple
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QTextEdit
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt


CURRENT_VERSION = "1.1.0"
GITHUB_REPO = "lxs-ol/movie-scraper"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class CheckUpdateThread(QThread):
    update_available = pyqtSignal(bool, str, str, str)
    
    def run(self):
        try:
            response = requests.get(GITHUB_API_URL, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get('tag_name', '').replace('v', '')
                release_notes = data.get('body', '暂无更新说明')
                download_url = None
                
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                
                has_update = self._compare_versions(latest_version, CURRENT_VERSION)
                self.update_available.emit(has_update, latest_version, release_notes, download_url or '')
            else:
                self.update_available.emit(False, '', '', '')
        except Exception as e:
            print(f"检查更新失败: {e}")
            self.update_available.emit(False, '', '', '')
    
    def _compare_versions(self, latest: str, current: str) -> bool:
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            for i in range(max(len(latest_parts), len(current_parts))):
                l = latest_parts[i] if i < len(latest_parts) else 0
                c = current_parts[i] if i < len(current_parts) else 0
                if l > c:
                    return True
                elif l < c:
                    return False
            return False
        except:
            return False


class DownloadUpdateThread(QThread):
    progress_update = pyqtSignal(int)
    download_complete = pyqtSignal(bool, str)
    
    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url
    
    def run(self):
        try:
            temp_dir = tempfile.gettempdir()
            filename = os.path.basename(self.download_url)
            save_path = os.path.join(temp_dir, filename)
            
            response = requests.get(self.download_url, stream=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_update.emit(progress)
            
            self.download_complete.emit(True, save_path)
        except Exception as e:
            print(f"下载更新失败: {e}")
            self.download_complete.emit(False, str(e))


class UpdateDialog(QDialog):
    def __init__(self, parent=None, latest_version: str = '', release_notes: str = '', download_url: str = ''):
        super().__init__(parent)
        self.download_url = download_url
        self.setWindowTitle('发现新版本')
        self.setMinimumWidth(450)
        self.setup_ui(latest_version, release_notes)
    
    def setup_ui(self, latest_version: str, release_notes: str):
        layout = QVBoxLayout(self)
        
        info_label = QLabel(f'<h2>发现新版本 {latest_version}</h2>')
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        current_label = QLabel(f'<p>当前版本: {CURRENT_VERSION}</p>')
        current_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(current_label)
        
        layout.addWidget(QLabel('<b>更新内容:</b>'))
        
        notes_edit = QTextEdit()
        notes_edit.setReadOnly(True)
        notes_edit.setPlainText(release_notes)
        notes_edit.setMaximumHeight(150)
        layout.addWidget(notes_edit)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel()
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton('下载并安装')
        self.download_btn.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_btn)
        
        self.later_btn = QPushButton('稍后提醒')
        self.later_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.later_btn)
        
        layout.addLayout(button_layout)
    
    def start_download(self):
        if not self.download_url:
            QMessageBox.warning(self, '错误', '未找到下载链接')
            return
        
        self.download_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText('正在下载更新...')
        
        self.download_thread = DownloadUpdateThread(self.download_url)
        self.download_thread.progress_update.connect(self.progress_bar.setValue)
        self.download_thread.download_complete.connect(self.on_download_complete)
        self.download_thread.start()
    
    def on_download_complete(self, success: bool, result: str):
        if success:
            self.status_label.setText('下载完成，正在启动安装程序...')
            self.progress_bar.setValue(100)
            
            try:
                if os.name == 'nt':
                    os.startfile(result)
                else:
                    subprocess.Popen(['xdg-open', result])
                
                self.accept()
                
                if self.parent():
                    self.parent().close()
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'启动安装程序失败: {e}')
        else:
            QMessageBox.critical(self, '下载失败', f'下载更新失败: {result}')
            self.download_btn.setEnabled(True)
            self.later_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setVisible(False)


class NoUpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('检查更新')
        self.setMinimumWidth(300)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        info_label = QLabel(f'<h3>当前已是最新版本</h3>')
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        version_label = QLabel(f'<p>版本: {CURRENT_VERSION}</p>')
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        ok_btn = QPushButton('确定')
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)


class AutoUpdater:
    def __init__(self, parent=None):
        self.parent = parent
        self.check_thread = None
    
    def check_for_updates(self, silent: bool = False):
        self.silent = silent
        self.check_thread = CheckUpdateThread()
        self.check_thread.update_available.connect(self._on_update_checked)
        self.check_thread.start()
    
    def _on_update_checked(self, has_update: bool, latest_version: str, release_notes: str, download_url: str):
        if has_update:
            dialog = UpdateDialog(self.parent, latest_version, release_notes, download_url)
            dialog.exec_()
        elif not self.silent:
            dialog = NoUpdateDialog(self.parent)
            dialog.exec_()
