"""
Initialisation du schéma PostgreSQL pour les données météo
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from pathlib import Path
import sys

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from config import DatabaseConfig

logger = logging.getLogger(__name__)

# Schémas SQL
CREATE_TABLES_SQL = """
-- ==============================================
-- TABLES PRINCIPALES DONNEES METEO
-- ==============================================

-- Table des mesures météorologiques
CREATE TABLE IF NOT EXISTS mesures_meteo (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    station VARCHAR(100) NOT NULL,
    temperature REAL,
    humidite REAL,
    pression REAL,
    vitesse_vent REAL,
    direction_vent REAL,
    precipitation REAL,
    rafale_max REAL,
    pluie_intensite_max REAL,
    type_station VARCHAR(50),
    heure_paris VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(timestamp, station)
);

-- Table des métriques calculées
CREATE TABLE IF NOT EXISTS metriques_calculees (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    station VARCHAR(100) NOT NULL,
    temp_moy_7j REAL,
    temp_moy_30j REAL,
    temp_volatilite_7j REAL,
    temp_volatilite_30j REAL,
    temp_tendance_24h REAL,
    indice_confort VARCHAR(50),
    risque_precipitation VARCHAR(50),
    score_anomalie_temp REAL,
    score_anomalie_vent REAL,
    score_anomalie_pression REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(timestamp, station)
);

-- Table des alertes météorologiques
CREATE TABLE IF NOT EXISTS alertes_meteo (
    id SERIAL PRIMARY KEY,
    type_alerte VARCHAR(100) NOT NULL,
    niveau VARCHAR(50) NOT NULL,
    zone_geographique VARCHAR(100),
    debut TIMESTAMP WITH TIME ZONE,
    fin TIMESTAMP WITH TIME ZONE,
    description TEXT,
    source VARCHAR(100),
    severite INTEGER DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table des événements urbains
CREATE TABLE IF NOT EXISTS evenements_urbains (
    id SERIAL PRIMARY KEY,
    titre VARCHAR(200) NOT NULL,
    description TEXT,
    type_evenement VARCHAR(100),
    localisation VARCHAR(200),
    debut TIMESTAMP WITH TIME ZONE,
    fin TIMESTAMP WITH TIME ZONE,
    impact_prevu VARCHAR(100),
    source VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table des corrélations météo-urbain
CREATE TABLE IF NOT EXISTS correlations_meteo_urbain (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    type_correlation VARCHAR(100) NOT NULL,
    valeur_correlation REAL,
    variable_meteo VARCHAR(50),
    variable_urbaine VARCHAR(50),
    zone VARCHAR(100),
    periode_analyse VARCHAR(50),
    significativite REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==============================================
-- INDEX POUR PERFORMANCE
-- ==============================================

-- Index sur les timestamps pour les requêtes temporelles
CREATE INDEX IF NOT EXISTS idx_mesures_meteo_timestamp ON mesures_meteo(timestamp);
CREATE INDEX IF NOT EXISTS idx_mesures_meteo_station ON mesures_meteo(station);
CREATE INDEX IF NOT EXISTS idx_mesures_meteo_station_timestamp ON mesures_meteo(station, timestamp);

CREATE INDEX IF NOT EXISTS idx_metriques_timestamp ON metriques_calculees(timestamp);
CREATE INDEX IF NOT EXISTS idx_metriques_station ON metriques_calculees(station);

CREATE INDEX IF NOT EXISTS idx_alertes_niveau ON alertes_meteo(niveau);
CREATE INDEX IF NOT EXISTS idx_alertes_zone ON alertes_meteo(zone_geographique);
CREATE INDEX IF NOT EXISTS idx_alertes_active ON alertes_meteo(active);
CREATE INDEX IF NOT EXISTS idx_alertes_debut_fin ON alertes_meteo(debut, fin);

CREATE INDEX IF NOT EXISTS idx_evenements_type ON evenements_urbains(type_evenement);
CREATE INDEX IF NOT EXISTS idx_evenements_debut ON evenements_urbains(debut);

-- Index GIN pour les recherches JSONB
CREATE INDEX IF NOT EXISTS idx_evenements_metadata ON evenements_urbains USING GIN(metadata);

-- ==============================================
-- VUES UTILES
-- ==============================================

-- Vue des dernières mesures par station
CREATE OR REPLACE VIEW v_dernieres_mesures AS
SELECT DISTINCT ON (station) 
    station,
    timestamp,
    temperature,
    humidite,
    pression,
    vitesse_vent,
    precipitation
FROM mesures_meteo 
ORDER BY station, timestamp DESC;

-- Vue des alertes actives
CREATE OR REPLACE VIEW v_alertes_actives AS
SELECT 
    type_alerte,
    niveau,
    zone_geographique,
    debut,
    fin,
    description
FROM alertes_meteo 
WHERE active = TRUE 
  AND (fin IS NULL OR fin > NOW())
ORDER BY severite DESC, debut DESC;

-- Vue des statistiques mensuelles
CREATE OR REPLACE VIEW v_stats_mensuelles AS
SELECT 
    station,
    DATE_TRUNC('month', timestamp) as mois,
    COUNT(*) as nb_mesures,
    AVG(temperature) as temp_moyenne,
    MIN(temperature) as temp_min,
    MAX(temperature) as temp_max,
    STDDEV(temperature) as temp_volatilite,
    AVG(humidite) as humidite_moyenne,
    SUM(precipitation) as precipitation_totale,
    AVG(vitesse_vent) as vent_moyen,
    MAX(vitesse_vent) as vent_max
FROM mesures_meteo 
WHERE timestamp >= NOW() - INTERVAL '12 months'
GROUP BY station, DATE_TRUNC('month', timestamp)
ORDER BY station, mois;

-- ==============================================
-- FONCTIONS UTILITAIRES
-- ==============================================

-- Fonction pour calculer la température ressentie
CREATE OR REPLACE FUNCTION temperature_ressentie(temp REAL, humidite REAL, vent REAL)
RETURNS REAL AS $$
BEGIN
    -- Formule simplifiée de température ressentie
    -- Prend en compte température, humidité et vent
    IF temp IS NULL OR humidite IS NULL OR vent IS NULL THEN
        RETURN temp;
    END IF;
    
    -- Facteur humidité (Heat Index simplifié)
    IF temp > 25 THEN
        RETURN temp + (humidite - 50) * 0.1;
    -- Facteur vent (Wind Chill simplifié)
    ELSIF temp < 10 THEN
        RETURN temp - vent * 0.5;
    ELSE
        RETURN temp;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour classifier le confort météo
CREATE OR REPLACE FUNCTION classifer_confort(temp REAL, humidite REAL)
RETURNS VARCHAR(50) AS $$
BEGIN
    IF temp IS NULL OR humidite IS NULL THEN
        RETURN 'inconnu';
    END IF;
    
    IF temp BETWEEN 18 AND 24 AND humidite BETWEEN 40 AND 60 THEN
        RETURN 'optimal';
    ELSIF temp > 30 OR (temp > 25 AND humidite > 70) THEN
        RETURN 'trop_chaud';
    ELSIF temp < 10 THEN
        RETURN 'froid';
    ELSIF humidite > 80 THEN
        RETURN 'humide';
    ELSIF humidite < 30 THEN
        RETURN 'sec';
    ELSE
        RETURN 'modere';
    END IF;
END;
$$ LANGUAGE plpgsql;
"""

def create_database_if_not_exists():
    """Crée la base de données si elle n'existe pas"""
    try:
        # Connexion à PostgreSQL sans spécifier de base
        conn_params = {
            'host': DatabaseConfig.POSTGRES_HOST,
            'port': DatabaseConfig.POSTGRES_PORT,
            'user': DatabaseConfig.POSTGRES_USER,
            'password': DatabaseConfig.POSTGRES_PASSWORD,
            'database': 'postgres'  # Base par défaut
        }
        
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Vérifier si la base existe
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DatabaseConfig.POSTGRES_DB,)
        )
        
        if not cursor.fetchone():
            # Créer la base
            cursor.execute(f"CREATE DATABASE {DatabaseConfig.POSTGRES_DB}")
            logger.info(f"Base de données {DatabaseConfig.POSTGRES_DB} créée")
        else:
            logger.info(f"Base de données {DatabaseConfig.POSTGRES_DB} existe déjà")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Erreur création base: {e}")
        raise

def init_postgresql_schema():
    """Initialise le schéma PostgreSQL"""
    try:
        # Créer la base si nécessaire
        create_database_if_not_exists()
        
        # Connexion à la base cible
        conn = psycopg2.connect(DatabaseConfig.POSTGRES_URL)
        cursor = conn.cursor()
        
        # Exécuter le script de création
        logger.info("Création des tables PostgreSQL...")
        cursor.execute(CREATE_TABLES_SQL)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ Schéma PostgreSQL initialisé avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur initialisation PostgreSQL: {e}")
        raise

def drop_all_tables():
    """Supprime toutes les tables (pour reset complet)"""
    DROP_SQL = """
    DROP VIEW IF EXISTS v_dernieres_mesures CASCADE;
    DROP VIEW IF EXISTS v_alertes_actives CASCADE;
    DROP VIEW IF EXISTS v_stats_mensuelles CASCADE;
    
    DROP FUNCTION IF EXISTS temperature_ressentie CASCADE;
    DROP FUNCTION IF EXISTS classifer_confort CASCADE;
    
    DROP TABLE IF EXISTS correlations_meteo_urbain CASCADE;
    DROP TABLE IF EXISTS evenements_urbains CASCADE;
    DROP TABLE IF EXISTS alertes_meteo CASCADE;
    DROP TABLE IF EXISTS metriques_calculees CASCADE;
    DROP TABLE IF EXISTS mesures_meteo CASCADE;
    """
    
    try:
        conn = psycopg2.connect(DatabaseConfig.POSTGRES_URL)
        cursor = conn.cursor()
        
        logger.warning("🗑️ Suppression de toutes les tables...")
        cursor.execute(DROP_SQL)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ Tables supprimées")
        
    except Exception as e:
        logger.error(f"❌ Erreur suppression: {e}")
        raise

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("🐘 Initialisation PostgreSQL...")
    init_postgresql_schema()
    print("✅ Terminé !")