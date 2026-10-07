# MOP-FW-05: Firewall policy change

Node type: Firewall
Vendor: Fortinet

## Steps

1. Back up the current policy.
2. Review the rule changes with traffic owners (SCTP 36412, Diameter 3868).
3. Apply the policy change.
4. Verify S1/SCTP and Diameter associations and deny logs.
5. Roll back immediately if associations drop.
