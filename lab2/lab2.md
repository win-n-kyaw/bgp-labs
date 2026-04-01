# Lab 2 Plan — Route Filtering with Prefix-Lists and Route-Maps (Full Mesh)

## Context

Lab 1 established eBGP fundamentals on a ring topology with `no bgp ebgp-requires-policy` (the training wheels). Lab 2 removes that crutch and introduces proper route filtering — the core skill that separates "BGP works" from "BGP is under control."

The lab2 Vagrantfile already exists with a **full-mesh** topology (6 links instead of 4), adding diagonal links r1-r3 and r2-r4. This gives richer path diversity to make filtering scenarios more interesting.

## Topology (Full Mesh)

```
r1 (AS65001) ----10.0.12.0/24---- r2 (AS65002)
   |  \                          /    |
   |   10.0.13.0/24    10.0.24.0/24   |
   |        \          /              |
10.0.14.0/24  \      /         10.0.23.0/24
   |            \  /                  |
r4 (AS65004) ----10.0.34.0/24---- r3 (AS65003)
```

6 links, 4 routers, each in its own AS. Every router peers with every other router (full mesh eBGP).

### IP Addressing (from Vagrantfile)

| Link | Subnet | Router A (IP) | Router B (IP) |
|------|--------|---------------|---------------|
| r1-r2 | 10.0.12.0/24 | r1 (.2) | r2 (.3) |
| r1-r3 | 10.0.13.0/24 | r1 (.2) | r3 (.4) |
| r1-r4 | 10.0.14.0/24 | r1 (.2) | r4 (.5) |
| r2-r3 | 10.0.23.0/24 | r2 (.3) | r3 (.4) |
| r2-r4 | 10.0.24.0/24 | r2 (.3) | r4 (.5) |
| r3-r4 | 10.0.34.0/24 | r3 (.4) | r4 (.5) |

Loopbacks: r1=1.1.1.1, r2=2.2.2.2, r3=3.3.3.3, r4=4.4.4.4

---

## 3-Day Plan

### Day 1 — Baseline Full Mesh + Prefix-List Fundamentals

**Goal:** Get the full mesh running with proper route-maps (no more `no bgp ebgp-requires-policy`), then use prefix-lists to selectively filter.

#### Lab 2a — Full Mesh Baseline (remove training wheels)

1. **Boot all 4 VMs** from the new lab2 Vagrantfile
2. **Configure all 4 routers** with full-mesh eBGP (each router peers with all 3 others)
   - r1: neighbors r2 (10.0.12.3), r3 (10.0.13.4), r4 (10.0.14.5)
   - r2: neighbors r1 (10.0.12.2), r3 (10.0.23.4), r4 (10.0.24.5)
   - r3: neighbors r1 (10.0.13.2), r2 (10.0.23.3), r4 (10.0.34.5)
   - r4: neighbors r1 (10.0.14.2), r2 (10.0.24.3), r3 (10.0.34.4)
3. **Use explicit permit-all route-maps** instead of `no bgp ebgp-requires-policy`:
   ```
   route-map PERMIT-ALL permit 10
   !
   router bgp 6500X
     neighbor X.X.X.X route-map PERMIT-ALL in
     neighbor X.X.X.X route-map PERMIT-ALL out
   ```
4. **Advertise** loopback + all connected link subnets via `network` statements
5. **Verify:** `show bgp summary` — all 3 peers Established on each router
6. **Verify:** full reachability ping test (all loopbacks + all link IPs)
7. **Observe:** `show bgp ipv4 unicast` — notice how full mesh changes path count vs ring (more direct paths, shorter AS paths)

**Key lesson:** route-maps are the gatekeeper. Even an empty `permit` route-map is an explicit policy decision ("I chose to allow everything"), unlike the `no ebgp-requires-policy` escape hatch.

#### Lab 2b — Prefix-List Basics (deny specific prefixes)

1. **Scenario:** r1 decides it does NOT want to receive r4's loopback (4.4.4.4/32) from r4
2. **Create a prefix-list on r1:**
   ```
   ip prefix-list DENY-R4-LO seq 5 deny 4.4.4.4/32
   ip prefix-list DENY-R4-LO seq 10 permit 0.0.0.0/0 le 32
   ```
3. **Apply via route-map on r1:**
   ```
   route-map FROM-R4 permit 10
     match ip address prefix-list DENY-R4-LO
   !
   neighbor 10.0.14.5 route-map FROM-R4 in
   ```
4. **Verify:** `show bgp ipv4 unicast` on r1 — 4.4.4.4/32 no longer learned from r4
5. **Observe:** r1 still has 4.4.4.4/32 via r2 or r3 (alternative paths through the mesh!)
6. **Experiment:** What happens if you also filter 4.4.4.4/32 from r2 and r3? Can r1 still reach r4's loopback?

**Key lessons:**
- Prefix-lists match on **network address and mask length**
- `le` (less-than-or-equal) and `ge` (greater-than-or-equal) modify mask matching
- The implicit deny at the end of a prefix-list — always need an explicit permit-all entry
- Full mesh provides resilience: filtering on one peer doesn't kill reachability if other paths exist

---

### Day 2 — Route-Map Deep Dive (match, set, multiple clauses)

**Goal:** Use route-maps for more than just permit/deny — modify route attributes, build multi-clause policies.

#### Lab 2c — Route-Map Actions: Setting Local Preference and MED

1. **Scenario:** r2 receives the same prefix (3.3.3.3/32) from both r3 (direct) and r1 (via r1→r3). Make r2 prefer the path through r1 using local-pref.
   ```
   route-map FROM-R1 permit 10
     match ip address prefix-list MATCH-R3-LO
     set local-preference 200
   route-map FROM-R1 permit 20
   !
   route-map FROM-R3 permit 10
     match ip address prefix-list MATCH-R3-LO
     set local-preference 100
   route-map FROM-R3 permit 20
   ```
2. **Verify:** `show bgp 3.3.3.3/32` — best path should now be via r1 (higher local-pref wins)
3. **Observe:** traceroute from r2 to 3.3.3.3 — traffic goes r2→r1→r3 instead of direct r2→r3

**Key lesson:** local-preference is LOCAL to the router (not sent to eBGP peers). It overrides the default best-path selection (shortest AS path). This is how operators implement routing policy ("prefer customer over peer").

#### Lab 2d — Outbound Filtering (controlling what you advertise)

1. **Scenario:** r3 decides to only advertise its loopback (3.3.3.3/32) to the world, keeping its link subnets private
   ```
   ip prefix-list LOOPBACK-ONLY seq 5 permit 3.3.3.3/32
   !
   route-map TO-ALL-PEERS permit 10
     match ip address prefix-list LOOPBACK-ONLY
   ```
   Apply as outbound route-map on all r3's neighbors.
2. **Verify:** check r1, r2, r4 — they should no longer see 10.0.13.0/24, 10.0.23.0/24, 10.0.34.0/24 from r3
3. **Observe:** Can r1 still ping r3's link IPs (10.0.13.4)? YES — because it's directly connected. Can r4 ping 10.0.23.4? It depends on whether r4 has a route to that subnet from another source.
4. **Test:** What breaks? What still works? Document the difference between reachability (routing table) and connectivity (physical link).

**Key lessons:**
- Outbound filtering controls what you **advertise** (your reputation)
- Inbound filtering controls what you **accept** (your worldview)
- Connected routes always work regardless of BGP — BGP only matters for non-connected destinations

#### Lab 2e — AS-Path Filtering

1. **Scenario:** r1 wants to reject any route that transited through AS65004 (r4), regardless of prefix
   ```
   bgp as-path access-list 1 deny _65004_
   bgp as-path access-list 1 permit .*
   !
   route-map FILTER-R4-TRANSIT permit 10
     match as-path 1
   ```
   Apply inbound on r1's peers r2 and r3 (not r4 directly — routes from r4 have origin AS65004 anyway).
2. **Verify:** routes with AS path containing 65004 are rejected
3. **Compare:** AS-path filtering vs prefix-list filtering — when to use which?

**Key lesson:** AS-path filtering matches on the **path the route traveled**, not the destination. Useful for blocking transit traffic or implementing peering policies without knowing exact prefixes.

---

### Day 3 — Advanced Scenarios + Putting It All Together

**Goal:** Combine multiple filtering tools, simulate real-world policy scenarios, break things intentionally.

#### Lab 2f — Community-Based Filtering (tagging routes)

1. **Concept:** BGP communities are tags attached to routes. Routers can set, match, and act on these tags.
2. **Scenario:** r3 tags its loopback route with community `65003:100` (meaning "customer route"). r1 uses a route-map to match this community and set local-preference to 300.
   ```
   # On r3 (outbound):
   route-map TO-PEERS permit 10
     match ip address prefix-list MY-LOOPBACK
     set community 65003:100
   route-map TO-PEERS permit 20

   # On r1 (inbound from any peer):
   route-map FROM-PEERS permit 10
     match community CUSTOMER-ROUTES
     set local-preference 300
   route-map FROM-PEERS permit 20
   ```
3. **Verify:** `show bgp 3.3.3.3/32` on r1 — community tag visible, local-pref elevated
4. **Key lesson:** Communities decouple policy from topology. The receiver doesn't need to know which prefix is a "customer route" — the sender tags it, and the receiver acts on the tag.

#### Lab 2g — Chaos Testing: What Happens When Filters Break Things?

1. **Block everything inbound on r2** — route-map with deny-all. Observe: r2 loses all BGP routes, falls back to connected-only. Other routers route around r2 (full mesh resilience).
2. **Create a routing loop** — Use local-pref to force suboptimal paths, observe what BGP's loop prevention (AS-path check) catches vs what it doesn't.
3. **Remove all route-maps** (without `no bgp ebgp-requires-policy`) — Observe: FRR's default deny kicks in, all routes disappear. This is why the default exists.

#### Lab 2h — Final Challenge: Build a Real-World Policy

Design and implement a complete filtering policy across all 4 routers:

| Router | Role | Policy |
|--------|------|--------|
| r1 | "Transit provider" | Accepts all routes, advertises all routes, sets community tags |
| r2 | "Customer of r1" | Accepts only default + specific prefixes from r1, advertises only its own prefixes |
| r3 | "Peer of r2" | Mutual exchange of customer routes only (no transit) |
| r4 | "Customer of r1" | Same as r2 but different prefix set |

Verify: r2 and r4 can reach each other through r1 (transit), but r3 only sees r2's direct routes (peering).

---

## Files to Create

| File | Purpose |
|------|---------|
| [lab2/lab2.md](lab2/lab2.md) | Main lab document (topology, milestones, lessons learned) |
| lab2/RUNBOOK2a.md | Day 1 step-by-step: full mesh baseline + prefix-list basics |
| lab2/RUNBOOK2b.md | Day 2 step-by-step: route-map deep dive |
| lab2/RUNBOOK2c.md | Day 3 step-by-step: advanced scenarios + final challenge |

## Vagrantfile

Already exists at [lab2/Vagrantfile](lab2/Vagrantfile) — full mesh with 6 links. **One fix needed:** VB names say `lab1-*` — should rename to `lab2-*` to avoid collisions if lab1 VMs are still running.

## Verification Strategy

After each milestone:
1. `show bgp summary` — session states
2. `show bgp ipv4 unicast` — route table (compare before/after filtering)
3. `show ip route` — what's actually installed in forwarding
4. Targeted pings — verify expected reachability AND expected unreachability
5. `show route-map` / `show ip prefix-list` — confirm policy is applied
