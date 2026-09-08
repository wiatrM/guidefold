import type {EvidenceEntry} from '../../domain';
import css from './ProvenanceTrail.module.css';

export function ProvenanceTrail({entries}:{entries:EvidenceEntry[]}){return <dl className={css.evidence}>{entries.map((entry,i)=><div key={entry.label+'-'+i}><dt>{entry.label}</dt><dd className={entry.code?css.mono:undefined}>{entry.href?<a href={entry.href} target="_blank" rel="noopener noreferrer">{entry.value}</a>:entry.value}{entry.detail&&<small>{entry.detail}</small>}</dd></div>)}</dl>;}
