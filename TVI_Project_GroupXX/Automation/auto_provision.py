import os
import yaml
import logging
from datetime import datetime
from getpass import getpass
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)

os.makedirs("backups", exist_ok=True)
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/automation.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

BASELINE_COMMANDS = [
    "ntp server 10.10.99.10",
    "logging host 10.10.99.10",
    "banner motd # Unauthorized access to TVI Corporate Infrastructure is prohibited. #",
]

SITE_VLANS = {
    "HCMC": [
        ("10", "EXEC_FINANCE"),
        ("20", "RND_ENGINEERING"),
        ("40", "GUEST"),
        ("99", "MANAGEMENT"),
    ],
    "HANOI": [
        ("20", "RND_ENGINEERING"),
        ("40", "GUEST"),
        ("99", "MANAGEMENT"),
    ],
    "DANANG": [
        ("30", "LOGISTICS_OPS"),
        ("60", "IOT"),
        ("99", "MANAGEMENT"),
    ],
}


def load_inventory(filepath="inventory.yaml"):
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["devices"]


def build_device_commands(site, role):
    commands = list(BASELINE_COMMANDS)
    if role == "switch":
        for vlan_id, vlan_name in SITE_VLANS.get(site, []):
            commands.extend([f"vlan {vlan_id}", f"name {vlan_name}"])
    return commands


def capture_device_state(ssh, hostname, phase):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"backups/{hostname}_{timestamp}_{phase}_backup.cfg"

    running_cfg = ssh.send_command("show running-config")
    ip_int_brief = ssh.send_command("show ip interface brief")

    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(f"! === CAPTURE PHASE: {phase.upper()} | HOST: {hostname} | TIME: {timestamp} ===\n\n")
        f.write("! --- SHOW IP INTERFACE BRIEF ---\n")
        f.write(ip_int_brief + "\n\n")
        f.write("! --- SHOW RUNNING-CONFIG ---\n")
        f.write(running_cfg + "\n")

    return backup_path


def run_automation():
    username = input("Enter SSH Username: ")
    password = getpass("Enter SSH Password: ")

    for dev in load_inventory():
        hostname = dev["hostname"]
        host_ip = dev["host"]
        site = dev["site"]
        role = dev["role"]

        device_params = {
            "device_type": dev["device_type"],
            "host": host_ip,
            "port": dev.get("port", 22),
            "username": username,
            "password": password,
            "secret": password,
            "conn_timeout": 10,
        }

        print(f"\n[*] Connecting to {hostname} ({host_ip}) [{site} - {role}]...")

        try:
            with ConnectHandler(**device_params) as ssh:
                if not ssh.check_enable_mode():
                    ssh.enable()

                pre_file = capture_device_state(ssh, hostname, "pre")
                print(f"  [+] Pre-change backup saved: {pre_file}")

                cmd_list = build_device_commands(site, role)
                output = ssh.send_config_set(cmd_list)
                print("  [+] Pushed baseline & VLAN configurations.")
                logging.info(f"Successfully provisioned {hostname} ({host_ip}):\n{output}")

                post_file = capture_device_state(ssh, hostname, "post")
                print(f"  [+] Post-change backup saved: {post_file}")

                ssh.save_config()
                print("  [+] Saved running-config to startup-config.")

        except NetmikoTimeoutException:
            msg = f"[-] Connection timed out for {hostname} ({host_ip})"
            print(msg)
            logging.error(msg)

        except NetmikoAuthenticationException:
            msg = f"[-] Authentication failed for {hostname} ({host_ip})"
            print(msg)
            logging.error(msg)

        except Exception as e:
            msg = f"[-] Unexpected error on {hostname} ({host_ip}): {str(e)}"
            print(msg)
            logging.error(msg)


if __name__ == "__main__":
    run_automation()