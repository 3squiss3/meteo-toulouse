"""
Traitement Spark pour les données météorologiques
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window
import json
import logging
from config import SparkConfig, KafkaConfig, DatabaseConfig

logger = logging.getLogger(__name__)

class MeteoSparkProcessor:
    """Processeur Spark pour les données météorologiques"""
    
    def __init__(self):
        self.spark = self._create_spark_session()
        self.spark.sparkContext.setLogLevel("WARN")
        
    def _create_spark_session(self):
        """Crée une session Spark avec la configuration appropriée"""
        builder = SparkSession.builder \
            .appName(SparkConfig.APP_NAME) \
            .config("spark.executor.memory", SparkConfig.EXECUTOR_MEMORY) \
            .config("spark.driver.memory", SparkConfig.DRIVER_MEMORY) \
            .config("spark.executor.cores", SparkConfig.EXECUTOR_CORES) \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        
        # Configuration pour Kafka
        builder = builder.config("spark.jars.packages", 
                                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0")
        
        # Configuration pour PostgreSQL
        builder = builder.config("spark.jars.packages", 
                                "org.postgresql:postgresql:42.6.0")
        
        if SparkConfig.MASTER_URL:
            builder = builder.master(SparkConfig.MASTER_URL)
        
        return builder.getOrCreate()
    
    def calculate_meteo_metrics(self, df):
        """Calcule les métriques météorologiques avancées"""
        
        # Fenêtres pour les calculs temporels
        window_7d = Window.partitionBy("station").orderBy("timestamp").rowsBetween(-168, 0)  # 7 jours
        window_24h = Window.partitionBy("station").orderBy("timestamp").rowsBetween(-24, 0)   # 24h
        window_30d = Window.partitionBy("station").orderBy("timestamp").rowsBetween(-720, 0)  # 30 jours
        
        # Calculs des métriques
        metrics_df = df.withColumn(
            # Moyennes mobiles
            "temp_moy_7j", avg("temperature").over(window_7d)
        ).withColumn(
            "temp_moy_30j", avg("temperature").over(window_30d)
        ).withColumn(
            # Volatilité (écart-type)
            "temp_volatilite_7j", stddev("temperature").over(window_7d)
        ).withColumn(
            "temp_volatilite_30j", stddev("temperature").over(window_30d)
        ).withColumn(
            # Tendance (différence avec la valeur d'il y a 24h)
            "temp_tendance_24h", 
            col("temperature") - lag("temperature", 24).over(window_24h)
        ).withColumn(
            # Indice de confort basé sur température et humidité
            "indice_confort",
            when((col("temperature").between(18, 24)) & (col("humidite").between(40, 60)), "optimal")
            .when(col("temperature") > 30, "trop_chaud")
            .when((col("temperature") > 25) & (col("humidite") > 70), "chaud_humide")
            .when(col("temperature") < 5, "tres_froid")
            .when(col("temperature") < 10, "froid")
            .when(col("humidite") > 80, "tres_humide")
            .when(col("humidite") < 30, "sec")
            .otherwise("modere")
        ).withColumn(
            # Risque de précipitation basé sur humidité et pression
            "risque_precipitation",
            when((col("humidite") > 80) & (col("pression") < 101000), "eleve")
            .when(col("humidite") > 70, "modere")
            .when(col("humidite") > 60, "faible")
            .otherwise("tres_faible")
        ).withColumn(
            # Température ressentie (Wind Chill / Heat Index simplifié)
            "temperature_ressentie",
            when(col("temperature") < 10, 
                 col("temperature") - (col("vitesse_vent") * 0.5))
            .when(col("temperature") > 25,
                 col("temperature") + ((col("humidite") - 50) * 0.1))
            .otherwise(col("temperature"))
        )
        
        return metrics_df
    
    def detect_weather_anomalies(self, df):
        """Détecte les anomalies météorologiques"""
        
        # Calcul des percentiles pour déterminer les seuils d'anomalie
        percentiles = df.select(
            expr("percentile_approx(temperature, 0.05)").alias("temp_p5"),
            expr("percentile_approx(temperature, 0.95)").alias("temp_p95"),
            expr("percentile_approx(vitesse_vent, 0.95)").alias("vent_p95"),
            expr("percentile_approx(pression, 0.05)").alias("pression_p5"),
            expr("percentile_approx(pression, 0.95)").alias("pression_p95")
        ).collect()[0]
        
        # Détection des anomalies
        anomalies_df = df.withColumn(
            "anomalie_temperature",
            when((col("temperature") < percentiles["temp_p5"]) | 
                 (col("temperature") > percentiles["temp_p95"]), lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "score_anomalie_temp",
            when(col("temperature") < percentiles["temp_p5"],
                 (lit(percentiles["temp_p5"]) - col("temperature")) / lit(percentiles["temp_p5"]))
            .when(col("temperature") > percentiles["temp_p95"],
                 (col("temperature") - lit(percentiles["temp_p95"])) / lit(percentiles["temp_p95"]))
            .otherwise(lit(0.0))
        ).withColumn(
            "anomalie_vent",
            when(col("vitesse_vent") > percentiles["vent_p95"], lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "score_anomalie_vent",
            when(col("vitesse_vent") > percentiles["vent_p95"],
                 (col("vitesse_vent") - lit(percentiles["vent_p95"])) / lit(percentiles["vent_p95"]))
            .otherwise(lit(0.0))
        ).withColumn(
            "anomalie_pression",
            when((col("pression") < percentiles["pression_p5"]) | 
                 (col("pression") > percentiles["pression_p95"]), lit(True))
            .otherwise(lit(False))
        ).withColumn(
            "score_anomalie_pression",
            when(col("pression") < percentiles["pression_p5"],
                 (lit(percentiles["pression_p5"]) - col("pression")) / lit(percentiles["pression_p5"]))
            .when(col("pression") > percentiles["pression_p95"],
                 (col("pression") - lit(percentiles["pression_p95"])) / lit(percentiles["pression_p95"]))
            .otherwise(lit(0.0))
        )
        
        return anomalies_df
    
    def process_batch_data(self, input_path, output_path):
        """Traite les données par batch"""
        logger.info(f"Traitement batch: {input_path} -> {output_path}")
        
        # Schéma des données météo
        meteo_schema = StructType([
            StructField("timestamp", TimestampType(), True),
            StructField("station", StringType(), True),
            StructField("temperature", DoubleType(), True),
            StructField("humidite", DoubleType(), True),
            StructField("pression", DoubleType(), True),
            StructField("vitesse_vent", DoubleType(), True),
            StructField("direction_vent", DoubleType(), True),
            StructField("precipitation", DoubleType(), True)
        ])
        
        # Lecture des données
        df = self.spark.read \
            .option("header", "true") \
            .schema(meteo_schema) \
            .csv(input_path)
        
        # Nettoyage des données
        df_clean = df.filter(col("temperature").isNotNull()) \
                    .filter(col("timestamp").isNotNull()) \
                    .filter(col("station").isNotNull())
        
        # Calcul des métriques
        df_with_metrics = self.calculate_meteo_metrics(df_clean)
        
        # Détection d'anomalies
        df_with_anomalies = self.detect_weather_anomalies(df_with_metrics)
        
        # Sauvegarde
        df_with_anomalies.coalesce(1) \
            .write \
            .mode("overwrite") \
            .option("header", "true") \
            .csv(output_path)
        
        logger.info(f"Traitement terminé: {df_with_anomalies.count()} enregistrements")
        
        return df_with_anomalies
    
    def process_streaming_data(self, kafka_servers=None):
        """Traite les données en streaming depuis Kafka"""
        if not kafka_servers:
            kafka_servers = ",".join(KafkaConfig.BOOTSTRAP_SERVERS)
        
        logger.info(f"Démarrage streaming Kafka: {kafka_servers}")
        
        # Configuration de lecture Kafka
        kafka_df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_servers) \
            .option("subscribe", KafkaConfig.TOPIC_METEO_TEMPS_REEL) \
            .option("startingOffsets", "latest") \
            .load()
        
        # Schéma des messages JSON
        meteo_schema = StructType([
            StructField("station", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("temperature", DoubleType(), True),
            StructField("humidite", DoubleType(), True),
            StructField("pression", DoubleType(), True),
            StructField("vitesse_vent", DoubleType(), True),
            StructField("direction_vent", DoubleType(), True),
            StructField("precipitation", DoubleType(), True)
        ])
        
        # Parsing des messages JSON
        parsed_df = kafka_df.select(
            from_json(col("value").cast("string"), meteo_schema).alias("data"),
            col("timestamp").alias("kafka_timestamp")
        ).select("data.*", "kafka_timestamp") \
         .withColumn("timestamp", to_timestamp(col("timestamp")))
        
        # Calcul des métriques en streaming
        enriched_df = self.calculate_meteo_metrics(parsed_df)
        
        # Écriture vers la console (pour debug)
        console_query = enriched_df.writeStream \
            .outputMode("append") \
            .format("console") \
            .option("truncate", False) \
            .trigger(processingTime=f'{SparkConfig.BATCH_INTERVAL} seconds') \
            .start()
        
        return console_query
    
    def save_to_postgresql(self, df, table_name):
        """Sauvegarde vers PostgreSQL"""
        logger.info(f"Sauvegarde vers PostgreSQL: {table_name}")
        
        df.write \
            .format("jdbc") \
            .option("url", DatabaseConfig.POSTGRES_URL) \
            .option("dbtable", table_name) \
            .option("user", DatabaseConfig.POSTGRES_USER) \
            .option("password", DatabaseConfig.POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
    
    def create_weather_summary(self, df):
        """Crée un résumé météorologique quotidien"""
        
        daily_summary = df.withColumn("date", date_format(col("timestamp"), "yyyy-MM-dd")) \
            .groupBy("station", "date") \
            .agg(
                count("*").alias("nb_mesures"),
                avg("temperature").alias("temp_moyenne"),
                min("temperature").alias("temp_min"),
                max("temperature").alias("temp_max"),
                stddev("temperature").alias("temp_volatilite"),
                avg("humidite").alias("humidite_moyenne"),
                min("humidite").alias("humidite_min"),
                max("humidite").alias("humidite_max"),
                avg("pression").alias("pression_moyenne"),
                min("pression").alias("pression_min"),
                max("pression").alias("pression_max"),
                sum("precipitation").alias("precipitation_totale"),
                avg("vitesse_vent").alias("vent_moyen"),
                max("vitesse_vent").alias("vent_max"),
                # Nombre d'anomalies si les colonnes existent
                sum(when(col("anomalie_temperature"), 1).otherwise(0)).alias("nb_anomalies_temp"),
                sum(when(col("anomalie_vent"), 1).otherwise(0)).alias("nb_anomalies_vent"),
                sum(when(col("anomalie_pression"), 1).otherwise(0)).alias("nb_anomalies_pression")
            ) \
            .orderBy("station", "date")
        
        return daily_summary
    
    def stop(self):
        """Arrête la session Spark"""
        if self.spark:
            self.spark.stop()
            logger.info("Session Spark fermée")

# Fonctions utilitaires
def run_batch_processing(input_path, output_path):
    """Lance un traitement batch"""
    processor = MeteoSparkProcessor()
    try:
        result = processor.process_batch_data(input_path, output_path)
        return result
    finally:
        processor.stop()

def run_streaming_processing():
    """Lance un traitement streaming"""
    processor = MeteoSparkProcessor()
    try:
        query = processor.process_streaming_data()
        query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Arrêt du streaming demandé")
    finally:
        processor.stop()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Processeur Spark pour données météo")
    parser.add_argument("--mode", choices=["batch", "streaming"], default="batch",
                       help="Mode de traitement")
    parser.add_argument("--input", help="Chemin d'entrée pour le mode batch")
    parser.add_argument("--output", help="Chemin de sortie pour le mode batch")
    
    args = parser.parse_args()
    
    if args.mode == "batch":
        if not args.input or not args.output:
            print("Mode batch requiert --input et --output")
            sys.exit(1)
        run_batch_processing(args.input, args.output)
    else:
        run_streaming_processing()