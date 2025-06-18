# 🌤️ Plateforme d'Analyse Météorologique Toulouse

## Vue d'ensemble

Ce projet adapte le TP original de "Plateforme d'Analyse des Marchés Boursiers" pour créer une **plateforme d'analyse météorologique** utilisant les données ouvertes de Toulouse Métropole.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Collecte      │    │   Traitement    │    │   Interface     │
│                 │    │                 │    │                 │
│ • Data Toulouse │───▶│ • Kafka Topics  │───▶│ • Recherche NL  │
│ • API Météo     │    │ • Spark Stream  │    │ • Streamlit UI  │
│ • Flux RSS      │    │ • LLM Enrich.   │    │ • Visualisation │
│ • Apache NiFi   │    │ • Métriques     │    │ • SQL/NoSQL     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Stockage de Données                       │
│   • PostgreSQL (Données structurées)                           │
│   • MongoDB (Événements, métadonnées)                          │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Démarrage Rapide

### Prérequis
- Docker & Docker Compose
- Python 3.9+
- 8GB RAM recommandés

### 1. Clone et Setup
```bash
git clone <votre-repo>
cd meteo-toulouse-platform

# Créer la structure des dossiers
mkdir -p {data,sql,spark-apps,nifi-processors,streamlit-app}

# Copier les scripts dans leurs dossiers respectifs
```

### 2. Lancement de l'environnement
```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier que tout fonctionne
docker-compose ps
```

### 3. Accès aux interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| Streamlit (Interface principale) | http://localhost:8501 | - |
| Kafka UI | http://localhost:8085 | - |
| NiFi | http://localhost:8080 | admin/adminpassword |
| Spark Master | http://localhost:9090 | - |
| PgAdmin | http://localhost:5050 | admin@meteo.local/admin |
| Mongo Express | http://localhost:8081 | - |

## 📊 Sources de Données

### Données Principales
- **Toulouse Open Data** : Station météo Compans Cafarelli
  - URL : `https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/42-station-meteo-toulouse-parc-compans-cafarelli`
  - Fréquence : Temps réel (15-30 min)
  - Variables : Température, humidité, pression, vent, précipitations

### Données Complémentaires
- **Météo France API** : Vigilances et alertes
- **OpenWeatherMap** : Données multi-villes
- **Flux RSS** : Actualités météo, alertes climatiques

## 🔧 Configuration des Topics Kafka

```bash
# Créer les topics
docker exec kafka kafka-topics --create --topic topic_meteo_temps_reel --bootstrap-server localhost:9092
docker exec kafka kafka-topics --create --topic topic_alertes_meteo --bootstrap-server localhost:9092
docker exec kafka kafka-topics --create --topic topic_evenements_urbains --bootstrap-server localhost:9092
```

## 💾 Schémas de Base de Données

### PostgreSQL (Données Structurées)
```sql
-- Mesures météorologiques
CREATE TABLE mesures_meteo (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    station VARCHAR(100),
    temperature REAL,
    humidite REAL,
    pression REAL,
    vitesse_vent REAL,
    direction_vent REAL,
    precipitation REAL
);

-- Métriques calculées
CREATE TABLE metriques_calculees (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    station VARCHAR(100),
    temp_moy_7j REAL,
    temp_volatilite REAL,
    indice_confort VARCHAR(50),
    tendance VARCHAR(50)
);
```

### MongoDB (Données Semi-Structurées)
```javascript
// Collection: evenements_meteo
{
    "_id": ObjectId("..."),
    "titre": "Alerte canicule Toulouse",
    "timestamp": ISODate("2024-06-10T15:00:00Z"),
    "source": "meteo_france",
    "contenu": "Températures supérieures à 35°C...",
    "entites_extraites": ["toulouse", "canicule", "35°C"],
    "metadonnees": {
        "type_evenement": "alerte_climatique",
        "niveau_severite": "orange",
        "zone_geographique": "toulouse_metropole",
        "impact_prevu": "forte_chaleur",
        "duree_estimee": "3_jours"
    },
    "associations": [
        {
            "type": "temperature_extremes",
            "correlation": 0.95
        }
    ]
}
```

## 🤖 Exemples de Requêtes NLP

L'interface Streamlit permet de poser des questions en langage naturel :

### Questions de Base
- *"Quelle est la température maintenant ?"*
- *"Il fait combien aujourd'hui ?"*
- *"Montre-moi le temps qu'il fait"*

### Analyses Temporelles
- *"Température des 7 derniers jours"*
- *"Évolution de l'humidité cette semaine"*
- *"Tendance météo du mois"*

### Événements Spécifiques
- *"Quand a-t-il plu récemment ?"*
- *"Y a-t-il eu du vent fort ?"*
- *"Alertes météo en cours"*

### Comparaisons
- *"Compare la température d'hier et aujourd'hui"*
- *"Différence avec la semaine dernière"*
- *"Année la plus chaude"*

## 📈 Métriques Calculées

### Indicateurs Temps Réel
- **Température ressentie** : Formule incluant humidité et vent
- **Indice de confort** : Optimal/Chaud/Froid basé sur temp + humidité
- **Risque de précipitation** : Basé sur humidité et pression

### Tendances
- **Moyennes mobiles** : 7j, 30j pour température et humidité
- **Volatilité météo** : Écart-type des variations
- **Détection d'anomalies** : Seuils percentiles 5% et 95%

### Associations LLM
- **Impact urbain** : Corrélation météo ↔ activité urbaine
- **Événements saisonniers** : Détection de patterns
- **Prédictions simples** : Basées sur historique

## 🔍 Moteur de Recherche

### Architecture NLP → SQL
```python
Question: "Température des 3 derniers jours"
     ↓
LLM Translation
     ↓
SQL: SELECT timestamp, temperature FROM mesures_meteo 
     WHERE timestamp >= datetime('now', '-3 days')
     ↓
Résultats + Visualisation
```

### Types de Réponses
- **Données tabulaires** : DataFrame Pandas
- **Graphiques** : Plotly (lignes, histogrammes)
- **Métriques** : Valeurs agrégées (min/max/moyenne)
- **Analyse LLM** : Interprétation en langage naturel

## 🐛 Troubleshooting

### Problèmes Courants

**Kafka ne démarre pas**
```bash
# Vérifier les logs
docker-compose logs kafka

# Nettoyer et redémarrer
docker-compose down -v
docker-compose up -d kafka
```

**Pas de données dans Streamlit**
```bash
# Générer des données d'exemple
docker exec streamlit-meteo python generate_sample_data.py
```

**Spark Jobs échouent**
```bash
# Vérifier la mémoire
docker stats
# Ajuster dans docker-compose.yml si nécessaire
```

### Monitoring
```bash
# Status des services
docker-compose ps

# Logs en temps réel
docker-compose logs -f meteo-collector

# Utilisation ressources
docker stats
```

## 📋 ToDo pour le TP

### Phase 1 : Setup et Collecte ✅
- [x] Architecture Docker complète
- [x] Connexion API Toulouse Open Data
- [x] Pipeline Kafka basique
- [x] Base de données initiale

### Phase 2 : Traitement et Enrichissement
- [ ] Scripts Spark pour métriques
- [ ] Intégration LLM (Hugging Face)
- [ ] NiFi processors personnalisés
- [ ] Associations événements-météo

### Phase 3 : Interface et Recherche
- [ ] Amélioration moteur NLP → SQL
- [ ] Graphiques avancés
- [ ] Export de rapports
- [ ] Système d'alertes

### Phase 4 : Production
- [ ] Tests automatisés
- [ ] CI/CD pipeline
- [ ] Monitoring avancé
- [ ] Documentation API

## 👥 Répartition des Tâches (Exemple)

**Membre 1 - Infrastructure & DevOps**
- Configuration Docker/Kafka/Spark
- Déploiement et monitoring
- Scripts d'automatisation

**Membre 2 - Data Engineering**
- Collecteurs de données
- Pipelines Spark
- Optimisation des performances

**Membre 3 - Machine Learning & LLM**
- Intégration modèles LLM
- Calcul de métriques avancées
- Détection d'anomalies

**Membre 4 - Frontend & UX**
- Interface Streamlit
- Visualisations interactives
- Expérience utilisateur

**Membre 5 - Data Science & Analysis**
- Analyse des corrélations
- Validation des modèles
- Rapport final et présentation

## 📚 Ressources

### Documentation Officielle
- [Toulouse Open Data](https://data.toulouse-metropole.fr/)
- [Apache Kafka](https://kafka.apache.org/documentation/)
- [Apache Spark](https://spark.apache.org/docs/latest/)
- [Streamlit](https://docs.streamlit.io/)

### APIs Météo
- [Météo France](https://meteofrance.com/previsions-meteo-france)
- [OpenWeatherMap](https://openweathermap.org/api)
- [European Centre for Medium-Range Weather Forecasts](https://www.ecmwf.int/)

---

**Note** : Ce projet est une adaptation pédagogique du TP original, utilisant des données météorologiques au lieu de données financières pour démontrer les mêmes concepts techniques.