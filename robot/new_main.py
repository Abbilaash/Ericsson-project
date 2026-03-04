
import socket
import time
import json
import threading
import logging
import os


# ======================== CONFIG ========================
UDP_SERVER_PORT = 8888
TCP_ACK_PORT = 9999
BASE_STATION_TCP_PORT = 9998
HEARTBEAT_INTERVAL_SEC = 60
POSITION_UPDATE_INTERVAL_SEC = 5
ROBOT_TYPE = "TYPE1"  # Set to TYPE1 or TYPE2

# Simulated robot position
robot_position = {"x": 100.0, "y": 120.0, "z": 5.0}

# ======================== LOGGING ========================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)

# ======================== GLOBAL STATE ========================
message_sender_socket = None
message_sender_lock = threading.Lock()

# Current task tracking
current_task = None
task_lock = threading.Lock()


# ======================== UTILITIES ========================
def get_local_ip() -> str:
    """Get local IP address for network communication"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_battery_health() -> int:
    """Get robot battery health percentage"""
    val = os.getenv("ROBOT_BATTERY")
    if val is not None:
        try:
            v = int(val)
            return max(0, min(100, v))
        except ValueError:
            pass

    try:
        with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
            val = f.read().strip()
            if val:
                v = int(val)
                return max(0, min(100, v))
    except Exception:
        pass

    return 100


sender_ip = get_local_ip()
device_id = f"ROBOT_{sender_ip.replace('.', '')}"


# ======================== COMMUNICATION FUNCTIONS ========================

def broadcast_join(reply_tcp_port: int = TCP_ACK_PORT) -> None:
    """
    Broadcast CONNECTION_REQUEST on UDP to announce presence to base station
    """
    timestamp = time.time()
    payload = {
        "message_id": f"{int(timestamp * 1000000)}",
        "timestamp": int(timestamp),
        "message_type": "CONNECTION_REQUEST",
        "device_id": device_id,
        "device_type": "robot",
        "sender_ip": sender_ip,
        "reply_tcp_port": reply_tcp_port,
        "position": {"x": 0, "y": 0, "z": 0},
        "robot_type": ROBOT_TYPE,
    }
    data = json.dumps(payload).encode("utf-8")
    logging.info("Broadcasting CONNECTION_REQUEST on UDP port %d", UDP_SERVER_PORT)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("", 0))
        except OSError:
            pass
        sock.sendto(data, ("255.255.255.255", UDP_SERVER_PORT))


def wait_for_tcp_ack(listen_port: int = TCP_ACK_PORT, timeout_sec: int = 60) -> str | None:
    """
    Listen for TCP CONNECTION_ACK from base station
    Returns base station IP if ACK received, None if timeout
    """
    local_ip = get_local_ip()
    logging.info("Listening for TCP CONNECTION_ACK on %s:%d", local_ip, listen_port)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", listen_port))
    srv.listen(1)
    srv.settimeout(timeout_sec)

    try:
        conn, addr = srv.accept()
    except socket.timeout:
        logging.error("Timed out waiting for CONNECTION_ACK")
        srv.close()
        return None

    with conn:
        logging.info("TCP connection from %s:%d", addr[0], addr[1])
        chunks = []
        conn.settimeout(10)
        while True:
            try:
                buf = conn.recv(4096)
                if not buf:
                    break
                chunks.append(buf)
            except socket.timeout:
                break

        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except Exception as e:
            logging.error("Invalid ACK payload: %s", e)
            srv.close()
            return None

        if payload.get("message_type") != "CONNECTION_ACK":
            logging.error("Unexpected message_type: %s", payload.get("message_type"))
            srv.close()
            return None

        base_ip = payload.get("base_station_ip")
        receiver_ip = payload.get("receiver_ip")
        if not base_ip:
            logging.error("ACK missing base_station_ip")
            srv.close()
            return None

        logging.info(
            "Received CONNECTION_ACK for receiver_ip=%s from base_station_ip=%s",
            receiver_ip,
            base_ip,
        )
    srv.close()
    return base_ip


def send_heartbeat(base_station_ip: str, stop_event: threading.Event | None = None) -> None:
    """
    Send periodic HEARTBEAT messages to base station (UDP)
    Includes battery health status
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while True:
            if stop_event and stop_event.is_set():
                logging.info("Heartbeat stopped")
                return

            timestamp = time.time()
            payload = {
                "message_id": f"{int(timestamp * 1000000)}",
                "timestamp": int(timestamp),
                "message_type": "HEARTBEAT",
                "receiver_category": "BASE_STATION",
                "battery_health": get_battery_health(),
                "sender_ip": sender_ip,
            }
            data = json.dumps(payload).encode("utf-8")
            try:
                sock.sendto(data, (base_station_ip, UDP_SERVER_PORT))
                logging.info("Sent HEARTBEAT to %s:%d", base_station_ip, UDP_SERVER_PORT)
            except OSError as e:
                logging.error("Failed to send HEARTBEAT: %s", e)

            time.sleep(HEARTBEAT_INTERVAL_SEC)


def send_position_update(base_station_ip: str, stop_event: threading.Event | None = None) -> None:
    """
    Send periodic position updates to base station (UDP)
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while True:
            if stop_event and stop_event.is_set():
                logging.info("Position updates stopped")
                return

            try:
                payload = {
                    "message_type": "POSITION_UPDATE",
                    "device_id": device_id,
                    "device_type": "robot",
                    "sender_ip": sender_ip,
                    "position": robot_position
                }
                data = json.dumps(payload).encode("utf-8")
                sock.sendto(data, (base_station_ip, UDP_SERVER_PORT))
                logging.debug(f"Sent position update: {robot_position}")
            except OSError as e:
                logging.error(f"Failed to send position update: {e}")

            time.sleep(POSITION_UPDATE_INTERVAL_SEC)


def send_message_to_base_station(base_station_ip: str, message_type: str, content: dict) -> bool:
    """
    Send message to base station via persistent TCP connection (newline-delimited JSON)
    Handles reconnection if connection drops.
    
    Args:
        base_station_ip: IP address of base station
        message_type: Type of message (e.g., "TASK_COMPLETED", "STATUS")
        content: Message payload
    
    Returns:
        True if message sent successfully, False otherwise
    """
    global message_sender_socket

    try:
        timestamp = time.time()
        msg = {
            "message_id": f"{int(timestamp * 1000000)}",
            "timestamp": int(timestamp),
            "message_type": message_type,
            "sender_id": device_id,
            "sender_ip": sender_ip,
            "content": content
        }

        message_data = json.dumps(msg).encode('utf-8') + b'\n'

        with message_sender_lock:
            # Try with existing connection first, then retry with new connection if it fails
            for attempt in range(2):
                # If no connection exists or it's broken, create a new one
                if message_sender_socket is None:
                    try:
                        message_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        message_sender_socket.settimeout(5)
                        message_sender_socket.connect((base_station_ip, BASE_STATION_TCP_PORT))
                        logging.info(f"[SEND] Connected to base station at {base_station_ip}:{BASE_STATION_TCP_PORT}")
                    except Exception as e:
                        logging.error(f"[SEND] Failed to connect: {e}")
                        message_sender_socket = None
                        if attempt == 1:
                            return False
                        continue

                try:
                    logging.info(f"[SEND] Sending {len(message_data)} bytes: {message_type}")
                    message_sender_socket.sendall(message_data)
                    logging.info(f"[SEND] ✓ Successfully sent {message_type} message")
                    return True
                except Exception as e:
                    logging.error(f"[SEND] ✗ Send failed (attempt {attempt + 1}/2): {e}")
                    # Close the broken connection
                    try:
                        message_sender_socket.close()
                    except:
                        pass
                    message_sender_socket = None

                    if attempt == 1:
                        return False
                    # Otherwise, loop will retry with new connection

        return False

    except Exception as e:
        logging.error(f"[SEND] Error in send_message_to_base_station: {e}")
        return False


def handle_movement_command(msg: dict, base_station_ip: str = None):
    """
    Handle movement commands from base station
    Placeholder for actual movement execution
    """
    global current_task, message_sender_socket

    content = msg.get("content", {})
    issue_type = content.get("issue_type") or content.get("color")
    coordinates = content.get("coordinates")
    command = content.get("command")
    stage = content.get("stage", 0)
    message_id = msg.get("message_id")

    if not issue_type:
        logging.error("[MOVEMENT] Missing issue_type/color in movement command")
        return
    if not coordinates or not isinstance(coordinates, dict):
        logging.error("[MOVEMENT] Missing or invalid coordinates in movement command")
        return

    logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")
    logging.info(f"[MOVEMENT] NEW TASK ASSIGNED")
    logging.info(f"[MOVEMENT] Issue type: {issue_type.upper()}")
    logging.info(f"[MOVEMENT] Location: X={coordinates.get('x')}, Y={coordinates.get('y')}, Z={coordinates.get('z')}")
    logging.info(f"[MOVEMENT] Task ID: {message_id} (stage {stage})")
    logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")

    # Store current task
    with task_lock:
        current_task = {
            "message_id": message_id,
            "issue_type": issue_type,
            "coordinates": coordinates,
            "command": command,
            "received_at": time.time(),
            "status": "in_progress",
            "stage": stage,
        }

    # TODO: Execute movement based on issue_type and robot type
    # For now, just simulate task execution
    logging.info(f"[MOVEMENT] Executing movement for {issue_type}...")
    time.sleep(1)

    # Update task status
    with task_lock:
        if current_task:
            current_task["status"] = "completed"
            current_task["completed_at"] = time.time()

    # Report completion back to base station
    if base_station_ip:
        completion_report = {
            "task_id": message_id,
            "issue_type": issue_type,
            "coordinates": coordinates,
            "status": "completed",
            "stage": stage,
            "message": f"Successfully rectified {issue_type} at location {coordinates} (stage {stage})"
        }

        logging.info(f"[MOVEMENT] → Reporting task completion to base station...")
        success = send_message_to_base_station(base_station_ip, "TASK_COMPLETED", completion_report)

        if success:
            logging.info(f"[MOVEMENT] ✓ Task completion reported")
        else:
            logging.error(f"[MOVEMENT] ✗ Failed to report completion")

    logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")
    logging.info(f"[MOVEMENT] TASK COMPLETED - Ready for next assignment")
    logging.info(f"[MOVEMENT] ═══════════════════════════════════════════\n")

    # Clear current task
    with task_lock:
        current_task = None


def receive_messages(stop_event: threading.Event, base_station_ip: str = None) -> None:
    """
    Listen for incoming messages from base station on TCP port TCP_ACK_PORT
    Processes newline-delimited JSON messages
    """
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", TCP_ACK_PORT))
        server_sock.listen(5)
        logging.info(f"[MESSAGE] Listening for messages on port {TCP_ACK_PORT}")

        server_sock.settimeout(1)  # Non-blocking with timeout

        while not stop_event.is_set():
            try:
                client_sock, addr = server_sock.accept()
                client_ip = addr[0]
                logging.info(f"[MESSAGE] Incoming connection from {client_ip}")

                try:
                    buffer = ""
                    while True:
                        data = client_sock.recv(4096)
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
                                message_type = msg.get('message_type')
                                logging.info(f"[MESSAGE] Received: {message_type}")

                                # Handle movement commands
                                if message_type == "MOVEMENT_COMMAND":
                                    handle_movement_command(msg, base_station_ip)

                            except json.JSONDecodeError as e:
                                logging.error(f"[MESSAGE] Failed to parse JSON: {e}")

                except Exception as e:
                    logging.error(f"[MESSAGE] Error receiving message: {e}")
                finally:
                    try:
                        client_sock.close()
                    except:
                        pass

            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"[MESSAGE] Error accepting connection: {e}")
                break

    except Exception as e:
        logging.error(f"[MESSAGE] Error in receive_messages: {e}")
    finally:
        try:
            server_sock.close()
        except:
            pass


def cleanup_connections():
    """Close persistent connections on shutdown"""
    global message_sender_socket
    with message_sender_lock:
        if message_sender_socket:
            try:
                message_sender_socket.close()
                logging.info("[CLEANUP] Closed persistent connection to base station")
            except:
                pass
            message_sender_socket = None


# ======================== MAIN ========================
def main():
    """
    Main communication loop for robot
    1. Broadcast connection request
    2. Wait for base station ACK
    3. Start heartbeat thread
    4. Start position update thread
    5. Start message receiver thread
    """
    logging.info(f"[ROBOT] Device ID: {device_id}, IP: {sender_ip}, Type: {ROBOT_TYPE}")

    # Step 1: Broadcast connection request
    broadcast_join(reply_tcp_port=TCP_ACK_PORT)

    # Step 2: Wait for base station acknowledgment
    base_ip = wait_for_tcp_ack(listen_port=TCP_ACK_PORT, timeout_sec=120)
    if not base_ip:
        logging.error("No base station ACK received; exiting")
        return

    logging.info("✓ Connected to base station at %s", base_ip)

    stop_event = threading.Event()

    # Step 3: Start heartbeat thread
    hb_thread = threading.Thread(
        target=send_heartbeat,
        args=(base_ip, stop_event),
        daemon=True
    )
    hb_thread.start()
    logging.info("[ROBOT] Heartbeat thread started")

    # Step 4: Start position update thread
    pos_thread = threading.Thread(
        target=send_position_update,
        args=(base_ip, stop_event),
        daemon=True
    )
    pos_thread.start()
    logging.info("[ROBOT] Position update thread started")

    # Step 5: Start message receiver thread
    msg_thread = threading.Thread(
        target=receive_messages,
        args=(stop_event, base_ip),
        daemon=True
    )
    msg_thread.start()
    logging.info("[ROBOT] Message receiver thread started")

    logging.info("[ROBOT] ✓ All communication threads started")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        stop_event.set()
        cleanup_connections()
        hb_thread.join(timeout=5)
        pos_thread.join(timeout=5)
        msg_thread.join(timeout=5)
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()
