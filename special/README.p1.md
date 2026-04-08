# Phase 1: Infrastructure — Completed

## What Was Built

**Vagrantfile** defining 8 VMs on VirtualBox with FRR provisioning for the SEARB Banking Sector BGP lab (AS 64512).

### VM Inventory

| VM | Role | ASN | Site |
|----|------|-----|------|
| sg-br1 | SG Border Router + RR1 | 64512 | SG |
| kl-br1 | KL Border Router + RR2 | 64512 | KL |
| bkk-br1 | BKK DR Router | 64512 | BKK |
| singtel | Primary Transit | 7473 | SG |
| sgix | IXP Route Server | 65500 | SG |
| tmnet | KL Transit | 4788 | KL |
| swift | Private Peer (dual-homed) | 19905 | SG/KL |
| aws | Cloud Peer | 16509 | SG |

### Network Links (8 links, /24 subnets)

```
L1: 10.0.1.0/24  sg-br1  <-> singtel     (link_sg_singtel)
L3: 10.0.3.0/24  sg-br1  <-> sgix        (link_sg_sgix)
L4: 10.0.4.0/24  kl-br1  <-> tmnet       (link_kl_tmnet)
L5: 10.0.5.0/24  sg-br1  <-> swift       (link_sg_swift)
L6: 10.0.6.0/24  sg-br1  <-> aws         (link_sg_aws)
L7: 10.0.7.0/24  sg-br1  <-> kl-br1      (link_sg_kl)
L8: 10.0.8.0/24  sg-br1  <-> bkk-br1     (link_sg_bkk)
L9: 10.0.9.0/24  kl-br1  <-> swift       (link_kl_swift)
```

Note: L2 was removed (starhub eliminated from topology).

### Provisioning Pipeline (per VM)

1. **IP forwarding** — enables `net.ipv4.ip_forward=1`
2. **Interface config** — writes systemd-networkd drop-ins (DHCP=no) then assigns static IPs
3. **FRR install** — adds FRR stable repo, installs `frr` + `frr-pythontools`, enables bgpd + ospfd
4. **FRR config** — copies `config/<hostname>-frr.conf` into `/etc/frr/frr.conf` and restarts FRR

### Key Design Decisions

- **/24 subnets** instead of /30 — simpler for lab, avoids broadcast address edge cases on some VBox versions
- **systemd-networkd drop-ins** — prevents DHCP race condition that kills Vagrant SSH on interface bring-up
- **Link numbering gap (no L2)** — intentional; preserves alignment with SRS peering table after starhub removal
- **512MB per VM** — ~4GB total; can reduce external peers to 384MB if host RAM is tight

### Verification

```bash
cd special/
vagrant up           # ~8-12 min
vagrant status       # all 8 VMs should be "running"
vagrant ssh sg-br1 -c "ip -br addr"    # verify all 6 interfaces have IPs
vagrant ssh sg-br1 -c "vtysh -c 'show version'"  # FRR is running
```

### Status

- [x] Vagrantfile created with 8 VMs
- [x] VBox intnet links defined for all 8 connections
- [x] FRR provisioning pipeline (install + config apply)
- [x] systemd-networkd DHCP fix for stable SSH
- [ ] Config files not yet created (Phase 2)
