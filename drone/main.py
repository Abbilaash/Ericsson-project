import socket
import time
import json
import threading
import logging
import os
import math
import numpy as np
import cv2
import requests
from picamera2 import Picamera2


UDP_SERVER_PORT = 8888 
TCP_ACK_PORT = 9999          # Port for receiving ACK from base station
BASE_STATION_TCP_PORT = 9998  # Port for sending messages TO base station
HEARTBEAT_INTERVAL_SEC = 60
POSITION_UPDATE_INTERVAL_SEC = 1  # Update position every 1 second

# Drone position (simulated - in real scenario would come from GPS/sensors)
drone_position = {"x": 10.0, "y": 20.0, "z": 15.0}

# QR Code to Issue Type Mapping
QR_CODE_TO_ISSUE = {
	"RUST_QR": "rust",
	"CIRCUIT_QR": "overheated_circuit",
	"ANTENNA_QR": "tilted_antenna"
}

# API Base URL for fetching QR data (adjust as needed)
API_BASE_URL = "http://192.168.226.132:5000/api"

# Lookup table to resolve short QR payloads (like "1") to full API URLs
# You can update these endpoints to match your backend routes.
LOCATION_LOOKUP = {
	# Numeric aliases
	"1": f"{API_BASE_URL}/rust_location",
	"2": f"{API_BASE_URL}/circuit_overheat_location",
	"3": f"{API_BASE_URL}/antenna_tilt_location",

	# Text aliases (case-insensitive lookup also supported)
	"rust": f"{API_BASE_URL}/rust_location",
	"overheated_circuit": f"{API_BASE_URL}/circuit_overheat_location",
	"tilted_antenna": f"{API_BASE_URL}/antenna_tilt_location",
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
device_id = f"DRONE_{sender_ip.replace('.', '')}"

# Persistent connection to base station for sending messages
message_sender_socket = None
message_sender_lock = threading.Lock()

def broadcast_join(reply_tcp_port: int = TCP_ACK_PORT) -> None:
	timestamp = time.time()
	payload = {
		"message_id": f"{int(timestamp * 1000000)}",
		"timestamp": int(timestamp),
		"message_type": "CONNECTION_REQUEST",
		"device_id": device_id,
		"device_type": "drone",
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
	val = os.getenv("DRONE_BATTERY")
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


def qr_detected(api_url: str, base_station_ip: str = None) -> str | None:
	"""Handle QR code detection.
	Accepts either a full API URL or a short alias (e.g., '1').
	Resolves aliases via LOCATION_LOOKUP before fetching.
	Returns the issue_type if fetched successfully so caller can dedupe."""
	raw_qr = (api_url or "").strip()

	# Resolve short alias or textual key to API URL if present
	resolved_url = None
	if raw_qr:
		# Exact match
		resolved_url = LOCATION_LOOKUP.get(raw_qr)
		# Case-insensitive fallback
		if resolved_url is None:
			resolved_url = LOCATION_LOOKUP.get(raw_qr.lower())

	api_url_to_fetch = resolved_url or raw_qr
	if resolved_url:
		logging.info(f"[QR] Resolved QR '{raw_qr}' -> {api_url_to_fetch}")
	else:
		logging.info(f"[QR] QR payload treated as URL: {api_url_to_fetch}")

	api_data: dict = {}
	issue_type: str | None = None
	max_retries = 2
	retry_delay = 1  # seconds between retries
	
	for attempt in range(max_retries):
		try:
			# Set proper headers and follow redirects
			headers = {
				'User-Agent': 'Mozilla/5.0 (Linux; Drone) DroneClient/1.0',
				'Accept': 'application/json'
			}
			logging.info(f"[QR] Fetching API (attempt {attempt + 1}/{max_retries}): {api_url_to_fetch}")
			response = requests.get(api_url_to_fetch, timeout=15, headers=headers, allow_redirects=True)
			response.raise_for_status()  # Raise exception for HTTP errors
			
			# Log response details for debugging
			logging.debug(f"[QR] Response status: {response.status_code}")
			logging.debug(f"[QR] Response headers: {dict(response.headers)}")
			logging.debug(f"[QR] Response text: {response.text[:500]}")  # First 500 chars
			
			# Check if response is empty
			if not response.text or not response.text.strip():
				logging.warning("[QR] API returned empty response body")
				api_data = {"error": "Empty response from API"}
				issue_type = "empty_response"
			else:
				try:
					api_data = response.json()
					issue_type = api_data.get("issue_type", "unknown")
					# Prefer issue coordinates from API if provided
					api_coordinates = api_data.get("coordinates") if isinstance(api_data, dict) else None
					logging.info(f"[QR] ✓ API data fetched: {api_data}")
					print(f"\n[QR] Scanned API: {api_url_to_fetch}")
					print(f"[QR] Data: {json.dumps(api_data, indent=2)}\n")
					break  # Success, exit retry loop
				except json.JSONDecodeError as je:
					logging.error(f"[QR] Failed to parse JSON: {je}")
					logging.error(f"[QR] Response was: {response.text[:200]}")
					api_data = {"error": "Invalid JSON response", "raw_response": response.text[:200]}
					issue_type = "invalid_json"
					break  # No point retrying JSON parse errors
			
			break  # Success
			
		except requests.exceptions.HTTPError as he:
			logging.warning(f"[QR] HTTP Error (attempt {attempt + 1}): {he.response.status_code}")
			api_data = {"error": f"HTTP {he.response.status_code}: {he.response.reason}"}
			issue_type = f"http_{he.response.status_code}"
			if attempt < max_retries - 1:
				logging.info(f"[QR] Retrying in {retry_delay}s...")
				time.sleep(retry_delay)
		except requests.exceptions.Timeout:
			logging.warning(f"[QR] API request timed out (15 seconds) - attempt {attempt + 1}/{max_retries}")
			api_data = {"error": "API request timed out"}
			issue_type = "timeout"
			if attempt < max_retries - 1:
				logging.info(f"[QR] Retrying in {retry_delay}s...")
				time.sleep(retry_delay)
		except requests.exceptions.ConnectionError as ce:
			logging.warning(f"[QR] Could not connect to API (attempt {attempt + 1}): {ce}")
			api_data = {"error": "Could not connect to API"}
			issue_type = "connection_error"
			if attempt < max_retries - 1:
				logging.info(f"[QR] Retrying in {retry_delay}s...")
				time.sleep(retry_delay)
		except Exception as e:
			logging.warning(f"[QR] Unexpected error (attempt {attempt + 1}): {type(e).__name__}: {e}")
			api_data = {"error": str(e)}
			issue_type = "unknown_error"
			if attempt < max_retries - 1:
				logging.info(f"[QR] Retrying in {retry_delay}s...")
				time.sleep(retry_delay)

	# Send QR_SCAN message to base station even if issue_type is missing or error
	if base_station_ip:
		content = {
			# Keep both original and resolved forms for observability
			"qr_raw": raw_qr,
			"qr_code": api_url_to_fetch,
			"issue_type": issue_type,
			# Use API-provided coordinates if available; fallback to drone position
			"coordinates": api_data.get("coordinates") if isinstance(api_data, dict) and api_data.get("coordinates") else drone_position,
			"api_data": api_data,
			"message": f"QR {raw_qr} detected by {device_id}",
			"timestamp": time.time()
		}
		success = send_message_to_base_station(base_station_ip, "QR_SCAN", content)
		if success:
			logging.info(f"[QR] ✓ Sent QR_SCAN to base station (issue_type={issue_type})")
		else:
			logging.error(f"[QR] ✗ Failed to send QR_SCAN to base station")
	else:
		logging.warning("[QR] No base_station_ip provided; cannot send QR_SCAN")

	return issue_type


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


def receive_messages(stop_event: threading.Event) -> None:
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
				
				# Handle the incoming message
				try:
					data = client_sock.recv(4096)
					if data:
						msg = json.loads(data.decode('utf-8'))
						message_type = msg.get('message_type')
						
						if message_type in ["FORWARD_ALL", "FORWARD_TO"]:
							handle_forward_message(msg)
						else:
							logging.info(f"[MESSAGE] Received: {message_type}")
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


def start_video_detection(stop_event: threading.Event, base_station_ip: str = None) -> None:
	"""Detect and decode QR codes using PiCamera2 and OpenCV"""
	picam2 = None
	sent_issues = set()  # Track which issues have already been sent to base station
	try:
		# Setup the Camera
		logging.info("[VIDEO] Initializing PiCamera2 for QR code detection...")
		picam2 = Picamera2()
		config = picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
		picam2.configure(config)
		picam2.start()
		
		# Initialize OpenCV QR Code Detector
		detector = cv2.QRCodeDetector()
		
		# Wait for camera to stabilize
		time.sleep(2)
		logging.info("[VIDEO] Camera initialized, starting QR code detection")
		
		while not stop_event.is_set():
			try:
				frame = picam2.capture_array()
				small_frame = cv2.resize(frame, (320, 240))
				gray = cv2.cvtColor(small_frame, cv2.COLOR_RGB2GRAY)
				qr_data, bbox, _ = detector.detectAndDecode(gray)
				
				# If QR data is found, treat it as an API URL to fetch issue data
				if qr_data:
					# Create location-based key to prevent duplicate detections at same location
					issue_key = f"{qr_data}_{drone_position['x']}_{drone_position['y']}_{drone_position['z']}"
					
					if issue_key in sent_issues:
						logging.debug(f"[VIDEO] Issue at location ({drone_position['x']}, {drone_position['y']}, {drone_position['z']}) already sent, ignoring")
					else:
						issue_type = qr_detected(qr_data, base_station_ip)
						if issue_type:
							sent_issues.add(issue_key)
							logging.info(f"[VIDEO] ✓ Stored issue key '{issue_key}' in sent list")
						else:
							logging.debug(f"[VIDEO] API {qr_data} did not return issue_type; not storing")
				
				# Small delay to prevent CPU spinning
				time.sleep(0.01)
				
			except Exception as e:
				logging.error(f"[VIDEO] Error processing frame: {e}")
				break
		
		logging.info("[VIDEO] QR code detection stopped")
		
	except Exception as e:
		logging.error(f"[VIDEO] Error in video detection: {e}")
	finally:
		if picam2:
			try:
				picam2.stop()
				logging.info("[VIDEO] Camera closed")
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


def main():
	global inspection_waypoints, patrol_active, tower_location
	
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

	# Start video detection thread with base_ip for message sending
	video_thread = threading.Thread(target=start_video_detection, args=(stop_event, base_ip), daemon=True)
	video_thread.start()
	
	# Start message receiver thread
	msg_thread = threading.Thread(target=receive_messages, args=(stop_event,), daemon=True)
	msg_thread.start()
	
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		logging.info("Shutting down...")
		stop_event.set()
		cleanup_connections()
		hb_thread.join(timeout=5)
		video_thread.join(timeout=5)
		msg_thread.join(timeout=5)


if __name__ == "__main__":
	main()
