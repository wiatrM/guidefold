import {ArrowUpRight,ArrowRight} from '@phosphor-icons/react';
import {RevealGroup} from './Reveal';
import {github} from './instruction';
import css from './landing.module.css';

/**
 * Footer, DESIGN.md 3.9. Closes section 9 rather than opening a tenth: four link groups
 * on `--landing-footer-columns` (identity plus three navs), the protected bottom line,
 * its own "Try the open-source version" link and the large wordmark. The four groups get
 * the P1 list-row entrance; the wordmark and the bottom line stay plain, since one of them
 * carries `aria-hidden` and `Reveal` does not forward arbitrary attributes.
 */
export function LandingFooter({emailAction}:{emailAction:boolean}){
 return <footer className={css.footer}>
  <RevealGroup pattern="p1" as="div" className={css.footerTop}>
   <div className={css.footerIdentity}>
    <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-web.webp" width="44" height="44" alt=""/>Guidefold</a>
    <p>Instructions that stay close to the code.</p>
    <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version <ArrowUpRight aria-hidden="true"/></a>
   </div>
   <nav aria-label="Product links"><h2>Product</h2><a href={emailAction?'/#demo':'#demo'}>Play demo</a><a href="/docs/">Documentation</a><a href="/import">Sign in <ArrowRight aria-hidden="true"/></a></nav>
   <nav aria-label="Project links"><h2>Open source</h2><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a><a href={github+'#coding-harness-to-instruction-delivery'}>Integrations</a><a href={github+'#quickstart'}>Quickstart</a></nav>
   <nav aria-label="Contact links"><h2>Stay in touch</h2><a href={emailAction?'/#waitlist':'#waitlist'}>Join the waitlist</a><a href="mailto:hello@cloudfloo.io">Email us <ArrowUpRight aria-hidden="true"/></a><a href={emailAction?'/#privacy':'#privacy'}>Privacy</a></nav>
  </RevealGroup>
  <div className={css.wordmark} aria-hidden="true">Guidefold<span>.</span></div>
  <div className={css.footerBottom}><span>Open-source tools. Hosted service planned.</span><span>Built by Cloudfloo</span></div>
 </footer>;
}
