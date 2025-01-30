import os
import subprocess
import signal

MARKER_FILE = "/tmp/hotspot_active"

def run_command(command):
    """Run a shell command and exit on failure."""
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        exit(result.returncode)
    return result.stdout.strip()

def write_temp_files(ssid):
    """Write temporary configuration files for hostapd, dnsmasq, and dhcpcd."""
    print("Creating temporary configuration files...")

    # hostapd configuration
    hostapd_config = f"""
    interface=wlan0
    driver=nl80211
    ssid={ssid}
    hw_mode=g
    channel=6
    wmm_enabled=0
    macaddr_acl=0
    auth_algs=1
    ignore_broadcast_ssid=0
    """
    with open("/tmp/hostapd.conf", "w") as f:
        f.write(hostapd_config)

    # dnsmasq configuration
    dnsmasq_config = """
    interface=wlan0
    dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
    """
    with open("/tmp/dnsmasq.conf", "w") as f:
        f.write(dnsmasq_config)

    # dhcpcd configuration
    dhcpcd_config = """
    interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
    """
    with open("/tmp/dhcpcd.conf", "w") as f:
        f.write(dhcpcd_config)

def start_hotspot(ssid):
    """Start the hotspot by setting up services with temporary files."""
    print("Starting Wi-Fi hotspot...")

    # Use the temporary configuration files
    run_command("sudo mv /tmp/dhcpcd.conf /etc/dhcpcd.conf")
    run_command("sudo systemctl restart dhcpcd")

    run_command("sudo mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf")
    run_command("sudo systemctl start hostapd")

    run_command("sudo mv /tmp/dnsmasq.conf /etc/dnsmasq.conf")
    run_command("sudo systemctl start dnsmasq")

    # Create marker file
    with open(MARKER_FILE, "w") as f:
        f.write("active")

    print("Hotspot is running. SSID: Your network is live!")

def stop_hotspot():
    """Stop the hotspot and restore system defaults."""
    print("Stopping Wi-Fi hotspot...")
    run_command("sudo systemctl stop hostapd")
    run_command("sudo systemctl stop dnsmasq")
    
    # Reset configuration
    print("Restoring default network configuration...")
    run_command("sudo cp /etc/dhcpcd.conf.backup /etc/dhcpcd.conf")
    run_command("sudo systemctl restart dhcpcd")

    # Remove marker file
    if os.path.exists(MARKER_FILE):
        os.remove(MARKER_FILE)
    
    print("Hotspot stopped and system reset to default network configuration.")

def check_and_restore():
    """Check if the hotspot was active during the last boot and restore the system."""
    if os.path.exists(MARKER_FILE):
        print("Detected unclean shutdown. Cleaning up leftover configurations...")
        stop_hotspot()

def handle_exit(signum, frame):
    """Handle termination signals to clean up on exit."""
    stop_hotspot()
    exit(0)

def main():
    """Main function to set up and manage the hotspot."""
    ssid = input("Enter SSID for the open hotspot: ")

    # Backup original configuration
    print("Backing up original network configuration...")
    run_command("sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.backup")

    # Check for previous state and restore if necessary
    check_and_restore()

    # Write and start the hotspot
    write_temp_files(ssid)
    start_hotspot(ssid)

    # Set up signal handlers for cleanup
    signal.signal(signal.SIGINT, handle_exit)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, handle_exit)  # Handle termination

    print("Press Ctrl+C to stop the hotspot.")
    try:
        # Keep the program running to maintain the hotspot
        signal.pause()
    except KeyboardInterrupt:
        handle_exit(None, None)