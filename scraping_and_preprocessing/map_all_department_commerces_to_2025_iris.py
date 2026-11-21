
import os
import pandas as pd
import geopandas as gpd


# --------------------------------------------------
# Configuration
# --------------------------------------------------
DEPARTMENT_LIST = [
    "Ain",
    "Aisne",
    "Allier",
    "Alpes-de-Haute-Provence",
    "Hautes-Alpes",
    "Alpes-Maritimes",
    "Ardèche",
    "Ardennes",
    "Ariège",
    "Aube",
    "Aude",
    "Aveyron",
    "Bouches-du-Rhône",
    "Calvados",
    "Cantal",
    "Charente",
    "Charente-Maritime",
    "Cher",
    "Corrèze",
    "Côte-d'Or",
    "Côtes-d'Armor",
    "Creuse",
    "Dordogne",
    "Doubs",
    "Drôme",
    "Eure",
    "Eure-et-Loir",
    "Finistère",
    "Gard",
    "Haute-Garonne",
    "Gers",
    "Gironde",
    "Hérault",
    "Ille-et-Vilaine",
    "Indre",
    "Indre-et-Loire",
    "Isère",
    "Jura",
    "Landes",
    "Loir-et-Cher",
    "Loire",
    "Haute-Loire",
    "Loire-Atlantique",
    "Loiret",
    "Lot",
    "Lot-et-Garonne",
    "Lozère",
    "Maine-et-Loire",
    "Manche",
    "Marne",
    "Haute-Marne",
    "Mayenne",
    "Meurthe-et-Moselle",
    "Meuse",
    "Morbihan",
    "Moselle",
    "Nièvre",
    "Nord",
    "Oise",
    "Orne",
    "Pas-de-Calais",
    "Puy-de-Dôme",
    "Pyrénées-Atlantiques",
    "Hautes-Pyrénées",
    "Pyrénées-Orientales",
    "Bas-Rhin",
    "Haut-Rhin",
    "Rhône",
    "Haute-Saône",
    "Saône-et-Loire",
    "Sarthe",
    "Savoie",
    "Haute-Savoie",
    "Paris",
    "Seine-Maritime",
    "Seine-et-Marne",
    "Yvelines",
    "Deux-Sèvres",
    "Somme",
    "Tarn",
    "Tarn-et-Garonne",
    "Var",
    "Vaucluse",
    "Vendée",
    "Vienne",
    "Haute-Vienne",
    "Vosges",
    "Yonne",
    "Territoire de Belfort",
    "Essonne",
    "Hauts-de-Seine",
    "Seine-Saint-Denis",
    "Val-de-Marne",
    "Val-d'Oise"
]

DEPARTMENT_LIST = [
    "Paris",
    "Haute-Garonne",
]

IRIS_FILE = "raw_resources/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2025-01-01/CONTOURS-IRIS/1_DONNEES_LIVRAISON_2025-06-00117/CONTOURS-IRIS_3-0_GPKG_LAMB93_FXX-ED2025-01-01/iris.gpkg"

def find_column(gdf, candidates, required=True):
    """Find a column using a list of possible field names."""
    for candidate in candidates:
        for column in gdf.columns:
            if column.lower() == candidate.lower():
                return column

    if required:
        raise ValueError(
            f"Column not found. Available columns: {list(gdf.columns)}"
        )

    return None


def assign_iris_to_restaurants(restaurant_file, output_file):
    """Assign the 2025 IRIS polygon containing each restaurant GPS point."""

    # 1. Load restaurant data
    restaurants = pd.read_csv(restaurant_file)

    restaurants["lat"] = pd.to_numeric(
        restaurants["lat"], errors="coerce"
    )
    restaurants["lon"] = pd.to_numeric(
        restaurants["lon"], errors="coerce"
    )

    # Keep the original row index to restore the results later
    restaurants["row_id"] = restaurants.index

    valid = restaurants.dropna(subset=["lat", "lon"]).copy()

    # 2. Convert restaurant coordinates into geographic points
    points = gpd.GeoDataFrame(
        valid,
        geometry=gpd.points_from_xy(valid["lon"], valid["lat"]),
        crs="EPSG:4326"
    )

    # 3. Load IRIS 2025 polygons
    iris = gpd.read_file(IRIS_FILE)

    if iris.crs is None:
        raise ValueError("The IRIS file has no defined coordinate system.")

    # Identify the relevant IRIS attributes
    code_col = find_column(
        iris, ["code_iris", "DCOMIRIS", "IRIS"]
    )
    iris_col = find_column(
        iris, ["iris", "IRIS"]
    )
    name_col = find_column(
        iris, ["nom_iris", "LIBIRIS"], required=False
    )

    commune_col = find_column(
        iris, ["nom_commune", "NOM_COM"], required=False
    )

    type_col = find_column(
        iris, ["type_iris", "TYP_IRIS"], required=False
    )

    # 4. Keep only useful polygon attributes
    selected_columns = [code_col]

    for col in [iris_col, name_col, commune_col, type_col]:
        if col:
            selected_columns.append(col)

    iris = iris[selected_columns + ["geometry"]].copy()

    # Rename fields to standard names
    rename = {code_col: "iris_code"}

    if name_col:
        rename[name_col] = "iris_name"

    if commune_col:
        rename[commune_col] = "commune_name"

    if iris_col:
        rename[iris_col] = "iris"

    if type_col:
        rename[type_col] = "iris_type"

    iris = iris.rename(columns=rename)

    # 5. Reproject points to the IRIS coordinate system
    points = points.to_crs(iris.crs)

    # 6. Spatial join: find the polygon containing each point
    joined = gpd.sjoin(
        points,
        iris,
        how="left",
        predicate="within"
    )

    # Avoid duplicate matches if a point happens to touch a boundary
    joined = joined.drop_duplicates(subset="row_id")

    # 7. Add IRIS information to the original dataset
    iris_columns = [
        col for col in [
            "iris_code",
            "iris",
            "iris_name",
            "commune_name",
            "iris_type"
        ]
        if col in joined.columns
    ]

    joined = joined.set_index("row_id")

    for col in iris_columns:
        restaurants[col] = restaurants["row_id"].map(joined[col])

    restaurants = restaurants.drop(columns=["row_id"])

    # 8. Export the enriched dataset
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    restaurants.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # 9. Display results
    matched = restaurants["iris_code"].notna().sum()

    print("=" * 50)
    print("IRIS MATCHING COMPLETED")
    print("=" * 50)
    print(f"Total establishments: {len(restaurants)}")
    print(f"Establishments assigned to an IRIS: {matched}")
    print(f"Establishments without an IRIS: {len(restaurants) - matched}")
    print(f"Output file: {output_file}")


if __name__ == "__main__":
    for department_name in DEPARTMENT_LIST:
        restaurant_file = (
            f"raw_resources/commerces/commerces_osm_{department_name}.csv"
        )
        output_file = (
            f"processed_resources/commerces/commerces_osm_{department_name}.csv"
        )
        assign_iris_to_restaurants(restaurant_file, output_file)
