import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {SkillDiff} from './index';

describe('SkillDiff',()=>{
 it('identifies exact equality without inventing a change',()=>{
  render(<SkillDiff source={'cache 30\n'} candidate={'cache 30\n'}/>);
  expect(screen.getByText('No text changes')).toBeInTheDocument();
  expect(screen.getByText(/matches the exact imported file/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Source to candidate line diff')).not.toBeInTheDocument();
 });
 it('shows source removal, candidate addition and unchanged context with an explicit legend',()=>{
  render(<SkillDiff source={'before\ncache 30\nafter'} candidate={'before\ncache 60\nafter'}/>);
  const diff=screen.getByLabelText('Source to candidate line diff');
  expect(diff.textContent).toContain('− cache 30\n');
  expect(diff.textContent).toContain('+ cache 60\n');
  expect(diff.textContent).toContain('  before\n');
  expect(diff.textContent).toContain('  after\n');
  expect(screen.getByText('+ Added lines · − Removed lines')).toBeInTheDocument();
  expect(diff).toHaveAttribute('tabindex','0');
 });
 it('treats source text as text, including markup, and detects a final newline change',()=>{
  const {container}=render(<SkillDiff source={'<script>alert(1)</script>'} candidate={'<script>alert(1)</script>\n'}/>);
  expect(container.querySelector('script')).toBeNull();
  expect(screen.queryByText('No text changes')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Source to candidate line diff').textContent).toContain('<script>alert(1)</script>');
 });
});
