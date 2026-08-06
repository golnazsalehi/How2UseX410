#!/usr/bin/env bash
set -e

# ===========================
# User variables
# ===========================
port_name="${1:-enp34s0}"
ip_addr="${2:-192.168.10.1}"
netmask="255.255.255.0"

echo "Configuring interface: $port_name"
echo "Assigning IP: $ip_addr"
echo ""

# Detect OS
os="$(uname -s)"

# ===========================
# Linux / Ubuntu
# ===========================
if [[ "$os" == "Linux" ]]; then
    echo "[Linux] Detected Ubuntu/Linux"

    # Remove existing IPs on that subnet
    sudo ip addr flush dev "$port_name"

    # Add new IP
    sudo ip addr add "$ip_addr"/24 dev "$port_name"

    # bring up port
    sudo ip link set "$port_name" up

    # Set MTU
    sudo ip link set "$port_name" mtu 9000

    sudo sysctl -w net.core.wmem_max=25000000
    sudo sysctl -w net.core.rmem_max=25000000

    echo "✔ Linux configuration done."
    exit 0
fi

# ===========================
# macOS
# ===========================

if [[ "$os" == "Darwin" ]]; then

    echo "[macOS detected]"

    echo "Removing any existing IPv4 aliases on $port_name ..."

    # Find all IPv4 addresses (excluding 127.0.0.1)
    existing_ips=$(ifconfig "$port_name" | awk '/inet / && $2 != "127.0.0.1" {print $2}')

    for ip in $existing_ips; do
        echo " - Removing IP: $ip"
        sudo ifconfig "$port_name" inet "$ip" -alias
    done

    echo "Assigning new IP: $ip_addr"
    sudo ifconfig "$port_name" inet "$ip_addr" netmask "$netmask" alias

    echo "Setting MTU to 9000"
    sudo ifconfig "$port_name" mtu 9000

    echo "✔ macOS configuration done."
    exit 0

fi

echo "❌ Unsupported OS: $os"
exit 1
