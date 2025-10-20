import pandas as pd
import sqlite3

# --- 1️⃣ Load Excel file ---
df = pd.read_excel("enseignants.xlsx")

# Suppose the Excel column is called "participe_surveillance"
# and contains "VRAI" / "FAUX"

# --- 2️⃣ Convert to Boolean ---
df["participe_surveillance"] = df["participe_surveillance"].apply(
    lambda x: True if str(x).strip().upper() == "VRAI" else False
)

# --- 3️⃣ Connect to SQLite ---
conn = sqlite3.connect("exam_scheduler.db")
c = conn.cursor()

# --- 4️⃣ Insert data ---
for _, row in df.iterrows():
    c.execute('''
        INSERT INTO Enseignants (
            nom_ens, prenom_ens, email_ens,
            grade_code_ens, code_smartex_ens,
            participe_surveillance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        row["session_id"],
        row["nom_ens"],
        row["prenom_ens"],
        row["email_ens"],
        row["grade_code_ens"],
        row["code_smartex_ens"],
        row["code_smartexam_ens"],
        row["participe_surveillance"]
    ))

conn.commit()
conn.close()
print("✅ Données importées avec succès !")
