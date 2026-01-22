import qrcode

# Use very short data (only 2-3 characters)
data = "3" 

qr = qrcode.QRCode(
    version=1, # Simplest version (21x21 grid)
    error_correction=qrcode.constants.ERROR_CORRECT_L, # Lowest correction = simplest pattern
    box_size=10,
    border=1,
)

qr.add_data(data)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
img.save("tilted_antenna.png")