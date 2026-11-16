# 04 — ROUTING & WAN ARCHITECTURE AUDIT
**Device:** MikroTik RB4011iGS+  
**Subsystem:** WAN Connectivity, Multi-WAN, Policy-Based Routing (PBR), and Routing Tables  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Upstream WAN Architecture

The router incorporates a hybrid Multi-WAN topology combining a local ISP modem connection, virtualized PPPoE tunnels over MACVLAN, and an external routed tower gateway.

```
                                  +-----------------------+
                                  |   UPSTREAM ISP / ONT  |
                                  |   192.168.4.1/24      |
                                  +-----------------------+
                                              |
                                     (ether1-ISP Physical)
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
         [DHCP Client: client1]                             [5x MACVLAN Sub-Interfaces]
         IP: 192.168.4.238/24                               (mv-pppoe1 to mv-pppoe5)
         Default Gateway: 192.168.4.1                                   |
         Role: Management & Cloud Access                                |
                                            +---------------------------+---------------------------+
                                            |                           |                           |
                                      [pppoe-out1]                [pppoe-out2]                [pppoe-out3]
                                     100.88.155.125              100.88.132.11               100.88.87.20
                                      Status: RUNNING             Status: RUNNING             Status: RUNNING
                                            |                           |                           |
                                      [pppoe-out4] (DISABLED)     [pppoe-out5] (DISABLED)   [Tower: ether2]
                                                                                            10.235.51.4/24 -> 10.235.51.1
```

---

## 2. WAN Connection Details

| Interface | Type | IP Address / Netmask | Gateway | Metric / Distance | Status | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ether1-ISP`** | Physical / DHCP | `192.168.4.238/24` | `192.168.4.1` | Distance 1 (DHCP) | **Bound / Running** | Local modem link, BTH VPN, Admin access |
| **`pppoe-out1`** | PPPoE Client | `100.88.155.125/32` | `100.93.0.7` | Distance 10 (Static) | **Connected / Running**| WAN Line 1 (PCC Split 0) |
| **`pppoe-out2`** | PPPoE Client | `100.88.132.11/32` | `100.93.0.7` | Distance 11 (Static) | **Connected / Running**| WAN Line 2 (PCC Split 1) |
| **`pppoe-out3`** | PPPoE Client | `100.88.87.20/32` | `100.93.0.7` | Distance 12 (Static) | **Connected / Running**| WAN Line 3 (PCC Split 2) |
| **`pppoe-out4`** | PPPoE Client | None (Disabled) | Unresolved | Distance 13 (Static) | **Disabled / Inactive**| Planned Line 4 |
| **`pppoe-out5`** | PPPoE Client | None (Disabled) | Unresolved | Distance 14 (Static) | **Disabled / Inactive**| Planned Line 5 |
| **`ether2`** | Physical / Static | `10.235.51.4/24` | `10.235.51.1` | Distance 1 (PBR) | **Connected / Running**| Tower / IXP Distribution (`Via-Quicknet `)|

---

## 3. Routing Tables Inventory (`/routing table`)

RouterOS v7 replaces legacy routing marks with independent Forwarding Information Base (FIB) routing tables:

```
Flags: D - DYNAMIC
 #   NAME           FIB   STATUS
 0 D main           yes   Active System Routing Table
 1   Via-Quicknet   yes   Active (Routed to 10.235.51.1 via ether2) [Trailing space in name]
 2   Via-Starlink   yes   Active (Routed to 192.168.4.1 via ether1-ISP)
 3   to_pppoe1      yes   Active (Routed to pppoe-out1)
 4   to_pppoe2      yes   Active (Routed to pppoe-out2)
 5   to_pppoe3      yes   Active (Routed to pppoe-out3)
 6   to_pppoe4      yes   Inactive (No active gateway)
 7   to_pppoe5      yes   Inactive (No active gateway)
```

- **Naming Glitch:** Table `Via-Quicknet ` contains a **trailing space** character in its name string (`"Via-Quicknet "`). This syntax quirk requires exact string matching in mangle rules and scripts; any typographical omission of the space causes silent PBR failure.

---

## 4. IP Routes Audit (`/ip route`)

The routing table contains **524 lines of dynamic and static routes**, including connected subscriber routes.

### Default Routes Summary:
```
Flags: D - DYNAMIC; I - INACTIVE, A - ACTIVE; c - CONNECT, s - STATIC, d - DHCP
 #     DST-ADDRESS    ROUTING-TABLE   GATEWAY        DISTANCE  SCOPE  TARGET-SCOPE  STATUS
 0  As 0.0.0.0/0      to_pppoe1       pppoe-out1     1         30     10            Active Static
 1  As 0.0.0.0/0      to_pppoe2       pppoe-out2     1         30     10            Active Static
 2  As 0.0.0.0/0      to_pppoe3       pppoe-out3     1         30     10            Active Static
 3  Is 0.0.0.0/0      to_pppoe4       pppoe-out4     1         30     10            Inactive Static
 4  Is 0.0.0.0/0      to_pppoe5       pppoe-out5     1         30     10            Inactive Static
 5  As 0.0.0.0/0      Via-Quicknet    10.235.51.1    1         30     10            Active Static
 6  As 0.0.0.0/0      Via-Starlink    192.168.4.1    1         30     10            Active Static
 7  As 0.0.0.0/0      main            pppoe-out1     10        30     10            Active Failover
 8   s 0.0.0.0/0      main            pppoe-out2     11        30     10            Backup Failover
 9   s 0.0.0.0/0      main            pppoe-out3     12        30     10            Backup Failover
10  Is 0.0.0.0/0      main            pppoe-out4     13        30     10            Inactive Backup
11  Is 0.0.0.0/0      main            pppoe-out5     14        30     10            Inactive Backup
```

---

## 5. Critical Flaw in PCC Multi-WAN Load Balancer [CRIT-03]

### Technical Decomposition of the Math Bug:
In `/ip firewall mangle`, the administrator implemented a 5-way Per Connection Classifier:
```
16  chain=prerouting action=mark-connection new-connection-mark=pppoe1_conn
    per-connection-classifier=both-addresses:5/0

17  chain=prerouting action=mark-connection new-connection-mark=pppoe2_conn
    per-connection-classifier=both-addresses:5/1

18  chain=prerouting action=mark-connection new-connection-mark=pppoe3_conn
    per-connection-classifier=both-addresses:5/2

19 X chain=prerouting action=mark-connection new-connection-mark=pppoe4_conn
    per-connection-classifier=both-addresses:5/3  [DISABLED]

20 X chain=prerouting action=mark-connection new-connection-mark=pppoe5_conn
    per-connection-classifier=both-addresses:5/4  [DISABLED]
```

### The Mechanism of Traffic Spillover:
1. When a client initiates a connection, the PCC algorithm computes a 32-bit hash of `(src-ip, dst-ip)` and applies modulo 5 (`hash % 5`), producing a remainder from 0 to 4:
   - **Remainder 0 (20% of traffic):** Matches Rule 16 -> Marked `pppoe1_conn` -> Routed via `pppoe-out1`.
   - **Remainder 1 (20% of traffic):** Matches Rule 17 -> Marked `pppoe2_conn` -> Routed via `pppoe-out2`.
   - **Remainder 2 (20% of traffic):** Matches Rule 18 -> Marked `pppoe3_conn` -> Routed via `pppoe-out3`.
   - **Remainder 3 (20% of traffic):** Hits Rule 19, which is **DISABLED**. Receives **NO connection mark**.
   - **Remainder 4 (20% of traffic):** Hits Rule 20, which is **DISABLED**. Receives **NO connection mark**.

2. **Where does the unmarked 40% go?**
   Because packets with remainder 3 and 4 have no connection mark, they bypass the routing-mark rules (Rules 21–25). They enter routing evaluation without any FIB table mark and are processed exclusively by the **`main` routing table**.
   In `main`, the lowest distance default route is:
   `dst-address=0.0.0.0/0 gateway=pppoe-out1 distance=10`
   Therefore, **all 40% of the unmarked connections are dumped directly onto `pppoe-out1`!**

### Traffic Distribution Impact:
| WAN Interface | Expected Share (if properly balanced) | Actual Current Traffic Share | Deviation |
| :--- | :--- | :--- | :--- |
| **`pppoe-out1`** | **33.3%** | **60.0%** (20% PCC + 40% Unmarked Spillover) | **+26.7% (Overloaded)** |
| **`pppoe-out2`** | **33.3%** | **20.0%** (20% PCC) | **-13.3% (Underutilized)** |
| **`pppoe-out3`** | **33.3%** | **20.0%** (20% PCC) | **-13.3% (Underutilized)** |

This explains why `pppoe-out1` experiences disproportionately higher latency and bufferbloat compared to `pppoe-out2` and `pppoe-out3`.

### Remediation:
To balance 3 lines equally, the classifier must be reconfigured to modulo 3:
- Line 1: `both-addresses:3/0`
- Line 2: `both-addresses:3/1`
- Line 3: `both-addresses:3/2`

---

## 6. Gateway Monitoring & Failover Deficiencies

- **No Active Gateway Probing (`check-gateway=none`):**
  None of the default routes in `main` or the PBR tables utilize `check-gateway=ping` or recursive routing via virtual scope hops.
- **Failover Limitations:**
  - If the physical Ethernet carrier remains up but upstream ISP routing stalls behind the PPPoE BRAS, RouterOS will continue directing traffic into the dead tunnel because `check-gateway` is absent.
  - Dedicated PBR tables (`to_pppoe1`, `to_pppoe2`, `to_pppoe3`) lack secondary fallback default routes. If `pppoe-out1` terminates, packets marked with `to_pppoe1` will be dropped with "No route to host" rather than falling back to surviving lines.
