# 09 — COMPREHENSIVE SECURITY AUDIT & VULNERABILITY ASSESSMENT
**Device:** MikroTik RB4011iGS+  
**Audit Discipline:** Infrastructure Security, Attack Surface Analysis, and Threat Modeling  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Executive Security Evaluation

The security posture of the audited MikroTik RB4011 presents **significant vulnerabilities**. While certain hardening practices have been applied (e.g., changing the default Winbox port from 8291 to 9797, disabling Telnet/FTP/WWW, and deploying WireGuard for remote admin access), the router suffers from **critical architectural exposures**—most notably the **total absence of firewall filter rules** on the input and forward chains, and an **open recursive DNS resolver**.

```
+-------------------------------------------------------------------------------+
|                           THREAT MODEL MATRIX                                 |
+---------------------+-------------------+---------------------+---------------+
| Threat Surface      | Exposure Level    | Attack Vectors      | Severity      |
+---------------------+-------------------+---------------------+---------------+
| Management Ports    | Wide Open (Any IP)| Brute-Force / RCE   | CRITICAL      |
| DNS Subsystem       | Open Recursive    | Amplification / Pois| CRITICAL      |
| Layer 2 Bridge      | STP Disabled      | Broadcast Loop      | CRITICAL      |
| IPv6 Stack          | Forwarding / No FW| Unprotected Ingress | HIGH          |
| RouterBOOT Firmware | 10 Versions Behind| Kernel Instability  | HIGH          |
| Neighbor Discovery  | Leaking on Tower  | Reconnaissance      | MEDIUM        |
| Cleartext API       | Port 8728 Enabled | Credential Sniffing | MEDIUM        |
+---------------------+-------------------+---------------------+---------------+
```

---

## 2. In-Depth Vulnerability Analysis

### [CRIT-01] Absence of Input & Forward Firewall Filter Rules
- **Configuration Evidence:**
  Inspection of `/ip firewall filter` reveals **zero static rules**.
  Only two dynamic rules injected by Back-To-Home VPN are present:
  ```
  0 D chain=forward action=drop src-address-list=back-to-home-lan-restricted-peers out-interface-list=LAN
  1 D chain=input action=accept protocol=udp dst-port=43294
  ```
- **Technical Explanation:**
  In Linux and MikroTik RouterOS, firewall chains operate with a default **ACCEPT** policy. Without an explicit terminal `action=drop` rule on the input chain, any packet addressed to the router's IP addresses is accepted and processed by internal services.
- **Attack Scenarios:**
  1. **Management Port Exploitation:** An attacker on the upstream ISP modem subnet (`192.168.4.0/24`), tower network (`10.235.51.0/24`), or any connected subscriber (`172.16.x.x` / `172.17.x.x`) can directly initiate TCP handshakes to SSH (22), Winbox (9797), API (8728), API-SSL (8729), and Reverse-Proxy (443).
  2. **Subnet Cross-Contamination:** Without forward chain filtering, subscribers in `172.16.x.x` can scan, access, and attack devices in the local management subnet (`192.168.0.0/24`) or tower network (`10.235.51.0/24`).
  3. **Denial of Service (DoS):** Volumetric SYN floods or malformed ICMP packets addressed to the router consume CPU interrupts directly, bypassing any connection tracking defense.

---

### [CRIT-02] Open Recursive DNS Resolver (`allow-remote-requests=yes`)
- **Configuration Evidence:**
  `/ip dns print`: `allow-remote-requests: yes`
  `/ip firewall nat`: Redirects port 53 UDP/TCP to local resolver.
- **Technical Explanation:**
  The router answers recursive DNS queries from any source IP. Because there is no firewall filter rule dropping external DNS queries arriving from the WAN, the router acts as an open DNS relay.
- **Attack Scenarios:**
  1. **DNS Amplification DDoS:** Remote attackers send spoofed UDP requests with EDNS0 extensions requesting large TXT or DNSSEC records. The router reflects responses amplified by a factor of up to 50x to the victim, saturating upstream bandwidth and blacklisting the ISP line.
  2. **Cache Poisoning / Hijacking:** Unauthenticated DNS queries can pollute the 2048 KiB cache, redirecting subscribers to malicious web destinations.

---

### [HIGH-01] Management Services Listening Without Subnet Whitelisting
- **Configuration Evidence (`/ip service print detail`):**
  ```
  1    name="ssh" port=22 proto=tcp available-from="" vrf=main
  8    name="reverse-proxy" port=443 proto=tcp available-from="" certificate=none
  14   name="api" port=8728 proto=tcp available-from="" vrf=main
  15   name="api-ssl" port=8729 proto=tcp available-from="" certificate=none
  16   name="winbox" port=9797 proto=tcp available-from="" vrf=main
  ```
- **Technical Explanation:**
  Every enabled management service has `available-from=""` (empty). In RouterOS, an empty `available-from` parameter allows connections from `0.0.0.0/0`.
- **Compounding Risks:**
  - **API Port 8728:** Plaintext API is enabled without encryption or source restriction. Any network tap or compromised subscriber can sniff API communication.
  - **Reverse-Proxy Port 443:** Enabled with `certificate=none`.
  - **Winbox Port 9797:** Obfuscating the port from 8291 to 9797 provides security through obscurity only. Automated port scanners identify Winbox protocol signatures within seconds.

---

### [HIGH-02] Outdated RouterBOARD Bootloader Firmware
- **Configuration Evidence:**
  ```
  current-firmware: 7.15.1
  upgrade-firmware: 7.25.1
  ```
- **Technical Explanation:**
  RouterOS kernel software was updated to 7.25.1, but `/system routerboard upgrade` was never confirmed with a reboot. Running a bootloader 10 minor versions behind can manifest as hardware offloading bugs across the dual RTL8367 switch ASICs, PCI bus instabilities, or boot loop failures during sudden power loss.

---

### [HIGH-03] Completely Unprotected IPv6 Stack
- **Configuration Evidence:**
  `/ipv6 settings print`: `disable-ipv6: no`, `forward: yes`
  `/ipv6 firewall filter print`: Zero static rules.
- **Technical Explanation:**
  IPv6 routing and packet forwarding are globally active. IPv6 does not use NAT; all IPv6 addresses are globally routable. If the upstream ISP enables IPv6 router advertisements, every connected internal device receiving an IPv6 address will be directly reachable from the worldwide internet without firewall protection.

---

### [MED-01] Information Disclosure via Neighbor Discovery (MNDP / CDP / LLDP)
- **Configuration Evidence:**
  `/ip neighbor discovery-settings`: `discover-interface-list=!WAN`
- **Technical Explanation:**
  Neighbor discovery is suppressed only on interfaces in list `WAN`.
  Because `ether2` (Tower link) is **not** in list `WAN`, the router actively broadcasts MNDP/CDP packets out `ether2` every 60 seconds.
  These broadcast packets advertise the router's identity (`Home`), hardware model (`RB4011iGS+`), MAC addresses, RouterOS version (`7.25.1`), and IP configuration to dozens of external devices across the tower network.

---

### [MED-02] Layer 2 Loop Susceptibility (`protocol-mode=none`)
- **Configuration Evidence:**
  `/interface bridge print`: `protocol-mode=none`
- **Technical Explanation:**
  With spanning tree completely disabled, the router cannot block redundant paths. A looped patch cable inserted by a subscriber or an accidental link between access switches will trigger a catastrophic broadcast storm.

---

## 3. Account & Authentication Security

### Local User Accounts (`/user print detail`):
```
0  ;;; system default user
   name="admin" group=full inactivity-timeout=10m inactivity-policy=none address=""
```

### Analysis:
- **Default Username:** The default `admin` username is active. Attackers conducting brute-force attacks target `admin` first.
- **Source Address Restriction:** `address=""` allows `admin` to authenticate from any reachable network location.
- **Inactivity Timeout:** `inactivity-timeout=10m` is correctly enforced, terminating idle administrative sessions.
- **SSH Key Authentication:** No SSH public keys are imported (`/user ssh-keys print` is empty). All administration relies strictly on password authentication.

---

## 4. MAC Server & Ingress Controls

```
/tool mac-server: allowed-interface-list=LAN
/tool mac-server mac-winbox: allowed-interface-list=LAN
/tool mac-server ping: enabled=no
```

### Critical Flaw Interaction:
- As documented in Section 02, `Bridge-Local` is **DISABLED** in `/interface list member` under list `LAN`!
- Because `Bridge-Local` is not an active member of `LAN`, MAC-Telnet and MAC-Winbox are technically denied on all bridge ports except `ether3` (the only port statically listed in `LAN`). While this accidentally restricts MAC access, it represents an uncontrolled configuration flaw.
