import requests
import math
import json
from python_chargepoint import ChargePoint
from time import sleep
import os

overhead = int(os.getenv("MIN_POWER_OVERHEAD", 240))
username = os.getenv("CHARGEPOINT_USERNAME")
pypowerwall_url = os.getenv("PYPOWERWALL_URL", "http://localhost:8675")
password = os.getenv("CHARGEPOINT_PASSWORD")
pypowerwall_url = os.getenv("PYPOWERWALL_URL")

if not username or not password or not pypowerwall_url:
  print("Environment variables for username, password, or pypowerwall URL not set, exiting.")
  exit()

client = ChargePoint(username=username, password=password)

chargers = client.get_home_chargers()

if not chargers:
  print("No chargers found, exiting.")
  exit()

while True:
    charger = client.get_home_charger_status(charger_id=chargers[0])
    print(f"Charger status: {charger.charging_status} at {charger.amperage_limit}A")
    if charger.charging_status == "CHARGING":
        try:
            response = requests.get(pypowerwall_url + "/aggregates")
            data = response.json()
            solar_power = data["solar"]["instant_power"]
            home_power = data["load"]["instant_power"]
        except:
            print("Failed to get Powerwall data")
            print()
            sleep(30)
            continue

        charger_power = charger.amperage_limit * 240
        excess = math.ceil(solar_power - home_power + charger_power)
        print(f"Charging at {charger_power} of {excess} excess watts")

        if excess > overhead:
            max_current = math.floor((excess - overhead) / 240)
            possible_limits = charger.possible_amperage_limits
            max_current = max([limit for limit in possible_limits if limit <= max_current], default=8)
            if max_current < 8 or max_current > 40:
                max_current = 8
            if max_current != charger.amperage_limit:
                max_power = max_current * 240
                print(f"Setting charger to {max_current}A to use {max_power}W")

                try:
                    client.set_amperage_limit(chargers[0], max_current)
                except:
                    print("Failed to set charger amperage limit")

    print()

    sleep(30)