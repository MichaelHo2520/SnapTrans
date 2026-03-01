import os
import sys
import requests
import zipfile
import threading
import tempfile
import subprocess
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QTimer

GITHUB_REPO = "MichaelHo2520/SnapTrans"

def get_latest_release(repo):
    """取得 GitHub 上的最新 Release 資訊"""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"檢查更新失敗: {e}")
        return None

def download_file(url, target_path, progress_callback=None):
    """下載檔案並提供進度回呼"""
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024 * 8 
        downloaded = 0
        
        with open(target_path, 'wb') as file:
            for data in response.iter_content(block_size):
                file.write(data)
                downloaded += len(data)
                if total_size > 0 and progress_callback:
                    progress_callback(int(downloaded * 100 / total_size))
        return True
    except Exception as e:
        print(f"下載失敗: {e}")
        return False

def extract_and_apply_update(zip_path):
    """解壓縮並建立/執行替換腳本"""
    try:
        extract_dir = os.path.join(tempfile.gettempdir(), "snaptrans_update")
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # 尋找解壓縮出來的 SnapTrans.exe
        new_exe_path = None
        for root, dirs, files in os.walk(extract_dir):
            if "SnapTrans.exe" in files:
                new_exe_path = os.path.join(root, "SnapTrans.exe")
                break
                
        if not new_exe_path:
            return False, "在更新檔中找不到主程式！"
            
        # 準備目前的執行路徑
        current_exe_path = sys.executable
        if not current_exe_path.lower().endswith('.exe'):
            # 如果是在開發環境跑 python main.py，不執行覆蓋
            return False, "目前非打包環境，無法執行覆蓋更新。"
            
        current_dir = os.path.dirname(current_exe_path)
        bat_path = os.path.join(current_dir, "update_apply.bat")
        
        # 產生背景覆蓋腳本
        # 腳本邏輯: 等待 2 秒讓主程式關閉 -> 把新的 exe 複製過去 -> 執行新的 exe -> 刪除腳本自己
        bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
ping 127.0.0.1 -n 2 > nul
copy /Y "{new_exe_path}" "{current_exe_path}"
start "" "{current_exe_path}"
del "%~f0"
"""
        with open(bat_path, "w", encoding='utf-8') as f:
            f.write(bat_content)
            
        # 靜默執行腳本 
        # CREATE_NO_WINDOW = 0x08000000 隱藏 cmd 視窗
        subprocess.Popen([bat_path], creationflags=0x08000000)
        
        return True, None
    except Exception as e:
        return False, str(e)

def parse_version(version_str):
    """將 v1.2.3 轉為整數 tuple (1, 2, 3) 方便比對"""
    clean_version = version_str.lower().replace('v', '')
    try:
        return tuple(map(int, clean_version.split('.')))
    except:
        return (0, 0, 0)

def check_for_updates(app_instance, current_version):
    """主打更新檢查與 UI 互動流程"""
    app_instance.tray_icon.showMessage("檢查更新", "正在連接 GitHub 檢查最新版本...", 0, 2000)
    
    # 建立一個隱藏的 QWidget 作為 MessageBox 的 parent，確保它能在最上層顯示且不報錯
    from PyQt5.QtWidgets import QWidget
    msg_parent = QWidget()
    msg_parent.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
    msg_parent.setAttribute(Qt.WA_TranslucentBackground)
    
    release_info = get_latest_release(GITHUB_REPO)
    if not release_info:
        QMessageBox.warning(msg_parent, "更新失敗", "無法連接伺服器檢查更新。")
        return
        
    latest_version = release_info.get("tag_name", "")
    if parse_version(latest_version) <= parse_version(current_version):
        QMessageBox.information(msg_parent, "檢查更新", f"目前已是最新版本 ({current_version})！")
        return
        
    # 找到微更新檔案 (SnapTrans-Update-xxx.zip)
    assets = release_info.get("assets", [])
    update_asset_url = None
    for asset in assets:
        if "Update" in asset["name"] and asset["name"].endswith(".zip"):
            update_asset_url = asset["browser_download_url"]
            break
            
    if not update_asset_url:
        QMessageBox.warning(msg_parent, "更新錯誤", "找到新版本，但發布包中找不到微更新檔案 (Update.zip)。\n請到 GitHub 網頁手動下載完整版。")
        return
        
    # 跳出更新確認對話框
    body = release_info.get("body", "無提供更新日誌")
    reply = QMessageBox.question(
        msg_parent, 
        "發現新版本！",
        f"發現新版本 {latest_version}！是否立即下載更新？\n\n更新內容：\n{body}",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )
    
    if reply == QMessageBox.No:
        return
        
    # 開始下載
    progress_dialog = QProgressDialog("正在下載更新檔案...", "取消", 0, 100, msg_parent)
    progress_dialog.setWindowTitle("下載中")
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setMinimumDuration(0)
    
    zip_path = os.path.join(tempfile.gettempdir(), "snaptrans_update.zip")
    
    # 用 threading 跑下載以防 UI 凍結
    download_success = False
    
    def download_task():
        nonlocal download_success
        def update_progress(pct):
            pass
        download_success = download_file(update_asset_url, zip_path)
        
    thread = threading.Thread(target=download_task)
    thread.start()
    
    # 使用 QTimer 輪詢檢測進度並保持 UI 響應
    def check_thread():
        if thread.is_alive():
            QTimer.singleShot(100, check_thread)
            val = progress_dialog.value() + 1
            if val > 99: val = 0
            progress_dialog.setValue(val)
        else:
            progress_dialog.close()
            if download_success:
                apply_reply = QMessageBox.information(
                    msg_parent,
                    "下載完成",
                    "下載完成！程式即將關閉並套用更新。",
                    QMessageBox.Ok
                )
                success, err = extract_and_apply_update(zip_path)
                if success:
                    from PyQt5.QtWidgets import QApplication
                    QApplication.quit()
                    sys.exit(0)
                else:
                    QMessageBox.warning(msg_parent, "更新失敗", f"套用更新發生錯誤：\n{err}")
            else:
                QMessageBox.warning(msg_parent, "下載失敗", "下載更新檔案時發生錯誤。")
                
    check_thread()
