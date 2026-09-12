import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {SkillContent} from './index';

describe('SkillContent',()=>{
 it('renders readable headings, lists and keyboard-focusable code without changing the content',()=>{
  render(<SkillContent content={'# Database access\n\nUse **scoped credentials**.\n\n- Read the source\n- Check the revision\n\n```sh\nguidefold load postgres-auth\n```'}/>);
  expect(screen.getByRole('heading',{level:3,name:'Database access'})).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(2);
  expect(screen.getByText('scoped credentials').tagName).toBe('STRONG');
  const code=screen.getByLabelText('Code example');
  expect(code).toHaveAttribute('tabindex','0');
  expect(code).toHaveTextContent('guidefold load postgres-auth');
 });
 it('rejects raw HTML, unsafe URLs and image fetching while retaining safe visible text',()=>{
  const content='Visible text\n\n<script>alert(1)</script>\n\n<img src="https://example.test/tracker" onerror="alert(1)">\n\n[Unsafe](javascript:alert%281%29)\n\n![Source diagram](https://example.test/diagram.png)';
  const {container}=render(<SkillContent content={content}/>);
  expect(screen.getByText('Visible text')).toBeInTheDocument();
  expect(container.querySelector('script,img,[onerror]')).toBeNull();
  const unsafe=screen.getByText('Unsafe').closest('a')!;
  expect(unsafe.getAttribute('href')||'').not.toMatch(/^javascript:/i);
  expect(screen.getByText('Source diagram')).toBeInTheDocument();
 });
 it('preserves an explicit source link and prevents opener access',()=>{
  render(<SkillContent content="[Source](https://github.com/wiatrM/guidefold/blob/main/README.md)"/>);
  const link=screen.getByRole('link',{name:'Source'});
  expect(link).toHaveAttribute('href','https://github.com/wiatrM/guidefold/blob/main/README.md');
  expect(link).toHaveAttribute('target','_blank');
  expect(link).toHaveAttribute('rel','noopener noreferrer');
 });
});

describe('SkillContent frontmatter',()=>{
 it('keeps YAML frontmatter as folded exact text instead of a heading',async()=>{
  const {default:userEvent}=await import('@testing-library/user-event');
  render(<SkillContent content={'---\nname: adr-process\ndescription: "How Meridian records decisions"\n---\n\n# ADR process\n\nWrite an ADR when a change crosses a platform.'}/>);
  expect(screen.getByRole('heading',{level:3,name:'ADR process'})).toBeInTheDocument();
  expect(screen.queryByRole('heading',{name:/name: adr-process/})).not.toBeInTheDocument();
  const trigger=screen.getByRole('button',{name:/Frontmatter/});
  expect(trigger).toHaveTextContent('2 lines');
  await userEvent.click(trigger);
  expect(screen.getByLabelText('Frontmatter')).toHaveTextContent('name: adr-process');
 });
 it('renders content without frontmatter unchanged',()=>{
  render(<SkillContent content={'Plain body'}/>);
  expect(screen.getByText('Plain body')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Frontmatter/})).not.toBeInTheDocument();
 });
});
