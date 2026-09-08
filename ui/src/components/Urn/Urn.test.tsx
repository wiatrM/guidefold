import {render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {Urn} from './index';

afterEach(()=>vi.restoreAllMocks());
describe('Urn',()=>{
 const value='urn:guidefold:meridian:postgres-auth';
 it('copies the entire identifier and announces success only after the clipboard resolves',async()=>{
  const user=userEvent.setup();
  let resolveCopy!:()=>void;
  const write=vi.spyOn(navigator.clipboard,'writeText').mockImplementation(()=>new Promise<void>(resolve=>{resolveCopy=resolve;}));
  render(<Urn value={value}/>);
  await user.click(screen.getByRole('button',{name:'Copy identifier'}));
  expect(write).toHaveBeenCalledWith(value);
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  resolveCopy();
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Copied identifier'));
  expect(screen.getByText(value)).toBeInTheDocument();
 });
 it('explains a clipboard failure while retaining selectable identifier text',async()=>{
  const user=userEvent.setup();
  vi.spyOn(navigator.clipboard,'writeText').mockRejectedValue(new Error('Clipboard denied'));
  render(<Urn value={value}/>);
  await user.click(screen.getByRole('button',{name:'Copy identifier'}));
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Copy unavailable. Select the identifier text.'));
  expect(screen.getByText(value).tagName).toBe('CODE');
  expect(screen.queryByText('Copied identifier')).not.toBeInTheDocument();
 });
});
