# -*- coding: utf-8 -*-
"""
아가서 강해 자막 저장 스크립트 (개인 열람용)

사용법 (Windows 명령 프롬프트 또는 PowerShell):
    python -m pip install -U yt-dlp
    python aga_transcripts.py --only 1      # 1강만 먼저 테스트
    python aga_transcripts.py               # 전체 실행

옵션:
    --force                        이미 있는 파일도 다시 받기
    --cookies-from-browser chrome  YouTube 차단/로그인 요구가 뜰 때 사용
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("먼저 설치하세요:  python -m pip install -U yt-dlp")

OUT_DIR = Path(r"C:\Users\eded7\OneDrive\Desktop\아가서")

# 목록 순서 = 강의 번호라고 가정했습니다. 각 파일 맨 위에 영상 제목을 적으니 꼭 확인하세요.
# 36번째 영상 ID는 아직 확인되지 않아 비워 두었습니다. 찾으면 아래 빈 칸에 넣으세요.
VIDEO_IDS = [
    "z69f8wVDWJk", "VUjxhTejwYQ", "lxY7Eahaf30", "WZqFEE-dwus", "Zzq596-cf58",
    "AYSoFmX1fJM", "glg_mKfXQKY", "ed14Cjf39ak", "8r0moukkePc", "P7wsC7_UQj0",
    "wOZWPj8WKok", "aoR12_nYKio", "r6MiGXkPXUE", "P38r6s5ySVw", "rXbi_h8guAs",
    "uF3LCc-jDuM", "_lOlc2_KJoE", "ktkT4cdhPGU", "jMFfLuaAI3U", "C-1I1ugOVDA",
    "T3YxJ46CPws", "cnYJj7OoMC8", "ZYOEOvFSoZU", "NZQBUQ4EdEU", "qca7ttD-fuc",
    "zosKYUhCxQM", "QgX1NCmWxdc", "ZGXf7aAEqwc", "7Oobr2EXQvs", "zHRLX0McT7E",
    "a3uciKyZnPY", "vVg0gFNTLgI", "MHG8A868eoA", "sUgFQVKnZyc", "_Z_4xL3ny84",
    "",  # 36강
]


def pick_track(info):
    """한국어 자막(수동 우선, 없으면 자동)의 json3 주소를 찾는다."""
    for source, label in (("subtitles", "수동 자막"), ("automatic_captions", "자동 자막")):
        tracks = info.get(source) or {}
        for lang, formats in tracks.items():
            if lang.split("-")[0] != "ko":
                continue
            for fmt in formats:
                if fmt.get("ext") == "json3":
                    return fmt["url"], label
    return None, None


def json3_to_text(raw):
    data = json.loads(raw)
    lines = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, help="이 번호의 강만 실행 (예: 1)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cookies-from-browser", dest="browser")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    if args.browser:
        opts["cookiesfrombrowser"] = (args.browser,)

    missing, failed = [], []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for n, vid in enumerate(VIDEO_IDS, start=1):
            if args.only and n != args.only:
                continue
            out = OUT_DIR / f"{n:03d}.txt"
            if not vid:
                print(f"[{n:03d}] 영상 ID가 비어 있어 건너뜀")
                failed.append(n)
                continue
            if out.exists() and not args.force:
                print(f"[{n:03d}] 이미 있음, 건너뜀")
                continue
            url = f"https://www.youtube.com/watch?v={vid}"
            try:
                info = ydl.extract_info(url, download=False)
                track_url, label = pick_track(info)
                if not track_url:
                    print(f"[{n:03d}] 한국어 자막 없음: {info.get('title')}")
                    missing.append(n)
                    continue
                text = json3_to_text(fetch(track_url))
                header = f"제목: {info.get('title')}\n주소: {url}\n자막 종류: {label}\n\n"
                out.write_text(header + text + "\n", encoding="utf-8-sig")
                print(f"[{n:03d}] 저장 완료 ({label}) {info.get('title')}")
            except Exception as e:  # noqa: BLE001
                print(f"[{n:03d}] 실패: {e}")
                failed.append(n)
            time.sleep(3)  # 차단 방지

    print("\n=== 결과 ===")
    print("자막 없음:", missing or "없음")
    print("실패/건너뜀:", failed or "없음")
    print("저장 위치:", OUT_DIR)


if __name__ == "__main__":
    main()
