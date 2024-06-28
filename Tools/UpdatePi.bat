@echo off

REM Set the source directory path
set src_dir=%cd%

REM Set the destination directory path on Raspberry Pi
set dest_dir=/consult_box

REM Set your Raspberry Pi's IP address
set rpi_ip=192.168.7.181

REM Set your Raspberry Pi's username
set rpi_user=kylec

REM Copy the directory recursively to Raspberry Pi
scp -r %src_dir%\* %rpi_user%@%rpi_ip%:%dest_dir%

pause