import glob
import json
import math
import os
import shutil

FOLDER = [
    os.path.expanduser("~/storage/downloads"),
    os.path.expanduser("~/sig-sumenep"),
]


def buang_z(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [buang_z(x) for x in c]


def luas_ring(ring):
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = math.cos(math.radians(lat0)) * 111.32
    ky = 110.574
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * kx * ring[i + 1][1] * ky - ring[i + 1][0] * kx * ring[i][1] * ky
    return abs(a) / 2.0


def luas_poligon(poly):
    total = luas_ring(poly[0])
    for lubang in poly[1:]:
        total -= luas_ring(lubang)
    return total


def cari_file():
    hasil = []
    for folder in FOLDER:
        for pola in ("*KAB_KOTA*.json", "*KAB_KOTA*.geojson"):
            for f in glob.glob(os.path.join(folder, pola)):
                if f not in hasil:
                    hasil.append(f)
    hasil.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return hasil


def main():
    berkas = cari_file()
    print("File batas kabupaten ditemukan:", len(berkas))
    if not berkas:
        print("Tidak ada file yang namanya mengandung KAB_KOTA di Download.")
        return

    terpilih = None
    for path in berkas:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("Gagal membaca", os.path.basename(path), "-", e)
            continue
        for fit in data.get("features", []):
            prop = fit.get("properties", {}) or {}
            if str(prop.get("kode_kk", "")) == "35.29":
                terpilih = (path, fit)
                break
        if terpilih:
            break

    if not terpilih:
        print("Tidak ada fitur Kabupaten Sumenep (kode 35.29) di file yang ada.")
        return

    path, fit = terpilih
    geom = fit["geometry"]
    if geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        polys = [geom["coordinates"]]

    luas = sum(luas_poligon(p) for p in polys)

    if os.path.exists("batas_sumenep.geojson") and not os.path.exists("batas_sumenep_osm.geojson"):
        shutil.copy("batas_sumenep.geojson", "batas_sumenep_osm.geojson")
        print("Batas lama disimpan sebagai batas_sumenep_osm.geojson")

    baru = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "nama": "Kabupaten Sumenep",
                    "kode_kk": "35.29",
                    "luas_km2_hitung": round(luas, 1),
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": buang_z(polys),
                },
            }
        ],
    }
    with open("batas_sumenep.geojson", "w", encoding="utf-8") as f:
        json.dump(baru, f, ensure_ascii=False)

    print("Sumber:", os.path.basename(path))
    print("Jumlah poligon (daratan dan pulau):", len(polys))
    print("Luas hitungan saya (km2):", round(luas, 1))
    print("Tersimpan: batas_sumenep.geojson")
    print("CATATAN: bandingkan luas ini dengan luas resmi di BPS Sumenep.")


main()
