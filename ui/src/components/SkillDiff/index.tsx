import {StateBadge} from '../StateBadge';
import {lineDiff} from '../../domain/diff';
import css from './SkillDiff.module.css';

export function SkillDiff({source,candidate}:{source:string;candidate:string}){
 if(source===candidate)return <p className={css.diffQuiet}><StateBadge>No text changes</StateBadge> The candidate matches the exact imported file.</p>;
 return <div className={css.diff}><p>+ Added lines · − Removed lines</p><pre tabIndex={0} aria-label="Source to candidate line diff">{lineDiff(source,candidate).split('\n').map((line,i)=><span key={i} className={line.startsWith('+')?css.diffAdded:line.startsWith('−')?css.diffRemoved:undefined}>{line}{'\n'}</span>)}</pre></div>;
}
