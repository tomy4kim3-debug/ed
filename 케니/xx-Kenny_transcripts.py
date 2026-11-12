# -*- coding: utf-8 -*-
"""
케니 목사 설교 자막 저장 스크립트 (개인 열람용)

케니 폴더 안의 링크 목록 텍스트 파일(기본: 케니.txt)에서 유튜브 링크 30개를 읽어,
각 설교 영상의 한국어 자막을 001.txt ~ 030.txt 로 같은 폴더에 저장합니다.

사용법 (Windows 명령 프롬프트 또는 PowerShell):
    python -m pip install -U yt-dlp
    python Kenny_transcripts.py --only 1      # 1번만 먼저 테스트
    python Kenny_transcripts.py               # 전체 실행

옵션:
    --force                        이미 있는 파일도 다시 받기
    --cookies-from-browser chrome  YouTube 차단/로그인 요구가 뜰 때 사용
    --links 경로                   링크 목록 파일을 직접 지정 (기본: 케니 폴더의 케니.txt)
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("먼저 설치하세요:  python -m pip install -U yt-dlp")

# 링크 목록이 들어 있고, 자막 파일(001.txt ~ 030.txt)이 저장될 폴더
OUT_DIR = Path(r"C:\Users\eded7\OneDrive\Desktop\케니")
LINKS_FILENAME = "케니.txt"

# 링크의 순서 = 설교 번호 (첫 번째 링크 = 001, 두 번째 = 002 ...)
# 각 파일 맨 위에 영상 제목을 적으니, 번호와 설교가 맞는지 꼭 확인하세요.

VIDEO_URL_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^\s&]*&)?v=|shorts/|live/|embed/))([\w-]{11})"
)
SEPARATOR_RE = re.compile(r"^\s*-{3,}\s*$")   # '-----' 구분선 아래는 메모로 보고 읽지 않음
OUTPUT_NAME_RE = re.compile(r"^\d{3}\.txt$")  # 이미 만든 자막 파일(001.txt 등)은 링크 목록 후보에서 제외


def find_links_file(explicit):
    """링크 목록 파일을 찾는다. 지정 > 케니.txt > 폴더 안의 유일한 후보 순서."""
    if explicit:
        p = Path(explicit)
        if not p.exists():
            sys.exit(f"[오류] 링크 파일이 없습니다: {p}")
        return p

    default = OUT_DIR / LINKS_FILENAME
    if default.exists():
        return default

    candidates = []
    for p in sorted(OUT_DIR.glob("*.txt")):
        if OUTPUT_NAME_RE.match(p.name):
            continue
        try:
            text = p.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        if VIDEO_URL_RE.search(text):
            candidates.append(p)

    if len(candidates) == 1:
        print(f"[정보] {LINKS_FILENAME} 가 없어서 {candidates[0].name} 을(를) 링크 파일로 사용합니다")
        return candidates[0]
    if not candidates:
        sys.exit(f"[오류] {OUT_DIR} 안에서 유튜브 링크가 들어 있는 txt 파일을 찾지 못했습니다.\n"
                 f"       --links 경로 로 직접 지정해 주세요.")
    names = ", ".join(c.name for c in candidates)
    sys.exit(f"[오류] 링크가 들어 있는 txt 파일이 여러 개입니다: {names}\n"
             f"       --links 경로 로 사용할 파일을 지정해 주세요.")


def load_video_ids(path):
    """링크 파일에서 영상 ID를 위에서부터 순서대로 읽는다 (빈 줄은 건너뜀)."""
    raw = Path(path).read_text(encoding="utf-8-sig")
    ids = []
    for line in raw.splitlines():
        if SEPARATOR_RE.match(line):
            break
        m = VIDEO_URL_RE.search(line)
        if m:
            ids.append(m.group(1))
    return ids


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
    ap.add_argument("--only", type=int, help="이 번호의 설교만 실행 (예: 1)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cookies-from-browser", dest="browser")
    ap.add_argument("--links", help="링크 목록 txt 파일 경로 (기본: 케니 폴더의 케니.txt)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    links_file = find_links_file(args.links)
    video_ids = load_video_ids(links_file)
    print(f"[정보] 링크 파일: {links_file}")
    print(f"[정보] 읽은 링크 {len(video_ids)}개")
    if len(video_ids) != 30:
        print(f"[주의] 링크가 30개가 아닙니다 ({len(video_ids)}개). 파일 내용을 확인하세요.")
    dup = len(video_ids) - len(set(video_ids))
    if dup:
        print(f"[주의] 같은 영상 링크가 {dup}개 중복되어 있습니다. 번호는 링크 순서대로 붙습니다.")
    if not video_ids:
        sys.exit("[오류] 읽은 링크가 없습니다.")

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    if args.browser:
        opts["cookiesfrombrowser"] = (args.browser,)

    missing, failed = [], []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for n, vid in enumerate(video_ids, start=1):
            if args.only and n != args.only:
                continue
            out = OUT_DIR / f"{n:03d}.txt"
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
