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
1. Connect the SPI display to the Raspberry Pi.
2. Run the Python script: `python main.py`
3. The script will start recording data over serial and display it on the SPI display.

## Configuration
- Modify the `config.py` file to specify the serial port and other settings.

## Acknowledgements
Thanks to [fridlington](https://github.com/fridlington) for the K11 consult program which a lot of this is based off of and [gregsqueeb](https://github.com/gregsqueeb) for inspiring me to take this project on after seeing his implementation of a consult dash. The smaller form factor and design were inspired by the [Yashio Factory OkaChan](https://yashiofactory.co.jp/en/product/okachan-water-temp-3/)
