@ECHO OFF
ECHO Launch Anaconda and python GUI...
%windir%\system32\cmd.exe "/C C:\ProgramData\Anaconda3\Scripts\activate.bat thermoelectrics_env && python GUI.py"
PAUSE