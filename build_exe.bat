@echo off
echo ========================================
echo   FastClip - 正在建立可執行檔 (.exe)
echo ========================================
echo 1. 正在安裝建置工具...
pip install pyinstaller

echo.
echo 2. 正在開始建置 (這需要幾分鐘，請稍候)...
:: --onefile: 包成單一檔案
:: --windowed: 執行時不顯示黑色的命令提示字元視窗
:: --name: 設定檔案名稱
:: --collect-all: 強制收集套件的所有中繼資料 (解決 MoviePy/imageio 報錯問題)
python -m PyInstaller --onefile --windowed --name FastClip_程式 --collect-all moviepy --collect-all imageio --collect-all yt-dlp main_gui.py

echo.
echo ========================================
echo   建置完成！
echo   請到「dist」資料夾找「FastClip_程式.exe」
echo ========================================
pause
