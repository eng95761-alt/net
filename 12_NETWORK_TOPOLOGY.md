# 12 — NETWORK TOPOLOGY & TRAFFIC-FLOW DIAGRAMS
**Device:** MikroTik RB4011iGS+  
**Audit Discipline:** Network Architecture, Physical & Logical Topology Mapping  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. Physical Hardware & Link Topology

```mermaid
flowchart TD
    subgraph WAN_Side["WAN & Upstream Ingress"]
        ISP_MODEM["Upstream ISP Modem / ONT<br/>LAN: 192.168.4.1/24"]
        TOWER_NET["Tower / IXP Network<br/>Gateway: 10.235.51.1"]
    end

    subgraph RB4011["MikroTik RB4011iGS+ (Identity: Home)"]
        direction TB
        subgraph Ports_Switch1["Switch 1 (Realtek RTL8367)"]
            E1["ether1-ISP (1 Gbps)"]
            E2["ether2 (1 Gbps)"]
            E3["ether3 (1 Gbps)"]
            E4["ether4 (1 Gbps)"]
            E5["ether5 (1 Gbps)"]
        end

        subgraph Ports_Switch2["Switch 2 (Realtek RTL8367)"]
            E6["ether6 (1 Gbps)"]
            E7["ether7 (1 Gbps)"]
            E8["ether8 (No Link)"]
            E9["ether9 (1 Gbps)"]
            E10["ether10 (No Link)"]
        end

        SFP["sfp-sfpplus1 (10G SFP+ - Disconnected)"]
        CPU["Annapurna AL21400 4-Core ARM CPU"]
    end

    subgraph LAN_Side["Distribution & Subscriber Nodes"]
        SW_CORE["Access Switch / APs (10.112.152.0/24)"]
        TOWER_RADIO["Wireless Links (10.191.250.0/24)"]
        RB3011["MikroTik RB3011 Node (Karbala Mall 3)"]
        LAN_CLIENTS["Local LAN Nodes (192.168.1.0/24 & 192.168.0.0/24)"]
        MGMT_PC["Admin Workstation (192.168.4.43 / 10.10.10.10)"]
    end

    ISP_MODEM === E1
    TOWER_NET === E2
    E3 === SW_CORE
    E4 === TOWER_RADIO
    E5 === RB3011
    E7 === LAN_CLIENTS
    E9 === MGMT_PC

    Ports_Switch1 -->|"2.5 Gbps SGMII"| CPU
    Ports_Switch2 -->|"2.5 Gbps SGMII"| CPU
    SFP -.->|"Direct 10G MAC"| CPU
```

---

## 2. Logical Architecture & Subsystem Diagram

```mermaid
flowchart TD
    subgraph Upstream["Upstream Providers & Clouds"]
        ISP["ISP Carrier-Grade NAT (100.88.x.x)"]
        BTH_RELAY["MikroTik EUR1 Cloud Relay (78.28.208.99)"]
    end

    subgraph RB4011_Logical["RB4011 Layer 2 & 3 Logical Plane"]
        direction TB
        E1_PHY["Physical Port: ether1-ISP"]
        DHCP_CL["DHCP Client: 192.168.4.238"]
        BTH_TUN["WireGuard Interface: back-to-home-vpn (192.168.216.1)"]

        subgraph MACVLAN_Trunk["MACVLAN Virtual Interfaces"]
            MV1["mv-pppoe1"]
            MV2["mv-pppoe2"]
            MV3["mv-pppoe3"]
        end

        subgraph PPPoE_Clients["Active PPPoE Client Sessions"]
            P1["pppoe-out1 (100.88.155.125)"]
            P2["pppoe-out2 (100.88.132.11)"]
            P3["pppoe-out3 (100.88.87.20)"]
        end

        subgraph Core_Routing["Core Routing & Classification"]
            PCC["PCC Classifier Mangle Engine (5-Way Defect)"]
            FIB_T1["Routing Table: to_pppoe1"]
            FIB_T2["Routing Table: to_pppoe2"]
            FIB_T3["Routing Table: to_pppoe3"]
            FIB_MAIN["Routing Table: main (Failover Default)"]
            NAT["NAT Masquerade Engine"]
        end

        subgraph Core_Switching["Layer 2 Core"]
            BR["Bridge-Local (STP=none)"]
            PPPOE_SRV["PPPoE Server (Server-PPOE)"]
            UM["User Manager v5 / RADIUS Database"]
            QUEUES["Simple Queues (PCQ Subnet Tiers 2M - 30M)"]
        end
    end

    subgraph Clients["Connected Endpoints"]
        SUB_SESSIONS["18 Active PPPoE Subscriber Tunnels"]
        DHCP_CLIENTS["DHCP Hosts (Karbala Mall Nodes)"]
    end

    ISP === E1_PHY
    E1_PHY --> DHCP_CL
    DHCP_CL --> BTH_TUN
    BTH_TUN <===> BTH_RELAY

    E1_PHY --> MV1 --> P1
    E1_PHY --> MV2 --> P2
    E1_PHY --> MV3 --> P3

    P1 & P2 & P3 --> Core_Routing
    PCC --> FIB_T1 & FIB_T2 & FIB_T3 & FIB_MAIN
    Core_Routing <--> NAT <--> BR

    BR <--> PPPOE_SRV
    PPPOE_SRV <--> UM
    PPPOE_SRV <--> QUEUES
    PPPOE_SRV === SUB_SESSIONS
    BR === DHCP_CLIENTS
```

---

## 3. End-to-End Traffic-Flow Diagram

The diagram below charts the exact transit lifecycle of subscriber data packets from client generation to Internet transit:

```mermaid
flowchart LR
    C["Subscriber Client"] -->|"PPPoE Ingress"| B["Bridge-Local"]
    B -->|"L2 Decapsulation"| D["PPPoE Server Session"]
    D -->|"Rate Limiting"| Q["Simple Queue / PCQ"]
    Q -->|"TTL / MSS Clamping"| M["Mangle Prerouting"]
    M -->|"PCC Hash Evaluation"| R["Routing Table Selection"]
    R -->|"to_pppoe1 / 2 / 3"| N["NAT Masquerade"]
    N -->|"PPPoE Encapsulation"| P["mv-pppoe1 / 2 / 3"]
    P -->|"Physical Trunk"| E["ether1-ISP"]
    E -->|"Fiber / Ethernet"| M_ISP["Upstream ISP Modem"]
    M_ISP -->|"CGNAT Gateway"| I["GLOBAL INTERNET"]
```

---

## 4. Multi-WAN Ingress/Egress Asymmetry Diagram

Visual demonstration of the current traffic distribution imbalance caused by [CRIT-03]:

```mermaid
pie title Current Traffic Share Across Active PPPoE WAN Lines
    "pppoe-out1 (60% - Overloaded)" : 60
    "pppoe-out2 (20% - Underutilized)" : 20
    "pppoe-out3 (20% - Underutilized)" : 20
```

- **Line 1 (`pppoe-out1`):** Absorbs PCC Hash Remainder 0 (20%) + Unmarked Hash Remainders 3 & 4 (40%) = **60% Aggregate Traffic**.
- **Line 2 (`pppoe-out2`):** Absorbs PCC Hash Remainder 1 = **20% Aggregate Traffic**.
- **Line 3 (`pppoe-out3`):** Absorbs PCC Hash Remainder 2 = **20% Aggregate Traffic**.
