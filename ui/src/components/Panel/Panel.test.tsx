import {render,screen,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {Panel} from './index';

describe('Panel',()=>{
 it('creates uniquely named regions even when titles repeat',()=>{
  render(<><Panel title="Source revision"><p>Imported source</p></Panel><Panel title="Source revision"><p>Candidate source</p></Panel></>);
  const regions=screen.getAllByRole('region',{name:'Source revision'});
  const labels=regions.map(region=>region.getAttribute('aria-labelledby'));
  expect(new Set(labels).size).toBe(2);
  for(const region of regions){
   expect(within(region).getByRole('heading',{level:2,name:'Source revision'})).toHaveAttribute('id',region.getAttribute('aria-labelledby'));
  }
 });
 it('keeps the action operable while decorative icons do not alter the region name',async()=>{
  const action=vi.fn();
  render(<Panel id="source" title="postgres-auth" eyebrow="Immutable source revision" icon={<span>Decoration</span>} action={<button onClick={action}>Open exact source revision</button>}><p>Imported body</p></Panel>);
  const region=screen.getByRole('region',{name:'postgres-auth'});
  expect(region).toHaveAttribute('id','source');
  expect(within(region).getByText('Decoration').closest('[aria-hidden]')).toHaveAttribute('aria-hidden','true');
  expect(within(region).getByText('Immutable source revision')).toBeVisible();
  await userEvent.click(within(region).getByRole('button',{name:'Open exact source revision'}));
  expect(action).toHaveBeenCalledOnce();
 });
});
