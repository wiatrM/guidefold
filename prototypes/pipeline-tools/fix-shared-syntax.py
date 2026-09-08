from pathlib import Path
p=Path("prototypes/pipeline-hifi/src/Shared.tsx");s=p.read_text();start=s.index("export function ScopeTree(");end=s.index("export function DataTable(",start)
replacement="""export function ScopeTree({nodes,selected,label}:{nodes:TreeNode[];selected?:string;label:string}){
 const contains=(node:TreeNode):boolean=>node.id===selected||!!node.children?.some(contains);
 function renderNodes(items:TreeNode[],depth:number):ReactNode{
  return <ul>{items.map(node=><li key={node.id}>
   {node.children?.length
    ? <details open={depth===0||contains(node)}>
       <summary><FolderSimple aria-hidden="true"/><span>{node.label}</span>{node.detail&&<small>{node.detail}</small>}</summary>
       {renderNodes(node.children,depth+1)}
      </details>
    : <div className={css.treeLeaf}>
       <FileText aria-hidden="true"/>
       {node.href?<Link to={node.href} aria-current={node.id===selected?'true':undefined}>{node.label}</Link>:<span>{node.label}</span>}
       {node.detail&&<small>{node.detail}</small>}
      </div>}
  </li>)}</ul>;
 }
 return <div className={css.tree} role="group" aria-label={label}>{renderNodes(nodes,0)}</div>;
}
"""
p.write_text(s[:start]+replacement+s[end:])
