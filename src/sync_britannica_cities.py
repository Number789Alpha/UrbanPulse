import sys
import time
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from src.db import init_db, engine
from src.load import get_or_create_city, upsert_daily_metrics
from src.fetch import fetch_daily_forecast, fetch_air_quality
from src.transform import transform_weather_daily, transform_air_quality_hourly, merge_and_clean_metrics
from src.analytics import (
    compute_environmental_score,
    compute_activity_index,
    compute_city_risk_score,
    get_historical_and_anomaly_stats
)
from src.ai_narrate import generate_ai_narrative

RAW_BRITANNICA_LIST = """
Andaman and Nicobar Islands (union territory)
Port Blair
Andhra Pradesh
Adoni
Amaravati
Anantapur
Chandragiri
Chittoor
Dowlaiswaram
Eluru
Guntur
Kadapa
Kakinada
Kurnool
Machilipatnam
Nagarjunakonda
Rajahmundry
Srikakulam
Tirupati
Vijayawada
Visakhapatnam
Vizianagaram
Yemmiganur
Arunachal Pradesh
Itanagar
Assam
Dhuburi
Dibrugarh
Dispur
Guwahati
Jorhat
Nagaon
Sivasagar
Silchar
Tezpur
Tinsukia
Bihar
Ara
Barauni
Begusarai
Bettiah
Bhagalpur
Bihar Sharif
Bodh Gaya
Buxar
Chapra
Darbhanga
Dehri
Dinapur Nizamat
Gaya
Hajipur
Jamalpur
Katihar
Madhubani
Motihari
Munger
Muzaffarpur
Patna
Purnia
Pusa
Saharsa
Samastipur
Sasaram
Sitamarhi
Siwan
Chandigarh (union territory)
Chandigarh
Chhattisgarh
Ambikapur
Bhilai
Bilaspur
Dhamtari
Durg
Jagdalpur
Raipur
Rajnandgaon
Dadra and Nagar Haveli and Daman and Diu (union territory)
Daman
Diu
Silvassa
Delhi (national capital territory)
Delhi
New Delhi
Goa
Madgaon
Panaji
Gujarat
Ahmadabad
Amreli
Bharuch
Bhavnagar
Bhuj
Dwarka
Gandhinagar
Godhra
Jamnagar
Junagadh
Kandla
Khambhat
Kheda
Mahesana
Morbi
Nadiad
Navsari
Okha
Palanpur
Patan
Porbandar
Rajkot
Surat
Surendranagar
Valsad
Veraval
Haryana
Ambala
Bhiwani
Faridabad
Firozpur Jhirka
Gurugram
Hansi
Hisar
Jind
Kaithal
Karnal
Kurukshetra
Panipat
Pehowa
Rewari
Rohtak
Sirsa
Sonipat
Himachal Pradesh
Bilaspur
Chamba
Dalhousie
Dharmshala
Hamirpur
Kangra
Kullu
Mandi
Nahan
Shimla
Una
Jammu and Kashmir (union territory)
Anantnag
Baramula
Doda
Gulmarg
Jammu
Kathua
Punch
Rajouri
Srinagar
Udhampur
Jharkhand
Bokaro
Chaibasa
Deoghar
Dhanbad
Dumka
Giridih
Hazaribag
Jamshedpur
Jharia
Rajmahal
Ranchi
Saraikela
Karnataka
Badami
Ballari
Bengaluru
Belagavi
Bhadravati
Bidar
Chikkamagaluru
Chitradurga
Davangere
Halebid
Hassan
Hubballi-Dharwad
Kalaburagi
Kolar
Madikeri
Mandya
Mangaluru
Mysuru
Raichur
Shivamogga
Shravanabelagola
Shrirangapattana
Tumakuru
Vijayapura
Kerala
Alappuzha
Vatakara
Idukki
Kannur
Kochi
Kollam
Kottayam
Kozhikode
Mattancheri
Palakkad
Thalassery
Thiruvananthapuram
Thrissur
Ladakh (union territory)
Kargil
Leh
Madhya Pradesh
Balaghat
Barwani
Betul
Bharhut
Bhind
Bhojpur
Bhopal
Burhanpur
Chhatarpur
Chhindwara
Damoh
Datia
Dewas
Dhar
Dr. Ambedkar Nagar (Mhow)
Guna
Gwalior
Hoshangabad
Indore
Itarsi
Jabalpur
Jhabua
Khajuraho
Khandwa
Khargone
Maheshwar
Mandla
Mandsaur
Morena
Murwara
Narsimhapur
Narsinghgarh
Narwar
Neemuch
Nowgong
Orchha
Panna
Raisen
Rajgarh
Ratlam
Rewa
Sagar
Sarangpur
Satna
Sehore
Seoni
Shahdol
Shajapur
Sheopur
Shivpuri
Ujjain
Vidisha
Maharashtra
Ahmadnagar
Akola
Amravati
Aurangabad
Bhandara
Bhusawal
Bid
Buldhana
Chandrapur
Daulatabad
Dhule
Jalgaon
Kalyan
Karli
Kolhapur
Mahabaleshwar
Malegaon
Matheran
Mumbai
Nagpur
Nanded
Nashik
Osmanabad
Pandharpur
Parbhani
Pune
Ratnagiri
Sangli
Satara
Sevagram
Solapur
Thane
Ulhasnagar
Vasai-Virar
Wardha
Yavatmal
Manipur
Imphal
Meghalaya
Cherrapunji
Shillong
Mizoram
Aizawl
Lunglei
Nagaland
Kohima
Mon
Phek
Wokha
Zunheboto
Odisha
Balangir
Baleshwar
Baripada
Bhubaneshwar
Brahmapur
Cuttack
Dhenkanal
Kendujhar
Konark
Koraput
Paradip
Phulabani
Puri
Sambalpur
Udayagiri
Puducherry (union territory)
Karaikal
Mahe
Puducherry
Yanam
Punjab
Amritsar
Batala
Faridkot
Firozpur
Gurdaspur
Hoshiarpur
Jalandhar
Kapurthala
Ludhiana
Nabha
Patiala
Rupnagar
Sangrur
Rajasthan
Abu
Ajmer
Alwar
Amer
Barmer
Beawar
Bharatpur
Bhilwara
Bikaner
Bundi
Chittaurgarh
Churu
Dhaulpur
Dungarpur
Ganganagar
Hanumangarh
Jaipur
Jaisalmer
Jalor
Jhalawar
Jhunjhunu
Jodhpur
Kishangarh
Kota
Merta
Nagaur
Nathdwara
Pali
Phalodi
Pushkar
Sawai Madhopur
Shahpura
Sikar
Sirohi
Tonk
Udaipur
Sikkim
Gangtok
Gyalshing
Lachung
Mangan
Tamil Nadu
Arcot
Chengalpattu
Chennai
Chidambaram
Coimbatore
Cuddalore
Dharmapuri
Dindigul
Erode
Kanchipuram
Kanniyakumari
Kodaikanal
Kumbakonam
Madurai
Mamallapuram
Nagappattinam
Nagercoil
Palayamkottai
Pudukkottai
Rajapalayam
Ramanathapuram
Salem
Thanjavur
Tiruchchirappalli
Tirunelveli
Tiruppur
Thoothukudi
Udhagamandalam
Vellore
Telangana
Hyderabad
Karimnagar
Khammam
Mahbubnagar
Nizamabad
Sangareddi
Warangal
Tripura
Agartala
Uttar Pradesh
Agra
Aligarh
Amroha
Ayodhya
Azamgarh
Bahraich
Ballia
Banda
Bara Banki
Bareilly
Basti
Bijnor
Bithur
Budaun
Bulandshahr
Deoria
Etah
Etawah
Faizabad
Farrukhabad-cum-Fatehgarh
Fatehpur
Fatehpur Sikri
Ghaziabad
Ghazipur
Gonda
Gorakhpur
Hamirpur
Hardoi
Hathras
Jalaun
Jaunpur
Jhansi
Kannauj
Kanpur
Lakhimpur
Lalitpur
Lucknow
Mainpuri
Mathura
Meerut
Mirzapur-Vindhyachal
Moradabad
Muzaffarnagar
Partapgarh
Pilibhit
Prayagraj
Rae Bareli
Rampur
Saharanpur
Sambhal
Shahjahanpur
Sitapur
Sultanpur
Tehri
Varanasi
Uttarakhand
Almora
Dehra Dun
Haridwar
Mussoorie
Nainital
Pithoragarh
West Bengal
Alipore
Alipur Duar
Asansol
Baharampur
Bally
Balurghat
Bankura
Baranagar
Barasat
Barrackpore
Basirhat
Bhatpara
Bishnupur
Budge Budge
Burdwan
Chandernagore
Darjeeling
Diamond Harbour
Dum Dum
Durgapur
Halisahar
Haora
Hugli
Ingraj Bazar
Jalpaiguri
Kalimpong
Kamarhati
Kanchrapara
Kharagpur
Cooch Behar
Kolkata
Krishnanagar
Malda
Midnapore
Murshidabad
Nabadwip
Palashi
Panihati
Purulia
Raiganj
Santipur
Shantiniketan
Shrirampur
Siliguri
Siuri
Tamluk
Titagarh
"""

def parse_britannica_list():
    lines = [l.strip() for l in RAW_BRITANNICA_LIST.strip().split("\n") if l.strip()]
    state_city_map = {}
    current_state = None

    for line in lines:
        if "(union territory)" in line or "(national capital territory)" in line or line in [
            "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
            "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
            "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
            "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
            "Uttar Pradesh", "Uttarakhand", "West Bengal"
        ]:
            clean_state = line.replace("(union territory)", "").replace("(national capital territory)", "").strip()
            current_state = clean_state
            if current_state not in state_city_map:
                state_city_map[current_state] = []
        else:
            if current_state:
                state_city_map[current_state].append(line)
    return state_city_map

def clean_non_indian_cities():
    """Remove foreign non-Indian cities from database."""
    foreign_cities = ["London", "New York", "Tokyo", "Singapore", "Dubai", "Paris", "Sydney", "San Francisco", "Berlin", "Toronto"]
    with engine.begin() as conn:
        for c in foreign_cities:
            conn.execute(text("DELETE FROM cities WHERE LOWER(city_name) = LOWER(:name)"), {"name": c})
            conn.execute(text("DELETE FROM api_logs WHERE LOWER(city_name) = LOWER(:name)"), {"name": c})
    print("Cleaned non-Indian cities from database.")

def seed_all_britannica_cities():
    init_db()
    clean_non_indian_cities()
    state_city_map = parse_britannica_list()

    total_cities = sum(len(cities) for cities in state_city_map.values())
    print(f"Parsing {len(state_city_map)} Indian States & UTs with {total_cities} total cities/towns...")

    all_dict = {}
    geocoded_count = 0

    for state, cities in state_city_map.items():
        print(f"\nProcessing State: {state} ({len(cities)} locations)...")
        for city in cities:
            try:
                # Check if in DB first
                with engine.begin() as conn:
                    existing = conn.execute(
                        text("SELECT city_id, city_name, latitude, longitude, timezone FROM cities WHERE LOWER(city_name) = LOWER(:name)"),
                        {"name": city}
                    ).fetchone()

                if existing:
                    all_dict[city] = {
                        "lat": existing[2],
                        "lon": existing[3],
                        "timezone": existing[4],
                        "country": "India",
                        "admin1": state
                    }
                    # Ensure admin1 is correct
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE cities SET admin1 = :state, country = 'India' WHERE city_id = :id"),
                            {"state": state, "id": existing[0]}
                        )
                else:
                    # Geocode
                    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
                    params = {"name": f"{city}", "count": 1, "language": "en", "format": "json"}
                    res = requests.get(geo_url, params=params, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        if "results" in data and len(data["results"]) > 0:
                            r = data["results"][0]
                            lat = r["latitude"]
                            lon = r["longitude"]
                            tz = r.get("timezone", "Asia/Kolkata")
                            with engine.begin() as conn:
                                conn.execute(
                                    text("INSERT OR REPLACE INTO cities (city_name, latitude, longitude, timezone, country, admin1) VALUES (:name, :lat, :lon, :tz, 'India', :state)"),
                                    {"name": city, "lat": lat, "lon": lon, "tz": tz, "state": state}
                                )
                            all_dict[city] = {"lat": lat, "lon": lon, "timezone": tz, "country": "India", "admin1": state}
                            geocoded_count += 1
                    time.sleep(0.08) # Respect API politeness
            except Exception as e:
                print(f"  Warning on {city}: {e}")

    print(f"\n✅ Finished processing all {len(all_dict)} Indian cities!")
    return all_dict

if __name__ == "__main__":
    seed_all_britannica_cities()
