@echo off
REM Wrapper for scheduled watchlist runs. Edit cadence via schtasks, not here.
cd /d "%~dp0"
if not exist logs mkdir logs
"C:\Users\tsiol\AppData\Local\Programs\Python\Python313\python.exe" jobs.py watchlist >> "logs\watchlist.log" 2>&1
