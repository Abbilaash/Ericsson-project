import logging
from typing import Optional

try:
	import serial
except ImportError as exc:
	raise ImportError("pyserial is required: pip install pyserial") from exc


def send_serial_command(letter: str,port: str = "COM3",baudrate: int = 9600,timeout: float = 2.0) -> bool:
	if not letter:
		logging.error("No letter provided for serial send")
		return False
	byte_to_send = letter[0].encode("ascii", errors="ignore")
	if not byte_to_send:
		logging.error("Provided letter is not ASCII-encodable")
		return False
	try:
		with serial.Serial(port=port, baudrate=baudrate, timeout=timeout) as ser:
			ser.reset_output_buffer()
			written = ser.write(byte_to_send)
			ser.flush()
			success = written == 1
			if success:
				logging.info("Sent byte %s to %s", byte_to_send, port)
			else:
				logging.error("Failed to write full byte to %s", port)
			return success
	except serial.SerialException as exc:
		logging.error("Serial error on %s: %s", port, exc)
		return False
	except Exception as exc:  # pragma: no cover
		logging.error("Unexpected error sending serial byte: %s", exc)
		return False
