import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen,waitFor,fireEvent,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import Landing from './landing';
import {submitWaitlist,WaitlistError} from '../data/waitlist';

vi.mock('../data/waitlist',async original=>({...await original<typeof import('../data/waitlist')>(),submitWaitlist:vi.fn()}));

const realMatchMedia=window.matchMedia;
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({
  matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false,
 })) as unknown as typeof window.matchMedia;
}
let errors:unknown[][];
beforeEach(()=>{errors=[];vi.spyOn(console,'error').mockImplementation((...args)=>{errors.push(args);});});
afterEach(()=>{vi.restoreAllMocks();vi.clearAllMocks();window.matchMedia=realMatchMedia;window.history.replaceState(null,'','/');});

async function fill(){
 const user=userEvent.setup();
 await user.type(screen.getByLabelText('Your email'),'person@example.test');
 await user.click(screen.getByRole('checkbox'));
 return user;
}

describe('public landing',()=>{
 it('has no structural axe violations (contrast requires browser layout)',async()=>{
  const {container}=render(<Landing/>);
  const result=await axe.run(container,{rules:{'color-contrast':{enabled:false}}});
  expect(result.violations).toEqual([]);
  expect(errors).toEqual([]);
 });

 it('answers why, then how, then value, under one h1',()=>{
  render(<Landing/>);
  expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1);
  const headings=screen.getAllByRole('heading',{level:2}).map(node=>node.textContent);
  expect(headings.slice(0,3)).toEqual(["Let's not make every team rediscover this from scratch",'What Guidefold does about it','What your team gets']);
  expect(headings.indexOf('Want to know when hosting is ready?')).toBeGreaterThan(headings.indexOf('What your team gets'));
  expect(headings.indexOf('Things you are probably wondering')).toBeGreaterThan(headings.indexOf('Want to know when hosting is ready?'));
 });

 it('keeps every protected destination and the availability statements',()=>{
  const {container}=render(<Landing/>);
  const href=(selector:string)=>container.querySelector(selector);
  expect(href('a[href="#how-it-works"]')).toBeInTheDocument();
  expect(href('a[href="#waitlist"]')).toBeInTheDocument();
  expect(href('a[href="#demo"]')).toBeInTheDocument();
  expect(href('a[href="#privacy"]')).toBeInTheDocument();
  expect(href('a[href="/docs/"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold#quickstart"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold#coding-harness-to-instruction-delivery"]')).toBeInTheDocument();
  expect(href('a[href="mailto:hello@cloudfloo.io"]')).toBeInTheDocument();
  expect(container.querySelector('#demo')).toBeInTheDocument();
  expect(container.querySelector('#waitlist')).toBeInTheDocument();
  for(const id of ['question-1','question-2','question-3','privacy'])expect(container.querySelector('#'+id)).toBeInTheDocument();
  expect(screen.getByText('Open source today.')).toBeInTheDocument();
  expect(screen.getByText('Hosting is planned.')).toBeInTheDocument();
  expect(screen.getByText('Open-source tools. Hosted service planned.')).toBeInTheDocument();
  expect(document.title).toBe('Guidefold | Team instructions for coding agents');
  expect(screen.getByRole('link',{name:'Skip to content'})).toHaveAttribute('href','#main');
 });

 it('keeps all four answers in the DOM with every panel closed on load',()=>{
  render(<Landing/>);
  for(const question of ['Can I use it today?','What will hosting cost?','Does it work with the tool my team already uses?','How is my email used?'])
   expect(screen.getByRole('button',{name:question})).toHaveAttribute('aria-expanded','false');
  expect(screen.getByText(/\$99 per organisation per month/)).toBeInTheDocument();
  expect(screen.getByText(/Unconfirmed signups are scheduled for deletion after 30 days/)).toBeInTheDocument();
 });

 it('opens the privacy disclosure from a direct anchor',()=>{
  window.history.replaceState(null,'','/#privacy');
  render(<Landing/>);
  expect(screen.getByRole('button',{name:'How is my email used?'})).toHaveAttribute('aria-expanded','true');
 });

 it('makes no signup request on arrival and requires explicit consent',()=>{
  render(<Landing/>);
  expect(submitWaitlist).not.toHaveBeenCalled();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(screen.getByRole('checkbox')).toBeRequired();
  expect(screen.getByLabelText('Your email')).toBeRequired();
  expect(screen.queryByTitle('Guidefold product demo')).not.toBeInTheDocument();
 });

 it('waits for acceptance, prevents duplicate submits, then focuses confirmation',async()=>{
  let finish!:()=>void;
  vi.mocked(submitWaitlist).mockImplementation(()=>new Promise<void>(r=>{finish=r;}));
  render(<Landing/>);
  const user=await fill();
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(screen.getByRole('button',{name:'Saving…'})).toBeDisabled();
  fireEvent.submit(document.getElementById('waitlist')!);
  expect(submitWaitlist).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('status',{name:'Waitlist confirmation'})).not.toBeInTheDocument();
  finish();
  await waitFor(()=>expect(screen.getByRole('status',{name:'Waitlist confirmation'})).toHaveFocus());
  expect(submitWaitlist).toHaveBeenCalledWith('join',{email:'person@example.test',consent:true,website:''},expect.any(AbortSignal));
  expect(screen.queryByLabelText('Your email')).not.toBeInTheDocument();
 });

 it('preserves input on rate limiting and allows retry',async()=>{
  vi.mocked(submitWaitlist).mockRejectedValueOnce(new WaitlistError('limited')).mockResolvedValueOnce();
  render(<Landing/>);
  const user=await fill();
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Please try again in an hour.');
  expect(screen.getByLabelText('Your email')).toHaveValue('person@example.test');
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(await screen.findByRole('status',{name:'Waitlist confirmation'})).toHaveTextContent('Check your inbox to confirm.');
 });

 it('loads the player only after click, stops it, and restores keyboard focus',async()=>{
  render(<Landing/>);
  const user=userEvent.setup();
  await user.click(screen.getByRole('button',{name:'Play demo'}));
  expect(screen.getByTitle('Guidefold product demo')).toHaveAttribute('src','https://www.youtube-nocookie.com/embed/e350wBr1W8c?autoplay=1');
  const dialog=screen.getByRole('dialog');
  expect(within(dialog).getByRole('link',{name:/Watch on YouTube/})).toBeInTheDocument();
  await user.click(screen.getByRole('button',{name:'Stop video'}));
  await waitFor(()=>expect(screen.queryByTitle('Guidefold product demo')).not.toBeInTheDocument());
  await waitFor(()=>expect(screen.getByRole('button',{name:'Play demo'})).toHaveFocus());
 });

 it.each(['confirm','unsubscribe'] as const)('requires an explicit %s action and hides third-party content',async action=>{
  window.history.replaceState(null,'','/?'+action+'=private-token');
  vi.mocked(submitWaitlist).mockResolvedValueOnce();
  render(<Landing/>);
  expect(window.location.search).toBe('');
  expect(submitWaitlist).not.toHaveBeenCalled();
  expect(document.querySelector('img[src^="https:"]')).toBeNull();
  expect(screen.queryByRole('button',{name:'Play demo'})).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole('button',{name:action==='confirm'?'Confirm email':'Unsubscribe'}));
  expect(submitWaitlist).toHaveBeenCalledWith(action,{token:'private-token'},expect.any(AbortSignal));
  expect(await screen.findByRole('status')).toBeInTheDocument();
 });

 it('creates no video element under reduced motion and keeps the posters',()=>{
  reduceMotion(true);
  const {container}=render(<Landing/>);
  expect(container.querySelector('video')).toBeNull();
  expect(container.querySelector('img[src="/assets/landing/intro-poster.webp"]')).toBeInTheDocument();
  expect(container.querySelector('img[src="/assets/landing/hero-poster.webp"]')).toBeInTheDocument();
 });

 it('mounts the mechanism clip only when motion is allowed',()=>{
  reduceMotion(false);
  const {container}=render(<Landing/>);
  const clip=container.querySelector('video');
  expect(clip).toHaveAttribute('poster','/assets/landing/intro-poster.webp');
  expect(clip).not.toHaveAttribute('loop');
  expect(clip).toHaveAttribute('preload','none');
 });
});
