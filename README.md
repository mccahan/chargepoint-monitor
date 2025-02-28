# ChargePoint pyPowerwall Monitor

Use [pyPowerwall Proxy](https://github.com/jasonacox/pypowerwall) and [python-chargepoint](https://github.com/mbillow/python-chargepoint) alongside a ChargePoint Home Flex to charge your EV only off of excess solar power.

![ChargePoint Monitor Screenshot](screenshot.png)

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