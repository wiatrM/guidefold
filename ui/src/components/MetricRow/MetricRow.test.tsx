import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {MetricRow} from './index';

describe('MetricRow',()=>{
 it('keeps Unknown distinct from an observed zero and preserves the evidence explanation',()=>{
  const {container}=render(<MetricRow items={[
   {label:'Delivery',value:'Unknown',detail:'No adapter event ledger'},
   {label:'Observed outcomes',value:'0',detail:'No assessments in the declared window'}
  ]}/>);
  const terms=Array.from(container.querySelectorAll('dt'));
  expect(terms.map(term=>term.textContent)).toEqual(['Delivery','Observed outcomes']);
  expect(terms[0].nextElementSibling?.textContent).toBe('UnknownNo adapter event ledger');
  expect(terms[1].nextElementSibling?.textContent).toBe('0No assessments in the declared window');
  expect(screen.getByText('No adapter event ledger')).toBeInTheDocument();
 });
 it('updates values from props without deriving an unsupported success rate',()=>{
  const {rerender,container}=render(<MetricRow items={[{label:'Delivery',value:'Unknown',detail:'No observations'}]}/>);
  rerender(<MetricRow items={[{label:'Delivery',value:'1',detail:'One declared test event'}]}/>);
  expect(screen.queryByText('Unknown')).not.toBeInTheDocument();
  expect(container.querySelector('dd')?.firstChild?.textContent).toBe('1');
  expect(container.querySelector('dl')?.textContent).not.toContain('%');
 });
 it('the funnel layout is a class on the same list, not a second component',()=>{
  const {container}=render(<MetricRow layout="funnel" items={[{label:'Exposed',value:'12',detail:'Cards placed into context'}]}/>);
  const list=container.querySelector('dl');
  expect(list?.className).toMatch(/funnel/);
  expect(container.querySelectorAll('dt')).toHaveLength(1);
 });
});
