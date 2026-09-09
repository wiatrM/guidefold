/** Downloads the delivered render for this job to raw.mp4 next to job.json. */
import {readFileSync, writeFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const job = JSON.parse(readFileSync(join(here, process.argv[2] ?? 'job.json'), 'utf8'));
const record = Array.isArray(job) ? job[0] : job;
const url = record.result_url;
if (!url) throw new Error('no result_url in job.json');
const response = await fetch(url);
if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
const bytes = Buffer.from(await response.arrayBuffer());
writeFileSync(join(here, process.argv[3] ?? 'raw.mp4'), bytes);
console.log('saved raw.mp4', bytes.length, 'bytes');
