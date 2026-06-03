from re import A
import time
import requests
from src.config import Parser
from structlog import BoundLogger
from src.excel_handler import ExcelHandler, DataSetType

GET_OKRUG_URL = "/rs/suggest/address"
GET_KATEGORY_URL = "/interpreter"
GET_ECOLOGY_RATE_URL = "/feed/geo"
GET_ROUTING_URL = "/driving"
DELAY = 1
MAX_RESULTS = 20

# Теги OpenStreetMap для каждой категории
OSM_FILTERS = {
    "metro": '["station"="subway"]',
    "bus_stop": '["highway"="bus_stop"]',
    "hospital": '["amenity"="hospital"]',
    "clinic": '["amenity"~"clinic|doctors"]',
    "school": '["amenity"="school"]',
    "kindergarten": '["amenity"="kindergarten"]',
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "canteen": '["amenity"~"canteen|cafeteria"]',
    "fast_food": '["amenity"="fast_food"]',
    "museum": '["tourism"="museum"]',
    "cultural_heritage": '["historic"]',
    "theatre": '["amenity"="theatre"]',
    "government": '["office"~"government|administrative"]',
    "mfc": '["name"~"МФЦ",i]',
}


class ApiCollector:
    def __init__(self, cfg: Parser, logger: BoundLogger, excel_handler: ExcelHandler,  radius=1000):
        self.radius = radius
        self.cfg: Parser = cfg
        self.logger: BoundLogger = logger.bind(service="ApiCollector")
        self.excel_handler: ExcelHandler = excel_handler

    def all_api_collect(self):
        df = self.excel_handler.get_df(DataSetType.TEMP)
        
        count = 0
        cords = [[0, 0] for _ in range(len(df))]
        districts = ["" for _ in range(len(df))]
        for i, row in df.iterrows():
            self.logger.info(f"district: {i}")
            
            try:
                data = self.get_okrug(row["Адрес"])
            except Exception as e:
                self.logger.error(f"failed to get district with first key: {e}")
                
                count += 1
                
                try:
                    data = self.get_okrug(row["Адрес"])
                except Exception as e:
                    self.logger.error(f"failed to get district with second key: {e}")
                    continue
                
            districts[i] = data.get("city_area", "")
            cords[i] = (data.get("geo_lat", 0), data.get("geo_lon", 0))
                
            time.sleep(0.01)
            
        df["АО"] = districts
        self.logger.info("successfully collected geocoding data")
        
        eco_rating = [0 for _ in range(len(df))]
        for i, cord in enumerate(cords):
            self.logger.info(f"eco: {i}")
            
            if cord[0] == 0 and cord[1] == 0:
                continue
            
            try:
                aqi = self.get_ecology_rating(cord[0], cord[1])
            
            except Exception as e:
                self.logger.error(f"failed to get eco_rating: {e}")
                continue
                
            eco_rating[i] = aqi
            time.sleep(0.1)
        
        df["Качество воздуха"] = eco_rating
        self.logger.info("successfully collected eco rating")

        distances = [0 for _ in range(len(df))]
        for i, cord in enumerate(cords):
            self.logger.info(f"distance: {i}")
            
            if cord[0] == 0 and cord[1] == 0:
                continue
                        
            try:
                distance = self.get_mocsow_center_distance(cord[0], cord[1])
        
            except Exception as e:
                self.logger.error(f"failed to get distance: {e}")
                continue
            
            distances[i] = distance
            time.sleep(0.1)
            
        df["Расстояние до центра"] = distances
        self.logger.info("successfully collected distances")
        
        # for i, address in enumerate(df["Адрес"]):
        #     self.logger.error(self.find(address).__str__())
        #     time.sleep(1)
        
        self.logger.info("successfully collected ecosystem")
        
        self.excel_handler.save(DataSetType.PROCESSED, df)
        
    def geocode(self, address):
        resp = requests.get(self.cfg.yandex_api.geocode_url, params={
            "geocode": address,
            "format": "json",
            "results": 1,
            "lang": "ru_RU",
            "apikey": self.cfg.yandex_api.geocode_api_key,
        }, timeout=10)

        resp.raise_for_status()
        members = resp.json()["response"]["GeoObjectCollection"]["featureMember"]
        if not members:
            raise Exception(f"Адрес не найден: {address}")
        lon_str, lat_str = members[0]["GeoObject"]["Point"]["pos"].split()
        return float(lat_str), float(lon_str)

    def search_category(self, lat, lon, category):
        query = f"""
[out:json];
nwr{OSM_FILTERS[category]}(around:{self.radius},{lat},{lon});
out center {MAX_RESULTS};
"""
        for attempt in range(3):
            try:
                resp = requests.post(f"{self.cfg.yandex_api.overpass_url}", data=query, timeout=30)
                resp.raise_for_status()
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
        else:
            return []
        places = []
        for el in resp.json().get("elements", []):
            tags = el.get("tags", {})
            if el["type"] == "node":
                p_lat, p_lon = el["lat"], el["lon"]
            else:
                p_lat = el.get("center", {}).get("lat", 0)
                p_lon = el.get("center", {}).get("lon", 0)

            street = tags.get("addr:street", "")
            house = tags.get("addr:housenumber", "")
            address = f"{street} {house}".strip()

            place = {
                "name": tags.get("name", ""),
                "category": category,
                "address": address,
                "lat": p_lat,
                "lon": p_lon,
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "url": tags.get("website") or tags.get("contact:website"),
            }
            places.append(place)

        return places

    def find(self, address, categories=None):
        if categories is None:
            categories = list(OSM_FILTERS.keys())
        lat, lon = self.geocode(address)
        result = {}
        for cat in categories:
            places = self.search_category(lat, lon, cat)
            result[cat] = places
            time.sleep(DELAY)
        return result

    def get_okrug(self, address) -> dict:
        resp = requests.post(f"{self.cfg.dadata_api.base_url}{GET_OKRUG_URL}",
                             json={
                                 "query": address,
                                 "count": 1,
                             },
                             headers={"Content-Type": "application/json",
                                      "Accept": "application/json",
                                      "Authorization": f"Token {self.cfg.dadata_api.api_key}"
                                      },
                             timeout=30)

        resp.raise_for_status()
        self.logger.debug(f"DaData response for address '{address}'")
        
        suggestions = resp.json().get("suggestions", [])

        if not suggestions:
            return {}

        data = suggestions[0].get("data", {})
        return data

    def get_ecology_rating(self, lat, lon) -> int:
        resp = requests.get(f"{self.cfg.aqicn_api.base_url}{GET_ECOLOGY_RATE_URL}:{lat};{lon}/",
                            params={
                                "token": self.cfg.aqicn_api.api_key,
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                            },
                            timeout=10)

        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("aqi", 0)

    def get_mocsow_center_distance(self, lat, lon) -> int:
        moscow_center = "37.6176,55.7558"
        
        resp = requests.get(f"{self.cfg.yandex_api.routing_url}{GET_ROUTING_URL}/{lon},{lat};{moscow_center}",
                            params={
                                "overview": "false",
                                "steps": "false",
                                "alternatives": "false"
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                            },
                            timeout=10)

        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            return 0
        
        routes = data.get("routes", [])
        if not routes:
            return 0
        
        return routes[0].get("distance", 0)
