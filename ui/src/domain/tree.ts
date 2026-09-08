import type {TreeNode} from '../domain';

/** Collapses a chain of directories whose only content is one more directory into a single row,
 * merging the already-slash-terminated labels so `.agents/` -> `skills/` -> `postgres-auth/`
 * reads as one `.agents/skills/postgres-auth/` row instead of three nested disclosures — the
 * same "compact folders" behaviour file trees in GitHub and VS Code use. A directory stops
 * collapsing once it holds two or more entries, or once its only entry is a file (a node with no
 * `children` of its own). Leaf nodes (skills) pass through unchanged. Pure data transform: it
 * does not know about routes, the fixture or `ScopeTree`, which stays generic. */
export function compactTree(nodes: TreeNode[]): TreeNode[] {
  return nodes.map(compactNode);
}

function compactNode(node: TreeNode): TreeNode {
  if (!node.children) return node;
  let merged = node;
  while (merged.children && merged.children.length === 1 && merged.children[0].children) {
    const only = merged.children[0];
    merged = {id: only.id, label: merged.label + only.label, children: only.children};
  }
  return merged.children ? {...merged, children: compactTree(merged.children)} : merged;
}
