from pathlib import Path
p=Path('s06-tables.mjs');s=p.read_text().replace("p.getByRole('region').filter({has:p.locator('table')}).first()","p.locator('div[role=\"region\"][tabindex=\"0\"]').filter({has:p.locator('table')}).first()")
s=s.replace("await table.scrollIntoViewIfNeeded();await table.focus();","await expect(table.locator('tbody tr').first()).toBeVisible();await expect(table.locator('table')).toHaveCSS('min-width','640px');\n  await table.scrollIntoViewIfNeeded();await table.focus();")
s=s.replace("if(before.width>before.client){","if(width<=820&&before.width<=before.client)throw Error('Expected narrow table overflow is missing');\n  if(before.width>before.client){")
s=s.replace("results.push({view,width,table:before,keyboardScroll:before.width>before.client?'verified':'not needed',pageOverflow:overflow});","results.push({view,width,table:before,scrollAfter:await table.evaluate(e=>e.scrollLeft),keyboardScroll:before.width>before.client?'verified':'not needed',pageOverflow:overflow});")
p.write_text(s)
