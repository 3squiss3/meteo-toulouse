"""
Configuration centralisée pour la plateforme météo Toulouse
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

class Config:
    """Configuration de base"""
    
    # Paths
    BASE_DIR = Path(__file__).parent.absolute()
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    
    # Application
    APP_NAME = os.getenv("APP_NAME", "meteo-toulouse-platform")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Création des dossiers si ils n'existent pas
    DATA_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "raw").mkdir(exist_ok=True)
    (DATA_DIR / "processed").mkdir(exist_ok=True)
    (DATA_DIR / "exports").mkdir(exist_ok=True)

class DatabaseConfig:
    """Configuration des bases de données"""
    
    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "meteo_toulouse")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "meteo_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "meteo_pass")
    POSTGRES_URL = os.getenv(
        "POSTGRES_URL", 
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # MongoDB
    MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
    MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
    MONGODB_DB = os.getenv("MONGODB_DB", "meteo_events")
    MONGODB_USER = os.getenv("MONGODB_USER", "meteo_user")
    MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "meteo_pass")
    MONGODB_URL = os.getenv(
        "MONGODB_URL",
        f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}"
    )
    
    # SQLite (développement)
    SQLITE_PATH = os.getenv("SQLITE_PATH", str(Config.DATA_DIR / "meteo_local.db"))

class KafkaConfig:
    """Configuration Kafka"""
    
    BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
    
    # Topics
    TOPIC_METEO_TEMPS_REEL = os.getenv("KAFKA_TOPIC_METEO_TEMPS_REEL", "topic_meteo_temps_reel")
    TOPIC_ALERTES_METEO = os.getenv("KAFKA_TOPIC_ALERTES_METEO", "topic_alertes_meteo")
    TOPIC_EVENEMENTS_URBAINS = os.getenv("KAFKA_TOPIC_EVENEMENTS_URBAINS", "topic_evenements_urbains")
    TOPIC_ACTIVITE_URBAINE = os.getenv("KAFKA_TOPIC_ACTIVITE_URBAINE", "topic_activite_urbaine")
    
    # Consumer/Producer
    GROUP_ID = os.getenv("KAFKA_GROUP_ID", "meteo-consumer-group")
    AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")
    BATCH_SIZE = int(os.getenv("KAFKA_BATCH_SIZE", "100"))

class SparkConfig:
    """Configuration Spark"""
    
    MASTER_URL = os.getenv("SPARK_MASTER_URL", "local[*]")
    APP_NAME = os.getenv("SPARK_APP_NAME", "MeteoToulouseAnalysis")
    EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "2g")
    DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "1g")
    EXECUTOR_CORES = int(os.getenv("SPARK_EXECUTOR_CORES", "2"))
    BATCH_INTERVAL = int(os.getenv("SPARK_BATCH_INTERVAL", "30"))

class APIConfig:
    """Configuration des APIs externes"""
    
    # Toulouse Open Data
    TOULOUSE_BASE_URL = os.getenv(
        "TOULOUSE_API_BASE_URL", 
        "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets"
    )
    TOULOUSE_TIMEOUT = int(os.getenv("TOULOUSE_API_TIMEOUT", "30"))
    TOULOUSE_RATE_LIMIT = int(os.getenv("TOULOUSE_API_RATE_LIMIT", "100"))
    
    # OpenWeatherMap
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    OPENWEATHER_BASE_URL = os.getenv("OPENWEATHER_BASE_URL", "http://api.openweathermap.org/data/2.5")
    
    # Météo France
    METEOFRANCE_API_URL = os.getenv("METEOFRANCE_API_URL", "https://donneespubliques.meteofrance.fr")
    METEOFRANCE_API_KEY = os.getenv("METEOFRANCE_API_KEY")
    
    # Configuration générale des requêtes
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

class LLMConfig:
    """Configuration LLM"""
    
    # Hugging Face
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    MODEL_NAME = os.getenv("LLM_MODEL_NAME", "microsoft/DialoGPT-medium")
    MAX_LENGTH = int(os.getenv("LLM_MAX_LENGTH", "200"))
    TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    # OpenAI (optionnel)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

class CollectionConfig:
    """Configuration de la collecte de données"""
    
    # Fréquences (en minutes)
    FREQUENCY_METEO = int(os.getenv("COLLECT_FREQUENCY_METEO", "15"))
    FREQUENCY_ALERTS = int(os.getenv("COLLECT_FREQUENCY_ALERTS", "60"))
    FREQUENCY_EVENTS = int(os.getenv("COLLECT_FREQUENCY_EVENTS", "30"))

class WebConfig:
    """Configuration interface web"""
    
    # Streamlit
    STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
    STREAMLIT_HOST = os.getenv("STREAMLIT_HOST", "0.0.0.0")
    STREAMLIT_MAX_UPLOAD_SIZE = int(os.getenv("STREAMLIT_SERVER_MAX_UPLOAD_SIZE", "200"))
    
    # FastAPI
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")

class LoggingConfig:
    """Configuration des logs"""
    
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", str(Config.LOGS_DIR / "meteo_platform.log"))
    LOG_MAX_SIZE = os.getenv("LOG_MAX_SIZE", "10MB")
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    
    @staticmethod
    def get_logging_config():
        """Retourne la configuration des logs pour logging.dictConfig"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                },
                "detailed": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": Config.LOG_LEVEL,
                    "formatter": "standard",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "detailed",
                    "filename": LoggingConfig.LOG_FILE_PATH,
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": LoggingConfig.LOG_BACKUP_COUNT
                }
            },
            "loggers": {
                "": {  # Root logger
                    "handlers": ["console", "file"],
                    "level": Config.LOG_LEVEL,
                    "propagate": False
                }
            }
        }

class FeatureFlags:
    """Flags pour activer/désactiver des fonctionnalités"""
    
    ENABLE_LLM_ENRICHMENT = os.getenv("ENABLE_LLM_ENRICHMENT", "true").lower() == "true"
    ENABLE_REAL_TIME_PROCESSING = os.getenv("ENABLE_REAL_TIME_PROCESSING", "true").lower() == "true"
    ENABLE_ALERTS = os.getenv("ENABLE_ALERTS", "true").lower() == "true"
    ENABLE_MONITORING = os.getenv("ENABLE_MONITORING", "false").lower() == "true"

# Configurations par environnement
class DevelopmentConfig(Config):
    """Configuration pour le développement"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Configuration pour la production"""
    DEBUG = False

class TestingConfig(Config):
    """Configuration pour les tests"""
    DEBUG = True
    TESTING = True
    SQLITE_PATH = ":memory:"  # Base en mémoire pour les tests

# Sélection de la configuration selon l'environnement
def get_config() -> Config:
    """Retourne la configuration selon l'environnement"""
    env = os.getenv("FLASK_ENV", "development")
    
    if env == "production":
        return ProductionConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()

# Configuration active
config = get_config()

# Export de toutes les configurations pour faciliter les imports
__all__ = [
    "Config", "DatabaseConfig", "KafkaConfig", "SparkConfig", 
    "APIConfig", "LLMConfig", "CollectionConfig", "WebConfig", 
    "LoggingConfig", "FeatureFlags", "config"
]