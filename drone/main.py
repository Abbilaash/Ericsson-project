import socket
import time
import json
import threading
import logging
import os
import cv2
from utils import detect_yellow


UDP_SERVER_PORT = 8888 
TCP_ACK_PORT = 9999   
HEARTBEAT_INTERVAL_SEC = 60
camera_ind = 0

ISSUE_TABLE = {
	"yellow":"robots"
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
	Send a message to the base station via TCP
	"""
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
		
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
			tcp.settimeout(2)
			tcp.connect((base_station_ip, 9999))
			tcp.sendall(json.dumps(msg).encode('utf-8'))
			logging.info(f"[SEND] Sent {message_type} message to base station at {base_station_ip}")
			return True
	except Exception as e:
		logging.error(f"[SEND] Failed to send message to base station: {e}")
		return False


def detected(issue: str, base_station_ip: str = None):
	"""Called when yellow or other issue is detected"""
	logging.info(f"[DETECTION] Issue detected: {issue}")
	if issue in ISSUE_TABLE:
		target = ISSUE_TABLE[issue]
		logging.info(f"[DETECTION] {issue.upper()} detected! Notifying {target}")
		
		# Send FORWARD_TO message to base station to relay to robots
		if base_station_ip:
			content = {
				"issue_type": issue,
				"message": f"{issue.upper()} detected by {device_id}",
				"timestamp": time.time()
			}
			send_message_to_base_station(base_station_ip, "FORWARD_TO", content)


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
	try:
		cap = cv2.VideoCapture("libcamerasrc ! video/x-raw,width=640,height=480 ! videoconvert ! appsink",
						 cv2.CAP_GSTREAMER)
		time.sleep(2)
		if not cap.isOpened():
			logging.error("[VIDEO] Failed to open camera")
			return
		logging.info("[VIDEO] Camera opened successfully")
		while not stop_event.is_set():
			ret, frame = cap.read()
			if not ret:
				logging.error("[VIDEO] Failed to capture frame")
				break
			is_yellow_detected, processed_frame = detect_yellow(frame)
			if is_yellow_detected:
				logging.info("YELLOW DETECTED")
				detected("yellow", base_station_ip)
			cv2.imshow('Drone Detection', processed_frame)
			if cv2.waitKey(1) & 0xFF == ord('q'):
				break
		cap.release()
		cv2.destroyAllWindows()
		logging.info("[VIDEO] Camera closed")
	except Exception as e:
		logging.error(f"[VIDEO] Error in video detection: {e}")


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
		hb_thread.join(timeout=5)
		video_thread.join(timeout=5)
		msg_thread.join(timeout=5)


if __name__ == "__main__":
	main()
