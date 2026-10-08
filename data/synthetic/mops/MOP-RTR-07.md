# MOP-RTR-07: Firmware / software upgrade on edge and core routers

Node type: Edge Router
Vendor: Cisco

## Steps

1. Back up the running and startup configuration off-box.
2. Diff running vs startup configuration and save pending changes.
3. Record BGP neighbour timers, interface MTU and QoS policies.
4. Install the firmware / SMU package.
5. Reload the router and verify interfaces and MTU on both ends.
6. Verify BGP sessions, timers and received prefixes.
7. Verify static routes and OAM reachability.
8. Close the change after 30 minutes of stable routing.
