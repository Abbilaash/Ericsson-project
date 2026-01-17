import socket
import json
import threading
import time
from flask import Flask, jsonify, request
import flask_cors

# NOTE: FORWARD_ALL, FORWARD_TO


def get_base_station_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

TCP_LISTEN_PORT = 9998  # Port for receiving connections FROM drones/robots
TCP_ROBOT_PORT = 9999   # Port for sending commands TO robots
UDP_PORT = 8888
BUFFER_SIZE = 8192
BASE_STATION_IP = get_base_station_ip()

# Issue type to location mappings with predefined coordinates
ISSUE_LOCATIONS = {
    "rust": {
        "coordinates": {"x": 50, "y": 75, "z": 10},
        "robot_count": 1,
        "description": "Rust detected at location"
    },
    "overheated_circuit": {
        "coordinates": {"x": 120, "y": 150, "z": 5},
        "robot_count": 2,
        "description": "Overheated circuit detected at location"
    },
    "tilted_antenna": {
        "coordinates": {"x": 200, "y": 100, "z": 20},
        "robot_count": 1,
        "description": "Tilted antenna detected at location"
    }
}

# QR code mapping to issue types
QR_CODE_TO_ISSUE = {
    "RUST_QR": "rust",
    "CIRCUIT_QR": "overheated_circuit",
    "ANTENNA_QR": "tilted_antenna"
}

connected_clients = {}
clients_lock = threading.Lock()
devices = {}
network_logs = []
logs_lock = threading.Lock()
MAX_LOGS = 500

app = Flask(__name__)
flask_cors.CORS(app)


def log_packet(direction, transport, packet_type, message_type, sender_id, receiver_id, payload):
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
    with logs_lock:
        network_logs.append(entry)
        if len(network_logs) > MAX_LOGS:
            del network_logs[:-MAX_LOGS]


def build_message(message_type, receiver_category, receiver_ip, message_content, sender_ip):
    timestamp = time.time()
    return {
        "message_id": f"{int(timestamp * 1000000)}",
        "timestamp": timestamp,
        "message_type": message_type,
        "receiver_category": receiver_category,
        "receiver_ip": receiver_ip,
        "sender_ip": sender_ip,
        "message_content": message_content
    }


def connection_ack_signal(receiver_id, receiver_ip):
    timestamp = time.time()
    return {
        "message_id": f"{int(timestamp * 1000000)}",
        "timestamp": timestamp,
        "message_type": "CONNECTION_ACK",
        "base_station_ip": BASE_STATION_IP,
        "receiver_id": receiver_id,
        "receiver_ip": receiver_ip
    }

def tcp_server():
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", TCP_LISTEN_PORT))
        server_sock.listen(10)
        print(f"[SERVER] TCP server listening on port {TCP_LISTEN_PORT}")
        
        while True:
            try:
                client_sock, addr = server_sock.accept()
                client_ip = addr[0]
                
                with clients_lock:
                    connected_clients[client_ip] = {
                        "socket": client_sock,
                        "connected_at": time.time()
                    }
                print(f"[TCP] Client connected: {client_ip}")
                threading.Thread(
                    target=handle_tcp_client, 
                    args=(client_sock, client_ip), 
                    daemon=True
                ).start() 
            except Exception as e:
                print(f"[TCP] Error accepting connection: {e}")
    except Exception as e:
        print(f"[TCP] Server error: {e}")


def handle_tcp_client(client_sock, client_ip):
    """Handle persistent TCP connection from drone/robot (newline-delimited JSON)"""
    # Set timeout so recv() doesn't block forever
    client_sock.settimeout(120)  # 2 minute timeout for detecting dead connections
    
    try:
        buffer = ""
        print(f"[TCP] ✓ Successfully accepted connection from {client_ip}")
        print(f"[TCP] Waiting for data from {client_ip}...")
        
        while True:
            try:
                # Receive data with timeout
                data = client_sock.recv(BUFFER_SIZE)
                
                # Empty data means the remote closed the connection
                if not data:
                    print(f"[TCP] ✗ Client {client_ip} closed connection (received 0 bytes)")
                    print(f"[TCP] This usually means:")
                    print(f"[TCP]   1. Client connected but never sent data")
                    print(f"[TCP]   2. Client encountered an error before sending")
                    print(f"[TCP]   3. Port conflict (client listening on same port it's trying to connect from)")
                    break
                
                print(f"[TCP] ✓ Received {len(data)} bytes from {client_ip}")
                
                # Decode and add to buffer
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
                        print(f"[TCP] Received from {client_ip}: {message_type}")
                        
                        # If this is a QR code scan from drone, automatically assign robots
                        if message_type == "QR_SCAN":
                            content = msg.get('content', {})
                            qr_code = content.get('qr_code')
                            api_data = content.get('api_data', {})
                            issue_type = QR_CODE_TO_ISSUE.get(qr_code)
                            
                            if issue_type and issue_type in ISSUE_LOCATIONS:
                                issue_info = ISSUE_LOCATIONS[issue_type]
                                coordinates = issue_info["coordinates"]
                                
                                print(f"\n[DETECTION] ╔════════════════════════════════════════════════════════════╗")
                                print(f"[DETECTION] ║ QR CODE SCANNED BY DRONE                                      ║")
                                print(f"[DETECTION] ║ Issue Type: {issue_type.upper():<43} ║")
                                print(f"[DETECTION] ║ QR Code: {qr_code:<53} ║")
                                print(f"[DETECTION] ║ API Data: {str(api_data):<49} ║")
                                print(f"[DETECTION] ║ Location: X={coordinates.get('x', 0)}, Y={coordinates.get('y', 0)}, Z={coordinates.get('z', 0):<20} ║")
                                print(f"[DETECTION] ║ Sender: {sender_id:<52} ║")
                                print(f"[DETECTION] ║ Time: {time.strftime('%Y-%m-%d %H:%M:%S'):<50} ║")
                                print(f"[DETECTION] ╚════════════════════════════════════════════════════════════╝\n")
                                
                                try:
                                    handle_issue_detection(issue_type, coordinates, api_data)
                                except Exception as e:
                                    print(f"[TCP] ✗ Error in handle_issue_detection: {e}")
                                    import traceback
                                    traceback.print_exc()
                        elif message_type == "TASK_COMPLETED":
                            content = msg.get('content', {})
                            task_id = content.get('task_id') or msg.get('message_id')
                            issue_type = content.get('issue_type')
                            coordinates = content.get('coordinates', {})
                            status = content.get('status')
                            message = content.get('message')

                            freed = False
                            for dev_id, dev in devices.items():
                                if dev_id == sender_id or dev.get("ip") == client_ip:
                                    dev["task_id"] = None
                                    dev["current_task"] = None
                                    dev["status"] = "READY"
                                    dev["updated_at"] = time.time()
                                    freed = True
                                    print(f"[TASK] ✓ Task completed by {dev_id} (status={status}, task_id={task_id})")
                                    print(f"[TASK] ✓ Robot is now available for new assignments")
                                    break

                            if not freed:
                                print(f"[TASK] ⚠ Received TASK_COMPLETED from unknown device {sender_id} / {client_ip}")

                            log_packet(
                                direction="in",
                                transport="TCP",
                                packet_type="STATUS",
                                message_type="TASK_COMPLETED",
                                sender_id=sender_id,
                                receiver_id="base_station",
                                payload=msg,
                            )
                        
                        log_packet(
                            direction="in",
                            transport="TCP",
                            packet_type="MESSAGE",
                            message_type=message_type,
                            sender_id=sender_id,
                            receiver_id="base_station",
                            payload=msg,
                        )
                    except json.JSONDecodeError as e:
                        print(f"[TCP] Failed to parse JSON from {client_ip}: {e}")
                    except Exception as e:
                        print(f"[TCP] ✗ Error processing message from {client_ip}: {e}")
                        import traceback
                        traceback.print_exc()
                    
            except socket.timeout:
                # Timeout waiting for data is normal for idle connections
                # Just continue waiting for more data
                continue
            except Exception as e:
                print(f"[TCP] ✗ Error receiving from {client_ip}: {e}")
                break
    
    except Exception as e:
        print(f"[TCP] ✗ Error handling client {client_ip}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            client_sock.close()
        except:
            pass
        
        with clients_lock:
            if client_ip in connected_clients:
                del connected_clients[client_ip]
        devices_to_remove = []
        for dev_id, dev in devices.items():
            if dev.get("ip") == client_ip:
                devices_to_remove.append(dev_id)
        for dev_id in devices_to_remove:
            del devices[dev_id]
            print(f"[TCP] Removed device {dev_id} due to TCP disconnect")
        print(f"[TCP] Client disconnected: {client_ip}")


def udp_listener():
    """UDP listener on port 8888 - catches broadcast signals"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", UDP_PORT))
        print(f"[SERVER] UDP listener on port {UDP_PORT}")
        
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

                log_packet(
                    direction="in",
                    transport="UDP",
                    packet_type="DISCOVERY" if message_type == "CONNECTION_REQUEST" else "STATUS",
                    message_type=message_type,
                    sender_id=device_id,
                    receiver_id="base_station",
                    payload=msg,
                )

                print(f"[UDP] {message_type} from {device_id} at {device_ip}")

                if message_type == "CONNECTION_REQUEST" and device_id and device_ip:
                    ack = connection_ack_signal(device_id, device_ip)
                    # Send ACK over TCP to client on the port they specified
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
                            tcp.settimeout(2)
                            tcp.connect((device_ip, reply_tcp_port))
                            tcp.sendall(json.dumps(ack).encode('utf-8'))
                        status = "CONNECTED"
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

                    devices[device_id] = {
                        "device_id": device_id,
                        "ip": device_ip,
                        "status": status,
                        "position": position,
                        "device_type": device_type,
                        "updated_at": time.time()
                    }
                elif message_type == "HEARTBEAT":
                    # Update device based on sender_ip since heartbeat may not include device_id
                    updated = False
                    for dev_id, dev in devices.items():
                        if dev.get("ip") == device_ip:
                            dev["updated_at"] = time.time()
                            dev["battery_health"] = msg.get('battery_health', 100)
                            print(f"[UDP] Updated {dev_id} heartbeat (battery: {msg.get('battery_health', 'N/A')}%)")
                            updated = True
                            break
                    
                    if updated:
                        log_packet(
                            direction="in",
                            transport="UDP",
                            packet_type="STATUS",
                            message_type="HEARTBEAT",
                            sender_id=device_id or device_ip,
                            receiver_id="base_station",
                            payload=msg,
                        )

            except Exception as e:
                print(f"[UDP] Error processing message: {e}")
    
    except Exception as e:
        print(f"[UDP] Listener error: {e}")

def forward_to_all(receiver_category: str, message_content: dict):
    sent_to = []
    timestamp = time.time()
    
    for dev_id, dev in devices.items():
        device_category = dev.get("device_type", "unknown").lower()
        
        if device_category == receiver_category:
            device_ip = dev.get("ip")
            if device_ip:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
                        tcp.settimeout(2)
                        tcp.connect((device_ip, TCP_ROBOT_PORT))
                        
                        forward_msg = {
                            "message_id": f"{int(timestamp * 1000000)}",
                            "timestamp": int(timestamp),
                            "message_type": "FORWARD_ALL",
                            "receiver_category": receiver_category,
                            "sender": "base_station",
                            "content": message_content
                        }
                        tcp.sendall(json.dumps(forward_msg).encode('utf-8'))
                        sent_to.append(dev_id)
                        print(f"[FORWARD] Sent FORWARD_ALL to {dev_id} at {device_ip}")
                        log_packet(
                            direction="out",
                            transport="TCP",
                            packet_type="FORWARD",
                            message_type="FORWARD_ALL",
                            sender_id="base_station",
                            receiver_id=dev_id,
                            payload=forward_msg,
                        )
                except Exception as e:
                    print(f"[FORWARD] Failed to send to {dev_id}: {e}")
    
    return sent_to


def forward_to_device(receiver_id: str, receiver_ip: str, message_content: dict):
    timestamp = time.time()
    message_id = f"{int(timestamp * 1000000)}"
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
            tcp.settimeout(2)
            tcp.connect((receiver_ip, TCP_ROBOT_PORT))
            
            forward_msg = {
                "message_id": message_id,
                "timestamp": int(timestamp),
                "message_type": "FORWARD_TO",
                "receiver_id": receiver_id,
                "sender": "base_station",
                "content": message_content
            }
            tcp.sendall(json.dumps(forward_msg).encode('utf-8'))
            print(f"[FORWARD] Sent FORWARD_TO message to {receiver_id} at {receiver_ip}")
            log_packet(
                direction="out",
                transport="TCP",
                packet_type="FORWARD",
                message_type="FORWARD_TO",
                sender_id="base_station",
                receiver_id=receiver_id,
                payload=forward_msg,
            )
            
            # Update the robot's task_id to the message_id
            for dev_id, dev in devices.items():
                if dev_id == receiver_id or dev.get("ip") == receiver_ip:
                    dev["task_id"] = message_id
                    print(f"[FORWARD] Updated {dev_id} task_id to {message_id}")
                    break
            
            return True, message_id
    except Exception as e:
        print(f"[FORWARD] Failed to send to {receiver_id} at {receiver_ip}: {e}")
        return False, None


def find_available_robot():
    """
    Find a robot that is not assigned to any task
    Returns: (robot_id, robot_ip) or (None, None) if no available robot
    """
    for dev_id, dev in devices.items():
        device_type = dev.get("device_type", "").lower()
        if device_type == "robot":
            # Check if robot doesn't have a task_id or task_id is None/empty
            task_id = dev.get("task_id")
            if not task_id:
                return dev_id, dev.get("ip")
    
    return None, None


def find_available_robots(count: int):
    """
    Find N available robots that are not assigned to any task
    Returns: list of (robot_id, robot_ip) tuples, may be less than count if not enough robots
    """
    available = []
    print(f"[ROBOTS] Searching for {count} available robot(s)...")
    print(f"[ROBOTS] Total devices in system: {len(devices)}")
    
    for dev_id, dev in devices.items():
        device_type = dev.get("device_type", "").lower()
        print(f"[ROBOTS] → Device: {dev_id}, Type: {device_type}, Has task_id: {bool(dev.get('task_id'))}")
        
        if device_type == "robot":
            task_id = dev.get("task_id")
            if not task_id:
                available.append((dev_id, dev.get("ip")))
                print(f"[ROBOTS] ✓ Found available robot: {dev_id}")
                if len(available) >= count:
                    break
    
    print(f"[ROBOTS] Found {len(available)}/{count} available robots\n")
    return available


def send_movement_command(robot_id: str, robot_ip: str, coordinates: dict, issue_type: str):
    """
    Send a movement command to a specific robot
    Returns: (success, message_id)
    """
    timestamp = time.time()
    message_id = f"{int(timestamp * 1000000)}"
    
    print(f"[MOVEMENT] Sending command to {robot_id} at {robot_ip}")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
            tcp.settimeout(2)
            tcp.connect((robot_ip, TCP_ROBOT_PORT))
            print(f"[MOVEMENT] ✓ Connected to {robot_ip}:{TCP_ROBOT_PORT}")
            
            movement_msg = {
                "message_id": message_id,
                "timestamp": int(timestamp),
                "message_type": "MOVEMENT_COMMAND",
                "receiver_id": robot_id,
                "sender": "base_station",
                "content": {
                    "issue_type": issue_type,
                    "coordinates": coordinates,
                    "command": "move_to_location"
                }
            }
            
            message_json = json.dumps(movement_msg)
            message_data = message_json.encode('utf-8') + b'\n'
            tcp.sendall(message_data)
            print(f"[MOVEMENT] ✓ Message sent ({len(message_data)} bytes)")
            
            print(f"[MOVEMENT] Sent movement command to {robot_id} at {robot_ip} for issue {issue_type} at {coordinates}")
            log_packet(
                direction="out",
                transport="TCP",
                packet_type="COMMAND",
                message_type="MOVEMENT_COMMAND",
                sender_id="base_station",
                receiver_id=robot_id,
                payload=movement_msg,
            )
            
            # Update the robot's task_id to the message_id
            for dev_id, dev in devices.items():
                if dev_id == robot_id or dev.get("ip") == robot_ip:
                    dev["task_id"] = message_id
                    dev["current_task"] = {
                        "issue_type": issue_type,
                        "coordinates": coordinates,
                        "assigned_at": time.time()
                    }
                    print(f"[MOVEMENT] Updated {dev_id} task_id to {message_id}")
                    break
            
            return True, message_id
    except socket.timeout:
        print(f"[MOVEMENT] ✗ Timeout connecting to {robot_id} at {robot_ip}:{TCP_ROBOT_PORT}")
        return False, None
    except ConnectionRefusedError:
        print(f"[MOVEMENT] ✗ Connection refused by {robot_id} at {robot_ip}:{TCP_ROBOT_PORT}")
        return False, None
    except Exception as e:
        print(f"[MOVEMENT] ✗ Failed to send movement command to {robot_id} at {robot_ip}: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def handle_issue_detection(issue_type: str, coordinates: dict, api_data: dict = None):
    """
    Handle detection of a specific issue type and assign robots accordingly
    - rust: 1 robot
    - overheated_circuit: 2 robots
    - tilted_antenna: 1 robot
    """
    if issue_type not in ISSUE_LOCATIONS:
        print(f"[ASSIGNMENT] ✗ Unknown issue type: {issue_type}")
        return False
    
    issue_info = ISSUE_LOCATIONS[issue_type]
    robot_count = issue_info["robot_count"]
    
    print(f"\n[ASSIGNMENT] ╔════════════════════════════════════════════════════════════╗")
    print(f"[ASSIGNMENT] ║ ROBOT ASSIGNMENT INITIATED                              ║")
    print(f"[ASSIGNMENT] ║ Issue Type: {issue_type.upper():<43} ║")
    print(f"[ASSIGNMENT] ║ Required Robots: {robot_count:<45} ║")
    print(f"[ASSIGNMENT] ║ Location: ({coordinates.get('x', 0)}, {coordinates.get('y', 0)}, {coordinates.get('z', 0):<25}) ║")
    if api_data:
        print(f"[ASSIGNMENT] ║ API Data: {str(api_data):<49} ║")
    print(f"[ASSIGNMENT] ╚════════════════════════════════════════════════════════════╝\n")
    
    # Find available robots
    available_robots = find_available_robots(robot_count)
    
    if not available_robots:
        print(f"[ASSIGNMENT] ⚠️  WARNING: No available robots for {issue_type.upper()} detection")
        print(f"[ASSIGNMENT] Available robots needed: {robot_count}, Found: 0\n")
        return False
    
    print(f"[ASSIGNMENT] ✓ Found {len(available_robots)} available robot(s)")
    
    # Send movement command to each robot
    for idx, (robot_id, robot_ip) in enumerate(available_robots, 1):
        print(f"[ASSIGNMENT] → Assigning Robot {idx}/{len(available_robots)}: {robot_id} at {robot_ip}")
        success, message_id = send_movement_command(robot_id, robot_ip, coordinates, issue_type)
        if not success:
            print(f"[ASSIGNMENT] ✗ Failed to assign robot {robot_id} for {issue_type.upper()} detection")
        else:
            print(f"[ASSIGNMENT] ✓ Successfully assigned robot {robot_id} (Message ID: {message_id})")
    
    print(f"[ASSIGNMENT] ═════════════════════════════════════════════════════════════\n")
    return True


def cleanup_stale_devices():
    while True:
        try:
            time.sleep(10)
            current_time = time.time()
            devices_to_remove = []
            
            for dev_id, dev in devices.items():
                last_seen = dev.get("updated_at", 0)
                if current_time - last_seen > 60:
                    devices_to_remove.append(dev_id)
            
            for dev_id in devices_to_remove:
                del devices[dev_id]
                print(f"[CLEANUP] Removed {dev_id} due to heartbeat timeout")
        
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")

@app.route("/api/connections")
def api_connections():
    return jsonify({
        "success": True,
        "devices": list(devices.values()),
        "timestamp": time.time()
    })

@app.route("/api/overview",methods=["GET"])
def api_overview():
    """Provide drones, robots, and tasks in a shape the frontend expects."""
    drones = {}
    robots = {}
    for dev_id, dev in devices.items():
        dtype = str(dev.get("device_type", "")).lower()
        ip = dev.get("ip")
        if dtype == "drone" and ip:
            norm_id = f"DRONE_{ip.replace('.', '')}"
        else:
            norm_id = dev_id
        
        # Get task information
        task_id = dev.get("task_id")
        current_task = dev.get("current_task", {})
        task_color = current_task.get("color") if task_id else None
        
        entry = {
            "id": norm_id,
            "original_id": dev_id,
            "battery": dev.get("battery_health"),
            "status": dev.get("status"),
            "last_seen": dev.get("updated_at"),
            "position": dev.get("position"),
            "ip": dev.get("ip"),
            "task_id": task_id,
            "task_color": task_color,
            "is_busy": bool(task_id),  # True if robot has a task
        }
        if dtype == "robot":
            robots[norm_id] = entry
        else:
            drones[norm_id] = entry

    return jsonify({
        "success": True,
        "drones": drones,
        "robots": robots,
        "tasks": {},
        "timestamp": time.time(),
    })


@app.route("/api/network-logs")
def api_network_logs():
    with logs_lock:
        packets = list(network_logs)
    # newest first
    packets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return jsonify({"packets": packets})


@app.route("/api/messages")
def api_messages():
    return api_network_logs()

@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    with logs_lock:
        network_logs.clear()
    return jsonify({"success": True, "message": "logs cleared"})


@app.route("/api/send-broadcast", methods=["POST"])
def api_send_broadcast():
    """
    Send a message to all devices in a specific category
    Request body: {
        "receiver_category": "robots" or "drones",
        "message": {...}
    }
    """
    data = request.get_json()
    receiver_category = data.get("receiver_category", "").lower()
    message_content = data.get("message", {})
    
    if not receiver_category:
        return jsonify({"success": False, "error": "receiver_category required"}), 400
    
    sent_to = forward_to_all(receiver_category, message_content)
    
    return jsonify({
        "success": True,
        "sent_to": sent_to,
        "count": len(sent_to),
        "message": f"Broadcast sent to {len(sent_to)} {receiver_category}"
    })


@app.route("/api/send-message", methods=["POST"])
def api_send_message():
    """
    Send a message to an available robot (not assigned to any task)
    Request body: {
        "message": {...}
    }
    OR if specifying a particular device:
    {
        "receiver_id": "ROBOT_172_27_240_63",
        "message": {...}
    }
    """
    data = request.get_json()
    receiver_id = data.get("receiver_id")
    message_content = data.get("message", {})
    
    # If no specific receiver, find an available robot
    if not receiver_id:
        receiver_id, receiver_ip = find_available_robot()
        if not receiver_id:
            return jsonify({"success": False, "error": "No available robot (all robots are assigned)"}), 404
    else:
        # Find device by ID
        device = None
        for dev_id, dev in devices.items():
            if dev_id == receiver_id or dev.get("ip") == receiver_id:
                device = dev
                break
        
        if not device:
            return jsonify({"success": False, "error": f"Device {receiver_id} not found"}), 404
        
        receiver_ip = device.get("ip")
    
    success, message_id = forward_to_device(receiver_id, receiver_ip, message_content)
    
    return jsonify({
        "success": success,
        "receiver_id": receiver_id,
        "message_id": message_id,
        "message": "Message sent and task assigned" if success else "Failed to send message"
    })


@app.route("/api/rust_location", methods=["GET"])
def api_rust_location():
    """Get predefined rust location and trigger robot assignment"""
    issue_type = "rust"
    issue_info = ISSUE_LOCATIONS.get(issue_type)
    
    if not issue_info:
        return jsonify({"success": False, "error": "Rust location not configured"}), 400
    
    try:
        handle_issue_detection(issue_type, issue_info["coordinates"])
        return jsonify({
            "success": True,
            "issue_type": issue_type,
            "coordinates": issue_info["coordinates"],
            "description": issue_info["description"],
            "robots_assigned": issue_info["robot_count"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/antenna_tilt_location", methods=["GET"])
def api_antenna_tilt_location():
    """Get predefined tilted antenna location and trigger robot assignment"""
    issue_type = "tilted_antenna"
    issue_info = ISSUE_LOCATIONS.get(issue_type)
    
    if not issue_info:
        return jsonify({"success": False, "error": "Tilted antenna location not configured"}), 400
    
    try:
        handle_issue_detection(issue_type, issue_info["coordinates"])
        return jsonify({
            "success": True,
            "issue_type": issue_type,
            "coordinates": issue_info["coordinates"],
            "description": issue_info["description"],
            "robots_assigned": issue_info["robot_count"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/circuit_overheat_location", methods=["GET"])
def api_circuit_overheat_location():
    """Get predefined overheated circuit location and trigger robot assignment"""
    issue_type = "overheated_circuit"
    issue_info = ISSUE_LOCATIONS.get(issue_type)
    
    if not issue_info:
        return jsonify({"success": False, "error": "Overheated circuit location not configured"}), 400
    
    try:
        handle_issue_detection(issue_type, issue_info["coordinates"])
        return jsonify({
            "success": True,
            "issue_type": issue_type,
            "coordinates": issue_info["coordinates"],
            "description": issue_info["description"],
            "robots_assigned": issue_info["robot_count"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print(f"\n[SERVER] Starting Network Server")
    print(f"[SERVER] TCP Listen Port (for drones/robots): {TCP_LISTEN_PORT}")
    print(f"[SERVER] TCP Robot Port (for commands): {TCP_ROBOT_PORT}")
    print(f"[SERVER] UDP Port: {UDP_PORT}\n")
    
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()
    threading.Thread(target=cleanup_stale_devices, daemon=True).start()
    
    app.run(host="0.0.0.0", port=5000, debug=False)
