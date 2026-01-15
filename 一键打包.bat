@echo off
chcp 65001
echo ========================================================
echo        Weibo SuperTopic V3.0 一键构建脚本
echo ========================================================
echo.

echo 1. 正在检查 PyInstaller 环境...
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 PyInstaller，正在为您安装...
    pip install pyinstaller
)

echo.
echo 2. 开始清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo 3. 正在打包 (这可能需要几分钟，请耐心等待)...
echo    - 收集 CustomTkinter 资源库
echo    - 隐藏控制台窗口 (--noconsole)
echo    - 生成单文件 (--onefile)
echo.

:: 核心打包命令
:: --collect-all customtkinter: 必须参数，否则打包后界面无法启动
:: --noconfirm: 不询问直接覆盖
:: --windowed: 无黑框模式
pyinstaller --noconfirm --onefile --windowed --name "WeiboSignV3" --collect-all customtkinter weibo_checkin.py

echo.
echo 4. 清理临时文件...
if exist build rmdir /s /q build
if exist *.spec del *.spec

echo.
echo ========================================================
echo    ✅ 打包成功！
echo    可执行文件位于 dist 文件夹内: WeiboSignV3.exe
echo ========================================================
echo.
pause