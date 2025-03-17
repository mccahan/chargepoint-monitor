# ChargePoint pyPowerwall Monitor

Use [pyPowerwall Proxy](https://github.com/jasonacox/pypowerwall) and [python-chargepoint](https://github.com/mbillow/python-chargepoint) alongside a ChargePoint Home Flex to charge your EV only off of excess solar power.

![ChargePoint Monitor Screenshot](screenshot.png)

## Warnings and Limitations

- The API doens't always respond very quickly to requests to the change in charge current limits, if you have huge swings in solar generation or home power usage (running a dryer, etc) you'll find yourself pulling hard from the Powerwall or grid sometimes
- This application currently **will not stop charging** when there isn't enough excess solar to meet the charger's lowest settings (8A for me). This is because with our VW id.4, if you stop charging because you had a really solid cloud cover, it won't restart on its own sometimes even if you re-enable charging through the Chargepoint app
- You should keep an eye on it to make sure it doesn't end up running up a bill during an on-peak Time of Use period for you
- Adjust your "Minimum Power Overhead" setting based on how fast you want your PW battery charging to reach its own fill on time, or if your solar power varies a lot during the day

## Other Notes

- This software functions best when the Powerwall is at <95% capacity, if you're not able to export power to the grid. As the battery gets close to full, the PW3 can curtail power generation from the solar panels to avoid overcharging, which makes it less obvious if there's any spare solar generation avaiable that's not being generated at all
- Above 95% charge, the software will try to "hunt" for a real solar power limit by trying to incrementally increase the charge current every 30 seconds to check to see whether the PW3 un-curtails solar generation and meets the increased demand. If it sees power getting pulled from the grid or the PW, it will incrementally back down again one amp at a time until it sees the system isn't pulling from the PW or grid anymore.

## Running with Docker

Assuming you have [pyPowerwall Proxy Server](https://github.com/jasonacox/pypowerwall/tree/main/proxy) running on localhost:8675:

```sh
docker run --rm -p 8085:8085 \
  -e CHARGEPOINT_USERNAME=YOUR_USERNAME \
  -e CHARGEPOINT_PASSWORD=YOUR_PASSWORD \
  -e PYPOWERWALL_URL=http://localhost:8675 \
  mccahan/chargepoint-monitor:latest
```

Then open your browser to http://localhost:8085/
