"""Bounded, snapshot-resident BM25 term contributions for the service spike.

Not a query cache: corpus terms are considered before readiness, without probe
queries. The supplied Router's original scorer computes every single-term
contribution, preserving field rounding and integer division. Request-time work
multiplies these constants by query TF and applies the current admissible set.

The index is immutable. Replacing it or changing weights disables this cache.
In-place postings/norm/IDF edits require invalidate() and a rebuilt snapshot.
"""
from __future__ import annotations

import sys
import time

DEFAULT_MAX_BYTES = 256 * 1024 * 1024


def _signature(index):
    """Cheap mutation guard, not a content hash of an immutable snapshot."""
    return (id(index), id(index.idf), id(index.postings), id(index.field_norm),
            tuple(index.FIELDS), tuple(index.weights[f"field.{f}"] for f in index.FIELDS),
            index.IDF_SCALE, index.K1)


class BM25TermCache:
    """Immutable term scores; no request-dependent state or lazy admission."""

    def __init__(self, router, *, max_bytes, tokenize):
        started = time.perf_counter()
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        self.router = router
        self.original = router._bm25_scores
        self.tokenize = tokenize
        self.signature = _signature(router.index)
        self.terms = {}
        self.valid = True
        index = router.index
        visible = set(index.cards)
        cached_pairs = total_pairs = owned_values_bytes = 0
        accepting_terms = max_bytes > 0
        rejected_terms = 0
        # Frequent terms cost most. This order uses only corpus IDF, never queries.
        terms = sorted(index.idf, key=lambda t: (index.idf[t] is None, index.idf[t] or 0, t))
        for term in terms:
            if list(tokenize(term)) != [term]:
                rejected_terms += 1
                continue
            contributions = self.original(term, visible)
            total_pairs += len(contributions)
            if not accepting_terms:
                continue
            # Term/URN strings already belong to the index. Conservatively count
            # score objects per occurrence, including shared small integers.
            value_bytes = sys.getsizeof(contributions) + sum(
                sys.getsizeof(score) for score in contributions.values())
            self.terms[term] = contributions
            projected = sys.getsizeof(self.terms) + owned_values_bytes + value_bytes
            if projected > max_bytes:
                del self.terms[term]
                # Rejected insertion may grow the dict; compact its retained size.
                self.terms = dict(self.terms)
                accepting_terms = False
                continue
            owned_values_bytes += value_bytes
            cached_pairs += len(contributions)
        retained = sys.getsizeof(self.terms) + owned_values_bytes if self.terms else 0
        self.metadata = {
            "kind": "precomputed_exact_bm25_term_scores",
            "max_bytes": max_bytes,
            "estimated_cache_bytes": retained,
            "memory_estimate_scope": "retained cache dicts and score objects; excludes shared index strings, fixed wrapper and transient build work; not RSS",
            "cached_terms": len(self.terms), "total_terms": len(terms),
            "uncacheable_term_keys": rejected_terms,
            "cached_term_doc_pairs": cached_pairs, "total_term_doc_pairs": total_pairs,
            "term_coverage": len(self.terms) / len(terms) if terms else 1.0,
            "posting_coverage": cached_pairs / total_pairs if total_pairs else 1.0,
            "fully_cached": len(self.terms) == len(terms),
            "admission_order": "corpus IDF ascending, stop retaining at budget; all terms counted",
            "query_cache": False, "lazy_warmup": False, "active": True,
            "startup_ms": (time.perf_counter() - started) * 1000,
        }

    def invalidate(self, reason="snapshot_changed"):
        self.valid = False
        self.metadata["active"] = False
        self.metadata["disabled_reason"] = reason

    def score(self, query, visible):
        if not self.valid or _signature(self.router.index) != self.signature:
            if self.valid:
                self.invalidate("index_or_scoring_configuration_changed")
            return self.original(query, visible)
        if not self.terms:
            return self.original(query, visible)
        qtf = {}
        for term in self.tokenize(query):
            qtf[term] = qtf.get(term, 0) + 1
        # Cached terms were checked at build time. Before using any uncached
        # single-term query, verify that retokenizing it cannot change semantics.
        # Fall back for the WHOLE original query before accumulating any scores.
        if any(term not in self.terms and list(self.tokenize(term)) != [term]
               for term in qtf):
            return self.original(query, visible)
        scores = {}
        for term, count in qtf.items():
            contributions = self.terms.get(term)
            if contributions is None:
                # No request-time admission or dependence on previous workloads.
                contributions = self.original(term, visible)
            for urn, score in contributions.items():
                if urn in visible:
                    # Zero keys still receive lexical ranks, including cross-ranks.
                    scores[urn] = scores.get(urn, 0) + score * count
        return scores


def install_bm25_cache(router, *, max_bytes=DEFAULT_MAX_BYTES, tokenize=None):
    """Patch one Router instance before readiness and return build metadata.

    The original method must implement additive query-TF BM25, as the shared
    Guidefold Router does. No global class/CLI is changed. router.bm25_cache
    exposes invalidate(); router.bm25_cache_metadata is the returned mapping.
    """
    if hasattr(router, "bm25_cache"):
        raise ValueError("BM25 cache is already installed on this router")
    if tokenize is None:
        method = getattr(router._bm25_scores, "__func__", router._bm25_scores)
        tokenize = getattr(method, "__globals__", {}).get("tokenize")
    if not callable(tokenize):
        raise TypeError("Supply the Router's exact tokenize callable")
    cache = BM25TermCache(router, max_bytes=max_bytes, tokenize=tokenize)
    router.bm25_cache = cache
    router.bm25_cache_metadata = cache.metadata
    router._bm25_scores = cache.score
    return cache.metadata