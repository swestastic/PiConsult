# PiConsult by Swestastic

## Description

This project uses Python to record data over serial on a Raspberry Pi and then display it on a small SPI display. Tested on a 1990 NA 300zx with the 8-bit ecu. Should work on 16-bit ECUs and other similar-era Nissans like Skylines, Cefiros, 240sx/180sx/Silvia, and some others, but this has not been tested.

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
- Safe shutdown button (clear and power off the screen, then send halt command to ECU, halt the loops and shutdown the pi)
- DC output (PWM -> DAC) to daisy chain PiConsult to Flock gauge or similar

## Known Bugs

- Data is displayed on screen as floats (e.g. rpm shows as 750.0, 3500.0, etc). I think this has to do with WriteText() and the string conversion for the numbers maybe?
- Peak data only shows for one frame when the button is pressed
- Some values may be displayed incorrectly. Need to evaluate and confirm accuracy from the data received

## Prerequisites

- [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/) with Raspbian OS or similar
- [WaveShare OLED 2.42in screen](https://www.waveshare.com/wiki/2.42inch_OLED_Module)
- Python 3.x with packages from `requirements.txt`
- [Nissan Consult Cable](https://conceptzperformance.com/plms-developments-plms-nissan-consult-interface-usb-cable-nistune-datscan-etc-1005_p_5664.php) (There are cheaper consult readers on eBay for $15-$20, but I have not tested these)
- 3D Printer for printing the 3 included STL files (it is recommended with filament that will last inside of a car, such as PETG, ABS, or ASA)
- 4x Screws (Need to confirm size on these)
- [4x two pin 6x6x5 buttons](https://www.amazon.com/dp/B07X8T9D2Q)

## Software Installation
1. Set up your Pi with Raspbian or a similar OS (enabling SSH may be helpful for testing or debugging!)
1. Grab the latest release from [Releases](github.com/swestastic/PiConsult/releases)
2. Install the required Python packages on the Pi: `pip install -r requirements.txt`
3. Set ConsultStart.sh to run at boot
4. It is recommended to look into optimizing boot times on the Pi for a better user experience. Do your own research on this.

## Assembly and Installation

First connect all of your wires according to the following pinout:

INSERT PICTURE OF PINOUT

Next, install the pi into the main body. It should click onto the 4 pegs

INSERT PICTURE OF PI INSTALLED

Place the OLED screen inside of the sandwich plate and connect the wires on the back

INSERT PICTURE OF SCREEN ASSEMBLY

Place the 4x buttons in the supplied slots and connect the wires on the back

INSERT PICTURE OF BUTTONS

Insert the faceplate on top and fasten with 4x screws

INSERT PICTURE OF ASSEMBLED

Connect to the Pi at the back of the case with a 5V power wire (USB charger in the cigarette lighter is easiest) and connect the consult cable to the USB port using an OTG cable.

INSERT PICTURE OF WIRES

Connect the other end of the Consult cable underneath the dashboard

INSERT PICTURE OF PORT

Turn on the car and you should be ready to go! Make sure to configure settings as necessary

INSERT PICTURE OF RUNNING ASSEMBLY MOUNTED TO CAR



## Usage

1. Connect the SPI display to the Raspberry Pi and ensure that SPI/I2C are enabled in settings.
2. Run the Python script: `python3 main.py`. Alternatively run `./ConsultStart.sh` in terminal.
3. The script will start recording data over serial and display it on the SPI display.

## Configuration

- `Resources/config.py` is configuration settings for the OLED displayas provided by the manufacturer.
- `configJSON.json` contains default values for variables, most of these are adjustable on the device itself.

## Acknowledgements

Thanks to [fridlington](https://github.com/fridlington) for the K11 consult program which much of the data steaming is based off of and [gregsqueeb](https://github.com/gregsqueeb) for inspiring me to take this project on after seeing his implementation of a consult dash. The smaller form factor and design were inspired by the [Yashio Factory OkaChan](https://yashiofactory.co.jp/en/product/okachan-water-temp-3/). Thanks to everyone who is helping to keep these golden era Nissans alive!
