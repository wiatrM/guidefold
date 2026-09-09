#!/usr/bin/env bash
set -u
cd /home/mike/projects/guidefold/ui
D=design/landing/imagegen
gen(){ id=$1; shift; refs="$@"; 
  higgsfield generate create gpt_image_2 --prompt "$(cat $D/$id.hf.txt)" --aspect_ratio 16:9 --resolution 2k --quality high --background opaque $refs --wait --wait-timeout 15m --wait-interval 8s --json > $D/$id.job.json 2> $D/$id.err
  url=$(node -e 'const s=require("fs").readFileSync(process.argv[1],"utf8");const m=s.match(/https?:\/\/[^"\s]+\.(png|jpg|jpeg|webp)[^"\s]*/i);console.log(m?m[0]:"")' $D/$id.job.json)
  if [ -n "$url" ]; then curl -fsSL "$url" -o $D/$id.png && echo "$id OK $(identify -format '%wx%h' $D/$id.png 2>/dev/null || ffprobe -v error -show_entries stream=width,height -of csv=p=0 $D/$id.png)"; else echo "$id NOURL"; head -c 400 $D/$id.err; head -c 600 $D/$id.job.json; fi
}
gen hero-keyframe --image-references public/assets/guidefold-stone-hero-v1.webp --image-references public/assets/landing/topographic-route-bg.webp &
gen plane-why --image-references public/assets/guidefold-paper-fold-film.webp --image-references public/assets/landing/topographic-route-bg.webp &
gen plane-how --image-references public/assets/guidefold-paper-fold-film.webp --image-references public/assets/landing/topographic-route-bg.webp &
gen plane-value --image-references public/assets/guidefold-stone-hero-v1.webp --image-references public/assets/landing/topographic-route-bg.webp &
wait
echo ALL_IMAGES_DONE; ls -la $D/*.png 2>&1
