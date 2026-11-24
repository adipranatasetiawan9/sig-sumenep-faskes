import csv
import json
import math

# Luas Kabupaten Pamekasan dalam km2 (angka dari ingatan, mohon dicek ke BPS lalu ganti kalau beda)
LUAS_KM2 = 792.24
RADIUS_BUFFER_KM = [3, 5]
R_BUMI = 6371.0088


def jarak_km(la1, lo1, la2, lo2):
    p1 = math.radians(la1)
    p2 = math.radians(la2)
    dp = p2 - p1
    dl = math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_BUMI * math.asin(math.sqrt(a))


def baca(nama_file):
    hasil = []
    with open(nama_file, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hasil.append((r["nama"], r["jenis"], float(r["lat"]), float(r["lon"])))
    return hasil


def lingkaran(lat, lon, radius_km, langkah=36):
    d = radius_km / R_BUMI
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    titik = []
    for i in range(langkah):
        b = 2 * math.pi * i / langkah
        p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
        l2 = l1 + math.atan2(
            math.sin(b) * math.sin(d) * math.cos(p1),
            math.cos(d) - math.sin(p1) * math.sin(p2),
        )
        titik.append([round(math.degrees(l2), 6), round(math.degrees(p2), 6)])
    titik.append(titik[0])
    return titik


def main():
    data = baca("fasilitas_gabungan.csv")
    n = len(data)
    print("Jumlah fasilitas:", n)
    if n < 2:
        print("Data kurang dari 2 titik.")
        return

    # 1. Nearest neighbor
    hasil_nn = []
    for i in range(n):
        terdekat = None
        jmin = 1e9
        for j in range(n):
            if i == j:
                continue
            j_km = jarak_km(data[i][2], data[i][3], data[j][2], data[j][3])
            if j_km < jmin:
                jmin = j_km
                terdekat = data[j][0]
        hasil_nn.append((data[i][0], terdekat, jmin))

    d_obs = sum(x[2] for x in hasil_nn) / n
    d_exp = 0.5 / math.sqrt(n / LUAS_KM2)
    rasio = d_obs / d_exp
    se = 0.26136 * math.sqrt(LUAS_KM2) / n
    z = (d_obs - d_exp) / se

    if abs(z) < 1.96:
        pola = "ACAK (random)"
    elif rasio < 1:
        pola = "MENGELOMPOK (clustered)"
    else:
        pola = "MENYEBAR (dispersed)"

    print("")
    print("=== NEAREST NEIGHBOR ===")
    print("Jarak rata-rata teramati (km):", round(d_obs, 3))
    print("Jarak rata-rata harapan  (km):", round(d_exp, 3))
    print("Rasio NN (R):", round(rasio, 3))
    print("Nilai z:", round(z, 3))
    print("Pola sebaran:", pola)

    print("")
    print("=== 5 TETANGGA TERDEKAT (jarak paling pendek) ===")
    urut = sorted(hasil_nn, key=lambda x: x[2])
    for nama, tetangga, j_km in urut[:5]:
        print("-", nama, "->", tetangga, ":", round(j_km, 2), "km")

    print("")
    print("=== 5 FASILITAS PALING TERPENCIL (jarak terjauh) ===")
    for nama, tetangga, j_km in urut[-5:][::-1]:
        print("-", nama, "->", tetangga, ":", round(j_km, 2), "km")

    with open("hasil_nearest_neighbor.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama", "tetangga_terdekat", "jarak_km"])
        for nama, tetangga, j_km in hasil_nn:
            w.writerow([nama, tetangga, round(j_km, 3)])

    # 2. Buffer
    print("")
    print("=== BUFFER ===")
    for r in RADIUS_BUFFER_KM:
        fitur = []
        for nama, jenis, la, lo in data:
            fitur.append(
                {
                    "type": "Feature",
                    "properties": {"nama": nama, "jenis": jenis, "radius_km": r},
                    "geometry": {"type": "Polygon", "coordinates": [lingkaran(la, lo, r)]},
                }
            )
        nama_file = "buffer_%dkm.geojson" % r
        with open(nama_file, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": fitur}, f)
        print("Tersimpan:", nama_file)

    print("")
    print("Selesai. File hasil: hasil_nearest_neighbor.csv, buffer_3km.geojson, buffer_5km.geojson")


main()
