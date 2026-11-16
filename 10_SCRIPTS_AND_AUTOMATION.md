# 10 — SCRIPTS & AUTOMATION AUDIT
**Device:** MikroTik RB4011iGS+  
**Subsystem:** Scripts, Schedulers, Netwatch, and Operational Automation  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. System Scripts Inventory (`/system script`)

```
/system script print detail
[Empty — 0 Scripts Configured]
```

- **Audit Findings:** The router contains **zero custom scripts**.
- No maintenance scripts, configuration export automations, dynamic DNS updates, or failover logic scripts are deployed.

---

## 2. System Schedulers Inventory (`/system scheduler`)

```
/system scheduler print detail
[Empty — 0 Schedulers Configured]
```

- **Audit Findings:** The router contains **zero scheduled tasks**.
- There are no cron-like tasks running periodically on the device.

---

## 3. Netwatch Link Monitoring (`/tool netwatch`)

```
/tool netwatch print detail
[Empty — 0 Netwatch Probes Configured]
```

- **Audit Findings:** Netwatch is completely unconfigured.
- The router does not perform active ICMP probing against external milestones (such as `8.8.8.8` or upstream ISP gateways) to detect stealth line degradation or silent packet loss.

---

## 4. Automation & Operational Resilience Assessment

### A. Total Absence of Automated Backup Procedures:
- **Operational Risk [HIGH]:**
  - There is no script or scheduler executing periodic configuration backups.
  - If the router experiences NAND corruption, power-surge hardware failure, or an erroneous configuration change, the administrator will be forced to reconstruct the entire Multi-WAN, PCC, User Manager, and PCQ subscriber architecture from scratch.
- **Recommended Architecture:**
  Deploy an automated weekly script that creates both a binary `.backup` (for full cryptographic state) and a redacted `.rsc` export (for human-readable recovery), transmitting them offsite via SFTP, email, or cloud storage.

### B. Lack of Intelligent Multi-WAN Failover Automation:
- **Current Failover Mechanism:**
  - Failover is handled strictly by static distance increments in the `main` routing table:
    - `pppoe-out1` (distance 10)
    - `pppoe-out2` (distance 11)
    - `pppoe-out3` (distance 12)
- **Failure Mode Analysis:**
  - If `pppoe-out1` loses internet routing upstream at the ISP core while the PPPoE carrier session remains established (LCP keepalives responding), the static default route remains **ACTIVE** in RouterOS.
  - 60% of all network traffic continues to be forwarded into the black hole.
  - Because Netwatch and script automation are absent, the router cannot dynamically withdraw the dead default route.
- **Recommended Architecture:**
  Implement RouterOS v7 Recursive Routing (virtual target-scope hops via Google DNS `8.8.8.8` and Cloudflare `1.1.1.1` with `check-gateway=ping`) or Netwatch-driven script triggers to automatically disable faulty routes upon ping failure.
