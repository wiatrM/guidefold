import {Reveal} from './Reveal';
import css from './landing.module.css';

/**
 * A real screen of the product in a thin frame: hairline border, the panel radius, one
 * shadow token, and a plain caption underneath saying what the screen is. Every capture
 * on this page comes from the hosted UI running against the Meridian example repository,
 * so the caption names the fixture rather than implying a customer's production data.
 *
 * The intrinsic size is on the element, so the frame reserves its box before the file
 * decodes: nothing on this page is allowed to shift when a screenshot lands.
 */
export function DeviceFrame({src,alt,caption,eager}:{
 src:string;
 alt:string;
 caption:string;
 eager?:boolean;
}){
 return <figure className={css.deviceFigure}>
  <Reveal pattern="p3" as="div" className={css.deviceFrame}>
   <img className={css.deviceShot} src={src} alt={alt} width="2880" height="1800"
    loading={eager?'eager':'lazy'} decoding="async"/>
  </Reveal>
  <figcaption className={css.deviceCaption}>{caption}</figcaption>
 </figure>;
}
