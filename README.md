# PiConsult by Swestastic

## Description
This project uses Python to record data over serial on a Raspberry Pi and then display it on a small SPI display.

## Prerequisites
- Raspberry Pi with Raspbian OS
- Python 3.x
- SPI display module
- Nissan Consult Cable

## Installation
1. Clone the repository: `git clone https://github.com/your-username/your-repo.git`
2. Install the required Python packages: `pip install -r requirements.txt`
3. Set ConsultStart.sh to run at boot

## Usage
1. Connect the SPI display to the Raspberry Pi and ensure that SPI/I2C are enabled in settings.
2. Run the Python script: `python3 main.py`. Alternatively run `./ConsultStart.sh` in terminal.
3. The script will start recording data over serial and display it on the SPI display.

## Configuration
- Modify `Resources/confs.ini` to specify the serial port and other settings. 
- `Resources/config.py` is configuration settings for the OLED displayas provided by the manufacturer.

## Acknowledgements
Thanks to [fridlington](https://github.com/fridlington) for the K11 consult program which a lot of this is based off of and [gregsqueeb](https://github.com/gregsqueeb) for inspiring me to take this project on after seeing his implementation of a consult dash. The smaller form factor and design were inspired by the [Yashio Factory OkaChan](https://yashiofactory.co.jp/en/product/okachan-water-temp-3/)

## Contact
- Your Name - [your-email@example.com](mailto:your-email@example.com)
- Project Link: [https://github.com/your-username/your-repo](https://github.com/your-username/your-repo)
