# 00 — EXECUTIVE SUMMARY & NETWORK AUDIT OVERVIEW
**Target Device:** MikroTik RB4011iGS+ (r2)  
**RouterOS Version:** 7.25.1 (Stable, Build: 2026-11-02 12:39:53)  
**System Identity:** `Home`  
**Audit Date:** 2026-11-15  
**Auditor:** Senior MikroTik RouterOS Network Engineer & Security Auditor  
**Audit Status:** COMPLETE — 100% READ-ONLY FORENSIC AUDIT (Zero Configuration Changes)

---

## 1. Executive Statement

A comprehensive, exhaustive, and non-intrusive forensic audit of the MikroTik RB4011iGS+ router was conducted on November 15, 2026. In strict accordance with the mandatory safety directives, **ZERO configuration changes, resets, or service interruptions were performed**.

All findings, architecture maps, and technical recommendations presented in this documentation package are derived exclusively from live state extraction, subsystem print outputs, and configuration exports.

---

## 2. Router Role & Operational Context

The RB4011 router operates as a **High-Performance Multi-WAN Distribution and WISP/ISP Access Gateway**. It serves three distinct roles simultaneously:

1. **Multi-WAN Aggregation Core:**
   - Terminating multiple PPPoE client sessions (`pppoe-out1` to `pppoe-out3`) over virtual MACVLAN interfaces (`mv-pppoe1` to `mv-pppoe5`) mapped to a single physical ISP interface (`ether1-ISP`).
   - Distributing outbound traffic using Per-Connection Classification (PCC) and Policy-Based Routing (PBR).
   - Providing secondary routed connectivity to a wireless tower network via `ether2` (`10.235.51.4/24`).

2. **Broadband Subscriber Access Server (PPPoE BNG / BRAS):**
   - Hosting a high-capacity PPPoE Server (`Server-PPOE`) on `Bridge-Local`.
   - Managing and authenticating active subscribers (18 concurrently connected during the audit) via a local MikroTik **User Manager v5 / RADIUS** database.
   - Enforcing tiered bandwidth limits through dynamic IP assignment mapped to hierarchical **Per Connection Queue (PCQ)** simple queues (tiers ranging from 2 Mbps to 30 Mbps).

3. **Remote Management & Secure Ingress Hub:**
   - Running MikroTik Cloud Back-To-Home (BTH) WireGuard VPN through a European relay server to bypass upstream ISP Carrier-Grade NAT (CGNAT).
   - Providing Winbox access via custom port `9797` and SSH management on port `22`.

---

## 3. Key Device Statistics & Vital Signs

| Parameter | Current Value | Optimal / Reference | Status |
| :--- | :--- | :--- | :--- |
| **Model** | MikroTik RB4011iGS+ | RB4011iGS+ | Normal |
| **Architecture / CPU** | ARM 4-Core @ 1400 MHz | ARM Cortex-A15 AL21400 | Warning (Manual Frequency) |
| **RAM Utilization** | 228.3 MiB used / 1024 MiB total (78% free) | > 20% free | Excellent |
| **Storage Utilization**| 91.4 MiB used / 512 MiB NAND (82% free) | > 20% free | Excellent |
| **Storage Health** | 0% Bad Blocks (1,286,470 write sectors total) | 0% | Healthy |
| **Hardware Voltage** | 25.1 V | 12 - 57 V range | Optimal |
| **Board Temperature** | 36 °C | < 65 °C | Excellent |
| **RouterOS Version** | 7.25.1 | Latest v7 Release | Up to date |
| **RouterBOOT Firmware**| **7.15.1** | **7.25.1** | **Outdated (Action Required)** |
| **System Uptime** | 1 week, 2 days, 17 hours, 22 minutes | Continuous | Stable |
| **Active PPPoE Clients**| 3 Active, 2 Disabled | 5 Configured | Asymmetric Balancer |
| **Connected Subscribers**| 18 Active PPPoE Sessions | Variable | Stable |

---

## 4. Summary of Audit Findings by Severity

A total of **16 distinct findings** were identified across 12 configuration subsystems:

```
+-------------------------------------------------------------+
|                     AUDIT FINDINGS SUMMARY                  |
+-------------------+-----------------------------------------+
| [CRITICAL]        | 4 Findings (Immediate Risk)             |
| [HIGH]            | 4 Findings (Security & Reliability)     |
| [MEDIUM]          | 4 Findings (Performance & Architecture) |
| [LOW]             | 2 Findings (Optimization & Cleanup)     |
| [INFORMATIONAL]   | 2 Findings (Architectural Notes)        |
+-------------------+-----------------------------------------+
```

### Critical Findings Summary (Immediate Risk):
1. **[CRIT-01] Absence of Input & Forward Firewall Filters:** The router possesses **zero user-defined filter rules** in the `/ip firewall filter` facility. Management ports (SSH 22, Winbox 9797, API 8728, API-SSL 8729, Reverse-Proxy 443) are completely unshielded and exposed to any host that can route traffic to the router from WAN, LAN, or VPN.
2. **[CRIT-02] Open DNS Recursive Resolver (`allow-remote-requests=yes`):** The internal DNS server responds to external and internal DNS requests without firewall restriction. Combined with port 53 `dstnat` redirect rules, the router is susceptible to DNS amplification attacks, cache poisoning, and upstream resource exhaustion.
3. **[CRIT-03] Broken 5-Way PCC Load Balancer Causing Severe Traffic Imbalance:** Mangle rules divide connections by 5 (`5/0`, `5/1`, `5/2`), but rules for `5/3` and `5/4` are disabled. Consequently, **40% of all client traffic fails to receive a routing mark**, defaulting to the `main` table default route (`pppoe-out1`). `pppoe-out1` carries ~60% of total bandwidth while `pppoe-out2` and `pppoe-out3` carry only 20% each.
4. **[CRIT-04] Complete Lack of Spanning Tree / Loop Protection (`protocol-mode=none`):** `Bridge-Local` has spanning tree disabled (`protocol-mode=none`). If a physical loop or misconfigured switch is attached to any of the 8 bridge ports (`ether3`-`ether10`), a broadcast storm will immediately incapacitate the router and all attached towers/clients.

### High Severity Findings Summary:
5. **[HIGH-01] Unrestricted Management Service Exposure:** Services (`ssh`, `winbox`, `api`, `api-ssl`, `reverse-proxy`) have `available-from=""`, permitting access from any IP address without subnet whitelisting.
6. **[HIGH-02] Outdated RouterBOOT Firmware (7.15.1 vs 7.25.1):** The RouterBOARD firmware is 10 minor versions behind the installed RouterOS software, risking driver instability and hardware offloading defects.
7. **[HIGH-03] Unprotected IPv6 Stack with Forwarding Enabled:** IPv6 is enabled and forwarding is active globally, but the IPv6 firewall filter contains zero user rules.
8. **[HIGH-04] Subnet Mask Mismatch (DHCP `/16` vs Interface `/24`):** The DHCP server broadcasts `192.168.0.0/16` to local clients, while `Bridge-Local` holds distinct `/24` subnets (`192.168.0.1/24`, `192.168.1.1/24`, `192.168.2.1/24`, `192.168.9.200/24`), resulting in ARP collisions and routing ambiguity.

---

## 5. Architectural Topology Overview

```
                      +---------------------------------------+
                      |               INTERNET                |
                      +---------------------------------------+
                                          |
                      +---------------------------------------+
                      | Upstream ISP Modem / ONT (CGNAT)      |
                      | LAN: 192.168.4.1/24                   |
                      +---------------------------------------+
                                          |
                          (Physical Trunk: ether1-ISP)
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
[DHCP Client: 192.168.4.238]    [MACVLAN Trunk: mv-pppoe1..5]     [ether2: 10.235.51.4/24]
        |                                 |                                 |
        v                                 v                                 v
[MikroTik Cloud / BTH]           [3x Active PPPoE Out]             [Tower / IXP Network]
[WireGuard Port 43294]           [pppoe-out1, out2, out3]          [GW: 10.235.51.1]
                                          |
                                          v
                      +---------------------------------------+
                      | MIKROTIK RB4011iGS+ CORE (v7.25.1)    |
                      | PCC Mangle Load Balancer (5-way defect)|
                      | NAT / Masquerade Engines              |
                      +---------------------------------------+
                                          |
                      +---------------------------------------+
                      | Bridge-Local (ether3 - ether10)       |
                      | STP: NONE | VLAN Filtering: OFF       |
                      +---------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
        v                                 v                                 v
[PPPoE Server: Server-PPOE]      [LAN IP Subnets /24]              [User Manager v5]
[18 Connected Subscribers]       [192.168.0.1, 1.1, 2.1, 9.200]    [Internal RADIUS Auth]
[PCQ Speed Queues: 2M - 30M]     [DHCP Pool: 192.168.0.10 - 250]   [Subscriber Profiles]
```

---

## 6. Documentation Package Structure

This audit has produced a complete, multi-part forensic documentation package:

| File Name | Description |
| :--- | :--- |
| [`00_EXECUTIVE_SUMMARY.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/00_EXECUTIVE_SUMMARY.md) | Network status, role, vital signs, and executive risk assessment |
| [`01_DEVICE_INFORMATION.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/01_DEVICE_INFORMATION.md) | Hardware, firmware, licensing, resources, health, and packages |
| [`02_INTERFACES_AND_LAYER2.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/02_INTERFACES_AND_LAYER2.md) | Physical ports, MACVLAN, bridges, STP, and switch chip architecture |
| [`03_IP_AND_VLAN_ARCHITECTURE.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/03_IP_AND_VLAN_ARCHITECTURE.md) | Addressing, subnets, ARP table, and Layer 2 broadcast domains |
| [`04_ROUTING_AND_WAN.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/04_ROUTING_AND_WAN.md) | Multi-WAN, PPPoE clients, routing tables, and failover design |
| [`05_FIREWALL_AND_NAT.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/05_FIREWALL_AND_NAT.md) | Rule-by-rule analysis of Filter, NAT, Mangle, RAW, and Address Lists |
| [`06_DHCP_AND_DNS.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/06_DHCP_AND_DNS.md) | DHCP server/client, pools, DNS cache, and recursive resolver audit |
| [`07_VPN_AND_REMOTE_ACCESS.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/07_VPN_AND_REMOTE_ACCESS.md) | Back-To-Home WireGuard, IPsec, PPPoE server, and remote access |
| [`08_QOS_AND_BANDWIDTH.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/08_QOS_AND_BANDWIDTH.md) | Simple queues, PCQ queue types, burst rates, and subscriber tiering |
| [`09_SECURITY_AUDIT.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/09_SECURITY_AUDIT.md) | Comprehensive vulnerability assessment and threat modeling |
| [`10_SCRIPTS_AND_AUTOMATION.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/10_SCRIPTS_AND_AUTOMATION.md) | Audit of scripts, schedulers, netwatch, and watchdog automation |
| [`11_DEPENDENCY_MAP.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/11_DEPENDENCY_MAP.md) | Inter-subsystem relationships and impact matrix |
| [`12_NETWORK_TOPOLOGY.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/12_NETWORK_TOPOLOGY.md) | Detailed Mermaid physical, logical, and traffic-flow diagrams |
| [`13_FINDINGS_AND_RECOMMENDATIONS.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/13_FINDINGS_AND_RECOMMENDATIONS.md) | Actionable remediation catalog with exact proposed commands |
| [`14_COMPLETE_RAW_CONFIGURATION_REDACTED.txt`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/14_COMPLETE_RAW_CONFIGURATION_REDACTED.txt) | Complete text configuration export with credentials redacted |
| [`15_AUDIT_INVENTORY.md`](file:///c:/Users/DIGITAL%20WORLD/Desktop/4011/15_AUDIT_INVENTORY.md) | Checklist of all 52 inspected RouterOS configuration subsystems |

---

## 7. Immediate Administrative Action Plan (Requires Approval)

To transition this network to an enterprise-grade, secure, and balanced state, the following phased interventions are recommended once explicitly authorized:

1. **Phase 1: Perimeter & Management Hardening (Urgent)**
   - Apply a stateful `/ip firewall filter` input and forward ruleset.
   - Restrict DNS `allow-remote-requests` to LAN and PPPoE subscribers only, or drop WAN DNS on input.
   - Restrict management services (`winbox`, `ssh`, `api`) to designated management IP subnets.
2. **Phase 2: Traffic Balancer Alignment**
   - Recalibrate the PCC mangle rules to match the 3 active PPPoE lines (`both-addresses:3/0`, `3/1`, `3/2`) to eliminate the 40% traffic spillover.
3. **Phase 3: Layer 2 Loop Protection & Bridge Optimization**
   - Enable RSTP (`protocol-mode=rstp`) on `Bridge-Local`.
   - Resolve the DHCP `/16` vs interface `/24` subnet mismatch.
4. **Phase 4: Maintenance & Firmware Upgrade**
   - Execute RouterBOARD firmware upgrade from 7.15.1 to 7.25.1 during a scheduled maintenance window.
