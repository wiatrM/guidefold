# Golden-set report — 6de2e6c

Router 0.1 weights (`Index.weights` at build time):

```json
{
  "abstain_threshold": 1200,
  "edge.refines": 60,
  "edge.replaces": 40,
  "edge.requires": 100,
  "edge.similar": 30,
  "field.body": 2,
  "field.description": 4,
  "field.digest": 3,
  "field.name": 6,
  "field.triggers": 5,
  "w_dense": 0,
  "w_ppr": 250,
  "w_scope": 200
}
```

```
stratum                                  n                 hit@1              recall@8               ndcg@10        completeness@4     distractor_rate@4  abstention_precision
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
multi_skill                             66                0.2727                0.8106                0.4644                0.1970                0.0000                     —
no_applicable                           44                     —                     —                     —                     —                0.2273                     —
sibling_ambiguity                       66                0.2424                0.9545                0.5065                0.2576                0.1515                     —
simple                                  22                0.2273                1.0000                0.4913                0.2727                     —                     —
stale_adversarial                       22                0.1000                0.7250                0.3678                0.0500                0.1364                     —
OVERALL                                220                0.2356                0.8793                0.4727                0.2126                0.1729                     —
```
