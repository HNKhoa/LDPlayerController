@echo off
cd /d %~dp0
git init
git add .
git commit -m "quick push"
git branch -M main
git remote add origin https://github.com/HNKhoa/LDPlayerController.git
git push -u origin main
pause
