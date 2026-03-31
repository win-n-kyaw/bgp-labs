# Decisions Log

## 2026-03-29: Ubuntu + FRR over VyOS for router VMs

### Decision
Use `ubuntu/jammy64` with FRRouting (FRR) provisioned via shell script instead of VyOS NOS images.

### Context
Evaluated VyOS as the primary NOS for the BGP lab. VyOS provides a professional router CLI (similar to Juniper/Cisco) and uses FRR under the hood.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **VyOS (`vyos/current`)** | NOS CLI, integrated config management | Guest OS detection fails, `configure_networks` capability missing, `vagrant-hostsupdater` conflicts, synced folders broken |
| **VyOS + `vagrant-vyos` plugin** | Adds guest capabilities | Extra plugin dependency, community-maintained, uncertain longevity |
| **Cumulus VX** | Real NOS, official Vagrant box | Password expiration breaks SSH every ~6 months, NVIDIA killed community support |
| **Ubuntu + FRR** (chosen) | Full Vagrant support, no guest detection issues, lighter (512MB), FRR is same engine VyOS uses | No NOS CLI — must use `vtysh` or Linux shell directly |

### Why Ubuntu + FRR
1. **Vagrant compatibility** — `ubuntu/jammy64` has full guest support (hostname, networking, synced folders). Zero plugin workarounds needed.
2. **Same routing engine** — FRR is what VyOS uses internally. BGP/OSPF config via `vtysh` is nearly identical.
3. **Lower resources** — 512MB per VM vs 1024MB for VyOS. 4-router lab needs only ~2GB.
4. **Reliability** — `vagrant up` just works. No capability errors, no auth failures.

### Trade-off Accepted
We lose the unified NOS CLI experience (VyOS `configure`/`commit`/`save`). Instead, routing config is done via `sudo vtysh` which uses the same FRR commands but without VyOS's configuration backend. This is acceptable for a BGP learning lab.

---

## 2026-03-30: Loopback as BGP Router-ID (not link IPs)

### Decision
Use dedicated loopback addresses as BGP router-id on every router, not link interface IPs.

### Assignment

| Router | Loopback | AS | router-id |
|--------|----------|----|-----------|
| r1 | 1.1.1.1/32 | 65001 | 1.1.1.1 |
| r2 | 2.2.2.2/32 | 65002 | 2.2.2.2 |
| r3 | 3.3.3.3/32 | 65003 | 3.3.3.3 |
| r4 | 4.4.4.4/32 | 65004 | 4.4.4.4 |

### Problem Statement
A BGP router-id must be a stable, unique IP that identifies the router. If a link IP (e.g. `10.0.12.2`) is used as router-id and that physical interface goes down:
- The router-id becomes unreachable
- The BGP process resets
- **All** BGP sessions drop — including sessions on other interfaces that are still healthy
- One cable failure cascades into a full routing meltdown

### Why Loopback Solves This
A loopback (`lo`) is a virtual interface — it has no physical link, so it **never goes down** unless the entire router dies. Using it as router-id means:
- A single link failure only kills the BGP session on that link
- All other BGP sessions remain established
- Failure is isolated, not cascaded

### Example (r1 in our lab)
```
Link r1<->r2 fails (enp0s8 goes down):

  router-id = 10.0.12.2 (link IP):
    → router-id lost → BGP restarts
    → r1<->r2 drops (expected)
    → r1<->r4 ALSO drops (collateral damage)

  router-id = 1.1.1.1 (loopback):
    → r1<->r2 drops (expected)
    → r1<->r4 stays UP (router-id unaffected)
```

### Key Takeaway
**Never use a link IP as router-id in production.** Loopback = stability. This is standard practice across Cisco, Juniper, and FRR.

---

## 2026-03-31: `network` command and return-path reachability

### Decision
Always advertise a router's connected link subnets via `network` statements in BGP, not just loopbacks.

### Problem Statement
After configuring r4 with eBGP peering to r1, r4 received routes to 2.2.2.2/32 and 3.3.3.3/32 (via r1). But pings to those loopbacks failed — 100% packet loss.

r4 had the **forward path** (BGP route to destination), but remote routers lacked a **return path** to r4's source IP.

### What happened

```
r4 pings 2.2.2.2:
  r4 (src 10.0.14.5) → r1 → r2 (receives echo request)
  r2 replies to 10.0.14.5 → r2 has route to 10.0.14.0/24 via r1 → reply reaches r4  ✓

r4 pings 3.3.3.3:
  r4 (src 10.0.14.5) → r1 → r2 → r3 (receives echo request)
  r3 replies to 10.0.14.5 → r3 needs route to 10.0.14.0/24
```

The initial failure was a combination of BGP convergence timing (the r4↔r1 session was only 20 seconds old) and incomplete route advertisement. Once r4 added `network 10.0.14.0/24` and `network 10.0.34.0/24`, those prefixes propagated through the ring via r1 → r2 → r3, ensuring every router had explicit return paths to r4.

### Key takeaway
The `network` command does not create routes — it tells BGP to **advertise** an existing route (connected, static, etc.) to peers. A router with only a loopback `network` statement has reachable BGP sessions but its link subnets are invisible to the rest of the network, breaking return-path reachability for traffic sourced from those links.

---

## 2026-03-31: Routes vs paths in a ring topology

### Decision
Understand that route count and path count are independent metrics. Route count determines reachability; path count determines redundancy and failover options.

### Observation
After completing the 4-router eBGP ring, all routers had the same 8 routes but different path counts:

| Router | Routes | Paths |
|--------|--------|-------|
| r1 | 8 | 11 |
| r2 | 8 | 13 |
| r3 | 8 | 15 |
| r4 | 8 | 13 |

### Why path counts differ
In a ring, each prefix can be reached clockwise or counterclockwise. But BGP limits path visibility through three rules:

1. **Best-path-only advertisement** — a router only advertises its single best path to each peer, not all known paths.
2. **No re-advertisement to source** — a route learned from peer X is never sent back to peer X.
3. **Tiebreaker asymmetry** — when two paths have equal AS path length, the lowest neighbor IP wins. This determines which path becomes "best", which in turn controls what gets re-advertised.

r1 has the lowest link IPs (10.0.12.2, 10.0.14.2), so both r2 and r4 tend to learn their best paths from r1 — and won't re-advertise them back. r1 sees the fewest alternatives.

r3's neighbors (r2, r4) learned most best paths from their *other* neighbor (r1), not from r3, so they freely advertise alternatives to r3. r3 sees the most alternatives.

### When alternative paths matter
- **Failover** — if the best path goes down, the alternative is promoted instantly (no reconvergence wait)
- **Load balancing** — `maximum-paths N` installs multiple equal-cost paths into the forwarding table
- **Policy** — route-maps can prefer a longer AS path based on business rules (customer vs transit)

For day-to-day forwarding, only the best path (`*>`) is used. Alternative paths are insurance.

---

## Progress Log

### 2026-03-29
- [x] Evaluated VyOS, Cumulus VX, Ubuntu+FRR — chose Ubuntu+FRR
- [x] Created 4-router ring Vagrantfile (lab1/)
- [x] Resolved VyOS guest capability errors (`configure_networks`, `change_host_name`)
- [x] Resolved IP conflicts (consistent scheme: last octet = router# + 1, avoiding .1)

### 2026-03-30
- [x] All 4 VMs booted successfully (`vagrant up`)
- [x] FRR provisioned and running on all routers (`bgpd` enabled)
- [x] Verified connected routes visible in FRR (`show ip route`)
- [x] Configured loopback interfaces on r1, r2, r3
- [x] Configured eBGP peerings: r1↔r2 (AS65001↔AS65002), r2↔r3 (AS65002↔AS65003)
- [x] Verified BGP sessions established (`show bgp summary`)
- [x] Verified end-to-end reachability: r1 ↔ r3 via r2 (TTL=63)
- [x] Completed lab1a milestone (3-router eBGP string)
- [x] Created RUNBOOK1a.md with full step-by-step reproduction guide
- [x] Added .gitignore for Vagrant, VirtualBox, and sensitive files
- [x] Resolved transient r2 boot timeout (resource contention — added recovery steps to runbook)

### 2026-03-31
- [x] Booted r4, configured eBGP peering with r1 and r3
- [x] Observed partial ring behavior (r4↔r1 up, r4↔r3 intentionally Active)
- [x] Diagnosed return-path reachability failure — missing `network` statements on r4
- [x] Completed ring: added r4 as neighbor on r3
- [x] Analyzed routes vs paths across all routers (8 routes, 11–15 paths)
- [x] Verified full reachability: 48/48 pings (loopbacks + link IPs)
- [x] Completed lab1b milestone (4-router eBGP ring)
- [x] Created RUNBOOK1b.md
