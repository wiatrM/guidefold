import {StatusTracker} from '@/components/spectrumui/blocks/ai-assistants/status-tracker';
import css from './StageStatus.module.css';

export interface Stage{id:string;label:string}
/**
 * Steps-completed progress, controlled entirely by the route (no internal state, no free jump
 * to an earlier or later step). `variant="steps"` is the three-step organisation wizard header
 * (Organization -> GitHub -> Import); `variant="inline"` is the compact per-repository
 * fetch/parse/propose status inside a repository list row. One adapted
 * `@spectrumui/status-tracker` (2026-09-13) serves both places rather than a second,
 * motion-duplicating stepper implementation.
 */
export function StageStatus({stages,activeIndex,progress,detail,variant='steps',className}:{stages:Stage[];activeIndex:number;progress?:number;detail?:string;variant?:'steps'|'inline';className?:string}){
 return <div className={css.wrap} data-slot="stage-status" data-variant={variant}>
  <StatusTracker stages={stages} activeIndex={activeIndex} progress={progress} detail={detail} variant={variant==='inline'?'Minimal':'Default'} className={className}/>
 </div>;
}
