# MOP-UPG-02: Software upgrade on mobility manager (CMM)

Node type: CMM
Vendor: Nokia

## Steps

1. Confirm maintenance window and put the node in NetAct maintenance mode.
2. Take a configuration and database backup.
3. Check free disk space on /var/log and the staging partition.
4. Transfer and verify the release package.
5. Upgrade the pods/VMs to the target release.
6. Verify S1/N2 associations and attach success rate.
7. Remove NetAct maintenance mode and verify alarm synchronisation between node and NetAct.
8. Verify license capacity and subscriber counters.
9. Monitor KPIs for 30 minutes and close the change.
