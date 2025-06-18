import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import re

# =============================================================================
# LLM QUERY TRANSLATOR
# =============================================================================

class MeteoQueryTranslator:
    def __init__(self):
        self.schema_info = {
            "tables": {
                "mesures_meteo": {
                    "columns": ["timestamp", "station", "temperature", "humidite", 
                              "pression", "vitesse_vent", "direction_vent", "precipitation"],
                    "description": "Données météorologiques historiques et temps réel"
                },
                "alertes_meteo": {
                    "columns": ["id", "type_alerte", "niveau", "debut", "fin", "zone"],
                    "description": "Alertes et vigilances météorologiques"
                },
                "metriques_calculees": {
                    "columns": ["timestamp", "station", "temp_moy_7j", "temp_volatilite", 
                              "indice_confort", "tendance"],
                    "description": "Métriques calculées et tendances"
                }
            }
        }
        
    def translate_natural_to_sql(self, question):
        """Traduit une question en langage naturel vers SQL"""
        
        # Patterns de reconnaissance
        patterns = {
            # Températures
            r"température.*([0-9]+).*jours?": self._query_temperature_period,
            r"température.*aujourd'hui|maintenant": self._query_current_temperature,
            r"température.*maximum|minimale?": self._query_temp_extremes,
            
            # Précipitations
            r"pluie|précipitation": self._query_precipitation,
            r"il.*pleut|va pleuvoir": self._query_rain_forecast,
            
            # Vent
            r"vent.*fort|rafale": self._query_strong_wind,
            r"direction.*vent": self._query_wind_direction,
            
            # Tendances
            r"tendance|évolution": self._query_trends,
            r"comparaison|comparer": self._query_comparison,
            
            # Alertes
            r"alerte|vigilance": self._query_alerts,
            
            # Période
            r"cette.*semaine": self._query_this_week,
            r"ce.*mois": self._query_this_month,
        }
        
        for pattern, query_func in patterns.items():
            if re.search(pattern, question.lower()):
                return query_func(question)
                
        # Requête générale par défaut
        return self._query_general(question)
    
    def _query_temperature_period(self, question):
        """Requêtes sur la température sur une période"""
        days = re.search(r"([0-9]+)", question)
        days = int(days.group(1)) if days else 7
        
        return f"""
        SELECT timestamp, temperature, humidite
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-{days} days')
        ORDER BY timestamp DESC
        LIMIT 100;
        """
    
    def _query_current_temperature(self, question):
        """Température actuelle"""
        return """
        SELECT timestamp, temperature, humidite, vitesse_vent, precipitation
        FROM mesures_meteo 
        ORDER BY timestamp DESC 
        LIMIT 1;
        """
    
    def _query_temp_extremes(self, question):
        """Températures extrêmes"""
        return """
        SELECT 
            DATE(timestamp) as date,
            MIN(temperature) as temp_min,
            MAX(temperature) as temp_max,
            AVG(temperature) as temp_moyenne
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date DESC;
        """
    
    def _query_precipitation(self, question):
        """Données de précipitations"""
        return """
        SELECT timestamp, precipitation, humidite
        FROM mesures_meteo 
        WHERE precipitation > 0
        AND timestamp >= datetime('now', '-7 days')
        ORDER BY timestamp DESC;
        """
    
    def _query_strong_wind(self, question):
        """Vents forts"""
        return """
        SELECT timestamp, vitesse_vent, direction_vent, temperature
        FROM mesures_meteo 
        WHERE vitesse_vent > 20
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
    
    def _query_this_week(self, question):
        """Cette semaine"""
        return """
        SELECT 
            DATE(timestamp) as date,
            AVG(temperature) as temp_moy,
            MAX(vitesse_vent) as vent_max,
            SUM(precipitation) as pluie_totale
        FROM mesures_meteo 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY date;
        """
    
    def _query_general(self, question):
        """Requête générale"""
        return """
        SELECT timestamp, temperature, humidite, vitesse_vent, precipitation
        FROM mesures_meteo 
        ORDER BY timestamp DESC 
        LIMIT 50;
        """

# =============================================================================
# DATABASE MANAGER
# =============================================================================

class MeteoDatabaseManager:
    def __init__(self, db_path="meteo_toulouse.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialise la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table mesures météo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesures_meteo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            station TEXT,
            temperature REAL,
            humidite REAL,
            pression REAL,
            vitesse_vent REAL,
            direction_vent REAL,
            precipitation REAL
        )
        """)
        
        # Table alertes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertes_meteo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_alerte TEXT,
            niveau TEXT,
            debut DATETIME,
            fin DATETIME,
            zone TEXT,
            description TEXT
        )
        """)
        
        # Table métriques
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metriques_calculees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            station TEXT,
            temp_moy_7j REAL,
            temp_volatilite REAL,
            indice_confort TEXT,
            tendance TEXT
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
    
    def insert_sample_data(self):
        """Insère des données d'exemple"""
        import random
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Génération de données d'exemple pour les 30 derniers jours
        base_date = datetime.now() - timedelta(days=30)
        
        for i in range(30 * 24):  # 30 jours * 24 heures
            timestamp = base_date + timedelta(hours=i)
            
            # Données réalistes pour Toulouse
            temp = 15 + 10 * (0.5 + 0.3 * np.sin(2 * np.pi * i / (24 * 365))) + random.gauss(0, 3)
            humidity = 50 + 30 * random.random()
            pressure = 1013 + random.gauss(0, 10)
            wind_speed = random.exponential(8)
            wind_dir = random.uniform(0, 360)
            precipitation = random.exponential(0.1) if random.random() < 0.2 else 0
            
            cursor.execute("""
            INSERT INTO mesures_meteo (timestamp, station, temperature, humidite, pression, vitesse_vent, direction_vent, precipitation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, "toulouse_compans_cafarelli", temp, humidity, pressure, wind_speed, wind_dir, precipitation))
        
        conn.commit()
        conn.close()

# =============================================================================
# STREAMLIT INTERFACE
# =============================================================================

def main():
    st.set_page_config(
        page_title="🌤️ Météo Toulouse - Recherche Intelligente",
        page_icon="🌤️",
        layout="wide"
    )
    
    st.title("🌤️ Plateforme d'Analyse Météorologique Toulouse")
    st.markdown("*Recherchez des informations météo en langage naturel*")
    
    # Initialisation
    translator = MeteoQueryTranslator()
    db_manager = MeteoDatabaseManager()
    
    # Sidebar avec exemples de questions
    with st.sidebar:
        st.header("💡 Exemples de questions")
        example_questions = [
            "Quelle est la température maintenant ?",
            "Montre-moi les températures des 7 derniers jours",
            "Quand a-t-il plu cette semaine ?",
            "Y a-t-il eu du vent fort récemment ?",
            "Quelle est la tendance de température ?",
            "Compare les températures de cette semaine",
            "Y a-t-il des alertes météo ?",
            "Température maximale et minimale ce mois"
        ]
        
        for question in example_questions:
            if st.button(question, key=f"example_{hash(question)}"):
                st.session_state.user_question = question
    
    # Interface principale
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Zone de saisie
        user_question = st.text_input(
            "🔍 Posez votre question météo :",
            value=st.session_state.get('user_question', ''),
            placeholder="Ex: Quelle est la température aujourd'hui ?"
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
                    
                    # Graphiques automatiques
                    if 'temperature' in results.columns and 'timestamp' in results.columns:
                        st.subheader("📈 Visualisation")
                        
                        fig = px.line(
                            results, 
                            x='timestamp', 
                            y='temperature',
                            title="Évolution de la température",
                            labels={'temperature': 'Température (°C)', 'timestamp': 'Date/Heure'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Analyse complémentaire
                    if len(results) > 1:
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
                                    "Température min/max", 
                                    f"{results['temperature'].min():.1f}°C / {results['temperature'].max():.1f}°C"
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
        st.subheader("🌟 État actuel")
        
        # Dernières mesures
        latest_query = """
        SELECT temperature, humidite, vitesse_vent, precipitation, timestamp
        FROM mesures_meteo 
        ORDER BY timestamp DESC 
        LIMIT 1
        """
        latest_data = db_manager.execute_query(latest_query)
        
        if not latest_data.empty:
            row = latest_data.iloc[0]
            
            st.metric("🌡️ Température", f"{row['temperature']:.1f}°C")
            st.metric("💧 Humidité", f"{row['humidite']:.0f}%")
            st.metric("💨 Vent", f"{row['vitesse_vent']:.1f} km/h")
            
            if row['precipitation'] > 0:
                st.metric("🌧️ Pluie", f"{row['precipitation']:.1f} mm")
            else:
                st.info("☀️ Pas de précipitations")
        
        # Bouton pour générer des données d'exemple
        if st.button("🎲 Générer données d'exemple"):
            with st.spinner("Génération de données..."):
                db_manager.insert_sample_data()
                st.success("✅ Données d'exemple ajoutées !")
                st.rerun()

if __name__ == "__main__":
    # Import numpy pour les données d'exemple
    import numpy as np
    main()