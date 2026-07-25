# -*- coding: utf-8 -*-
"""사회조사분석사 2급 필기 — 학습앱 데이터 빌드
   입력: kordoc OCR 마크다운
   출력: data.json  { subjects, theory, questions }
"""
import re, json, sys, os
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spacing import respace, fix_jamo, fix_jamo_lead

SRC = os.environ.get(
    'OCR_MD',
    r'output\kordoc\사회조사분석사 2급 필기 OCR.md')  # 교재 OCR 마크다운 (저장소에 미포함)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'docs/data.json'
L = open(SRC, encoding='utf-8').read().split('\n')

THEORY_START, THEORY_END = 575, 3923
Q_START = 3924

PARTS = {1: '조사방법과 설계', 2: '조사관리와 자료처리', 3: '통계분석과 활용',
         4: '2025년 기출복원문제'}
CHAPTERS = {
    (1, 1): '통계조사계획', (1, 2): '표본설계', (1, 3): '설문설계',
    (1, 4): 'FGI 및 심층인터뷰 정성조사',
    (2, 1): '자료수집방법', (2, 2): '실사관리', (2, 3): '2차 자료 분석',
    (2, 4): '측정의 타당성과 신뢰성', (2, 5): '자료처리',
    (3, 1): '확률분포', (3, 2): '기술통계분석', (3, 3): '회귀분석',
    (4, 1): '2025년 기출복원문제',
}
# OCR 표기 흔들림 → 정규 챕터. 챕터명은 전역 고유하므로 이름으로 과목까지 결정한다.
CH_ALIAS = {}
for (p, c), name in CHAPTERS.items():
    CH_ALIAS[re.sub(r'\s', '', name)] = (p, c)
for alias, key in {
    '표본살계': (1, 2), '설문살계': (1, 3), 'FGI및심승인터뷰정성조사': (1, 4),
    '측정의타당성과신리성': (2, 4), '측정의타당성과신화성': (2, 4),
    '측정의타당성과산뢰성': (2, 4), '학률분포': (3, 1), '통계문석과활용': (3, 2),
}.items():
    CH_ALIAS[alias] = key


# ══════════════ 1. 이론(빨간키) ══════════════
HANGUL = re.compile(r'[가-힣]')
FORMULA = re.compile(r'[=|Σ∑∫√±×÷~≈≤≥$\[\]{}]|\d\s*\)|P\(|Var\(|Cov\(|E\(')
BULLET = '•·▪∙‧・*-'
PART_HEAD = re.compile(r'^PART\s*[0Q]?\s*(\d)\s*[|)]?\s*(조사방법과\s*설계|조사관리와\s*자료처리|통계분석과\s*활용)')
PAGE_FOOT = re.compile(r'^PART\s*[0Q]?\s*\d?\s*\)?\s*(조사방법과|조사관리와|통계분석과|통계문석과)')


def is_heading(l):
    if not l or l[:1] in BULLET or len(l) > 34 or re.search(r'[.。]$', l):
        return False
    if re.search(r'(이다|한다|된다|있다|없다|같다|않다|보다|린다|온다|난다|시다|킨다|긴다|짓다|하다)$', l):
        return False
    if re.search(r'[→=<>()]$', l):
        return False
    b = re.sub(r'^###\s*', '', l)
    han = len(HANGUL.findall(b))
    if han < 2 or han / max(len(b), 1) < 0.5 or FORMULA.search(b):
        return False
    return True


def strip_mark(l):
    l = re.sub(r'^###\s*', '', l)
    l = re.sub(r'^[•·▪∙‧・]\s*', '', l)
    return re.sub(r'^-\s+', '', l).strip()


theory, cur_p, cur_t = [], None, None
for i in range(THEORY_START, THEORY_END + 1):
    raw = L[i].strip()
    if not raw or raw.startswith('!['):
        continue
    m = PART_HEAD.match(raw)
    if m and not re.search(r'\d\s*$', raw):
        cur_p = {'part': int(m.group(1)), 'title': PARTS[int(m.group(1))], 'topics': []}
        theory.append(cur_p); cur_t = None
        continue
    if PAGE_FOOT.match(raw) or '속의 책' in raw or '속의책' in raw:
        continue
    if cur_p is None:
        continue
    txt = strip_mark(raw)
    if not txt:
        continue
    if is_heading(raw):
        cur_t = {'title': txt, 'body': []}
        cur_p['topics'].append(cur_t)
    else:
        if cur_t is None:
            cur_t = {'title': '개요', 'body': []}
            cur_p['topics'].append(cur_t)
        cur_t['body'].append({'b': raw[:1] in BULLET, 't': txt})

for p in theory:                       # 본문 없는 헤딩 흡수
    merged = []
    for t in p['topics']:
        if not t['body'] and merged:
            merged[-1]['body'].append({'b': False, 't': t['title']})
        else:
            merged.append(t)
    p['topics'] = merged


# ══════════════ 2. 기출문제 + 해설 ══════════════
CELL = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.S)
MD_SEP = re.compile(r'^[\s|:-]*$')


def md_clean(s):
    """마크다운 잔여물(### 머리표, 표 구분선, 파이프)을 걷어낸다."""
    s = re.sub(r'#{1,6}\s*', ' ', s)
    if MD_SEP.match(s):                     # |---|---| 같은 표 구분행
        return ''
    s = re.sub(r'\s*\|\s*', ' ', s)         # 표 파이프 → 공백
    return re.sub(r'\s+', ' ', s).strip()


chunks, i = [], Q_START
while i < len(L):
    l = L[i]
    if l.strip().startswith('<table>'):
        j, buf = i, []
        while j < len(L) and not L[j].strip().startswith('</table>'):
            buf.append(L[j]); j += 1
        for c in CELL.findall('\n'.join(buf)):
            c = md_clean(re.sub(r'<[^>]+>', ' ', c))
            if c:
                chunks.append(c)
        i = j + 1
        continue
    t = md_clean(l)
    if t and not t.startswith('!['):
        chunks.append(t)
    i += 1

ANS_PAIR = re.compile(r'(\d{1,3})\s*([①②③④])')
FOOT = re.compile(r'(정답|정담)')
CH_FOOT = re.compile(r'CHAPTER\s*[O0oQ]?\s*(\d)\s*([가-힣A-Za-z0-9 ·및]+?)\s*\d*$')
MOCK = re.compile(r'2025\s*년?\s*기출복원문제')

clean, ans_ev, ch_ev = [], [], []
mock_at = None
for txt in chunks:
    foot = False
    if FOOT.search(txt) and len(txt) < 160:
        pairs = [(int(n), '①②③④'.index(a) + 1)
                 for n, a in ANS_PAIR.findall(re.sub(r'(정답|정담)', ' ', txt))]
        if pairs:
            ans_ev.append((len(clean), pairs))
        foot = True
    mc = CH_FOOT.search(txt)
    if mc and len(txt) < 100:
        key = CH_ALIAS.get(re.sub(r'\s', '', mc.group(2)))
        if key:
            ch_ev.append((len(clean), key))
        foot = True
    if MOCK.search(txt) and len(txt) < 60 and mock_at is None:
        mock_at = len(clean)
    if not foot:
        clean.append(txt)

text = '\n'.join(clean)
offs, pos = [], 0
for t in clean:
    offs.append(pos); pos += len(t) + 1


def chunk_of(off):
    lo, hi = 0, len(offs) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offs[mid] <= off:
            lo = mid
        else:
            hi = mid - 1
    return lo


def chapter_for(ci):
    if mock_at is not None and ci >= mock_at:
        return (4, 1)
    for p, key in ch_ev:            # 문제 뒤에 오는 첫 챕터 꼬리말이 그 문제의 챕터
        if p >= ci:
            return key
    return ch_ev[-1][1] if ch_ev else (1, 1)


# 문제번호는 (?!\d) 로 막아 '2010년'의 201 을 번호로 오인하지 않게 한다
STEM = re.compile(
    r'(?:(?<=\n)\s*(?P<n1>\d{1,3}(?!\d))?\s*|(?<=[\s.다])(?P<n2>\d{1,3}(?!\d))\s*)'
    r'(?P<stem>[^\n①②③④?]{8,90}\?)\s*(?P<rd>(?:\s*\d\d-\d)*)')
# 발문이 표 셀 두 개로 쪼개진 경우, 앞줄이 문장으로 끝나지 않으면 발문의 앞부분이다
CONT_BAD = re.compile(r'[①②③④]|^(해설|해실|해성|허성|없성)|(다|다\.|음|임|함|요|까)\s*$|[.?]\s*$')
# 'ㄱ.…' 같은 보기 지문 항목은 발문 앞부분이 아니다
PASSAGE_ITEM = re.compile(r'^[ㄱ-ㅎ]\s*[.,)]|^\[')
# 발문 앞에 눌어붙은 페이지 머리말·절 제목
STEM_PREFIX = re.compile(
    r'^\s*(?:\d{1,3}\s*)?(?:PART|CHAPTER)\s*[O0oQ]?[\d\s\-–—|]*[가-힣A-Za-z0-9 ·및]{0,20}?\s*(?=[가-힣])'
    r'|^\s*\(\d\)\s*[가-힣][가-힣 ·]{0,18}\s+(?=[가-힣])'
    r'|^\s*\d{1,3}\s*[|｜]\s*')


def clean_stem(s):
    s = re.sub(r'\s+', ' ', s).strip(' -–—·')
    for _ in range(3):
        t = STEM_PREFIX.sub('', s).strip(' -–—·')
        if t == s or len(t) < 8:
            break
        s = t
    return s
OPTM = re.compile(r'[①②③④]')
BARE = re.compile(r'(?:(?<=\n)|(?<=\s)|^)-?\s*([1-4])\s*(?=[가-힣A-Za-z(])')
HAESUL = re.compile(r'(해설|해실|해성|허성|없성|헤설|해섬|애설|하설|해섧|해셜)')
# 문장 끝. OCR이 마침표 뒤 공백을 흘리는 일이 잦아 마침표만으로도 끊는다.
SENT_END = re.compile(r'[다요까음함것오]\.\s*|[다요까음함것오]\s')
# 보기가 '~한다', '~이다' 처럼 문장형인지 판정
SENT_TAIL = re.compile(r'(다|음|함|요|까|니다)\.?\s*$')
# 'ㄱ,ㄴ,ㄹ' 형태의 보기 (OCR이 ㄱ→7, ㄹ→2 로 흘린 것 포함)
JAMO_OPT = re.compile(r'^[ㄱ-ㅎ0-9A-Za-z□\s,.·~()-]{1,16}$')
JAMO_HEAD = re.compile(r'^[ㄱ-ㅎ0-9A-Za-z□,.·~()-]+')
# 페이지 번호·머리말 잔여물
PAGE_JUNK = re.compile(r'^(\d{1,3}\s*)?(PART|CHAPTER)\b|^\d{1,3}$|^[\d\s.·|]+$')

stems = list(STEM.finditer(text))
recs = []
for k, m in enumerate(stems):
    s = m.end()
    e = stems[k + 1].start() if k + 1 < len(stems) else len(text)
    body = text[s:e]

    cands = [('①②③④'.index(o.group()) + 1, o.start(), o.end(), 0) for o in OPTM.finditer(body)]
    cands += [(int(o.group(1)), o.start(1), o.end(1), 1) for o in BARE.finditer(body)]
    cands.sort(key=lambda t: (t[1], t[3]))
    marks, want = [], 1
    for n, a, b, _ in cands:
        if n == want:
            marks.append((n, a, b)); want += 1
            if want > 4:
                break
    if len(marks) < 4:
        first = {}
        for o in OPTM.finditer(body):
            first.setdefault('①②③④'.index(o.group()) + 1, (o.start(), o.end()))
        if len(first) < 4:
            continue
        marks = sorted(((n, a, b) for n, (a, b) in first.items()), key=lambda t: t[1])

    segs = {}
    for si, (n, a, b) in enumerate(marks):
        stop = marks[si + 1][1] if si + 1 < len(marks) else len(body)
        segs[n] = body[b:stop]

    last_n = marks[-1][0]
    tail = segs[last_n]
    others = [len(v) for k2, v in segs.items() if k2 != last_n] or [40]
    h = HAESUL.search(tail)
    if h:
        segs[last_n], expl = tail[:h.start()], tail[h.end():]
        # 2단 조판이 뒤엉켜 '해설' 표기가 해설 한복판에 찍힌 경우가 있다.
        # 그 결과 마지막 보기가 비정상적으로 길어지면 문장 끝에서 다시 끊는다.
        if len(segs[last_n]) > max(others) * 1.25 + 20:
            c2 = SENT_END.search(segs[last_n], max(8, int(min(others) * 0.5)))
            if c2:
                expl = segs[last_n][c2.end():] + ' ' + expl
                segs[last_n] = segs[last_n][:c2.end()]
    else:
        others_txt = [v.strip() for k2, v in segs.items() if k2 != last_n]
        if all(JAMO_OPT.match(o) for o in others_txt if o):
            # 'ㄱ,ㄴ,ㄷ' 식 보기라면 마지막 보기도 자모 나열까지만이다
            mm = JAMO_HEAD.match(tail.lstrip())
            cut = (len(tail) - len(tail.lstrip())) + mm.end() if mm else 0
            segs[last_n], expl = tail[:cut], tail[cut:]
        elif all(len(o) <= 3 for o in others_txt) or max(others) == 0:
            expl = ''
        else:
            # 한 문항의 보기는 길이·형태가 서로 비슷하다.
            # 다른 보기가 '~다'로 끝나는 문장형이면 첫 문장 끝에서,
            # 명사구형이면 같은 어절 수만큼만 끊는다.
            sentence_like = any(SENT_TAIL.search(o) for o in others_txt)
            lim = int(max(others) * 1.5) + 12
            if len(tail) <= lim:
                expl = ''
            elif sentence_like:
                cut = SENT_END.search(tail, max(8, int(min(others) * 0.5)))
                cut = cut.end() if cut else lim
                segs[last_n], expl = tail[:cut], tail[cut:]
            else:
                nw = max(1, round(sum(len(o.split()) for o in others_txt) / len(others_txt)))
                parts = tail.strip().split()
                cut_txt = ' '.join(parts[:nw])
                idx = tail.find(cut_txt) + len(cut_txt)
                segs[last_n], expl = tail[:idx], tail[idx:]

    opts = [re.sub(r'\s+', ' ', segs[n]).strip(' -–—·.') for n in (1, 2, 3, 4)]
    expl = re.sub(r'\s+', ' ', expl).strip(' -–—·')
    # 해설 뒤에 다음 문제가 새어 들어온 경우 절단
    qm = expl.find('?')
    if qm > 0 and '①' in expl[qm:]:
        expl = expl[:qm + 1].rsplit('. ', 1)[0].strip()

    # ── 발문과 첫 보기 사이 = 보기 지문(ㄱㄴㄷㄹ 박스, 자료 제시문) ──
    passage = []
    for ln in body[:marks[0][1]].split('\n'):
        ln = ln.strip(' -–—·')
        if not ln or PAGE_JUNK.match(ln) or HAESUL.match(ln):
            continue
        passage.append(ln)
    passage = passage if 0 < sum(len(x) for x in passage) <= 600 else []

    # 발문이 표 셀 두 개로 쪼개진 경우에만 앞줄을 이어붙인다.
    # 판별 조건: 앞줄은 문제번호로 시작하고, 이번 매치에는 번호가 없다.
    stem_txt = m.group('stem')
    ls = text.rfind('\n', 0, m.start())
    if ls > 0 and not (m.group('n1') or m.group('n2')):
        prev = text[text.rfind('\n', 0, ls) + 1:ls].strip()
        pm = re.match(r'^(\d{1,3})(?!\d)\s+(\S.*)$', prev)
        # ① 앞줄이 문제번호로 시작하면 그 줄이 발문의 앞부분이다
        # ② 번호가 없더라도 이번 발문이 지나치게 짧으면 잘린 것으로 본다
        cand = (pm.group(2) if pm else prev).strip()
        if (pm or len(stem_txt) < 22) and 8 <= len(cand) <= 120 \
                and not CONT_BAD.search(cand) and not PASSAGE_ITEM.match(cand):
            stem_txt = cand + ' ' + stem_txt

    ci = chunk_of(m.start())
    num = m.group('n1') or m.group('n2')
    recs.append({
        'num': int(num) if num else None,
        'stem': clean_stem(stem_txt),
        'rounds': m.group('rd').split(),
        'passage': passage,
        'options': opts, 'expl': expl,
        'ch': chapter_for(ci), 'ci': ci,
    })

# ── 정답 정렬 (페이지 꼬리말 단위) ──
recs.sort(key=lambda r: r['ci'])
qi = last_num = 0
for fpos, pairs in ans_ev:
    span = []
    while qi < len(recs) and recs[qi]['ci'] < fpos:
        span.append(recs[qi]); qi += 1
    nums = [n for n, _ in pairs]
    contiguous = all(nums[i] + 1 == nums[i + 1] for i in range(len(nums) - 1))
    extra = len(span) - len(pairs)
    if extra == 0:
        for q, (n, a) in zip(span, pairs):
            q['num'], q['answer'] = n, a
    elif extra > 0 and contiguous and nums[0] == last_num + 1 + extra:
        # 앞 페이지 꼬리말이 소실된 경우: 번호 연속성으로 확인 후 뒤에서부터 정렬
        for q, (n, a) in zip(span[extra:], pairs):
            q['num'], q['answer'] = n, a
    else:
        amap = dict(pairs)
        for q in span:
            if q['num'] in amap:
                q['answer'] = amap[q['num']]
    if nums:
        last_num = nums[-1]

# ── 품질 필터 ──
STEM_JUNK = re.compile(r'^(PART|CHAPTER|\(\d\))')


def ok(q):
    o = q['options']
    if any(not x or len(x) > 260 for x in o):
        return False
    if len(set(o)) < 4:
        return False
    # 보기 안에 다른 보기 마커가 남아 있으면 표가 뒤엉킨 것
    if any(OPTM.search(x) for x in o):
        return False
    # 앞부분이 잘렸거나 머리말이 눌어붙은 발문은 문제로 못 쓴다
    if len(q['stem']) < 14:
        return False
    if STEM_JUNK.match(q['stem']):
        return False
    return True


kept = [q for q in recs if ok(q)]
for q in kept:
    q.pop('ci', None)

# ── OCR 정리: 자모 복원 + 띄어쓰기 교정 ──
print('띄어쓰기 교정 중...', flush=True)
for q in kept:
    q['stem'] = respace(q['stem'])
    q['options'] = [respace(fix_jamo(o)) for o in q['options']]
    q['passage'] = [respace(fix_jamo_lead(fix_jamo(p))) for p in q['passage']]
    q['expl'] = respace(q['expl'])
for p in theory:
    for t in p['topics']:
        t['title'] = respace(t['title'])
        for b in t['body']:
            b['t'] = respace(b['t'])

# ── 챕터별 그룹핑 ──
groups = {}
for q in kept:
    p, c = q['ch']
    groups.setdefault((p, c), []).append(q)

questions = []
for (p, c), qs in sorted(groups.items()):
    for idx, q in enumerate(qs):
        q['id'] = f'{p}-{c}-{idx + 1}'
        q.pop('ch', None)
    questions.append({
        'part': p, 'partTitle': PARTS[p],
        'chapter': c, 'chapterTitle': CHAPTERS[(p, c)],
        'items': qs,
    })

# ══════════════ 3. 이론을 챕터에 배치 ══════════════
# 빨간키 토픽은 교재의 챕터 순서를 그대로 따른다.
# 각 토픽이 어느 챕터의 기출 문항과 가장 많은 어휘를 공유하는지 점수를 매기고,
# '순서를 거스르지 않는다'는 제약 아래 최적 분할을 찾는다(단조 DP).
TOKEN = re.compile(r'[가-힣]{2,}')
STOP = {'것은', '경우', '대한', '있다', '없다', '한다', '되는', '이다', '하는', '위한', '다음',
        '가장', '모두', '해당', '관한', '설명', '내용', '방법', '때문', '통해', '따라', '또는',
        '그리고', '하여', '에서', '으로', '이러한', '이를', '수록', '거리가', '옳은', '틀린'}


def toks(s):
    return [w for w in TOKEN.findall(s) if w not in STOP]


def assign_chapters():
    corpus = {}                       # (part, ch) -> Counter
    for g in questions:
        c = Counter()
        for q in g['items']:
            c.update(toks(q['stem']))
            for o in q['options']:
                c.update(toks(o))
            c.update(toks(q['expl']))
        total = sum(c.values()) or 1
        corpus[(g['part'], g['chapter'])] = (c, total)

    for p in theory:
        chs = sorted(c for (pp, c) in corpus if pp == p['part'])
        if not chs:
            continue
        n, m = len(p['topics']), len(chs)
        # 토픽 i 가 챕터 j 와 얼마나 어울리는지
        sc = [[0.0] * m for _ in range(n)]
        for i, t in enumerate(p['topics']):
            words = toks(t['title']) * 3 + toks(' '.join(b['t'] for b in t['body']))
            for j, ch in enumerate(chs):
                c, total = corpus[(p['part'], ch)]
                sc[i][j] = sum(c.get(w, 0) / total for w in words) * 1000
        # 단조 증가 제약 DP
        best = [[0.0] * m for _ in range(n)]
        prev = [[0] * m for _ in range(n)]
        for j in range(m):
            best[0][j] = sc[0][j]
        for i in range(1, n):
            run = -1e18
            arg = 0
            for j in range(m):
                if best[i - 1][j] > run:
                    run, arg = best[i - 1][j], j
                best[i][j] = sc[i][j] + run
                prev[i][j] = arg
        j = max(range(m), key=lambda x: best[n - 1][x])
        path = [0] * n
        for i in range(n - 1, -1, -1):
            path[i] = chs[j]
            j = prev[i][j] if i else j
        for t, ch in zip(p['topics'], path):
            t['ch'] = ch


assign_chapters()

# ══════════════ 4. 해설 → 개념 정리 카드 ══════════════
# 해설 중 '제목 + 불릿' 구조인 것은 그대로 이론 카드가 된다.
BULLET_SPLIT = re.compile(r'\s*[•·▪∙‧・]\s*')
BAD_TITLE = re.compile(r'해설|참조|PART|CHAPTER|다음과 같다$|^\d')
# 앞머리에 눌어붙은 보기번호·자모나열 (예: 'ㄴ,ㄷ.2,ㅁ 과학적 방법의 특징')
TITLE_LEAD = re.compile(r'^(?:[①②③④]|[ㄱ-ㅎ0-9]\s*[,.)]|\s)+')
SENT_SPLIT = re.compile(r'(?<=다)\s+|(?<=다\.)\s*|(?<=[음함])\s+')


def title_of(head):
    """불릿 앞머리에서 개념 제목을 뽑는다.

    책의 해설은 '…앞 문장. 제목 •항목 •항목' 꼴이 많다.
    따라서 마지막 조각이 문장으로 끝나지 않으면 그것이 제목이고,
    문장으로 끝나면 첫 어절(정의 대상)을 제목으로 삼고 본문은 첫 항목으로 넘긴다.
    """
    head = re.sub(r'~~', ' ', head or '')
    head = TITLE_LEAD.sub('', head).strip(' -–—·.:')
    # OCR이 흘린 낱글자 머리(‘성 ’, ‘실 ’, ‘ㅁ ’)를 떼어낸다
    head = re.sub(r'^(?:[가-힣ㄱ-ㅎ]\s+){1,2}(?=[가-힣]{2,})', '', head)
    if not head:
        return '', ''
    frags = [f.strip(' -–—·.:') for f in SENT_SPLIT.split(head) if f.strip(' -–—·.:')]
    if not frags:
        return '', ''
    last = frags[-1]
    if not re.search(r'(다|음|함|요|까)\.?$', last) and 4 <= len(last) <= 45:
        return last, ' '.join(frags[:-1]).strip()
    # 전체가 문장이면 정의 대상(첫 1~2어절)을 제목으로
    w = head.split()
    for n in (1, 2):
        cand = ' '.join(w[:n]).strip(' -–—·.:,')
        if 3 <= len(cand) <= 24 and not re.search(r'(다|음|함)\.?$', cand):
            return cand, head
    return '', ''


# 제목이 조사·어미로 끝나면 문장 도막이지 개념 이름이 아니다
TITLE_TAIL_BAD = re.compile(
    r'(은|는|이|가|을|를|에|에서|으로|로|와|과|의|도|만|부터|까지|하고|하는|한|된|될|및|또는)$')
TITLE_BAD_WORD = re.compile(r'해설|해실|해성|허설|허 설|없성|참조|PART|CHAPTER|&|\d{2,}')


def good_title(t):
    if not t or TITLE_BAD_WORD.search(t):
        return False
    t = t.strip()
    if re.match(r'^(의|은|는|이|가|을|를|에|와|과|및)\s', t):   # 조사로 시작 = 문장 도막
        return False
    if not (4 <= len(t) <= 40):
        return False
    if len(re.findall(r'[가-힣]', t)) < 3:
        return False
    if TITLE_TAIL_BAD.search(t):
        return False
    if len(t.split()) < 2 and len(t) < 6:      # '과학적' 같은 토막
        return False
    return True


def concept_cards():
    by_ch = {}
    for g in questions:
        seen = {}
        for q in g['items']:
            e = q['expl']
            if len(e) < 40 or BULLET_SPLIT.search(e) is None:
                continue
            parts_ = [x.strip(' -–—·.') for x in BULLET_SPLIT.split(e)]
            head, bullets = parts_[0], [x for x in parts_[1:] if len(x) > 4]
            if len(bullets) < 2:
                continue
            title, lead = title_of(head)
            if not good_title(title):
                continue
            if lead:
                bullets = [lead] + bullets
            key = re.sub(r'\s', '', title)
            cand = {'title': title, 'body': bullets, 'from': q['id']}
            if key not in seen or len(bullets) > len(seen[key]['body']):
                seen[key] = cand
        if seen:
            by_ch[(g['part'], g['chapter'])] = sorted(
                seen.values(), key=lambda x: -len(x['body']))
    return by_ch


CARDS = concept_cards()

# ── 이론을 과목 > 챕터 구조로 재조립 ──
lessons = []
for g in questions:
    p, c = g['part'], g['chapter']
    keywords = []
    for tp in theory:
        if tp['part'] != p:
            continue
        for t in tp['topics']:
            if t.get('ch') == c:
                keywords.append({'title': t['title'], 'body': t['body']})
    cards = CARDS.get((p, c), [])
    if not keywords and not cards:
        continue
    lessons.append({
        'part': p, 'partTitle': PARTS[p],
        'chapter': c, 'chapterTitle': CHAPTERS[(p, c)],
        'keywords': keywords, 'cards': cards,
    })

data = {
    'source': '사회조사분석사 2급 필기 (OCR 자동 추출)',
    'parts': PARTS,
    'theory': theory,
    'lessons': lessons,
    'questions': questions,
}
json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

tot = sum(len(g['items']) for g in questions)
ans = sum(1 for g in questions for q in g['items'] if q.get('answer'))
expl = sum(1 for g in questions for q in g['items'] if len(q['expl']) > 15)
print(f'이론 토픽 {sum(len(p["topics"]) for p in theory)}'
      f' | 개념카드 {sum(len(l["cards"]) for l in lessons)}')
print(f'문항 {tot} | 정답확정 {ans} | 해설보유 {expl}')
for g in questions:
    a = sum(1 for q in g['items'] if q.get('answer'))
    ls = next((l for l in lessons if (l['part'], l['chapter']) == (g['part'], g['chapter'])), None)
    kw = len(ls['keywords']) if ls else 0
    cd = len(ls['cards']) if ls else 0
    print(f"  PART{g['part']} CH{g['chapter']} {g['chapterTitle']}: "
          f"{len(g['items'])}문항(정답 {a}) · 키워드 {kw} · 개념 {cd}")
print('→', os.path.abspath(OUT), os.path.getsize(OUT) // 1024, 'KB')
