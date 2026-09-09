#!/usr/bin/env bash
set -u
cd /home/mike/projects/guidefold/ui/design/landing/scenes
NEG="$(cat negatives.txt)"
gen(){ id=$1
  higgsfield generate create gpt_image_2 --prompt "$(cat $id.txt) Strictly avoid: $NEG. No text, letters, numbers or logos anywhere in the image." \
    --aspect_ratio 16:9 --resolution 2k --quality high --background opaque \
    --image-references /home/mike/projects/guidefold/ui/public/assets/landing/topographic-route-bg.webp \
    --wait --wait-timeout 15m --wait-interval 8s --json > $id.job.json 2> $id.err
  url=$(node -e 'const s=require("fs").readFileSync(process.argv[1],"utf8");const m=s.match(/https?:\/\/[^"\s]+\.(png|jpg|jpeg|webp)[^"\s]*/i);console.log(m?m[0]:"")' $id.job.json)
  if [ -n "$url" ]; then node -e "const [u,o]=process.argv.slice(1);const r=await fetch(u);require('fs').writeFileSync(o,Buffer.from(await r.arrayBuffer()));console.log(o,'saved')" "$url" "$id.png"; else echo "$id NOURL"; head -c 300 "$id.err"; fi
}
for s in scene-1 scene-2 scene-3 scene-4 scene-5; do gen $s & done
wait
echo SCENES_DONE
ls -la *.png 2>&1
