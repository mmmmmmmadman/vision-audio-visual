#!/bin/bash
cd "$(dirname "$0")"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
source venv/bin/activate
python narrator_gui.py
