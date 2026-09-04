"""Shared synthetic-card builder for Router/Index unit tests.

Not a test module itself (no ``test_`` prefix) so pytest never collects it; test files import
from it directly, e.g. ``from _router_helpers import make_card``.
"""


def make_card(urn, node, *, name=None, description="", digest="", triggers=(),
              negative_triggers=(), requires=(), refines=(), status="active",
              replaced_by=None, owner=None, body=""):
    """Build a card dict with exactly the keys Index.build produces, for Index.from_cards."""
    return {
        "urn": urn, "node": node, "name": name or urn.rsplit(":", 1)[-1],
        "description": description, "digest": digest or description[:200],
        "triggers": list(triggers), "negative_triggers": list(negative_triggers),
        "requires": list(requires), "refines": list(refines),
        "status": status, "replaced_by": replaced_by,
        "kind": None, "layer": None, "owner": owner,
        "_body": body,
    }


def make_nodes(*names):
    """A minimal guidefold.yaml-shaped nodes dict; hierarchy is inferred from dotted names."""
    return {n: {"paths": [f"{n}/**"], "owner": "team"} for n in names}
