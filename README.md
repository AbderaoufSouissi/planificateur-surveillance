# ISI-Exam-Scheduler

Lien GitHub du projet (pour l'évaluation de la qualité du code) :
[https://github.com/AbderaoufSouissi/ISI-Exam-Scheduler](https://github.com/AbderaoufSouissi/planificateur-surveillance)

## Description
ISI-Exam-Scheduler est une application Python/Tkinter destinée à la génération et gestion des plannings d'examens (importation des voeux, génération d'horaires, exports, rapports). Le dépôt contient le code source (sous `src/`), des scripts de vérification et des configurations pour empaquetage.

## Prérequis
- Python 3.10+ (idéalement 3.11)
- pip
- Sur Windows, PowerShell est recommandé pour les commandes fournies ci-dessous.

## Installation rapide (en développement)
1. Cloner le dépôt :

```powershell
git clone https://github.com/AbderaoufSouissi/ISI-Exam-Scheduler.git
cd ISI-Exam-Scheduler
```

2. Créer un environnement virtuel et l'activer :

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

3. Installer les dépendances :

```powershell
pip install -r requirements.txt
# ou pour l'environnement complet
pip install -r requirements_full.txt
```

## Exécution en mode développement
L'application contient une interface Tkinter dans `tkinter_isi/`.

Pour lancer l'application principale :

```powershell
cd src\tkinter_isi
python main.py
```

Pour lancer des scripts utilitaires (exemples) :

```powershell
# ISI-Exam-Scheduler

Lien GitHub du projet (pour l'évaluation de la qualité du code) :
https://github.com/AbderaoufSouissi/ISI-Exam-Scheduler

## Description
ISI-Exam-Scheduler est une application Python avec interface Tkinter pour aider à la planification des examens : importation des vœux, génération d'horaires/plannings, exportations (PDF/excel) et rapports. Le code source principal se trouve sous `src/`. Le dépôt contient également des scripts de vérification, des fichiers pour l'empaquetage (PyInstaller) et des tests de base.

## Contenu important du dépôt
- `src/` : code source de l'application
- `src/tkinter_isi/` : interface graphique et écrans
- `src/db/` : accès à la base de données locale et opérations liées
- `build_exe.py`, `main.spec`, `ISI_Exam_Scheduler.spec` : utilitaires pour construire un exécutable
- `requirements.txt` / `requirements_full.txt` : dépendances
- `test_*.py` : tests unitaires et scripts de diagnostic

## Prérequis
- Python 3.10+ (3.11 recommandé)
- pip
- Sur Windows : PowerShell pour les exemples ci-dessous

## Installation (développement)
1. Cloner le dépôt :

```powershell
git clone https://github.com/AbderaoufSouissi/ISI-Exam-Scheduler.git
cd ISI-Exam-Scheduler
```

2. Créer et activer un environnement virtuel :

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

3. Installer les dépendances :

```powershell
pip install -r requirements.txt
# ou, si vous avez besoin de dépendances optionnelles:
pip install -r requirements_full.txt
```

## Exécution en mode développement
L'interface principale se trouve dans `src/tkinter_isi/main.py`.

```powershell
cd src\tkinter_isi
python main.py
```

Exemples utiles :

```powershell
# Exécuter les tests unitaires
python -m pytest -q

# Lancer des vérifications CSV/Excel (script d'exemple)
python ..\check_voeux.py <chemin_vers_fichier_voeux.xlsx>
```

Note : certains scripts attendent des fichiers d'entrée spécifiques (format Excel/CSV). Consultez les fichiers de code dans `src/` pour plus de détails.

## Empaquetage (générer un exécutable Windows)
Le projet inclut des fichiers de configuration PyInstaller et un script `build_exe.py`.

```powershell
# Utiliser le script fourni (si adapté)
python build_exe.py

# Ou utiliser pyinstaller directement (exemple)
pyinstaller --onefile --windowed main.spec
```

Après construction, vérifiez le dossier `build/` dans la racine du projet (ou `dist/` si vous avez utilisé pyinstaller). Testez l'exécutable sur une machine cible.

## Tests
Le dépôt contient des tests de base (p.ex. `test_scheduler.py`). Pour exécuter tous les tests :

```powershell
python -m pytest
```

## Recommandations d'utilisation
- Travaillez toujours dans un environnement virtuel pour éviter les conflits de dépendances.
- Faites des sauvegardes des fichiers d'entrée originaux (voeux, emplois du temps) avant toute transformation.
- Sauvegardez la base de données locale (`src/db/`) avant d'exécuter des opérations d'écriture.
- Activez et consultez les logs pour diagnostiquer les problèmes (ajoutez logging si nécessaire).
- Lors de l'empaquetage, testez l'exécutable sur une machine ayant une configuration similaire à celle des utilisateurs finaux.

## Dépannage rapide
- ImportError / ModuleNotFoundError : assurez-vous que l'environnement virtuel est activé et que `pip install -r requirements.txt` a été exécuté.
- Erreurs PyInstaller : supprimez les dossiers `build/` et `dist/` puis relancez la construction.
- Problèmes Tkinter : vérifiez que votre installation Python inclut le support Tk (sur Windows, le packaging officiel l'inclut généralement).

## Contribuer
- Forkez le projet, créez une branche `feature/*` ou `bugfix/*`, puis ouvrez une pull request.
- Exécutez les tests avant de proposer une PR et documentez vos changements.

## Licence
Ajoutez un fichier `LICENSE` si vous souhaitez préciser une licence (MIT, Apache-2.0, etc.).

## Contact / Auteur
- Dépôt GitHub : https://github.com/AbderaoufSouissi/ISI-Exam-Scheduler

---

Fichier mis à jour automatiquement : `README.md`

