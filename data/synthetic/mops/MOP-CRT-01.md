# MOP-CRT-01: TLS certificate renewal on SBC

Node type: SBC
Vendor: Ribbon

## Steps

1. Check current certificate expiry and peer trust requirements.
2. Generate the CSR and obtain the signed certificate.
3. Install the leaf and intermediate certificates (full chain).
4. Restart the TLS profile in a low-traffic period.
5. Verify the TLS handshake with each interconnect peer using openssl s_client.
6. Monitor SIP trunk status and close the change.
