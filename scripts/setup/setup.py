#!/usr/bin/env python3
"""
Script d'installation automatique pour la plateforme météo Toulouse
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Couleurs pour l'affichage
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def print_colored(message, color=Colors.GREEN):
    print(f"{color}{message}{Colors.ENDC}")

def print_step(step, message):
    print_colored(f"\n📋 Étape {step}: {message}", Colors.BLUE + Colors.BOLD)

def check_python_version():
    """Vérifie la version de Python"""
    version = sys.version_info
    if version < (3, 8):
        print_colored("❌ Python 3.8+ requis", Colors.RED)
        print_colored(f"Version actuelle: {version.major}.{version.minor}", Colors.RED)
        sys.exit(1)
    
    print_colored(f"✅ Python {version.major}.{version.minor}.{version.micro}", Colors.GREEN)

def check_command_exists(command):
    """Vérifie si une commande existe"""
    return shutil.which(command) is not None

def create_project_structure():
    """Crée la structure complète du projet"""
    print_step(1, "Création de la structure du projet")
    
    folders = [
        # Scripts de collecte
        "data-collection/collectors",
        "data-collection/schedulers",
        
        # Pipeline de traitement
        "data-processing/spark-jobs",
        "data-processing/kafka-config",
        
        # Base de données
        "database/sql",
        "database/mongodb", 
        
        # Interface web
        "web-interface/streamlit-app",
        "web-interface/api",
        "web-interface/static",
        "web-interface/templates",
        
        # Configuration Docker
        "docker/dockerfiles",
        "docker/config",
        
        # NiFi
        "nifi/processors",
        "nifi/templates",
        
        # Scripts utilitaires
        "scripts/setup",
        "scripts/monitoring",
        "scripts/deployment",
        
        # Données et logs
        "data/raw",
        "data/processed", 
        "data/exports",
        "logs",
        
        # Tests
        "tests/unit",
        "tests/integration",
        "tests/data",
        
        # Documentation
        "docs/api",
        "docs/setup",
        "docs/user-guide"
    ]
    
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        # Créer un fichier .gitkeep pour les dossiers vides
        gitkeep = Path(folder) / ".gitkeep"
        if not any(Path(folder).iterdir()):
            gitkeep.touch()
    
    print_colored("✅ Structure créée", Colors.GREEN)

def copy_main_files():
    """Copie les fichiers principaux depuis les artifacts"""
    print_step(2, "Création des fichiers de base")
    
    # Copier le collecteur météo dans le bon dossier
    collector_content = '''# Votre collecteur météo ici
# Copié depuis l'artifact meteo_collector
from data_collection.collectors.toulouse_collector import ToulouseMeteoCollector
'''
    
    with open("data-collection/collectors/toulouse_collector.py", "w") as f:
        f.write("# Fichier collecteur - À remplir avec le code de l'artifact\n")
    
    with open("data-collection/collectors/__init__.py", "w") as f:
        f.write("")
    
    # Fichiers __init__.py pour tous les packages Python
    init_files = [
        "data-collection/__init__.py",
        "data-processing/__init__.py", 
        "data-processing/spark-jobs/__init__.py",
        "data-processing/kafka-config/__init__.py",
        "database/__init__.py",
        "database/sql/__init__.py",
        "database/mongodb/__init__.py",
        "web-interface/__init__.py",
        "web-interface/streamlit-app/__init__.py",
        "web-interface/api/__init__.py",
        "tests/__init__.py"
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
    
    print_colored("✅ Fichiers de base créés", Colors.GREEN)

def install_dependencies():
    """Installe les dépendances Python"""
    print_step(3, "Installation des dépendances Python")
    
    if not Path("requirements.txt").exists():
        print_colored("❌ requirements.txt non trouvé", Colors.RED)
        return False
    
    try:
        print_colored("📦 Installation en cours...", Colors.YELLOW)
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print_colored("✅ Dépendances installées", Colors.GREEN)
            return True
        else:
            print_colored(f"❌ Erreur pip: {result.stderr}", Colors.RED)
            return False
            
    except subprocess.TimeoutExpired:
        print_colored("❌ Timeout lors de l'installation", Colors.RED)
        return False
    except Exception as e:
        print_colored(f"❌ Erreur: {e}", Colors.RED)
        return False

def setup_environment():
    """Configure l'environnement (.env, etc.)"""
    print_step(4, "Configuration de l'environnement")
    
    # Créer .env depuis .env.example
    if Path(".env.example").exists() and not Path(".env").exists():
        shutil.copy(".env.example", ".env")
        print_colored("✅ Fichier .env créé depuis .env.example", Colors.GREEN)
        print_colored("⚠️  N'oubliez pas d'éditer .env avec vos paramètres !", Colors.YELLOW)
    elif Path(".env").exists():
        print_colored("✅ Fichier .env existe déjà", Colors.GREEN)
    else:
        print_colored("❌ .env.example non trouvé", Colors.RED)
    
    # Créer .gitignore si nécessaire
    if not Path(".gitignore").exists():
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*.so
.Python
venv/
env/
.env

# Data
data/raw/*
data/processed/*
data/exports/*
!data/*/.gitkeep

# Logs
logs/
*.log

# IDE
.vscode/
.idea/

# Database
*.db
*.sqlite
"""
        with open(".gitignore", "w") as f:
            f.write(gitignore_content)
        print_colored("✅ .gitignore créé", Colors.GREEN)

def check_docker():
    """Vérifie si Docker est disponible"""
    print_step(5, "Vérification de Docker")
    
    if check_command_exists("docker"):
        try:
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print_colored(f"✅ {result.stdout.strip()}", Colors.GREEN)
            else:
                print_colored("❌ Docker non fonctionnel", Colors.RED)
        except:
            print_colored("❌ Erreur Docker", Colors.RED)
    else:
        print_colored("❌ Docker non installé", Colors.YELLOW)
        print_colored("  Installez Docker pour utiliser l'environnement complet", Colors.YELLOW)
    
    if check_command_exists("docker-compose"):
        try:
            result = subprocess.run(["docker-compose", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print_colored(f"✅ {result.stdout.strip()}", Colors.GREEN)
            else:
                print_colored("❌ Docker Compose non fonctionnel", Colors.RED)
        except:
            print_colored("❌ Erreur Docker Compose", Colors.RED)
    else:
        print_colored("❌ Docker Compose non installé", Colors.YELLOW)

def create_docker_compose():
    """Crée un docker-compose.yml basique"""
    print_step(6, "Création du Docker Compose")
    
    if Path("docker-compose.yml").exists():
        print_colored("✅ docker-compose.yml existe déjà", Colors.GREEN)
        return
    
    docker_compose_content = """version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: postgres:15
    container_name: postgres_meteo
    restart: always
    environment:
      POSTGRES_DB: meteo_toulouse
      POSTGRES_USER: meteo_user
      POSTGRES_PASSWORD: meteo_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # MongoDB
  mongodb:
    image: mongo:7.0
    container_name: mongodb_meteo
    restart: always
    environment:
      MONGO_INITDB_ROOT_USERNAME: meteo_user
      MONGO_INITDB_ROOT_PASSWORD: meteo_pass
      MONGO_INITDB_DATABASE: meteo_events
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

  # Interface Streamlit
  streamlit:
    build:
      context: .
      dockerfile: docker/dockerfiles/Dockerfile.streamlit
    container_name: streamlit_meteo
    restart: always
    ports:
      - "8501:8501"
    depends_on:
      - postgres
      - mongodb
    volumes:
      - ./data:/app/data
      - ./web-interface:/app/web-interface

volumes:
  postgres_data:
  mongodb_data:
"""
    
    with open("docker-compose.yml", "w") as f:
        f.write(docker_compose_content)
    
    print_colored("✅ docker-compose.yml créé", Colors.GREEN)

def create_dockerfile():
    """Crée les Dockerfiles"""
    print_step(7, "Création des Dockerfiles")
    
    # Dockerfile pour Streamlit
    dockerfile_streamlit = """FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copie des requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY . .

# Port Streamlit
EXPOSE 8501

# Commande par défaut
CMD ["streamlit", "run", "web-interface/streamlit-app/main.py", "--server.address", "0.0.0.0"]
"""
    
    dockerfile_path = Path("docker/dockerfiles")
    dockerfile_path.mkdir(parents=True, exist_ok=True)
    
    with open(dockerfile_path / "Dockerfile.streamlit", "w") as f:
        f.write(dockerfile_streamlit)
    
    print_colored("✅ Dockerfiles créés", Colors.GREEN)

def run_initial_tests():
    """Lance des tests basiques"""
    print_step(8, "Tests de base")
    
    try:
        # Test d'import de config
        sys.path.append(str(Path.cwd()))
        import config
        print_colored("✅ Configuration importée", Colors.GREEN)
    except Exception as e:
        print_colored(f"❌ Erreur config: {e}", Colors.RED)
    
    # Test création répertoires
    if Path("data/raw").exists():
        print_colored("✅ Répertoires de données OK", Colors.GREEN)
    else:
        print_colored("❌ Problème répertoires", Colors.RED)

def display_next_steps():
    """Affiche les prochaines étapes"""
    print_colored(f"\n🎉 Installation terminée !", Colors.GREEN + Colors.BOLD)
    
    print_colored(f"\n📋 Prochaines étapes:", Colors.BLUE + Colors.BOLD)
    
    steps = [
        "1. Éditez le fichier .env avec vos configurations",
        "2. Copiez le code du collecteur météo dans data-collection/collectors/toulouse_collector.py",
        "3. Lancez les services: python main.py docker up",
        "4. Initialisez les bases de données: python main.py db init", 
        "5. Testez la collecte: python main.py collect meteo",
        "6. Lancez l'interface: python main.py web streamlit"
    ]
    
    for step in steps:
        print_colored(f"  {step}", Colors.YELLOW)
    
    print_colored(f"\n🌐 URLs utiles:", Colors.BLUE + Colors.BOLD)
    urls = [
        "• Interface Streamlit:  http://localhost:8501",
        "• PgAdmin:             http://localhost:5050", 
        "• Mongo Express:       http://localhost:8081",
        "• Kafka UI:            http://localhost:8085"
    ]
    
    for url in urls:
        print_colored(f"  {url}", Colors.GREEN)
    
    print_colored(f"\n💡 Aide:", Colors.BLUE + Colors.BOLD)
    print_colored("  • python main.py --help          Voir toutes les commandes", Colors.YELLOW)
    print_colored("  • python main.py info            Infos sur la configuration", Colors.YELLOW)
    print_colored("  • python main.py test            Lancer les tests", Colors.YELLOW)

def main():
    """Fonction principale d'installation"""
    print_colored("🌤️ INSTALLATION PLATEFORME METEO TOULOUSE", Colors.BLUE + Colors.BOLD)
    print_colored("=" * 50, Colors.BLUE)
    
    # Vérifications préliminaires
    check_python_version()
    
    try:
        # Étapes d'installation
        create_project_structure()
        copy_main_files() 
        
        # Installation des dépendances (optionnel si problème)
        deps_ok = install_dependencies()
        if not deps_ok:
            print_colored("⚠️  Vous pouvez installer manuellement avec:", Colors.YELLOW)
            print_colored("   pip install -r requirements.txt", Colors.YELLOW)
        
        setup_environment()
        check_docker()
        create_docker_compose()
        create_dockerfile()
        
        if deps_ok:
            run_initial_tests()
        
        display_next_steps()
        
    except KeyboardInterrupt:
        print_colored("\n❌ Installation interrompue", Colors.RED)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n❌ Erreur inattendue: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()