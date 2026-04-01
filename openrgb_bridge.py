import sacn
import time
import usb.core
import usb.util
import libusb_package
import sys
import threading

# Initialize USB Device
print("Initializing SyncLight USB...")
backend = libusb_package.get_libusb1_backend()
dev = usb.core.find(idVendor=0x1A86, idProduct=0xFE07, backend=backend)
ep_out = None

if dev:
    try:
        dev.set_configuration()
    except Exception:
        pass
    
    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )

if not ep_out:
    print("WARNING: SyncLight device not found! Bridge will run but no lights will update.")
else:
    print("SyncLight hardware initialized successfully.")

last_send_time = 0

# Start sACN Receiver (Listens on port 5568 for E1.31 packets from OpenRGB)
receiver = sacn.sACNreceiver()
receiver.start()

# OpenRGB typically maps the first device to Universe 1, Channels 1 (R), 2 (G), 3 (B)
# Add these globals at the top if not present, or use them here
last_dmx_printed = None

@receiver.listen_on('universe', universe=1)
def callback(packet):
    global last_send_time
    
    now = time.time()
    if now - last_send_time < 0.05:
        return
    last_send_time = now
    
    if ep_out and len(packet.dmxData) >= 3:
        raw_r, raw_g, raw_b = packet.dmxData[0], packet.dmxData[1], packet.dmxData[2]
        
        # Hardware Color Calibration (neutralizing the cheap LED tint)
        # White reference: R:251, G:180, B:155
        r = int(raw_r * (251 / 255.0))
        g = int(raw_g * (180 / 255.0))
        b = int(raw_b * (155 / 255.0))
        
        payload = bytearray(
            [0x52, 0x42, 0x10, 0x01, 0x86, 0x01, r, g, b, 0x50, 0x51, 0x00, 0x00, 0x00, 0xFE, 0x00] + 
            [0x00] * 48
        )
        try:
            ep_out.write(payload)
        except Exception as e:
            pass

print("⚡ SyncLight OpenRGB Bridge is Running!")
print("Listening on E1.31 Universe 1 for lighting commands. Press Ctrl+C to exit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    receiver.stop()
    print("Gracefully stopped!")
