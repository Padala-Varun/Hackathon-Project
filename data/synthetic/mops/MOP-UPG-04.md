# MOP-UPG-04: Software upgrade on packet core gateway (CMG)

Node type: CMG
Vendor: Nokia

## Steps

1. Confirm maintenance window approval and notify the NOC and the mate-site team.
2. Export the configuration backup to the backup server and verify the checksum.
3. Run pre-checks: capture 'show router bgp summary', 'show bfd session', interface MTU, GTP path-management timers and active session counts.
4. Drain user-plane traffic to the mate gateway (check mate load first).
5. Load the new software package and activate the target release.
6. Reboot the gateway and wait for all cards and pods to come up.
7. Re-enable BGP/BFD sessions and restore traffic.
8. Post-checks: compare session counts, BGP/BFD state, interface MTU and GTP timers with the pre-check snapshot.
9. Confirm alarms and PM data are flowing to NetAct, monitor KPIs for 30 minutes and close the change.
