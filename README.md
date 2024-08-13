# PiConsult by Swestastic

## Description

This project uses Python to record data over serial on a Raspberry Pi and then display it on a small SPI display.

## Current Functionality

- Reads the following data from the ECU and can display live data on the screen. Displayed value changes with button press
  - Wheel speed
  - Engine RPM
  - Engine coolant temperature
  - Battery voltage
  - MAF voltage
  - AAC duty cycle percentage
  - Injector duty cycle percentage
  - Ignition timing

## Future Functionality

- More data able to be displayed
  - TPS percentage
  - TPS open/closed
  - Clutch switch on/off
  - Starter signal on/off
- Peak values saved and viewable with button press
- Data Trouble Codes (DTC) reading and resetting
- Test mode
  - Power Balance
  - EGR on/off
  - Fuel pump on/off
  - Clear fuel self learn
  - Probably others
- Blinking light or screen flash for RPM shift light or overheating
- Builtin settings mode with adjustments for the following
  - Gear ratio (factory and adjusted)
  - Tire size (factory and adjusted)
  - Injector size (factory and adjusted) 
  <!-- Idk how injector duty cycle behaves with a chipped ECU, which you would need if you're running different injector sizes --!>
  - Speed units: MPH or KPH
  - Temperature units: Farenheight or Celsius
- Data logging to SD card
- WiFi functionality to read data from phone
- Instant and average MPG based on rpm, speed, injector duty cycle, and injector size

## Prerequisites

- Raspberry Pi with Raspbian OS or similar
- Python 3.x
- SPI display module
- Nissan Consult Cable

## Installation

1. Clone the repository: `git clone https://github.com/swestastic/PiConsult.git`
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