#!/usr/bin/python3.11

import requests
from pymodbus.client import ModbusTcpClient
import time
import json
import os
from datetime import datetime, timedelta 
from astral import LocationInfo
from astral.sun import sun
import pytz
import logging
import signal
import sys

# Load configuration
def load_config(config_file="solar_robot.json"):
    with open(config_file, 'r') as file:
        config = json.load(file)
    return config

config = load_config()

# Set up logging
logging.basicConfig(level=getattr(logging, config["log_level"]),
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def log(level, message):
    logging.log(level, message)

# Graceful exit handling
def signal_handler(sig, frame):
    log(logging.INFO, "Received SIGINT (CTRL+C). Exiting gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def has_passed_event(event_type, city_name, region_name, timezone):
    location = LocationInfo(city_name, region_name)
    
    s = sun(location.observer, date=datetime.now().date(), tzinfo=pytz.utc)
    event_time = s[event_type].astimezone(pytz.timezone(timezone))
    
    current_time = datetime.now(pytz.timezone(timezone))

    return current_time > event_time

def wait_until_sunrise(city_name, region_name, timezone):
    location = LocationInfo(city_name, region_name)
    
    today_sun = sun(location.observer, date=datetime.now().date(), tzinfo=pytz.utc)
    sunset_time = today_sun['sunset'].astimezone(pytz.timezone(timezone))
    sunrise_time = today_sun['sunrise'].astimezone(pytz.timezone(timezone))

    current_time = datetime.now(pytz.timezone(timezone))

    if current_time > sunset_time:
        log(logging.INFO, "It is after sunset. Sleeping until the next sunrise...")
        tomorrow_sun = sun(location.observer, date=(datetime.now().date() + timedelta(days=1)), tzinfo=pytz.utc)
        next_sunrise_time = tomorrow_sun['sunrise'].astimezone(pytz.timezone(timezone))
        sleep_duration = (next_sunrise_time - current_time).total_seconds()
        log(logging.INFO, f"Next sunrise is at {next_sunrise_time}. Sleeping for {sleep_duration} seconds.")
        time.sleep(sleep_duration)
        log(logging.INFO, "Woke up at sunrise!")
    else:
        log(logging.INFO, "It is not after sunset, no need to sleep.")

def get_solar_output():
    try:
        client = ModbusTcpClient(config["solar_panel_ip"])
        client.connect()
        result = client.read_input_registers(5029, count=2)
        client.close()
        
        if result.isError():
            log(logging.ERROR, "Error reading registers.")
            return None
        else:
            registers = result.registers
            power_output = registers[1]
            return power_output
    except Exception as e:
        log(logging.ERROR, f"Failed to get solar output: {e}")
        return None

def get_shelly_device_state(device_ip, device_type):
    try:
        if device_type == 'relay':
            url = f"http://{device_ip}/relay/0"
        elif device_type == 'lamp':
            url = f"http://{device_ip}/light/0"
        
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('ison', False)
        else:
            log(logging.ERROR, f"Failed to get state for {device_type} {device_ip}. HTTP Status: {response.status_code}")
            return False
    except Exception as e:
        log(logging.ERROR, f"Error getting state for {device_type} {device_ip}: {e}")
        return False

def control_shelly_device(device_ip, device_type, turn_on, track_state=True):
    try:
        if device_type == 'relay':
            url = f"http://{device_ip}/relay/0"
        elif device_type == 'lamp':
            url = f"http://{device_ip}/light/0"

        payload = {'turn': 'on' if turn_on else 'off'}
        response = requests.get(url, params=payload)
        
        if response.status_code == 200:
            action = 'on' if turn_on else 'off'
            log(logging.INFO, f"{device_type.capitalize()} {device_ip} turned {action} by script.")

            if track_state:
                save_state(device_type, turn_on)
        else:
            log(logging.ERROR, f"Failed to control {device_type} {device_ip}. HTTP Status: {response.status_code}")
    except Exception as e:
        log(logging.ERROR, f"Error controlling {device_type} {device_ip}: {e}")

def load_state():
    try:
        if os.path.exists(config["state_file"]):
            with open(config["state_file"], 'r') as file:
                state = json.load(file)
                return state
        else:
            return {"relay_turned_on_by_script": False, "lamp_turned_on_by_script": False}
    except Exception as e:
        log(logging.ERROR, f"Failed to load state: {e}")
        return {"relay_turned_on_by_script": False, "lamp_turned_on_by_script": False}

def save_state(device_type, turn_on):
    try:
        state = load_state()
        if device_type == 'relay':
            state["relay_turned_on_by_script"] = turn_on
        elif device_type == 'lamp':
            state["lamp_turned_on_by_script"] = turn_on
        
        with open(config["state_file"], 'w') as file:
            json.dump(state, file)
    except Exception as e:
        log(logging.ERROR, f"Failed to save state for {device_type}: {e}")

def main():
    location = LocationInfo(config["city_name"], config["region_name"])
    
    today_sun = sun(location.observer, date=datetime.now().date(), tzinfo=pytz.utc)
    sunset_time = today_sun['sunset'].astimezone(pytz.timezone(config["timezone"]))
    sunrise_time = today_sun['sunrise'].astimezone(pytz.timezone(config["timezone"]))

    current_time = datetime.now(pytz.timezone(config["timezone"]))

    log(logging.INFO, f"Sunrise in {config['city_name']} is at {sunrise_time}.")
    log(logging.INFO, f"Sunset in {config['city_name']} is at {sunset_time}.")
    log(logging.INFO, f"Current time is {current_time}.")

    state = load_state()
    relay_turned_on_by_script = state["relay_turned_on_by_script"]
    lamp_turned_on_by_script = state["lamp_turned_on_by_script"]
    
    relay_initial_state = get_shelly_device_state(config["shelly_relay_ip"], 'relay')
    lamp_initial_state = get_shelly_device_state(config["shelly_lamp_ip"], 'lamp')
    
    if relay_initial_state and not relay_turned_on_by_script:
        save_state('relay', False)  # Assume turned on by user
    if lamp_initial_state and not lamp_turned_on_by_script:
        save_state('lamp', False)  # Assume turned on by user

    while True:
        power_output = get_solar_output()
        if power_output is not None:
            log(logging.INFO, f"Solar Power: {power_output} W | High Threshold: {config['high_threshold']} W | Low Threshold: {config['low_threshold']} W")
            
            if power_output > config["high_threshold"]:
                log(logging.INFO, "Power exceeds high threshold. Turning on devices if not already on.")
                control_shelly_device(config["shelly_relay_ip"], 'relay', True)
                control_shelly_device(config["shelly_lamp_ip"], 'lamp', True)
            elif power_output < config["low_threshold"]:
                log(logging.INFO, "Power below low threshold. Turning off devices if they were turned on by the script.")
                
                if get_shelly_device_state(config["shelly_relay_ip"], 'relay'):
                    if relay_turned_on_by_script:
                        control_shelly_device(config["shelly_relay_ip"], 'relay', False)
                    else:
                        log(logging.INFO, "Relay was not turned on by the script. No action taken.")
                else:
                    log(logging.INFO, "Relay is already off. No action needed.")

                if get_shelly_device_state(config["shelly_lamp_ip"], 'lamp'):
                    if lamp_turned_on_by_script:
                        control_shelly_device(config["shelly_lamp_ip"], 'lamp', False)
                    else:
                        log(logging.INFO, "Lamp was not turned on by the script. No action taken.")
                else:
                    log(logging.INFO, "Lamp is already off. No action needed.")
            else:
                log(logging.INFO, "Power is within the thresholds. No action taken.")

        if has_passed_event("sunset", config["city_name"], config["region_name"], config["timezone"]):
            log(logging.INFO, "Passed sunset")
            wait_until_sunrise(config["city_name"], config["region_name"], config["timezone"])
        else:
            time.sleep(5)

if __name__ == "__main__":
    main()

