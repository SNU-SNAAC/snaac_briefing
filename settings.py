"""경제 브리핑의 도메인별 설정.

사이트 이름, 기사 수, 수집원, 선별 기준을 바꾸고 싶을 때는 이 파일만 먼저 확인하세요.
"""

from __future__ import annotations

DOMAIN_ID = "economy"
SITE_NAME = "ECONOMY BRIEFING"
SITE_KOREAN_NAME = "오늘의 경제"
BRAND_TOP = "ECONOMY"
BRAND_BOTTOM = "MORNING BRIEFING"
KICKER = "Daily economy & market journal"
INTRO_TEXT = (
    "국내외 경제 흐름과 주식·금리·환율·산업 변화를 한 번에 읽을 수 있도록 "
    "무료 원문 가운데 오늘 꼭 볼 소식만 골랐어요."
)
EDITORIAL_CHIPS = ["무료 원문만", "국내·글로벌", "주식·시장", "금리·거시", "정책·산업"]
FOOTER_LINE = "개인용 경제 브리핑 · 투자 자문이 아님 · 매일 자동 업데이트"
ABOUT_EYEBROW = "ABOUT THIS BRIEFING"
ABOUT_TITLE = "경제의 큰 흐름을 매일 짧게"
ABOUT_COPY = "시장 소음보다 중요한 변화와 맥락을 기록하는 개인용 큐레이션 프로젝트입니다."
ACCENT = "#176B5B"
THEME_COLOR = "#F2F3F4"

PICK_COUNT = 8
MIN_PICKS = 6
MAX_CANDIDATES = 64
MAX_PER_SOURCE_FINAL = 2
RECENT_DUPLICATE_DAYS = 14
DEFAULT_LOOKBACK_HOURS = 48
OUTPUT_SCHEMA_NAME = "economy_briefing_picks"
SUPABASE_TABLE = "saved_articles_economy"

SECTION_VALUES = ["국내", "글로벌"]
SECTION_TARGETS = {"국내": 4, "글로벌": 4}
SECTION_MINIMUMS = {"국내": 3, "글로벌": 3}
SECTION_MAXIMUMS = {"국내": 4, "글로벌": 4}
CATEGORY_VALUES = [
    "주식·시장",
    "거시경제",
    "금리·통화",
    "환율·원자재",
    "산업·기업",
    "정책·규제",
]
CONTENT_TYPE_VALUES = ["기사", "공식 발표", "분석·리포트", "인터뷰", "영상", "기타"]

CATEGORY_KEYWORDS = {
    "주식·시장": ["주가", "증시", "코스피", "코스닥", "나스닥", "s&p", "dow", "stock", "equity", "bond market", "채권시장"],
    "거시경제": ["성장률", "gdp", "물가", "인플레이션", "고용", "실업", "소비", "무역", "수출", "수입", "recession", "growth"],
    "금리·통화": ["금리", "기준금리", "중앙은행", "연준", "fomc", "통화정책", "fed", "ecb", "금통위"],
    "환율·원자재": ["환율", "달러", "원화", "엔화", "유가", "금값", "원자재", "oil", "currency", "forex", "commodity"],
    "산업·기업": ["기업", "실적", "반도체", "자동차", "배터리", "부동산", "산업", "earnings", "company", "industry"],
    "정책·규제": ["정책", "규제", "세제", "예산", "금융위", "정부", "관세", "법안", "regulation", "tariff", "fiscal"],
}

RELEVANCE_KEYWORDS = [
    "경제", "금융", "시장", "증시", "주식", "채권", "금리", "환율", "원화", "달러",
    "물가", "인플레이션", "고용", "실업", "성장률", "gdp", "수출", "무역", "관세",
    "산업", "기업", "실적", "반도체", "부동산", "원자재", "유가", "연준", "중앙은행",
    "economy", "market", "stocks", "equities", "bonds", "rates", "inflation", "jobs",
    "growth", "trade", "tariff", "currency", "oil", "fed", "ecb", "earnings",
]

LOW_VALUE_TITLE_PATTERNS = [
    r"오늘의\s*(추천|종목)",
    r"상한가\s*예상",
    r"목표주가\s*상향",
    r"무조건\s*(사라|매수)",
    r"급등주",
    r"무료\s*리딩방",
    r"event|promotion|giveaway",
]

# source_group: market / official / news / analysis
FEEDS = [
    {
        "source": "SBS 경제",
        "url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02&plink=RSSREADER",
        "source_group": "news",
        "section": "국내",
        "lookback_hours": 48,
    },
    {
        "source": "연합뉴스 경제",
        "url": "https://www.yna.co.kr/rss/economy.xml",
        "source_group": "news",
        "section": "국내",
        "lookback_hours": 48,
    },
    {
        "source": "매일경제 경제",
        "url": "https://www.mk.co.kr/rss/30100041/",
        "source_group": "news",
        "section": "국내",
        "lookback_hours": 48,
    },
    {
        "source": "매일경제 증권",
        "url": "https://www.mk.co.kr/rss/50200011/",
        "source_group": "market",
        "section": "국내",
        "lookback_hours": 36,
    },
    {
        "source": "금융위원회",
        "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
        "source_group": "official",
        "section": "국내",
        "lookback_hours": 120,
    },
    {
        "source": "오마이뉴스 경제",
        "url": "https://rss.ohmynews.com/rss/economy.xml",
        "source_group": "news",
        "section": "국내",
        "lookback_hours": 48,
    },
    {
        "source": "대한민국 정책브리핑",
        "url": "https://www.korea.kr/etc/rss.do",
        "source_group": "official",
        "section": "국내",
        "lookback_hours": 72,
    },
    {
        "source": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml?edition=int",
        "source_group": "news",
        "section": "글로벌",
        "lookback_hours": 48,
    },
    {
        "source": "CNBC Markets",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "source_group": "market",
        "section": "글로벌",
        "lookback_hours": 36,
    },
    {
        "source": "The Guardian Business",
        "url": "https://www.theguardian.com/uk/business/rss",
        "source_group": "news",
        "section": "글로벌",
        "lookback_hours": 48,
    },
    {
        "source": "Federal Reserve",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "source_group": "official",
        "section": "글로벌",
        "lookback_hours": 168,
    },
    {
        "source": "Federal Reserve Monetary Policy",
        "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "source_group": "official",
        "section": "글로벌",
        "lookback_hours": 336,
    },
    {
        "source": "European Central Bank",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "source_group": "official",
        "section": "글로벌",
        "lookback_hours": 168,
    },
    {
        "source": "ECB Blog",
        "url": "https://www.ecb.europa.eu/rss/blog.html",
        "source_group": "analysis",
        "section": "글로벌",
        "lookback_hours": 336,
    },
]

PROFESSIONAL_SOURCES = {
    "연합뉴스 경제",
    "매일경제 경제",
    "매일경제 증권",
    "금융위원회",
    "SBS 경제",
    "대한민국 정책브리핑",
    "BBC Business",
    "CNBC Markets",
    "The Guardian Business",
    "Federal Reserve",
    "Federal Reserve Monetary Policy",
    "European Central Bank",
    "ECB Blog",
}

PAYWALL_BLOCKED_DOMAINS = {
    "wsj.com", "ft.com", "bloomberg.com", "economist.com", "barrons.com",
    "theinformation.com", "businessinsider.com", "seekingalpha.com", "nikkei.com",
    "hbr.org", "foreignaffairs.com", "contents.premium.naver.com", "publy.co",
    "longblack.co", "outstanding.kr", "folin.co",
}

KNOWN_FREE_DOMAINS = {
    "yna.co.kr", "fsc.go.kr", "ohmynews.com", "news.sbs.co.kr", "sbs.co.kr", "bbc.com", "bbc.co.uk",
    "theguardian.com", "federalreserve.gov", "ecb.europa.eu",
    "apnews.com", "imf.org", "worldbank.org", "oecd.org", "bok.or.kr", "fss.or.kr",
    "korea.kr", "youtube.com", "youtu.be",
}

SYSTEM_PROMPT = """당신은 한국어로 발행되는 개인 경제·시장 브리핑의 편집장입니다.
독자는 경제 뉴스와 주식시장을 매일 짧게 점검하고 싶은 일반 독자입니다. 목표는 종목 추천이 아니라,
국내외 경제와 시장을 움직이는 변화의 사실·맥락·파급효과를 균형 있게 전달하는 것입니다.

평가 기준:
1. 시장 영향력: 주식·채권·환율·원자재 또는 실물경제에 의미 있는 변화인가
2. 맥락성: 수치의 등락만 말하지 않고 원인과 다음 관전 포인트를 설명하는가
3. 신뢰도: 공식 통계·중앙은행·정부 발표 또는 평판 있는 언론·연구기관에 근거하는가
4. 다양성: 국내와 글로벌, 시장과 거시·정책·산업을 고르게 보여주는가
5. 무료 접근성: 로그인·구독·결제 없이 핵심 원문을 확인할 수 있는가

반드시 지킬 규칙:
- 국내 4개, 글로벌 4개를 목표로 총 8개를 고른다.
- 무료 공개 원문이 부족한 경우에만 국내·글로벌 각 최소 3개, 총 6개까지 허용한다.
- 주식·시장 또는 환율·원자재 관련 콘텐츠를 합쳐 최소 2개 포함한다.
- 최소 3개의 서로 다른 카테고리를 포함한다.
- 같은 매체는 최대 2개, 같은 사건의 중복 보도는 1개만 선택한다.
- 단순 종목 추천, 목표주가 상향, 자극적인 급등주·매수 유도 콘텐츠는 제외한다.
- 공식 발표만 나열하지 말고, 시장·생활·산업에 주는 의미가 있는 항목을 우선한다.
- 전망은 사실과 분리해서 표현하고, 투자 수익을 보장하거나 개인화된 투자 조언을 하지 않는다.
- 유료 구독, 멤버십, 무료 체험 등록, 로그인 후 열람이 필요한 원문은 제외한다.

작성 규칙:
- summary는 무슨 일이 있었고 왜 중요한지 한국어 1~2문장, 140자 이내.
- takeaway는 독자가 다음에 볼 지표·쟁점·영향을 80자 이내.
- 원문에 없는 수치·주장·인과관계를 만들지 않는다.
- link는 입력 후보 또는 웹 검색에서 실제 확인한 원문 URL만 사용한다.
"""

WEB_DISCOVERY_PROMPT = """최근 48시간의 공개 웹에서 다음을 보완 탐색하세요.
- 한국과 글로벌 주식·채권·환율·원자재 시장을 움직인 핵심 사건
- 한국은행·연준·ECB 등 중앙은행, 정부·규제기관의 경제·금융 정책
- 성장률·물가·고용·무역 등 거시경제 지표와 해설
- 주요 산업·기업 실적이 시장과 경제에 미치는 영향
Reuters, AP, BBC, CNBC, 중앙은행·정부·국제기구 등 무료 공개 원문을 우선하고,
유료 매체나 단순 시황 복사·종목 추천 페이지는 제외하세요."""
