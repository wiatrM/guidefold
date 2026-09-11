import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import Landing from '../landing';

const PROTECTED=[
 'Skip to content',
 'Open source today.','CLI and retrieval service.',
 'Paid hosting is planned.','Sign up for availability updates.',
 'Open-source tools. Hosted service planned.',
 'Instructions that stay close to the code.',
 'Your email','Join the waitlist','Play demo',
 'Is Guidefold available now?','What will hosting cost?','Which coding tools can I use?','How is my email used?',
];

describe('preservation contract',()=>{
 it('keeps every protected string verbatim',()=>{
  render(<Landing/>);
  for(const text of PROTECTED)expect(screen.getAllByText(text,{exact:true}).length).toBeGreaterThan(0);
 });

 it('keeps the pricing figures unrounded and unlifted',()=>{
  render(<Landing/>);
  expect(screen.getByText(/\$99 per organisation per month, excluding taxes\./)).toBeInTheDocument();
  expect(screen.getByText(/\$9 of provider usage costs \$10/)).toBeInTheDocument();
  expect(screen.getByText(/There is no unlimited AI allowance\./)).toBeInTheDocument();
  expect(screen.getByText(/Enterprise SSO is not included/)).toBeInTheDocument();
 });

 it('keeps the full privacy answer including both deletion schedules',()=>{
  render(<Landing/>);
  expect(screen.getByText(/Unconfirmed signups are scheduled for deletion after 30 days/)).toBeInTheDocument();
  expect(screen.getByText(/deletion 365 days after signup/)).toBeInTheDocument();
  expect(screen.getByText(/a deduplication hash is retained until deletion/)).toBeInTheDocument();
 });

 it('keeps both required instances of the hosting statement',()=>{
  render(<Landing/>);
  expect(screen.getAllByText('Paid hosting is planned.',{exact:true}).length).toBe(1);
  expect(screen.getAllByText('Paid hosting is planned. Sign up for availability updates.',{exact:true}).length).toBe(1);
 });

 it('links Try the open-source version exactly twice: section 3 and the footer',()=>{
  const {container}=render(<Landing/>);
  const links=[...container.querySelectorAll('a')].filter(a=>a.textContent==='Try the open-source version');
  expect(links).toHaveLength(2);
 });

 it('glues no directional glyph to any link label',()=>{
  const {container}=render(<Landing/>);
  for(const a of container.querySelectorAll('a'))expect(a.textContent??'').not.toMatch(/[→←↑↓➔]/);
 });
});
