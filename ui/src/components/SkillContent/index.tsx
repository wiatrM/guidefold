import Markdown from 'react-markdown';
import css from './SkillContent.module.css';

export function SkillContent({content}:{content:string}){return <div className={css.markdown}><Markdown skipHtml components={{h1:({children})=><h3>{children}</h3>,h2:({children})=><h4>{children}</h4>,h3:({children})=><h5>{children}</h5>,pre:({children})=><pre tabIndex={0} aria-label="Code example">{children}</pre>,a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt})=><span>{alt||'Image reference'}</span>}}>{content}</Markdown></div>;}
