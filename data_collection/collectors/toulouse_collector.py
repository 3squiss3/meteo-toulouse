import pandas as pd
import json
from datetime import datetime, timedelta
import time
import logging
from kafka.producer import KafkaProducer
from kafka.errors import KafkaError
import sys
from pathlib import Path
import requests 

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

try:
    from config import APIConfig, KafkaConfig
except ImportError:
    # Configuration par défaut si config.py n'est pas disponible
    class KafkaConfig:
        BOOTSTRAP_SERVERS = ['localhost:9092']
        TOPIC_METEO_TEMPS_REEL = 'topic_meteo_temps_reel'
        TOPIC_ALERTES_METEO = 'topic_alertes_meteo'

logger = logging.getLogger(__name__)

class ToulouseMeteoCollector:
    def __init__(self):
        # Station météo n°42 - Parc Compans Caffarelli
        self.base_url = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/42-station-meteo-toulouse-parc-compans-cafarelli/records"
        self.station_name = "Station Météo Toulouse - Parc Compans Caffarelli"
        self.station_id = "toulouse_compans_cafarelli"
        
        # Initialiser le producteur Kafka
        self.kafka_producer = None
        self._init_kafka_producer()
        
    def _init_kafka_producer(self):
        """Initialise le producteur Kafka"""
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=KafkaConfig.BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8'),
                retries=3,
                acks='all'
            )
            logger.info(f"✅ Kafka producteur connecté: {KafkaConfig.BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.warning("Kafka non disponible: %s", e)
            self.kafka_producer = None
        
    def debug_api_response(self, limit=1):
        """Debug pour voir la structure réelle de l'API"""
        try:
            response = requests.get(self.base_url, params={'limit': limit})
            response.raise_for_status()
            data = response.json()
            
            print(f"=== STRUCTURE DE L'API - {self.station_name} ===")
            print(f"Status: {response.status_code}")
            print(f"Nombre de résultats: {data.get('total_count', 0)}")
            
            if data.get('results'):
                first_record = data['results'][0]
                print("\n=== STRUCTURE D'UN ENREGISTREMENT ===")
                print(json.dumps(first_record, indent=2, ensure_ascii=False))
                
                print(f"\n=== CHAMPS DISPONIBLES ===")
                for key, value in first_record.items():
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
                    # Format compatible avec le processeur Spark
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'station': self.station_id,
                        'temperature': float(record.get('temperature_en_degre_c')) if record.get('temperature_en_degre_c') is not None else None,
                        'humidite': float(record.get('humidite')) if record.get('humidite') is not None else None,
                        'pression': float(record.get('pression')) if record.get('pression') is not None else None,
                        'vitesse_vent': float(record.get('force_moyenne_du_vecteur_vent')) if record.get('force_moyenne_du_vecteur_vent') is not None else None,
                        'direction_vent': float(record.get('direction_du_vecteur_vent_moyen')) if record.get('direction_du_vecteur_vent_moyen') is not None else None,
                        'precipitation': float(record.get('pluie')) if record.get('pluie') is not None else None,
                        # Champs supplémentaires pour l'analyse
                        'rafale_max': float(record.get('force_rafale_max')) if record.get('force_rafale_max') is not None else None,
                        'pluie_intensite_max': float(record.get('pluie_intensite_max')) if record.get('pluie_intensite_max') is not None else None,
                        'station_type': record.get('type_de_station'),
                        'heure_paris': record.get('heure_de_paris'),
                        'station_name': self.station_name
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
    
    def send_to_kafka(self, data):
        """Envoie les données vers Kafka"""
        if not self.kafka_producer:
            logger.warning("Kafka producteur non disponible")
            return False
        
        sent_count = 0
        error_count = 0
        
        for _, row in data.iterrows():
            try:
                # Message compatible avec le schéma Spark
                message = {
                    'station': row['station'],
                    'timestamp': str(row['timestamp']),
                    'temperature': row['temperature'],
                    'humidite': row['humidite'],
                    'pression': row['pression'],
                    'vitesse_vent': row['vitesse_vent'],
                    'direction_vent': row['direction_vent'],
                    'precipitation': row['precipitation']
                }
                
                # Filtrer les valeurs None
                message = {k: v for k, v in message.items() if v is not None}
                
                # Envoyer vers Kafka
                future = self.kafka_producer.send(
                    KafkaConfig.TOPIC_METEO_TEMPS_REEL,
                    key=row['station'],
                    value=message
                )
                
                # Callback pour gérer les erreurs
                future.add_callback(lambda metadata: None)
                future.add_errback(lambda e: logger.error(f"Erreur Kafka: {e}"))
                
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Erreur envoi message: {e}")
                error_count += 1
        
        # Attendre que tous les messages soient envoyés
        self.kafka_producer.flush()
        
        logger.info(f"Kafka: {sent_count} messages envoyés, {error_count} erreurs")
        return sent_count > 0
    
    def collect_historical_data(self, days_back=7):
        """Collecte des données historiques"""
        # D'abord, on fait une requête pour voir quelle est la période disponible
        test_response = requests.get(self.base_url, params={'limit': 1, 'order_by': '-heure_utc'})
        if test_response.status_code == 200:
            test_data = test_response.json()
            if test_data.get('results'):
                latest_date = test_data['results'][0].get('heure_utc')
                print(f"Date la plus récente disponible: {latest_date}")
        
        # Utilisation de dates relatives
        params = {
            'limit': 1000,
            'order_by': '-heure_utc'
        }
        
        try:
            print(f"Collecte historique des {days_back} derniers jours")
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            print(f"Données historiques reçues: {data.get('total_count', 0)} enregistrements")
            
            records = []
            for record in data.get('results', []):
                try:
                    # Format compatible Spark
                    record_data = {
                        'timestamp': record.get('heure_utc'),
                        'station': self.station_id,
                        'temperature': float(record.get('temperature_en_degre_c')) if record.get('temperature_en_degre_c') is not None else None,
                        'humidite': float(record.get('humidite')) if record.get('humidite') is not None else None,
                        'pression': float(record.get('pression')) if record.get('pression') is not None else None,
                        'vitesse_vent': float(record.get('force_moyenne_du_vecteur_vent')) if record.get('force_moyenne_du_vecteur_vent') is not None else None,
                        'direction_vent': float(record.get('direction_du_vecteur_vent_moyen')) if record.get('direction_du_vecteur_vent_moyen') is not None else None,
                        'precipitation': float(record.get('pluie')) if record.get('pluie') is not None else None,
                        'station_name': self.station_name
                    }
                    
                    records.append(record_data)
                    
                except Exception as e:
                    print(f"Erreur traitement: {e}")
                    continue
            
            df = pd.DataFrame(records)
            
            # Filtrer par date si nécessaire
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff_date = datetime.now() - timedelta(days=days_back)
                df = df[df['timestamp'] >= cutoff_date]
            
            print(f"DataFrame historique créé avec {len(df)} lignes après filtrage")
            return df
            
        except Exception as e:
            print(f"Erreur lors de la collecte historique: {e}")
            return pd.DataFrame()

    def collect_and_send_to_kafka(self, limit=10):
        """Collecte et envoie directement vers Kafka"""
        logger.info("Collecte et envoi vers Kafka...")
        
        # Collecter les données
        data = self.get_latest_data(limit=limit)
        
        if data.empty:
            logger.warning("Aucune donnée collectée")
            return False
        
        # Envoyer vers Kafka
        success = self.send_to_kafka(data)
        
        if success:
            logger.info(f"✅ {len(data)} enregistrements envoyés vers Kafka")
        else:
            logger.error("❌ Échec envoi vers Kafka")
        
        return success

    def collect_for_project(self, output_format='spark'):
        """
        Collecte spécialisée pour le projet de plateforme d'analyse
        Retourne les données dans un format adapté pour Kafka/Spark
        """
        latest_data = self.get_latest_data(limit=100)
        
        if latest_data.empty:
            return []
        
        if output_format == 'spark':
            # Format direct pour Spark (DataFrame compatible)
            return latest_data
        
        elif output_format == 'kafka':
            # Format pour Kafka topics
            kafka_messages = []
            
            for _, row in latest_data.iterrows():
                # Message pour le topic des données météo
                message = {
                    'station': row['station'],
                    'timestamp': str(row['timestamp']),
                    'temperature': row['temperature'],
                    'humidite': row['humidite'],
                    'pression': row['pression'],
                    'vitesse_vent': row['vitesse_vent'],
                    'direction_vent': row['direction_vent'],
                    'precipitation': row['precipitation']
                }
                
                kafka_messages.append(message)
            
            return kafka_messages
    
    def close(self):
        """Ferme les connexions"""
        if self.kafka_producer:
            self.kafka_producer.close()
            logger.info("Kafka producteur fermé")

class CombinedMeteoCollector:
    """Collecteur combiné pour plusieurs stations météo de Toulouse"""
    
    def __init__(self):
        self.collectors = {
            'meteopole': {
                'url': 'https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/01-station-meteo-toulouse-meteopole/records',
                'name': 'Météopole',
                'station_id': 'toulouse_meteopole'
            },
            'compans': {
                'url': 'https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/42-station-meteo-toulouse-parc-compans-cafarelli/records',
                'name': 'Parc Compans Caffarelli',
                'station_id': 'toulouse_compans_cafarelli'
            }
        }
        
        # Kafka producer pour l'envoi combiné
        self.kafka_producer = None
        self._init_kafka_producer()
    
    def _init_kafka_producer(self):
        """Initialise le producteur Kafka"""
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=KafkaConfig.BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8')
            )
        except Exception as e:
            logger.warning(f"Kafka non disponible: {e}")
    
    def collect_all_stations(self, limit=10, send_to_kafka=False):
        """Collecte les données de toutes les stations"""
        all_data = []
        
        for station_id, station_info in self.collectors.items():
            print(f"\nCollecte station: {station_info['name']}")
            
            try:
                params = {'limit': limit, 'order_by': '-heure_utc'}
                response = requests.get(station_info['url'], params=params)
                response.raise_for_status()
                data = response.json()
                
                for record in data.get('results', []):
                    # Format compatible Spark
                    formatted_record = {
                        'timestamp': record.get('heure_utc'),
                        'station': station_info['station_id'],
                        'temperature': float(record.get('temperature_en_degre_c')) if record.get('temperature_en_degre_c') is not None else None,
                        'humidite': float(record.get('humidite')) if record.get('humidite') is not None else None,
                        'pression': float(record.get('pression')) if record.get('pression') is not None else None,
                        'vitesse_vent': float(record.get('force_moyenne_du_vecteur_vent')) if record.get('force_moyenne_du_vecteur_vent') is not None else None,
                        'direction_vent': float(record.get('direction_du_vecteur_vent_moyen')) if record.get('direction_du_vecteur_vent_moyen') is not None else None,
                        'precipitation': float(record.get('pluie')) if record.get('pluie') is not None else None,
                        'station_name': station_info['name']
                    }
                    
                    all_data.append(formatted_record)
                    
                    # Envoyer vers Kafka si demandé
                    if send_to_kafka and self.kafka_producer:
                        try:
                            kafka_message = {k: v for k, v in formatted_record.items() if v is not None and k != 'station_name'}
                            self.kafka_producer.send(
                                KafkaConfig.TOPIC_METEO_TEMPS_REEL,
                                key=station_info['station_id'],
                                value=kafka_message
                            )
                        except Exception as e:
                            logger.error(f"Erreur Kafka pour {station_id}: {e}")
                    
                print(f"✅ {len(data.get('results', []))} enregistrements collectés")
                
            except Exception as e:
                print(f"❌ Erreur pour {station_info['name']}: {e}")
        
        if send_to_kafka and self.kafka_producer:
            self.kafka_producer.flush()
            logger.info(f"Données de toutes les stations envoyées vers Kafka")
        
        # Conversion en DataFrame
        if all_data:
            df = pd.DataFrame(all_data)
            print(f"\nTotal: {len(df)} enregistrements de {df['station'].nunique()} stations")
            return df
        
        return pd.DataFrame()

# Exemple d'utilisation adapté pour l'intégration Kafka/Spark
if __name__ == "__main__":
    print("=== COLLECTE MÉTÉO INTÉGRÉE KAFKA/SPARK ===\n")
    
    # 1. Test du collecteur principal
    collector = ToulouseMeteoCollector()
    
    print("1. COLLECTE ET ENVOI VERS KAFKA...")
    collector.collect_and_send_to_kafka(limit=5)
    
    print("\n2. COLLECTE POUR TRAITEMENT SPARK...")
    spark_data = collector.collect_for_project(output_format='spark')
    
    if not spark_data.empty:
        print(f"✅ {len(spark_data)} enregistrements prêts pour Spark")
        
        # Sauvegarde en format CSV pour Spark batch
        spark_data.to_csv('data/raw/meteo_spark_input.csv', index=False)
        print("✅ Données sauvegardées pour traitement Spark batch")
    
    print("\n3. COLLECTE MULTI-STATIONS AVEC KAFKA...")
    combined_collector = CombinedMeteoCollector()
    all_data = combined_collector.collect_all_stations(limit=3, send_to_kafka=True)
    
    if not all_data.empty:
        print(f"\n✅ {len(all_data)} enregistrements de {all_data['station'].nunique()} stations")
        
        # Sauvegarde pour analyse
        all_data.to_csv('data/raw/meteo_all_stations.csv', index=False)
        print("✅ Données multi-stations sauvegardées")
    
    # Fermer les connexions
    collector.close()
    
    print("\n=== COLLECTE TERMINÉE ===")
    print("Les données sont maintenant disponibles pour :")
    print("• Traitement Spark streaming (via Kafka)")
    print("• Traitement Spark batch (via CSV)")
    print("• Interface Streamlit (via base de données)")
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