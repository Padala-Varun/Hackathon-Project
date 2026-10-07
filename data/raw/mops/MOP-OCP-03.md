# MOP-OCP-03: Worker node patching on OpenShift (OCP)

Node type: OCP Cluster
Vendor: Red Hat

## Steps

1. Check cluster health and operator status.
2. List PodDisruptionBudgets and confirm each allows at least one disruption.
3. Cordon and drain the worker node.
4. Apply the OS patch.
5. Reboot the node and wait for Ready state.
6. Uncordon the node and verify pods rescheduled.
7. Repeat for the next worker; close the change.
