# RUNBOOK 1b — Complete the eBGP Ring (add r4)

Continues from [RUNBOOK1a.md](RUNBOOK1a.md). Adds r4 (AS65004) to complete the 4-router eBGP ring.

## Topology

```
r1 (AS65001) ---eth1--- r2 (AS65002)
   |                       |
 eth2                    eth2
   |                       |
r4 (AS65004) ---eth1--- r3 (AS65003)
```

## Prerequisites

- Lab 1a completed (r1, r2, r3 running with eBGP string)
- r4 VM available in the Vagrantfile

---

## Step 1: Boot r4

```bash
cd bgp-labs/lab1
vagrant up r4
```

Verify:

```bash
vagrant status
```

All 4 should show `running (virtualbox)`.

---

## Step 2: Verify r4 interfaces

```bash
vagrant ssh r4 -c "ip -4 addr show enp0s8 && ip -4 addr show enp0s9"
```

Expected:

| Interface | IP |
|-----------|----|
| enp0s8 | 10.0.34.5/24 |
| enp0s9 | 10.0.14.5/24 |

---

## Step 3: Verify direct connectivity

```bash
vagrant ssh r4 -c "ping -c 2 10.0.34.4"   # r4 -> r3
vagrant ssh r4 -c "ping -c 2 10.0.14.2"   # r4 -> r1
```

Both should show 0% packet loss.

---

## Step 4: Configure r4

```bash
vagrant ssh r4
sudo vtysh
```

```
configure terminal

interface lo
 ip address 4.4.4.4/32
exit

router bgp 65004
 bgp router-id 4.4.4.4
 no bgp ebgp-requires-policy
 neighbor 10.0.14.2 remote-as 65001
 neighbor 10.0.34.4 remote-as 65003
 !
 address-family ipv4 unicast
  network 4.4.4.4/32
  network 10.0.14.0/24
  network 10.0.34.0/24
 exit-address-family
exit
exit
```

| Command | Purpose |
|---------|---------|
| `neighbor 10.0.14.2 remote-as 65001` | Peer with r1 (closes top edge of ring) |
| `neighbor 10.0.34.4 remote-as 65003` | Peer with r3 (closes bottom edge of ring) |
| `network 10.0.14.0/24` | Advertise r4–r1 link |
| `network 10.0.34.0/24` | Advertise r4–r3 link |

---

## Step 5: Observe partial ring — r4↔r1 up, r4↔r3 intentionally down

At this point, r4↔r1 establishes immediately (r1 already has `neighbor 10.0.14.5 remote-as 65004` from Lab 1a). But r4↔r3 stays **Active** because r3 has no neighbor statement for r4 yet.

```bash
vagrant ssh r4 -c "sudo vtysh -c 'show bgp summary'"
```

Expected:

```
Neighbor        V    AS   Up/Down  State/PfxRcd
10.0.14.2       4  65001  00:00:xx           5     ← Established
10.0.34.4       4  65003     never      Active     ← r3 not configured
```

### What r4 sees with only the r1 session

```bash
vagrant ssh r4 -c "sudo vtysh -c 'show bgp ipv4 unicast'"
```

r4 receives 5 prefixes from r1 — all routes flow through a single path via r1. There are no alternative paths because the r3 session is down. Every remote prefix has a single next-hop (10.0.14.2).

### Key observation: `network` statements and return-path reachability

Initially, without `network 10.0.14.0/24` and `network 10.0.34.0/24` on r4, pings from r4 to remote loopbacks (2.2.2.2, 3.3.3.3) failed — even though r4 had BGP routes to those destinations.

**Why:** r4 had the forward path, but remote routers lacked a return route to r4's source IP. The `network` command tells BGP to advertise an existing connected route to peers. Once r4 advertised its link subnets, r1 re-advertised them to r2 and r3, completing the return path.

> See [DECISIONS.md](../DECISIONS.md) — "network command and return-path reachability" for full rationale.

---

## Step 6: Complete the ring — add r4 as neighbor on r3

```bash
vagrant ssh r3
sudo vtysh
```

```
configure terminal
router bgp 65003
 neighbor 10.0.34.5 remote-as 65004
 address-family ipv4 unicast
  network 10.0.34.0/24
 exit-address-family
exit
exit
```

---

## Step 7: Verify all BGP sessions

```bash
vagrant ssh r1 -c "sudo vtysh -c 'show bgp summary'"
vagrant ssh r2 -c "sudo vtysh -c 'show bgp summary'"
vagrant ssh r3 -c "sudo vtysh -c 'show bgp summary'"
vagrant ssh r4 -c "sudo vtysh -c 'show bgp summary'"
```

Expected — all sessions Established:

| Session | State |
|---------|-------|
| r1 ↔ r2 | Established |
| r2 ↔ r3 | Established |
| r3 ↔ r4 | Established |
| r4 ↔ r1 | Established |

---

## Step 8: Verify BGP tables — routes vs paths

```bash
vagrant ssh r1 -c "sudo vtysh -c 'show bgp ipv4 unicast'"
vagrant ssh r2 -c "sudo vtysh -c 'show bgp ipv4 unicast'"
vagrant ssh r3 -c "sudo vtysh -c 'show bgp ipv4 unicast'"
vagrant ssh r4 -c "sudo vtysh -c 'show bgp ipv4 unicast'"
```

All routers see the same **8 routes** but different **path counts**:

| Router | Routes | Paths | Dual-path prefixes |
|--------|--------|-------|--------------------|
| r1 | 8 | 11 | 3 |
| r2 | 8 | 13 | 5 |
| r3 | 8 | 15 | 7 |
| r4 | 8 | 13 | 5 |

### Why are path counts different?

In a ring, each prefix can theoretically be reached two ways (clockwise and counterclockwise). But three BGP rules limit which alternatives each router actually sees:

1. **BGP only advertises its best path** — not all known paths
2. **A router never re-advertises a route back to the peer it learned it from**
3. **Tiebreaker (lowest neighbor IP)** — when two paths have equal AS path length, the lower neighbor IP wins best-path selection, which determines what gets re-advertised

r3 sees the most alternative paths (15) because its neighbors (r2, r4) learned most of their best paths from their *other* neighbor, not from r3, so they freely advertise those routes to r3.

r1 sees the fewest (11) because tiebreaker results (r1 has the lowest IPs: 10.0.12.2, 10.0.14.2) cause both r2 and r4 to learn best paths *from r1*, which they won't re-advertise back.

### Routes vs paths — what matters?

- **Routes** determine forwarding. Only the best path (`*>`) is installed in the routing table.
- **Alternative paths** sit idle until needed: link failure (instant failover), load balancing (`maximum-paths`), or policy decisions (route-maps).

> See [DECISIONS.md](../DECISIONS.md) — "Routes vs paths in a ring topology" for full analysis.

---

## Step 9: Full reachability matrix

### Loopback reachability

```bash
# From each router, ping all loopbacks
for r in r1 r2 r3 r4; do
  for ip in 1.1.1.1 2.2.2.2 3.3.3.3 4.4.4.4; do
    vagrant ssh $r -c "ping -c 1 -W 2 $ip" 2>/dev/null | grep -q '1 received' \
      && echo "$r -> $ip : OK" \
      || echo "$r -> $ip : FAIL"
  done
done
```

Expected (16/16 OK):

| From \ To | 1.1.1.1 | 2.2.2.2 | 3.3.3.3 | 4.4.4.4 |
|-----------|---------|---------|---------|---------|
| **r1** | OK | OK | OK | OK |
| **r2** | OK | OK | OK | OK |
| **r3** | OK | OK | OK | OK |
| **r4** | OK | OK | OK | OK |

### Link IP reachability

```bash
for r in r1 r2 r3 r4; do
  for ip in 10.0.12.2 10.0.12.3 10.0.23.3 10.0.23.4 10.0.34.4 10.0.34.5 10.0.14.2 10.0.14.5; do
    vagrant ssh $r -c "ping -c 1 -W 2 $ip" 2>/dev/null | grep -q '1 received' \
      && echo "$r -> $ip : OK" \
      || echo "$r -> $ip : FAIL"
  done
done
```

Expected (32/32 OK):

| From \ To | 10.0.12.2 | 10.0.12.3 | 10.0.23.3 | 10.0.23.4 | 10.0.34.4 | 10.0.34.5 | 10.0.14.2 | 10.0.14.5 |
|-----------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|
| **r1** | OK | OK | OK | OK | OK | OK | OK | OK |
| **r2** | OK | OK | OK | OK | OK | OK | OK | OK |
| **r3** | OK | OK | OK | OK | OK | OK | OK | OK |
| **r4** | OK | OK | OK | OK | OK | OK | OK | OK |

**48/48 pings successful. Lab 1b complete.**

---

## Final Router Configs

### r1 (AS65001)
```
interface lo
 ip address 1.1.1.1/32

router bgp 65001
 bgp router-id 1.1.1.1
 no bgp ebgp-requires-policy
 neighbor 10.0.12.3 remote-as 65002
 neighbor 10.0.14.5 remote-as 65004
 address-family ipv4 unicast
  network 1.1.1.1/32
  network 10.0.12.0/24
  network 10.0.14.0/24
```

### r2 (AS65002)
```
interface lo
 ip address 2.2.2.2/32

router bgp 65002
 bgp router-id 2.2.2.2
 no bgp ebgp-requires-policy
 neighbor 10.0.12.2 remote-as 65001
 neighbor 10.0.23.4 remote-as 65003
 address-family ipv4 unicast
  network 2.2.2.2/32
  network 10.0.12.0/24
  network 10.0.23.0/24
```

### r3 (AS65003)
```
interface lo
 ip address 3.3.3.3/32

router bgp 65003
 bgp router-id 3.3.3.3
 no bgp ebgp-requires-policy
 neighbor 10.0.23.3 remote-as 65002
 neighbor 10.0.34.5 remote-as 65004
 address-family ipv4 unicast
  network 3.3.3.3/32
  network 10.0.23.0/24
  network 10.0.34.0/24
```

### r4 (AS65004)
```
interface lo
 ip address 4.4.4.4/32

router bgp 65004
 bgp router-id 4.4.4.4
 no bgp ebgp-requires-policy
 neighbor 10.0.14.2 remote-as 65001
 neighbor 10.0.34.4 remote-as 65003
 address-family ipv4 unicast
  network 4.4.4.4/32
  network 10.0.14.0/24
  network 10.0.34.0/24
```

---

## Quick Reference

| Router | AS | Loopback | Peers | Networks Advertised |
|--------|----|----------|-------|-------------------|
| r1 | 65001 | 1.1.1.1 | r2 (10.0.12.3), r4 (10.0.14.5) | 1.1.1.1/32, 10.0.12.0/24, 10.0.14.0/24 |
| r2 | 65002 | 2.2.2.2 | r1 (10.0.12.2), r3 (10.0.23.4) | 2.2.2.2/32, 10.0.12.0/24, 10.0.23.0/24 |
| r3 | 65003 | 3.3.3.3 | r2 (10.0.23.3), r4 (10.0.34.5) | 3.3.3.3/32, 10.0.23.0/24, 10.0.34.0/24 |
| r4 | 65004 | 4.4.4.4 | r1 (10.0.14.2), r3 (10.0.34.4) | 4.4.4.4/32, 10.0.14.0/24, 10.0.34.0/24 |
