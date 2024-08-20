#!/bin/bash

# Define the name of the virtual environment directory
VENV_DIR="venv"

# Check if the virtual environment directory already exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Activate the virtual environment
source $VENV_DIR/bin/activate

# Install required packages
echo "Installing required packages..."
pip install -r requirements.txt

# Run the script
echo "Starting the script..."
python3 solar_robot.py

# Deactivate the virtual environment after the script runs
deactivate
