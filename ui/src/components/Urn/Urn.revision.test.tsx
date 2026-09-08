import {act,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,it,expect,vi} from 'vitest';
import {Urn} from './index';
afterEach(()=>vi.restoreAllMocks());
it('clears copied status when the displayed identifier changes',async()=>{
 const user=userEvent.setup();vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();
 const {rerender}=render(<Urn value="urn:source:a"/>);
 await user.click(screen.getByRole('button',{name:'Copy identifier'}));
 expect(screen.getByRole('status')).toHaveTextContent('Copied identifier');
 rerender(<Urn value="urn:source:b"/>);
 expect(screen.getByRole('status')).toBeEmptyDOMElement();
});
it('ignores a clipboard completion for an identifier that is no longer displayed',async()=>{
 const user=userEvent.setup();let finish!:()=>void;
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(()=>new Promise<void>(resolve=>{finish=resolve;}));
 const {rerender}=render(<Urn value="urn:source:a"/>);
 await user.click(screen.getByRole('button',{name:'Copy identifier'}));
 rerender(<Urn value="urn:source:b"/>);
 await act(async()=>{finish();});
 expect(screen.getByRole('status')).toBeEmptyDOMElement();
 expect(screen.getByText('urn:source:b')).toBeInTheDocument();
});
