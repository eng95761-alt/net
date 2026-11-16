# 11 — CONFIGURATION DEPENDENCY & RELATIONSHIP MAP
**Device:** MikroTik RB4011iGS+  
**Discipline:** End-to-End Architectural Tracing, Inter-Subsystem Relationships & Failure Cascades  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Architectural Tracing: How the Entire Network Operates

To safely troubleshoot, optimize, and maintain this router, configuration settings must not be viewed as isolated commands. Every packet traverses a precise chain of interconnected subsystems.

### Chain A: Subscriber Access, Authentication & Dynamic Rate Limiting
```
[Physical Port: ether3-10]
          |
          v
[Bridge-Local (STP=none)]
          |
          v
[PPPoE Server: Server-PPOE] <---> [Radius Client (/radius)] <---> [User Manager v5 (/user-manager)]
          |                                                              |
          v                                                              v
[PPP Profile (e.g. 5M)] <----------------------------------------- [User Group & Limitations]
          |
          +---> Local IP: Pool-Local (192.168.0.1)
          +---> Remote IP: Pool-PPOE-5M (172.16.5.x)
          |
          v
[Dynamic Interface: <pppoe-username>]
          |
          v
[Simple Queue Match: "5M" (Target: 172.16.5.0/24)]
          |
          +---> Queue Type Upload: PCQ-Upload-5M (Rate: 5M, Class: src-address)
          +---> Queue Type Download: PCQ-Download-5M (Rate: 5M, Class: dst-address)
```

- **Dependency Rule:** If the `user-manager` database becomes corrupted or the internal RADIUS socket (UDP 1812/1813) is blocked, no PPPoE subscriber can authenticate.
- **Dependency Rule:** If a PPP profile's remote address pool name does not match `/ip pool`, subscriber connection negotiation stalls at IPCP phase.

---

### Chain B: Outbound Multi-WAN PCC Load Balancing & NAT Pipeline
```
[Client Egress Packet from 172.16.5.223 destined to 1.1.1.1]
          |
          v
[Mangle Prerouting: RFC1918 Bypass (Rules 13-15)]
  - Is destination 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16? NO -> Proceed.
          |
          v
[Mangle Prerouting: PCC Hash Calculation (Rules 16-18)]
  - Evaluates both-addresses hash % 5:
      * Remainder 0 -> Mark: pppoe1_conn
      * Remainder 1 -> Mark: pppoe2_conn
      * Remainder 2 -> Mark: pppoe3_conn
      * Remainder 3 or 4 -> UNMARKED (Rules 19 & 20 disabled)
          |
          v
[Mangle Prerouting: Routing Mark Application (Rules 21-25)]
  - pppoe1_conn -> routing-mark: to_pppoe1
  - pppoe2_conn -> routing-mark: to_pppoe2
  - pppoe3_conn -> routing-mark: to_pppoe3
  - Unmarked -> NO ROUTING MARK
          |
          v
[Routing Evaluation (/ip route)]
  - If routing-mark=to_pppoe1 -> Uses Table "to_pppoe1" -> Gateway: pppoe-out1
  - If routing-mark=to_pppoe2 -> Uses Table "to_pppoe2" -> Gateway: pppoe-out2
  - If routing-mark=to_pppoe3 -> Uses Table "to_pppoe3" -> Gateway: pppoe-out3
  - If NO ROUTING MARK        -> Uses Table "main"      -> Gateway: pppoe-out1 (dist 10)
          |
          v
[NAT Evaluation (/ip firewall nat)]
  - Out-interface pppoe-out1 -> Rule 7 (srcnat masquerade)
  - Out-interface pppoe-out2 -> Rule 8 (srcnat masquerade)
  - Out-interface pppoe-out3 -> Rule 9 (srcnat masquerade)
          |
          v
[Mangle Postrouting & Forward Clamping]
  - Forward: Rule 31 (change-mss clamp-to-pmtu) -> TCP MSS clamped to 1440 bytes
          |
          v
[Layer 2 Egress Encapsulation]
  - pppoe-out1 -> encapsulated into mv-pppoe1 (MAC: 50:D4:F7:31:8A:12)
  - Transmitted out physical port ether1-ISP to Upstream Modem
```

---

### Chain C: Inbound Remote Management & Cloud WireGuard
```
[Admin Smartphone / Remote Laptop]
          |
          v
[Public Internet] ---> [MikroTik EUR1 Cloud Relay: 78.28.208.99:43294]
                                       |
                                       v
[Upstream ISP Modem / ONT (CGNAT 100.88.x.x)]
                                       |
                                       v
[ether1-ISP (192.168.4.238 via DHCP Client)]
                                       |
                                       v
[WireGuard Tunnel: back-to-home-vpn (192.168.216.1)]
                                       |
                                       v
[Firewall Input Chain (Rule 1 dynamic accept UDP 43294)]
                                       |
                                       v
[Admin Access to Winbox (port 9797) or SSH (port 22)]
```

---

## 2. Configuration Dependency Matrix

| If You Modify / Disrupt: | Cascading Direct Impact: | Subsystems at Risk: |
| :--- | :--- | :--- |
| **`ether1-ISP`** | All 5 MACVLANs drop; all 3 active PPPoE WAN sessions drop; BTH VPN drops. | Total loss of Internet egress and remote management. |
| **`mv-pppoe1` to `3`** | The corresponding `pppoe-out` tunnel collapses. | Outbound PCC routing tables stall; traffic blackholes. |
| **`Bridge-Local`** | All subscriber PPPoE sessions terminate immediately. | 18 connected subscribers disconnected; DHCP down. |
| **`/ip pool`** | PPP profiles referencing altered pool names cannot assign IPs. | PPPoE subscribers fail authentication with IPCP errors. |
| **`/routing table`** | Removing tables `to_pppoe1..3` renders mangle routing marks invalid. | Packets with orphaned routing marks are dropped. |
| **`/queue type` (PCQ)** | Modifying `PCQ-Upload` or `PCQ-Download` alters rate limits globally. | Subscriber bandwidth limits fail or reset to default. |
| **Mangle Rules 16–18** | Modifying PCC classifier modulus impacts traffic balance across all lines. | Line saturation or packet loss on surviving lines. |
| **NAT Rules 7–9** | Disabling masquerade rules halts packet translation for that WAN line. | Clients assigned to that line lose external connectivity. |
| **`User Manager`** | Modifying user database or RADIUS secret blocks authentication. | PPPoE server rejects all subscriber login credentials. |

---

## 3. Critical Dependency Insights for Future Maintenance

1. **Interface List `LAN` Dependency:**
   - Currently, `Bridge-Local` is **DISABLED** inside `/interface list member` under list `LAN`.
   - If an engineer introduces standard firewall filter rules referencing `in-interface-list=LAN`, all traffic from `Bridge-Local` will be immediately dropped because `Bridge-Local` is not currently an active member of `LAN`.
   - **Prerequisite:** Before applying any firewall filter rules referencing list `LAN`, `Bridge-Local` must be enabled in `LAN` and `ether3` removed.

2. **PBR Route Fallback Dependency:**
   - Dedicated routing tables (`to_pppoe1`, `to_pppoe2`, `to_pppoe3`) contain only a **single default route** each, with no backup gateway.
   - If `pppoe-out2` goes down, packets carrying `routing-mark=to_pppoe2` will not fall back to `pppoe-out1`; they will be dropped by the kernel with destination unreachable.
   - **Prerequisite:** Secondary backup routes with higher distance (e.g., distance 20 via `pppoe-out1`) must be added inside table `to_pppoe2` and `to_pppoe3`.
