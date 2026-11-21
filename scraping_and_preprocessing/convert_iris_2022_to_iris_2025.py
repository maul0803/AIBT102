#!/usr/bin/env python3
"""Utilisation de la table de conversion des IRIS pour estimer les revenus de 2021 sur un IRIS de 2025
"""
import pandas as pd
import numpy as np
from pathlib import Path

# =====================================================
# 1. CONFIGURATION
# =====================================================


RAW_PATH = Path("raw_resources")
PROCESSED_PATH = Path('processed_resources')
FICHIER_DONNEES_2022 = (
    RAW_PATH
    / "BASE_TD_FILO_IRIS_2021_DISP_CSV"
    / "BASE_TD_FILO_IRIS_2021_DISP.csv"
)

FICHIER_PASSAGE = (
    PROCESSED_PATH
    / "iris_table_conversion"
    / "PASSAGE_IRIS_2022_2025.csv"
)

SORTIE = (
        PROCESSED_PATH
        / "BASE_TD_FILO_ESTIMATED_IRIS_2025_DISP_CSV"
        / "BASE_TD_FILO_ESTIMATED_IRIS_2025_DISP")
SORTIE.mkdir(parents=True, exist_ok=True)

# Même seuil que dans le script de correspondance.
# 0.01 signifie 0,01 % et non 1 %.
SEUIL_PCT = 0.01

# =====================================================
# 2. LECTURE DES FICHIERS
# =====================================================

print("Lecture des fichiers...")

donnees = pd.read_csv(
    FICHIER_DONNEES_2022,
    sep=";",
    decimal=",",
    dtype={"IRIS": str},
    encoding="utf-8-sig"
)

passage = pd.read_csv(
    FICHIER_PASSAGE,
    sep=";",
    decimal=",",
    dtype={
        "IRIS_2022": str,
        "IRIS_2025": str
    },
    encoding="utf-8-sig"
)

# Nettoyage des codes IRIS
donnees["IRIS"] = donnees["IRIS"].str.strip()

passage["IRIS_2022"] = (
    passage["IRIS_2022"].str.strip()
)

passage["IRIS_2025"] = (
    passage["IRIS_2025"].str.strip()
)

# Vérification des doublons dans les données initiales
if donnees["IRIS"].duplicated().any():
    raise ValueError(
        "Plusieurs lignes existent pour un même IRIS 2022."
    )

# =====================================================
# 3. IDENTIFICATION DES INDICATEURS
# =====================================================

colonnes_indicateurs = [
    col for col in donnees.columns
    if col != "IRIS"
]

# Conversion des indicateurs en valeurs numériques
for col in colonnes_indicateurs:
    donnees[col] = pd.to_numeric(
        donnees[col],
        errors="coerce"
    )

# Suppression des indicateurs entièrement vides
colonnes_indicateurs = [
    col for col in colonnes_indicateurs
    if donnees[col].notna().any()
]

print("Nombre d'indicateurs :", len(colonnes_indicateurs))

# =====================================================
# 4. SELECTION DES CORRESPONDANCES
# =====================================================

liens = passage[
    (
        (passage["PCT_IRIS_2022"] >= SEUIL_PCT)
        |
        (passage["PCT_IRIS_2025"] >= SEUIL_PCT)
    )
].copy()

# On conserve uniquement les colonnes nécessaires
liens = liens[
    [
        "IRIS_2022",
        "IRIS_2025",
        "SURF_INTERSECTION",
        "SURF_2025"
    ]
]

# Suppression des intersections invalides
liens = liens[
    liens["SURF_INTERSECTION"] > 0
].copy()

# =====================================================
# 5. ASSOCIATION DES DONNEES AUX CORRESPONDANCES
# =====================================================

print("Association des données...")

fusion = liens.merge(
    donnees,
    left_on="IRIS_2022",
    right_on="IRIS",
    how="left",
    indicator=True
)

# Contrôle des données manquantes
iris_sans_donnees = (
    fusion.loc[
        fusion["_merge"] == "left_only",
        "IRIS_2022"
    ]
    .drop_duplicates()
)

print(
    "IRIS 2022 sans données statistiques :",
    len(iris_sans_donnees)
)

fusion = fusion[
    fusion["_merge"] == "both"
].copy()

# =====================================================
# 6. CALCUL DES INDICATEURS IRIS 2025
# =====================================================

print("Calcul des indicateurs 2025...")

resultats = []

for iris25, groupe in fusion.groupby("IRIS_2025"):

    ligne = {
        "IRIS": iris25
    }

    # Pondération par surface d'intersection
    poids = groupe["SURF_INTERSECTION"]

    for col in colonnes_indicateurs:

        valeurs = groupe[col]

        # Exclusion des valeurs manquantes
        masque = valeurs.notna() & poids.notna()

        if masque.any():

            ligne[col] = np.average(
                valeurs[masque],
                weights=poids[masque]
            )

        else:
            ligne[col] = np.nan

    # Nombre d'anciens IRIS contributeurs
    ligne["NB_IRIS_2022_SOURCES"] = (
        groupe["IRIS_2022"].nunique()
    )

    # Contrôle de la couverture géographique
    surface_couverte = poids.sum()

    surface_totale = groupe["SURF_2025"].iloc[0]

    ligne["COUVERTURE_SURF_2025_PCT"] = (
        surface_couverte / surface_totale * 100
        if surface_totale > 0
        else np.nan
    )

    resultats.append(ligne)

# Création du tableau final
df_final = pd.DataFrame(resultats)

# =====================================================
# 7. EXPORT DU CSV
# =====================================================

df_final = df_final.sort_values("IRIS")

df_final.to_csv(
    SORTIE / "DONNEES_IRIS_2025_ESTIMEES.csv",
    sep=";",
    decimal=",",
    index=False,
    encoding="utf-8-sig"
)

# =====================================================
# 8. EXPORT DES CONTROLES
# =====================================================

# IRIS 2022 sans données statistiques
pd.DataFrame({
    "IRIS_2022": iris_sans_donnees
}).to_csv(
    SORTIE / "IRIS_2022_SANS_DONNEES.csv",
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

# IRIS 2025 sans correspondance géographique
iris25_sans = pd.read_csv(
    PROCESSED_PATH / "iris_table_conversion"
    / "IRIS_2025_SANS_CORRESPONDANCE.csv",
    sep=";",
    dtype=str,
    encoding="utf-8-sig"
)

iris25_sans.to_csv(
    SORTIE / "IRIS_2025_SANS_ESTIMATION.csv",
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

# =====================================================
# 9. BILAN
# =====================================================

print("\n========== BILAN ==========")

print("IRIS 2022 en entrée :", len(donnees))

print(
    "IRIS 2025 estimés :",
    len(df_final)
)

print(
    "IRIS 2025 sans correspondance :",
    len(iris25_sans)
)

print(
    "Nombre d'indicateurs convertis :",
    len(colonnes_indicateurs)
)

print(
    "\nCouverture surfacique moyenne :",
    round(
        df_final["COUVERTURE_SURF_2025_PCT"].mean(),
        2
    ),
    "%"
)

print("\nTraitement terminé.")
print("Résultats :", SORTIE.resolve())