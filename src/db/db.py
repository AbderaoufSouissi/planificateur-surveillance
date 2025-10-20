import sqlite3

# Connexion (ou création) à la base de données SQLite
conn = sqlite3.connect("planning.db")
curseur = conn.cursor()

# Création des tables
curseur.executescript("""
CREATE TABLE IF NOT EXISTS Sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    annee_academique TEXT NOT NULL,
    semestre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    surveillants_par_salle INTEGER,
    quotas_json TEXT,
    poids_voeux INTEGER,
    FOREIGN KEY (session_id) REFERENCES Sessions(id)
);

CREATE TABLE IF NOT EXISTS Enseignants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    nom_ens TEXT NOT NULL,
    prenom_ens TEXT NOT NULL,
    email_ens TEXT,
    grade TEXT,
    code_smartexam_ens TEXT NOT NULL,
    participe_surveillance BOOLEAN DEFAULT 1,
    FOREIGN KEY (session_id) REFERENCES Sessions(id),
    UNIQUE(session_id, code_smartexam_ens)
);

CREATE TABLE IF NOT EXISTS Voeux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    enseignant_id INTEGER NOT NULL,
    jour TEXT NOT NULL,
    seance TEXT NOT NULL,
    ordre_timestamp INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES Sessions(id),
    FOREIGN KEY (enseignant_id) REFERENCES Enseignants(code_smartexam_ens)
);

CREATE TABLE IF NOT EXISTS Creneaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    date_examen TEXT NOT NULL,
    heure_debut TEXT NOT NULL,
    nb_surveillants INTEGER,
    code_responsable TEXT,
    FOREIGN KEY (session_id) REFERENCES Sessions(id)
);

CREATE TABLE IF NOT EXISTS Affectations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enseignant_id TEXT NOT NULL,
    creneau_id INTEGER NOT NULL,
    role TEXT DEFAULT 'Surveillant',
    date_affectation TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enseignant_id) REFERENCES Enseignants(code_smartexam_ens),
    FOREIGN KEY (creneau_id) REFERENCES Creneaux(id)
);

CREATE TABLE IF NOT EXISTS Audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    affectation_id INTEGER,
    action TEXT,
    raison TEXT,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES Sessions(id),
    FOREIGN KEY (affectation_id) REFERENCES Affectations(id)
);

CREATE TABLE IF NOT EXISTS Exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    type TEXT,
    chemin_fichier TEXT,
    cree_le TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES Sessions(id)
);

CREATE TABLE IF NOT EXISTS TeacherSatisfaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    teacher_id TEXT NOT NULL,
    name TEXT NOT NULL,
    grade TEXT,
    satisfaction_score REAL NOT NULL,
    total_assignments INTEGER,
    quota INTEGER,
    quota_excess INTEGER,
    working_days INTEGER,
    consecutive_days INTEGER,
    isolated_days INTEGER,
    gap_days INTEGER,
    voeux_respected INTEGER DEFAULT 0,
    voeux_total INTEGER DEFAULT 0,
    voeux_details TEXT,
    gap_hours INTEGER DEFAULT 0,
    schedule_pattern TEXT,
    issues_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES Sessions(id),
    FOREIGN KEY (teacher_id) REFERENCES Enseignants(code_smartexam_ens)
);
""")

conn.commit()
conn.close()

print("✅ Base de données 'planning.db' créée avec succès !")
