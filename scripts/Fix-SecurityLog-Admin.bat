@echo off
title Secure Monitor - Fix Security Log
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Fix-SecurityLog-Admin.ps1"
pause
