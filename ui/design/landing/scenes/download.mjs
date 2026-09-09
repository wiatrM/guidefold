/** Downloads every completed scene job in this directory to <id>.png. */
import {readFileSync, writeFileSync, readdirSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
for (const file of readdirSync(here).filter((f) => f.endsWith('.job.json'))) {
  const job = JSON.parse(readFileSync(join(here, file), 'utf8'));
  const record = Array.isArray(job) ? job[0] : job;
  if (!record.result_url) {console.log(file, 'no result_url', record.status); continue;}
  const response = await fetch(record.result_url);
  if (!response.ok) {console.log(file, response.status); continue;}
  const out = file.replace('.job.json', '.png');
  writeFileSync(join(here, out), Buffer.from(await response.arrayBuffer()));
  console.log(out, 'saved');
}
