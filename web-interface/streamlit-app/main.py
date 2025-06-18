import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import re
import sys
from pathlib import Path
import numpy as np

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

# Configuration par défaut si modules non disponibles
class DatabaseConfig:
    SQLITE_PATH = "meteo_toulouse.db"

# =============================================================================
# LLM QUERY TRANSLATOR - Adapté pour les nouvelles données
# =============================================================================

class MeteoQueryTranslator:
    def __init__(self):
        self.schema_info = {
            "tables": {
                "mesures_meteo": {
                    "columns": ["timestamp", "station", "temperature", "humidite", 
                              "pression", "vitesse_vent", "direction_vent", "precipitation",
                              "station_name"],
                    "description": "Données météorologiques de Toulouse (Compans Caffarelli et Météopole)"
                },
                "alertes_meteo": {
                    "columns": ["id", "type_alerte", "niveau", "debut", "fin", "zone"],
                    "description": "Alertes et vigilances météorologiques"
                },
                "metriques_calculees": {
                    "columns": ["timestamp", "station", "temp_moy_7j", "temp_volatilite", 
                              "indice_confort", "tendance"],
                    "description": "Métriques calculées par Spark"
                }
            }
        }
        
    def translate_natural_to_sql(self, question):
        """Traduit une question en langage naturel vers SQL"""
        
        # Patterns de reconnaissance adaptés aux stations Toulouse
        patterns = {
            # Températures
            r"température.*([0-9]+).*jours?": self._query_temperature_period,
            r"température.*aujourd'hui|maintenant|actuelle": self._query_current_temperature,
            r"température.*maximum|minimale?|extrême": self._query_temp_extremes,
            r"température.*compans|caffarelli": self._query_temperature_compans,
            r"température.*méteopole": self._query_temperature_meteopole,
            
            # Précipitations
            r"pluie|précipitation": self._query_precipitation,
            r"il.*pleut|va pleuvoir": self._query_rain_forecast,
            
            # Vent
            r"vent.*fort|rafale": self._query_strong_wind,
            r"direction.*vent": self._query_wind_direction,
            
            # Comparaisons entre stations
            r"compar.*station|différence.*station": self._query_station_comparison,
            r"quelle.*station.*plus|moins": self._query_station_ranking,
            
            # Tendances
            r"tendance|évolution": self._query_trends,
            r"comparaison|comparer": self._query_comparison,
            
            # Alertes
            r"alerte|vigilance": self._query_alerts,
            
            # Période
            r"cette.*semaine": self._query_this_week,
            r"ce.*mois": self._query_this_month,
            r"hier": self._query_yesterday,
        }
        
        for pattern, query_func in patterns.items():
            if re.search(pattern, question.lower()):
                return query_func(question)
                
        # Requête générale par défaut
        return self._query_general(question)
    
    def _query_current_temperature(self, question):
        """Température actuelle des deux stations"""
        return """
        SELECT 
            station_name,
            temperature,
            humidite,
            vitesse_vent,
            timestamp
        FROM mesures_meteo 
        WHERE timestamp = (
            SELECT MAX(timestamp) FROM mesures_meteo
        )
        ORDER BY station_name;
        """
    
    def _query_temperature_compans(self, question):
        """Température spécifique à Compans Caffarelli"""
        return """
        SELECT timestamp, temperature, humidite, vitesse_vent
        FROM mesures_meteo 
        WHERE station = 'toulouse_compans_cafarelli'
        ORDER BY timestamp DESC 
        LIMIT 24;
        """
    
    def _query_temperature_meteopole(self, question):
        """Température spécifique à Météopole"""
        return """
        SELECT timestamp, temperature, humidite, vitesse_vent
        FROM mesures_meteo 
        WHERE station = 'toulouse_meteopole'
        ORDER BY timestamp DESC 
        LIMIT 24;
        """
    
    def _query_station_comparison(self, question):
        """Comparaison entre les stations"""
        return """
        SELECT 
            station_name,
            AVG(temperature) as temp_moyenne,
            AVG(humidite) as humidite_moyenne,
            AVG(vitesse_vent) as vent_moyen,
            COUNT(*) as nb_mesures
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY station_name, station
        ORDER BY temp_moyenne DESC;
        """
    
    def _query_station_ranking(self, question):
        """Classement des stations"""
        if "plus chaud" in question.lower() or "plus chaude" in question.lower():
            order = "DESC"
            metric = "temperature"
        elif "plus froid" in question.lower() or "plus froide" in question.lower():
            order = "ASC"
            metric = "temperature"
        elif "plus humide" in question.lower():
            order = "DESC"
            metric = "humidite"
        elif "plus venteux" in question.lower() or "plus de vent" in question.lower():
            order = "DESC"
            metric = "vitesse_vent"
        else:
            order = "DESC"
            metric = "temperature"
        
        return f"""
        SELECT 
            station_name,
            AVG({metric}) as valeur_moyenne,
            MAX({metric}) as valeur_max,
            MIN({metric}) as valeur_min
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY station_name, station
        ORDER BY valeur_moyenne {order};
        """
    
    def _query_temperature_period(self, question):
        """Requêtes sur la température sur une période"""
        days = re.search(r"([0-9]+)", question)
        days = int(days.group(1)) if days else 7
        
        return f"""
        SELECT 
            timestamp, 
            station_name,
            temperature, 
            humidite
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-{days} days')
        ORDER BY timestamp DESC
        LIMIT 100;
        """
    
    def _query_temp_extremes(self, question):
        """Températures extrêmes par station"""
        return """
        SELECT 
            DATE(timestamp) as date,
            station_name,
            MIN(temperature) as temp_min,
            MAX(temperature) as temp_max,
            AVG(temperature) as temp_moyenne
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp), station_name, station
        ORDER BY date DESC, station_name;
        """
    
    def _query_precipitation(self, question):
        """Données de précipitations par station"""
        return """
        SELECT 
            timestamp, 
            station_name,
            precipitation, 
            humidite,
            temperature
        FROM mesures_meteo 
        WHERE precipitation > 0
        AND timestamp >= datetime('now', '-7 days')
        ORDER BY timestamp DESC;
        """
    
    def _query_strong_wind(self, question):
        """Vents forts par station"""
        return """
        SELECT 
            timestamp, 
            station_name,
            vitesse_vent, 
            direction_vent, 
            temperature
        FROM mesures_meteo 
        WHERE vitesse_vent > 15
        AND timestamp >= datetime('now', '-7 days')
        ORDER BY vitesse_vent DESC;
        """
    
    def _query_wind_direction(self, question):
        """Direction du vent"""
        return """
        SELECT timestamp, direction_vent, vitesse_vent
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-24 hours')
        ORDER BY timestamp DESC;
        """
    
    def _query_trends(self, question):
        """Tendances météorologiques"""
        return """
        SELECT timestamp, temp_moy_7j, temp_volatilite, indice_confort
        FROM metriques_calculees 
        WHERE timestamp >= datetime('now', '-30 days')
        ORDER BY timestamp DESC;
        """
    
    def _query_alerts(self, question):
        """Alertes météo"""
        return """
        SELECT type_alerte, niveau, debut, fin, zone
        FROM alertes_meteo 
        WHERE fin >= datetime('now')
        ORDER BY debut DESC;
        """
    
    def _query_yesterday(self, question):
        """Données d'hier"""
        return """
        SELECT 
            DATE(timestamp) as date,
            station_name,
            AVG(temperature) as temp_moyenne,
            MAX(temperature) as temp_max,
            MIN(temperature) as temp_min,
            AVG(humidite) as humidite_moyenne,
            SUM(precipitation) as pluie_totale
        FROM mesures_meteo 
        WHERE DATE(timestamp) = DATE('now', '-1 day')
        GROUP BY DATE(timestamp), station_name, station
        ORDER BY station_name;
        """
    
    def _query_this_week(self, question):
        """Cette semaine par station"""
        return """
        SELECT 
            DATE(timestamp) as date,
            station_name,
            AVG(temperature) as temp_moy,
            MAX(vitesse_vent) as vent_max,
            SUM(precipitation) as pluie_totale
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY DATE(timestamp), station_name, station
        ORDER BY date, station_name;
        """
    
    def _query_this_month(self, question):
        """Ce mois par station"""
        return """
        SELECT 
            DATE(timestamp) as date,
            station_name,
            AVG(temperature) as temp_moy,
            MAX(vitesse_vent) as vent_max,
            SUM(precipitation) as pluie_totale
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp), station_name, station
        ORDER BY date, station_name;
        """
    
    def _query_rain_forecast(self, question):
        """Prévision de pluie"""
        return """
        SELECT 
            timestamp, 
            station_name,
            precipitation, 
            humidite,
            temperature
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-24 hours')
        ORDER BY timestamp DESC;
        """
    
    def _query_comparison(self, question):
        """Comparaison générale"""
        return """
        SELECT 
            station_name,
            AVG(temperature) as temp_moyenne,
            AVG(humidite) as humidite_moyenne,
            AVG(vitesse_vent) as vent_moyen
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY station_name, station
        ORDER BY temp_moyenne DESC;
        """
    
    def _query_general(self, question):
        """Requête générale avec les deux stations"""
        return """
        SELECT 
            timestamp, 
            station_name,
            temperature, 
            humidite, 
            vitesse_vent, 
            precipitation
        FROM mesures_meteo 
        ORDER BY timestamp DESC 
        LIMIT 50;
        """

# =============================================================================
# DATABASE MANAGER - Adapté pour les nouvelles données
# =============================================================================

class MeteoDatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            try:
                db_path = DatabaseConfig.SQLITE_PATH
            except:
                db_path = "meteo_toulouse.db"
        
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialise la base de données avec le nouveau schéma"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table mesures météo adaptée aux nouvelles données
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesures_meteo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            station TEXT,
            station_name TEXT,
            temperature REAL,
            humidite REAL,
            pression REAL,
            vitesse_vent REAL,
            direction_vent REAL,
            precipitation REAL,
            rafale_max REAL,
            pluie_intensite_max REAL,
            station_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, station)
        )
        """)
        
        # Index pour performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON mesures_meteo(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station ON mesures_meteo(station)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_timestamp ON mesures_meteo(station, timestamp)")
        
        # Table alertes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertes_meteo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_alerte TEXT,
            niveau TEXT,
            debut DATETIME,
            fin DATETIME,
            zone TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Table métriques calculées (compatibles avec Spark)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metriques_calculees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            station TEXT,
            temp_moy_7j REAL,
            temp_moy_30j REAL,
            temp_volatilite_7j REAL,
            temp_volatilite_30j REAL,
            temp_tendance_24h REAL,
            indice_confort TEXT,
            risque_precipitation TEXT,
            temperature_ressentie REAL,
            score_anomalie_temp REAL,
            score_anomalie_vent REAL,
            score_anomalie_pression REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(timestamp, station)
        )
        """)
        
        conn.commit()
        conn.close()
        
    def execute_query(self, query):
        """Exécute une requête SQL"""
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"Erreur lors de l'exécution de la requête: {e}")
            return pd.DataFrame()
    
    def insert_meteo_data(self, data):
        """Insère des données météo dans la base"""
        if data.empty:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Insérer en ignorant les doublons
            inserted = data.to_sql('mesures_meteo', conn, if_exists='append', index=False)
            conn.commit()
            return len(data)
        except Exception as e:
            st.error(f"Erreur insertion: {e}")
            return 0
        finally:
            conn.close()
    
    def get_latest_data_from_db(self):
        """Récupère les dernières données de la base"""
        query = """
        SELECT * FROM mesures_meteo 
        ORDER BY timestamp DESC 
        LIMIT 100
        """
        return self.execute_query(query)
    
    def insert_sample_data(self):
        """Insère des données d'exemple réalistes pour Toulouse"""
        import random
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Générer des données pour les deux stations
        stations = [
            ('toulouse_compans_cafarelli', 'Station Météo Toulouse - Parc Compans Caffarelli'),
            ('toulouse_meteopole', 'Météopole')
        ]
        
        base_date = datetime.now() - timedelta(days=7)
        
        for station_id, station_name in stations:
            for i in range(7 * 24):  # 7 jours * 24 heures
                timestamp = base_date + timedelta(hours=i)
                
                # Données réalistes pour Toulouse avec légères variations entre stations
                base_temp = 15 + 10 * np.sin(2 * np.pi * i / (24 * 365))
                station_offset = 1 if 'compans' in station_id else 0  # Compans légèrement plus chaud
                
                temp = base_temp + station_offset + random.gauss(0, 2)
                humidity = 50 + 30 * random.random()
                pressure = 1013 + random.gauss(0, 8)
                wind_speed = random.expovariate(1 / 6)  # mean = 6
                wind_dir = random.uniform(0, 360)
                precipitation = random.expovariate(1 / 0.1) if random.random() < 0.15 else 0  # mean = 0.1
                
                cursor.execute("""
                INSERT OR IGNORE INTO mesures_meteo 
                (timestamp, station, station_name, temperature, humidite, pression, 
                 vitesse_vent, direction_vent, precipitation, station_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, station_id, station_name, temp, humidity, pressure,
                    wind_speed, wind_dir, precipitation, 'ISS'
                ))
        
        conn.commit()
        conn.close()

# =============================================================================
# STREAMLIT INTERFACE ADAPTÉE
# =============================================================================

def main():
    st.set_page_config(
        page_title="🌤️ Météo Toulouse - Analyse Multi-Stations",
        page_icon="🌤️",
        layout="wide"
    )
    
    st.title("🌤️ Plateforme d'Analyse Météorologique Toulouse")
    st.markdown("*Recherchez des informations météo en langage naturel - Données de Compans Caffarelli et Météopole*")
    
    # Initialisation
    translator = MeteoQueryTranslator()
    db_manager = MeteoDatabaseManager()
    
    # Sidebar avec exemples et collecte
    with st.sidebar:
        st.header("💡 Exemples de questions")
        example_questions = [
            "Quelle est la température maintenant ?",
            "Compare les deux stations météo",
            "Quelle station est la plus chaude ?",
            "Température à Compans Caffarelli aujourd'hui",
            "Données de Météopole cette semaine",
            "Y a-t-il eu de la pluie récemment ?",
            "Vent fort dans les deux stations ?",
            "Tendance de température hier",
            "Différence entre les stations",
            "Température maximale ce mois"
        ]
        
        for question in example_questions:
            if st.button(question, key=f"example_{hash(question)}"):
                st.session_state.user_question = question
        
        st.markdown("---")
        
        # Section collecte de données en temps réel (optionnelle si modules disponibles)
        st.header("🔄 Données d'Exemple")
        
        if st.button("🎲 Générer données d'exemple"):
            with st.spinner("Génération de données..."):
                db_manager.insert_sample_data()
                st.success("✅ Données d'exemple ajoutées !")
                st.rerun()
    
    # Interface principale
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Zone de saisie
        user_question = st.text_input(
            "🔍 Posez votre question météo :",
            value=st.session_state.get('user_question', ''),
            placeholder="Ex: Compare la température entre les deux stations"
        )
        
        if st.button("🚀 Rechercher", type="primary") and user_question:
            with st.spinner("Analyse de votre question..."):
                # Traduction en SQL
                sql_query = translator.translate_natural_to_sql(user_question)
                
                # Affichage de la requête générée
                with st.expander("🔧 Requête SQL générée"):
                    st.code(sql_query, language="sql")
                
                # Exécution et affichage des résultats
                results = db_manager.execute_query(sql_query)
                
                if not results.empty:
                    st.success(f"✅ {len(results)} résultats trouvés")
                    
                    # Affichage des données
                    st.subheader("📊 Résultats")
                    st.dataframe(results, use_container_width=True)
                    
                    # Graphiques automatiques adaptés aux stations
                    if 'temperature' in results.columns and 'timestamp' in results.columns:
                        st.subheader("📈 Visualisation")
                        
                        if 'station_name' in results.columns:
                            # Graphique par station
                            fig = px.line(
                                results, 
                                x='timestamp', 
                                y='temperature',
                                color='station_name',
                                title="Évolution de la température par station",
                                labels={'temperature': 'Température (°C)', 
                                       'timestamp': 'Date/Heure',
                                       'station_name': 'Station'}
                            )
                        else:
                            # Graphique simple
                            fig = px.line(
                                results, 
                                x='timestamp', 
                                y='temperature',
                                title="Évolution de la température",
                                labels={'temperature': 'Température (°C)', 'timestamp': 'Date/Heure'}
                            )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Analyse complémentaire pour plusieurs stations
                    if len(results) > 1 and 'station_name' in results.columns:
                        st.subheader("🔍 Analyse Comparative")
                        
                        if 'temperature' in results.columns:
                            # Statistiques par station
                            stats_by_station = results.groupby('station_name').agg({
                                'temperature': ['mean', 'min', 'max', 'std']
                            }).round(2)
                            
                            st.write("**Statistiques de température par station :**")
                            st.dataframe(stats_by_station)
                            
                            # Graphique de comparaison
                            if len(results.groupby('station_name')) == 2:
                                fig_box = px.box(
                                    results,
                                    x='station_name',
                                    y='temperature',
                                    title="Distribution des températures par station"
                                )
                                st.plotly_chart(fig_box, use_container_width=True)
                    
                    # Statistiques générales
                    elif len(results) > 1:
                        st.subheader("🧮 Statistiques")
                        stats_col1, stats_col2, stats_col3 = st.columns(3)
                        
                        if 'temperature' in results.columns:
                            with stats_col1:
                                st.metric(
                                    "Température moyenne", 
                                    f"{results['temperature'].mean():.1f}°C"
                                )
                            with stats_col2:
                                st.metric(
                                    "Amplitude", 
                                    f"{results['temperature'].max() - results['temperature'].min():.1f}°C"
                                )
                        
                        if 'humidite' in results.columns:
                            with stats_col3:
                                st.metric(
                                    "Humidité moyenne", 
                                    f"{results['humidite'].mean():.0f}%"
                                )
                else:
                    st.warning("❌ Aucun résultat trouvé pour cette question.")
    
    with col2:
        st.subheader("🌟 État Actuel")
        
        # Dernières mesures par station
        latest_query = """
        SELECT 
            station_name,
            temperature,
            humidite,
            vitesse_vent,
            precipitation,
            timestamp
        FROM mesures_meteo 
        WHERE timestamp = (SELECT MAX(timestamp) FROM mesures_meteo)
        ORDER BY station_name
        """
        latest_data = db_manager.execute_query(latest_query)
        
        if not latest_data.empty:
            for _, row in latest_data.iterrows():
                st.markdown(f"**{row['station_name']}**")
                
                col_temp, col_hum = st.columns(2)
                with col_temp:
                    if pd.notna(row['temperature']):
                        st.metric("🌡️ Température", f"{row['temperature']:.1f}°C")
                with col_hum:
                    if pd.notna(row['humidite']):
                        st.metric("💧 Humidité", f"{row['humidite']:.0f}%")
                
                if pd.notna(row['vitesse_vent']):
                    st.metric("💨 Vent", f"{row['vitesse_vent']:.1f} km/h")
                
                if pd.notna(row['precipitation']) and row['precipitation'] > 0:
                    st.metric("🌧️ Pluie", f"{row['precipitation']:.1f} mm")
                
                st.markdown("---")
        
        # Comparaison rapide des stations
        st.subheader("⚖️ Comparaison Rapide")
        
        comparison_query = """
        SELECT 
            station_name,
            AVG(temperature) as temp_moy,
            AVG(humidite) as hum_moy,
            COUNT(*) as nb_mesures
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY station_name, station
        ORDER BY temp_moy DESC
        """
        
        comparison_data = db_manager.execute_query(comparison_query)
        
        if not comparison_data.empty:
            for _, row in comparison_data.iterrows():
                st.write(f"**{row['station_name']}**")
                st.write(f"• Temp: {row['temp_moy']:.1f}°C")
                st.write(f"• Humidité: {row['hum_moy']:.0f}%")
                st.write(f"• Mesures: {row['nb_mesures']}")
                st.write("")
        else:
            st.info("Aucune donnée disponible. Cliquez sur 'Générer données d'exemple' dans la barre latérale.")

if __name__ == "__main__":
    main()