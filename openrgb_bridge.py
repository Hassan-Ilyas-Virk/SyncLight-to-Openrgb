import sacn
import time
import usb.core
import usb.util
import libusb_package
import sys
import json
import os

# ─── Configuration ───────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "synclight_config.json")
MAX_USB_RETRIES = 30        # Try for up to 60 seconds on cold boot
RETRY_DELAY_SEC = 2         # Wait 2s between each retry
THROTTLE_SEC = 0.05         # Max 20 Hz USB writes

# ─── USB Initialization (with cold-boot retry) ──────────────
def connect_usb():
    """Attempt to connect to the SyncLight USB device, retrying on failure."""
    backend = libusb_package.get_libusb1_backend()
    
    for attempt in range(1, MAX_USB_RETRIES + 1):
        print(f"[Attempt {attempt}/{MAX_USB_RETRIES}] Searching for SyncLight USB...")
        dev = usb.core.find(idVendor=0x1A86, idProduct=0xFE07, backend=backend)
        
        if dev is None:
            print(f"  Device not found. Retrying in {RETRY_DELAY_SEC}s...")
            time.sleep(RETRY_DELAY_SEC)
            continue
        
        try:
            dev.set_configuration()
        except Exception:
            pass
        
        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]
            ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            if ep_out:
                print("SyncLight USB connected successfully!")
                return ep_out
            else:
                print("  Found device but no OUT endpoint. Retrying...")
        except usb.core.USBError as e:
            print(f"  USB access error: {e}. Retrying in {RETRY_DELAY_SEC}s...")
        except Exception as e:
            print(f"  Unexpected error: {e}. Retrying in {RETRY_DELAY_SEC}s...")
        
        time.sleep(RETRY_DELAY_SEC)
    
    return None

def send_color(ep_out, r, g, b):
    """Send a calibrated RGB color to the SyncLight hardware."""
    payload = bytearray(
        [0x52, 0x42, 0x10, 0x01, 0x86, 0x01, r, g, b, 0x50, 0x51, 0x00, 0x00, 0x00, 0xFE, 0x00] +
        [0x00] * 48
    )
    ep_out.write(payload)

# ─── Main Startup ───────────────────────────────────────────
print("═══════════════════════════════════════")
print("  SyncLight OpenRGB Bridge v2.0")
print("═══════════════════════════════════════")

ep_out = connect_usb()

if not ep_out:
    # All retries exhausted — show a helpful error popup
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "SyncLight USB Error",
            "Could not connect to the SyncLight USB device after 60 seconds.\n\n"
            "Possible causes:\n"
            "• The LED strip is not plugged in\n"
            "• Windows reverted the USB driver\n\n"
            "Solution:\n"
            "1. Check that the LED strip is plugged in.\n"
            "2. Open Zadig and re-install the WinUSB driver.\n"
            "3. Run this bridge again."
        )
    except Exception:
        pass
    sys.exit(1)

# ─── Wake the device with the last saved color ──────────────
current_saved_color = None
last_save_time = 0

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            r, g, b = data.get("r", 255), data.get("g", 255), data.get("b", 255)
            send_color(ep_out, r, g, b)
            current_saved_color = (r, g, b)
            print(f"Applied startup color: RGB({r}, {g}, {b})")
    except Exception:
        print("No saved color found, device is awake with default state.")
else:
    # First run ever — wake the device with white
    try:
        send_color(ep_out, 251, 180, 155)
        print("First run — applied calibrated white.")
    except Exception:
        pass

# ─── Start sACN / E1.31 Receiver ────────────────────────────
last_send_time = 0
receiver = sacn.sACNreceiver()
receiver.start()

@receiver.listen_on('universe', universe=1)
def callback(packet):
    global last_send_time, current_saved_color, last_save_time

    now = time.time()
    if now - last_send_time < THROTTLE_SEC:
        return
    last_send_time = now

    if ep_out and len(packet.dmxData) >= 3:
        raw_r, raw_g, raw_b = packet.dmxData[0], packet.dmxData[1], packet.dmxData[2]

        # Hardware Color Calibration (neutralizing cheap LED tint)
        # White reference: R:251, G:180, B:155
        r = int(raw_r * (251 / 255.0))
        g = int(raw_g * (180 / 255.0))
        b = int(raw_b * (155 / 255.0))

        try:
            send_color(ep_out, r, g, b)

            # Auto-save color (throttled to every 2s to protect SSD)
            if current_saved_color != (r, g, b) and now - last_save_time > 2.0:
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"r": r, "g": g, "b": b}, f)
                current_saved_color = (r, g, b)
                last_save_time = now
        except Exception:
            pass

print("⚡ Bridge is LIVE — listening on E1.31 Universe 1")
print("Press Ctrl+C to exit.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    receiver.stop()
    print("Gracefully stopped!")
