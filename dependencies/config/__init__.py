import time
import importlib

try:
    SMBus = importlib.import_module("smbus").SMBus
except ModuleNotFoundError:
    try:
        SMBus = importlib.import_module("smbus2").SMBus
    except ModuleNotFoundError:
        class SMBus:  # type: ignore[no-redef]
            def __init__(self, *_args, **_kwargs):
                return None

            def write_byte_data(self, *_args, **_kwargs):
                return None

            def close(self):
                return None

try:
    spidev = importlib.import_module("spidev")
except ModuleNotFoundError:
    class _FallbackSpiDev:
        def __init__(self, *args, **kwargs):
            self.max_speed_hz = 0
            self.mode = 0

        def writebytes(self, _data):
            return None

        def close(self):
            return None

    class _FallbackSpiModule:
        SpiDev = _FallbackSpiDev

    spidev = _FallbackSpiModule()

try:
    _gpiozero = importlib.import_module("gpiozero")
    DigitalOutputDevice = _gpiozero.DigitalOutputDevice
    DigitalInputDevice = _gpiozero.DigitalInputDevice
except ModuleNotFoundError:
    class DigitalOutputDevice:
        def __init__(self, *_args, **_kwargs):
            self.value = 0

        def on(self):
            self.value = 1

        def off(self):
            self.value = 0

    class DigitalInputDevice:
        def __init__(self, *_args, **_kwargs):
            self.value = 0

Device_SPI = 1
Device_I2C = 0

# Consult box button GPIO assignments
MODE_BUTTON_PIN = 26
SELECT_BUTTON_PIN = 16
UP_BUTTON_PIN = 23
DOWN_BUTTON_PIN = 17
BUTTON_HOLD_TIME_SECONDS = 0.5
BUTTON_BOUNCE_TIME_SECONDS = 0.05

# UI font sizing
FOOTER_FONT_SIZE = 14 # Used for footers and secondary text in the menu
MENU_FONT_SIZE = 18 # Menu list items
MENU_TITLE_FONT_SIZE = 24 # Titles atop menus
GAUGE_RANGE_FONT_SIZE = 18 # Min/Max values on gauge display
GAUGE_VALUE_FONT_SIZE = 40 # Value text on gauge display
VALUE_ONLY_FONT_SIZE = 50 # Value text when in "Value Only" display mode

SOFTWARE_VERSION = "1.0.0"


class RaspberryPi:
    def __init__(self, spi=spidev.SpiDev(0, 0), spi_freq=10000000, rst=27, dc=25, bl=18, bl_freq=1000, i2c=None):
        self.INPUT = False
        self.OUTPUT = True

        self.SPEED = spi_freq

        if Device_SPI == 1:
            self.Device = Device_SPI
            self.spi = spi
        else:
            self.Device = Device_I2C
            self.address = 0x3c
            self.bus = SMBus(1)

        self.RST_PIN = self.gpio_mode(rst, self.OUTPUT)
        self.DC_PIN = self.gpio_mode(dc, self.OUTPUT)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def gpio_mode(self, Pin, Mode, pull_up=None, active_state=True):
        if Mode:
            return DigitalOutputDevice(Pin, active_high=True, initial_value=False)
        return DigitalInputDevice(Pin, pull_up=pull_up, active_state=active_state)

    def digital_write(self, Pin, value):
        if value:
            Pin.on()
        else:
            Pin.off()

    def digital_read(self, Pin):
        return Pin.value

    def spi_writebyte(self, data):
        self.spi.writebytes([data[0]])

    def i2c_writebyte(self, reg, value):
        self.bus.write_byte_data(self.address, reg, value)

    def module_init(self):
        self.digital_write(self.RST_PIN, False)
        if self.Device == Device_SPI:
            self.spi.max_speed_hz = self.SPEED
            self.spi.mode = 0b11
        self.digital_write(self.DC_PIN, False)
        return 0

    def module_exit(self):
        if self.Device == Device_SPI:
            self.spi.close()
        else:
            self.bus.close()
        self.digital_write(self.RST_PIN, False)
        self.digital_write(self.DC_PIN, False)


### END OF FILE ###