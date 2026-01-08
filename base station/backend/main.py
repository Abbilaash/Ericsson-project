import socket
import json
import threading
import time
from flask import Flask, jsonify, request
import flask_cors


def get_base_station_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

TCP_PORT = 9999
UDP_PORT = 8888
BUFFER_SIZE = 8192
BASE_STATION_IP = get_base_station_ip()

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
        server_sock.bind(("0.0.0.0", TCP_PORT))
        server_sock.listen(10)
        print(f"[SERVER] TCP server listening on port {TCP_PORT}")
        
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
    try:
        while True:
            data = client_sock.recv(BUFFER_SIZE)
            if not data:
                break
            try:
                msg = json.loads(data.decode('utf-8'))
                print(f"[TCP] Received from {client_ip}: {msg.get('message_type', 'UNKNOWN')}")
                log_packet(
                    direction="in",
                    transport="TCP",
                    packet_type="MESSAGE",
                    message_type=msg.get('message_type', 'UNKNOWN'),
                    sender_id=msg.get('sender_id') or client_ip,
                    receiver_id="base_station",
                    payload=msg,
                )
            except:
                pass
    except Exception as e:
        print(f"[TCP] Error handling client {client_ip}: {e}")
    finally:
        client_sock.close()
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
                reply_tcp_port = msg.get('reply_tcp_port', TCP_PORT)
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
                elif message_type == "HEARTBEAT" and device_id:
                    if device_id in devices:
                        devices[device_id]["updated_at"] = time.time()
                        devices[device_id]["battery_health"] = msg.get('battery_health', 100)
                        print(f"[UDP] Updated {device_id} heartbeat (battery: {msg.get('battery_health', 'N/A')}%)")
                        log_packet(
                            direction="in",
                            transport="UDP",
                            packet_type="STATUS",
                            message_type="HEARTBEAT",
                            sender_id=device_id,
                            receiver_id="base_station",
                            payload=msg,
                        )

            except Exception as e:
                print(f"[UDP] Error processing message: {e}")
    
    except Exception as e:
        print(f"[UDP] Listener error: {e}")

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
        entry = {
            "id": norm_id,
            "original_id": dev_id,
            "battery": dev.get("battery_health"),
            "status": dev.get("status"),
            "last_seen": dev.get("updated_at"),
            "position": dev.get("position"),
            "ip": dev.get("ip"),
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


if __name__ == "__main__":
    print(f"\n[SERVER] Starting Network Server")
    print(f"[SERVER] TCP Port: {TCP_PORT}")
    print(f"[SERVER] UDP Port: {UDP_PORT}\n")
    
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()
    
    app.run(host="0.0.0.0", port=5000, debug=False)
