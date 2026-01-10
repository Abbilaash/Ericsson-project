from pymavlink import mavutil
import time
import math

# --------------------------------------------------
# USER INPUTS
# --------------------------------------------------
CONNECTION = "COM11"     # or /dev/ttyACM0
BAUD = 9600

CENTER_X = 0.0           # meters (forward)
CENTER_Y = 0.0           # meters (right)
CENTER_Z = -1.0          # meters (up = negative)

RADIUS = 1.0             # meters
ANGULAR_SPEED = 0.3      # rad/sec (slow & safe)
UPDATE_RATE = 10         # Hz
# --------------------------------------------------


def arm_and_guided(master):
    master.wait_heartbeat()
    print("Heartbeat received")

    master.set_mode_apm("GUIDED")
    time.sleep(2)

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1, 0, 0, 0, 0, 0, 0
    )

    print("Arming...")
    time.sleep(3)


print("Connecting...")
master = mavutil.mavlink_connection(CONNECTION, baud=BAUD)
arm_and_guided(master)

print("Starting orbit...")

theta = 0.0
dt = 1.0 / UPDATE_RATE

try:
    while True:
        # Position on circle
        x = CENTER_X + RADIUS * math.cos(theta)
        y = CENTER_Y + RADIUS * math.sin(theta)
        z = CENTER_Z

        # Yaw: point toward center
        yaw = math.atan2(CENTER_Y - y, CENTER_X - x)

        master.mav.set_position_target_local_ned_send(
            0,
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111111000,   # Position + yaw enabled
            x, y, z,              # position
            0, 0, 0,              # velocity (ignored)
            0, 0, 0,              # acceleration (ignored)
            yaw, 0                # yaw, yaw_rate
        )

        theta += ANGULAR_SPEED * dt
        time.sleep(dt)

except KeyboardInterrupt:
    print("Stopping orbit")

# --------------------------------------------------
# Stop & disarm
# --------------------------------------------------
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0,
    0, 0, 0, 0, 0, 0, 0
)

print("Disarmed")
