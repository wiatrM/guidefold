import {useState} from 'react';
import Markdown from 'react-markdown';
import {CaretRightIcon} from '@phosphor-icons/react';
import {Collapsible,CollapsibleTrigger,CollapsibleContent} from '@/components/ui/collapsible';
import {cn} from '@/lib/utils';
import css from './SkillContent.module.css';

/** `---` YAML frontmatter at the top of a SKILL.md. Left inline, Markdown reads the block as a
 * setext heading and prints the metadata as one bold paragraph; here it stays exact text,
 * folded by default, and the body is rendered on its own. */
export function splitFrontmatter(content:string):{frontmatter:string|null;body:string}{
 const match=/^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(content);
 if(!match)return {frontmatter:null,body:content};
 return {frontmatter:match[1],body:content.slice(match[0].length)};
}

export function SkillContent({content}:{content:string}){
 const {frontmatter,body}=splitFrontmatter(content);
 const [open,setOpen]=useState(false);
 const lines=frontmatter?frontmatter.split('\n').length:0;
 return <div className={css.markdown} data-slot="typography">
  {frontmatter!==null&&<Collapsible open={open} onOpenChange={setOpen} className={css.frontmatter} data-slot="frontmatter">
   <CollapsibleTrigger className={cn(css.frontmatterTrigger,'group inline-flex min-h-(--control-height) cursor-pointer items-center gap-2 rounded-md border-0 bg-transparent px-2 text-stone-300 hover:bg-graphite-800 hover:text-stone-100')}><CaretRightIcon aria-hidden="true" className="transition-transform group-data-[panel-open]:rotate-90"/>Frontmatter<small>{lines} {lines===1?'line':'lines'}</small></CollapsibleTrigger>
   <CollapsibleContent><pre tabIndex={0} aria-label="Frontmatter" data-slot="code-block">{frontmatter}</pre></CollapsibleContent>
  </Collapsible>}
  <Markdown skipHtml components={{h1:({children})=><h3>{children}</h3>,h2:({children})=><h4>{children}</h4>,h3:({children})=><h5>{children}</h5>,pre:({children})=><pre tabIndex={0} aria-label="Code example" data-slot="code-block">{children}</pre>,a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt})=><span>{alt||'Image reference'}</span>}}>{body}</Markdown>
 </div>;
}
