# 🚥 SyncLight OpenRGB Bridge

This lightweight custom software bridge seamlessly links your generic Chinese CH341 USB LED Strips (VID: `0x1A86`, PID: `0xFE07`) directly into the **OpenRGB** ecosystem. It mimics an E1.31 network device perfectly, allowing instant frame-perfect RGB syncing mapped alongside all of your ASUS graphics cards and premium gaming hardware!

---

## 🛠️ Step 1: Pre-Requisite USB Driver Swap (Zadig)
By default, Windows installs a stubborn core serial driver that aggressively blocks background hardware access. We need to overwrite it with `WinUSB` or `libusb-win32` so the Python bridge can blast colors to the endpoint without throwing "Access Denied."

1. Unplug the LED strip and **plug it back in**.
2. Download [Zadig](https://zadig.akeo.ie/) and run the `.exe` as Administrator.
3. In the Zadig top menu, select **Options -> List All Devices**.
4. Open the large dropdown menu and find your light. It's often generically named something like **USB2.0-Serial** or **Unknown HID Device**. (Double-check that the USB ID string says exactly `1A86 FE07`).
5. On the right side of the green arrow, scroll to either **WinUSB** or **libusbK**.
6. Click the big **Replace Driver** button and wait a few seconds.

*That’s it! Windows will now let our script freely communicate with the lights.*

---

## 💻 Step 2: Adding it to OpenRGB
Since the physical USB driver is now unlocked, you need to tell OpenRGB to route lighting commands locally over the loopback protocol. 

1. Ensure `SyncLight-OpenRGB-Bridge.exe` is currently running in your Windows background. (I've already added a shortcut directly to your `shell:startup` folder so this happens completely automatically every time you log in!)
2. Launch **OpenRGB**.
3. Open the **E1.31 Devices** settings window.
4. Set up the network receiver using exactly these options:
   - **Name:** `Local_SyncLight` (or whatever you prefer)
   - **IP:** `127.0.0.1`
   - **Start Universe:** `1`
   - **Start Channel:** `1` *(CRITICAL: Must not be 0, or Red will be mathematically omitted!)*
   - **Number of LEDs:** `1`
   - **Type:** `Single`
   - **RGB Order:** `RGB`
5. Enable the checkbox next to the row, click **Save**.
6. Back on the main dashboard, hit **Rescan Devices** at the bottom if it doesn't appear instantly.

---

## 🎨 Advanced Color Calibration Note
Since cheap LED diodes run "cold" (naturally tinted quite blue/green out of the factory), sending standard absolute `(255, 255, 255)` White completely washes out. 

Inside the `openrgb_bridge.py` backend source code, a strict physical neutral calibration matrix is hardcoded: `R: 251 | G: 180 | B: 155`. You don't have to manage this! Even when you set standard white in OpenRGB, it mathematically squashes it down to your preferred neutral tint right before broadcasting over USB!
