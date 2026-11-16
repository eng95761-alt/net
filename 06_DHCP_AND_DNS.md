# 06 — DHCP & DNS ARCHITECTURE AUDIT
**Device:** MikroTik RB4011iGS+  
**Subsystem:** DHCP Servers, DHCP Clients, Address Pools, DNS Resolver, and Cache  
**Audit Timestamp:** 2026-11-15T18:09:53  
**Status:** FULLY INSPECTED & AUDITED

---

## 1. DHCP Server Audit (`/ip dhcp-server`)

```
0  name="DHCP-Server" interface=Bridge-Local lease-time=30m
   address-pool=Pool-Local dynamic-lease-identifiers=client-mac,client-id
   add-dns-entries-suffix="lan" use-radius=no use-reconfigure=no
```

### Operational Parameters:
- **Binding Interface:** `Bridge-Local`.
- **Address Pool:** `Pool-Local` (`192.168.0.10` – `192.168.0.250`, yielding 241 assignable dynamic host addresses).
- **Lease Duration:** `30 minutes`. (A short lease time appropriate for high-turnover public or commercial client environments).
- **DNS Suffix Injection:** `add-dns-entries-suffix="lan"`. Automatically maps hostnames to local DNS table under `.lan`.

---

## 2. DHCP Network Parameters (`/ip dhcp-server network`)

```
0  address=192.168.0.0/16 gateway=192.168.0.1 dns-server=8.8.8.8,1.1.1.1
   wins-server="" ntp-server="" caps-manager="" dhcp-option=""
```

### Critical Finding [HIGH-04]: Subnet Mask Inconsistency
- **The Defect:** The DHCP network broadcasts subnet `192.168.0.0/16` (mask `255.255.0.0`) with default gateway `192.168.0.1`. However, the physical router interface `Bridge-Local` holds the address `192.168.0.1/24` (mask `255.255.255.0`).
- **Network Consequences:**
  - Connected clients believe their broadcast domain covers `192.168.0.1` to `192.168.255.254`.
  - When a client attempts to communicate with management hosts on `192.168.1.15` or `192.168.9.200`, it assumes they are on the same local wire and issues ARP requests directly instead of routing via `192.168.0.1`.
  - Because `Bridge-Local` is a flat bridge without proxy-ARP, ARP resolution fails for cross-subnet targets, resulting in communication blackouts.
- **Remediation:** Update DHCP network definition from `192.168.0.0/16` to `192.168.0.0/24`.

---

## 3. Active DHCP Leases (`/ip dhcp-server lease`)

```
Flags: D - DYNAMIC
 #   ADDRESS          MAC-ADDRESS        STATUS  EXPIRES-AFTER  LAST-SEEN  HOST-NAME
 0 D 192.168.0.249    08:55:31:24:1A:17  bound   27m46s         2m14s      Karbala Mall 3
 1 D 192.168.0.250    74:4D:28:2C:6A:E3  bound   27m36s         2m24s      Karbala Mall 111
```

- **Analysis:**
  - Dynamic leases are currently bound to commercial customer nodes (`Karbala Mall 3` and `Karbala Mall 111`).
  - Both devices are active MikroTik routers acting as downstream CPEs (as evidenced by their MAC prefixes and MNDP records).
  - No static reservations exist (`use-radius=no`). All lease management is dynamic.

---

## 4. DHCP Client Audit (`/ip dhcp-client`)

```
Flags: X - DISABLED
 #   INTERFACE   ADD-DEFAULT-ROUTE  DISTANCE  USE-PEER-DNS  USE-PEER-NTP  STATUS  ADDRESS           GATEWAY
 0 X ether1-ISP  yes                1         yes           yes           stopped
 1   ether1-ISP  yes                1         no            yes           bound   192.168.4.238/24  192.168.4.1
```

- **Client 1 (`client1`):** Active on `ether1-ISP`. Obtains IP `192.168.4.238/24` from upstream modem/gateway (`192.168.4.1`).
- **Default Route:** `add-default-route=yes` with `distance=1`.
- **Peer DNS:** `use-peer-dns=no`. Correctly disabled so that upstream ISP modem DNS servers do not overwrite the router's configured static resolvers.
- **Client 0 (`ether1-ISP`):** Disabled duplicate client. Recommend removal during maintenance cleanup.

---

## 5. DNS Server & Resolver Audit (`/ip dns`)

```
                      servers: 8.8.8.8, 8.8.4.4
              dynamic-servers: 8.8.8.8, 8.8.4.4
               use-doh-server: ""
              verify-doh-cert: no
        allow-remote-requests: yes
          max-udp-packet-size: 4096
         query-server-timeout: 2s
          query-total-timeout: 10s
       max-concurrent-queries: 100
  max-concurrent-tcp-sessions: 20
                   cache-size: 2048 KiB
                cache-max-ttl: 1w
                   cache-used: 637 KiB
```

---

## 6. Critical Security Vulnerability: Open Recursive DNS Resolver [CRIT-02]

### Vulnerability Mechanics:
1. **The Exposure:** `allow-remote-requests: yes` configures RouterOS to operate as a full caching recursive DNS resolver listening on UDP and TCP port 53.
2. **Missing Ingress Controls:** Because there are **zero firewall filter rules on the input chain**, the DNS resolver responds to queries arriving from **ANY interface**, including:
   - Upstream WAN interface (`192.168.4.238`).
   - PPPoE WAN tunnels (`100.88.x.x`).
   - External Tower network (`10.235.51.4`).
   - Public WireGuard endpoints.
3. **Exploitation Vectors:**
   - **DNS Amplification / Reflection Attacks:** Attackers spoof a victim's IP and send small DNS requests with EDNS0 (max packet size 4096) to the router. The router generates large responses (amplification factor of 20x–50x), reflecting volumetric DDoS traffic onto the victim.
   - **DNS Cache Poisoning:** Attackers flood fraudulent DNS responses, injecting malicious records into the 2048 KiB cache and redirecting subscribers to phishing portals.
   - **CPU & Conntrack Exhaustion:** External query flooding exhausts the `max-concurrent-queries: 100` ceiling, causing internal subscriber DNS queries to time out.

### DNS Interception in NAT:
In `/ip firewall nat`, rules 5 & 6 forcefully redirect all outgoing client DNS traffic to the local resolver:
```
chain=dstnat action=redirect to-ports=53 protocol=udp dst-port=53
chain=dstnat action=redirect to-ports=53 protocol=tcp dst-port=53
```
While this ensures subscribers utilize cached entries (accelerating web browsing), it intensifies the necessity of securing the resolver with input firewall filter rules.

### Static DNS & DoH Audit:
- **Static Records (`/ip dns static`):** Completely empty (0 records).
- **DNS over HTTPS (DoH):** Disabled. Queries to upstream resolvers (`8.8.8.8`, `8.8.4.4`) are transmitted in cleartext UDP/53, vulnerable to upstream ISP interception, eavesdropping, and spoofing.
