#!/usr/bin/env python3
"""Code pour créer une table de conversion de IRIS 2021 vers IRIS 2025
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path

# =====================================================
# 1. CONFIGURATION DES CHEMINS
# =====================================================

FICHIER_2022 = (
    Path("raw_resources")
    / "CONTOURS-IRIS_2-1__SHP__FRA_2022-01-01"
    / "CONTOURS-IRIS"
    / "1_DONNEES_LIVRAISON_2022-06-00180"
    / "CONTOURS-IRIS_2-1_SHP_LAMB93_FXX-2022"
    / "CONTOURS-IRIS.shp"
)

FICHIER_2025 = (
    Path("raw_resources")
    / "CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2025-01-01"
    / "CONTOURS-IRIS"
    / "1_DONNEES_LIVRAISON_2025-06-00117"
    / "CONTOURS-IRIS_3-0_GPKG_LAMB93_FXX-ED2025-01-01"
    / "iris.gpkg"
)

SORTIE = Path("processed_resources/iris_table_conversion")
SORTIE.mkdir(parents=True, exist_ok=True)

SEUIL_PCT = 0.01

# =====================================================
# 2. VERIFICATION DES FICHIERS
# =====================================================

for fichier in [FICHIER_2022, FICHIER_2025]:
    if not fichier.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {fichier}"
        )

# =====================================================
# 3. LECTURE DES DONNEES
# =====================================================

print("Lecture des fichiers...")

iris22 = gpd.read_file(FICHIER_2022)
iris25 = gpd.read_file(FICHIER_2025)

print("Nombre d'IRIS 2022 :", len(iris22))
print("Nombre d'IRIS 2025 :", len(iris25))

print("\nChamps 2022 :")
print(iris22.columns.tolist())

print("\nChamps 2025 :")
print(iris25.columns.tolist())

# =====================================================
# 4. DETECTION DU CODE IRIS
# =====================================================

def trouver_code_iris(gdf):
    candidats = [
        "CODE_IRIS",
        "CODEIRIS",
        "IRIS",
        "DCOMIRIS"
    ]

    # Recherche exacte
    for champ in candidats:
        if champ in gdf.columns:
            return champ

    # Recherche insensible à la casse
    mapping = {
        str(col).upper(): col
        for col in gdf.columns
    }

    for champ in candidats:
        if champ in mapping:
            return mapping[champ]

    raise ValueError(
        "Code IRIS introuvable. "
        "Vérifier les champs affichés précédemment."
    )


champ22 = trouver_code_iris(iris22)
champ25 = trouver_code_iris(iris25)

iris22 = iris22.rename(
    columns={champ22: "IRIS_2022"}
)

iris25 = iris25.rename(
    columns={champ25: "IRIS_2025"}
)

# Conservation des codes sous forme de texte
iris22["IRIS_2022"] = iris22["IRIS_2022"].astype(str)
iris25["IRIS_2025"] = iris25["IRIS_2025"].astype(str)

# =====================================================
# 5. CONTROLE DES PROJECTIONS
# =====================================================

print("\nCRS 2022 :", iris22.crs)
print("CRS 2025 :", iris25.crs)

if iris22.crs is None or iris25.crs is None:
    raise ValueError("CRS manquant.")

# Harmonisation Lambert 93
iris22 = iris22.to_crs("EPSG:2154")
iris25 = iris25.to_crs("EPSG:2154")

# =====================================================
# 6. NETTOYAGE GEOMETRIQUE
# =====================================================

iris22 = iris22[
    iris22.geometry.notna()
    & ~iris22.geometry.is_empty
].copy()

iris25 = iris25[
    iris25.geometry.notna()
    & ~iris25.geometry.is_empty
].copy()

iris22["geometry"] = iris22.geometry.make_valid()
iris25["geometry"] = iris25.geometry.make_valid()

# =====================================================
# 7. CALCUL DES SURFACES INITIALES
# =====================================================

iris22["SURF_2022"] = iris22.geometry.area
iris25["SURF_2025"] = iris25.geometry.area

# Vérification des identifiants uniques
if iris22["IRIS_2022"].duplicated().any():
    raise ValueError("Codes IRIS 2022 en doublon.")

if iris25["IRIS_2025"].duplicated().any():
    raise ValueError("Codes IRIS 2025 en doublon.")

surfaces22 = iris22.set_index(
    "IRIS_2022"
)["SURF_2022"]

surfaces25 = iris25.set_index(
    "IRIS_2025"
)["SURF_2025"]

# =====================================================
# 8. INTERSECTION GEOGRAPHIQUE
# =====================================================

print("\nCalcul des intersections spatiales...")

intersections = gpd.overlay(
    iris25[["IRIS_2025", "geometry"]],
    iris22[["IRIS_2022", "geometry"]],
    how="intersection",
    keep_geom_type=True
)

intersections["SURF_INTERSECTION"] = (
    intersections.geometry.area
)

intersections = intersections[
    intersections["SURF_INTERSECTION"] > 0
].copy()

# =====================================================
# 9. CALCUL DES POURCENTAGES
# =====================================================

intersections["SURF_2022"] = (
    intersections["IRIS_2022"].map(surfaces22)
)

intersections["SURF_2025"] = (
    intersections["IRIS_2025"].map(surfaces25)
)

intersections["PCT_IRIS_2022"] = (
    intersections["SURF_INTERSECTION"]
    / intersections["SURF_2022"] * 100
)

intersections["PCT_IRIS_2025"] = (
    intersections["SURF_INTERSECTION"]
    / intersections["SURF_2025"] * 100
)

# =====================================================
# 10. CLASSIFICATION DES CORRESPONDANCES
# =====================================================

# Relations significatives pour classifier les IRIS
liens = intersections[
    (
        (intersections["PCT_IRIS_2022"] >= SEUIL_PCT)
        | (intersections["PCT_IRIS_2025"] >= SEUIL_PCT)
    )
].copy()

nb_iris25 = (
    liens.groupby("IRIS_2022")["IRIS_2025"]
    .nunique()
)

nb_iris22 = (
    liens.groupby("IRIS_2025")["IRIS_2022"]
    .nunique()
)

intersections["NB_IRIS_2025"] = (
    intersections["IRIS_2022"]
    .map(nb_iris25)
    .fillna(0)
    .astype(int)
)

intersections["NB_IRIS_2022"] = (
    intersections["IRIS_2025"]
    .map(nb_iris22)
    .fillna(0)
    .astype(int)
)

def classifier(row):

    n22 = row["NB_IRIS_2022"]
    n25 = row["NB_IRIS_2025"]

    if n22 > 1 and n25 > 1:
        return "REDECOUPAGE_MULTIPLE"

    if n22 > 1:
        return "FUSION_IRIS_2022"

    if n25 > 1:
        return "SCISSION_IRIS_2022"

    if row["IRIS_2022"] == row["IRIS_2025"]:
        return "CODE_IDENTIQUE_1_1"

    return "CORRESPONDANCE_1_1_CODE_MODIFIE"


intersections["TYPE_CORRESPONDANCE"] = (
    intersections.apply(classifier, axis=1)
)

# =====================================================
# 11. EXPORT TABLE DE PASSAGE
# =====================================================

colonnes = [
    "IRIS_2022",
    "IRIS_2025",
    "SURF_INTERSECTION",
    "SURF_2022",
    "SURF_2025",
    "PCT_IRIS_2022",
    "PCT_IRIS_2025",
    "NB_IRIS_2022",
    "NB_IRIS_2025",
    "TYPE_CORRESPONDANCE"
]

table_passage = pd.DataFrame(
    intersections[colonnes]
).sort_values(
    ["IRIS_2022", "IRIS_2025"]
)

table_passage.to_csv(
    SORTIE / "PASSAGE_IRIS_2022_2025.csv",
    index=False,
    sep=";",
    decimal=",",
    encoding="utf-8-sig"
)

# =====================================================
# 12. IRIS SANS CORRESPONDANCE
# =====================================================

iris22_sans = (
    set(iris22["IRIS_2022"])
    - set(liens["IRIS_2022"])
)

iris25_sans = (
    set(iris25["IRIS_2025"])
    - set(liens["IRIS_2025"])
)

pd.DataFrame({
    "IRIS_2022": sorted(iris22_sans)
}).to_csv(
    SORTIE / "IRIS_2022_SANS_CORRESPONDANCE.csv",
    index=False,
    sep=";",
    encoding="utf-8-sig"
)

pd.DataFrame({
    "IRIS_2025": sorted(iris25_sans)
}).to_csv(
    SORTIE / "IRIS_2025_SANS_CORRESPONDANCE.csv",
    index=False,
    sep=";",
    encoding="utf-8-sig"
)

# =====================================================
# 13. EXPORT GEOGRAPHIQUE
# =====================================================

intersections.to_file(
    SORTIE / "INTERSECTIONS_IRIS_2022_2025.gpkg",
    driver="GPKG"
)

# =====================================================
# 14. STATISTIQUES DE CONTROLE
# =====================================================

print("\n========== BILAN ==========")

print("IRIS 2022 :", len(iris22))
print("IRIS 2025 :", len(iris25))
print("Intersections :", len(intersections))

print("\nTypes de correspondance :")

print(
    liens.merge(
        intersections[
            ["IRIS_2022", "IRIS_2025",
             "TYPE_CORRESPONDANCE"]
        ].drop_duplicates(),
        on=["IRIS_2022", "IRIS_2025"]
    )["TYPE_CORRESPONDANCE"].value_counts()
)

print("\nIRIS 2022 sans correspondance :", len(iris22_sans))
print("IRIS 2025 sans correspondance :", len(iris25_sans))

print("\nTraitement terminé.")
print("Résultats :", SORTIE.resolve())
