# BGP Labs

Hands-on BGP learning lab using Vagrant, VirtualBox, and FRRouting (FRR) on Ubuntu VMs.

## Topology

```
r1 (AS65001) ---eth1--- r2 (AS65002)
   |                       |
 eth2                    eth2
   |                       |
r4 (AS65004) ---eth1--- r3 (AS65003)
```

4-router ring with point-to-point /24 links. Each router runs FRR in its own AS (eBGP).

## Progress

- [x] **Lab 1a** — 3-router eBGP string (r1 ↔ r2 ↔ r3). End-to-end reachability verified.
- [x] **Lab 1b** — Complete the ring (add r4), full-mesh eBGP peering. 48/48 reachability.
- [ ] **Lab 2** — Route filtering with prefix-lists and route-maps.

## Quick Start

```bash
cd lab1
vagrant up r1 && vagrant up r2 && vagrant up r3
```

Requires VirtualBox and Vagrant with ~2 GB free RAM (512 MB per VM).

## Stack

| Component | Choice |
|-----------|--------|
| Hypervisor | VirtualBox 7.0 |
| VM orchestration | Vagrant |
| Base image | `ubuntu/jammy64` |
| Routing engine | FRRouting 10.x |

See [DECISIONS.md](DECISIONS.md) for rationale behind these choices.
