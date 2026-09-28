#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/demos"
RAW="$DEMO/raw/civic-pathfinder-walkthrough.webm"
VOICE="$DEMO/narration.wav"
CAPTIONS="$DEMO/captions.srt"
LANDSCAPE="$DEMO/civic-pathfinder-demo.mp4"
VERTICAL="$DEMO/civic-pathfinder-social.mp4"
BG="$DEMO/vertical-bg.png"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DURATION=40.4

for f in "$RAW" "$VOICE" "$CAPTIONS"; do
  test -s "$f" || { echo "Missing required input: $f" >&2; exit 1; }
done

python3 - "$BG" <<'PY'
from PIL import Image, ImageDraw, ImageFilter
import math, sys
w,h=1080,1920
im=Image.new('RGB',(w,h))
p=im.load()
for y in range(h):
    t=y/(h-1)
    a=(11,29,43); b=(22,53,62)
    base=tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))
    for x in range(w): p[x,y]=base
# Soft civic-green and warm-amber light, kept behind the UI and copy.
glow=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(glow)
d.ellipse((610,80,1350,820), fill=(36,126,99,88))
d.ellipse((-350,1250,430,2030), fill=(226,143,69,50))
glow=glow.filter(ImageFilter.GaussianBlur(145))
im=Image.alpha_composite(im.convert('RGBA'),glow)
# Architectural arcs suggest a connected route without competing with the screen.
lines=Image.new('RGBA',(w,h),(0,0,0,0)); q=ImageDraw.Draw(lines)
for r,alpha in [(270,23),(400,17),(535,12)]:
    q.arc((w-r,140-r,w+r,140+r),205,330,fill=(205,229,215,alpha),width=2)
for i in range(7):
    x=76+i*154
    q.line((x,590,x,605),fill=(231,239,229,22),width=2)
im=Image.alpha_composite(im,lines).convert('RGB')
im.save(sys.argv[1], quality=94)
PY

# Build separate ASS tracks with explicit canvas sizes, sensible type sizes,
# and manual line wrapping. SRT defaults can scale badly on portrait canvases.
LAND_ASS="/tmp/civic-pathfinder-landscape.ass"
VERT_ASS="/tmp/civic-pathfinder-vertical.ass"
python3 - "$CAPTIONS" "$LAND_ASS" "$VERT_ASS" <<'PY'
from pathlib import Path
import re, sys, textwrap

src, *destinations = map(Path, sys.argv[1:])
blocks = re.split(r"\n\s*\n", src.read_text(encoding="utf-8").strip())
items = []
for block in blocks:
    lines = block.strip().splitlines()
    if len(lines) < 3 or "-->" not in lines[1]:
        continue
    start, end = (part.strip() for part in lines[1].split("-->"))
    text = " ".join(line.strip() for line in lines[2:])
    items.append((start, end, text))

def ass_time(value):
    hms, millis = value.split(",")
    h, m, s = (int(part) for part in hms.split(":"))
    centis = round(int(millis) / 10)
    if centis == 100:
        s += 1
        centis = 0
    if s == 60:
        m += 1
        s = 0
    return f"{h}:{m:02d}:{s:02d}.{centis:02d}"

def write_ass(path, width, height, font_size, margin, wrap_width):
    header = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}",
        f"PlayResY: {height}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H000000FF,&H900A1B25,&H900A1B25,0,0,0,0,100,100,0,0,3,5,0,2,60,60,{margin},1",
        "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for start, end, text in items:
        wrapped = "\\N".join(textwrap.wrap(text, width=wrap_width, break_long_words=False))
        wrapped = wrapped.replace("{", r"\{").replace("}", r"\}")
        header.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{wrapped}")
    path.write_text("\n".join(header) + "\n", encoding="utf-8")

write_ass(destinations[0], 1600, 900, 27, 48, 68)
write_ass(destinations[1], 1080, 1920, 32, 220, 32)
PY

# Wide hero demo: true app capture, clean editorial brand bug, accurate subtitles,
# then a restrained end slate over the final frozen dashboard frame.
ffmpeg -hide_banner -y -loglevel warning \
  -i "$RAW" -i "$VOICE" \
  -filter_complex "\
    [0:v]fps=30,scale=1600:900:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration=12,\
      drawbox=x=1250:y=75:w=308:h=36:color=#10243A@0.88:t=fill,\
      drawtext=fontfile='$BOLD':text='SAMPLE DATA / DEMO':x=1264:y=82:fontsize=16:fontcolor=white,\
      drawbox=x=0:y=0:w=1600:h=900:color=#10243A@0.94:t=fill:enable='gte(t,34.9)',\
      drawtext=fontfile='$BOLD':text='Civic Path Navigator':x=(w-text_w)/2:y=356:fontsize=52:fontcolor=white:enable='gte(t,34.9)',\
      drawtext=fontfile='$FONT':text='Find. Understand. Complete.':x=(w-text_w)/2:y=435:fontsize=34:fontcolor=#DDE9E3:enable='gte(t,34.9)',\
      drawtext=fontfile='$FONT':text='A sample sandbox walkthrough':x=(w-text_w)/2:y=500:fontsize=22:fontcolor=#C4D2D0:enable='gte(t,34.9)',\
      subtitles='$LAND_ASS'\
    [v];\
    [1:a]apad=pad_dur=1,afade=t=out:st=39.2:d=0.9[a]" \
  -map '[v]' -map '[a]' -t "$DURATION" -c:v libx264 -preset medium -crf 19 \
  -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$LANDSCAPE"

# Vertical social edit: retain the whole, readable interface inside a framed
# landscape window, with ample breathing room for title and subtitles.
ffmpeg -hide_banner -y -loglevel warning \
  -loop 1 -framerate 30 -i "$BG" -i "$RAW" -i "$VOICE" \
  -filter_complex "\
    [1:v]fps=30,scale=1000:563:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration=2,\
      pad=1016:579:8:8:color=#F2EEE5[screen];\
    [0:v][screen]overlay=(W-w)/2:662:shortest=0,\
      drawtext=fontfile='$BOLD':text='CIVIC PATH NAVIGATOR  /  SAMPLE DEMO':x=(w-text_w)/2:y=174:fontsize=24:fontcolor=#F2EEE5,\
      drawtext=fontfile='$BOLD':text='A clearer path through':x=(w-text_w)/2:y=292:fontsize=49:fontcolor=white,\
      drawtext=fontfile='$BOLD':text='public services':x=(w-text_w)/2:y=354:fontsize=49:fontcolor=white,\
      drawtext=fontfile='$BOLD':text='Find. Understand. Complete.':x=(w-text_w)/2:y=1320:fontsize=32:fontcolor=#DCE8E1,\
      subtitles='$VERT_ASS'\
    [v];\
    [2:a]apad=pad_dur=1,afade=t=out:st=39.2:d=0.9[a]" \
  -map '[v]' -map '[a]' -t "$DURATION" -c:v libx264 -preset medium -crf 20 \
  -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$VERTICAL"

printf 'Rendered:\n  %s\n  %s\n' "$LANDSCAPE" "$VERTICAL"
