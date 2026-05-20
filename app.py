"""
(주)리치시스템 — 분양현장 시세조사 API
국토부 실거래 + 카카오 로컬 API 통합

배포: Render.com 무료 티어
환경변수 필요:
  - MOLIT_API_KEY: 공공데이터포털 서비스키 (국토부 실거래)
  - KAKAO_REST_KEY: 카카오 REST API 키
"""
import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# CORS 허용 도메인 (GitHub Pages + 로컬 테스트)
CORS(app, origins=[
    "https://arttoy61-png.github.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
])

# === API Keys ===
MOLIT_KEY = os.getenv('MOLIT_API_KEY', '')
KAKAO_KEY = os.getenv('KAKAO_REST_KEY', '')

# === 시군구 코드 매핑 (LAWD_CD 5자리) ===
SIGUNGU_CODES = {
    # 서울
    "종로구": "11110", "중구 서울": "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구": "11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
    # 부산
    "중구 부산": "26110", "서구 부산": "26140", "동구 부산": "26170", "영도구": "26200",
    "부산진구": "26230", "동래구": "26260", "남구 부산": "26290", "북구 부산": "26320",
    "해운대구": "26350", "사하구": "26380", "금정구": "26410", "강서구 부산": "26440",
    "연제구": "26470", "수영구": "26500", "사상구": "26530",
    # 울산
    "중구 울산": "31110", "남구 울산": "31140", "동구 울산": "31170", "북구 울산": "31200",
    "울주군": "31710",
    # 대구·광주·대전·인천·세종
    "수성구": "27260", "달서구": "27290", "남구 대구": "27200",
    "광산구": "29200", "서구 광주": "29140", "남구 광주": "29155",
    "유성구": "30200", "서구 대전": "30170", "중구 대전": "30110",
    "남동구": "28200", "연수구": "28185", "서구 인천": "28260", "부평구": "28237",
    "세종특별자치시": "36110",
    # 경기
    "수원시": "41110", "성남시": "41130", "안양시": "41170", "부천시": "41190",
    "광명시": "41210", "평택시": "41220", "안산시": "41270", "고양시": "41280",
    "과천시": "41290", "용인시": "41460", "파주시": "41480", "김포시": "41570",
}


def extract_sigungu(addr):
    """주소에서 시군구 추출 → 코드 반환"""
    # 광역시·도 정보 함께 고려 (예: '부산 동구' vs '서울 동작구')
    addr_clean = addr.replace('특별시', '').replace('광역시', '').replace('특별자치시', '')
    
    # 광역 + 구 패턴 매칭
    for k, code in SIGUNGU_CODES.items():
        parts = k.split()
        if len(parts) == 1:
            # 단일 키워드 (예: "강남구")
            if parts[0] in addr_clean:
                return code, k
        else:
            # 광역명 + 구 (예: "부산 해운대구")
            metro = parts[1]  # "부산", "서울", "대구" etc.
            district = parts[0]  # "중구", "동구" etc.
            if metro in addr_clean and district in addr_clean:
                return code, k
    
    return None, None


def geocode_kakao(addr):
    """카카오 주소 → 좌표"""
    if not KAKAO_KEY:
        return None
    try:
        r = requests.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params={"query": addr},
            timeout=5
        )
        if r.ok:
            docs = r.json().get('documents', [])
            if docs:
                d = docs[0]
                return {"lat": float(d['y']), "lng": float(d['x'])}
        # 키워드 검색 폴백
        r = requests.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params={"query": addr},
            timeout=5
        )
        if r.ok:
            docs = r.json().get('documents', [])
            if docs:
                d = docs[0]
                return {"lat": float(d['y']), "lng": float(d['x'])}
    except Exception as e:
        print(f"[geocode] {e}")
    return None


def fetch_molit_data(api_path, sigungu_code, months=6):
    """국토부 실거래 API 호출 (최근 N개월)"""
    if not MOLIT_KEY:
        return []
    
    results = []
    today = datetime.now()
    for i in range(months):
        target_date = today - timedelta(days=30 * i)
        deal_ym = target_date.strftime('%Y%m')
        
        url = f"https://apis.data.go.kr/1613000/{api_path}"
        params = {
            "serviceKey": MOLIT_KEY,
            "LAWD_CD": sigungu_code,
            "DEAL_YMD": deal_ym,
            "numOfRows": "100",
            "pageNo": "1",
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if not r.ok:
                continue
            root = ET.fromstring(r.text)
            for item in root.iter('item'):
                data = {}
                for child in item:
                    data[child.tag] = (child.text or '').strip()
                data['_deal_ym'] = deal_ym
                results.append(data)
        except Exception as e:
            print(f"[molit] {deal_ym}: {e}")
            continue
    
    return results


def parse_officetel_sale(item):
    """오피스텔 매매 데이터 정규화"""
    try:
        amount_str = item.get('거래금액') or item.get('dealAmount') or '0'
        amount = int(re.sub(r'[^\d]', '', amount_str))  # 만원
        area = float(item.get('전용면적') or item.get('excluUseAr') or 0)
        name = (item.get('단지') or item.get('offiNm') or '').strip()
        dong = (item.get('법정동') or item.get('umdNm') or '').strip()
        year = (item.get('건축년도') or item.get('buildYear') or '').strip()
        
        if area <= 0 or amount <= 0:
            return None
        
        # 평당가 계산 (만원/평)
        pyung = area / 3.3058  # ㎡ → 평
        pyung_price = round(amount / pyung) if pyung > 0 else 0
        
        return {
            "name": name,
            "dong": dong,
            "year": year,
            "area_m2": round(area, 1),
            "area_pyung": round(pyung, 1),
            "amount_manwon": amount,
            "pyung_price": pyung_price,
        }
    except Exception as e:
        print(f"[parse_sale] {e}")
        return None


def build_pricing_matrix(sales, top_n=8):
    """매매 데이터 → 비교군 매트릭스 (상위 N개)"""
    parsed = [parse_officetel_sale(s) for s in sales]
    parsed = [p for p in parsed if p is not None]
    
    if not parsed:
        return [], {}
    
    # 단지별 평균 (중복 제거)
    by_name = {}
    for p in parsed:
        key = p['name'] or f"{p['dong']}_{p['area_m2']}"
        if key not in by_name:
            by_name[key] = []
        by_name[key].append(p)
    
    aggregated = []
    for name, items in by_name.items():
        if not items:
            continue
        # 평균
        avg_amount = sum(i['amount_manwon'] for i in items) / len(items)
        avg_area = sum(i['area_m2'] for i in items) / len(items)
        avg_pyung_price = sum(i['pyung_price'] for i in items) / len(items)
        latest = max(items, key=lambda x: x['year'] or '0')
        
        aggregated.append({
            "name": items[0]['name'] or '단지명 미상',
            "dong": items[0]['dong'],
            "year": latest['year'],
            "area_m2": round(avg_area, 1),
            "amount_manwon": int(avg_amount),
            "pyung_price": int(avg_pyung_price),
            "sample_count": len(items),
        })
    
    # 정렬: 평당가 내림차순
    aggregated.sort(key=lambda x: x['pyung_price'], reverse=True)
    
    # 통계
    pyung_prices = [a['pyung_price'] for a in aggregated]
    stats = {
        "count": len(aggregated),
        "total_transactions": len(parsed),
        "min_pyung": min(pyung_prices) if pyung_prices else 0,
        "max_pyung": max(pyung_prices) if pyung_prices else 0,
        "avg_pyung": int(sum(pyung_prices) / len(pyung_prices)) if pyung_prices else 0,
        "median_pyung": sorted(pyung_prices)[len(pyung_prices)//2] if pyung_prices else 0,
    }
    
    return aggregated[:top_n], stats


def parse_officetel_rent(item):
    """오피스텔 전월세 정규화"""
    try:
        deposit_str = item.get('보증금액') or item.get('deposit') or '0'
        deposit = int(re.sub(r'[^\d]', '', deposit_str))  # 만원
        rent_str = item.get('월세') or item.get('monthlyRent') or '0'
        rent = int(re.sub(r'[^\d]', '', rent_str))  # 만원
        area = float(item.get('전용면적') or item.get('excluUseAr') or 0)
        
        if area <= 0:
            return None
        
        is_jeonse = rent == 0
        
        return {
            "deposit_manwon": deposit,
            "rent_manwon": rent,
            "area_m2": round(area, 1),
            "is_jeonse": is_jeonse,
        }
    except Exception:
        return None


def calc_rent_stats(rents):
    """전월세 통계"""
    parsed = [parse_officetel_rent(r) for r in rents]
    parsed = [p for p in parsed if p is not None]
    
    if not parsed:
        return {}
    
    jeonse = [p for p in parsed if p['is_jeonse']]
    wolse = [p for p in parsed if not p['is_jeonse']]
    
    stats = {"sample_count": len(parsed)}
    
    if jeonse:
        deposits = sorted([p['deposit_manwon'] for p in jeonse])
        stats['jeonse_min'] = deposits[0]
        stats['jeonse_max'] = deposits[-1]
        stats['jeonse_median'] = deposits[len(deposits)//2]
        stats['jeonse_count'] = len(deposits)
    
    if wolse:
        rents = sorted([p['rent_manwon'] for p in wolse])
        stats['wolse_min'] = rents[0]
        stats['wolse_max'] = rents[-1]
        stats['wolse_median'] = rents[len(rents)//2]
        stats['wolse_count'] = len(rents)
    
    return stats


# === Routes ===
@app.route('/')
def home():
    return jsonify({
        "service": "(주)리치시스템 분양 시세조사 API",
        "version": "1.0",
        "endpoints": {
            "/api/analyze": "GET ?address=주소&proj=현장명 → 시세 분석 JSON",
            "/api/health": "GET → 키 등록 상태 확인",
        }
    })


@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "molit_key": bool(MOLIT_KEY),
        "kakao_key": bool(KAKAO_KEY),
        "supported_sigungu": len(SIGUNGU_CODES),
        "now": datetime.now().isoformat(),
    })


@app.route('/api/analyze')
def analyze():
    address = request.args.get('address', '').strip()
    proj_name = request.args.get('proj', '').strip()
    months = int(request.args.get('months', 6))
    
    if not address:
        return jsonify({"error": "address parameter required"}), 400
    
    # 1. 시군구 코드 추출
    sigungu_code, sigungu_name = extract_sigungu(address)
    if not sigungu_code:
        return jsonify({
            "error": "지원하지 않는 지역 — 주소에서 시군구를 인식하지 못함",
            "address": address,
            "supported": list(SIGUNGU_CODES.keys()),
        }), 400
    
    # 2. 좌표 (카카오)
    coords = geocode_kakao(address)
    
    # 3. 국토부 매매 데이터
    sales = fetch_molit_data(
        "RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
        sigungu_code, months
    )
    
    # 4. 매트릭스 + 통계
    matrix, stats = build_pricing_matrix(sales, top_n=8)
    
    # 5. 전월세
    rents = fetch_molit_data(
        "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
        sigungu_code, months
    )
    rent_stats = calc_rent_stats(rents)
    
    return jsonify({
        "address": address,
        "proj_name": proj_name,
        "sigungu_code": sigungu_code,
        "sigungu_name": sigungu_name,
        "coords": coords,
        "pricing": {
            "comparables": matrix,
            "stats": stats,
        },
        "rent": rent_stats,
        "months_fetched": months,
        "fetched_at": datetime.now().isoformat(),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
