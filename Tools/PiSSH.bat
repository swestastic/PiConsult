@echo off

REM Set your Raspberry Pi's IP address
set rpi_ip=192.168.6.91

REM Set your Raspberry Pi's username
set rpi_user=kylec

REM SSH to Raspberry Pi
ssh %rpi_user%@%rpi_ip%
