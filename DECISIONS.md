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
