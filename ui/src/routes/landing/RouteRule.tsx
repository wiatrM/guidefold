import css from './landing.module.css';

/**
 * A decorative survey route under the three mechanism beats. It draws with scroll and
 * is redundant with the text beside it, so losing it costs nothing. Its resting state
 * is fully drawn: the base rules paint the complete route and the waypoints, and only
 * an element the sampler is actually driving (`data-p-ready`) gets the `--p` mapping.
 * That keeps no-JS, reduced motion and Save-Data on the finished composition instead of
 * the 73% that the `--p = .5` default would otherwise produce.
 */
export function RouteRule(){
 return <svg className={css.routeRule} viewBox="0 0 520 64" role="presentation" aria-hidden="true" focusable="false">
  <path className={css.routeLine} d="M6 46C60 46 90 22 150 22L250 22C320 22 340 44 400 44L514 44" fill="none"/>
  <circle className={css.waypointNear} cx="150" cy="22" r="5"/>
  <circle className={css.waypointFar} cx="400" cy="44" r="5"/>
 </svg>;
}
