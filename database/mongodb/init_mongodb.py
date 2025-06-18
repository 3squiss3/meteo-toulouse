"""
Initialisation MongoDB pour les données météo
"""

import sys
from pathlib import Path
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from config import DatabaseConfig

logger = logging.getLogger(__name__)

def init_mongodb_collections():
    """Initialise les collections MongoDB"""
    try:
        # Connexion à MongoDB
        client = MongoClient(DatabaseConfig.MONGODB_URL)
        
        # Test de connexion
        client.admin.command('ping')
        logger.info("Connexion MongoDB établie")
        
        # Base de données
        db = client[DatabaseConfig.MONGODB_DB]
        
        # Collection événements météo
        evenements_collection = db.evenements_meteo
        
        # Index pour optimiser les recherches
        evenements_collection.create_index("timestamp")
        evenements_collection.create_index("type_evenement")
        evenements_collection.create_index("zone_geographique")
        evenements_collection.create_index([("titre", "text"), ("description", "text")])
        
        # Collection associations
        associations_collection = db.associations_meteo
        associations_collection.create_index("timestamp")
        associations_collection.create_index("type_association")
        
        # Collection métadonnées LLM
        metadonnees_collection = db.metadonnees_llm
        metadonnees_collection.create_index("timestamp")
        metadonnees_collection.create_index("type_analyse")
        
        # Exemples de documents
        sample_evenement = {
            "titre": "Test - Conditions météo normales",
            "timestamp": "2024-06-10T15:00:00Z",
            "source": "init_script",
            "type_evenement": "test",
            "zone_geographique": "toulouse",
            "description": "Document d'exemple créé lors de l'initialisation",
            "metadonnees": {
                "impact_prevu": "aucun",
                "niveau_confiance": 0.95,
                "entites_extraites": ["toulouse", "test"]
            }
        }
        
        # Insérer si la collection est vide
        if evenements_collection.count_documents({}) == 0:
            evenements_collection.insert_one(sample_evenement)
            logger.info("Document d'exemple inséré dans evenements_meteo")
        
        logger.info("✅ Collections MongoDB initialisées")
        
        client.close()
        
    except ConnectionFailure:
        logger.error("❌ Impossible de se connecter à MongoDB")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur initialisation MongoDB: {e}")
        raise

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("🍃 Initialisation MongoDB...")
    init_mongodb_collections()
    print("✅ Terminé !")