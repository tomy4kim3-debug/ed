# pip install youtube-transcript-api
import re
from youtube_transcript_api import YouTubeTranscriptApi

api = YouTubeTranscriptApi()
ids = []
for line in open("links.txt", encoding="utf-8"):
    m = re.search(r"youtu\.be/([\w-]{11})", line)
    if m and m.group(1) not in ids:
        ids.append(m.group(1))

parts = []
for i, vid in enumerate(ids, 1):
    try:
        t = api.fetch(vid, languages=["ko", "en"])
        text = " ".join(s.text for s in t)
    except Exception as e:
        text = f"[자막 가져오기 실패: {e}]"
    parts.append(f"\n\n==== [{i:02d}] https://youtu.be/{vid} ====\n\n{text}")
    print("처리", i, vid)

# 1) 전체 합본
open("전체합본.txt", "w", encoding="utf-8").write("".join(parts))

# 2) 5편씩 묶음
for b in range(0, len(parts), 5):
    n = b // 5 + 1
    open(f"묶음{n}.txt", "w", encoding="utf-8").write("".join(parts[b:b+5]))