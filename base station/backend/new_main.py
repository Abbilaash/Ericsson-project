"""
BASE STATION COMMUNICATION MODULE
Handles TCP/UDP communication with drones and robots, message passing, and device coordination.
Excludes API routes, Flask web server, and issue detection logic.
"""

import socket
import json
import threading
import time
import logging
from collections import defaultdict


# ======================== CONFIG ========================
TCP_LISTEN_PORT = 9998  # Port for receiving connections FROM drones/robots
TCP_ROBOT_PORT = 9999   # Port for sending commands TO robots
UDP_PORT = 8888
BUFFER_SIZE = 8192

# ======================== LOGGING ========================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)

# ======================== GLOBAL STATE ========================
def get_base_station_ip():
    """Get local IP address of base station"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


BASE_STATION_IP = get_base_station_ip()

# Connected devices registry
connected_clients = {}
clients_lock = threading.Lock()

devices = {}  # Format: {device_id: {device_id, ip, status, position, device_type, ...}}
devices_lock = threading.Lock()

# Track device positions
last_position_log = defaultdict(float)
POSITION_LOG_INTERVAL = 5  # seconds


# ======================== COMMUNICATION UTILITIES ========================

def log_packet(direction, transport, packet_type, message_type, sender_id, receiver_id, payload):
    """Log network packet for debugging/monitoring"""
    entry = {
        "timestamp": time.time(),
        "direction": direction,
        "transport": transport,
        "packet_type": packet_type,
        "message_type": message_type,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "payload": payload,
    }
    logging.debug(f"[PACKET] {direction} {transport} {message_type} from {sender_id}")


def connection_ack_signal(receiver_id, receiver_ip):
    """
    Create CONNECTION_ACK response to send back to connecting device
    """
    timestamp = time.time()
    return {
        "message_id": f"{int(timestamp * 1000000)}",
        "timestamp": timestamp,
        "message_type": "CONNECTION_ACK",
        "base_station_ip": BASE_STATION_IP,
        "receiver_id": receiver_id,
        "receiver_ip": receiver_ip
    }


# ======================== MESSAGE SENDING FUNCTIONS ========================

def send_movement_command_to_robot(robot_id: str, base_station_ip: str, issue_type: str, coordinates: dict, stage: int = 0) -> bool:
    """
    Send MOVEMENT_COMMAND to a specific robot via TCP
    
    Args:
        robot_id: Device ID of the robot
        base_station_ip: IP of the base station (for reference)
        issue_type: Type of issue (rust, overheated_circuit, tilted_antenna)
        coordinates: Location coordinates {x, y, z}
        stage: Stage number for multi-stage issues (default 0)
    
    Returns:
        True if message sent successfully, False otherwise
    """
    with devices_lock:
        if robot_id not in devices:
            logging.error(f"[SEND] Robot {robot_id} not found in devices")
            return False

        robot = devices[robot_id]
        robot_ip = robot.get("ip")

    if not robot_ip:
        logging.error(f"[SEND] No IP address for robot {robot_id}")
        return False

    try:
        timestamp = time.time()
        message_id = f"{int(timestamp * 1000000)}"

        msg = {
            "message_id": message_id,
            "timestamp": int(timestamp),
            "message_type": "MOVEMENT_COMMAND",
            "content": {
                "issue_type": issue_type,
                "coordinates": coordinates,
                "command": "move_to_location",
                "stage": stage,
            }
        }

        message_data = json.dumps(msg).encode('utf-8') + b'\n'

        # Try to send via TCP to robot's listening port
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((robot_ip, TCP_ROBOT_PORT))
                sock.sendall(message_data)
                logging.info(f"[SEND] ✓ Sent MOVEMENT_COMMAND to {robot_id} at {robot_ip}:{TCP_ROBOT_PORT}")
                logging.info(f"[SEND]   Issue: {issue_type}, Location: {coordinates}, Stage: {stage}")

                # Update robot task info in devices registry
                with devices_lock:
                    if robot_id in devices:
                        devices[robot_id]["task_id"] = message_id
                        devices[robot_id]["current_task"] = {
                            "issue_type": issue_type,
                            "coordinates": coordinates,
                            "stage": stage,
                        }
                        devices[robot_id]["status"] = "BUSY"

                log_packet(
                    direction="out",
                    transport="TCP",
                    packet_type="COMMAND",
                    message_type="MOVEMENT_COMMAND",
                    sender_id="base_station",
                    receiver_id=robot_id,
                    payload=msg,
                )

                return True

        except socket.timeout:
            logging.error(f"[SEND] Timeout sending to {robot_id} at {robot_ip}:{TCP_ROBOT_PORT}")
            return False
        except Exception as e:
            logging.error(f"[SEND] Failed to send to {robot_id}: {e}")
            return False

    except Exception as e:
        logging.error(f"[SEND] Error in send_movement_command_to_robot: {e}")
        return False


# ======================== TCP SERVER (RECEIVE MESSAGES) ========================

def tcp_server():
    """
    TCP server that listens for incoming messages from drones/robots
    Handles:
    - QR_SCAN messages (from drones)
    - TASK_COMPLETED messages (from robots)
    - Other status messages
    """
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", TCP_LISTEN_PORT))
        server_sock.listen(10)
        logging.info(f"[TCP] Server listening on port {TCP_LISTEN_PORT}")

        while True:
            try:
                client_sock, addr = server_sock.accept()
                client_ip = addr[0]
                logging.info(f"[TCP] New connection from {client_ip}")

                # Handle client in a separate thread
                client_thread = threading.Thread(
                    target=handle_tcp_client,
                    args=(client_sock, client_ip),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                logging.error(f"[TCP] Error accepting connection: {e}")

    except Exception as e:
        logging.error(f"[TCP] Server error: {e}")
    finally:
        try:
            server_sock.close()
        except:
            pass


def handle_tcp_client(client_sock: socket.socket, client_ip: str):
    """Handle a single TCP client connection"""
    try:
        with clients_lock:
            connected_clients[client_ip] = time.time()

        buffer = ""
        client_sock.settimeout(10)

        while True:
            try:
                data = client_sock.recv(BUFFER_SIZE)
                if not data:
                    break

                buffer += data.decode('utf-8', errors='ignore')

                # Process complete messages (separated by newlines)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        msg = json.loads(line)
                        message_type = msg.get('message_type', 'UNKNOWN')
                        sender_id = msg.get('sender_id') or client_ip
                        logging.info(f"[TCP] Received {message_type} from {sender_id}")

                        if message_type == "QR_SCAN":
                            # Handle QR scan from drone
                            content = msg.get('content', {})
                            issue_type = content.get('issue_type')
                            coordinates = content.get('coordinates', {})
                            logging.info(f"[TCP] QR_SCAN: {issue_type} at {coordinates}")

                            log_packet(
                                direction="in",
                                transport="TCP",
                                packet_type="DETECTION",
                                message_type="QR_SCAN",
                                sender_id=sender_id,
                                receiver_id="base_station",
                                payload=msg,
                            )

                        elif message_type == "TASK_COMPLETED":
                            # Handle task completion from robot
                            content = msg.get('content', {})
                            task_id = content.get('task_id')
                            issue_type = content.get('issue_type')
                            status = content.get('status')
                            logging.info(f"[TCP] TASK_COMPLETED: {issue_type} (task_id={task_id})")

                            # Mark robot as READY in devices registry
                            with devices_lock:
                                for dev_id, dev in devices.items():
                                    if dev.get("task_id") == task_id and dev.get("device_type", "").lower() == "robot":
                                        dev["task_id"] = None
                                        dev["current_task"] = None
                                        dev["status"] = "READY"
                                        logging.info(f"[TCP] Freed robot {dev_id}")
                                        break

                            log_packet(
                                direction="in",
                                transport="TCP",
                                packet_type="STATUS",
                                message_type="TASK_COMPLETED",
                                sender_id=sender_id,
                                receiver_id="base_station",
                                payload=msg,
                            )

                        else:
                            logging.debug(f"[TCP] Unhandled message type: {message_type}")

                    except json.JSONDecodeError as e:
                        logging.error(f"[TCP] Failed to parse JSON: {e}")
                    except Exception as e:
                        logging.error(f"[TCP] Error processing message: {e}")

            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"[TCP] Error receiving data: {e}")
                break

    except Exception as e:
        logging.error(f"[TCP] Error handling client: {e}")
    finally:
        try:
            client_sock.close()
        except:
            pass

        with clients_lock:
            if client_ip in connected_clients:
                del connected_clients[client_ip]

        # Remove disconnected devices
        with devices_lock:
            devices_to_remove = [
                dev_id for dev_id, dev in devices.items()
                if dev.get("ip") == client_ip
            ]
            for dev_id in devices_to_remove:
                del devices[dev_id]
                logging.info(f"[TCP] Removed device {dev_id} due to TCP disconnect")

        logging.info(f"[TCP] Client disconnected: {client_ip}")


# ======================== UDP SERVER (DISCOVER & HEARTBEAT) ========================

def udp_listener():
    """
    UDP listener on port 8888 - catches broadcast signals and position updates
    Handles:
    - CONNECTION_REQUEST (from new drones/robots)
    - HEARTBEAT (periodic status)
    - POSITION_UPDATE (position tracking)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", UDP_PORT))
        logging.info(f"[UDP] Listener on port {UDP_PORT}")

        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode('utf-8'))

                device_id = msg.get('device_id')
                device_ip = msg.get('sender_ip') or addr[0]
                position = msg.get('position')
                message_type = msg.get('message_type')
                reply_tcp_port = msg.get('reply_tcp_port', TCP_ROBOT_PORT)
                device_type = msg.get('device_type', 'unknown')

                if message_type == "POSITION_UPDATE":
                    # Update device position (quiet logging)
                    with devices_lock:
                        now = time.time()
                        if device_id and device_id in devices:
                            devices[device_id]["position"] = position
                            devices[device_id]["updated_at"] = now
                            if now - last_position_log[device_id] >= POSITION_LOG_INTERVAL:
                                logging.debug(f"[POSITION] Updated {device_id}: {position}")
                                last_position_log[device_id] = now
                    continue  # Skip further logging for position updates

                logging.info(f"[UDP] {message_type} from {device_id} ({device_type}) at {device_ip}")

                if message_type == "CONNECTION_REQUEST" and device_id and device_ip:
                    # New device joining - send ACK and register device
                    ack = connection_ack_signal(device_id, device_ip)

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
                            tcp.settimeout(2)
                            tcp.connect((device_ip, reply_tcp_port))
                            tcp.sendall(json.dumps(ack).encode('utf-8'))

                        status = "CONNECTED"
                        logging.info(f"[UDP] ✓ Sent CONNECTION_ACK to {device_id}")

                        log_packet(
                            direction="out",
                            transport="TCP",
                            packet_type="ACK",
                            message_type="CONNECTION_ACK",
                            sender_id="base_station",
                            receiver_id=device_id,
                            payload=ack,
                        )

                    except Exception as e:
                        status = f"ACK_FAIL: {e}"
                        logging.error(f"[UDP] Failed to send ACK to {device_id}: {e}")

                    robot_type = msg.get('robot_type') if device_type.lower() == "robot" else None

                    # Register device
                    with devices_lock:
                        devices[device_id] = {
                            "device_id": device_id,
                            "ip": device_ip,
                            "status": status,
                            "position": position,
                            "device_type": device_type,
                            "robot_type": robot_type,
                            "updated_at": time.time(),
                            "task_id": None,
                            "current_task": None,
                        }

                    if robot_type:
                        logging.info(f"[UDP] Robot {device_id} registered as {robot_type}")
                    else:
                        logging.info(f"[UDP] Device {device_id} ({device_type}) registered")

                    log_packet(
                        direction="in",
                        transport="UDP",
                        packet_type="DISCOVERY",
                        message_type="CONNECTION_REQUEST",
                        sender_id=device_id,
                        receiver_id="base_station",
                        payload=msg,
                    )

                elif message_type == "HEARTBEAT":
                    # Update device heartbeat
                    with devices_lock:
                        for dev_id, dev in devices.items():
                            if dev.get("ip") == device_ip:
                                dev["updated_at"] = time.time()
                                dev["battery_health"] = msg.get('battery_health', 100)
                                logging.debug(f"[HEARTBEAT] {dev_id} (battery: {msg.get('battery_health', 'N/A')}%)")
                                break

                    log_packet(
                        direction="in",
                        transport="UDP",
                        packet_type="STATUS",
                        message_type="HEARTBEAT",
                        sender_id=device_id,
                        receiver_id="base_station",
                        payload=msg,
                    )

            except json.JSONDecodeError as e:
                logging.error(f"[UDP] Invalid JSON: {e}")
            except Exception as e:
                logging.error(f"[UDP] Error processing: {e}")

    except Exception as e:
        logging.error(f"[UDP] Server error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass


# ======================== MAIN ========================

def main():
    """
    Start base station communication servers
    - TCP server for receiving messages (port 9998)
    - UDP server for discovery and heartbeats (port 8888)
    """
    logging.info(f"[BASE_STATION] IP: {BASE_STATION_IP}")
    logging.info(f"[BASE_STATION] Starting communication servers...")

    # Start TCP server (in background thread)
    tcp_thread = threading.Thread(target=tcp_server, daemon=True)
    tcp_thread.start()
    logging.info("[BASE_STATION] TCP server thread started")

    # Start UDP listener (in background thread)
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()
    logging.info("[BASE_STATION] UDP listener thread started")

    logging.info("[BASE_STATION] ✓ All communication servers started")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
            # Optional: print device status periodically
            if int(time.time()) % 30 == 0:
                with devices_lock:
                    logging.info(f"[STATUS] Connected devices: {len(devices)}")
                    for dev_id, dev in devices.items():
                        logging.debug(f"  {dev_id}: {dev.get('status')} (battery: {dev.get('battery_health', 'N/A')}%)")

    except KeyboardInterrupt:
        logging.info("Shutting down...")
        tcp_thread.join(timeout=5)
        udp_thread.join(timeout=5)
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()
