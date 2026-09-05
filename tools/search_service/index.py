"""Export the reference CLI's build-time BM25F integers for the Go publisher.

No alternate tokenizer, IDF formula or field normalization is introduced here.
Go compiles the term contributions once and sums them at query time.
"""
import hashlib
from tools.serve_spike.repository import canonical


def with_router_index(cli, bundle, index=None):
    snapshot = bundle['snapshot']
    index = index or cli.Index.from_cards(snapshot['cards'], snapshot['nodes'], weights=snapshot['weights'])
    order = sorted(index.cards)
    positions = {urn: i for i, urn in enumerate(order)}
    data = {
        'format': 'guidefold-bm25f-build-v1',
        'policy_sha256': snapshot['cli_sha256'],
        'snapshot_sha256': bundle['sha256'],
        'order': order,
        'fields': list(index.FIELDS),
        'idf': index.idf,
        'norms': {field: [index.field_norm[field][urn] for urn in order] for field in index.FIELDS},
        'postings': {field: {term: [[positions[urn], tf] for urn, tf in sorted(post.items())]
                             for term, post in index.postings[field].items()} for field in index.FIELDS},
    }
    return {**bundle, 'router_index': data, 'router_index_sha256': hashlib.sha256(canonical(data)).hexdigest()}