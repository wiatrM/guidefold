import {render} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {ShimmerSkeleton} from './index';

describe('ShimmerSkeleton',()=>{
 it('is decorative and renders the requested number of lines',()=>{
  const {container}=render(<ShimmerSkeleton lines={3}/>);
  const stack=container.querySelector('[data-slot=shimmer-skeleton]');
  expect(stack).toHaveAttribute('aria-hidden','true');
  expect(stack?.children).toHaveLength(3);
 });
 it('defaults to a single line',()=>{
  const {container}=render(<ShimmerSkeleton/>);
  expect(container.querySelector('[data-slot=shimmer-skeleton]')?.children).toHaveLength(1);
 });
});
