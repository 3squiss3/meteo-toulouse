import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time

class ToulouseMeteoCollector:
    def __init__(self):
        # Utilisation du dataset Station météo n°1 (Météopole) qui est plus fiable
        self.base_url = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/01-station-meteo-toulouse-meteopole/records"
        
    def debug_api_response(self, limit=1):
        """Debug pour voir la structure réelle de l'API"""
        try:
            response = requests.get(self.base_url, params={'limit': limit})
            response.raise_for_status()
            data = response.json()
            
            print("=== STRUCTURE DE L'API ===")
            print(f"Status: {response.status_code}")
            print(f"Nombre de résultats: {data.get('total_count', 0)}")
            
            if data.get('results'):
                first_record = data['results'][0]
                print("\n=== STRUCTURE D'UN ENREGISTREMENT ===")
                print(json.dumps(first_record, indent=2, ensure_ascii=False))
                
                if 'record' in first_record and 'fields' in first_record['record']:
                    fields = first_record['record']['fields']
                    print(f"\n=== CHAMPS DISPONIBLES ===")
                    for key, value in fields.items():
                        print(f"'{key}': {value} ({type(value).__name__})")
            
            return data
            
        except Exception as e:
            print(f"Erreur debug: {e}")
            return {}
        
    def get_latest_data(self, limit=10):
        """Récupère les dernières données météo"""
        params = {
            'limit': limit,
            'order_by': '-heure_utc'  # Tri par heure décroissante
        }
        
        try:
            print(f"Requête: {self.base_url}")
            print(f"Paramètres: {params}")
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            print(f"Réponse reçue: {data.get('total_count', 0)} enregistrements")
            
            if not data.get('results'):
                print("Aucun résultat dans la réponse")
                return pd.DataFrame()
            
            records = []
            for i, record in enumerate(data.get('results', [])):
                try:
                    # Structure CORRECTE : les données sont directement dans 'record'
                    # Pas besoin de record.fields !
                    
                    # Mapping avec les VRAIS noms de champs
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'temperature': record.get('temperature_en_degre_c'),
                        'humidite': record.get('humidite'),
                        'pression': record.get('pression'),
                        'vitesse_vent': record.get('force_moyenne_du_vecteur_vent'),
                        'direction_vent': record.get('direction_du_vecteur_vent_moyen'),
                        'precipitation': record.get('pluie'),
                        'rafale_max': record.get('force_rafale_max'),
                        'pluie_intensite_max': record.get('pluie_intensite_max'),
                        'station_type': record.get('type_de_station'),
                        'heure_paris': record.get('heure_de_paris')
                    }
                    
                    records.append(record_data)
                    
                    # Debug du premier enregistrement
                    if i == 0:
                        print(f"Premier enregistrement traité: {record_data}")
                
                except Exception as e:
                    print(f"Erreur traitement enregistrement {i}: {e}")
                    continue
            
            df = pd.DataFrame(records)
            print(f"DataFrame créé avec {len(df)} lignes")
            return df
            
        except Exception as e:
            print(f"Erreur lors de la collecte: {e}")
            return pd.DataFrame()
    
    
    def collect_historical_data(self, days_back=7):
        """Collecte des données historiques"""
        # ATTENTION: Les données semblent être de 2022, pas 2025 !
        # Utilisons une date de 2022 pour tester
        base_date = datetime(2022, 12, 16)  # Date vue dans le debug
        end_date = base_date
        start_date = end_date - timedelta(days=days_back)
        
        # Format ISO pour l'API
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S')
        
        params = {
            'where': f'heure_utc >= "{start_str}" AND heure_utc <= "{end_str}"',
            'limit': 1000,  # Limite réduite
            'order_by': '-heure_utc'
        }
        
        try:
            print(f"Collecte historique du {start_str} au {end_str}")
            print(f"Paramètres: {params}")
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            print(f"Données historiques reçues: {data.get('total_count', 0)} enregistrements")
            
            records = []
            for record in data.get('results', []):
                try:
                    # Structure CORRECTE : données directement dans record
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'temperature': record.get('temperature_en_degre_c'),
                        'humidite': record.get('humidite'),
                        'pression': record.get('pression'),
                        'vitesse_vent': record.get('force_moyenne_du_vecteur_vent'),
                        'direction_vent': record.get('direction_du_vecteur_vent_moyen'),
                        'precipitation': record.get('pluie'),
                        'rafale_max': record.get('force_rafale_max'),
                        'pluie_intensite_max': record.get('pluie_intensite_max'),
                        'heure_paris': record.get('heure_de_paris')
                    }
                    
                    records.append(record_data)
                    
                except Exception as e:
                    print(f"Erreur traitement: {e}")
                    continue
            
            df = pd.DataFrame(records)
            print(f"DataFrame historique créé avec {len(df)} lignes")
            return df
            
        except Exception as e:
            print(f"Erreur lors de la collecte historique: {e}")
            # Tentative sans filtre de date - STRUCTURE CORRIGEE
            try:
                print("Tentative de collecte sans filtre...")
                simple_params = {'limit': 100, 'order_by': '-heure_utc'}
                response = requests.get(self.base_url, params=simple_params)
                response.raise_for_status()
                data = response.json()
                
                print(f"Collecte simple: {data.get('total_count', 0)} disponibles")
                
                records = []
                for record in data.get('results', []):
                    # Structure CORRECTE
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'temperature': record.get('temperature_en_degre_c'),
                        'humidite': record.get('humidite'),
                        'pression': record.get('pression'),
                        'vitesse_vent': record.get('force_moyenne_du_vecteur_vent'),
                        'direction_vent': record.get('direction_du_vecteur_vent_moyen'),
                        'precipitation': record.get('pluie'),
                        'rafale_max': record.get('force_rafale_max')
                    }
                    records.append(record_data)
                
                df = pd.DataFrame(records)
                print(f"Collecte simple réussie: {len(df)} enregistrements")
                return df
                
            except Exception as e2:
                print(f"Erreur collecte simple: {e2}")
                return pd.DataFrame()

# Collecteur d'autres sources météo
class MultiMeteoCollector:
    def __init__(self, openweather_api_key=None):
        self.openweather_key = openweather_api_key
        
    def get_meteo_france_alerts(self):
        """Récupère les vigilances Météo France"""
        # Utilisation d'une URL alternative qui fonctionne
        urls_to_try = [
            "https://data.gouv.fr/api/1/datasets/donnees-temps-reel-de-mesure-des-concentrations-de-polluants-atmospheriques-reglementes-1/",
            "https://api.meteo-concept.com/api/vigilance/departementslist",  # Alternative
        ]
        
        for url in urls_to_try:
            try:
                print(f"Tentative avec: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                print(f"Succès avec {url}")
                return response.json()
            except Exception as e:
                print(f"Erreur avec {url}: {e}")
                continue
        
        # Si toutes les URLs échouent, retourner des données simulées
        print("Aucune API d'alertes accessible, génération de données d'exemple...")
        return {
            "results": [{
                "type_alerte": "Information",
                "niveau": "Vert",
                "zone": "Haute-Garonne",
                "message": "Pas d'alerte en cours (données simulées)"
            }]
        }
    
    def get_openweather_data(self, city="Toulouse"):
        """Données OpenWeatherMap"""
        if not self.openweather_key:
            print("Pas de clé OpenWeatherMap fournie, génération de données simulées...")
            import random
            return {
                "name": city,
                "main": {
                    "temp": round(15 + random.random() * 20, 1),
                    "humidity": round(40 + random.random() * 40),
                    "pressure": round(1000 + random.random() * 50)
                },
                "wind": {
                    "speed": round(random.random() * 20, 1),
                    "deg": round(random.random() * 360)
                },
                "weather": [{"description": "Données simulées"}]
            }
            
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': self.openweather_key,
            'units': 'metric',
            'lang': 'fr'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Erreur OpenWeather: {e}")
            return {}

# Exemple d'utilisation avec debugging amélioré
if __name__ == "__main__":
    import requests  # Import nécessaire pour la section de test
    import pandas as pd  # Import pandas
    
    print("=== DEBUT DU TEST DE COLLECTE ===\n")
    
    # Collecte données Toulouse
    toulouse_collector = ToulouseMeteoCollector()
    
    print("1. DEBUGGING DE L'API...")
    debug_info = toulouse_collector.debug_api_response()
    
    print("\n2. COLLECTE DES DERNIERES DONNEES...")
    latest_data = toulouse_collector.get_latest_data(limit=5)
    print("Aperçu des données récentes:")
    print(latest_data.head())
    
    if not latest_data.empty:
        print(f"\nStatistiques:")
        print(f"- Nombre de lignes: {len(latest_data)}")
        print(f"- Colonnes: {list(latest_data.columns)}")
        print(f"- Valeurs non-nulles par colonne:")
        for col in latest_data.columns:
            non_null = latest_data[col].notna().sum()
            print(f"  {col}: {non_null}/{len(latest_data)}")
    
    print("\n3. COLLECTE DONNEES HISTORIQUES...")
    
    # D'abord, essayer la collecte simple pour voir les données disponibles
    print("Test collecte simple pour comprendre les dates disponibles...")
    simple_test = toulouse_collector.collect_historical_data(days_back=3)
    
    if simple_test.empty:
        print("Pas de données avec filtre de date, essai collecte sans filtre...")
        
        # Collecte sans filtre pour voir ce qui est disponible
        try:
            response = requests.get(toulouse_collector.base_url, params={'limit': 10, 'order_by': '-heure_utc'})
            data = response.json()
            
            if data.get('results'):
                records = []
                for record in data.get('results', []):
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'temperature': record.get('temperature_en_degre_c'),
                        'humidite': record.get('humidite'),
                        'pression': record.get('pression'),
                        'vitesse_vent': record.get('force_moyenne_du_vecteur_vent'),
                        'direction_vent': record.get('direction_du_vecteur_vent_moyen'),
                        'precipitation': record.get('pluie')
                    }
                    records.append(record_data)
                
                historical_data = pd.DataFrame(records)
                print(f"✅ Collecte sans filtre réussie: {len(historical_data)} enregistrements")
                
                # Afficher un aperçu des données
                if not historical_data.empty:
                    print("Aperçu des données collectées:")
                    print(historical_data[['timestamp', 'temperature', 'humidite']].head())
                    
                    # Infos sur les dates
                    dates = pd.to_datetime(historical_data['timestamp'])
                    print(f"Période des données: {dates.min()} à {dates.max()}")
                    
            else:
                print("❌ Aucune donnée disponible")
                historical_data = pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Erreur collecte simple: {e}")
            historical_data = pd.DataFrame()
    else:
        historical_data = simple_test
        
    print(f"Données historiques finales: {len(historical_data)} enregistrements")
    
    print("\n4. COLLECTE DONNEES COMPLEMENTAIRES...")
    multi_collector = MultiMeteoCollector()
    
    print("Test alertes météo...")
    alerts = multi_collector.get_meteo_france_alerts()
    print(f"Alertes récupérées: {len(alerts.get('results', []))}")
    
    print("\nTest OpenWeatherMap...")
    openweather_data = multi_collector.get_openweather_data()
    if openweather_data:
        print(f"Données OpenWeather pour {openweather_data.get('name', 'Inconnu')}: {openweather_data.get('main', {}).get('temp', 'N/A')}°C")
    
    print("\n=== FIN DU TEST ===")
    
    # Sauvegarde des données si disponibles
    if not latest_data.empty:
        try:
            latest_data.to_csv('toulouse_meteo_latest.csv', index=False)
            print("✅ Données sauvegardées dans 'toulouse_meteo_latest.csv'")
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
    
    if not historical_data.empty:
        try:
            historical_data.to_csv('toulouse_meteo_historical.csv', index=False)
            print("✅ Données historiques sauvegardées dans 'toulouse_meteo_historical.csv'")
        except Exception as e:
            print(f"❌ Erreur sauvegarde historique: {e}")