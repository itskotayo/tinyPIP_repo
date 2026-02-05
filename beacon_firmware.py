import network, time

def read_battery():
    # Replace with your ADC pin if you wire one
    # For now, return a fake number for testing
    return 87

def start_beacon():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    while True:
        battery = read_battery()
        ssid = "BEACON|{}".format(battery)

        ap.config(essid=ssid, authmode=network.AUTH_OPEN)
        time.sleep(5)

start_beacon()