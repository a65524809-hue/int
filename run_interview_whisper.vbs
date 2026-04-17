' Run InterviewWhisper with no console window. Double-click this file or run from Start.
Set WshShell = CreateObject("WScript.Shell")
scriptDir = Replace(WScript.ScriptFullName, WScript.ScriptName, "")
WshShell.CurrentDirectory = scriptDir
WshShell.Run "pythonw.exe main.py", 0, False
