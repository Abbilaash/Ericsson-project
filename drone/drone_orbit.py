from dronekit import connect, VehicleMode
from pymavlink import mavutil
import time

# -------------------------------
# CONNECT TO VEHICLE
# -------------------------------
print("Connecting to Pixhawk...")
vehicle = connect('COM11', baud=9600, wait_ready=True)
# For real hardware, use:
# vehicle = connect('/dev/ttyACM0', baud=57600, wait_ready=True)

print("Connected")

# -------------------------------
# CHECK MISSION EXISTS
# -------------------------------
cmds = vehicle.commands
cmds.download()
cmds.wait_ready()

if cmds.count == 0:
    print("No mission found on vehicle!")
    vehicle.close()
    exit(1)

print(f"Mission with {cmds.count} waypoints found")

# -------------------------------
# WAIT UNTIL ARMABLE
# -------------------------------
while not vehicle.is_armable:
    print("Waiting for vehicle to initialise...")
    time.sleep(1)

# -------------------------------
# ARM VEHICLE
# -------------------------------
print("Arming motors")
vehicle.mode = VehicleMode("GUIDED")
vehicle.armed = True

while not vehicle.armed:
    print("Waiting for arming...")
    time.sleep(1)

print("Vehicle armed")

# -------------------------------
# REQUIRED FOR COPTER (on ground)
# MAV_CMD_MISSION_START
# -------------------------------
print("Starting mission")
vehicle._master.mav.command_long_send(
    vehicle._master.target_system,
    vehicle._master.target_component,
    mavutil.mavlink.MAV_CMD_MISSION_START,
    0,
    0, 0, 0, 0, 0, 0, 0
)

time.sleep(1)

# -------------------------------
# SWITCH TO AUTO MODE
# -------------------------------
vehicle.mode = VehicleMode("AUTO")

while vehicle.mode.name != "AUTO":
    print("Waiting for AUTO mode...")
    time.sleep(1)

print("Mission started in AUTO mode")

# -------------------------------
# MONITOR MISSION PROGRESS
# -------------------------------
while True:
    next_wp = vehicle.commands.next
    print(f"Current Waypoint: {next_wp}")

    if next_wp == cmds.count:
        print("Final waypoint reached")
        break

    time.sleep(2)

# -------------------------------
# MISSION COMPLETE
# -------------------------------
print("Mission completed")
print("Vehicle mode:", vehicle.mode.name)

vehicle.close()
print("Connection closed")
