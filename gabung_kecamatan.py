import glob
import json
import os

FOLDER = [
    os.path.expanduser("~/storage/downloads"),
    os.path.expanduser("~/sig-sumenep"),
]

POLA = [
    "Kecamatan_*.json",
    "Kecamatan_*.geojson",
    "*KECAMATAN*.json",
    "*KECAMATAN*.geojson",
]


def buang_z(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [buang_z(x) for x in c]


def milik_sumenep(prop):
    if str(prop.get("kode_kk", "")) == "35.29":
        return True
    return str(prop.get("kab_kota", "")).strip().lower() == "sumenep"


def cari_file():
    hasil = []
    for folder in FOLDER:
        for pola in POLA:
            for f in glob.glob(os.path.join(folder, pola)):
                if f not in hasil:
                    hasil.append(f)
    return hasil


def main():
    berkas = cari_file()
    print("File batas kecamatan ditemukan:", len(berkas))
    if not berkas:
        print("Tidak ada file. Pastikan unduhan ada di folder Download")
        print("dan namanya mengandung kata Kecamatan.")
        return

    terkumpul = {}
    for path in berkas:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("Gagal membaca", os.path.basename(path), "-", e)
            continue
        fitur = data.get("features", [])
        terpakai = 0
        for fit in fitur:
            prop = fit.get("properties", {}) or {}
            geom = fit.get("geometry")
            if not geom or not milik_sumenep(prop):
                continue
            kunci = prop.get("kode_kec") or prop.get("nama") or prop.get("kecamatan")
            if kunci in terkumpul:
                continue
            nama = prop.get("kecamatan") or prop.get("nama") or "(tanpa nama)"
            terkumpul[kunci] = {
                "type": "Feature",
                "properties": {"nama": nama, "kode_kec": prop.get("kode_kec", "")},
                "geometry": {
                    "type": geom["type"],
                    "coordinates": buang_z(geom["coordinates"]),
                },
            }
            terpakai += 1
        print("-", os.path.basename(path), ":", len(fitur), "fitur,", terpakai, "baru dipakai")

    if not terkumpul:
        print("Tidak ada kecamatan Sumenep yang terbaca.")
        return

    hasil = sorted(terkumpul.values(), key=lambda x: x["properties"]["nama"])
    with open("batas_kecamatan.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": hasil}, f, ensure_ascii=False)

    print("")
    print("Jumlah kecamatan terkumpul:", len(hasil), "(target 27)")
    print("Nama:", ", ".join(x["properties"]["nama"] for x in hasil))
    print("Tersimpan: batas_kecamatan.geojson")
    if len(hasil) < 27:
        print("Masih kurang", 27 - len(hasil), "kecamatan. Unduh yang kurang, lalu jalankan lagi.")


main()
