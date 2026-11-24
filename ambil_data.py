import json
import csv
import urllib.request
import urllib.parse

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

KOTAK = "-7.32,113.28,-6.90,113.72"

ISI_QUERY = """
  nwr["amenity"~"^(hospital|clinic|doctors)$"]%s;
  nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"]%s;
"""

QUERY_BATAS = (
    '[out:json][timeout:90];\n'
    'rel["boundary"="administrative"]["admin_level"="5"]["name"~"Pamekasan"];\n'
    'map_to_area->.a;\n'
    '(' + ISI_QUERY % ("(area.a)", "(area.a)") + ');\n'
    'out center tags;'
)

QUERY_KOTAK = (
    '[out:json][timeout:90];\n'
    '(' + ISI_QUERY % ("(" + KOTAK + ")", "(" + KOTAK + ")") + ');\n'
    'out center tags;'
)

KATA_BUANG = ["telkom", "kantor", "bank", "toko"]


def kirim(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    for server in SERVERS:
        try:
            print("Mencoba server:", server)
            req = urllib.request.Request(
                server, data=data, headers={"User-Agent": "tugas-sig-pamekasan"}
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("Gagal:", e)
    return None


def tentukan_jenis(tags):
    nama = (tags.get("name") or "").lower()
    kata_pustu = ["pustu", "postu", "poskesdes", "polindes", "pembantu", "posyandu"]
    if any(k in nama for k in kata_pustu):
        return "Pustu/Poskesdes"
    if "puskesmas" in nama:
        return "Puskesmas"
    if (
        "rumah sakit" in nama
        or "rsud" in nama
        or "rsu" in nama
        or tags.get("amenity") == "hospital"
        or tags.get("healthcare") == "hospital"
    ):
        return "Rumah Sakit"
    if tags.get("amenity") == "doctors" or tags.get("healthcare") == "doctor":
        return "Praktik Dokter"
    return "Klinik/Lainnya"


def main():
    hasil = kirim(QUERY_BATAS)
    metode = "batas administrasi"
    if hasil is None or not hasil.get("elements"):
        print("Batas administrasi tidak ketemu, pakai kotak koordinat.")
        hasil = kirim(QUERY_KOTAK)
        metode = "kotak koordinat (MASIH BISA ADA DATA LUAR PAMEKASAN)"

    if hasil is None or not hasil.get("elements"):
        print("Data kosong atau semua server gagal. Coba lagi nanti.")
        return

    elemen = hasil["elements"]
    print("Metode:", metode)
    print("Data mentah:", len(elemen))

    kandidat = []
    dibuang = []

    for el in elemen:
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            pusat = el.get("center")
            if not pusat:
                continue
            lat = pusat["lat"]
            lon = pusat["lon"]

        tags = el.get("tags", {})
        nama = tags.get("name", "(tanpa nama)")

        if any(k in nama.lower() for k in KATA_BUANG):
            dibuang.append(nama + " (bukan faskes)")
            continue

        kandidat.append((nama, tentukan_jenis(tags), lat, lon))

    bersih = []
    for nama, jenis, lat, lon in kandidat:
        ganda = False
        for n2, j2, la2, lo2 in bersih:
            if n2.lower() == nama.lower() and abs(la2 - lat) < 0.003 and abs(lo2 - lon) < 0.003:
                ganda = True
                break
        if ganda:
            dibuang.append(nama + " (ganda)")
        else:
            bersih.append((nama, jenis, lat, lon))

    fitur = []
    with open("fasilitas_kesehatan_pamekasan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama", "jenis", "lat", "lon"])
        for nama, jenis, lat, lon in bersih:
            w.writerow([nama, jenis, lat, lon])
            fitur.append(
                {
                    "type": "Feature",
                    "properties": {"nama": nama, "jenis": jenis},
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                }
            )

    with open("fasilitas_kesehatan_pamekasan.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": fitur}, f, ensure_ascii=False)

    print("Dibuang:", len(dibuang))
    for d in dibuang:
        print("  x", d)

    print("Selesai. Total fasilitas bersih:", len(bersih))
    hitung = {}
    for b in bersih:
        hitung[b[1]] = hitung.get(b[1], 0) + 1
    for j, n in hitung.items():
        print("-", j, ":", n)


main()
