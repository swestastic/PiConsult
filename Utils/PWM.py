import threading
import time
import RPi.GPIO as GPIO #type: ignore

class PWMOutput(threading.Thread):
    def __init__(self, pwm_pin, frequency=100, daemon=True):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.pwm_pin = pwm_pin
        self.frequency = frequency
        self.duty_cycle = 0
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pwm_pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
        self.pwm.start(0)  # Start with 0% duty cycle
        
        self.start()
    
    def run(self):
        while True:
            # The thread loop for controlling PWM output
            self.update_pwm(self.duty_cycle)
            time.sleep(0.1)  # Adjust as needed
    
    def update_pwm(self, data):
        try:
            # Convert data to a PWM duty cycle (0 to 100)
            duty_cycle = float(data)  # Ensure your data can be converted to a float
            duty_cycle = max(0, min(100, duty_cycle))  # Clamp to valid duty cycle range
            self.pwm.ChangeDutyCycle(duty_cycle)
        except ValueError:
            print("Invalid data for PWM:", data)
    
    def set_duty_cycle(self, duty_cycle):
        # Call this method to update the duty cycle from outside the class
        self.duty_cycle = duty_cycle
    
    def stop_pwm(self):
        # Stop the PWM when the application is closing.
        self.pwm.stop()
        GPIO.cleanup()



# ## Example Usage:
# from Main_Bare_Imports.PWM import PWMOutput
# pwm_output = PWMOutput(pwm_pin=18)

# In the main loop:
# pwm_output.set_duty_cycle(R.RPM_Value)  # Set the duty cycle to 50%


# # To stop PWM:
# pwm_output.stop_pwm()