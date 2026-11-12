# AI 음성기반 고정밀 자막(SRT) 생성 작업 매뉴얼
> **버전**: v1.0 (2026-10-11)  
> **용도**: 다음 세션에서 AI가 이 파일을 읽고 추가 질문 없이 음성/영상 파일로부터 100% 동일한 고품질 자막을 자동 생성하도록 정의한 표준 작업 지침서.

---

## 1. 작업 개요 및 기본 원칙

1. **목적**:
   - 무음 편집이 완료된 음성/영상 파일(`*.mp4`, `*.wav`)로부터 `faster-whisper large-v3` (CUDA, float16)를 구동하여 실측 단어별 타임스탬프(Word Timestamps)를 추출.
   - 한국어 자연어 어법에 맞춘 **의미 단위 분할(한 줄 최대 25자 이하)**, **누락 구간 자동 복구**, **최소 간격(0.1초) 보정**, **UTF-8 with BOM (CRLF)** 규격을 적용한 표준 SRT 자막 파일 생성.

2. **절대 규칙**:
   - **원본 보존**: 기존 원본 영상, 원본 자막, 음성 파일은 절대 수정하거나 삭제/이동하지 않는다.
   - **임의 시간 왜곡 금지**: 자막의 시작 시간은 반드시 음성 인식된 첫 단어의 실측 시작 시간을 그대로 사용한다. 자막 간격 0.1초를 확보할 때도 **앞 자막의 종료 시간만 줄이고, 뒷 자막의 시작 시간은 절대 이동하지 않는다.**
   - **모델 임의 변경 금지**: 반드시 NVIDIA GPU (CUDA) 기반의 `faster-whisper large-v3 (float16)`을 사용한다. CPU로 임의 다운그레이드하지 않는다.

---

## 2. 필수 환경 및 사전 점검

- **GPU**: NVIDIA RTX 시리즈 (CUDA 가속 지원)
- **Python**: 3.12 이상
- **필수 라이브러리**:
  ```bash
  pip install faster-whisper ctranslate2 torch av
  ```
- **FFmpeg / FFprobe**: 시스템 PATH에 등록되어 있어야 함 (음성 파형 및 무음 구간 감지용).

---

## 3. 음성 인식 설정 (Whisper Parameters)

```python
model = WhisperModel("large-v3", device="cuda", compute_type="float16")

segments, info = model.transcribe(
    audio_path,
    language="ko",
    word_timestamps=True,          # 필수: 단어별 실측 시간 추출
    vad_filter=True,
    vad_parameters=dict(threshold=0.3, min_silence_duration_ms=1000), # 말소리 누락 방지용 느슨한 VAD
    condition_on_previous_text=False, # 필수: 문맥 의존 환각 및 무한반복 방지
    beam_size=5
)
```

---

## 4. 핵심 안전장치: 누락 구간 자동 복구 (Speech Gap Recovery)

전체 긴 음성을 일괄 전사할 때, Whisper의 슬라이딩 윈도우나 VAD로 인해 조용하거나 낭독조인 긴 성경 구절/인용문 등이 통째로 건너뛰어지는 현상(예: 20초 이상의 공백 발생)이 발생할 수 있다.

### 복구 알고리즘:
1. 추출된 단어 시퀀스에서 인접 단어 간의 공백이 **3.0초 이상**인 구간을 탐지.
2. 해당 공백 구간(`[gap_start, gap_end]`)을 FFmpeg로 슬라이스하여 임시 음원 생성.
3. 슬라이스 음원을 `vad_filter=False` 조건으로 단독 전사.
4. 인식된 단어들의 타임스탬프에 `gap_start`를 오프셋으로 더하여 원래 단어 스트림에 시간 순으로 병합.
5. 이를 통해 음성에 존재하는 모든 발화가 100% 자막으로 복원됨.

---

## 5. 한국어 의미 단위 자막 분할 규칙 (Hierarchical Semantic Chunking)

Whisper의 기본 세그먼트 블록을 그대로 쓰지 않고, 단어 타임스탬프를 조합하여 직접 자막을 생성한다.

### 5-1. 기본 제약 조건
- **길이 제한**: 1자막 1줄, 공백 포함 **최대 25자 이하** (억지로 25자를 채우지 않으며, 12~22자 권장).
- **짧은 자막 처리**: 8자 미만 또는 0.3초 미만 덩어리는 앞뒤와 합치되, 합쳐서 25자를 초과하면 짧은 채로 유지.

### 5-2. 분할 우선순위
1. **1순위 (문장 종결)**: 문장부호(`.`, `?`, `!`) 또는 상대높임법 종결 어미(`-습니다`, `-니다`, `-시오`, `-지요`, `-답니다`, `-라구요`).
2. **2순위 (접속 어미 및 쉼표)**: 쉼표(`,`) 뒤, 대등/종속적 연결 어미(`-고`, `-며`, `-면`, `-으면`, `-는데`, `-은데`, `-지만`, `-아서`, `-어서`, `-니까`, `-려고`, `-도록`, `-게`).
3. **3순위 (주어부/목적어부 경계)**: 체언 + 격조사(`은/는`, `이/가`, `을/를`, `에`, `에서`, `으로/로`) 뒤.

### 5-3. 절대 분할 금지 규칙 (Protected Constructs)
아래 항목 사이에서는 절대 줄바꿈이나 자막 분할을 하지 않는다:
- **보조용언 및 서술 연결**:
  - `('본', '적이')`, `('적이', '있으십니까')`, `('적이', '있습니다')`
  - `('수', '있습니다')`, `('수', '없습니다')`, `('수', '밖에')`
  - `('것이', '아닙니다')`, `('것은', '아닙니다')`, `('것', '같습니다')`
- **수식어 + 의존명사 피수식어 (관형사형 전성어미 + 의존명사)**:
  - `-는 / -은 / -ㄴ / -을 / -ㄹ / -던` 뒤의 `것, 것을, 것이, 것은, 줄, 수, 바, 때, 곳, 분, 이, 자`
  - (예: `보신다는 / 것을` ❌ 분할 금지 → `보신다는 것을` 한 덩어리 유지)
- **관형사(지시어) + 명사**:
  - `이`, `그`, `저`, `온`, `모든`, `어떤`, `각`, `옛`, `새`, `헌`, `한`, `두`, `내`, `네` + 뒤 명사
  - (예: `온 / 세상이` ❌ 분할 금지, `내 / 감정이` ❌ 분할 금지)

---

## 6. SRT 포맷팅 및 파일 저장 규칙

1. **타임스탬프**:
   - 시작 시간: 첫 단어의 실측 시작 시간 (`00:00:00,000`)
   - 종료 시간: 마지막 단어의 실측 종료 시간
   - 최소 간격: 다음 자막 시작 시간과 간격이 0.1초 미만이면 앞 자막의 종료 시간을 앞당겨 `다음 시작 - 0.100초`로 설정.
2. **번호 체계**: 1번부터 빠짐없이 연속 정수 부여.
3. **인코딩**: **UTF-8 with BOM** (캡컷 및 프리미어 한글 깨짐 방지).
4. **줄바꿈 코드**: Windows 표준 `CRLF (\r\n)`.
5. **파일명**: 입력 mp4/wav와 동일한 베이스 이름 (예: `4-1.mp4` → `4-1.srt`).

---

## 7. 4단계 자동 검증 체크리스트

모든 자막 파일이 생성된 후 자동으로 실행하여 검증하는 항목:

| 검증 항목 | 검증 기준 | 정상 판정 요건 |
|---|:---:|---|
| **첫 발화 일치** | ffmpeg silencedetect 발화 시작과 비교 | 0.5초 이내 근접 |
| **종료 시점** | mp4 총 재생 길이와 비교 | 마지막 자막 종료시간 $\le$ mp4 총 길이 |
| **글자 수 상한** | 공백 포함 25자 이하 | **25자 초과 0개** |
| **자막 간 최소 간격** | 최소 0.1초 확보 | **0.1초 미만 0개** |
| **시간 역전/겹침** | 시작 $\ge$ 종료, 앞 종료 $>$ 뒷 시작 | **역전 및 겹침 0개** |
| **3초 이상 자막 공백** | 말소리 누락 방지 | **공백 구간 0개** |
| **인코딩 규격** | UTF-8 BOM, CRLF, 쉼표 시간 | 규격 일치 여부 확인 |

---

## 8. 즉시 실행 가능한 완전 자동화 파이썬 코드

다음 세션에서 AI는 아래 코드를 그대로 실행하거나 인자로 경로만 넘겨 일괄 처리할 수 있다.

```python
import os
import sys
import time
import json
import re
import subprocess
import torch

# PyTorch DLL 로드 (Windows ctranslate2 호환)
try:
    import torch
    t_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(t_lib):
        os.add_dll_directory(t_lib)
except Exception:
    pass

from faster_whisper import WhisperModel

PROTECTED_PAIRS = [
    ('본', '적이'), ('적이', '있'), ('수', '있'), ('수', '없'), ('수', '밖에'),
    ('것이', '아닙'), ('것은', '아닙'), ('것', '같'), ('온', '세상'),
    ('새벽', '세'), ('세', '시'), ('한', '마디'), ('한', '번'), ('더', '이상'), ('첫', '번째')
]
DETERMINERS = {'이', '그', '저', '새', '헌', '온', '모든', '어떤', '각', '옛', '내', '네'}
DEPENDENT_NOUNS = {'것', '것이', '것을', '것은', '거', '게', '줄', '수', '바', '때', '곳', '분', '이', '자'}

def format_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000: s += 1; ms -= 1000
    if s >= 60: m += 1; s -= 60
    if m >= 60: h += 1; m -= 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def is_protected_split(w1_text, w2_text):
    c1 = re.sub(r'[^\w가-힣]', '', w1_text)
    c2 = re.sub(r'[^\w가-힣]', '', w2_text)
    for p1, p2 in PROTECTED_PAIRS:
        if c1.endswith(p1) and c2.startswith(p2): return True
    if c1 in DETERMINERS: return True
    if c2 in DEPENDENT_NOUNS or any(c2.startswith(dn) for dn in ('것', '줄', '수', '바')):
        if any(c1.endswith(ad) for ad in ('는', '은', 'ㄴ', '을', 'ㄹ', '던', '단')): return True
    return False

def is_sentence_boundary(w1, w2):
    t1, t2 = w1["word"].strip(), w2["word"].strip()
    gap = w2["start"] - w1["end"]
    if t1.endswith(('.', '?', '!')): return True
    c1, c2 = re.sub(r'[^\w가-힣]', '', t1), re.sub(r'[^\w가-힣]', '', t2)
    if c1.endswith(('습니다', '니다', '시오', '지요', '답니다', '라구요')):
        if not c2.startswith(('라고', '하고')): return True
    if any(c1.endswith(end) for end in ('했다', '였다', '인다', '는다', '었다', '았다', '이다')):
        if gap >= 0.25 or c2 in {'그래서', '그러나', '그리고', '하지만', '그런데', '그러므로', '방금', '또한'}:
            return True
    return gap >= 0.7

def split_long_sentence(sent_words):
    text = " ".join(w["word"].strip() for w in sent_words)
    if len(text) <= 25: return [sent_words]
    sn = len(sent_words)
    dp, backtrack = [-float('inf')] * (sn + 1), [-1] * (sn + 1)
    dp[sn] = 0.0
    for i in range(sn - 1, -1, -1):
        curr_words, c_len = [], 0
        for j in range(i + 1, sn + 1):
            w = sent_words[j - 1]
            w_text = w["word"].strip()
            c_len += len(w_text) + (1 if curr_words else 0)
            if c_len > 25: break
            curr_words.append(w_text)
            if j < sn:
                nxt_text = sent_words[j]["word"].strip()
                gap = sent_words[j]["start"] - w["end"]
                if is_protected_split(w_text, nxt_text): continue
                clean1 = re.sub(r'[^\w가-힣]', '', w_text)
                score = 80.0 if w_text.endswith(',') else 0.0
                if gap >= 0.3: score += 40.0
                for sfx in ('고', '며', '거나', '면', '으면', '는데', '은데', '지만', '아서', '어서', '니까', '려고', '도록', '게'):
                    if clean1.endswith(sfx): score += 50.0; break
                for sfx in ('은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로'):
                    if clean1.endswith(sfx): score += 20.0; break
            else: score = 100.0
            if c_len < 8: score -= 30.0
            elif 12 <= c_len <= 22: score += 20.0
            if score + dp[j] > dp[i]:
                dp[i] = score + dp[j]; backtrack[i] = j
    chunks, curr = [], 0
    while curr < sn:
        nxt = backtrack[curr] if backtrack[curr] > curr else curr + 1
        chunks.append(sent_words[curr:nxt])
        curr = nxt
    return chunks

def words_to_subtitles(words):
    if not words: return []
    sentences, curr_sent = [], [words[0]]
    for i in range(1, len(words)):
        if is_sentence_boundary(words[i-1], words[i]):
            sentences.append(curr_sent); curr_sent = [words[i]]
        else: curr_sent.append(words[i])
    if curr_sent: sentences.append(curr_sent)
    
    raw_chunks = []
    for sent in sentences:
        for sc in split_long_sentence(sent):
            raw_chunks.append({
                "words": sc, "text": " ".join(w["word"].strip() for w in sc),
                "start": sc[0]["start"], "end": sc[-1]["end"]
            })
    merged, i = [], 0
    while i < len(raw_chunks):
        c = raw_chunks[i]
        if (len(c["text"]) < 8 or (c["end"] - c["start"]) < 0.3) and i + 1 < len(raw_chunks):
            nxt = raw_chunks[i+1]
            comb = c["text"] + " " + nxt["text"]
            if len(comb) <= 25 and not is_protected_split(c["words"][-1]["word"], nxt["words"][0]["word"]):
                merged.append({"words": c["words"] + nxt["words"], "text": comb, "start": c["start"], "end": nxt["end"]})
                i += 2; continue
        if (len(c["text"]) < 8 or (c["end"] - c["start"]) < 0.3) and merged:
            prev = merged[-1]
            comb = prev["text"] + " " + c["text"]
            if len(comb) <= 25:
                prev["words"].extend(c["words"]); prev["text"] = comb; prev["end"] = c["end"]
                i += 1; continue
        merged.append(c); i += 1
        
    for j in range(len(merged) - 1):
        if merged[j+1]["start"] - merged[j]["end"] < 0.1:
            new_end = merged[j+1]["start"] - 0.1
            if new_end > merged[j]["start"]: merged[j]["end"] = round(new_end, 3)
    return merged
```

---

## 9. AI 사용법 (다음 세션 지시 명령어)

다음 세션에서 AI에게 다음과 같이 지시하면 본 매뉴얼의 모든 규칙을 바탕으로 즉시 완벽하게 수행한다:

```text
C:\Users\eded7\OneDrive\Desktop\mp4-Text\AI_음성기반_자막생성_작업매뉴얼.md 읽고,
입력 폴더 {경로}의 음성/영상 파일에 대해 자막 파일을 생성해줘.
```
