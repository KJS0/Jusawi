from __future__ import annotations

"""
GPS 좌표를 주소로 변환하는 Geocoding 모듈
한국: Kakao Map API 사용 (도로명주소 우선, 지번주소 대체)
해외: Google Maps Geocoding API 사용
"""

import os
import logging
from typing import Optional, Dict

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv() -> None:  # type: ignore
        pass

logger = logging.getLogger(__name__)

# 환경 변수 로드(있으면 사용)
try:
    load_dotenv()
except Exception:
    pass

PROVINCE_MAPPING = {
    '서울특별시': '서울특별시',  # 2024 개정명칭 대응(없으면 원본 유지)
    '서울시': '서울특별시',
    '서울': '서울특별시',
    '부산광역시': '부산광역시',
    '부산시': '부산광역시',
    '부산': '부산광역시',
    '대구광역시': '대구광역시',
    '대구시': '대구광역시',
    '대구': '대구광역시',
    '인천광역시': '인천광역시',
    '인천시': '인천광역시',
    '인천': '인천광역시',
    '광주광역시': '광주광역시',
    '광주시': '광주광역시',
    '광주': '광주광역시',
    '대전광역시': '대전광역시',
    '대전시': '대전광역시',
    '대전': '대전광역시',
    '울산광역시': '울산광역시',
    '울산시': '울산광역시',
    '울산': '울산광역시',
    '세종특별자치시': '세종특별자치시',
    '세종시': '세종특별자치시',
    '세종': '세종특별자치시',
    '경기': '경기도',
    '경기도': '경기도',
    '강원': '강원특별자치도',
    '강원도': '강원특별자치도',
    '강원특별자치도': '강원특별자치도',
    '충북': '충청북도',
    '충청북도': '충청북도',
    '충남': '충청남도',
    '충청남도': '충청남도',
    '전북': '전북특별자치도',
    '전라북도': '전북특별자치도',
    '전북특별자치도': '전북특별자치도',
    '전남': '전라남도',
    '전라남도': '전라남도',
    '경북': '경상북도',
    '경상북도': '경상북도',
    '경남': '경상남도',
    '경상남도': '경상남도',
    '제주': '제주특별자치도',
    '제주도': '제주특별자치도',
    '제주특별자치도': '제주특별자치도'
}


def standardize_province_name(address: str) -> str:
    if not address:
        return address
    # 긴 키부터 치환
    for short_name, full_name in sorted(PROVINCE_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
        if address.startswith(short_name + ' '):
            return address.replace(short_name + ' ', full_name + ' ', 1)
        if address.startswith(short_name):
            return address.replace(short_name, full_name, 1)
    return address


class GeocodingService:
    def __init__(self):
        self.kakao_api_key = os.getenv('KAKAO_REST_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.kakao_api_key:
            logger.info("Kakao API 키 미설정 — 한국 주소 변환 비활성화")
        if not self.google_api_key:
            logger.info("Google Maps API 키 미설정 — 해외 주소 변환 비활성화")

    def is_korea_coordinate(self, latitude: float, longitude: float) -> bool:
        return (33.0 <= float(latitude) <= 38.6) and (124.0 <= float(longitude) <= 132.0)

    def get_address_from_coordinates(self, latitude: float, longitude: float, language: str | None = None) -> Optional[Dict]:
        try:
            if requests is None:
                return None
            if self.is_korea_coordinate(latitude, longitude):
                return self._get_korea_address(latitude, longitude)
            # 국제 주소: 언어 코드 전달(기본 ko)
            lang = (language or "ko").strip() or "ko"
            return self._get_international_address(latitude, longitude, language=lang)
        except Exception:
            return None

    def _get_korea_address(self, latitude: float, longitude: float) -> Optional[Dict]:
        if not self.kakao_api_key or requests is None:
            return None
        try:
            url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
            headers = {"Authorization": f"KakaoAK {self.kakao_api_key}"}
            params = {"x": longitude, "y": latitude, "input_coord": "WGS84"}
            resp = requests.get(url, headers=headers, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            docs = data.get('documents', [])
            if not docs:
                return None
            doc = docs[0]
            road = (doc.get('road_address') or {})
            addr = (doc.get('address') or {})
            if road:
                full = road.get('address_name', '')
                a_type = '도로명'
            elif addr:
                full = addr.get('address_name', '')
                a_type = '지번'
            else:
                return None
            full = standardize_province_name(full)
            return {
                'country': '대한민국',
                'full_address': full,
                'address_type': a_type,
                'coordinates': f"{latitude}, {longitude}",
                'formatted': f"{full} ({a_type})",
            }
        except Exception:
            return None

    def _get_international_address(self, latitude: float, longitude: float, language: str = "ko") -> Optional[Dict]:
        if not self.google_api_key or requests is None:
            return None
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"latlng": f"{latitude},{longitude}", "key": self.google_api_key, "language": str(language or "ko")}
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if data.get('status') != 'OK':
                return None
            results = data.get('results', [])
            if not results:
                return None
            best = results[0]
            full = best.get('formatted_address', '')
            return {
                'country': '',
                'full_address': full,
                'address_type': '해외주소',
                'coordinates': f"{latitude}, {longitude}",
                'formatted': full,
            }
        except Exception:
            return None


# 전역 인스턴스
geocoding_service = GeocodingService()


def get_google_static_map_png(latitude: float, longitude: float, width: int = 640, height: int = 400, zoom: int = 15) -> Optional[bytes]:
    """Google Static Maps PNG 바이트를 반환. 키 없거나 실패 시 None.

    주의: Google Cloud에서 Static Maps API가 활성화되어 있어야 합니다.
    """
    try:
        if requests is None:
            return None
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            return None
        w = max(64, min(640, int(width)))
        h = max(64, min(640, int(height)))
        z = max(1, min(20, int(zoom)))
        url = "https://maps.googleapis.com/maps/api/staticmap"
        params = {
            "center": f"{float(latitude)},{float(longitude)}",
            "zoom": str(z),
            "size": f"{w}x{h}",
            "maptype": "roadmap",
            "markers": f"color:red|{float(latitude)},{float(longitude)}",
            "key": api_key,
            "scale": "3",  # 고해상도 요청(가능 시)
        }
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code != 200:
            return None
        ctype = resp.headers.get("Content-Type", "")
        if "image" not in ctype:
            return None
        return resp.content
    except Exception:
        return None


