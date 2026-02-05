import network
import utime
import json

def wifi_fallback_update():
    # Reset WiFi stack
    ap = network.WLAN(network.AP_IF)
    ap.active(False)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    utime.sleep_ms(200)
    wlan.active(True)
    utime.sleep_ms(200)

    # --- Load saved WiFi credentials ---
    saved_ssid = None
    saved_pass = None

    try:
        with open("wifi.json") as f:
            data = json.loads(f.read())
            saved_ssid = data.get("ssid", "")
            saved_pass = data.get("password", "")
    except:
        pass

    # --- Connection helper ---
    def try_connect(ssid, password=None):
        wlan.connect(ssid, password)
        for _ in range(150):  # 15 seconds
            if wlan.isconnected():
                return True
            utime.sleep_ms(100)
        return False

    connected = False

    # --- Try saved WiFi first ---
    if saved_ssid:
        if try_connect(saved_ssid, saved_pass):
            connected = True

    # --- Try open networks if saved WiFi fails ---
    if not connected:
        try:
            nets = wlan.scan()
        except:
            nets = []

        open_nets = []
        for n in nets:
            ssid = n[0].decode() if isinstance(n[0], bytes) else n[0]
            rssi = n[3]
            auth = n[4]
            if auth == 0 and ssid:
                open_nets.append((ssid, rssi))

        if open_nets:
            open_nets.sort(key=lambda x: x[1], reverse=True)
            best_open = open_nets[0][0]
            if try_connect(best_open):
                connected = True

    # --- If still not connected, fail ---
    if not connected:
        wlan.active(False)
        return False

    # --- Sync time ---
    try:
        import ntptime
        ntptime.settime()
    except:
        pass

    # --- Sync weather ---
    try:
        from weather import update_weather
        update_weather()
    except:
        pass

    # --- Disconnect + turn off WiFi ---
    try:
        wlan.disconnect()
    except:
        pass

    wlan.active(False)

    return True