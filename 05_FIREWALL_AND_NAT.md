# 05 — FIREWALL, NAT & MANGLE AUDIT
**Device:** MikroTik RB4011iGS+  
**Subsystem:** Filter Rules, NAT, Mangle, RAW, Address Lists, and Connection Tracking  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Firewall Filter Rules Audit (`/ip firewall filter`)

### Current Configuration Inventory:
```
Flags: D - DYNAMIC
 #   CHAIN    ACTION  PROTOCOL  DST-PORT  SRC-ADDRESS-LIST                    OUT-INTERFACE-LIST  COMMENT
 0 D forward  drop                        back-to-home-lan-restricted-peers   LAN                 back-to-home-vpn
 1 D input    accept  udp       43294                                                             back-to-home-vpn
```

### [CRIT-01] Complete Absence of Protective Firewall Rules:
- **Zero Static Filter Rules:** The firewall filter table contains **zero user-configured rules**. The only 2 rules present were dynamically injected by the RouterOS Cloud Back-To-Home VPN engine.
- **Input Chain Vulnerability:**
  - Default action on input chain is implicit **ACCEPT**.
  - All router management services (SSH port 22, Winbox port 9797, API port 8728, API-SSL port 8729, Reverse-Proxy port 443) are wide open and directly reachable from the WAN, upstream modem subnet (`192.168.4.0/24`), tower network (`10.235.51.0/24`), PPPoE client links, and local bridge.
  - Zero brute-force rate limiting or blacklisting exists.
- **Forward Chain Vulnerability:**
  - Default action on forward chain is implicit **ACCEPT**.
  - There is no stateful filtering (`connection-state=established,related,untracked accept` / `invalid drop`).
  - No inter-subnet isolation exists between local management (`192.168.0.0/24`) and subscriber pools (`172.16.0.0/16`, `172.17.0.0/16`).
  - Subscribers can port-scan, probe, and attack other subscribers across the bridge.

---

## 2. NAT (Network Address Translation) Audit (`/ip firewall nat`)

```
Flags: I - INVALID; D - DYNAMIC
 #    CHAIN   ACTION      DST-PORT  PROTO  OUT-INTERFACE  ROUTING-MARK  SRC-ADDRESS       TO-ADDRESSES   COMMENT
 0 D  srcnat  masquerade                   (in: bth-vpn)                                                 back-to-home-vpn
 1    srcnat  masquerade                   ether2                                                        NAT Local users to Tower
 2    srcnat  src-nat                      ether2         Via-Quicknet                    10.235.50.21
 3    srcnat  masquerade                   ether1-ISP     Via-Starlink  list: Local
 4    srcnat  masquerade                   ether1-ISP                   172.16.0.0/16
 5    dstnat  redirect    53        udp                                                   to: 53         Force Router DNS
 6    dstnat  redirect    53        tcp                                                   to: 53         Force Router DNS
 7    srcnat  masquerade                   pppoe-out1                                                    Masquerade pppoe-out1
 8    srcnat  masquerade                   pppoe-out2                                                    Masquerade pppoe-out2
 9    srcnat  masquerade                   pppoe-out3                                                    Masquerade pppoe-out3
10 I  srcnat  masquerade                   pppoe-out4                                                    [pppoe-out4 not ready]
11 I  srcnat  masquerade                   pppoe-out5                                                    [pppoe-out5 not ready]
```

### Rule-by-Rule NAT Analysis:
- **Rule 0 (Dynamic BTH):** Translates incoming Back-To-Home WireGuard VPN client traffic onto the local LAN.
- **Rule 1 (`ether2` Masquerade):** Masquerades local packets exiting towards the Tower network.
- **Rule 2 (`ether2` SNAT):** Explicit Source NAT rewriting egress packets marked `Via-Quicknet ` to tower IP `10.235.50.21`.
- **Rules 3 & 4 (`ether1-ISP` Masquerade):** Legacy masquerade rules for Starlink and `172.16.0.0/16`.
- **Rules 5 & 6 (DNS Interception):** Forces all outbound UDP and TCP DNS traffic (port 53) to be redirected locally to the router's internal DNS resolver. Combined with `allow-remote-requests=yes`, this forces clients to use the router's DNS cache.
- **Rules 7, 8, 9 (PPPoE WAN Masquerade):** Correctly masquerades traffic exiting through the active PPPoE lines (`pppoe-out1`, `pppoe-out2`, `pppoe-out3`).
- **Rules 10 & 11 (Invalid Rules):** Flagged `I - INVALID` because `pppoe-out4` and `pppoe-out5` are disabled. While harmless, they represent unnecessary configuration clutter.

---

## 3. Mangle Rules Audit (`/ip firewall mangle`)

The mangle table is the core engine for Multi-WAN PCC load balancing, TTL normalization, and TCP MSS clamping. It contains **32 rules**.

### A. TTL Manipulation (Anti-Tethering / Hotspot Bypass):
```
0  chain=postrouting action=change-ttl new-ttl=set:65 passthrough=no out-interface=ether1-ISP
1  chain=prerouting action=change-ttl new-ttl=set:255 passthrough=no in-interface=ether1-ISP
```
- **Rule 0:** Sets outbound TTL to `65`. When traffic exits the modem to the upstream cellular ISP, the first upstream hop decrements TTL to `64` (standard host TTL for Windows/Linux), masking the presence of downstream routed devices and bypassing carrier tethering throttling.
- **Rule 1:** Resets incoming TTL to `255` on `ether1-ISP`.

### B. Route Exceptions & Legacy PBR:
```
2    chain=prerouting action=accept dst-address=10.235.51.0/24 src-address-list=Local
3 X  chain=prerouting action=mark-routing new-routing-mark=Via-Quicknet src-address-list=Quicknet
4 X  chain=prerouting action=mark-connection new-connection-mark=Quick-Net per-connection-classifier=src-address:2/0
5 X  chain=prerouting action=mark-routing new-routing-mark=Via-Quicknet connection-mark=Quick-Net
6 X  chain=prerouting action=mark-connection new-connection-mark=Starlink
7 X  chain=prerouting action=mark-routing new-routing-mark=Via-Starlink connection-mark=Starlink
```
- Rules 3–7 are **DISABLED**, indicating a migration away from an earlier 2-way Starlink/Quicknet setup toward the current PPPoE Multi-WAN balancer.

### C. Inbound Connection Tracking (PPPoE Interfaces):
```
 8    chain=prerouting action=mark-connection new-connection-mark=pppoe1_conn in-interface=pppoe-out1 passthrough=yes
 9    chain=prerouting action=mark-connection new-connection-mark=pppoe2_conn in-interface=pppoe-out2 passthrough=yes
10    chain=prerouting action=mark-connection new-connection-mark=pppoe3_conn in-interface=pppoe-out3 passthrough=yes
11 I  chain=prerouting action=mark-connection new-connection-mark=pppoe4_conn in-interface=pppoe-out4 [INVALID]
12 I  chain=prerouting action=mark-connection new-connection-mark=pppoe5_conn in-interface=pppoe-out5 [INVALID]
```
- Ensures that replies to connections initiated from the outside return via the exact same WAN interface on which they entered (Symmetric Ingress/Egress).

### D. Private RFC1918 Inter-LAN Routing Bypass:
```
13  chain=prerouting action=accept dst-address=10.0.0.0/8
14  chain=prerouting action=accept dst-address=172.16.0.0/12
15  chain=prerouting action=accept dst-address=192.168.0.0/16
```
- Essential bypass rules: Internal traffic destined for local subnets or other routers is accepted immediately, bypassing subsequent PCC connection marking and routing marks.

### E. PCC Classification Rules (Prerouting):
```
16    chain=prerouting action=mark-connection new-connection-mark=pppoe1_conn
      connection-state=new src-address-list=Local dst-address-list=!Local
      per-connection-classifier=both-addresses:5/0 passthrough=yes

17    chain=prerouting action=mark-connection new-connection-mark=pppoe2_conn
      connection-state=new src-address-list=Local dst-address-list=!Local
      per-connection-classifier=both-addresses:5/1 passthrough=yes

18    chain=prerouting action=mark-connection new-connection-mark=pppoe3_conn
      connection-state=new src-address-list=Local dst-address-list=!Local
      per-connection-classifier=both-addresses:5/2 passthrough=yes

19 X  chain=prerouting action=mark-connection new-connection-mark=pppoe4_conn
      per-connection-classifier=both-addresses:5/3 passthrough=yes [DISABLED]

20 X  chain=prerouting action=mark-connection new-connection-mark=pppoe5_conn
      per-connection-classifier=both-addresses:5/4 passthrough=yes [DISABLED]
```
- **CRITICAL DEFECT [CRIT-03]:** Rules 19 and 20 are disabled while rules 16–18 use denominator 5. Connections evaluating to hash remainders 3 and 4 bypass marking and dump onto `pppoe-out1` via the `main` table default route.

### F. Routing Mark Application:
```
21  chain=prerouting action=mark-routing new-routing-mark=to_pppoe1 connection-mark=pppoe1_conn passthrough=no
22  chain=prerouting action=mark-routing new-routing-mark=to_pppoe2 connection-mark=pppoe2_conn passthrough=no
23  chain=prerouting action=mark-routing new-routing-mark=to_pppoe3 connection-mark=pppoe3_conn passthrough=no
24  chain=prerouting action=mark-routing new-routing-mark=to_pppoe4 connection-mark=pppoe4_conn passthrough=no
25  chain=prerouting action=mark-routing new-routing-mark=to_pppoe5 connection-mark=pppoe5_conn passthrough=no

26  chain=output action=mark-routing new-routing-mark=to_pppoe1 connection-mark=pppoe1_conn passthrough=no
27  chain=output action=mark-routing new-routing-mark=to_pppoe2 connection-mark=pppoe2_conn passthrough=no
28  chain=output action=mark-routing new-routing-mark=to_pppoe3 connection-mark=pppoe3_conn passthrough=no
29  chain=output action=mark-routing new-routing-mark=to_pppoe4 connection-mark=pppoe4_conn passthrough=no
30  chain=output action=mark-routing new-routing-mark=to_pppoe5 connection-mark=pppoe5_conn passthrough=no
```
- Correctly binds connection marks to FIB routing tables for forwarded client traffic (prerouting) and router-generated traffic (output).

### G. TCP MSS Clamping:
```
31  chain=forward action=change-mss new-mss=clamp-to-pmtu passthrough=yes protocol=tcp tcp-flags=syn
```
- **Function:** Enforces dynamic Path MTU discovery clamping on TCP SYN packets traversing the router.
- **Significance:** PPPoE encapsulates Ethernet with an 8-byte header, reducing standard MTU from 1500 to 1480 (or 1492). MSS clamping prevents packet fragmentation, web page timeouts, and SSL/TLS handshake failures.

---

## 4. Firewall Address Lists Audit (`/ip firewall address-list`)

| List Name | Entry / Subnet | Type | Purpose |
| :--- | :--- | :--- | :--- |
| **`Local`** | `10.0.0.0/8` | Static | RFC1918 Private Addressing |
| **`Local`** | `172.16.0.0/16` | Static | Subscriber Addressing Block A |
| **`Local`** | `192.168.0.0/16` | Static | LAN / Tower Addressing Block |
| **`VPN`** | `172.16.0.0/20`, `172.16.100.0/24` | Static | Legacy VPN Subnets |
| **`Route-VPN`** | `1.1.1.1` | Static | Single IP targeted for VPN routing |
| **`VIP_Bypass`** | `172.16.8.250` | Static | High-priority client bypass |
| **`Quicknet`** | `172.17.0.0/16` + Dynamic IPs | Mixed | PPPoE Subscribers routed via Quicknet |
| **`back-to-home-lan-restricted-peers`**| `192.168.216.4` | Dynamic | Peer "Naeil" restricted from accessing local LAN |

---

## 5. Connection Tracking & RAW Settings

```
/ip firewall connection tracking
set udp-timeout=10s
```

- **Tuning Analysis:** Default UDP connection tracking timeout in RouterOS is `30s`. Setting `udp-timeout=10s` is a deliberate optimization for high-density subscriber gateways. It accelerates the eviction of dead UDP NAT states (DNS queries, streaming sessions, gaming sessions), conserving RAM and keeping the conntrack table lean.
- **RAW Filter Rules:** `/ip firewall raw` is completely **empty**. No stateless pre-conntrack dropping is in place.
