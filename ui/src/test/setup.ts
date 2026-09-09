import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';
// jsdom has no layout, so the shell's scroll reset would log "Not implemented".
window.scrollTo=()=>{};
// jsdom does not implement browser media queries. Keep the browser-shaped API;
// real reduced-motion behavior is exercised by Playwright.
if(!window.matchMedia)window.matchMedia=(media:string)=>({
 matches:false,media,onchange:null,addListener:()=>{},removeListener:()=>{},
 addEventListener:()=>{},removeEventListener:()=>{},dispatchEvent:()=>false,
});
afterEach(()=>cleanup());
