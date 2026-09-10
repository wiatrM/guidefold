import {useEffect,useState} from 'react';
import {ArrowDownIcon} from '@phosphor-icons/react';
import css from './landing.module.css';

/**
 * A hint that the page keeps going, not a control: aria-hidden, no click
 * handler, gone the instant the visitor scrolls at all so it never competes
 * with real content, and never rendered under reduced motion or Save-Data
 * (the CSS reduced-motion block hides it outright; this only handles the
 * "has the visitor scrolled" half).
 */
export function ScrollCue(){
 const [scrolled,setScrolled]=useState(false);
 useEffect(()=>{
  if(window.scrollY>0){setScrolled(true);return;}
  const onScroll=()=>{setScrolled(true);window.removeEventListener('scroll',onScroll);};
  window.addEventListener('scroll',onScroll,{passive:true});
  return()=>window.removeEventListener('scroll',onScroll);
 },[]);
 return <div className={css.cue} data-hidden={scrolled||undefined} aria-hidden="true">
  <span>Scroll</span>
  <ArrowDownIcon weight="bold" className={css.cueIcon}/>
 </div>;
}
