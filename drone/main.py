import socket
import time
import json
import threading
import logging
import os
import numpy as np
import cv2
import requests
from picamera2 import Picamera2


UDP_SERVER_PORT = 8888 
TCP_ACK_PORT = 9999          # Port for receiving ACK from base station
BASE_STATION_TCP_PORT = 9998  # Port for sending messages TO base station
HEARTBEAT_INTERVAL_SEC = 60

# QR Code to Issue Type Mapping
QR_CODE_TO_ISSUE = {
	"RUST_QR": "rust",
	"CIRCUIT_QR": "overheated_circuit",
	"ANTENNA_QR": "tilted_antenna"
}

# API Base URL for fetching QR data (adjust as needed)
API_BASE_URL = "http://localhost:5000/api"


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
	"""Handle QR code detection when the QR payload is an API URL.
	Returns the issue_type if fetched successfully so caller can dedupe."""
	logging.info(f"[QR] QR code detected; treating as API URL: {api_url}")

	api_data: dict = {}
	issue_type: str | None = None
	try:
		response = requests.get(api_url, timeout=5)
		if response.status_code == 200:
			api_data = response.json()
			issue_type = api_data.get("issue_type")
			logging.info(f"[QR] ✓ API data fetched: {api_data}")
			print(f"\n[QR] Scanned API: {api_url}")
			print(f"[QR] Data: {json.dumps(api_data, indent=2)}\n")
		else:
			logging.warning(f"[QR] API returned status {response.status_code}")
			api_data = {"error": f"API returned status {response.status_code}"}
	except requests.exceptions.Timeout:
		logging.warning("[QR] API request timed out")
		api_data = {"error": "API request timed out"}
	except requests.exceptions.ConnectionError:
		logging.warning("[QR] Could not connect to API")
		api_data = {"error": "Could not connect to API"}
	except Exception as e:
		logging.warning(f"[QR] Error fetching API data: {e}")
		api_data = {"error": str(e)}

	# Send QR_SCAN message to base station if we know the issue type
	if base_station_ip and issue_type:
		content = {
			"qr_code": api_url,
			"issue_type": issue_type,
			"api_data": api_data,
			"message": f"QR API {api_url} detected by {device_id}",
			"timestamp": time.time()
		}
		send_message_to_base_station(base_station_ip, "QR_SCAN", content)
	elif base_station_ip:
		logging.warning("[QR] No issue_type in API response; skipping send to base station")

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
				gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
				qr_data, bbox, _ = detector.detectAndDecode(gray)
				
				# If QR data is found, treat it as an API URL to fetch issue data
				if qr_data:
					if qr_data in sent_issues:
						logging.debug(f"[VIDEO] API {qr_data} already sent, ignoring")
					else:
						issue_type = qr_detected(qr_data, base_station_ip)
						if issue_type:
							sent_issues.add(qr_data)
							sent_issues.add(issue_type)
							logging.info(f"[VIDEO] Stored '{issue_type}' / {qr_data} in sent list")
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
