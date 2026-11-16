# 13 — AUDIT FINDINGS & TECHNICAL RECOMMENDATIONS CATALOG
**Device:** MikroTik RB4011iGS+  
**Audit Discipline:** Vulnerability Management, Engineering Defect Remediation & Optimization  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULL AUDIT COMPLETE — ZERO CONFIGURATION CHANGES IMPLEMENTED

---

> [!CAUTION]
> **ABSOLUTE SAFETY DIRECTIVE:**
> In accordance with the non-negotiable safety rules governing this audit, **NO CHANGES HAVE BEEN MADE TO THE ROUTER**.
> The proposed remediation commands and architectural recommendations cataloged below are strictly advisory.
> **DO NOT EXECUTE ANY REMEDIATION COMMAND WITHOUT EXPLICIT ADMINISTRATIVE APPROVAL AND A VERIFIED BACKUP.**

---

## 1. Findings Classification Matrix

| Finding ID | Title | Severity | Impacted Subsystem | Maintenance Window Required? |
| :--- | :--- | :--- | :--- | :--- |
| **CRIT-01** | Total Absence of Input & Forward Firewall Filter Rules | **CRITICAL** | `/ip firewall filter` | Yes (Low Risk) |
| **CRIT-02** | Open Recursive DNS Resolver (`allow-remote-requests=yes`) | **CRITICAL** | `/ip dns` | No (Immediate) |
| **CRIT-03** | Broken 5-Way PCC Multi-WAN Balancer Causing 40% Traffic Spillover | **CRITICAL** | `/ip firewall mangle` | Yes (Brief Session Reset) |
| **CRIT-04** | Complete Lack of Spanning Tree / Loop Protection (`protocol-mode=none`) | **CRITICAL** | `/interface bridge` | Yes (Layer 2 Convergence) |
| **HIGH-01** | Management Services Exposed Without Source IP Whitelisting | **HIGH** | `/ip service` | No |
| **HIGH-02** | Outdated RouterBOARD Bootloader Firmware (7.15.1 vs 7.25.1) | **HIGH** | `/system routerboard`| Yes (Reboot Required) |
| **HIGH-03** | Unshielded IPv6 Stack with Global Forwarding Enabled | **HIGH** | `/ipv6 firewall` | No |
| **HIGH-04** | Subnet Mask Inconsistency (DHCP `/16` vs Interface `/24`) | **HIGH** | `/ip dhcp-server` | Yes (DHCP Lease Renewal) |
| **MED-01** | `Bridge-Local` Disabled in Interface List `LAN` | **MEDIUM** | `/interface list member` | No |
| **MED-02** | Problematic Network-Zero (.0) Addresses in PPPoE IP Pools | **MEDIUM** | `/ip pool` | Yes (Pool Drainage) |
| **MED-03** | Information Leakage via MNDP/CDP Over Tower Link `ether2` | **MEDIUM** | `/ip neighbor` | No |
| **MED-04** | Lack of Dynamic Gateway Probing (`check-gateway=none`) in Routing | **MEDIUM** | `/ip route` | No |
| **LOW-01** | RouterBOARD Manual CPU Frequency Override Warning | **LOW** | `/system routerboard`| No |
| **LOW-02** | Legacy Disabled NAT & Mangle Configuration Residue | **LOW** | Firewall Cleanliness | No |
| **INFO-01**| Connection Tracking Aggressive UDP Eviction (10s Timeout) | **INFORMATIONAL** | `/ip firewall c-track`| None (Working as Intended) |
| **INFO-02**| Outbound TTL Modification (`new-ttl=set:65`) for Anti-Tethering | **INFORMATIONAL** | `/ip firewall mangle` | None (Working as Intended) |

---

## 2. Detailed Technical Findings & Remediation Plans

---

### [CRIT-01] Total Absence of Input & Forward Firewall Filter Rules
- **Severity:** **CRITICAL**
- **Configuration Location:** `/ip firewall filter`
- **Evidence:**
  ```
  /ip firewall filter print
  Flags: D - DYNAMIC
  0 D chain=forward action=drop src-address-list=back-to-home-lan-restricted-peers out-interface-list=LAN
  1 D chain=input action=accept protocol=udp dst-port=43294
  ```
- **Technical Explanation:**
  The router lacks user-defined stateful firewall filtering. In RouterOS, default chain policy is ACCEPT. Anyone who can reach any of the router's IP addresses (`192.168.4.238`, `10.235.51.4`, `100.88.x.x`, `192.168.0.1`) can establish connections to router management daemons or transit traffic through the router.
- **Potential Consequences:**
  Remote exploit execution, brute-force dictionary attacks against admin credentials, subscriber cross-subnet attacks, CPU starvation via volumetric packet floods.
- **Dependencies:** Requires fixing [MED-01] (`Bridge-Local` in `LAN` list) first so that legitimate LAN traffic is not dropped.
- **Maintenance Window:** Recommended (10 minutes).
- **Proposed Remediation Commands (FOR FUTURE EXECUTION ONLY):**
  ```routeros
  # 1. State tracking on Input
  /ip firewall filter
  add chain=input action=accept connection-state=established,related,untracked comment="Accept Established/Related"
  add chain=input action=drop connection-state=invalid comment="Drop Invalid"
  add chain=input action=accept protocol=icmp comment="Accept ICMP"
  add chain=input action=accept in-interface-list=LAN comment="Accept Management from LAN"
  add chain=input action=drop comment="Drop All Other Input from WAN/Untrusted"

  # 2. State tracking on Forward
  add chain=forward action=accept connection-state=established,related,untracked comment="Accept Forward Established/Related"
  add chain=forward action=drop connection-state=invalid comment="Drop Forward Invalid"
  add chain=forward action=accept in-interface-list=LAN out-interface-list=WAN comment="Accept LAN to Internet"
  add chain=forward action=accept in-interface=Bridge-Local out-interface=ether2 comment="Accept LAN to Tower"
  add chain=forward action=drop comment="Drop Unauthorized Forward Traffic"
  ```

---

### [CRIT-02] Open Recursive DNS Resolver (`allow-remote-requests=yes`)
- **Severity:** **CRITICAL**
- **Configuration Location:** `/ip dns` and `/ip firewall filter`
- **Evidence:**
  `/ip dns print`: `allow-remote-requests: yes`
  Zero rules dropping incoming UDP/TCP port 53 on WAN interfaces.
- **Technical Explanation:**
  The router accepts recursive DNS queries from external IP addresses. Because `ether1-ISP` and `ether2` receive incoming packets, external actors can query the internal cache and use the router as an amplifier for volumetric DDoS attacks.
- **Potential Consequences:**
  Inclusion of the router IP in global DDoS amplifier blacklists, ISP suspension of WAN accounts, cache poisoning, and DNS query latency degradation for legitimate subscribers.
- **Maintenance Window:** Not required.
- **Proposed Remediation Commands:**
  ```routeros
  /ip firewall filter
  add chain=input action=drop protocol=udp dst-port=53 in-interface-list=WAN comment="Drop WAN DNS UDP" place-before=0
  add chain=input action=drop protocol=tcp dst-port=53 in-interface-list=WAN comment="Drop WAN DNS TCP" place-before=1
  ```

---

### [CRIT-03] Broken 5-Way PCC Multi-WAN Balancer Causing 40% Traffic Spillover
- **Severity:** **CRITICAL**
- **Configuration Location:** `/ip firewall mangle` (Rules 16–20)
- **Evidence:**
  Rules 16, 17, 18 use `both-addresses:5/0`, `both-addresses:5/1`, `both-addresses:5/2`.
  Rules 19 and 20 (`both-addresses:5/3` and `both-addresses:5/4`) are **DISABLED**.
  Lines `pppoe-out4` and `pppoe-out5` are disabled.
- **Technical Explanation:**
  The PCC classifier splits connections into 5 equal buckets (0, 1, 2, 3, 4). When buckets 3 and 4 match disabled rules, those packets exit the mangle table without a connection mark or routing mark. They default to table `main`, which routes 100% of unmarked packets to `pppoe-out1` (distance 10).
  Result: `pppoe-out1` carries **60% of total network bandwidth**, while `pppoe-out2` and `pppoe-out3` carry only 20% each.
- **Potential Consequences:**
  Severe bufferbloat, packet loss, and high latency on `pppoe-out1`, while 2 active lines remain heavily underutilized.
- **Maintenance Window:** Recommended (3 minutes; will rebalance active connections).
- **Proposed Remediation Commands:**
  ```routeros
  /ip firewall mangle
  set [find comment~"PCC: Split 5/0"] per-connection-classifier=both-addresses:3/0 comment="PCC: Split 3/0 -> pppoe1_conn"
  set [find comment~"PCC: Split 5/1"] per-connection-classifier=both-addresses:3/1 comment="PCC: Split 3/1 -> pppoe2_conn"
  set [find comment~"PCC: Split 5/2"] per-connection-classifier=both-addresses:3/2 comment="PCC: Split 3/2 -> pppoe3_conn"
  ```

---

### [CRIT-04] Complete Lack of Spanning Tree / Loop Protection (`protocol-mode=none`)
- **Severity:** **CRITICAL**
- **Configuration Location:** `/interface bridge`
- **Evidence:**
  `/interface bridge print`: `protocol-mode=none` on `Bridge-Local`.
- **Technical Explanation:**
  `Bridge-Local` encompasses 8 physical Gigabit ports (`ether3` through `ether10`) spanning two Realtek switch chips. With STP disabled, any Layer 2 loop will circulate broadcast packets indefinitely across the switch chips and internal 2.5 Gbps CPU interconnects.
- **Potential Consequences:**
  Instant 100% CPU lockup, immediate termination of all 18 active PPPoE subscriber sessions, complete loss of network connectivity, and management unreachable until physical cable disconnection.
- **Maintenance Window:** Required (30 seconds for RSTP convergence).
- **Proposed Remediation Commands:**
  ```routeros
  /interface bridge
  set Bridge-Local protocol-mode=rstp priority=0x8000
  ```

---

### [HIGH-01] Management Services Exposed Without Source IP Whitelisting
- **Severity:** **HIGH**
- **Configuration Location:** `/ip service`
- **Evidence:**
  `ssh`, `winbox`, `api`, `api-ssl`, and `reverse-proxy` have `available-from=""`.
- **Technical Explanation:**
  Management services accept connection requests from any IP address on the planet that can route to the router.
- **Proposed Remediation Commands:**
  ```routeros
  /ip service
  set ssh address=192.168.0.0/16,192.168.216.0/24,192.168.4.0/24
  set winbox address=192.168.0.0/16,192.168.216.0/24,192.168.4.0/24
  set api disabled=yes
  set api-ssl disabled=yes
  set reverse-proxy disabled=yes
  ```

---

### [HIGH-02] Outdated RouterBOARD Bootloader Firmware (7.15.1 vs 7.25.1)
- **Severity:** **HIGH**
- **Configuration Location:** `/system routerboard`
- **Evidence:**
  `current-firmware: 7.15.1`, `upgrade-firmware: 7.25.1`.
- **Technical Explanation:**
  The hardware bootloader is significantly behind the running RouterOS kernel.
- **Proposed Remediation Commands:**
  ```routeros
  /system routerboard upgrade
  # System must be rebooted during maintenance window:
  # /system reboot
  ```

---

### [HIGH-03] Unshielded IPv6 Stack with Global Forwarding Enabled
- **Severity:** **HIGH**
- **Configuration Location:** `/ipv6 settings` and `/ipv6 firewall filter`
- **Evidence:**
  `forward: yes`, `/ipv6 firewall filter` has 0 static rules.
- **Proposed Remediation Commands:**
  ```routeros
  # If IPv6 is not provided by upstream ISP:
  /ipv6 settings set disable-ipv6=yes
  # OR if IPv6 is required, deploy stateful IPv6 filter rules:
  /ipv6 firewall filter
  add chain=input action=accept connection-state=established,related
  add chain=input action=drop connection-state=invalid
  add chain=input action=accept protocol=icmpv6
  add chain=input action=drop in-interface-list=WAN
  add chain=forward action=accept connection-state=established,related
  add chain=forward action=drop connection-state=invalid
  add chain=forward action=drop in-interface-list=WAN
  ```

---

### [HIGH-04] Subnet Mask Inconsistency (DHCP `/16` vs Interface `/24`)
- **Severity:** **HIGH**
- **Configuration Location:** `/ip dhcp-server network`
- **Evidence:**
  Interface has `192.168.0.1/24`, DHCP network gives `192.168.0.0/16`.
- **Proposed Remediation Commands:**
  ```routeros
  /ip dhcp-server network
  set [find address="192.168.0.0/16"] address=192.168.0.0/24 gateway=192.168.0.1
  ```

---

### [MED-01] `Bridge-Local` Disabled in Interface List `LAN`
- **Severity:** **MEDIUM**
- **Configuration Location:** `/interface list member`
- **Evidence:**
  `list=LAN interface=Bridge-Local` is `DISABLED`. `ether3` is listed as member.
- **Proposed Remediation Commands:**
  ```routeros
  /interface list member
  enable [find list=LAN interface=Bridge-Local]
  remove [find list=LAN interface=ether3]
  ```

---

### [MED-02] Problematic Network-Zero (.0) Addresses in PPPoE IP Pools
- **Severity:** **MEDIUM**
- **Configuration Location:** `/ip pool`
- **Evidence:**
  `Pool-PPOE-2M` starts at `172.16.2.0`.
  `Pool-PPOE-10M` starts at `172.16.10.0`.
- **Proposed Remediation Commands:**
  ```routeros
  /ip pool
  set Pool-PPOE-2M ranges=172.16.2.1-172.16.2.254
  set Pool-PPOE-10M ranges=172.16.10.1-172.16.10.254
  ```

---

### [MED-03] Information Leakage via MNDP/CDP Over Tower Link `ether2`
- **Severity:** **MEDIUM**
- **Configuration Location:** `/ip neighbor discovery-settings`
- **Evidence:**
  `discover-interface-list=!WAN`. `ether2` is not in `WAN`.
- **Proposed Remediation Commands:**
  ```routeros
  /ip neighbor discovery-settings
  set discover-interface-list=LAN
  ```

---

### [MED-04] Lack of Dynamic Gateway Probing (`check-gateway=none`) in Routing
- **Severity:** **MEDIUM**
- **Configuration Location:** `/ip route`
- **Evidence:**
  `check-gateway=none` on all static default routes.
- **Proposed Remediation Commands:**
  ```routeros
  /ip route
  set [find gateway=pppoe-out1 routing-table=main] check-gateway=ping
  set [find gateway=pppoe-out2 routing-table=main] check-gateway=ping
  set [find gateway=pppoe-out3 routing-table=main] check-gateway=ping
  ```
