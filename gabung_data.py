import csv
import json


def baca(nama_file):
    hasil = []
    try:
        with open(nama_file, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    hasil.append(
                        (r["nama"].strip(), r["jenis"].strip(), float(r["lat"]), float(r["lon"]))
                    )
                except Exception:
                    print("Baris dilewati (format salah):", r)
    except FileNotFoundError:
        print("File tidak ada:", nama_file)
    return hasil


def dalam_pamekasan(lat, lon):
    return -7.32 <= lat <= -6.80 and 113.28 <= lon <= 113.72


def main():
    osm = baca("fasilitas_kesehatan_pamekasan.csv")
    manual = baca("data_manual.csv")
    print("Dari OSM:", len(osm), "| Manual:", len(manual))

    gabung = list(manual)
    for n, j, la, lo in osm:
        ganda = False
        for n2, j2, la2, lo2 in gabung:
            dekat = abs(la - la2) < 0.003 and abs(lo - lo2) < 0.003
            if dekat and (n.lower() == n2.lower() or j == j2):
                ganda = True
                break
        if not ganda:
            gabung.append((n, j, la, lo))

    final = []
    for n, j, la, lo in gabung:
        if dalam_pamekasan(la, lo):
            final.append((n, j, la, lo))
        else:
            print("Di luar kotak Pamekasan, dibuang:", n)

    fitur = []
    with open("fasilitas_gabungan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama", "jenis", "lat", "lon"])
        for n, j, la, lo in final:
            w.writerow([n, j, la, lo])
            fitur.append(
                {
                    "type": "Feature",
                    "properties": {"nama": n, "jenis": j},
                    "geometry": {"type": "Point", "coordinates": [lo, la]},
                }
            )

    with open("fasilitas_gabungan.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": fitur}, f, ensure_ascii=False)

    print("Selesai. Total fasilitas gabungan:", len(final))
    hitung = {}
    for x in final:
        hitung[x[1]] = hitung.get(x[1], 0) + 1
    for j, n in hitung.items():
        print("-", j, ":", n)


main()
