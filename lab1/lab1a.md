# Lab 1A — Milestone 1: eBGP String Topology (r1 -- r2 -- r3)

## Topology

```
  r1 (AS65001) ---10.0.12.0/24--- r2 (AS65002) ---10.0.23.0/24--- r3 (AS65003)
  lo: 1.1.1.1                     lo: 2.2.2.2                     lo: 3.3.3.3
  .2 on link_r1_r2                .3 on link_r1_r2                .4 on link_r2_r3
  .2 on link_r1_r4                .3 on link_r2_r3                .4 on link_r3_r4
```

r1 and r3 are **not** physically connected. They can only reach each other through r2.
r4 exists in the Vagrantfile but has no BGP configuration yet.

## Infrastructure (see RUNBOOK.md)

- **Platform:** VirtualBox + Vagrant
- **OS:** Ubuntu 22.04 (ubuntu/jammy64)
- **Routing:** FRRouting 10.6.0 (provisioned via shell script)
- **Resources:** 512MB RAM, 1 CPU per router

### Interface Mapping (all routers)

| Interface | Purpose |
|-----------|---------|
| enp0s3 (10.0.2.15/24) | Vagrant NAT management — identical on all VMs, isolated per VM |
| enp0s8 | First private network link |
| enp0s9 | Second private network link |

## Router Configurations

### r1 (AS 65001)
```
interface lo
 ip address 1.1.1.1/32
!
router bgp 65001
 bgp router-id 1.1.1.1
 no bgp ebgp-requires-policy
 neighbor 10.0.12.3 remote-as 65002
 neighbor 10.0.14.5 remote-as 65004
 !
 address-family ipv4 unicast
  network 1.1.1.1/32
  network 10.0.12.0/24
  network 10.0.14.0/24
 exit-address-family
```

### r2 (AS 65002)
```
interface lo
 ip address 2.2.2.2/32
!
router bgp 65002
 bgp router-id 2.2.2.2
 no bgp ebgp-requires-policy
 neighbor 10.0.12.2 remote-as 65001
 neighbor 10.0.23.4 remote-as 65003
 !
 address-family ipv4 unicast
  network 10.0.0.0/8
  network 10.0.23.4/32
 exit-address-family
```

**Note:** r2's network statements are incorrect (see Lessons Learned #4).

### r3 (AS 65003)
```
interface lo
 ip address 3.3.3.3/32
!
router bgp 65003
 bgp router-id 3.3.3.3
 no bgp ebgp-requires-policy
 neighbor 10.0.23.3 remote-as 65002
 !
 address-family ipv4 unicast
  network 3.3.3.3/32
  network 10.0.23.0/24
 exit-address-family
```

### r4 (AS 65004) — Not yet configured
r4 VM is running but has no BGP configuration. r1's neighbor 10.0.14.5 shows `Active (never)`.

## BGP Session Status

| From | To | Neighbor IP | State | Prefixes Received |
|------|----|-------------|-------|-------------------|
| r1 | r2 | 10.0.12.3 | **Established** (4h+) | 2 |
| r2 | r1 | 10.0.12.2 | **Established** (4h+) | 3 |
| r2 | r3 | 10.0.23.4 | **Established** (3h+) | 2 |
| r3 | r2 | 10.0.23.3 | **Established** (3h+) | 3 |
| r1 | r4 | 10.0.14.5 | **Active (never)** | 0 |

## The Milestone: r1 can ping r3

r1 has no direct link to r3. Before BGP, pinging `10.0.23.4` from r1 failed (100% packet loss).
After advertising networks in BGP, r1 learned routes via r2:

```
r1# show ip route (BGP-learned routes only)
B>* 3.3.3.3/32    [20/0] via 10.0.12.3, enp0s8   ← r3's loopback, via r2
B>* 10.0.23.0/24  [20/0] via 10.0.12.3, enp0s8   ← r2-r3 link, via r2
```

```
r1# ping 10.0.23.4
64 bytes from 10.0.23.4: icmp_seq=1 ttl=63 time=0.218 ms   ← TTL=63 (1 hop through r2)

r3# ping 10.0.12.2
64 bytes from 10.0.12.2: icmp_seq=1 ttl=63 time=0.261 ms   ← return path also works
```

**TTL=63** confirms the packet traversed 1 intermediate hop (r2). Default TTL is 64, minus 1 per hop.

## r1's BGP Table

```
     Network          Next Hop        Metric Weight Path
 *>  1.1.1.1/32       0.0.0.0              0  32768 i            ← local
 *>  3.3.3.3/32       10.0.12.3                   0 65002 65003 i ← learned: r2 → r3
 *>  10.0.12.0/24     0.0.0.0              0  32768 i            ← local
 *>  10.0.14.0/24     0.0.0.0              0  32768 i            ← local
 *>  10.0.23.0/24     10.0.12.3                   0 65002 65003 i ← learned: r2 → r3
```

**Reading the AS path:** `65002 65003` means this route originated in AS65003, passed through AS65002, then arrived at r1 (AS65001). The path shows the route traveled r3 → r2 → r1.

## Lessons Learned

### 1. Why loopback as router-id (not link IP)
A link IP is tied to a physical interface. If that interface goes down, the router-id disappears and BGP resets **all** sessions — even sessions on healthy interfaces. A loopback never goes down unless the entire router dies. See DECISIONS.md for full analysis.

### 2. Why neighbor uses link IP (not loopback)
The `neighbor` address must be **directly reachable** via a connected interface. r2 can reach r1 at `10.0.12.2` because they share the `10.0.12.0/24` link. r2 cannot reach `1.1.1.1` because there is no route to it (until BGP or OSPF advertises it). Loopback-based peering is an iBGP pattern that requires an underlying IGP — not needed for eBGP.

### 3. Why `network` statements are required
Establishing a BGP session (`neighbor` command) only opens the TCP connection. No routes are exchanged until you tell BGP **what to advertise** using `network` statements under `address-family ipv4 unicast`. Without them, `PfxRcd = 0` and `PfxSnt = 0` — sessions are up but useless.

### 4. r2's network statements need cleanup
r2 currently advertises `network 10.0.0.0/8` (the entire 10.x.x.x range) and `network 10.0.23.4/32` (a host route). These should be corrected to match its actual connected subnets:
- `network 2.2.2.2/32` (loopback)
- `network 10.0.12.0/24` (link to r1)
- `network 10.0.23.0/24` (link to r3)

### 5. `no bgp ebgp-requires-policy` is required in FRR
By default, FRR blocks all eBGP route exchange unless route-maps are defined. This safety feature prevents accidental route leaks in production. For lab purposes, disabling it allows routes to flow freely.

### 6. Connected routes vs BGP routes
Before BGP: each router only knows its directly connected subnets (C routes). A router cannot ping a subnet it has no route to — the packet falls to the default NAT gateway and is lost. After BGP: learned routes (B routes) fill the gaps, enabling end-to-end reachability.

## Next Steps
- [ ] Fix r2 network statements
- [ ] Configure r4 (AS65004) with BGP
- [ ] Complete the ring: r3 ↔ r4 and r4 ↔ r1 peerings
- [ ] Verify full ring reachability (all routers can ping all others)
