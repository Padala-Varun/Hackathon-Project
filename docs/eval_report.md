# Evaluation report

Dataset: 23 LNI records, 0 MOPs, 0 logs. Test set: 22 incidents with a known correct past match + 2 out-of-scope.

Models: embeddings `BAAI/bge-small-en-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`, vector store `chroma`, confidence threshold 50%.

## Retrieval ablation

| Pipeline | Hit@1 | Hit@3 | MRR | Latency |
|---|---|---|---|---|
| BM25 keyword only | 95% | 100% | 0.98 | 0.02s |
| Dense semantic only | 100% | 100% | 1.00 | 0.03s |
| Hybrid (RRF) | 100% | 100% | 1.00 | 0.02s |
| Hybrid + rerank | 100% | 100% | 1.00 | 2.52s |
| Hybrid + rerank + fingerprint | 100% | 100% | 1.00 | 2.22s |
| Full pipeline with bge-reranker-base | 100% | 100% | 1.00 | 10.98s |

## Agent (end to end, LLM off)

- Correct past match ranked first: **100%**, in top 3: **100%**
- Out-of-scope incidents answered with "No verified match found": **100%**
- Recommendation statements citing a retrieved record: **100%**
- Average time per agent run: 4.70s

| Test | Mode | Incident / planned LNI | Top match | Result |
|---|---|---|---|---|
| T01 | incident | NetAct still lists alarms that the mobility manager already cleared, w | PACOSDKB-213 (88%) | HIT@1 |
| T02 | incident | After moving the CMM to release 26.7 our file copy with scp to the nod | PACOSDKB-212 (81%) | HIT@1 |
| T03 | incident | CMG appliance installation stops with a message to switch on secure bo | PACOSDKB-215 (85%) | HIT@1 |
| T04 | incident | Packet loss when pinging the two NRD virtual IPs, the VIP keeps jumpin | PACOSDKB-231 (96%) | HIT@1 |
| T05 | incident | Location of the 5G user is not written into the charging records altho | PACOSDKB-232 (84%) | HIT@1 |
| T06 | incident | UPF LMG pods restart in a loop after the CMG 25.7 lab deployment, SMF  | PACOSDKB-246 (97%) | HIT@1 |
| T07 | incident | How do I take a packet capture on the VSR router in front of a VNF CMM | PACOSDKB-247 (83%) | HIT@1 |
| T08 | incident | AMF never registers to the NRF when the NRF FQDN is only set on the NF | PACOSDKB-248 (96%) | HIT@1 |
| T09 | incident | We need to decode a raw SGSN per-call measurement record (PCMD) line | PACOSDKB-250 (81%) | HIT@1 |
| T10 | incident | cmg start does not bring the virtual machines up on HPE gen12 even tho | PACOSDKB-251 (87%) | HIT@1 |
| T11 | incident | CMM pods are not created: exceeded quota on limits.cpu and no Priority | PACOSDKB-252 (91%) | HIT@1 |
| T12 | incident | SSH to the standalone NSSF OAM over NCP ends with connection closed on | PACOSDKB-254 (97%) | HIT@1 |
| T13 | incident | kubectl get cnf stays Pending after the CMG operator-pod deployment, o | PACOSDKB-256 (98%) | HIT@1 |
| T14 | incident | 3LS package cannot be verified after we edited spinner.yaml by hand | PACOSDKB-260 (96%) | HIT@1 |
| T15 | incident | Some IP pools on the gateway receive no subscribers at all, address al | PACOSDKB-262 (51%) | HIT@1 |
| T16 | incident | egress-proxy pod crash loops on NRD 25.7, envoy complains about unknow | PACOSDKB-263 (85%) | HIT@1 |
| T17 | incident | Subscribers are unevenly spread across the CMM pool since includeMappe | PACOSDKB-287 (81%) | HIT@1 |
| T18 | incident | Path management log always shows RefPointName default for the S8 SGW p | PACOSDKB-230 (97%) | HIT@1 |
| T19 | incident | Cisco TWAG deletes the session right after Create Session Response, IP | PACOSDKB-296 (89%) | HIT@1 |
| T20 | pre_change | Planning to upgrade the CMM to release 26.7 next week, what can go wro | PACOSDKB-213 (62%) | HIT@1 |
| T21 | pre_change | Fresh CMG 26.7 deployment with the operator pod on a cloud platform | PACOSDKB-256 (87%) | HIT@1 |
| T22 | pre_change | Deploying CMM with xFDS pods, how should the S1, N2 and S11 interfaces | PACOSDKB-214 (98%) | HIT@1 |
| T23 | incident | Office printer on floor 3 does not print double-sided | PACOSDKB-260 (16%) | correctly refused |
| T24 | incident | Kafka consumer lag keeps growing on the analytics data lake | PACOSDKB-295 (16%) | correctly refused |
