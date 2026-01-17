import socket
import time
import json
import threading
import logging
import os


UDP_SERVER_PORT = 8888 
TCP_ACK_PORT = 9999          # Port for receiving ACK from base station
BASE_STATION_TCP_PORT = 9998  # Port for sending messages TO base station
HEARTBEAT_INTERVAL_SEC = 60

# Issue types handled by this robot
ISSUE_TYPES = {
	"rust": "robot_task",
	"overheated_circuit": "robot_task",
	"tilted_antenna": "robot_task"
}


logging.basicConfig(
	level=logging.INFO,
	format="[%(asctime)s] %(levelname)s: %(message)s",
)


def get_local_ip() -> str:
	try:
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
			s.connect(("8.8.8.8", 80))
			return s.getsockname()[0]
	except Exception:
		return "127.0.0.1"


sender_ip = get_local_ip()
device_id = f"ROBOT_{sender_ip.replace('.', '')}"

# Persistent connection to base station for sending messages
message_sender_socket = None
message_sender_lock = threading.Lock()

# Current task/movement
current_task = None
task_lock = threading.Lock()

def broadcast_join(reply_tcp_port: int = TCP_ACK_PORT) -> None:
	timestamp = time.time()
	payload = {
		"message_id": f"{int(timestamp * 1000000)}",
		"timestamp": int(timestamp),
		"message_type": "CONNECTION_REQUEST",
		"device_id": device_id,
		"device_type": "robot",
		"sender_ip": sender_ip,
		"reply_tcp_port": reply_tcp_port,
		"position": {"x": 0, "y": 0, "z": 0}
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


def get_battery_health() -> int:
	# Try environment variable first
	val = os.getenv("ROBOT_BATTERY")
	if val is not None:
		try:
			v = int(val)
			return max(0, min(100, v))
		except ValueError:
			pass
	
	# Try Ubuntu battery file
	try:
		with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
			val = f.read().strip()
			if val:
				v = int(val)
				return max(0, min(100, v))
	except Exception:
		pass
	
	# Default fallback
	return 100


def send_heartbeat(base_station_ip: str, stop_event: threading.Event | None = None) -> None:
	sender_ip = get_local_ip()

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


def send_message_to_base_station(base_station_ip: str, message_type: str, content: dict):
	"""
	Send a message to the base station via persistent TCP connection (newline-delimited JSON)
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
						if attempt == 1:  # Last attempt
							return False
						continue
				
				try:
					# Send JSON message with newline delimiter
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
					
					if attempt == 1:  # Last attempt failed
						return False
					# Otherwise, loop will retry with new connection
			
			return False
	
	except Exception as e:
		logging.error(f"[SEND] Error in send_message_to_base_station: {e}")
		return False


def handle_forward_message(msg: dict):
	"""Handle FORWARD_ALL or FORWARD_TO messages from base station"""
	message_type = msg.get("message_type", "")
	content = msg.get("content", {})
	
	if message_type == "FORWARD_ALL":
		logging.info(f"[MESSAGE] FORWARD_ALL received: {content}")
		# Handle broadcast message
	elif message_type == "FORWARD_TO":
		logging.info(f"[MESSAGE] FORWARD_TO received: {content}")
		# Handle direct message
	else:
		logging.warning(f"[MESSAGE] Unknown message type: {message_type}")


def handle_movement_command(msg: dict, base_station_ip: str = None):
	"""Handle movement commands from base station"""
	global current_task
	
	content = msg.get("content", {})
	
	# Accept either "issue_type" or "color" (for backward compatibility with old base station)
	issue_type = content.get("issue_type") or content.get("color")
	coordinates = content.get("coordinates")
	command = content.get("command")
	message_id = msg.get("message_id")

	# Validate required fields before proceeding
	if not issue_type:
		logging.error("[MOVEMENT] Missing issue_type/color in movement command; skipping")
		logging.error(f"[MOVEMENT] DEBUG - content keys: {list(content.keys())}")
		return
	if not coordinates or not isinstance(coordinates, dict):
		logging.error("[MOVEMENT] Missing or invalid coordinates in movement command; skipping")
		return

	logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")
	logging.info(f"[MOVEMENT] NEW TASK ASSIGNED")
	logging.info(f"[MOVEMENT] Issue type to rectify: {issue_type.upper()}")
	logging.info(f"[MOVEMENT] Location: X={coordinates.get('x')}, Y={coordinates.get('y')}, Z={coordinates.get('z')}")
	logging.info(f"[MOVEMENT] Task ID: {message_id}")
	logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")
	
	# Store current task
	with task_lock:
		current_task = {
			"message_id": message_id,
			"issue_type": issue_type,
			"coordinates": coordinates,
			"command": command,
			"received_at": time.time(),
			"status": "in_progress"
		}
	
	# Perform the movement and rectification
	if command == "move_to_location":
		try:
			# Step 1: Move to location
			logging.info(f"[MOVEMENT] → Moving to coordinates: {coordinates}")
			logging.info(f"[MOVEMENT] → Motor control: Activating movement...")
			# TODO: Replace with actual motor control code
			# e.g., motor_controller.move_to(coordinates['x'], coordinates['y'], coordinates['z'])
			time.sleep(3)  # Simulate travel time
			logging.info(f"[MOVEMENT] ✓ Arrived at location")
			
			# Step 2: Rectify the issue
			logging.info(f"[MOVEMENT] → Starting issue rectification for {issue_type.upper()}")
			logging.info(f"[MOVEMENT] → Activating remediation mechanism...")
			# TODO: Replace with actual rectification mechanism
			# e.g., remediation_system.fix_issue(issue_type)
			time.sleep(2)  # Simulate remediation time
			logging.info(f"[MOVEMENT] ✓ Issue {issue_type.upper()} rectified successfully")
			
			# Step 3: Update task status
			with task_lock:
				if current_task:
					current_task["status"] = "completed"
					current_task["completed_at"] = time.time()
			
			# Step 4: Report completion back to base station
			if base_station_ip:
				completion_report = {
					"task_id": message_id,
					"issue_type": issue_type,
					"coordinates": coordinates,
					"status": "completed",
					"message": f"Successfully rectified {issue_type} at location {coordinates}"
				}
				
				logging.info(f"[MOVEMENT] → Reporting task completion to base station...")
				success = send_message_to_base_station(base_station_ip, "TASK_COMPLETED", completion_report)
				
				if success:
					logging.info(f"[MOVEMENT] ✓ Task completion reported to base station")
				else:
					logging.error(f"[MOVEMENT] ✗ Failed to report completion to base station")
			
			logging.info(f"[MOVEMENT] ═══════════════════════════════════════════")
			logging.info(f"[MOVEMENT] TASK COMPLETED - Ready for next assignment")
			logging.info(f"[MOVEMENT] ═══════════════════════════════════════════\n")
			
			# Clear current task
			with task_lock:
				current_task = None
				
		except Exception as e:
			logging.error(f"[MOVEMENT] ✗ Error during task execution: {e}")
			with task_lock:
				if current_task:
					current_task["status"] = "failed"
					current_task["error"] = str(e)


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


def receive_messages(stop_event: threading.Event, base_station_ip: str = None) -> None:
	"""Listen for incoming messages from base station on TCP port 9999"""
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
				
				# Handle the incoming message (newline-delimited JSON)
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
								
								if message_type == "MOVEMENT_COMMAND":
									# Handle movement command in a separate thread
									threading.Thread(
										target=handle_movement_command,
										args=(msg, base_station_ip),
										daemon=True
									).start()
								elif message_type in ["FORWARD_ALL", "FORWARD_TO"]:
									handle_forward_message(msg)
								else:
									logging.info(f"[MESSAGE] Received: {message_type}")
							except json.JSONDecodeError:
								pass
				
				except Exception as e:
					logging.error(f"[MESSAGE] Error processing message: {e}")
				finally:
					client_sock.close()
			
			except socket.timeout:
				continue
			except Exception as e:
				logging.error(f"[MESSAGE] Error accepting connection: {e}")
				break
		
		server_sock.close()
		logging.info("[MESSAGE] Message server closed")
	
	except Exception as e:
		logging.error(f"[MESSAGE] Error in receive_messages: {e}")


def main():
	broadcast_join(reply_tcp_port=TCP_ACK_PORT)
	base_ip = wait_for_tcp_ack(listen_port=TCP_ACK_PORT, timeout_sec=120)
	if not base_ip:
		logging.error("No base station ACK received; exiting")
		return
	logging.info("Stored base station IP: %s", base_ip)
	
	stop_event = threading.Event()
	
	# Start heartbeat thread
	hb_thread = threading.Thread(target=send_heartbeat, args=(base_ip, stop_event), daemon=True)
	hb_thread.start()
	
	# Start message receiver thread with base_ip for task completion reporting
	msg_thread = threading.Thread(target=receive_messages, args=(stop_event, base_ip), daemon=True)
	msg_thread.start()
	
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		logging.info("Shutting down...")
		stop_event.set()
		cleanup_connections()
		hb_thread.join(timeout=5)
		msg_thread.join(timeout=5)


if __name__ == "__main__":
	main()
