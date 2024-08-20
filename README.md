# Shelly Device Control Script

## Overview

This script controls Shelly relay and lamp devices based on the power output from a connected power source. The script monitors the power output and toggles the devices on or off based on predefined high and low power thresholds. All actions are logged, ensuring that devices are only turned on or off when necessary.

## Features

- **Automatic Device Control**: The script automatically turns on devices when power output exceeds a high threshold and turns them off when it falls below a low threshold.
- **State Checking**: Before turning off a device, the script checks whether the device was turned on by the script and whether it is currently on, preventing unnecessary actions.
- **Error Handling**: The script handles errors gracefully, logging any issues that occur while attempting to control or check the state of the devices.

## Dependencies

The script requires the following Python modules:

- `pymodbus`: Used to interact with Modbus devices.
- `requests`: Used to send HTTP requests to the Shelly devices.
- `astral`: Used for calculating sunrise and sunset times.

### Installing Dependencies

Install all the required dependencies using pip:

```bash
pip install pymodbus requests astral

