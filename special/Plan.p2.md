# Phase 2: FRR Configuration Plan

## Overview

Write 8 FRR config files (`special/config/*-frr.conf`) that implement the SEARB Banking Sector BGP routing policy from the SRS. Phase 1 (Vagrantfile) is complete — this phase creates the configs that get deployed onto each VM.

---

## Task 2.1: sg-br1-frr.conf (SG Border Router + RR1)

**The most complex config — all inbound/outbound policies live here.**

### Interfaces & IGP
- Loopback: 10.255.0.1/32
- OSPF area 0 on loopback + iBGP links (L7: 10.0.7.0/24, L8: 10.0.8.0/24)
- Static routes for eBGP point-to-point links (not in OSPF)

### iBGP (AS 64512)
- Route Reflector: `neighbor <kl-br1-lo> route-reflector-client` NO (kl-br1 is also RR)
- Peer with kl-br1 (10.255.0.2) — RR-to-RR peering (neither is client of the other)
- Peer with bkk-br1 (10.255.0.3) — `route-reflector-client`
- All iBGP: `update-source lo`, `next-hop-self`, `send-community both`
- `soft-reconfiguration inbound` on all peers (REQ-B-OPS-02)
- `graceful-restart` restart-time 120, stalepath-time 360 (REQ-B-OPS-01)

### eBGP Peers (4 sessions)
| Peer | ASN | Peer IP | LOCAL_PREF | Inbound Route-Map | Outbound Route-Map |
|------|-----|---------|------------|--------------------|--------------------|
| singtel | 7473 | 10.0.1.2 | 150 | FROM-SINGTEL | TO-TRANSIT |
| sgix | 65500 | 10.0.3.2 | 200 | FROM-SGIX | TO-IXP |
| swift | 19905 | 10.0.5.2 | 300 | FROM-SWIFT | TO-SWIFT |
| aws | 16509 | 10.0.6.2 | 250 | FROM-AWS | TO-CLOUD |

### Inbound Policy (route-maps)
Each inbound route-map chains these checks (deny on match):
1. `ip prefix-list BOGONS` — deny RFC 6890 bogons (REQ-B-IN-01)
2. `ip prefix-list MAX-PREFIX-LEN` — deny ge 25 (REQ-B-IN-02)
3. `ip prefix-list OWN-SPACE` — deny 203.0.113.0/22, 198.51.100.0/23, 192.0.2.0/24 (REQ-B-IN-03)
4. `bgp as-path access-list LONG-AS-PATH` — deny paths > 25 hops (REQ-B-IN-04)
5. `bgp as-path access-list PRIVATE-ASN` — deny private ASNs (REQ-B-IN-05)
6. Community scrub: `set community none` for 64512:* inbound (REQ-B-SEC-03)
7. `set local-preference <value>` per peer (REQ-B-LP hierarchy)
8. Max-prefix limits per peer (REQ-B-IN-07):
   - singtel: 900,000 (warn 85%) — lab: use 100 for testing
   - sgix: 200,000 — lab: 50
   - swift: 50 — lab: 10
   - aws: 5,000 — lab: 20

### Outbound Policy
- `ip prefix-list OWN-PREFIXES` — permit only SEARB space (REQ-B-OUT-01, REQ-B-OUT-06)
- Always advertise 203.0.113.0/22 aggregate (REQ-B-OUT-02)
- `set community 64512:100 additive` on all outbound (REQ-B-OUT-03, SG-originated tag)
- TO-SWIFT: `set community no-export additive` (REQ-B-OUT-05)

### Prefix Origination
- `network 203.0.113.0/22` (aggregate)
- `network 203.0.113.0/24` (SG more-specific)

### Security
- `neighbor X password <key>` on all eBGP (REQ-B-SEC-01)
- `neighbor X ttl-security hops 1` on all eBGP (REQ-B-SEC-02)

### RTBH (REQ-B-TE-05)
- `ip community-list standard BLACKHOLE permit 64512:666`
- Route-map match: `set ip next-hop 192.0.2.1` (null-routed)
- `ip route 192.0.2.1/32 Null0`

---

## Task 2.2: kl-br1-frr.conf (KL Border Router + RR2)

### Interfaces & IGP
- Loopback: 10.255.0.2/32
- OSPF area 0 on loopback + iBGP link (L7: 10.0.7.0/24)

### iBGP (AS 64512)
- Route Reflector: peer with sg-br1 (RR-to-RR), bkk-br1 as `route-reflector-client`
- Same iBGP settings as sg-br1 (next-hop-self, send-community, soft-reconfig, graceful-restart)

### eBGP Peers (2 sessions)
| Peer | ASN | Peer IP | LOCAL_PREF | Inbound | Outbound |
|------|-----|---------|------------|---------|----------|
| tmnet | 4788 | 10.0.4.2 | 120 | FROM-TMNET | TO-TRANSIT |
| swift | 19905 | 10.0.9.2 | 300 | FROM-SWIFT | TO-SWIFT |

### Inbound Policy
- Same filtering chain as sg-br1 (bogons, max-len, own-space, AS-path, private ASN, community scrub)
- REQ-B-TE-02: Malaysian traffic preference — `bgp as-path access-list MY-ASNS permit` Malaysian ASNs, set higher LP on TM Net for those prefixes

### Outbound Policy
- Same OWN-PREFIXES whitelist
- `set community 64512:200 additive` (KL-originated tag)
- TO-SWIFT: `set community no-export additive`

### Prefix Origination
- `network 198.51.100.0/23`
- `network 198.51.100.0/24`

---

## Task 2.3: bkk-br1-frr.conf (BKK DR Router)

### Interfaces & IGP
- Loopback: 10.255.0.3/32
- OSPF area 0 on loopback + iBGP link (L8: 10.0.8.0/24)

### iBGP (AS 64512)
- RR client of both sg-br1 (10.255.0.1) and kl-br1 (10.255.0.2)
- next-hop-self, send-community, soft-reconfig, graceful-restart

### Prefix Origination (REQ-B-OUT-04)
- `network 192.0.2.0/24`
- Outbound route-map: `set as-path prepend 64512 64512 64512` (3x prepend to de-prefer DR path)
- `set community 64512:300 additive` (BKK-originated tag)

### DR Failover (REQ-B-TE-04)
- Normal mode: 3x prepend, standard LP
- Activation: remove prepend, set LP to 350 (manual config change or scripted)

### No eBGP peers — purely iBGP

---

## Task 2.4: singtel-frr.conf (AS 7473 — Primary Transit Simulator)

- Loopback: 10.255.1.1/32
- eBGP peer: sg-br1 at 10.0.1.1 (AS 64512)
- Originate:
  - `0.0.0.0/0` (default route)
  - `8.8.8.0/24` (sample Google DNS)
  - `1.1.1.0/24` (sample Cloudflare)
  - `13.0.0.0/24` (sample prefix — overlaps with AWS range for testing)
- Accept SEARB prefixes (for verification)
- MD5 auth + GTSM to match sg-br1

---

## Task 2.5: sgix-frr.conf (IXP RS — AS 65500)

- Loopback: 10.255.1.3/32
- eBGP peer: sg-br1 at 10.0.3.1 (AS 64512)
- Originate regional APAC prefixes:
  - `103.0.0.0/24` (sample APNIC prefix)
  - `202.0.0.0/24` (sample APAC prefix)
  - `210.0.0.0/24` (sample JP prefix)
- Accept SEARB prefixes
- MD5 auth + GTSM

---

## Task 2.6: tmnet-frr.conf (AS 4788 — KL Transit)

- Loopback: 10.255.1.4/32
- eBGP peer: kl-br1 at 10.0.4.1 (AS 64512)
- Originate Malaysian prefixes (for REQ-B-TE-02 testing):
  - `175.136.0.0/16` (sample TM Net range)
  - `219.93.0.0/24` (sample MY prefix)
  - `0.0.0.0/0` (default route)
- AS-path should contain Malaysian ASNs (4788) for TE-02 matching
- MD5 auth + GTSM

---

## Task 2.7: swift-frr.conf (AS 19905 — Private Peer, dual-homed)

- Loopback: 10.255.1.5/32
- eBGP peers (2 sessions):
  - sg-br1 at 10.0.5.1 (AS 64512) via enp0s8
  - kl-br1 at 10.0.9.1 (AS 64512) via enp0s9
- Originate SWIFT-specific prefixes only (narrow scope):
  - `57.128.0.0/16` (sample SWIFTNet range)
  - `149.134.0.0/24` (sample SWIFT prefix)
- NO default route (SWIFT is not a transit provider)
- MD5 auth + GTSM
- Accept only SEARB prefixes (should see no-export community from SEARB)

---

## Task 2.8: aws-frr.conf (AS 16509 — Cloud Peer)

- Loopback: 10.255.1.6/32
- eBGP peer: sg-br1 at 10.0.6.1 (AS 64512)
- Originate AWS prefix ranges:
  - `52.0.0.0/16` (sample AWS range)
  - `54.0.0.0/16` (sample AWS range)
  - `13.0.0.0/16` (sample AWS range — broader than singtel's /24 for testing)
- MD5 auth + GTSM

---

## Implementation Order

Start with the SEARB routers (they define the policies), then external peers (simpler, just originate prefixes):

1. `sg-br1-frr.conf` — most complex, sets the policy baseline
2. `kl-br1-frr.conf` — mirrors sg-br1 patterns with KL-specific peers
3. `bkk-br1-frr.conf` — simplest internal (iBGP only)
4. `singtel-frr.conf` — primary transit simulator
5. `sgix-frr.conf` — IXP simulator
6. `tmnet-frr.conf` — KL transit simulator
7. `swift-frr.conf` — private peer (dual-homed)
8. `aws-frr.conf` — cloud peer simulator

---

## SRS Requirements Coverage

| Req ID | Config File(s) | Status |
|--------|---------------|--------|
| REQ-B-IN-01 to IN-07 | sg-br1, kl-br1 | Pending |
| REQ-B-OUT-01 to OUT-06 | sg-br1, kl-br1, bkk-br1 | Pending |
| REQ-B-TE-01 | sg-br1 (LP hierarchy) | Pending |
| REQ-B-TE-02 | kl-br1 (MY AS-path match) | Pending |
| REQ-B-TE-03 | sg-br1, kl-br1 (SWIFT no-export + blackhole) | Pending |
| REQ-B-TE-04 | bkk-br1 (DR prepend/LP) | Pending |
| REQ-B-TE-05 | sg-br1 (RTBH community) | Pending |
| REQ-B-SEC-01 to SEC-04 | all eBGP configs | Pending |
| REQ-B-IBGP-01 to IBGP-04 | sg-br1, kl-br1, bkk-br1 | Pending |
| REQ-B-OPS-01, OPS-02 | all BGP configs | Pending |
| REQ-B-IBGP-05 (BFD) | — | Omitted (lab) |
| REQ-B-SEC-05 (SNMP) | — | Omitted (lab) |
| REQ-B-SEC-06 (RPKI infra) | — | Simulated via community |
