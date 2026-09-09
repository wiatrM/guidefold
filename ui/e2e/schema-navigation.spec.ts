import {test,expect} from '@playwright/test';
import {stubApi,query,axeViolations,noHorizontalScroll} from './stub';

test('fold navigation, profile, context actions and Sonner favorites',async({page})=>{
 await stubApi(page);
 await page.goto('/library'+query());
 await page.getByRole('button',{name:'Collapse sidebar'}).click();
 await expect(page.getByRole('button',{name:'Expand sidebar'})).toBeVisible();
 await page.getByRole('button',{name:'Expand sidebar'}).click();
 await page.getByRole('button',{name:'Open profile menu'}).click();
 await expect(page.getByRole('menuitem',{name:'Profile and organization'})).toBeVisible();
 await expect(page.getByRole('menuitem',{name:'Sign out',exact:true})).toBeVisible();
 expect(await axeViolations(page)).toEqual([]);
 await page.keyboard.press('Escape');
 const favorite=page.getByRole('button',{name:'Add adr-process to favorites',exact:true});
 await favorite.click();
 await expect(page.locator('[data-sonner-toast]').filter({hasText:'Added to favorites'})).toBeVisible();
 await page.reload();
 await expect(page.getByRole('button',{name:'Remove adr-process from favorites',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('link',{name:'adr-process',exact:true}).click({button:'right'});
 await expect(page.getByRole('menu')).toBeVisible();
 expect(await axeViolations(page)).toEqual([]);
 await page.keyboard.press('Escape');
 await page.screenshot({path:'qa/navigation-redesign/previews/library-desktop.png'});
});

test('real schema engine draws connectors and offers a keyboard list alternative',async({page})=>{
 await page.goto('/__components');
 const chart=page.locator('[data-component="PyramidChart"]');
 await chart.scrollIntoViewIfNeeded();
 await expect(chart.locator('[data-slot="database-schema-node"]')).toHaveCount(4);
 await expect(chart.locator('.react-flow__edge')).toHaveCount(3);
 await expect(chart.locator('[data-slot="schema-flow"]')).toHaveAttribute('data-animated','false');
 await expect(chart.getByRole('button',{name:'Play flow animation'})).toBeDisabled();
 await chart.getByRole('button',{name:'List',exact:true}).click();
 await expect(chart.locator('[aria-current="true"]')).toBeVisible();
 await chart.getByRole('button',{name:'Graph',exact:true}).click();
 expect(await noHorizontalScroll(page)).toBe(true);
 await chart.screenshot({path:'qa/navigation-redesign/previews/schema-desktop.png'});
});
