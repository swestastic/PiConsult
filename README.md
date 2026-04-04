# PiConsult by Swestastic

## Description

This project uses Python to record data over serial on a Raspberry Pi and then display it on a small SPI display. Tested on 1990 NA/MT 300zx and 2001 NA/MT S15 Silvia ECUs. Should support most other similar-era cars, but this has not been tested.

## Current Functionality

### Mode 1: Data stream

![gauge image](images/gauge.gif)

Reads the following data from the ECU and can display live data on the screen. Displayed value changes with button press of Up/Down. Press Select to see the peak value stored during this drive.

- Engine RPM
- Wheel speed
- MAF voltage
- AAC duty cycle percentage
- Engine coolant temperature
- Battery voltage
- Injector timing
- Ignition timing
- Throttle Position

### Mode 2: DTCs

![dtc image](images/dtc.gif)

Reading of Data Trouble Codes (DTCs) and ability to clear stored DTCs. Cycle through stored DTCs with Up/Down. Press Select to clear stored ones.

### Mode 3: Settings

![settings image](images/settings.gif)

Settings adjustment mode with the following options:

- Speed Units (MPH/KPH)
- Temperature Units (F/C)
- Speed Correction
- Default Display
- RPM Warning threshold
- Coolant Temp Warning threshold

### Mode 4: Active Test

Active Testing mode with the following functions:

- Manual selection of coolant temp
- Increase/decrease injector pulse width
- Increase/decrease base ignition timing
- Increase/decrease IACV duty cycle
- Power balance test
- Fuel pump on/off
- Clear self learn trims

### Mode 5: Digital Bit Register

![digital bit image](images/digitalbit.gif)

View binary values in the ECU that tell you when solenoids or other switches are triggered

- EGR Solenoid
- Coolant Fan Low
- Coolant Fan Hi
- Closed Throttle
- Start Signal
- A/C Switch
- A/C Relay
- LH Bank Lean
- RH Bank Lean
- Fuel Pump Relay
- VTC Solenoid
- Wastegate Solenoid
- P/Reg Control
- Power Steering
- IACV/FICD Solenoid
- Park/Neutral Switch

## In Testing

- More active test options
- Display items based on ECU P/N (i.e. only display Power Balance cylinder 1-4 for 4-cylinder engines, display both left and right bank O2 sensors for V6 or V8, etc.)

## Prerequisites

- [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/) with Raspbian OS or similar
- [WaveShare LCD 1.9in screen](https://www.waveshare.com/wiki/1.9inch_LCD_Module)
- Python 3.x with packages from `requirements.txt`
- [Nissan Consult Cable](https://conceptzperformance.com/plms-developments-plms-nissan-consult-interface-usb-cable-nistune-datscan-etc-1005_p_5664.php) (There are cheaper consult readers on eBay for $15-$20, but I have not tested these)
- 3D Printer for printing the 3 included STL files (it is recommended to use a filament that will last inside of a car, such as PETG, ABS, or ASA, especially if it is parked outside)
- 4x Screws (Need to confirm size on these)
- [4x two pin 6x6x5 buttons](https://www.amazon.com/dp/B07X8T9D2Q)

## Software Installation

1. Set up your Pi with Raspbian or a similar OS (enabling SSH may be helpful for testing or debugging!)
2. Grab the latest release from [Releases](github.com/swestastic/PiConsult/releases)
3. Install the required Python packages on the Pi: `pip install -r requirements.txt`
4. Set ConsultStart.sh to run at boot (I used systemd method)
5. It is recommended to look into optimizing boot times on the Pi for a better user experience. Do your own research on this.

## Assembly and Installation

First connect all of your wires according to the following pinout:

**Missing Photo**

Next, install the pi into the main body. It should click onto the 4 pegs

**Missing Photo**

Place the OLED screen inside of the sandwich plate and connect the wires on the back

**Missing Photo**

Place the 4x buttons in the supplied slots and connect the wires on the back

**Missing Photo**

Insert the faceplate on top and fasten with 4x screws

**Missing Photo**

Connect to the Pi at the back of the case with a 5V power wire (USB charger in the cigarette lighter is easiest) and connect the consult cable to the USB port using an OTG cable.

**Missing Photo**

Connect the other end of the Consult cable underneath the dashboard

**Missing Photo**

Turn on the car and you should be ready to go! Make sure to configure settings as necessary

**Missing Photo**

## Usage

1. Connect the SPI display to the Raspberry Pi and ensure that SPI/I2C are enabled in settings.
2. Run the Python script: `python3 Main.py`. Alternatively run `./ConsultStart.sh` in terminal. Make sure to give ConsultStart.sh executable permission with `chmod +x ConsultStart.sh`
3. The script will start recording data over serial and display it on the SPI display.
4. You can set up SSH to connect to the device once it is on your network. The default address is `kylec@consult.local`.

## Local Desktop Mode (Laptop/Windows/macOS/Linux)

You can run the project without a Raspberry Pi display. A popup window is used as a virtual LCD, and on-screen Mode/Select/Up/Down buttons drive the same app logic. This is largely just used for testing, but you could use it functionally as well.

1. Install dependencies: `pip install -r requirements.txt`
2. Optional: force desktop mode with `CONSULT_LOCAL_UI=1`
3. Optional: set popup scale with `CONSULT_LOCAL_SCALE=2` (integer)
4. Run demo mode locally (no ECU required): `python Main.py --demo`

Notes:

- Desktop mode is selected automatically when Pi hardware dependencies are unavailable.
- On Raspberry Pi, hardware display and GPIO behavior remain the default unless `CONSULT_LOCAL_UI=1` is set.

## Configuration

- `Dependencies/config.py` contains hardware configuration for GPIO/SPI/I2C interfaces.
- `Dependencies/configJSON.json` contains runtime settings and defaults.

## Acknowledgements

Thanks to [fridlington](https://github.com/fridlington) for the K11 consult program which much of the data steaming is based off of and [gregsqueeb](https://github.com/gregsqueeb) for inspiring me to take this project on after seeing his implementation of a consult dash. The smaller form factor and design were inspired by the [Yashio Factory OkaChan](https://yashiofactory.co.jp/en/product/okachan-water-temp-3/). Thanks to everyone who is helping to keep these golden era Nissans alive!
