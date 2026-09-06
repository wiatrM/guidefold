# Additional CPU control: full-coverage source prefix

Added while the original five-arm routing run is in progress, before inspecting any new-cohort outcome or running analyze.py. This is an explicitly exploratory extension, not one of the four primary planned tests. It does not replace any original arm or alter the filter gate.

Use the same frozen 2,048 queries and full 10,123-skill bank. Reuse A_original outputs. F_full_prefix20 appends to triggers the first up to 20 whitespace words of original name + description + stripped body for EVERY skill. The 20-word budget is fixed and not tuned. This control is independent of generated text and of gold identities. It is not directly word-count matched to B or E. It answers whether a trivial, inexpensive representation intervention across the entire bank merits later study; it does not estimate the effect of full-coverage LLM enrichment.

Keep the exact production routing defaults and top-50/select-4 contract. Use the same research term cache, and require full-pipeline parity on the same 64 hash-selected queries. Run one CPU process at nice 10, no GPU or new generation. Hash this protocol, run code, source documents and baseline manifest before F runs. Preserve all outcomes.

Report F versus A macro Recall@10, complete@4, candidate Recall@50 and all-gold candidate coverage, with descriptive paired query and shared-gold-component bootstrap intervals (5,000 draws, seeds 202609064/202609065). No added confirmatory significance claim or change to the original Holm family. Require separate source/held-out replication before adoption; ordinary header reweighting is not novel. Independently reconstruct outcome counts and deltas from saved IDs and qrels in a separate script.
