#!/bin/bash
set -e

# If WireGuard credentials exist in environment, start wireproxy tunnel
if [ -n "$WG_PRIVATE_KEY" ] && [ -n "$WG_PEER_PUBLIC_KEY" ] && [ -n "$WG_ENDPOINT" ]; then
    echo "[*] Setting up userspace WireGuard proxy..."
    cat <<EOF > /tmp/wireproxy.conf
[Interface]
Address = ${WG_ADDRESS:-192.168.216.2/24}
PrivateKey = ${WG_PRIVATE_KEY}

[Peer]
PublicKey = ${WG_PEER_PUBLIC_KEY}
Endpoint = ${WG_ENDPOINT}
AllowedIPs = ${WG_ALLOWED_IPS:-192.168.216.0/24}
PersistentKeepalive = 15

[Socks5]
BindAddress = 127.0.0.1:1085
EOF
    echo "[*] Launching wireproxy..."
    /usr/local/bin/wireproxy -c /tmp/wireproxy.conf &
    export SOCKS5_PROXY="127.0.0.1:1085"
    export ROUTER_IP="${ROUTER_IP:-192.168.216.1}"
    export ROUTER_PORT="${ROUTER_PORT:-22}"
    sleep 2
fi

echo "[*] Starting MSCP Dashboard on port ${PORT:-8000}..."
cd /app/dashboard
exec python backend.py
