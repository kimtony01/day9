import os
import random
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from dotenv import load_dotenv

load_dotenv()
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY") or st.secrets.get("KAKAO_REST_API_KEY")

st.set_page_config(page_title="어디갈까? 여행 도우미", page_icon="🧭", layout="wide")

st.markdown("""
<style>
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 1200px;
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        text-align: center;
        margin-top: 0.5rem;
        margin-bottom: 0.2rem;
        background: linear-gradient(90deg, #FF6B35, #F7B32B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        text-align: center;
        font-size: 1.15rem;
        color: #888;
        margin-bottom: 1.2rem;
    }
    .loc-badge {
        text-align: center;
        color: #4CB963;
        font-size: 0.85rem;
        margin-bottom: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

if not KAKAO_REST_API_KEY:
    st.error(".env 파일 또는 Secrets에 KAKAO_REST_API_KEY가 설정되어 있지 않습니다.")
    st.stop()


# ================= 공통 유틸 함수 =================

def search_place(keyword: str, user_lat=None, user_lng=None):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": keyword}

    if user_lat is not None and user_lng is not None:
        params["x"] = user_lng
        params["y"] = user_lat
        params["sort"] = "distance"

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("documents", [])


def format_distance(distance_str):
    if not distance_str:
        return None
    try:
        meters = int(distance_str)
    except ValueError:
        return None
    if meters == 0:
        return None
    if meters < 1000:
        return f"{meters}m"
    return f"{meters / 1000:.1f}km"


def get_roadview_url(lat, lng):
    return f"https://map.kakao.com/link/roadview/{lat},{lng}"


def get_marker_emoji_color(place_name, category_name):
    name = place_name.replace(" ", "").lower()
    brand_styles = {
        "스타벅스": ("☕", "green"),
        "starbucks": ("☕", "green"),
        "이디야": ("☕", "blue"),
        "투썸플레이스": ("☕", "darkred"),
        "메가커피": ("☕", "orange"),
        "맥도날드": ("🍔", "red"),
        "버거킹": ("🍔", "darkred"),
        "롯데리아": ("🍔", "red"),
        "cu": ("🏪", "purple"),
        "gs25": ("🏪", "blue"),
        "세븐일레븐": ("🏪", "orange"),
        "올리브영": ("🧴", "lightgreen"),
    }
    for kw, (emoji, color) in brand_styles.items():
        if kw in name:
            return emoji, color
    if "카페" in category_name:
        return "☕", "cadetblue"
    if "음식점" in category_name:
        return "🍽️", "orange"
    if "편의점" in category_name:
        return "🏪", "gray"
    return "📍", "blue"


def render_place_card(i, place, key_prefix=""):
    name = place["place_name"]
    lat = float(place["y"])
    lng = float(place["x"])
    address = place.get("road_address_name") or place.get("address_name")
    category_name = place.get("category_name", "")
    emoji, _ = get_marker_emoji_color(name, category_name)
    dist_label = format_distance(place.get("distance"))
    roadview_url = get_roadview_url(lat, lng)
    place_url = place.get("place_url")

    with st.container(border=True):
        title_col, dist_col = st.columns([4, 1])
        with title_col:
            st.markdown(f"**{i}. {emoji} {name}**")
        with dist_col:
            if dist_label:
                st.caption(f"📍 {dist_label}")
        st.caption(address)

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.link_button("🚶 로드뷰", roadview_url, use_container_width=True, key=f"{key_prefix}rv_{i}")
        with btn_col2:
            if place_url:
                st.link_button("⭐ 평점/후기", place_url, use_container_width=True, key=f"{key_prefix}rt_{i}")
            else:
                st.button("⭐ 정보없음", disabled=True, use_container_width=True, key=f"{key_prefix}none_{i}")


def build_map(results, user_lat=None, user_lng=None):
    if user_lat is not None:
        center_lat, center_lng = user_lat, user_lng
    else:
        center_lat = float(results[0]["y"])
        center_lng = float(results[0]["x"])

    m = folium.Map(location=[center_lat, center_lng], zoom_start=15, tiles="OpenStreetMap")

    if user_lat is not None:
        folium.Marker(
            location=[user_lat, user_lng],
            popup="내 위치",
            tooltip="📍 내 위치",
            icon=folium.Icon(color="black", icon="user", prefix="fa"),
        ).add_to(m)

    for place in results:
        name = place["place_name"]
        lat = float(place["y"])
        lng = float(place["x"])
        address = place.get("road_address_name") or place.get("address_name")
        category_name = place.get("category_name", "")
        emoji, color = get_marker_emoji_color(name, category_name)
        dist_label = format_distance(place.get("distance"))
        roadview_url = get_roadview_url(lat, lng)
        place_url = place.get("place_url")

        popup_lines = [f"<b>{emoji} {name}</b>", address]
        if dist_label:
            popup_lines.append(f"내 위치에서 {dist_label}")
        popup_lines.append(f'<a href="{roadview_url}" target="_blank">🚶 로드뷰 보기</a>')
        if place_url:
            popup_lines.append(f'<a href="{place_url}" target="_blank">⭐ 평점/후기</a>')
        else:
            popup_lines.append("평점 정보 없음")
        popup_html = "<br>".join(popup_lines)

        folium.Marker(
            location=[lat, lng],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{emoji} {name}" + (f" · {dist_label}" if dist_label else ""),
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(m)

    return m


HERO_SVG = """<div style="text-align:center; margin-bottom: -1.2rem;">
<svg width="260" height="200" viewBox="0 0 260 200" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="130" cy="185" rx="90" ry="10" fill="#F3E9DC"/>
<rect x="40" y="140" width="180" height="10" rx="3" fill="#D9B48F"/>
<rect x="55" y="150" width="8" height="30" fill="#C9A47A"/>
<rect x="197" y="150" width="8" height="30" fill="#C9A47A"/>
<rect x="95" y="80" width="90" height="60" rx="6" fill="#3C3B6E"/>
<rect x="102" y="87" width="76" height="46" rx="3" fill="#EAF4FF"/>
<rect x="128" y="140" width="14" height="12" fill="#B0B0B0"/>
<rect x="115" y="151" width="40" height="6" rx="2" fill="#9C9C9C"/>
<circle cx="140" cy="110" r="16" fill="#CFE8CF"/>
<path d="M124 110c0-9 7-16 16-16s16 7 16 16-16 24-16 24-16-15-16-24z" fill="#FF6B35"/>
<circle cx="140" cy="108" r="5" fill="white"/>
<circle cx="75" cy="100" r="16" fill="#FFD6B8"/>
<path d="M50 150c0-18 12-32 25-32s25 14 25 32z" fill="#FF6B35"/>
<path d="M70 118c-8 4-14 12-16 20" stroke="#FFD6B8" stroke-width="7" stroke-linecap="round" fill="none"/>
<path d="M84 118c6 4 10 10 12 16" stroke="#FFD6B8" stroke-width="7" stroke-linecap="round" fill="none"/>
<circle cx="205" cy="55" r="14" fill="none" stroke="#F7B32B" stroke-width="5"/>
<line x1="215" y1="65" x2="228" y2="78" stroke="#F7B32B" stroke-width="5" stroke-linecap="round"/>
<path d="M40 60c0-7 5-12 12-12s12 5 12 12-12 18-12 18-12-11-12-18z" fill="#4CB963" opacity="0.85"/>
<circle cx="52" cy="59" r="4" fill="white"/>
</svg>
</div>"""

# 국내 여행지 큐레이션 데이터
DOMESTIC_DESTINATIONS = [
    {"name": "부산 해운대", "emoji": "🏖️", "desc": "탁 트인 해변과 야경, 광안대교가 매력적인 대표 해양 관광지.", "search": "해운대 해수욕장"},
    {"name": "제주도", "emoji": "🌴", "desc": "한라산, 오름, 에메랄드빛 바다까지 사계절 다른 매력의 섬.", "search": "제주공항"},
    {"name": "강릉", "emoji": "☕", "desc": "안목해변 커피거리와 경포호, 감성 여행지로 인기.", "search": "강릉 안목해변"},
    {"name": "경주", "emoji": "🏯", "desc": "불국사, 첨성대 등 신라 천년의 역사를 걸으며 느낄 수 있는 도시.", "search": "경주 불국사"},
    {"name": "여수", "emoji": "🌉", "desc": "여수 밤바다로 유명한 낭만적인 항구 도시.", "search": "여수 밤바다"},
    {"name": "전주 한옥마을", "emoji": "🏮", "desc": "전통 한옥과 골목, 다양한 먹거리가 있는 대표 전통문화 거리.", "search": "전주 한옥마을"},
]

# 해외 여행지 큐레이션 데이터 (카카오 API 범위 밖이라 정적 정보로 구성)
OVERSEAS_DESTINATIONS = [
    {"country": "일본 오사카", "emoji": "🇯🇵", "currency": "JPY", "season": "3~5월(벚꽃), 10~11월(단풍)",
     "desc": "도톤보리, 오사카성 등 먹거리와 볼거리가 풍부한 간사이 지역 관문."},
    {"country": "태국 방콕", "emoji": "🇹🇭", "currency": "THB", "season": "11~2월(건기)",
     "desc": "사원 투어와 야시장, 가성비 좋은 물가로 인기 있는 동남아 여행지."},
    {"country": "베트남 다낭", "emoji": "🇻🇳", "currency": "VND", "season": "2~8월(건기)",
     "desc": "미케 비치와 바나힐, 가족 여행지로 각광받는 휴양 도시."},
    {"country": "미국 뉴욕", "emoji": "🇺🇸", "currency": "USD", "season": "4~6월, 9~11월",
     "desc": "타임스퀘어, 센트럴파크 등 도시 여행의 정수를 느낄 수 있는 곳."},
    {"country": "프랑스 파리", "emoji": "🇫🇷", "currency": "EUR", "season": "4~6월, 9~10월",
     "desc": "에펠탑, 루브르 박물관 등 예술과 낭만의 도시."},
    {"country": "필리핀 세부", "emoji": "🇵🇭", "currency": "PHP", "season": "12~5월(건기)",
     "desc": "화이트비치와 스노클링으로 유명한 대표 휴양 섬."},
]

CURRENCY_OPTIONS = {
    "USD (미국 달러)": "USD",
    "JPY (일본 엔)": "JPY",
    "EUR (유로)": "EUR",
    "CNY (중국 위안)": "CNY",
    "GBP (영국 파운드)": "GBP",
    "THB (태국 바트)": "THB",
    "VND (베트남 동)": "VND",
    "PHP (필리핀 페소)": "PHP",
    "KRW (한국 원)": "KRW",
}


@st.cache_data(ttl=3600)
def get_exchange_rates(base_currency: str):
    """무료 환율 API(open.er-api.com)로 기준 통화 대비 환율표를 가져온다. 키 불필요."""
    url = f"https://open.er-api.com/v6/latest/{base_currency}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        raise ValueError("환율 정보를 가져오지 못했습니다.")
    return data["rates"], data.get("time_last_update_utc", "")


# ================= 세션 상태 초기화 =================
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""
if "food_keyword" not in st.session_state:
    st.session_state.food_keyword = ""
if "prefill_search" not in st.session_state:
    st.session_state.prefill_search = ""

# ---------- 위치 정보 (모든 메뉴 공통) ----------
location = get_geolocation()
user_lat, user_lng = None, None
if location and "coords" in location:
    user_lat = location["coords"]["latitude"]
    user_lng = location["coords"]["longitude"]

# ================= 사이드바 메뉴 =================
with st.sidebar:
    st.markdown("## 🧭 메뉴")
    menu = st.radio(
        "메뉴 선택",
        ["🗺️ 어디 갈까?", "🍚 오늘 뭐 먹지?", "✈️ 여행 준비 도우미"],
        label_visibility="collapsed",
    )
    st.divider()
    if user_lat is not None:
        st.caption("📍 내 위치 확인됨 — 거리 계산이 가능해요")
    else:
        st.caption("위치 권한을 허용하면 거리(m)도 함께 보여드려요")


# ================= 🗺️ 어디 갈까? =================
if menu == "🗺️ 어디 갈까?":
    st.markdown(HERO_SVG, unsafe_allow_html=True)
    st.markdown('<div class="hero-title">🧭 어디 갈까?</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">가고 싶은 곳을 자유롭게 검색해보세요!!</div>', unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 3, 1])
    with center_col:
        default_value = st.session_state.prefill_search or ""
        keyword_input = st.text_input(
            "장소 검색",
            value=default_value,
            placeholder="예: 강남역 스타벅스, 경복궁, 을지로 맛집 ...",
            label_visibility="collapsed",
            key="map_search_input",
        )
        search_clicked = st.button("🔍 검색하기", use_container_width=True)

    st.session_state.prefill_search = ""

    if search_clicked and keyword_input.strip():
        st.session_state.search_keyword = keyword_input.strip()

    keyword = st.session_state.search_keyword

    if not keyword:
        st.write("")
        tip_col1, tip_col2, tip_col3 = st.columns(3)
        with tip_col1:
            st.markdown("### ☕ 카페")
            st.caption("스타벅스, 이디야, 투썸플레이스처럼 브랜드명으로 검색해보세요")
        with tip_col2:
            st.markdown("### 🍽️ 맛집")
            st.caption("동네 이름 + 맛집으로 검색하면 주변 인기 장소가 쭉 나와요")
        with tip_col3:
            st.markdown("### 🏛️ 명소")
            st.caption("경복궁, N서울타워 같은 관광 명소도 검색 가능해요")
    else:
        results = search_place(keyword, user_lat, user_lng)

        if not results:
            st.warning(f"'{keyword}' 검색 결과가 없습니다.")
        else:
            st.markdown(f"#### '{keyword}' 검색 결과 **{len(results)}건**")
            st.write("")

            m = build_map(results, user_lat, user_lng)
            map_col, list_col = st.columns([3, 2], gap="large")

            with map_col:
                st.markdown("**🗺️ 지도** (마커를 클릭하면 로드뷰·평점 링크가 떠요)")
                st_folium(m, width=None, height=620, use_container_width=True)

            with list_col:
                st.markdown("**📋 결과 & 평점/후기**")
                list_area = st.container(height=620)
                with list_area:
                    for i, place in enumerate(results, start=1):
                        render_place_card(i, place, key_prefix="main_")


# ================= 🍚 오늘 뭐 먹지? =================
elif menu == "🍚 오늘 뭐 먹지?":
    st.markdown("## 🍚 오늘 뭐 먹지?")
    st.caption("주변 맛집을 추천해드려요. 음식 종류나 동네를 적어도 되고, 비워두면 아무거나 골라드려요!")

    food_col1, food_col2 = st.columns([4, 1])
    with food_col1:
        food_keyword_input = st.text_input(
            "밥 뭐먹지 검색",
            placeholder="예: 한식, 파스타, 강남 맛집 ... (비워두면 랜덤 추천)",
            label_visibility="collapsed",
            key="food_search_input",
        )
    with food_col2:
        food_search_clicked = st.button("🍽️ 추천받기", use_container_width=True)

    if food_search_clicked:
        st.session_state.food_keyword = food_keyword_input.strip()

    if st.session_state.food_keyword or food_search_clicked:
        query = st.session_state.food_keyword if st.session_state.food_keyword else "맛집"
        food_results = search_place(query, user_lat, user_lng)

        if not food_results:
            st.warning("추천할 만한 곳을 못 찾았어요. 다른 키워드로 시도해보세요.")
        else:
            pick = random.choice(food_results[: min(10, len(food_results))])
            st.success(f"오늘의 추천: **{pick['place_name']}** 어때요? 🍽️")

            pick_lat = float(pick["y"])
            pick_lng = float(pick["x"])
            pick_address = pick.get("road_address_name") or pick.get("address_name")
            dist_label = format_distance(pick.get("distance"))

            with st.container(border=True):
                st.markdown(f"### 🍽️ {pick['place_name']}")
                st.caption(pick_address + (f" · 내 위치에서 {dist_label}" if dist_label else ""))
                b1, b2 = st.columns(2)
                with b1:
                    st.link_button("🚶 로드뷰", get_roadview_url(pick_lat, pick_lng), use_container_width=True)
                with b2:
                    if pick.get("place_url"):
                        st.link_button("⭐ 평점/후기", pick["place_url"], use_container_width=True)
                    else:
                        st.button("⭐ 정보없음", disabled=True, use_container_width=True)

            st.write("")
            if st.button("🔄 다른 곳 추천받기"):
                st.rerun()

            with st.expander("다른 후보들도 보기"):
                for i, place in enumerate(food_results[:10], start=1):
                    if place is pick:
                        continue
                    render_place_card(i, place, key_prefix="food_")


# ================= ✈️ 여행 준비 도우미 =================
elif menu == "✈️ 여행 준비 도우미":
    st.markdown("## ✈️ 여행 준비 도우미")
    st.caption("국내/해외 여행지를 둘러보고, 환율 계산까지 한 번에!")

    tab_domestic, tab_overseas, tab_currency = st.tabs(["🇰🇷 국내 여행지", "🌍 해외 여행지", "💱 환율 계산기"])

    # ---------- 국내 여행지 ----------
    with tab_domestic:
        st.write("")
        cols = st.columns(2)
        for idx, dest in enumerate(DOMESTIC_DESTINATIONS):
            col = cols[idx % 2]
            with col:
                with st.container(border=True):
                    st.markdown(f"### {dest['emoji']} {dest['name']}")
                    st.write(dest["desc"])
                    if st.button("지도에서 보기", key=f"domestic_{idx}", use_container_width=True):
                        st.session_state.prefill_search = dest["search"]
                        st.session_state.search_keyword = dest["search"]
                        st.info("왼쪽 사이드바에서 '🗺️ 어디 갈까?' 메뉴를 눌러 지도를 확인하세요!")

    # ---------- 해외 여행지 ----------
    with tab_overseas:
        st.write("")
        st.caption("해외는 국내 지도 검색 대신 여행 참고 정보로 안내해드려요.")
        cols = st.columns(2)
        for idx, dest in enumerate(OVERSEAS_DESTINATIONS):
            col = cols[idx % 2]
            with col:
                with st.container(border=True):
                    st.markdown(f"### {dest['emoji']} {dest['country']}")
                    st.write(dest["desc"])
                    st.caption(f"💰 사용 통화: {dest['currency']}  ·  🗓️ 추천 시기: {dest['season']}")

    # ---------- 환율 계산기 ----------
    with tab_currency:
        st.write("")
        st.caption("실시간 환율 정보를 기준으로 계산합니다 (약 1시간 캐시).")

        calc_col1, calc_col2, calc_col3 = st.columns([2, 1, 2])
        with calc_col1:
            from_label = st.selectbox("변환할 통화", list(CURRENCY_OPTIONS.keys()), index=8)  # 기본 KRW
        with calc_col2:
            st.markdown("<div style='text-align:center; padding-top: 2rem;'>➡️</div>", unsafe_allow_html=True)
        with calc_col3:
            to_label = st.selectbox("도착 통화", list(CURRENCY_OPTIONS.keys()), index=0)  # 기본 USD

        amount = st.number_input("금액", min_value=0.0, value=10000.0, step=1000.0)

        if st.button("💱 환율 계산하기", use_container_width=True):
            from_code = CURRENCY_OPTIONS[from_label]
            to_code = CURRENCY_OPTIONS[to_label]

            try:
                rates, updated_at = get_exchange_rates(from_code)
                if to_code not in rates:
                    st.error("해당 통화의 환율 정보를 찾을 수 없습니다.")
                else:
                    converted = amount * rates[to_code]
                    st.success(f"{amount:,.0f} {from_code} = **{converted:,.2f} {to_code}**")
                    st.caption(f"기준 환율 업데이트: {updated_at}")
            except Exception as e:
                st.error(f"환율 정보를 가져오는 중 문제가 발생했습니다: {e}")