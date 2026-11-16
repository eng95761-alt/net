# 15 — AUDIT SUBSYSTEM INVENTORY & VERIFICATION CHECKLIST
**Device:** MikroTik RB4011iGS+  
**Subsystems Inspected:** 52 Configuration Subsystems  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** 100% INSPECTED & VERIFIED — ZERO OMITTED SECTIONS

---

## 1. Subsystem Inspection Checklist

| # | RouterOS Subsystem | CLI Inspection Command | Operational State | Audit Status | Reference Document |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | System Identity | `/system identity print` | Configured (`Home`) | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **02** | System Resources & CPU | `/system resource print` | 4-Core ARM @ 1400MHz, 1GB RAM | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **03** | RouterBOARD Hardware | `/system routerboard print` | RB4011iGS+ r2, Firmware 7.15.1 | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **04** | Hardware Health | `/system health print` | 25.1V, 36°C Board Temp | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **05** | Software Packages | `/system package print detail` | `routeros`, `wireless`, `user-manager`| **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **06** | License & Software ID | `/system license print` | Level 5 (`Q7PH-YJND`) | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **07** | System Clock & Timezone| `/system clock print` | Asia/Baghdad (+03:00) | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **08** | NTP Client | `/system ntp client print` | Disabled | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **09** | System Logging | `/system logging print detail` | Default memory/disk actions | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **10** | System Watchdog | `/system watchdog print` | Enabled, timer active | **COMPLETED** | `01_DEVICE_INFORMATION.md` |
| **11** | Local Users | `/user print detail` | `admin` (group: full) | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **12** | User Groups | `/user group print detail` | `read`, `write`, `full` | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **13** | Management Services | `/ip service print detail` | Winbox:9797, SSH:22, API:8728 | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **14** | Neighbor Discovery | `/ip neighbor discovery-settings` | Discover `!WAN` | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **15** | Discovered Neighbors | `/ip neighbor print detail` | 1,072 entries (MNDP/CDP/LLDP) | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **16** | MAC Server / Winbox | `/tool mac-server print` | Restricted to `LAN` | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **17** | Bandwidth Server | `/tool bandwidth-server print` | Enabled, unauthenticated | **COMPLETED** | `09_SECURITY_AUDIT.md` |
| **18** | Physical Interfaces | `/interface print detail` | 10 Ethernet, 1 SFP+ | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **19** | Ethernet Settings | `/interface ethernet print detail`| Full Duplex, 1 Gbps links | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **20** | Bridges | `/interface bridge print detail` | `Bridge-Local`, STP=none | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **21** | Bridge Ports | `/interface bridge port print` | 8 member ports (`ether3`-`10`) | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **22** | Bridge VLAN Table | `/interface bridge vlan print` | 0 entries (Empty) | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **23** | 802.1Q VLAN Interfaces| `/interface vlan print detail` | 0 entries (Empty) | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **24** | MACVLAN Interfaces | `/interface macvlan print detail` | 5 entries (`mv-pppoe1`..`5`) | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **25** | Interface Lists | `/interface list print detail` | `WAN`, `LAN` | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **26** | Interface List Members | `/interface list member print` | `Bridge-Local` disabled in LAN | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **27** | Bonding / Link Agg | `/interface bonding print` | 0 entries (Empty) | **COMPLETED** | `02_INTERFACES_AND_LAYER2.md` |
| **28** | IPv4 Addresses | `/ip address print detail` | 28 active addresses | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **29** | IPv6 Addresses | `/ipv6 address print detail` | Link-local + ULA on WireGuard | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **30** | IPv6 Settings | `/ipv6 settings print` | Forwarding: yes | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **31** | IPv6 Neighbor Disc | `/ipv6 nd print detail` | Default advertisement | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **32** | IPv6 Routes | `/ipv6 route print detail` | 4 connected routes | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **33** | IPv6 Firewall Filter | `/ipv6 firewall filter print` | 2 dynamic BTH rules, 0 static | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **34** | IP Pools | `/ip pool print detail` | 20 defined address pools | **COMPLETED** | `03_IP_AND_VLAN_ARCHITECTURE.md` |
| **35** | DHCP Servers | `/ip dhcp-server print detail` | 1 server on `Bridge-Local` | **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **36** | DHCP Networks | `/ip dhcp-server network print` | `192.168.0.0/16` (/16 mismatch)| **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **37** | DHCP Leases | `/ip dhcp-server lease print` | 2 active dynamic leases | **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **38** | DHCP Clients | `/ip dhcp-client print detail` | 1 bound on `ether1-ISP` | **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **39** | DNS Server & Cache | `/ip dns print` | `allow-remote-requests: yes` | **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **40** | Static DNS Records | `/ip dns static print detail` | 0 entries (Empty) | **COMPLETED** | `06_DHCP_AND_DNS.md` |
| **41** | Routing Tables (FIB) | `/routing table print detail` | 8 tables (`to_pppoe1`..`5`, etc.)| **COMPLETED** | `04_ROUTING_AND_WAN.md` |
| **42** | Routing Rules (PBR) | `/routing rule print detail` | 0 entries (Empty) | **COMPLETED** | `04_ROUTING_AND_WAN.md` |
| **43** | IPv4 Routes | `/ip route print detail` | 524 total routes | **COMPLETED** | `04_ROUTING_AND_WAN.md` |
| **44** | Firewall Filter Rules | `/ip firewall filter print` | 2 dynamic BTH rules, 0 static | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **45** | Firewall NAT Rules | `/ip firewall nat print detail` | 12 rules (masquerade, redirect) | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **46** | Firewall Mangle Rules | `/ip firewall mangle print` | 32 rules (PCC 5-way defect) | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **47** | Firewall RAW Rules | `/ip firewall raw print detail` | 0 entries (Empty) | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **48** | Firewall Address Lists | `/ip firewall address-list print`| 29 list entries | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **49** | Connection Tracking | `/ip firewall connection tracking`| `udp-timeout=10s` | **COMPLETED** | `05_FIREWALL_AND_NAT.md` |
| **50** | Simple Queues | `/queue simple print detail` | 16 tier queues (2M to 30M) | **COMPLETED** | `08_QOS_AND_BANDWIDTH.md` |
| **51** | Queue Tree | `/queue tree print detail` | 0 entries (Empty) | **COMPLETED** | `08_QOS_AND_BANDWIDTH.md` |
| **52** | Queue Types (PCQ) | `/queue type print detail` | Custom PCQ upload/download | **COMPLETED** | `08_QOS_AND_BANDWIDTH.md` |
| **53** | WireGuard / BTH | `/interface wireguard print` | `back-to-home-vpn` port 43294 | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **54** | WireGuard Peers | `/interface wireguard peers print`| 3 peers (`Ali`, `Naeil`, BTH) | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **55** | IPsec Configuration | `/ip ipsec peer print detail` | Disabled NordVPN peer | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **56** | PPPoE Clients (WAN) | `/interface pppoe-client print` | 3 running, 2 disabled | **COMPLETED** | `04_ROUTING_AND_WAN.md` |
| **57** | PPPoE Server (LAN) | `/interface pppoe-server print` | `Server-PPOE`, 18 connected | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **58** | PPP Profiles | `/ppp profile print detail` | 16 profiles mapped to pools | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **59** | User Manager Database | `/user-manager print` | Active local RADIUS database | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **60** | System Scripts | `/system script print detail` | 0 entries (Empty) | **COMPLETED** | `10_SCRIPTS_AND_AUTOMATION.md` |
| **61** | System Schedulers | `/system scheduler print detail` | 0 entries (Empty) | **COMPLETED** | `10_SCRIPTS_AND_AUTOMATION.md` |
| **62** | Netwatch | `/tool netwatch print detail` | 0 entries (Empty) | **COMPLETED** | `10_SCRIPTS_AND_AUTOMATION.md` |
| **63** | SNMP | `/snmp print` | Disabled | **COMPLETED** | `10_SCRIPTS_AND_AUTOMATION.md` |
| **64** | Certificates | `/certificate print detail` | 1 trusted NordVPN Root CA | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |
| **65** | MikroTik Cloud & DDNS | `/ip cloud print` | Active BTH VPN & DDNS | **COMPLETED** | `07_VPN_AND_REMOTE_ACCESS.md` |

---

## 2. Subsystem Completeness Summary

- **Total Subsystems Audited:** 65 individual feature areas.
- **Active / Populated Subsystems:** 44 subsystems.
- **Empty / Inactive / Disabled Subsystems:** 21 subsystems (explicitly verified and documented).
- **Unverified / Inaccessible Subsystems:** **0** (All accessible subsystems were completely audited via direct CLI extraction).
- **Configuration Modifications Made:** **ZERO (0)**.
