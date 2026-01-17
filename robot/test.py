from flask import Flask, render_template_string, request
import logging

# Disable extra flask logging so the output is clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# The HTML/JavaScript that runs in your browser
HTML_SOURCE = """
<!DOCTYPE html>
<html>
<body>
    <script>
        function getLocation() {
            const options = {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            };

            navigator.geolocation.watchPosition(success, error, options);
        }

        function success(pos) {
            const data = {
                x: pos.coords.latitude,
                y: pos.coords.longitude,
                z: pos.coords.altitude || 0 // z is often null on PC browsers
            };
            
            // Send coordinates to the Python console
            fetch('/print_coords', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
        }

        function error(err) {
            console.warn(`ERROR(${err.code}): ${err.message}`);
        }

        window.onload = getLocation;
    </script>
    <h2>GPS Data is being sent to the Python Terminal...</h2>
    <p>Check your terminal for X, Y, Z output.</p>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_SOURCE)

@app.route('/print_coords', methods=['POST'])
def print_coords():
    coords = request.json
    print(f"X: {coords['x']:.8f} | Y: {coords['y']:.8f} | Z: {coords['z']} m")
    return "OK", 200

if __name__ == '__main__':
    print("1. Open your browser to http://127.0.0.1:5000")
    print("2. Allow location access when prompted.")
    print("-" * 40)
    app.run(host='0.0.0.0', port=5000)
