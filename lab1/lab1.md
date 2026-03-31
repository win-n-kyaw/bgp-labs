# Lab 1 — eBGP Ring: 4 Routers, 4 Autonomous Systems

## Topology

```
r1 (AS65001) ---10.0.12.0/24--- r2 (AS65002)
   |                                |
10.0.14.0/24                   10.0.23.0/24
   |                                |
r4 (AS65004) ---10.0.34.0/24--- r3 (AS65003)
```

Each router runs FRR in its own AS. Point-to-point /24 links, loopback /32 for router-id.

## Milestones

### Lab 1a — 3-router eBGP string (r1 ↔ r2 ↔ r3)

Configured eBGP peering across a linear topology. r1 and r3 have no direct link — they reach each other through r2.

**Verification:** r1 pings r3 (`10.0.23.4`) with TTL=63, confirming 1 hop through r2.

Steps: [RUNBOOK1a.md](RUNBOOK1a.md)

### Lab 1b — Complete the ring (add r4)

Added r4 with peerings to r1 and r3, closing the ring. Observed two key BGP behaviors along the way:

1. **Partial ring (r3↔r4 intentionally left down)** — r4↔r1 established, r4↔r3 stayed `Active`. r4 received routes from r1 but pings to remote loopbacks failed until r4 advertised its own link subnets (`network 10.0.14.0/24`, `network 10.0.34.0/24`), enabling return-path reachability.

2. **Routes vs paths** — all 4 routers see the same 8 routes but different path counts (11–15). The ring provides two directions to each prefix, but BGP's best-path-only advertisement and tiebreaker rules mean each router sees a different number of alternatives.

**Verification:** 48/48 pings across all loopbacks and link IPs.

Steps: [RUNBOOK1b.md](RUNBOOK1b.md)

## Lessons Learned

1. **Loopback as router-id** — a link IP dies with its interface and cascades all BGP sessions. A loopback never goes down. See [DECISIONS.md](../DECISIONS.md).

2. **Neighbor uses link IP, not loopback** — eBGP neighbors must be directly reachable. Loopback-based peering requires an IGP underneath (an iBGP pattern).

3. **`network` does two things** — it advertises a prefix AND enables return-path reachability for that subnet. Without it, sessions are up but remote routers can't route replies back. See [DECISIONS.md](../DECISIONS.md).

4. **`no bgp ebgp-requires-policy`** — FRR blocks all eBGP route exchange by default unless route-maps are defined. Disabled for lab use only.

5. **Routes vs paths** — routes determine forwarding (same on all routers). Paths are alternatives that matter for failover, load balancing, and policy. See [DECISIONS.md](../DECISIONS.md).

## Final State

| Router | AS | Loopback | Peers | Networks Advertised |
|--------|----|----------|-------|---------------------|
| r1 | 65001 | 1.1.1.1 | r2, r4 | 1.1.1.1/32, 10.0.12.0/24, 10.0.14.0/24 |
| r2 | 65002 | 2.2.2.2 | r1, r3 | 2.2.2.2/32, 10.0.12.0/24, 10.0.23.0/24 |
| r3 | 65003 | 3.3.3.3 | r2, r4 | 3.3.3.3/32, 10.0.23.0/24, 10.0.34.0/24 |
| r4 | 65004 | 4.4.4.4 | r1, r3 | 4.4.4.4/32, 10.0.14.0/24, 10.0.34.0/24 |

## What's Next

- [ ] **Lab 2** — Route filtering with prefix-lists and route-maps
