# -*- coding: utf-8 -*-
"""사회조사분석사 2급 필기 — 학습앱 데이터 빌드
   입력: kordoc OCR 마크다운
   출력: data.json  { subjects, theory, questions }
"""
import re, json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

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
chunks, i = [], Q_START
while i < len(L):
    l = L[i]
    if l.strip().startswith('<table>'):
        j, buf = i, []
        while j < len(L) and not L[j].strip().startswith('</table>'):
            buf.append(L[j]); j += 1
        for c in CELL.findall('\n'.join(buf)):
            c = re.sub(r'<[^>]+>', ' ', c).strip()
            if c:
                chunks.append(c)
        i = j + 1
        continue
    t = l.strip()
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


STEM = re.compile(
    r'(?:(?<=\n)\s*(?P<n1>\d{1,3})?\s*|(?<=[\s.다])(?P<n2>\d{1,3})\s*)'
    r'(?P<stem>[^\n①②③④?]{8,90}\?)\s*(?P<rd>(?:\s*\d\d-\d)*)')
OPTM = re.compile(r'[①②③④]')
BARE = re.compile(r'(?:(?<=\n)|(?<=\s)|^)-?\s*([1-4])\s*(?=[가-힣A-Za-z(])')
HAESUL = re.compile(r'(해설|해실|해성|허성|없성|헤설|해섬|애설|하설|해섧|해셜)')
SENT_END = re.compile(r'(다|요|까|음|함|것|오)\.?\s')

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
    else:
        lim = int(max(others) * 1.6) + 25
        if len(tail) > lim:
            cut = SENT_END.search(tail, lim // 2)
            cut = cut.end() if cut else lim
            segs[last_n], expl = tail[:cut], tail[cut:]
        else:
            expl = ''

    opts = [re.sub(r'\s+', ' ', segs[n]).strip(' -–—·.') for n in (1, 2, 3, 4)]
    expl = re.sub(r'\s+', ' ', expl).strip(' -–—·')
    # 해설 뒤에 다음 문제가 새어 들어온 경우 절단
    qm = expl.find('?')
    if qm > 0 and '①' in expl[qm:]:
        expl = expl[:qm + 1].rsplit('. ', 1)[0].strip()

    ci = chunk_of(m.start())
    num = m.group('n1') or m.group('n2')
    recs.append({
        'num': int(num) if num else None,
        'stem': re.sub(r'\s+', ' ', m.group('stem')).strip(' -–—·'),
        'rounds': m.group('rd').split(),
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
def ok(q):
    o = q['options']
    if any(not x or len(x) > 260 for x in o):
        return False
    if len(set(o)) < 4:
        return False
    # 보기 안에 다른 보기 마커가 남아 있으면 표가 뒤엉킨 것
    if any(OPTM.search(x) for x in o):
        return False
    if len(q['stem']) < 8:
        return False
    return True


kept = [q for q in recs if ok(q)]
for q in kept:
    q.pop('ci', None)

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

data = {
    'source': '사회조사분석사 2급 필기 (OCR 자동 추출)',
    'parts': PARTS,
    'theory': theory,
    'questions': questions,
}
json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

tot = sum(len(g['items']) for g in questions)
ans = sum(1 for g in questions for q in g['items'] if q.get('answer'))
expl = sum(1 for g in questions for q in g['items'] if len(q['expl']) > 15)
print(f'이론 토픽 {sum(len(p["topics"]) for p in theory)}')
print(f'문항 {tot} | 정답확정 {ans} | 해설보유 {expl}')
for g in questions:
    a = sum(1 for q in g['items'] if q.get('answer'))
    print(f"  PART{g['part']} CH{g['chapter']} {g['chapterTitle']}: {len(g['items'])}문항 (정답 {a})")
print('→', os.path.abspath(OUT), os.path.getsize(OUT) // 1024, 'KB')
