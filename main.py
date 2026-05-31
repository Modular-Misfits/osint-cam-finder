#!/usr/bin/env python3
import socket
import sys

from app.core.env_loader import load_env
from app.ui.main_window import launch

load_env()


def check_connectivity() -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("www.google.com", 80))
        sock.close()
        return result == 0
    except OSError:
        return False


if __name__ == "__main__":
    if not check_connectivity():
        print("[!] No internet connection detected. Some scan sources will be unavailable.")
    sys.exit(launch())
