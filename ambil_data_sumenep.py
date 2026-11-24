import csv
import json
import math
import time
import urllib.parse
import urllib.request

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

AWAL = (
    '[out:json][timeout:180];\n'
    'rel["boundary"="administrative"]["admin_level"="5"]["name"~"Sumenep"];\n'
    'map_to_area->.a;\n'
)

QUERY_FASILITAS = AWAL + (
    '(\n'
    '  nwr["amenity"~"^(hospital|clinic|doctors)$"](area.a);\n'
    '  nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"](area.a);\n'
    '  nwr["name"~"puskesmas|pustu|poskesdes|polindes|rumah sakit|rsud",i](area.a);\n'
    ');\n'
    'out center tags;'
)

QUERY_BATAS_KAB = (
    '[out:json][timeout:180];\n'
    'rel["boundary"="administrative"]["admin_level"="5"]["name"~"Sumenep"];\n'
    'out geom;'
)

QUERY_KECAMATAN = AWAL + (
    'rel["boundary"="administrative"]["admin_level"="6"](area.a);\n'
    'out geom;'
)

KATA_BUANG = ["telkom", "kantor", "bank", "toko"]


def kirim(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    for server in SERVERS:
        try:
            print("Mencoba server:", server)
            req = urllib.request.Request(
                server, data=data, headers={"User-Agent": "tugas-sig-sumenep"}
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("Gagal:", e)
    return None


def rangkai(ways):
    sisa = [w[:] for w in ways if len(w) >= 2]
    cincin = []
    while sisa:
        cur = sisa.pop(0)
        berubah = True
        while berubah and cur[0] != cur[-1]:
            berubah = False
            for i, w in enumerate(sisa):
                if w[0] == cur[-1]:
                    cur = cur + w[1:]
                elif w[-1] == cur[-1]:
                    cur = cur + w[::-1][1:]
                elif w[-1] == cur[0]:
                    cur = w[:-1] + cur
                elif w[0] == cur[0]:
                    cur = w[::-1][:-1] + cur
                else:
                    continue
                sisa.pop(i)
                berubah = True
                break
        if len(cur) >= 4 and cur[0] == cur[-1]:
            cincin.append(cur)
    return cincin


def ambil_cincin(rel):
    ways = []
    for m in rel.get("members", []):
        if m.get("type") == "way" and m.get("role") in ("outer", "") and m.get("geometry"):
            ways.append([(p["lon"], p["lat"]) for p in m["geometry"]])
    return rangkai(ways)


def luas_km2(cincin):
    lat0 = sum(p[1] for p in cincin) / len(cincin)
    kx = math.cos(math.radians(lat0)) * 111.32
    ky = 110.574
    a = 0.0
    for i in range(len(cincin) - 1):
        x1 = cincin[i][0] * kx
        y1 = cincin[i][1] * ky
        x2 = cincin[i + 1][0] * kx
        y2 = cincin[i + 1][1] * ky
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def fitur_dari_relasi(rel, nama):
    cincin = ambil_cincin(rel)
    if not cincin:
        return None, 0.0
    total = sum(luas_km2(c) for c in cincin)
    fitur = {
        "type": "Feature",
        "properties": {"nama": nama, "luas_km2_osm": round(total, 2)},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[p[0], p[1]] for p in c]] for c in cincin],
        },
    }
    return fitur, total


def tentukan_jenis(tags):
    nama = (tags.get("name") or "").lower()
    kata_pustu = ["pustu", "poskesdes", "polindes", "pembantu"]
    if any(k in nama for k in kata_pustu):
        return "Pustu/Poskesdes"
    if "puskesmas" in nama:
        return "Puskesmas"
    if (
        "rumah sakit" in nama
        or "rsud" in nama
        or tags.get("amenity") == "hospital"
        or tags.get("healthcare") == "hospital"
    ):
        return "Rumah Sakit"
    return "Klinik/Lainnya"


def simpan_json(nama_file, isi):
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False)


def langkah_batas_kabupaten():
    print("")
    print("=== 1. BATAS KABUPATEN SUMENEP ===")
    hasil = kirim(QUERY_BATAS_KAB)
    if not hasil or not hasil.get("elements"):
        print("Batas kabupaten tidak ketemu.")
        return
    rel = hasil["elements"][0]
    nama = rel.get("tags", {}).get("name", "Kabupaten Sumenep")
    fitur, luas = fitur_dari_relasi(rel, nama)
    if fitur is None:
        print("Batas ketemu tapi gagal dirangkai jadi poligon.")
        return
    simpan_json("batas_sumenep.geojson", {"type": "FeatureCollection", "features": [fitur]})
    print("Nama di OSM:", nama)
    print("Jumlah poligon (pulau/daratan):", len(fitur["geometry"]["coordinates"]))
    print("Luas dari batas OSM (km2):", round(luas, 1))
    print("Tersimpan: batas_sumenep.geojson")
    print("CATATAN: bandingkan luas ini dengan luas resmi di BPS.")


def langkah_fasilitas():
    print("")
    print("=== 2. FASILITAS KESEHATAN ===")
    hasil = kirim(QUERY_FASILITAS)
    if not hasil or not hasil.get("elements"):
        print("Data fasilitas kosong atau semua server gagal.")
        return
    elemen = hasil["elements"]
    print("Data mentah:", len(elemen))

    kandidat = []
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
            continue
        kandidat.append((nama, tentukan_jenis(tags), lat, lon))

    bersih = []
    for nama, jenis, lat, lon in kandidat:
        ganda = False
        for n2, j2, la2, lo2 in bersih:
            if n2.lower() == nama.lower() and abs(la2 - lat) < 0.002 and abs(lo2 - lon) < 0.002:
                ganda = True
                break
        if not ganda:
            bersih.append((nama, jenis, lat, lon))

    fitur = []
    with open("fasilitas_osm_sumenep.csv", "w", newline="", encoding="utf-8") as f:
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
    simpan_json("fasilitas_osm_sumenep.geojson", {"type": "FeatureCollection", "features": fitur})

    print("Total fasilitas bersih:", len(bersih))
    hitung = {}
    for b in bersih:
        hitung[b[1]] = hitung.get(b[1], 0) + 1
    for j, n in hitung.items():
        print("-", j, ":", n)

    print("")
    print("Daftar Puskesmas dan Rumah Sakit dari OSM:")
    for nama, jenis, lat, lon in bersih:
        if jenis in ("Puskesmas", "Rumah Sakit"):
            print(" *", jenis, "|", nama)
    print("Tersimpan: fasilitas_osm_sumenep.csv dan .geojson")


def langkah_kecamatan():
    print("")
    print("=== 3. BATAS KECAMATAN ===")
    hasil = kirim(QUERY_KECAMATAN)
    if not hasil or not hasil.get("elements"):
        print("Batas kecamatan tidak ketemu atau server gagal. Bisa dicoba lagi nanti.")
        return
    fitur = []
    nama_list = []
    for rel in hasil["elements"]:
        tags = rel.get("tags", {})
        nama = tags.get("name", "")
        if nama.lower().startswith("kecamatan "):
            nama = nama[10:]
        f, luas = fitur_dari_relasi(rel, nama)
        if f is not None:
            fitur.append(f)
            nama_list.append(nama)
    if not fitur:
        print("Relasi ketemu tapi gagal dirangkai jadi poligon.")
        return
    simpan_json("batas_kecamatan.geojson", {"type": "FeatureCollection", "features": fitur})
    print("Jumlah kecamatan terbaca:", len(fitur), "(seharusnya 27)")
    print("Nama:", ", ".join(sorted(nama_list)))
    print("Tersimpan: batas_kecamatan.geojson")


def main():
    langkah_batas_kabupaten()
    time.sleep(3)
    langkah_fasilitas()
    time.sleep(3)
    langkah_kecamatan()
    print("")
    print("Selesai.")


main()
