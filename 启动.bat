@echo off
cd /d "C:\Users\%USERNAME%\OneDrive\桌面\简历系统"
echo 🚀 启动简历筛选系统...
start http://localhost:5000
python app.py
pause
