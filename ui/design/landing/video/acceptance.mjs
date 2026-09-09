/**
 * Acceptance probe for the hero loop: copy-safe luminance per sampled frame, loop-seam
 * difference between the first and last frame, and drift of the composition between
 * frames. Reads PNG frames extracted next to this script by ffmpeg.
 */
import {PNG} from 'pngjs';
import {readFileSync, readdirSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, 'frames');
const files = readdirSync(dir).filter((f) => f.endsWith('.png')).sort();
const srgb = (c) => {const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;};
const lum = (r, g, b) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);

const frames = files.map((f) => ({name: f, png: PNG.sync.read(readFileSync(join(dir, f)))}));
const {width, height} = frames[0].png;
const box = {x0: 0, x1: Math.round(width * 0.55), y0: Math.round(height * 0.16), y1: Math.round(height * 0.84)};

const rows = frames.map(({name, png}) => {
  let max = 0, sum = 0, n = 0;
  for (let y = box.y0; y < box.y1; y += 2) {
    for (let x = box.x0; x < box.x1; x += 2) {
      const i = (png.width * y + x) << 2;
      const l = lum(png.data[i], png.data[i + 1], png.data[i + 2]);
      max = Math.max(max, l); sum += l; n++;
    }
  }
  return {frame: name, copySafeMaxLuminance: +(max * 100).toFixed(1), copySafeMeanLuminance: +((sum / n) * 100).toFixed(1)};
});

const diff = (a, b) => {
  let changed = 0, total = 0, worst = 0;
  for (let y = 0; y < height; y += 3) {
    for (let x = 0; x < width; x += 3) {
      const i = (width * y + x) << 2;
      const d = Math.abs(a.data[i] - b.data[i]) + Math.abs(a.data[i + 1] - b.data[i + 1]) + Math.abs(a.data[i + 2] - b.data[i + 2]);
      if (d > 24) changed++;
      worst = Math.max(worst, d); total++;
    }
  }
  return {changedPixelPercent: +((changed / total) * 100).toFixed(2), worstChannelSum: worst};
};

console.log(JSON.stringify({
  frames: rows,
  loopSeam: diff(frames[0].png, frames[frames.length - 1].png),
  midDrift: diff(frames[0].png, frames[Math.floor(frames.length / 2)].png),
}, null, 1));
