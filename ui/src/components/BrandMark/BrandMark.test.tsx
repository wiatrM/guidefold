import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {BrandMark} from './index';

describe('BrandMark',()=>{
 it('names the product once and uses the original decorative raster',()=>{
  render(<BrandMark/>);
  expect(screen.getByText('Guidefold')).toBeVisible();
  const raster=screen.getByRole('presentation');
  expect(raster).toHaveAttribute('src','/assets/guidefold-mark.png');
  expect(raster).toHaveAttribute('alt','');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
 });
});
