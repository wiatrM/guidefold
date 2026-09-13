import css from './ShimmerSkeleton.module.css';

/**
 * Loading shimmer (ADR-0049): a highlight sweeps across each placeholder line. Purely
 * decorative and already loading, so it is aria-hidden rather than announced; the route's own
 * loading state carries the accessible text (RouteState). The sweep's duration collapses to
 * 0ms under reduced motion (tokens.css), leaving a static two-tone block.
 */
export function ShimmerSkeleton({lines=1,className}:{lines?:number;className?:string}){
 return <div aria-hidden="true" data-slot="shimmer-skeleton" className={[css.stack,className].filter(Boolean).join(' ')}>
  {Array.from({length:lines}).map((_,i)=><div key={i} className={css.line}/>)}
 </div>;
}
