import {ArrowUpRight,ArrowRight} from '@phosphor-icons/react';
import {github} from './instruction';
import css from './landing.module.css';

export function LandingFooter({emailAction}:{emailAction:boolean}){
 return <footer className={css.footer}>
  <div className={css.footerTop}>
   <div className={css.footerIdentity}>
    <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-web.webp" width="44" height="44" alt=""/>Guidefold</a>
    <p>Instructions that stay close to the code.</p>
    <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version <ArrowUpRight aria-hidden="true"/></a>
   </div>
   <nav aria-label="Product links"><h2>Product</h2><a href={emailAction?'/#demo':'#demo'}>Play demo</a><a href="/docs/">Documentation</a><a href="/import">Sign in <ArrowRight aria-hidden="true"/></a></nav>
   <nav aria-label="Project links"><h2>Open source</h2><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a><a href={github+'#coding-harness-to-instruction-delivery'}>Integrations</a><a href={github+'#quickstart'}>Quickstart</a></nav>
   <nav aria-label="Contact links"><h2>Stay in touch</h2><a href={emailAction?'/#waitlist':'#waitlist'}>Join the waitlist</a><a href="mailto:hello@cloudfloo.io">Email us <ArrowUpRight aria-hidden="true"/></a><a href={emailAction?'/#privacy':'#privacy'}>Privacy</a></nav>
  </div>
  <div className={css.wordmark} aria-hidden="true">Guidefold<span>.</span></div>
  <div className={css.footerBottom}><span>Open-source tools. Hosted service planned.</span><span>Built by Cloudfloo</span></div>
 </footer>;
}
