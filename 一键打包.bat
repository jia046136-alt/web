@echo off
chcp 65001
echo ========================================================
echo        Weibo V3.3 完美图标版构建脚本
echo ========================================================
echo.

echo 1. 环境自检...
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    pip install pyinstaller
)

echo.
echo 2. 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo 3. 正在打包 (这步最关键)...
echo    [图标] --icon: 设置 EXE 文件外观
echo    [数据] --add-data: 将 ico 放入 EXE 内部供运行时读取
echo.

:: 核心命令
:: --add-data "logo.ico;." : Windows下用分号分隔，将logo.ico放入程序运行根目录
pyinstaller --noconfirm --onefile --windowed --name "WeiboSignPro" --icon="logo.ico" --add-data "logo.ico;." --collect-all customtkinter weibo_checkin.py

echo.
echo 4. 清理临时文件...
if exist build rmdir /s /q build
if exist *.spec del *.spec

echo.
echo ========================================================
echo    ✅ 打包完成！
echo    去 dist 文件夹打开 WeiboSignPro.exe 看看吧
echo    现在托盘和任务栏应该都是你的 Logo 了！
echo ========================================================
echo.
pause