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
export function DeviceFrame({src,alt,caption,eager,whole}:{
 src:string;
 alt:string;
 caption:string;
 eager?:boolean;
 /** Show the capture whole rather than cropped to the page's letterbox. The wide blocks
   * crop, because a full screen at the full column is 900 px of document each; the hero's
   * screen sits in six columns and fits uncropped, so it is not cut. */
 whole?:boolean;
}){
 return <figure className={css.deviceFigure}>
  <Reveal pattern="p3" as="div" className={[css.deviceFrame,whole?css.deviceWhole:''].filter(Boolean).join(' ')}>
   {/* The captures are encoded at 1280x800, which is the frame's own box at the container
     * width on a 1.4x display and a third of the bytes of the 2880 original. The hero's is the
     * page's LCP element, so it is fetched eagerly and at high priority; the rest are lazy. */}
   <img className={css.deviceShot} src={src} alt={alt} width="1280" height="800"
    loading={eager?'eager':'lazy'} fetchPriority={eager?'high':'auto'} decoding="async"/>
  </Reveal>
  <figcaption className={css.deviceCaption}>{caption}</figcaption>
 </figure>;
}
