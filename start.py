#!/usr/bin/env python3
"""
🌤️ Script de démarrage simple pour la plateforme météo Toulouse

Usage:
    python start.py              # Installation + interface
    python start.py --collect    # Collecte de données seulement
    python start.py --docker     # Mode Docker complet
"""

import sys
import subprocess
import time
from pathlib import Path

def print_banner():
    """Affiche la bannière de démarrage"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                🌤️  METEO TOULOUSE PLATFORM                  ║
║                                                              ║
║         Plateforme d'Analyse Météorologique Temps Réel      ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_requirements():
    """Vérifie les prérequis de base"""
    print("🔍 Vérification des prérequis...")
    
    # Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ requis")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Fichiers essentiels
    essential_files = ["main.py", "config.py", "requirements.txt"]
    missing_files = [f for f in essential_files if not Path(f).exists()]
    
    if missing_files:
        print(f"❌ Fichiers manquants: {missing_files}")
        print("📋 Lancez d'abord: python setup.py")
        sys.exit(1)
    
    print("✅ Fichiers essentiels présents")

def quick_install():
    """Installation rapide des dépendances"""
    print("\n📦 Installation des dépendances critiques...")
    
    critical_packages = [
        "requests",
        "pandas", 
        "streamlit",
        "python-dotenv"
    ]
    
    for package in critical_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"📦 Installation de {package}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         capture_output=True)

def collect_data():
    """Collecte rapide de données"""
    print("\n🌤️ Collecte de données météo...")
    
    try:
        # Essayer d'importer et utiliser le collecteur
        sys.path.append(str(Path.cwd()))
        
        # Import simple du collecteur
        from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector
        
        collector = ToulouseMeteoCollector()
        data = collector.get_latest_data(limit=10)
        
        if not data.empty:
            print(f"✅ {len(data)} enregistrements collectés")
            
            # Sauvegarde rapide
            data_dir = Path("data/raw")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"meteo_quick_{int(time.time())}.csv"
            data.to_csv(data_dir / filename, index=False)
            print(f"💾 Sauvegardé: {filename}")
            
            return True
        else:
            print("❌ Aucune donnée collectée")
            return False
            
    except Exception as e:
        print(f"❌ Erreur collecte: {e}")
        print("💡 Vérifiez votre connexion internet")
        return False

def start_streamlit():
    """Lance l'interface Streamlit"""
    print("\n🌐 Lancement de l'interface...")
    
    # Créer un fichier Streamlit minimal si nécessaire
    streamlit_dir = Path("web-interface/streamlit-app")
    streamlit_dir.mkdir(parents=True, exist_ok=True)
    
    streamlit_file = streamlit_dir / "main.py"
    
    if not streamlit_file.exists():
        print("📝 Création de l'interface de base...")
        streamlit_content = '''import streamlit as st
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

st.title("🌤️ Météo Toulouse - Interface de Base")
st.markdown("---")

st.info("""
🚧 **Interface en cours de développement**

Cette interface basique vous permet de démarrer rapidement.
Pour l'interface complète, consultez le fichier `meteo_search_engine` 
dans les artifacts.
""")

# Section test de collecte
st.header("📊 Test de Collecte")

if st.button("🔄 Collecter des données météo"):
    with st.spinner("Collecte en cours..."):
        try:
            from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector
            
            collector = ToulouseMeteoCollector()
            data = collector.get_latest_data(limit=5)
            
            if not data.empty:
                st.success(f"✅ {len(data)} enregistrements collectés !")
                st.dataframe(data)
                
                # Statistiques basiques
                if 'temperature' in data.columns:
                    temp_avg = data['temperature'].mean()
                    if pd.notna(temp_avg):
                        st.metric("🌡️ Température moyenne", f"{temp_avg:.1f}°C")
                
                if 'humidite' in data.columns:
                    hum_avg = data['humidite'].mean()
                    if pd.notna(hum_avg):
                        st.metric("💧 Humidité moyenne", f"{hum_avg:.0f}%")
            else:
                st.error("❌ Aucune donnée collectée")
                
        except Exception as e:
            st.error(f"❌ Erreur: {e}")

# Section configuration
st.header("⚙️ Configuration")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 Fichiers")
    files_status = {
        "config.py": Path("config.py").exists(),
        "requirements.txt": Path("requirements.txt").exists(),
        ".env": Path(".env").exists(),
        "docker-compose.yml": Path("docker-compose.yml").exists()
    }
    
    for file, exists in files_status.items():
        st.write(f"{'✅' if exists else '❌'} {file}")

with col2:
    st.subheader("📦 Modules")
    modules_status = {}
    
    for module in ["requests", "pandas", "streamlit"]:
        try:
            __import__(module)
            modules_status[module] = True
        except ImportError:
            modules_status[module] = False
    
    for module, imported in modules_status.items():
        st.write(f"{'✅' if imported else '❌'} {module}")

# Instructions
st.header("📋 Prochaines Étapes")

st.markdown("""
1. **Collecte de données** : Utilisez le bouton ci-dessus pour tester
2. **Configuration** : Éditez le fichier `.env` si nécessaire
3. **Interface complète** : Copiez le code de l'artifact `meteo_search_engine`
4. **Services complets** : Lancez `python main.py docker up`

**Commandes utiles :**
```bash
# Collecte manuelle
python main.py collect meteo

# Interface complète
python main.py web streamlit

# Services Docker
python main.py docker up
```
""")

import pandas as pd
'''
        
        with open(streamlit_file, "w", encoding="utf-8") as f:
            f.write(streamlit_content)
    
    # Lancer Streamlit
    try:
        print("🚀 Ouverture de l'interface sur http://localhost:8501")
        print("⏹️  Ctrl+C pour arrêter")
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(streamlit_file),
            "--server.address", "localhost",
            "--server.port", "8501"
        ])
        
    except KeyboardInterrupt:
        print("\n👋 Interface fermée")
    except FileNotFoundError:
        print("❌ Streamlit non installé")
        print("📦 Installation: pip install streamlit")
    except Exception as e:
        print(f"❌ Erreur Streamlit: {e}")

def start_docker():
    """Lance l'environnement Docker complet"""
    print("\n🐳 Lancement de l'environnement Docker...")
    
    if not Path("docker-compose.yml").exists():
        print("❌ docker-compose.yml non trouvé")
        print("📋 Lancez d'abord: python setup.py")
        return False
    
    try:
        # Vérifier Docker
        result = subprocess.run(["docker", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker non disponible")
            return False
        
        print("🐳 Démarrage des services...")
        result = subprocess.run(["docker-compose", "up", "-d"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Services Docker lancés")
            print("\n🌐 Services disponibles:")
            print("  • Interface principale: http://localhost:8501")
            print("  • Kafka UI:             http://localhost:8085")
            print("  • PgAdmin:              http://localhost:5050")
            print("  • Mongo Express:        http://localhost:8081")
            
            # Attendre que les services soient prêts
            print("\n⏳ Attente du démarrage des services...")
            time.sleep(10)
            
            # Initialiser les bases de données
            print("🗄️ Initialisation des bases de données...")
            subprocess.run([sys.executable, "main.py", "db", "init"], 
                         capture_output=True)
            
            return True
        else:
            print(f"❌ Erreur Docker: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ Docker ou Docker Compose non installé")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    """Fonction principale"""
    print_banner()
    
    # Analyser les arguments
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print("""
Usage:
    python start.py              # Installation + interface
    python start.py --collect    # Collecte de données seulement
    python start.py --docker     # Mode Docker complet
    python start.py --quick      # Démarrage ultra-rapide
    
Options:
    --help, -h     Affiche cette aide
    --collect      Collecte des données et arrête
    --docker       Lance l'environnement Docker complet
    --quick        Démarrage minimal (interface seulement)
""")
        return
    
    try:
        # Mode collecte uniquement
        if "--collect" in args:
            check_requirements()
            quick_install()
            collect_data()
            print("\n✅ Collecte terminée")
            return
        
        # Mode Docker complet
        if "--docker" in args:
            check_requirements()
            if start_docker():
                print("\n🎉 Environnement Docker prêt !")
                print("👀 Consultez http://localhost:8501 pour l'interface")
            else:
                print("\n❌ Problème avec Docker, mode local...")
                main_flow()
            return
        
        # Mode quick (minimal)
        if "--quick" in args:
            print("🚀 Démarrage ultra-rapide...")
            quick_install()
            start_streamlit()
            return
        
        # Mode normal (par défaut)
        main_flow()
        
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")

def main_flow():
    """Flux principal de démarrage"""
    # Vérifications
    check_requirements()
    
    # Installation rapide
    quick_install()
    
    # Collecte de données
    print("\n🎯 Collecte initiale de données...")
    data_collected = collect_data()
    
    if not data_collected:
        print("⚠️  Continuons sans données initiales...")
    
    # Proposition de choix
    print("\n🚀 Choisissez votre mode de démarrage:")
    print("  1. Interface Streamlit (recommandé)")
    print("  2. Environnement Docker complet")
    print("  3. Collecte de données seulement")
    print("  4. Configuration manuelle")
    
    try:
        choice = input("\nVotre choix (1-4) [1]: ").strip() or "1"
        
        if choice == "1":
            start_streamlit()
        elif choice == "2":
            start_docker()
        elif choice == "3":
            collect_data()
            print("✅ Collecte terminée")
        elif choice == "4":
            print("\n📋 Configuration manuelle:")
            print("  • Éditez .env pour vos paramètres")
            print("  • Lancez: python main.py --help")
            print("  • Consultez: QUICK_START.md")
        else:
            print("❌ Choix invalide")
            
    except EOFError:
        # Mode automatique si pas d'entrée (script)
        start_streamlit()

if __name__ == "__main__":
    main()