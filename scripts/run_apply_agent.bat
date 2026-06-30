@echo off
REM Nightly autonomous apply agent. Wire to Windows Task Scheduler, e.g.:
REM   schtasks /Create /SC DAILY /TN "JobsBot Apply Agent" ^
REM     /TR "C:\Users\tsiol\jobs-bot\scripts\run_apply_agent.bat" /ST 02:00
REM The machine must be awake at the scheduled time.
cd /d C:\Users\tsiol\jobs-bot
python apply_agent.py >> apply_agent.log 2>&1
