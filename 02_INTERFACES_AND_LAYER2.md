# 02 — INTERFACES & LAYER 2 ARCHITECTURE
**Device:** MikroTik RB4011iGS+  
**Subsystem:** Interfaces, Ethernet, MACVLAN, Bridges, Ports, and Interface Lists  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Physical Hardware Port Mapping & Switch Architecture

The MikroTik RB4011iGS+ utilizes a dual-switch-chip architecture powered by two Realtek RTL8367 switch ASICs. Understanding this physical layout is critical for Layer 2 performance and hardware offloading:

- **Switch Chip 1 (RTL8367):** Connects physical ports `ether1` through `ether5` and links to the Alpine CPU via a dedicated 2.5 Gbps SGMII interconnect.
- **Switch Chip 2 (RTL8367):** Connects physical ports `ether6` through `ether10` and links to the CPU via a separate 2.5 Gbps SGMII interconnect.
- **SFP+ Cage (`sfp-sfpplus1`):** Bypasses both switch chips and connects directly to the CPU's internal 10G MAC.

```
                    +------------------------------------+
                    |        Annapurna AL21400 CPU       |
                    +------------------------------------+
                         /         | 10 Gbps        \
             2.5 Gbps   /          |                 \   2.5 Gbps
                       v           v                  v
         +-------------------+  [SFP+ Cage]   +-------------------+
         | Realtek RTL8367 #1|  (sfpplus1)    | Realtek RTL8367 #2|
         +-------------------+  (Link Down)   +-------------------+
          |   |   |   |   |                    |   |   |   |   |
          e1  e2  e3  e4  e5                   e6  e7  e8  e9  e10
```

---

## 2. Physical Port Operational Status

| Interface Name | Default Name | Role / Function | Operational Status | Speed / Duplex | MTU / L2MTU | MAC Address |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ether1-ISP`** | `ether1` | Physical WAN Trunk to ISP Modem | **RUNNING (Up)** | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:81` |
| **`ether2`** | `ether2` | Routed Link to Tower / IXP Network | **RUNNING (Up)** | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:82` |
| **`ether3`** | `ether3` | LAN Bridge Port (Switch 1) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:83` |
| **`ether4`** | `ether4` | LAN Bridge Port (Switch 1) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:84` |
| **`ether5`** | `ether5` | LAN Bridge Port (Switch 1) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:85` |
| **`ether6`** | `ether6` | LAN Bridge Port (Switch 2) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:86` |
| **`ether7`** | `ether7` | LAN Bridge Port (Switch 2) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:87` |
| **`ether8`** | `ether8` | LAN Bridge Port (Switch 2) | **DISABLED / DOWN** | No Link | 1500 / 1592 | `48:A9:8A:71:7A:88` |
| **`ether9`** | `ether9` | LAN Bridge Port (Switch 2) | **RUNNING (Up)**, Slave | 1 Gbps / Full | 1500 / 1592 | `48:A9:8A:71:7A:89` |
| **`ether10`**| `ether10`| LAN Bridge Port (Switch 2) | **DISABLED / DOWN** | No Link | 1500 / 1592 | `48:A9:8A:71:7A:8A` |
| **`sfp-sfpplus1`**| `sfp-sfpplus1`| 10G SFP+ Uplink | **DISCONNECTED / DOWN**| No SFP Module | 1500 / 1600 | `48:A9:8A:71:7A:8B` |

---

## 3. Virtual Interfaces & Layer 2 Sub-Interfaces

### A. MACVLAN Sub-Interfaces (`/interface macvlan`)
To enable multi-session PPPoE dialing across a single physical modem port without triggering MAC conflict restrictions at the ISP BRAS, five distinct MACVLAN interfaces are layered over `ether1-ISP`:

```
/interface macvlan
add interface=ether1-ISP mac-address=50:D4:F7:31:8A:12 mtu=1500 name=mv-pppoe1
add interface=ether1-ISP mac-address=D8:0D:17:4C:9B:34 mtu=1500 name=mv-pppoe2
add interface=ether1-ISP mac-address=60:32:B1:7E:2C:56 mtu=1500 name=mv-pppoe3
add interface=ether1-ISP mac-address=B0:4E:26:8A:1D:78 mtu=1500 name=mv-pppoe4
add interface=ether1-ISP mac-address=E8:48:B8:5B:3F:9A mtu=1500 name=mv-pppoe5
```

- **Technical Analysis:** Each MACVLAN possesses a locally administered unicast MAC address. The upstream ISP sees 5 physically distinct endpoints over the single Ethernet line. This is an efficient, standard engineering technique for ISP Multi-WAN bonding in RouterOS v7.

### B. PPPoE Client WAN Interfaces (`/interface pppoe-client`)
- **`pppoe-out1`:** Attached to `mv-pppoe1`, User `ali.nael` -> **RUNNING** (IP: `100.88.155.125`)
- **`pppoe-out2`:** Attached to `mv-pppoe2`, User `k@1234` -> **RUNNING** (IP: `100.88.132.11`)
- **`pppoe-out3`:** Attached to `mv-pppoe3`, User `m@232` -> **RUNNING** (IP: `100.88.87.20`)
- **`pppoe-out4`:** Attached to `mv-pppoe4`, User `user4` -> **DISABLED / STOPPED**
- **`pppoe-out5`:** Attached to `mv-pppoe5`, User `user5` -> **DISABLED / STOPPED**

### C. PPPoE Server Dynamic Ingress Interfaces
- There are **18 dynamic active PPPoE server interfaces** (`<pppoe-username>`) running over `Bridge-Local`, each terminating a subscriber session with MTU=1480, MRU=1480.

### D. WireGuard VPN Interface
- **`back-to-home-vpn`:** Virtual point-to-point interface for MikroTik Back-To-Home cloud WireGuard tunneling, listening on UDP port `43294` with MTU=1420.

---

## 4. Bridge & Layer 2 Switching Audit

### Bridge Configuration (`/interface bridge print detail`):
```
0 R name="Bridge-Local" mtu=auto actual-mtu=1500 l2mtu=1592 arp=enabled
    arp-timeout=auto mac-address=48:A9:8A:71:7A:83 protocol-mode=none
    fast-forward=yes igmp-snooping=no auto-mac=yes ageing-time=5m
    vlan-filtering=no dhcp-snooping=no dhcpv6-snooping=no ra-guard=no
    port-cost-mode=long forward-reserved-addresses=no max-learned-entries=auto
```

### Critical Layer 2 Findings:
1. **[CRIT-04] Spanning Tree Protocol Completely Disabled (`protocol-mode=none`):**
   - **Configuration:** `protocol-mode=none`
   - **Vulnerability:** The router performs zero loop detection or mitigation. If any subscriber, tower radio, or access switch connects a looped patch cord or redundant uplink between ports `ether3`–`ether10`, the bridge will forward broadcast frames infinitely.
   - **Consequence:** In a dual-switch-chip router like the RB4011, inter-switch loops will saturate the 2.5 Gbps CPU interconnects instantly, pegging CPU cores at 100%, terminating PPPoE sessions, and freezing all routing.
   - **Remediation:** Switch `protocol-mode` to `rstp` (Rapid Spanning Tree Protocol) with appropriate bridge root priorities.

2. **Cross-Switch Bridging Architecture:**
   - Ports `ether3`-`ether5` reside on Switch 1, while `ether6`-`ether10` reside on Switch 2.
   - All ports have Hardware Offloading enabled (`hw=yes`).
   - Hardware offloading functions intra-switch (within Switch 1 or Switch 2). Any Layer 2 forwarding between a device on `ether3` and a device on `ether7` traverses the CPU over the internal 2.5 Gbps SGMII buses. Because CPU utilization is currently 6%–11%, the CPU comfortably handles this load, but engineers must remain cognizant of this throughput ceiling.

3. **Disabled Security Features on Bridge:**
   - `dhcp-snooping=no`: Rogue DHCP servers connected to any bridge port can intercept subscriber credentials.
   - `vlan-filtering=no`: No 802.1Q hardware filtering is active. The bridge is entirely flat.
   - `igmp-snooping=no`: Multicast traffic is flooded as broadcast across all bridge ports.

---

## 5. Bridge Port Membership

```
Flags: I - INACTIVE; H - HW-OFFLOAD
 #   INTERFACE  BRIDGE        PRIORITY  PATH-COST  HORIZON  HW   PVID  FRAME-TYPES
 0 H ether3     Bridge-Local  0x80      10         none     yes  1     admit-all
 1 H ether4     Bridge-Local  0x80      10         none     yes  1     admit-all
 2 H ether5     Bridge-Local  0x80      10         none     yes  1     admit-all
 3 H ether6     Bridge-Local  0x80      10         none     yes  1     admit-all
 4 H ether7     Bridge-Local  0x80      10         none     yes  1     admit-all
 5IH ether8     Bridge-Local  0x80      10         none     yes  1     admit-all
 6 H ether9     Bridge-Local  0x80      10         none     yes  1     admit-all
 7IH ether10    Bridge-Local  0x80      10         none     yes  1     admit-all
```

- All 8 ports (`ether3` through `ether10`) are assigned to `Bridge-Local`.
- Horizon is set to `none` (ports can communicate with each other at Layer 2).
- PVID is default `1`.

---

## 6. Interface Lists Audit (`/interface list`)

Interface lists simplify firewall and service policies by grouping physical and logical interfaces.

### Configured Lists:
- **`WAN`**
- **`LAN`**

### List Membership Audit (`/interface list member`):
```
Flags: X - DISABLED, D - DYNAMIC
 #   LIST  INTERFACE         STATUS
 0 X WAN   pppoe-out1        Disabled
 1 X LAN   Bridge-Local      DISABLED (CRITICAL CONFIGURATION DEFECT)
 2   LAN   ether3            Static Member
 3   WAN   ether1-ISP        Static Member
 4 D LAN   back-to-home-vpn  Dynamic Member (Cloud VPN)
 5   WAN   mv-pppoe1         Static Member
 6   WAN   pppoe-out1        Static Member
 7   WAN   mv-pppoe2         Static Member
 8   WAN   pppoe-out2        Static Member
 9   WAN   mv-pppoe3         Static Member
10   WAN   pppoe-out3        Static Member
11   WAN   mv-pppoe4         Static Member
12   WAN   pppoe-out4        Static Member
13   WAN   mv-pppoe5         Static Member
14   WAN   pppoe-out5        Static Member
```

### Critical Finding on Interface Lists:
- **`Bridge-Local` Disabled in `LAN` List:** Rule 1 (`list=LAN interface=Bridge-Local`) is **DISABLED**!
- **Consequence:**
  - The primary local bridge interface `Bridge-Local` is **NOT recognized as a LAN member** by RouterOS.
  - Only `ether3` is statically in `LAN`. Traffic arriving on `Bridge-Local` via `ether4`, `ether5`, `ether6`, `ether7`, `ether9`, or subscriber PPPoE frames does NOT match `in-interface-list=LAN`.
  - While there are currently no firewall filter rules checking `in-interface-list=LAN`, this defect will cause immediate failure as soon as standard firewall filter rules or MAC Server management restrictions are enforced.
  - **Remediation:** Enable `Bridge-Local` in the `LAN` list and remove `ether3` (since `ether3` is a slave of `Bridge-Local` and slave ports must not be referenced directly in interface lists).
