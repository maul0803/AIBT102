
#!/usr/bin/env python3
"""
Download all commercial establishments located within the
administrative boundaries of Paris using OpenStreetMap.

The script retrieves the following OSM categories:
- shop: Retail stores and commercial shops.
- amenity: Restaurants, cafes, pharmacies and other facilities.
- craft: Craftspeople and workshops.
- office: Professional and administrative offices.

Usage:
    python download_all_commerces.py

Output:
    raw_resources/commerces/commerces_osm_paris.csv
"""

import csv
import os
import urllib.parse
import urllib.request
import urllib.error
import json
import time
import random


UA = "TrouveTonBusinessLocal/1.0"
OVERPASS = "https://overpass-api.de/api/interpreter"

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

def get_json(url, data=None, max_retries=7, timeout=180):
    """
    Send an HTTP request and return the response as JSON.

    This function implements a retry mechanism to handle temporary
    HTTP errors and network failures.

    Retryable HTTP status codes:
        - 429: Too Many Requests
        - 500: Internal Server Error
        - 502: Bad Gateway
        - 503: Service Unavailable
        - 504: Gateway Timeout

    An exponential backoff strategy with random jitter is used
    between retry attempts. The Retry-After header is respected
    when provided by the server.

    Args:
        url (str): Target URL for the HTTP request.
        data (bytes, optional): Encoded request body. Defaults to None.
        max_retries (int, optional): Maximum number of retry attempts.
            Defaults to 7.
        timeout (int, optional): Maximum request duration in seconds.
            Defaults to 180.

    Returns:
        dict: JSON response parsed into a Python dictionary.

    Raises:
        urllib.error.HTTPError: If a non-retryable HTTP error occurs
            or all retry attempts fail.
        urllib.error.URLError: If the network request fails.
        RuntimeError: If the maximum number of attempts is reached.
    """

    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(max_retries + 1):

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Content-Type": (
                    "application/x-www-form-urlencoded"
                    if data else "application/json"
                )
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.load(response)

        except urllib.error.HTTPError as exc:

            if exc.code not in retryable_statuses or attempt >= max_retries:
                raise

            retry_after = exc.headers.get("Retry-After")

            try:
                delay = float(retry_after) if retry_after else 2 ** (attempt + 1)
            except ValueError:
                delay = 2 ** (attempt + 1)

            delay = min(120, delay) + random.uniform(0, 1)

            print(
                f"\nHTTP {exc.code} | "
                f"Attempt {attempt + 1}/{max_retries} | "
                f"Retrying in {delay:.1f}s"
            )

            time.sleep(delay)

        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError
        ) as exc:

            if attempt >= max_retries:
                raise

            delay = min(120, 2 ** (attempt + 1))
            delay += random.uniform(0, 1)

            print(
                f"\nNetwork error: {exc} | "
                f"Attempt {attempt + 1}/{max_retries} | "
                f"Waiting {delay:.1f}s"
            )

            time.sleep(delay)

    raise RuntimeError("Maximum number of retry attempts reached")


def download_department_commerces(department_name):
    """
    Download all commercial establishments located within a French
    department using its administrative boundary.
    """
    print(f"Preparing the search for {department_name}...")

    query = f"""
    [out:json][timeout:180];

    area["name"="{department_name}"]
         ["boundary"="administrative"]
         ["admin_level"="6"]->.department;

    (
        nwr(area.department)[shop];

        nwr(area.department)[amenity~"^(restaurant|cafe|fast_food|bar|pub|ice_cream|pharmacy|bank|clinic|doctors|dentist|childcare|kindergarten|fuel|car_wash|car_rental|marketplace|veterinary)$"];

        nwr(area.department)[craft];

        nwr(area.department)[office];
    );

    out center tags;
    """

    payload = urllib.parse.urlencode({
        "data": query
    }).encode()

    print(f"Downloading data for {department_name}...")

    data = get_json(OVERPASS, payload)

    rows = []
    elements = data.get("elements", [])

    print(f"Number of elements retrieved: {len(elements)}")

    for el in elements:
        tags = el.get("tags", {})
        center = el.get("center", {})

        category_type = ""
        category = ""

        for key in ["shop", "amenity", "craft", "office"]:
            if tags.get(key):
                category_type = key
                category = tags[key]
                break

        lat = el.get("lat", center.get("lat", ""))
        lon = el.get("lon", center.get("lon", ""))

        address = " ".join(filter(None, [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:postcode"),
            tags.get("addr:city"),
        ]))

        rows.append({
            "source": "OpenStreetMap",
            "name": tags.get("name", ""),
            "activity_query": (
                f"all_commercial_establishments_{department_name.lower()}"
            ),
            "category": category,
            "category_type": category_type,
            "address": address,
            "lat": lat,
            "lon": lon,
            "opening_hours": tags.get("opening_hours", ""),
            "phone": tags.get("phone", ""),
            "website": tags.get("website", ""),
            "siret": "",
            "osm_type": el["type"],
            "osm_id": el["id"],
            "osm_url": (
                f"https://www.openstreetmap.org/"
                f"{el['type']}/{el['id']}"
            )
        })

    return rows

def save_csv(path, rows):
    """
    Export the collected OpenStreetMap data to a CSV file.

    The CSV file is saved using UTF-8 with BOM encoding to ensure
    better compatibility with Microsoft Excel and other spreadsheet
    applications.

    The function uses csv.DictWriter to map dictionary values
    to the corresponding CSV columns.

    Args:
        path (str): Destination path of the CSV file.
        rows (list[dict]): List of dictionaries containing
            the commercial establishment data.

    Returns:
        None: The function writes the data directly to disk.

    Raises:
        OSError: If the destination directory or file cannot
            be accessed or created.
    """

    columns = [
        "source",
        "name",
        "activity_query",
        "category",
        "category_type",
        "address",
        "lat",
        "lon",
        "opening_hours",
        "phone",
        "website",
        "siret",
        "osm_type",
        "osm_id",
        "osm_url"
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)

def main():
    """
    Download commercial establishments for the configured department
    and export the results to CSV.
    """
    for department_name in DEPARTMENT_LIST:
        print("=" * 55)
        print("DEPARTMENT COMMERCIAL ESTABLISHMENTS DOWNLOAD")
        print("=" * 55)

        rows = download_department_commerces(department_name)

        output_dir = "raw_resources/commerces"
        os.makedirs(output_dir, exist_ok=True)

        output_name = (
            f"commerces_osm_{department_name.lower().replace(' ', '_')}.csv"
        )

        output = os.path.join(output_dir, output_name)

        save_csv(output, rows)

        print("\n" + "=" * 55)
        print("DOWNLOAD COMPLETED!")
        print("=" * 55)

        print(f"Department: {department_name}")
        print(f"Total number of rows: {len(rows)}")
        print(f"Establishments with a name: {sum(bool(r['name']) for r in rows)}")
        print(f"CSV file: {output}")


if __name__ == "__main__":
    main()
