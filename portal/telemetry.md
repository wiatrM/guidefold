---
title: Telemetry and skill health
description: What is counted, what is not, and why missing data is never shown as zero.
---

Guidefold records four things about every rule. Each one is an event with an id, a time, the rule and its exact revision.

| Event | Means | Does not mean |
|---|---|---|
| card shown | the hook printed the card | the agent read it |
| full text loaded | `load` fetched the file and checked its checksum | the agent used it |
| card led to full text | the load named the search that showed the card | the card was not enough (it may have been irrelevant) |
| judged | a person said it helped, hindered, or did not apply | anything about other rules |

An HTTP 200 from the service is never counted as "used". Only a load or a judgement is.

## Did the card suffice

Since contract 1.1.4, a load carries the id of the search that exposed the card, when the adapter knows it. That gives two numbers per rule: how many exposures led to a load, and how many loads came from an adapter that did not say. The second one is unknown, not zero. While it is above zero, "exposures minus expanded" is an upper bound on cards that were enough, not a fact.

Events never contain the prompt, the rule text or a token. They are spooled locally under `.guidefold/telemetry/` and sent in batches with `guidefold telemetry flush`.

## The skill health panel

The hosted review screen shows one row per rule with four gates and a recommendation.

Reach is how often the card was shown. Pull is how often a card led to the full text; if any loads are unlinked it shows as a lower bound, never as green. Value is the helped ratio, shown as counts until twenty judgements exist, because a percentage of five is noise. Health is open questions about the rule: never loaded, source changed in git, or a queued item waiting for the owner.

The recommendation is one of: promote up, keep, review, archive candidate. It is a suggestion with its reasons listed. Nothing happens until the owner clicks through to the queue or opens a proposal. Guidefold does not promote or archive on its own.

## Unknown is not zero

If no adapter reported for a rule, the row says unknown and why. If a sample is small, it says so and shows counts. A blank never becomes a zero, because a zero would look like a decision.
