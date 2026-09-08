import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {ProvenanceTrail} from './index';

describe('ProvenanceTrail',()=>{
 it('associates source terms with their values and explanatory details',()=>{
  render(<ProvenanceTrail entries={[{label:'Scope',value:'data',detail:'Declared source scope'},{label:'Observation',value:<strong>Unknown</strong>}]}/>);
  const term=screen.getByText('Scope');
  expect(term.tagName).toBe('DT');
  expect(term.nextElementSibling?.tagName).toBe('DD');
  expect(term.nextElementSibling).toHaveTextContent('dataDeclared source scope');
  expect(screen.getByText('Observation').nextElementSibling).toHaveTextContent('Unknown');
 });
 it('preserves the exact source URL and opens it with isolation',()=>{
  const source='https://github.com/wiatrM/guidefold/blob/88e404561a9f6994cd870743bf858b9b0a616126/examples/monorepo/README.md';
  render(<ProvenanceTrail entries={[{label:'Source',value:'README.md',href:source,code:true}]}/>);
  const link=screen.getByRole('link',{name:'README.md'});
  expect(link).toHaveAttribute('href',source);
  expect(link).toHaveAttribute('target','_blank');
  expect(link).toHaveAttribute('rel','noopener noreferrer');
 });
 it('does not synthesize missing evidence',()=>{
  render(<ProvenanceTrail entries={[]}/>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.queryByText('Published')).not.toBeInTheDocument();
 });
});
