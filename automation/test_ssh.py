import getpass
import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)

with open("inventory.yaml", "r", encoding="utf-8") as f:
    inventory = yaml.safe_load(f)

username = input("SSH Username: ")
password = getpass.getpass("SSH Password: ")

for device in inventory["devices"]:
    print(f"\nConnecting to {device['hostname']}...")

    try:
        with ConnectHandler(
            device_type=device["device_type"],
            host=device["host"],
            port=device.get("port", 22),
            username=username,
            password=password,
            conn_timeout=10,
        ) as ssh:
            result = ssh.send_command("show version")
            print(result[:1000])
            print("[SUCCESS] SSH connected!")

    except NetmikoAuthenticationException:
        print("[ERROR] Authentication failed")

    except NetmikoTimeoutException:
        print("[ERROR] SSH connection timeout")

    except Exception as e:
        print(f"[ERROR] {e}")
