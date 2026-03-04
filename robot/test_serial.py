import serial
import time
import subprocess

# Configure your Arduino port
ARDUINO_PORT = '/dev/ttyUSB0'  # Change to COM3, COM4, /dev/ttyUSB0, etc.
BAUD_RATE = 9600

# Connect to Arduino
print(f"Connecting to Arduino on {ARDUINO_PORT}...")
arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # Wait for Arduino to reset
print("Connected!")

# Send 'f' signal
print("Sending 'f' signal...")
arduino.write(b'f\n')
print("'f' signal sent!")
time.sleep(2)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'l' signal...")
arduino.write(b'l\n')
print("'l' signal sent!")
time.sleep(0.8)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'f' signal...")
arduino.write(b'f\n')
print("'f' signal sent!")
time.sleep(2)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'l' signal...")
arduino.write(b'l\n')
print("'l' signal sent!")
time.sleep(0.05)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

# ARM TASK
time.sleep(1)

print("Sending 'l' signal...")
arduino.write(b'l\n')
print("'l' signal sent!")
time.sleep(1.3)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'f' signal...")
arduino.write(b'f\n')
print("'f' signal sent!")
time.sleep(1.9)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'r' signal...")
arduino.write(b'r\n')
print("'r' signal sent!")
time.sleep(0.7)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'f' signal...")
arduino.write(b'f\n')
print("'f' signal sent!")
time.sleep(1.5)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")

print("Sending 'r' signal...")
arduino.write(b'r\n')
print("'r' signal sent!")
time.sleep(1.2)

print("Sending 's' signal...")
arduino.write(b's\n')
print("'s' signal sent!")


# Close connection
arduino.close()
print("Done!")
