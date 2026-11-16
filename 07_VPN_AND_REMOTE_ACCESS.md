# 07 — VPN & REMOTE ACCESS AUDIT
**Device:** MikroTik RB4011iGS+  
**Subsystem:** WireGuard (Back-To-Home), IPsec, PPPoE Access Server, and Tunneling Protocols  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. MikroTik Cloud Back-To-Home (BTH) WireGuard VPN

MikroTik Back-To-Home is a native RouterOS v7 WireGuard orchestration feature that facilitates remote management and peer tunneling through Carrier-Grade NAT (CGNAT) without requiring a public IPv4 address.

### A. Interface & Relay Architecture:
- **Interface Name:** `back-to-home-vpn`
- **Listening Port:** UDP `43294`
- **Interface MTU:** `1420`
- **IPv4 Address:** `192.168.216.1/24`
- **IPv6 Address:** `fc00:0:0:216::1/64` (Unique Local IPv6)
- **DDNS Hostname:** `he608smwf5a.sn.mynetname.net` (Resolving to `150.228.105.8`)
- **VPN DNS Hostname:** `he608smwf5a.vpn.mynetname.net`
- **Cloud Relay Status:** Active via Region **EUR1** (`78.28.208.99`, RTT: 86.4 ms)
- **Role & Necessity:** Because the upstream ISP assigns CGNAT private addresses (`100.88.x.x`), direct inbound connections to the router from the public internet are impossible. The router establishes an outbound persistent tunnel to MikroTik's European cloud relay, allowing authorized mobile applications and engineers to reach the router securely.

### B. Peer Configuration & Active Sessions:
```
Flags: D - DYNAMIC
 #   NAME   ALLOWED-ADDRESSES                            LAST-HANDSHAKE  RX / TX          ROLE / NOTES
 0 D peer1  192.168.216.3/32, fc00:0:0:216::3/128        1h 34s ago      32.6M / 117.5M   User: Ali (Full LAN Access)
 1 D peer2  192.168.216.4/32, fc00:0:0:216::4/128        None (Never)    0 / 0            User: Naeil (LAN Restricted)
 2 D peer3  192.168.216.2/32, fc00:0:0:216::2/128        None (Never)    0 / 0            Cloud Controller Link
```

### C. Security Analysis of BTH Configuration:
1. **Peer Permissions:**
   - User `Ali` (`192.168.216.3`) is granted `allow-lan=yes`, granting full access to router management and internal subnets.
   - User `Naeil` (`192.168.216.4`) has `allow-lan=no`. The dynamic firewall filter rule:
     `chain=forward action=drop src-address-list=back-to-home-lan-restricted-peers out-interface-list=LAN`
     successfully confines this peer to router-local services.
2. **Cryptographic Material Handling:**
   - In `/ip cloud print`, RouterOS outputs the full client WireGuard configuration file, including embedded `PrivateKey` strings and ASCII QR codes.
   - **AUDIT SAFEGUARD:** All private keys, pre-shared keys, and sensitive cryptographic strings have been strictly redacted from the generated technical documentation to prevent credential leakage.

---

## 2. IPsec Configuration Audit (`/ip ipsec`)

### A. Peer & Profile Inventory:
```
Flags: X - DISABLED
 #   NAME     ADDRESS           PROFILE  EXCHANGE-MODE  STATUS
 0 X NordVPN  eg2.nordvpn.com   NordVPN  ike2           DISABLED
```

- **Operational State:** The IPsec tunnel to NordVPN Egypt (`eg2.nordvpn.com`) is **DISABLED**.
- **Cryptographic Settings (`/ip ipsec profile`):**
  - Hash Algorithm: `sha512`
  - Encryption: `aes-256`, `aes-192`, `aes-128` (CBC)
  - Diffie-Hellman Group: `modp2048`
  - Lifetime: 1 day
- **Installed Certificate (`/certificate`):**
  - Name: `root.der_0` (NordVPN Root CA)
  - Common Name: `NordVPN Root CA`
  - Digest: SHA-512, RSA 4096-bit, Trusted: `yes`, Valid until: `2036-01-01`.
- **Finding:** The NordVPN configuration is completely inactive and harmless, but represents legacy configuration residue. If external commercial VPN egress is no longer required, the profile, peer, proposals, and certificates can be archived and safely removed during future maintenance.

---

## 3. PPPoE Access Server (`Server-PPOE`)

The router functions as a high-density Broadband Network Gateway (BNG) terminating subscriber links.

### Server Parameters:
```
/interface pppoe-server server
add default-profile=default disabled=no interface=Bridge-Local max-mru=1480 max-mtu=1480 \
    mrru=disabled one-session-per-host=no service-name=Server-PPOE
```

### Operational Analysis:
- **Binding Interface:** `Bridge-Local`. PPPoE Discovery (PADI/PADO) frames are answered across all active ports (`ether3` through `ether10`).
- **MTU / MRU:** Clamped to `1480` bytes. Combined with MSS clamping in Mangle (`new-mss=clamp-to-pmtu`), packet fragmentation is eliminated across subscriber links.
- **Concurrent Connections:** **18 active subscriber sessions** authenticated simultaneously during the audit.
- **Authentication Source:** Delegated entirely to local **User Manager v5 (RADIUS)**. `/ppp secret` is empty.

---

## 4. Other Tunneling & Remote Access Subsystems

| Subsystem | Configuration Command | Configured Items | Operational Status |
| :--- | :--- | :--- | :--- |
| **OpenVPN Client** | `/interface ovpn-client` | 0 Items | Disabled / Inactive |
| **OpenVPN Server** | `/interface ovpn-server server`| Default settings | Disabled (`enable=no`) |
| **L2TP Client / Server** | `/interface l2tp-client`, `/interface l2tp-server` | 0 Items | Disabled / Unconfigured |
| **PPTP Client / Server** | `/interface pptp-client`, `/interface pptp-server` | 0 Items | Disabled / Unconfigured |
| **SSTP Client / Server** | `/interface sstp-client`, `/interface sstp-server` | 0 Items | Disabled / Unconfigured |
| **GRE / EoIP Tunnels** | `/interface gre`, `/interface eoip` | 0 Items | Disabled / Unconfigured |
| **IP-IP / IPIP6 Tunnels** | `/interface ipip` | 0 Items | Disabled / Unconfigured |
