# -*- coding: utf-8 -*-
"""
========================================================================
  (주)리치시스템 — 분양현장 시세조사 API (백엔드)
  auto_report.py v1.1 의 검증된 로직을 Flask로 포팅
========================================================================
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

CORS(app, origins=[
    "https://arttoy61-png.github.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
])

MOLIT_KEY = os.getenv('MOLIT_API_KEY', '')
KAKAO_KEY = os.getenv('KAKAO_REST_KEY', '')

# === 국토부 실거래 API (auto_report.py와 동일) ===
MOLIT_ENDPOINTS = {
    "apt_sale":       "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "officetel_sale": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
    "apt_rent":       "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}

KAKAO_GEOCODE_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# === 법정동 코드 (auto_report.py LAWD_CODES + 확장) ===
LAWD_CODES = {
    # 울산 (auto_report.py 원본)
    "울산광역시 동구 일산동":  {"lawd_cd": "31170", "dong_cd": "3117010100"},
    "울산광역시 동구 미포동":  {"lawd_cd": "31170", "dong_cd": "3117010200"},
    "울산광역시 동구 전하동":  {"lawd_cd": "31170", "dong_cd": "3117010400"},
    "울산광역시 동구 동부동":  {"lawd_cd": "31170", "dong_cd": "3117010500"},
    "울산광역시 동구 서부동":  {"lawd_cd": "31170", "dong_cd": "3117010600"},
    "울산광역시 동구 방어동":  {"lawd_cd": "31170", "dong_cd": "3117010700"},
    "울산광역시 동구 화정동":  {"lawd_cd": "31170", "dong_cd": "3117010800"},
    "울산광역시 동구 남목동":  {"lawd_cd": "31170", "dong_cd": "3117010900"},
    "울산광역시 남구 신정동":  {"lawd_cd": "31140", "dong_cd": "3114010300"},
    "울산광역시 남구 야음동":  {"lawd_cd": "31140", "dong_cd": "3114010500"},
    "울산광역시 남구 삼산동":  {"lawd_cd": "31140", "dong_cd": "3114010800"},
    # 서울 강서구 (auto_report.py 원본)
    "서울특별시 강서구 화곡동": {"lawd_cd": "11500", "dong_cd": "1150010500"},
    "서울특별시 강서구 가양동": {"lawd_cd": "11500", "dong_cd": "1150010300"},
    "서울특별시 강서구 등촌동": {"lawd_cd": "11500", "dong_cd": "1150010400"},
    "서울특별시 강서구 염창동": {"lawd_cd": "11500", "dong_cd": "1150010200"},
    "서울특별시 강서구 발산동": {"lawd_cd": "11500", "dong_cd": "1150010700"},
    "서울특별시 강서구 마곡동": {"lawd_cd": "11500", "dong_cd": "1150010800"},
    "서울특별시 강서구 공항동": {"lawd_cd": "11500", "dong_cd": "1150010100"},
    # 서울 영등포 (파크라움 여의도)
    "서울특별시 영등포구 여의도동": {"lawd_cd": "11560", "dong_cd": "1156011000"},
    "서울특별시 영등포구 영등포동": {"lawd_cd": "11560", "dong_cd": "1156010100"},
    "서울특별시 영등포구 당산동":   {"lawd_cd": "11560", "dong_cd": "1156010400"},
    # 서울 양천
    "서울특별시 양천구 목동":   {"lawd_cd": "11470", "dong_cd": "1147010100"},
    "서울특별시 양천구 신정동": {"lawd_cd": "11470", "dong_cd": "1147010200"},
    "서울특별시 양천구 신월동": {"lawd_cd": "11470", "dong_cd": "1147010300"},
    # 서울 동대문
    "서울특별시 동대문구 답십리동": {"lawd_cd": "11230", "dong_cd": "1123010500"},
    "서울특별시 동대문구 청량리동": {"lawd_cd": "11230", "dong_cd": "1123010100"},
    "서울특별시 동대문구 전농동":   {"lawd_cd": "11230", "dong_cd": "1123010200"},
    "서울특별시 동대문구 회기동":   {"lawd_cd": "11230", "dong_cd": "1123010700"},
    # 서울 강남권
    "서울특별시 강남구 역삼동":   {"lawd_cd": "11680", "dong_cd": "1168010100"},
    "서울특별시 강남구 삼성동":   {"lawd_cd": "11680", "dong_cd": "1168010500"},
    "서울특별시 강남구 대치동":   {"lawd_cd": "11680", "dong_cd": "1168010600"},
    "서울특별시 강남구 논현동":   {"lawd_cd": "11680", "dong_cd": "1168010800"},
    "서울특별시 강남구 신사동":   {"lawd_cd": "11680", "dong_cd": "1168010700"},
    "서울특별시 서초구 서초동":   {"lawd_cd": "11650", "dong_cd": "1165010800"},
    "서울특별시 서초구 반포동":   {"lawd_cd": "11650", "dong_cd": "1165010700"},
    "서울특별시 송파구 잠실동":   {"lawd_cd": "11710", "dong_cd": "1171010100"},
    # 서울 마포·성수·용산
    "서울특별시 마포구 공덕동":   {"lawd_cd": "11440", "dong_cd": "1144010100"},
    "서울특별시 마포구 합정동":   {"lawd_cd": "11440", "dong_cd": "1144013800"},
    "서울특별시 마포구 상수동":   {"lawd_cd": "11440", "dong_cd": "1144014000"},
    "서울특별시 성동구 성수동":   {"lawd_cd": "11200", "dong_cd": "1120013100"},
    "서울특별시 용산구 한남동":   {"lawd_cd": "11170", "dong_cd": "1117011400"},
    "서울특별시 용산구 이태원동": {"lawd_cd": "11170", "dong_cd": "1117011700"},
    # 부산
    "부산광역시 해운대구 우동":   {"lawd_cd": "26350", "dong_cd": "2635010100"},
    "부산광역시 해운대구 중동":   {"lawd_cd": "26350", "dong_cd": "2635010200"},
    "부산광역시 해운대구 좌동":   {"lawd_cd": "26350", "dong_cd": "2635010400"},
    "부산광역시 수영구 광안동":   {"lawd_cd": "26500", "dong_cd": "2650010200"},
    # 경기·인천
    "경기도 성남시 분당구 정자동": {"lawd_cd": "41135", "dong_cd": "4113510800"},
    "경기도 성남시 분당구 서현동": {"lawd_cd": "41135", "dong_cd": "4113510700"},
    "인천광역시 연수구 송도동":    {"lawd_cd": "28185", "dong_cd": "2818510700"},
}

KNOWN_COMPLEXES = {
    "KCC스위첸 웰츠타워":   "울산광역시 동구 전하동",
    "KCC스위첸웰츠타워":     "울산광역시 동구 전하동",
    "웰츠타워":              "울산광역시 동구 전하동",
    "전하 KCC스위첸":        "울산광역시 동구 전하동",
    "아이파크 2단지":        "울산광역시 동구 전하동",
    "e편한세상 전하":        "울산광역시 동구 전하동",
    "울산전하 푸르지오":     "울산광역시 동구 전하동",
    "베스티안":              "울산광역시 동구 전하동",
    "파크라움 여의도":       "서울특별시 영등포구 여의도동",
    "파크라움":              "서울특별시 영등포구 여의도동",
}


def normalize_input(user_input):
    """auto_report.py normalize_input과 동일"""
    s = (user_input or "").strip()
    if not s:
        return None
    s_nospace = s.replace(" ", "")
    for complex_name, full_addr in KNOWN_COMPLEXES.items():
        if complex_name.replace(" ", "") in s_nospace:
            return full_addr
    for full_addr in LAWD_CODES.keys():
        m = re.search(r'(\S+동)\b', full_addr)
        if m:
            dong = m.group(1)
            if dong in s:
                return full_addr
    if s in LAWD_CODES:
        return s
    return None


def get_codes(full_addr):
    info = LAWD_CODES.get(full_addr)
    if info:
        return info["lawd_cd"], info["dong_cd"]
    return None, None


def fetch_molit(api_name, lawd_cd, ymd, page=1, num_rows=100):
    """국토부 API 호출 (auto_report.py와 동일)"""
    url = MOLIT_ENDPOINTS[api_name]
    params = {
        "serviceKey": MOLIT_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": ymd,
        "pageNo": page,
        "numOfRows": num_rows,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return parse_molit_xml(r.text)
    except Exception as e:
        print(f"[molit] {api_name} {ymd}: {e}")
        return []


def parse_molit_xml(xml_text):
    out = []
    try:
        root = ET.fromstring(xml_text)
        result_code = root.findtext(".//resultCode")
        if result_code and result_code != "000":
            msg = root.findtext(".//resultMsg")
            print(f"[molit] code={result_code}: {msg}")
            return []
        for item in root.iter("item"):
            d = {}
            for child in item:
                d[child.tag] = (child.text or "").strip()
            out.append(d)
    except ET.ParseError as e:
        print(f"[molit] XML 파싱 오류: {e}")
    return out


def collect_transactions(lawd_cd, months_back=3):
    """병렬 호출 — 3개 API × N개월 동시 처리 (10초 내 완료)"""
    now = datetime.now()
    months = [(now - timedelta(days=30 * i)).strftime("%Y%m") for i in range(months_back)]
    all_tx = {"apt_sale": [], "officetel_sale": [], "apt_rent": []}
    
    # 모든 (API × 월) 조합 작업 목록
    tasks = []
    for ymd in months:
        for api_name in all_tx.keys():
            tasks.append((api_name, ymd))
    
    # 6개 worker 병렬 실행
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_task = {
            executor.submit(fetch_molit, api_name, lawd_cd, ymd): (api_name, ymd)
            for api_name, ymd in tasks
        }
        for future in as_completed(future_to_task):
            api_name, ymd = future_to_task[future]
            try:
                rows = future.result(timeout=25)
                for r in rows:
                    r["_category"] = api_name
                    r["_ymd"] = ymd
                all_tx[api_name].extend(rows)
            except Exception as e:
                print(f"[parallel] {api_name} {ymd}: {e}")
    
    return all_tx


def to_num(s):
    if s is None: return 0
    s = str(s).replace(",", "").replace(" ", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return 0


def calc_pyeong_price(deal_amt_man_won, area_sqm):
    """평당가 = 거래금액(만원) / (전용면적㎡ × 0.3025)"""
    if area_sqm <= 0:
        return 0
    return round(deal_amt_man_won / (area_sqm * 0.3025), 1)


def process_transactions(tx_data):
    """auto_report.py와 완전 동일"""
    cleaned = []
    for t in tx_data.get("apt_sale", []):
        try:
            amt = to_num(t.get("dealAmount", ""))
            area = to_num(t.get("excluUseAr", ""))
            if amt <= 0 or area <= 0:
                continue
            cleaned.append({
                "category": "아파트 매매",
                "name": t.get("aptNm", "").strip(),
                "dong": t.get("umdNm", "").strip(),
                "area": area,
                "pyeong": round(area * 0.3025, 1),
                "amount_man": amt,
                "pyeong_price_man": calc_pyeong_price(amt, area),
                "floor": t.get("floor", ""),
                "deal_date": f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}",
                "build_year": t.get("buildYear", ""),
            })
        except Exception:
            continue
    for t in tx_data.get("officetel_sale", []):
        try:
            amt = to_num(t.get("dealAmount", ""))
            area = to_num(t.get("excluUseAr", ""))
            if amt <= 0 or area <= 0:
                continue
            cleaned.append({
                "category": "오피스텔 매매",
                "name": t.get("offiNm", "").strip(),
                "dong": t.get("umdNm", "").strip(),
                "area": area,
                "pyeong": round(area * 0.3025, 1),
                "amount_man": amt,
                "pyeong_price_man": calc_pyeong_price(amt, area),
                "floor": t.get("floor", ""),
                "deal_date": f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}",
                "build_year": t.get("buildYear", ""),
            })
        except Exception:
            continue
    for t in tx_data.get("apt_rent", []):
        try:
            deposit = to_num(t.get("deposit", ""))
            monthly = to_num(t.get("monthlyRent", ""))
            area = to_num(t.get("excluUseAr", ""))
            if area <= 0:
                continue
            cleaned.append({
                "category": "전세" if monthly == 0 else "월세",
                "name": t.get("aptNm", "").strip(),
                "dong": t.get("umdNm", "").strip(),
                "area": area,
                "pyeong": round(area * 0.3025, 1),
                "deposit_man": deposit,
                "monthly_man": monthly,
                "floor": t.get("floor", ""),
                "deal_date": f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}",
            })
        except Exception:
            continue
    return cleaned


def aggregate_by_complex(transactions):
    """단지별 그룹핑 (auto_report.py와 동일)"""
    by_complex = {}
    for t in transactions:
        if "pyeong_price_man" not in t:
            continue
        name = t["name"]
        if not name:
            continue
        if name not in by_complex:
            by_complex[name] = {
                "name": name,
                "build_year": t.get("build_year", ""),
                "transactions": [],
                "pyeong_prices": [],
                "latest_date": "",
                "category": t.get("category", ""),
                "dong": t.get("dong", ""),
            }
        by_complex[name]["transactions"].append(t)
        by_complex[name]["pyeong_prices"].append(t["pyeong_price_man"])
        if t["deal_date"] > by_complex[name]["latest_date"]:
            by_complex[name]["latest_date"] = t["deal_date"]
            by_complex[name]["latest_tx"] = t
            by_complex[name]["build_year"] = t.get("build_year") or by_complex[name].get("build_year","")
    
    result = []
    for name, info in by_complex.items():
        prices = info["pyeong_prices"]
        info["avg_pyeong_price"] = round(sum(prices) / len(prices), 0) if prices else 0
        info["tx_count"] = len(info["transactions"])
        result.append(info)
    result.sort(key=lambda x: (x["latest_date"], x["avg_pyeong_price"]), reverse=True)
    return result


def calc_rent_stats(transactions):
    jeonse = [t for t in transactions if t.get("category") == "전세"]
    wolse  = [t for t in transactions if t.get("category") == "월세"]
    stats = {"sample_count": len(jeonse) + len(wolse)}
    if jeonse:
        deps = sorted([t["deposit_man"] for t in jeonse if t.get("deposit_man",0) > 0])
        if deps:
            stats.update({
                "jeonse_min": deps[0],
                "jeonse_median": deps[len(deps)//2],
                "jeonse_max": deps[-1],
                "jeonse_count": len(deps),
            })
    if wolse:
        rents = sorted([t["monthly_man"] for t in wolse if t.get("monthly_man",0) > 0])
        if rents:
            stats.update({
                "wolse_min": rents[0],
                "wolse_median": rents[len(rents)//2],
                "wolse_max": rents[-1],
                "wolse_count": len(rents),
            })
    return stats


def kakao_geocode(addr):
    if not KAKAO_KEY:
        return None
    try:
        r = requests.get(KAKAO_GEOCODE_URL,
                         headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
                         params={"query": addr}, timeout=10)
        if r.ok:
            docs = r.json().get("documents", [])
            if docs:
                return {"lat": float(docs[0]["y"]), "lng": float(docs[0]["x"])}
        r = requests.get(KAKAO_KEYWORD_URL,
                         headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
                         params={"query": addr}, timeout=10)
        if r.ok:
            docs = r.json().get("documents", [])
            if docs:
                return {"lat": float(docs[0]["y"]), "lng": float(docs[0]["x"])}
    except Exception as e:
        print(f"[kakao] {e}")
    return None


@app.route('/')
def home():
    return jsonify({
        "service": "(주)리치시스템 분양 시세조사 API",
        "version": "1.1",
        "based_on": "auto_report.py v1.1 (검증된 로직)",
        "endpoints": {
            "/api/analyze": "GET ?address=주소&proj=현장명&months=N",
            "/api/health":  "GET 키 등록 상태 확인",
        }
    })


@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "molit_key": bool(MOLIT_KEY),
        "kakao_key": bool(KAKAO_KEY),
        "supported_dongs": len(LAWD_CODES),
        "known_complexes": len(KNOWN_COMPLEXES),
        "now": datetime.now().isoformat(),
    })


@app.route('/api/analyze')
def analyze():
    address = request.args.get('address', '').strip()
    proj_name = request.args.get('proj', '').strip()
    months = int(request.args.get('months', 3))
    
    if not address:
        return jsonify({"error": "address parameter required"}), 400
    
    # 1. 주소 정규화 (현장명 먼저 시도 → 주소)
    full_addr = normalize_input(proj_name) or normalize_input(address)
    if not full_addr:
        return jsonify({
            "error": "지원하지 않는 지역 — 동 인식 실패",
            "address": address,
            "hint": "주소에 동 이름이 포함되어야 합니다",
            "supported_count": len(LAWD_CODES),
        }), 400
    
    # 2. 코드
    lawd_cd, dong_cd = get_codes(full_addr)
    
    # 3. 좌표
    coords = kakao_geocode(address) or kakao_geocode(full_addr)
    
    # 4. 국토부 데이터 (3개 API × N개월)
    tx_data = collect_transactions(lawd_cd, months_back=months)
    
    # 5. 정제 + 집계
    cleaned = process_transactions(tx_data)
    sales = [t for t in cleaned if "pyeong_price_man" in t]
    rents = [t for t in cleaned if t.get("category") in ("전세", "월세")]
    complexes = aggregate_by_complex(sales)
    
    # 6. 통계
    pyung_prices = [c["avg_pyeong_price"] for c in complexes if c["avg_pyeong_price"] > 0]
    if pyung_prices:
        stats = {
            "count": len(complexes),
            "total_transactions": len(sales),
            "min_pyung": int(min(pyung_prices)),
            "max_pyung": int(max(pyung_prices)),
            "avg_pyung": int(sum(pyung_prices) / len(pyung_prices)),
            "median_pyung": int(sorted(pyung_prices)[len(pyung_prices)//2]),
        }
    else:
        stats = {"count": 0, "total_transactions": 0, "min_pyung": 0,
                 "max_pyung": 0, "avg_pyung": 0, "median_pyung": 0}
    
    # 7. 상위 8개 비교군
    top_comparables = []
    for c in complexes[:8]:
        latest = c.get("latest_tx", {})
        top_comparables.append({
            "name": c["name"],
            "dong": c.get("dong", ""),
            "year": c.get("build_year", "—"),
            "area_m2": latest.get("area", 0),
            "area_pyung": latest.get("pyeong", 0),
            "amount_manwon": latest.get("amount_man", 0),
            "pyung_price": int(c["avg_pyeong_price"]),
            "tx_count": c["tx_count"],
            "latest_date": c.get("latest_date", ""),
            "category": c.get("category", ""),
        })
    
    rent_stats = calc_rent_stats(rents)
    
    return jsonify({
        "address": address,
        "proj_name": proj_name,
        "normalized_addr": full_addr,
        "lawd_cd": lawd_cd,
        "dong_cd": dong_cd,
        "coords": coords,
        "pricing": {
            "comparables": top_comparables,
            "stats": stats,
        },
        "rent": rent_stats,
        "months_fetched": months,
        "fetched_at": datetime.now().isoformat(),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"  (주)리치시스템 분양 시세조사 API")
    print(f"  포트: {port}")
    print(f"  국토부: {'✓' if MOLIT_KEY else '✗'} / 카카오: {'✓' if KAKAO_KEY else '✗'}")
    print(f"  지원 동: {len(LAWD_CODES)}개")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
