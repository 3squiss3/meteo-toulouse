import logging
import logging.config
import click
import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.absolute()))

from config import config, LoggingConfig, KafkaConfig

# Configuration des logs
logging.config.dictConfig(LoggingConfig.get_logging_config())
logger = logging.getLogger(__name__)

@click.group()
@click.version_option(version=config.APP_VERSION)
def cli():
    """
    🌤️ Plateforme d'Analyse Météorologique Toulouse
    
    Système de collecte, traitement et analyse des données météo en temps réel
    """
    logger.info(f"Démarrage de {config.APP_NAME} v{config.APP_VERSION}")

@cli.group()
def collect():
    """Commandes de collecte de données"""
    pass

@collect.command()
@click.option('--station', default='compans', 
              type=click.Choice(['compans', 'meteopole', 'all']),
              help='Station météo à collecter')
@click.option('--limit', default=10, help='Nombre max d\'enregistrements')
@click.option('--save', is_flag=True, help='Sauvegarder en CSV')
@click.option('--kafka', is_flag=True, help='Envoyer vers Kafka')
def meteo(station, limit, save, kafka):
    """Collecte les données météo de Toulouse (nouveau système)"""
    logger.info(f"Collecte météo - Station: {station}, Limit: {limit}")
    
    try:
        if station == 'all':
            # Collecte multi-stations
            from data_collection.collectors.toulouse_collector import CombinedMeteoCollector
            
            collector = CombinedMeteoCollector()
            data = collector.collect_all_stations(limit=limit, send_to_kafka=kafka)
            
            if not data.empty:
                click.echo(f"✅ {len(data)} enregistrements de {data['station'].nunique()} stations")
                click.echo(data.head().to_string())
                
                if save:
                    filename = f"meteo_all_stations_{limit}.csv"
                    data.to_csv(config.DATA_DIR / "raw" / filename, index=False)
                    click.echo(f"💾 Données sauvegardées dans {filename}")
            else:
                click.echo("❌ Aucune donnée collectée")
        
        else:
            # Collecte station simple
            from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector
            
            collector = ToulouseMeteoCollector()
            
            if kafka:
                # Collecte et envoi direct vers Kafka
                success = collector.collect_and_send_to_kafka(limit=limit)
                if success:
                    click.echo(f"✅ Données envoyées vers Kafka")
                else:
                    click.echo("❌ Échec envoi Kafka")
            else:
                # Collecte normale
                data = collector.get_latest_data(limit=limit)
                
                if not data.empty:
                    click.echo(f"✅ {len(data)} enregistrements collectés")
                    click.echo(data[['timestamp', 'station_name', 'temperature', 'humidite']].head().to_string())
                    
                    if save:
                        filename = f"meteo_{station}_{limit}.csv"
                        data.to_csv(config.DATA_DIR / "raw" / filename, index=False)
                        click.echo(f"💾 Données sauvegardées dans {filename}")
                else:
                    click.echo("❌ Aucune donnée collectée")
            
            # Fermer les connexions
            collector.close()
            
    except ImportError as e:
        click.echo(f"❌ Erreur d'import: {e}")
        click.echo("Vérifiez que les collecteurs sont correctement installés")
    except Exception as e:
        logger.error(f"Erreur lors de la collecte: {e}")
        click.echo(f"❌ Erreur: {e}")

@collect.command()
def all():
    """Collecte toutes les données (météo + alertes + événements)"""
    logger.info("Collecte complète de toutes les données")
    
    try:
        from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector, CombinedMeteoCollector
        
        # Météo multi-stations
        click.echo("📊 Collecte des données météo multi-stations...")
        combined_collector = CombinedMeteoCollector()
        meteo_data = combined_collector.collect_all_stations(limit=20, send_to_kafka=True)
        
        # Météo principale (Compans)
        click.echo("🌤️ Collecte station principale (Compans)...")
        main_collector = ToulouseMeteoCollector()
        main_data = main_collector.get_latest_data(limit=10)
        
        # Envoyer vers Kafka
        if not main_data.empty:
            main_collector.send_to_kafka(main_data)
        
        # Fermer connexions
        main_collector.close()
        
        # Résumé
        click.echo(f"\n✅ Collecte terminée:")
        if not meteo_data.empty:
            click.echo(f"  • Données multi-stations: {len(meteo_data)} enregistrements")
            click.echo(f"  • Stations actives: {meteo_data['station'].nunique()}")
        if not main_data.empty:
            click.echo(f"  • Station principale: {len(main_data)} enregistrements")
        click.echo(f"  • Données envoyées vers Kafka: ✅")
        
    except Exception as e:
        logger.error(f"Erreur lors de la collecte complète: {e}")
        click.echo(f"❌ Erreur: {e}")

@collect.command()
@click.option('--mode', default='batch', type=click.Choice(['batch', 'streaming']), 
              help='Mode de collecte')
@click.option('--interval', default=300, help='Intervalle en secondes pour le streaming')
def continuous(mode, interval):
    """Collecte continue pour alimenter Kafka en temps réel"""
    logger.info(f"Collecte continue en mode {mode}")
    
    try:
        from data_collection.collectors.toulouse_collector import CombinedMeteoCollector
        import time
        
        collector = CombinedMeteoCollector()
        
        if mode == 'streaming':
            click.echo(f"🔄 Collecte streaming toutes les {interval} secondes...")
            click.echo("⏹️  Ctrl+C pour arrêter")
            
            try:
                while True:
                    click.echo(f"\n📡 Collecte à {datetime.now().strftime('%H:%M:%S')}")
                    
                    # Collecter et envoyer vers Kafka
                    data = collector.collect_all_stations(limit=5, send_to_kafka=True)
                    
                    if not data.empty:
                        click.echo(f"✅ {len(data)} enregistrements envoyés vers Kafka")
                    else:
                        click.echo("⚠️  Aucune donnée collectée")
                    
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                click.echo("\n⏹️  Collecte streaming arrêtée")
        
        else:
            # Mode batch
            click.echo("📦 Collecte batch...")
            data = collector.collect_all_stations(limit=50, send_to_kafka=True)
            
            if not data.empty:
                click.echo(f"✅ {len(data)} enregistrements traités")
                
                # Sauvegarder pour traitement Spark
                filename = f"meteo_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                data.to_csv(config.DATA_DIR / "raw" / filename, index=False)
                click.echo(f"💾 Sauvegardé: {filename}")
            
    except Exception as e:
        logger.error(f"Erreur collecte continue: {e}")
        click.echo(f"❌ Erreur: {e}")

@cli.group()
def db():
    """Commandes de gestion de base de données"""
    pass

@db.command()
def init():
    """Initialise les bases de données"""
    logger.info("Initialisation des bases de données")
    
    try:
        from database.sql.init_postgresql import init_postgresql_schema
        from database.mongodb.init_mongodb import init_mongodb_collections
        
        click.echo("🐘 Initialisation PostgreSQL...")
        init_postgresql_schema()
        
        click.echo("🍃 Initialisation MongoDB...")
        init_mongodb_collections()
        
        click.echo("✅ Bases de données initialisées")
        
    except ImportError:
        click.echo("❌ Modules de base de données non trouvés")
    except Exception as e:
        logger.error(f"Erreur initialisation DB: {e}")
        click.echo(f"❌ Erreur: {e}")

@db.command()
def status():
    """Vérifie le statut des bases de données"""
    click.echo("🔍 Vérification du statut des bases de données...")
    
    # PostgreSQL
    try:
        import psycopg2
        from config import DatabaseConfig
        conn = psycopg2.connect(DatabaseConfig.POSTGRES_URL)
        conn.close()
        click.echo("🐘 PostgreSQL: ✅ Connecté")
    except Exception as e:
        click.echo(f"🐘 PostgreSQL: ❌ Erreur - {e}")
    
    # MongoDB
    try:
        from pymongo import MongoClient
        from config import DatabaseConfig
        client = MongoClient(DatabaseConfig.MONGODB_URL)
        client.admin.command('ping')
        click.echo("🍃 MongoDB: ✅ Connecté")
        client.close()
    except Exception as e:
        click.echo(f"🍃 MongoDB: ❌ Erreur - {e}")
    
    # SQLite
    try:
        import sqlite3
        from config import DatabaseConfig
        conn = sqlite3.connect(DatabaseConfig.SQLITE_PATH)
        conn.close()
        click.echo("📁 SQLite: ✅ Accessible")
    except Exception as e:
        click.echo(f"📁 SQLite: ❌ Erreur - {e}")

@cli.group()
def process():
    """Commandes de traitement des données"""
    pass

@process.command()
@click.option('--mode', default='local', type=click.Choice(['local', 'cluster']), 
              help='Mode d\'exécution Spark')
@click.option('--input', help='Chemin du fichier d\'entrée pour le mode batch')
@click.option('--output', help='Chemin de sortie pour le mode batch')
@click.option('--streaming', is_flag=True, help='Mode streaming au lieu de batch')
def spark(mode, input, output, streaming):
    """Lance le traitement Spark"""
    logger.info(f"Démarrage du traitement Spark en mode {mode}")
    
    try:
        from data_processing.spark_jobs.meteo_processor import MeteoSparkProcessor, run_batch_processing, run_streaming_processing
        
        if streaming:
            click.echo("🌊 Lancement du traitement Spark Streaming...")
            click.echo("📡 Lecture depuis Kafka...")
            click.echo("⏹️  Ctrl+C pour arrêter")
            
            try:
                run_streaming_processing()
            except KeyboardInterrupt:
                click.echo("\n⏹️ Traitement streaming arrêté")
        
        else:
            # Mode batch
            if not input:
                # Utiliser le dernier fichier généré
                import glob
                files = glob.glob(str(config.DATA_DIR / "raw" / "meteo_*.csv"))
                if files:
                    input = max(files, key=lambda x: os.path.getctime(x))  # Dernier fichier
                    click.echo(f"📁 Fichier d'entrée automatique: {input}")
                else:
                    click.echo("❌ Aucun fichier d'entrée trouvé")
                    click.echo("💡 Lancez d'abord: python main.py collect meteo --save")
                    return
            
            if not output:
                output = str(config.DATA_DIR / "processed" / f"meteo_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            click.echo(f"⚡ Traitement Spark batch:")
            click.echo(f"  📥 Entrée: {input}")
            click.echo(f"  📤 Sortie: {output}")
            
            result = run_batch_processing(input, output)
            
            if result is not None and not result.count() == 0:
                click.echo("✅ Traitement Spark terminé avec succès")
                click.echo(f"📊 {result.count()} enregistrements traités")
                
                # Afficher quelques statistiques
                click.echo("\n📈 Aperçu des métriques calculées:")
                result.select("station", "temperature", "temp_moy_7j", "indice_confort").show(5, truncate=False)
            else:
                click.echo("❌ Échec du traitement Spark")
        
    except ImportError as e:
        click.echo(f"❌ Erreur d'import Spark: {e}")
        click.echo("💡 Vérifiez l'installation de PySpark")
    except Exception as e:
        logger.error(f"Erreur Spark: {e}")
        click.echo(f"❌ Erreur: {e}")

@process.command()
@click.option('--topics', default='meteo', 
              type=click.Choice(['meteo', 'alertes', 'all']),
              help='Topics Kafka à traiter')
def kafka(topics):
    """Lance le streaming Kafka"""
    logger.info(f"Démarrage du streaming Kafka pour {topics}")
    
    try:
        from kafka import KafkaConsumer
        import json
        
        # Configuration des topics selon le choix
        if topics == 'meteo':
            topic_list = [KafkaConfig.TOPIC_METEO_TEMPS_REEL]
        elif topics == 'alertes':
            topic_list = [KafkaConfig.TOPIC_ALERTES_METEO]
        else:
            topic_list = [
                KafkaConfig.TOPIC_METEO_TEMPS_REEL,
                KafkaConfig.TOPIC_ALERTES_METEO,
                KafkaConfig.TOPIC_EVENEMENTS_URBAINS
            ]
        
        click.echo(f"📡 Démarrage des consommateurs Kafka...")
        click.echo(f"🎯 Topics: {', '.join(topic_list)}")
        click.echo("⏹️  Ctrl+C pour arrêter")
        
        # Créer le consommateur
        consumer = KafkaConsumer(
            *topic_list,
            bootstrap_servers=KafkaConfig.BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id=KafkaConfig.GROUP_ID,
            auto_offset_reset='latest'
        )
        
        message_count = 0
        
        try:
            for message in consumer:
                message_count += 1
                
                topic = message.topic
                value = message.value
                timestamp = datetime.fromtimestamp(message.timestamp / 1000)
                
                click.echo(f"\n📨 Message {message_count} reçu:")
                click.echo(f"  🎯 Topic: {topic}")
                click.echo(f"  ⏰ Timestamp: {timestamp}")
                
                if topic == KafkaConfig.TOPIC_METEO_TEMPS_REEL:
                    station = value.get('station', 'Unknown')
                    temp = value.get('temperature', 'N/A')
                    humidity = value.get('humidite', 'N/A')
                    click.echo(f"  🌡️ Station: {station}")
                    click.echo(f"  🌡️ Température: {temp}°C")
                    click.echo(f"  💧 Humidité: {humidity}%")
                
                elif topic == KafkaConfig.TOPIC_ALERTES_METEO:
                    alert_type = value.get('type_alerte', 'Unknown')
                    level = value.get('niveau', 'Unknown')
                    click.echo(f"  🚨 Type: {alert_type}")
                    click.echo(f"  ⚠️ Niveau: {level}")
                
                else:
                    click.echo(f"  📄 Données: {str(value)[:100]}...")
                
                # Pause pour la lisibilité
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            click.echo(f"\n⏹️ Arrêt du streaming Kafka ({message_count} messages traités)")
        finally:
            consumer.close()
        
    except ImportError as e:
        click.echo(f"❌ Erreur d'import Kafka: {e}")
        click.echo("💡 Installez kafka-python")
    except Exception as e:
        logger.error(f"Erreur Kafka: {e}")
        click.echo(f"❌ Erreur: {e}")

@process.command()
@click.option('--pipeline', default='full', 
              type=click.Choice(['collect', 'kafka', 'spark', 'full']),
              help='Pipeline à exécuter')
def pipeline(pipeline):
    """Lance le pipeline complet de traitement"""
    logger.info(f"Lancement du pipeline: {pipeline}")
    
    try:
        if pipeline in ['collect', 'full']:
            click.echo("🔄 Étape 1: Collecte des données...")
            
            # Collecte et envoi vers Kafka
            from data_collection.collectors.toulouse_collector import CombinedMeteoCollector
            collector = CombinedMeteoCollector()
            data = collector.collect_all_stations(limit=10, send_to_kafka=True)
            
            if not data.empty:
                click.echo(f"✅ {len(data)} enregistrements collectés et envoyés vers Kafka")
                
                # Sauvegarde pour Spark batch
                filename = config.DATA_DIR / "raw" / f"pipeline_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                data.to_csv(filename, index=False)
                click.echo(f"💾 Données sauvegardées: {filename}")
            else:
                click.echo("❌ Échec de la collecte")
                return
        
        if pipeline in ['spark', 'full']:
            click.echo("\n⚡ Étape 2: Traitement Spark...")
            
            # Lancer traitement Spark en mode batch
            import glob
            files = glob.glob(str(config.DATA_DIR / "raw" / "*.csv"))
            if files:
                latest_file = max(files, key=lambda x: os.path.getctime(x))
                output_dir = config.DATA_DIR / "processed" / f"spark_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                from data_processing.spark_jobs.meteo_processor import run_batch_processing
                result = run_batch_processing(latest_file, str(output_dir))
                
                if result is not None:
                    click.echo(f"✅ Traitement Spark terminé: {result.count()} enregistrements")
                else:
                    click.echo("❌ Échec traitement Spark")
            else:
                click.echo("❌ Aucun fichier de données trouvé")
        
        if pipeline == 'full':
            click.echo("\n🌐 Étape 3: Interface disponible")
            click.echo("💡 Lancez: python main.py web streamlit")
        
        click.echo(f"\n🎉 Pipeline {pipeline} terminé avec succès!")
        
    except Exception as e:
        logger.error(f"Erreur pipeline: {e}")
        click.echo(f"❌ Erreur pipeline: {e}")

# Ajouter l'import nécessaire en haut du fichier
import os
import time
from datetime import datetime

@cli.group()
def web():
    """Commandes interface web"""
    pass

@web.command()
@click.option('--port', default=8501, help='Port Streamlit')
@click.option('--host', default='localhost', help='Host Streamlit')
def streamlit(port, host):
    """Lance l'interface Streamlit"""
    logger.info(f"Démarrage Streamlit sur {host}:{port}")
    
    import subprocess
    import sys
    
    try:
        streamlit_path = config.BASE_DIR / "web-interface" / "streamlit-app" / "main.py"
        
        if not streamlit_path.exists():
            click.echo(f"❌ Fichier Streamlit non trouvé: {streamlit_path}")
            click.echo("Créez le fichier avec: python main.py setup streamlit")
            return
        
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(streamlit_path),
            "--server.port", str(port),
            "--server.address", host
        ]
        
        click.echo(f"🌐 Lancement Streamlit sur http://{host}:{port}")
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        click.echo("\n⏹️ Arrêt de Streamlit")
    except Exception as e:
        logger.error(f"Erreur Streamlit: {e}")
        click.echo(f"❌ Erreur: {e}")

@web.command()
def api():
    """Lance l'API FastAPI"""
    logger.info("Démarrage API FastAPI")
    
    try:
        from web_interface.api.main import app
        import uvicorn
        from config import WebConfig
        
        click.echo(f"🚀 Lancement API sur http://{WebConfig.FASTAPI_HOST}:{WebConfig.FASTAPI_PORT}")
        uvicorn.run(app, host=WebConfig.FASTAPI_HOST, port=WebConfig.FASTAPI_PORT)
        
    except Exception as e:
        logger.error(f"Erreur API: {e}")
        click.echo(f"❌ Erreur: {e}")

@cli.group()
def docker():
    """Commandes Docker"""
    pass

@docker.command()
def up():
    """Lance tous les services Docker"""
    logger.info("Lancement des services Docker")
    
    import subprocess
    
    try:
        click.echo("🐳 Lancement de Docker Compose...")
        result = subprocess.run(["docker-compose", "up", "-d"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("✅ Services Docker lancés")
            click.echo("\n📋 Services disponibles:")
            click.echo("  • Streamlit:     http://localhost:8501")
            click.echo("  • Kafka UI:      http://localhost:8085") 
            click.echo("  • NiFi:          http://localhost:8080")
            click.echo("  • Spark Master:  http://localhost:9090")
            click.echo("  • PgAdmin:       http://localhost:5050")
            click.echo("  • Mongo Express: http://localhost:8081")
        else:
            click.echo(f"❌ Erreur Docker: {result.stderr}")
            
    except FileNotFoundError:
        click.echo("❌ Docker Compose non trouvé. Installez Docker.")
    except Exception as e:
        click.echo(f"❌ Erreur: {e}")

@docker.command()
def down():
    """Arrête tous les services Docker"""
    logger.info("Arrêt des services Docker")
    
    import subprocess
    
    try:
        click.echo("🐳 Arrêt de Docker Compose...")
        result = subprocess.run(["docker-compose", "down"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("✅ Services Docker arrêtés")
        else:
            click.echo(f"❌ Erreur Docker: {result.stderr}")
            
    except Exception as e:
        click.echo(f"❌ Erreur: {e}")

@docker.command()
def status():
    """Affiche le statut des services Docker"""
    import subprocess
    
    try:
        click.echo("🔍 Statut des services Docker:")
        subprocess.run(["docker-compose", "ps"])
    except Exception as e:
        click.echo(f"❌ Erreur: {e}")

@cli.group()
def setup():
    """Commandes de configuration initiale"""
    pass

@setup.command()
def install():
    """Installation complète du projet"""
    click.echo("🚀 Installation de la plateforme météo Toulouse")
    
    # Vérification Python
    python_version = sys.version_info
    if python_version < (3, 8):
        click.echo("❌ Python 3.8+ requis")
        return
    
    click.echo(f"✅ Python {python_version.major}.{python_version.minor}")
    
    # Installation des dépendances
    import subprocess
    
    try:
        click.echo("📦 Installation des dépendances...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        click.echo("✅ Dépendances installées")
    except subprocess.CalledProcessError:
        click.echo("❌ Erreur lors de l'installation des dépendances")
        return
    
    # Création des dossiers
    click.echo("📁 Création de la structure...")
    for folder in ["data/raw", "data/processed", "data/exports", "logs"]:
        (config.BASE_DIR / folder).mkdir(parents=True, exist_ok=True)
    
    # Création du .env
    env_file = config.BASE_DIR / ".env"
    if not env_file.exists():
        click.echo("⚙️ Création du fichier .env...")
        env_example = config.BASE_DIR / ".env.example"
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            click.echo("✅ Fichier .env créé (éditez-le pour vos paramètres)")
    
    click.echo("\n🎉 Installation terminée !")
    click.echo("\n📋 Prochaines étapes:")
    click.echo("  1. Éditez le fichier .env avec vos configurations")
    click.echo("  2. Lancez: python main.py docker up")
    click.echo("  3. Initialisez les DB: python main.py db init")
    click.echo("  4. Testez la collecte: python main.py collect meteo")
    click.echo("  5. Lancez l'interface: python main.py web streamlit")

@setup.command()
def streamlit():
    """Crée l'application Streamlit de base"""
    click.echo("🌐 Création de l'application Streamlit")
    
    streamlit_dir = config.BASE_DIR / "web-interface" / "streamlit-app"
    streamlit_dir.mkdir(parents=True, exist_ok=True)
    
    # Création du fichier Streamlit principal
    streamlit_main = streamlit_dir / "main.py"
    
    streamlit_content = '''import streamlit as st
import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from web_interface.streamlit_app.meteo_search_engine import main

if __name__ == "__main__":
    main()
'''
    
    with open(streamlit_main, 'w', encoding='utf-8') as f:
        f.write(streamlit_content)
    
    click.echo(f"✅ Fichier Streamlit créé: {streamlit_main}")

@setup.command()
def examples():
    """Génère des données d'exemple"""
    click.echo("📊 Génération de données d'exemple")
    
    try:
        from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Données simulées
        click.echo("🎲 Génération de données météo simulées...")
        
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=30), 
            end=datetime.now(), 
            freq='H'
        )
        
        np.random.seed(42)
        data = pd.DataFrame({
            'timestamp': dates,
            'temperature': 15 + 10 * np.sin(np.arange(len(dates)) * 2 * np.pi / (24 * 365)) + np.random.normal(0, 3, len(dates)),
            'humidite': 50 + 30 * np.random.random(len(dates)),
            'pression': 1013 + np.random.normal(0, 10, len(dates)),
            'vitesse_vent': np.random.normal(8, len(dates)),
            'direction_vent': np.random.uniform(0, 360, len(dates)),
            'precipitation': np.where(np.random.random(len(dates)) < 0.2, np.random.normal(2), 0)
        })
        
        # Sauvegarde
        example_file = config.DATA_DIR / "raw" / "example_meteo_data.csv"
        data.to_csv(example_file, index=False)
        
        click.echo(f"✅ {len(data)} enregistrements d'exemple créés dans {example_file}")
        
    except Exception as e:
        click.echo(f"❌ Erreur: {e}")

@cli.command()
def test():
    """Lance les tests unitaires"""
    logger.info("Lancement des tests")
    
    import subprocess
    
    try:
        click.echo("🧪 Lancement des tests...")
        result = subprocess.run(["python", "-m", "pytest", "tests/", "-v"], 
                              capture_output=True, text=True)
        
        click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr)
            
        if result.returncode == 0:
            click.echo("✅ Tous les tests passent")
        else:
            click.echo("❌ Certains tests échouent")
            
    except FileNotFoundError:
        click.echo("❌ pytest non trouvé. Installez avec: pip install pytest")
    except Exception as e:
        click.echo(f"❌ Erreur: {e}")

@cli.command()
def info():
    """Affiche les informations sur la plateforme"""
    click.echo(f"""
🌤️ {config.APP_NAME} v{config.APP_VERSION}

📊 Configuration:
  • Mode Debug: {config.DEBUG}
  • Répertoire: {config.BASE_DIR}
  • Logs: {config.LOG_LEVEL}

🗄️ Bases de données:
  • PostgreSQL: {DatabaseConfig.POSTGRES_HOST}:{DatabaseConfig.POSTGRES_PORT}
  • MongoDB: {DatabaseConfig.MONGODB_HOST}:{DatabaseConfig.MONGODB_PORT}
  • SQLite: {DatabaseConfig.SQLITE_PATH}

📡 Services:
  • Kafka: {', '.join(KafkaConfig.BOOTSTRAP_SERVERS)}
  • Spark: {SparkConfig.MASTER_URL}

🌐 Web:
  • Streamlit: http://localhost:{WebConfig.STREAMLIT_PORT}
  • API: http://localhost:{WebConfig.FASTAPI_PORT}

📋 Commandes disponibles:
  • python main.py collect meteo    - Collecte données météo
  • python main.py docker up       - Lance tous les services
  • python main.py web streamlit   - Interface utilisateur
  • python main.py db status       - Statut des bases
  • python main.py setup install   - Installation complète
""")

if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n👋 Au revoir !")
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        click.echo(f"❌ Erreur inattendue: {e}")
        sys.exit(1)