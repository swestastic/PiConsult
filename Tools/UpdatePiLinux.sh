#!/bin/bash

# Set the source directory path
src_dir=$(pwd)

# Set the destination directory path on Raspberry Pi
dest_dir="/consult_box"

# Set your Raspberry Pi's IP address
rpi_ip="192.168.6.91"

# Set your Raspberry Pi's username
rpi_user="kylec"

# Copy the directory recursively to Raspberry Pi
scp -r "$src_dir" "$rpi_user@$rpi_ip:$dest_dir" 
pause