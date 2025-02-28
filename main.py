import os
import math
import json
import requests
import threading
import asyncio
from time import sleep
from aiohttp import web
from python_chargepoint import ChargePoint

# Global settings (can be updated by WebSocket messages)
auto_adjust = True
manual_amperage_limit = None  # When not None, use this value instead of auto-adjusting.
overhead = int(os.getenv("MIN_POWER_OVERHEAD", 240))  # minimum_overhead setting.

# Load environment variables.
username = os.getenv("CHARGEPOINT_USERNAME")
password = os.getenv("CHARGEPOINT_PASSWORD")
pypowerwall_url = os.getenv("PYPOWERWALL_URL", "http://localhost:8675")
max_current_limit = os.getenv("MAX_CURRENT", 24)

# Global dictionary to hold the latest charging information.
latest_data = {
    "charging_status": None,
    "amperage_limit": None,
    "excess": None,
    "minimum_overhead": overhead,
    "total_solar": None,
}
data_lock = threading.Lock()

if not username or not password or not pypowerwall_url:
    print("Environment variables for username, password, or pypowerwall URL not set, exiting.")
    exit()

# Initialize the ChargePoint client.
client = ChargePoint(username=username, password=password)
chargers = client.get_home_chargers()
if not chargers:
    print("No chargers found, exiting.")
    exit()

def charging_monitor_loop():
    global latest_data, overhead, auto_adjust, manual_amperage_limit
    while True:
        try:
            charger = client.get_home_charger_status(charger_id=chargers[0])
        except Exception as e:
            print("Failed to get charger status:", e)
            sleep(15)
            continue
        charger_status = charger.charging_status
        print(f"Charger status: {charger_status} at {charger.amperage_limit}A")
        current_excess = 0

        try:
            response = requests.get(pypowerwall_url + "/aggregates")
            data = response.json()
            solar_power = data["solar"]["instant_power"]
            home_power = data["load"]["instant_power"]
            grid_power = data["site"]["instant_power"]
        except Exception as e:
            print("Failed to get Powerwall data:", e)
            sleep(30)
            continue

        # If we're pulling power from the grid, we don't want to be
        if grid_power < 0:
            grid_power = 0

        if charger_status == "CHARGING":
            charger_power = charger.amperage_limit * 240
        else:
            charger_power = 0
        current_excess = math.ceil(solar_power - home_power - grid_power + charger_power)

        # The charger might say CHARGING, but the car isn't actually pulling any current
        if home_power < charger_power:
            charger_status = "PLUGGED_IN"
            print("Not enough power in use")
        if charger_status == "NOT_CHARGING":
            charger_status = "PLUGGED_IN"

        # Update the global charging data.
        with data_lock:
            latest_data['charging_status'] = charger_status
            latest_data['amperage_limit'] = charger.amperage_limit
            latest_data['excess'] = current_excess
            latest_data['total_solar'] = solar_power

        if charger_status == "CHARGING":
            print(f"Charging at {charger_power}W with {current_excess} excess watts")
            # Use manual setting if auto_adjust is disabled.
            if not auto_adjust and manual_amperage_limit is not None:
                if manual_amperage_limit != charger.amperage_limit:
                    print(f"Setting charger to {manual_amperage_limit}A (manual override)")
                    try:
                        client.set_amperage_limit(chargers[0], manual_amperage_limit)
                    except Exception as e:
                        print("Failed to set charger amperage limit:", e)
            else:
                # Auto-adjust mode.
                if current_excess > latest_data['minimum_overhead']:
                    max_current = math.floor((current_excess - latest_data['minimum_overhead']) / 240)

                    if (current_excess < 0):
                        max_current = 8
                    
                    # Make sure we don't exceed our configured max limit
                    if max_current > max_current_limit:
                        max_current = max_current_limit

                    possible_limits = charger.possible_amperage_limits
                    valid_limits = [limit for limit in possible_limits if limit <= max_current]
                    if valid_limits:
                        max_current = max(valid_limits)
                    else:
                        max_current = 8
                    if max_current < 8 or max_current > 40:
                        max_current = 8
                    if max_current != charger.amperage_limit:
                        max_power = max_current * 240
                        print(f"Setting charger to {max_current}A to use {max_power}W")
                        try:
                            client.set_amperage_limit(chargers[0], max_current)
                            with data_lock:
                                latest_data['amperage_limit'] = max_current
                        except Exception as e:
                            print("Failed to set charger amperage limit:", e)
                else:
                    max_current = min(charger.possible_amperage_limits)
                    if charger.amperage_limit != max_current:
                        print(f"Setting charger to minimum possible amperage limit: {max_current}A")
                        try:
                            client.set_amperage_limit(chargers[0], max_current)
                            with data_lock:
                                latest_data['amperage_limit'] = max_current
                        except Exception as e:
                            print("Failed to set charger amperage limit:", e)
        else:
            print("Charger is not charging.")

        print()
        sleep(15)


# WebSocket handler that sends the latest charging data.
# WebSocket handler that both sends the latest charging data and listens for settings updates.
async def websocket_handler(request):
    global overhead, auto_adjust, manual_amperage_limit
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async def send_latest_data():
        while not ws.closed:
            with data_lock:
                data_to_send = latest_data.copy()
            await ws.send_json(data_to_send)
            await asyncio.sleep(5)

    async def receive_settings():
        nonlocal ws
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    settings = json.loads(msg.data)
                except json.JSONDecodeError:
                    print("Invalid JSON received:", msg.data)
                    continue

                # Update settings based on the received message.
                if "auto_adjust" in settings:
                    auto_adjust = settings["auto_adjust"]
                    print("auto_adjust set to", auto_adjust)
                if "amperage_limit" in settings:
                    manual_amperage_limit = settings["amperage_limit"]
                    print("manual_amperage_limit set to", manual_amperage_limit)
                if "minimum_overhead" in settings:
                    try:
                        new_overhead = int(settings["minimum_overhead"])
                        overhead = new_overhead
                        print("minimum_overhead set to", overhead)
                    except ValueError:
                        print("Invalid minimum_overhead value:", settings["minimum_overhead"])

                with data_lock:
                    latest_data["minimum_overhead"] = overhead
                
                print()

            elif msg.type == web.WSMsgType.ERROR:
                print("WebSocket connection closed with exception", ws.exception())

    # Run both sender and receiver concurrently.
    sender = asyncio.create_task(send_latest_data())
    receiver = asyncio.create_task(receive_settings())
    done, pending = await asyncio.wait(
        [sender, receiver],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    return ws


# Explicit route to serve index.html for the root path.
async def index_handler(request):
    static_dir = os.path.abspath('./static')
    index_path = os.path.join(static_dir, 'index.html')
    return web.FileResponse(index_path)

# Set up the aiohttp application.
app = web.Application()

# Add an explicit route for "/" that returns index.html.
app.router.add_get('/', index_handler)

# Serve all static files (including JS and CSS) from the current directory.
static_path = os.path.abspath('./static')
print("Serving static files from:", static_path)
app.router.add_static('/', path=static_path, show_index=True)

# WebSocket endpoint.
app.router.add_get('/ws', websocket_handler)

if __name__ == '__main__':
    # Start the charging monitor loop in a separate thread.
    monitor_thread = threading.Thread(target=charging_monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Run the HTTP and WebSocket server on port 8085.
    web.run_app(app, port=8085)
