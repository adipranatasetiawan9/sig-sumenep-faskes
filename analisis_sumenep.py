import csv
import json
import math
import os

# =====================================================================
# PENGATURAN (boleh diubah)
# =====================================================================
LUAS_RESMI_KM2 = None            # isi angka BPS bila sudah ada, misalnya 2093.45
RADIUS_PUSKESMAS_KM = [2, 5]     # radius buffer puskesmas (km)
RADIUS_RS_KM = [20]              # radius buffer rumah sakit (km)
RADIUS_SERVICE_KM = [1.0]        # pendekatan "service area" 15 menit jalan kaki (km)
LANGKAH_GRID_KM = 1.0            # ketelitian hitungan persen cakupan
R_BUMI = 6371.0088

HASIL_TEKS = []


def cetak(*bagian):
    teks = " ".join(str(b) for b in bagian)
    print(teks)
    HASIL_TEKS.append(teks)


# =====================================================================
# BACA DATA
# =====================================================================
def baca_titik(nama_file):
    hasil = []
    kosong = []
    if not os.path.exists(nama_file):
        print("File tidak ada:", nama_file)
        return hasil, kosong
    with open(nama_file, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                hasil.append(
                    (r["nama"].strip(), r["jenis"].strip(), float(r["lat"]), float(r["lon"]))
                )
            except Exception:
                if r.get("nama"):
                    kosong.append(r["nama"].strip())
    return hasil, kosong


def luas_ring(ring):
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = math.cos(math.radians(lat0)) * 111.32
    ky = 110.574
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * kx * ring[i + 1][1] * ky - ring[i + 1][0] * kx * ring[i][1] * ky
    return abs(a) / 2.0


def muat_poligon(nama_file, maks_titik=3000):
    if not os.path.exists(nama_file):
        return []
    with open(nama_file, encoding="utf-8") as f:
        data = json.load(f)
    hasil = []
    for fit in data.get("features", []):
        g = fit.get("geometry") or {}
        if g.get("type") == "MultiPolygon":
            polys = g["coordinates"]
        elif g.get("type") == "Polygon":
            polys = [g["coordinates"]]
        else:
            continue
        daftar = []
        for p in polys:
            cinc = []
            for r in p:
                rr = [(c[0], c[1]) for c in r]
                cinc.append(rr)
            luas = luas_ring(cinc[0])
            for h in cinc[1:]:
                luas -= luas_ring(h)
            ringan = []
            for rr in cinc:
                if len(rr) > maks_titik:
                    k = int(math.ceil(len(rr) / float(maks_titik)))
                    rr = rr[::k]
                    if rr[0] != rr[-1]:
                        rr.append(rr[0])
                ringan.append(rr)
            xs = [c[0] for c in ringan[0]]
            ys = [c[1] for c in ringan[0]]
            daftar.append(
                {"rings": ringan, "bbox": (min(xs), min(ys), max(xs), max(ys)), "luas": luas}
            )
        hasil.append((fit.get("properties", {}) or {}, daftar))
    return hasil


# =====================================================================
# GEOMETRI
# =====================================================================
def jarak_km(la1, lo1, la2, lo2):
    p1 = math.radians(la1)
    p2 = math.radians(la2)
    dp = p2 - p1
    dl = math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_BUMI * math.asin(math.sqrt(a))


def jarak_cepat(la1, lo1, la2, lo2):
    dx = (lo1 - lo2) * math.cos(math.radians((la1 + la2) / 2.0)) * 111.32
    dy = (la1 - la2) * 110.574
    return math.sqrt(dx * dx + dy * dy)


def dalam_ring(x, y, ring):
    dalam = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                dalam = not dalam
        j = i
    return dalam


def dalam_poly(x, y, poly):
    b = poly["bbox"]
    if x < b[0] or x > b[2] or y < b[1] or y > b[3]:
        return False
    if not dalam_ring(x, y, poly["rings"][0]):
        return False
    for h in poly["rings"][1:]:
        if dalam_ring(x, y, h):
            return False
    return True


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


def simpan_json(nama_file, isi):
    with open(nama_file, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False)


def normal(nama):
    s = "".join(c for c in nama.lower() if c.isalpha())
    alias = {"giligenting": "giliginting", "gilienting": "giliginting"}
    return alias.get(s, s)


# =====================================================================
# 1. GABUNG DATA
# =====================================================================
def gabung_data():
    manual, kosong = baca_titik("data_manual_sumenep.csv")
    osm, _ = baca_titik("fasilitas_osm_sumenep.csv")
    cetak("Dari OSM:", len(osm), "| Manual (Google Maps):", len(manual))
    if kosong:
        cetak("Belum ada koordinat:", ", ".join(kosong))

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

    wajar = []
    for n, j, la, lo in gabung:
        if -7.5 <= la <= -5.2 and 113.4 <= lo <= 116.2:
            wajar.append((n, j, la, lo))
        else:
            cetak("Dibuang (di luar kotak Sumenep):", n, la, lo)
    return wajar


def tentukan_kecamatan(fasilitas, kec):
    hasil = []
    luar = []
    for n, j, la, lo in fasilitas:
        nama_kec = None
        for prop, daftar in kec:
            if any(dalam_poly(lo, la, p) for p in daftar):
                nama_kec = prop.get("nama") or prop.get("kecamatan") or "?"
                break
        if nama_kec is None:
            nama_kec = "(di luar poligon)"
            luar.append(n)
        hasil.append((n, j, la, lo, nama_kec))
    return hasil, luar


# =====================================================================
# 2. NEAREST NEIGHBOR
# =====================================================================
def nearest_neighbor(titik, luas_km2):
    n = len(titik)
    jarak = []
    for i in range(n):
        jmin = 1e9
        tetangga = ""
        for j in range(n):
            if i == j:
                continue
            d = jarak_km(titik[i][2], titik[i][3], titik[j][2], titik[j][3])
            if d < jmin:
                jmin = d
                tetangga = titik[j][0]
        jarak.append((titik[i][0], tetangga, jmin))
    d_obs = sum(x[2] for x in jarak) / n
    d_exp = 0.5 / math.sqrt(n / luas_km2)
    r = d_obs / d_exp
    se = 0.26136 * math.sqrt(luas_km2) / n
    z = (d_obs - d_exp) / se
    p = math.erfc(abs(z) / math.sqrt(2.0))
    if p >= 0.05:
        pola = "ACAK (tidak signifikan)"
    elif r < 1:
        pola = "MENGELOMPOK (clustered)"
    else:
        pola = "MENYEBAR (dispersed)"
    return jarak, d_obs, d_exp, r, z, p, pola


# =====================================================================
# 3. GRID DARAT UNTUK PERSEN CAKUPAN
# =====================================================================
def grid_darat(polys_kab, langkah_km):
    minx = min(p["bbox"][0] for p in polys_kab)
    miny = min(p["bbox"][1] for p in polys_kab)
    maxx = max(p["bbox"][2] for p in polys_kab)
    maxy = max(p["bbox"][3] for p in polys_kab)
    titik = []
    lat = miny
    while lat <= maxy:
        dlon = langkah_km / (111.32 * math.cos(math.radians(lat)))
        lon = minx
        while lon <= maxx:
            for p in polys_kab:
                if dalam_poly(lon, lat, p):
                    titik.append((lat, lon))
                    break
            lon += dlon
        lat += langkah_km / 110.574
    return titik


def persen_cakupan(titik_darat, fasilitas, radius_km):
    if not titik_darat or not fasilitas:
        return 0.0
    ok = 0
    for la, lo in titik_darat:
        for fa, fo in fasilitas:
            if jarak_cepat(la, lo, fa, fo) <= radius_km:
                ok += 1
                break
    return 100.0 * ok / len(titik_darat)


# =====================================================================
# PROGRAM UTAMA
# =====================================================================
def main():
    cetak("=== 1. GABUNG DATA FASILITAS ===")
    fasilitas = gabung_data()
    if not fasilitas:
        cetak("Tidak ada data fasilitas. Cek data_manual_sumenep.csv dan fasilitas_osm_sumenep.csv.")
        return

    kab = muat_poligon("batas_sumenep.geojson")
    kec = muat_poligon("batas_kecamatan.geojson")
    if not kab:
        cetak("batas_sumenep.geojson tidak ditemukan. Jalankan siapkan_batas.py dulu.")
        return
    polys_kab = []
    for prop, daftar in kab:
        polys_kab.extend(daftar)

    luas_hitung = sum(p["luas"] for p in polys_kab)
    luas_pakai = LUAS_RESMI_KM2 if LUAS_RESMI_KM2 else luas_hitung
    cetak("Luas wilayah dari poligon (km2):", round(luas_hitung, 1))
    if LUAS_RESMI_KM2:
        cetak("Luas resmi yang dipakai (km2):", LUAS_RESMI_KM2)
    else:
        cetak("PERHATIAN: memakai luas hitungan, bukan angka BPS (isi LUAS_RESMI_KM2 di atas skrip).")

    if kec:
        fasilitas5, luar = tentukan_kecamatan(fasilitas, kec)
        if luar:
            cetak("Titik di luar poligon kecamatan (mungkin di tepi pantai):", ", ".join(luar))
    else:
        cetak("batas_kecamatan.geojson belum ada, kolom kecamatan dikosongkan.")
        fasilitas5 = [(n, j, la, lo, "") for n, j, la, lo in fasilitas]

    with open("fasilitas_gabungan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama", "jenis", "lat", "lon", "kecamatan"])
        for n, j, la, lo, k in fasilitas5:
            w.writerow([n, j, la, lo, k])
    fitur = []
    for n, j, la, lo, k in fasilitas5:
        fitur.append(
            {
                "type": "Feature",
                "properties": {"nama": n, "jenis": j, "kecamatan": k},
                "geometry": {"type": "Point", "coordinates": [lo, la]},
            }
        )
    simpan_json("fasilitas_gabungan.geojson", {"type": "FeatureCollection", "features": fitur})

    hitung = {}
    for n, j, la, lo, k in fasilitas5:
        hitung[j] = hitung.get(j, 0) + 1
    cetak("Total fasilitas gabungan:", len(fasilitas5))
    for j, c in hitung.items():
        cetak("-", j, ":", c)

    puskesmas = [x for x in fasilitas5 if x[1] == "Puskesmas"]
    rs = [x for x in fasilitas5 if x[1] == "Rumah Sakit"]

    # ---------------- tabel per kecamatan ----------------
    if kec:
        cetak("")
        cetak("=== 2. TABEL PER KECAMATAN (seperti Tabel 3 jurnal) ===")
        penduduk = {}
        if os.path.exists("data_penduduk_sumenep.csv"):
            with open("data_penduduk_sumenep.csv", newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    try:
                        penduduk[normal(r["kecamatan"])] = float(r["penduduk"])
                    except Exception:
                        pass
        else:
            cetak("Catatan: data_penduduk_sumenep.csv belum ada, kolom penduduk dikosongkan.")

        baris = []
        nama_kec = sorted(set((prop.get("nama") or prop.get("kecamatan") or "?") for prop, d in kec))
        for nk in nama_kec:
            n_p = sum(1 for x in puskesmas if x[4] == nk)
            n_r = sum(1 for x in rs if x[4] == nk)
            n_all = sum(1 for x in fasilitas5 if x[4] == nk)
            pend = penduduk.get(normal(nk))
            per100 = ""
            if pend:
                per100 = round(n_p / pend * 100000.0, 2)
            baris.append([nk, n_p, n_r, n_all, int(pend) if pend else "", per100])
        with open("tabel_kecamatan.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["kecamatan", "puskesmas", "rumah_sakit", "semua_fasilitas", "penduduk", "puskesmas_per_100rb"])
            w.writerows(baris)
        for b in baris:
            cetak("  %-14s puskesmas=%d  RS=%d  semua=%d  penduduk=%s  per100rb=%s" % tuple(b))
        tanpa = [b[0] for b in baris if b[1] == 0]
        if tanpa:
            cetak("Kecamatan tanpa puskesmas di data:", ", ".join(tanpa))

    # ---------------- nearest neighbor ----------------
    cetak("")
    cetak("=== 3. NEAREST NEIGHBOR (seperti Gambar 5 jurnal) ===")
    terbesar = max(polys_kab, key=lambda p: p["luas"])
    daratan = [
        x for x in fasilitas5 if dalam_poly(x[3], x[2], terbesar)
    ]
    cetak("Poligon terbesar (daratan Madura bagian Sumenep) luas km2:", round(terbesar["luas"], 1))

    ringkas = []
    semua_jarak = []
    skenario = [
        ("Seluruh kabupaten", fasilitas5, luas_pakai),
        ("Daratan Madura saja", daratan, terbesar["luas"]),
    ]
    for nama_s, data_s, luas_s in skenario:
        cetak("")
        cetak("-- Wilayah:", nama_s, "(luas %.1f km2)" % luas_s)
        himpunan = [
            ("Puskesmas", [x for x in data_s if x[1] == "Puskesmas"]),
            ("Rumah Sakit", [x for x in data_s if x[1] == "Rumah Sakit"]),
            ("Semua fasilitas", data_s),
        ]
        for nama_k, titik in himpunan:
            if len(titik) < 5:
                cetak("   %-16s n=%d : terlalu sedikit titik untuk uji statistik" % (nama_k, len(titik)))
                continue
            jarak, d_obs, d_exp, r, z, p, pola = nearest_neighbor(titik, luas_s)
            cetak(
                "   %-16s n=%d  d_obs=%.2f km  d_exp=%.2f km  NNR=%.3f  z=%.3f  p=%.4f  -> %s"
                % (nama_k, len(titik), d_obs, d_exp, r, z, p, pola)
            )
            ringkas.append([nama_s, nama_k, len(titik), round(d_obs, 3), round(d_exp, 3), round(r, 3), round(z, 3), round(p, 4), pola])
            if nama_s == "Seluruh kabupaten" and nama_k == "Semua fasilitas":
                semua_jarak = jarak

    with open("hasil_nn_ringkas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["wilayah", "kategori", "n", "d_obs_km", "d_exp_km", "NNR", "z", "p", "pola"])
        w.writerows(ringkas)
    with open("hasil_nearest_neighbor.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama", "tetangga_terdekat", "jarak_km"])
        for nm, tt, jk in semua_jarak:
            w.writerow([nm, tt, round(jk, 3)])

    if semua_jarak:
        urut = sorted(semua_jarak, key=lambda x: x[2], reverse=True)
        cetak("")
        cetak("5 fasilitas paling terpencil (jarak ke tetangga terdekat):")
        for nm, tt, jk in urut[:5]:
            cetak("   -", nm, "->", tt, ":", round(jk, 2), "km")

    # ---------------- buffer dan cakupan ----------------
    cetak("")
    cetak("=== 4. BUFFER DAN PERSEN CAKUPAN WILAYAH (seperti Gambar 6, 7 dan 8) ===")
    cetak("Menghitung titik-titik daratan (grid %.1f km)..." % LANGKAH_GRID_KM)
    darat = grid_darat(polys_kab, LANGKAH_GRID_KM)
    cetak("Titik daratan terhitung:", len(darat), "(perkiraan luas %.0f km2)" % (len(darat) * LANGKAH_GRID_KM ** 2))

    titik_p = [(x[2], x[3]) for x in puskesmas]
    titik_r = [(x[2], x[3]) for x in rs]
    cakupan = []
    daftar_buffer = []
    for r in RADIUS_PUSKESMAS_KM:
        daftar_buffer.append(("Puskesmas", r, puskesmas, "buffer_puskesmas_%gkm.geojson" % r))
    for r in RADIUS_RS_KM:
        daftar_buffer.append(("Rumah Sakit", r, rs, "buffer_rs_%gkm.geojson" % r))
    for r in RADIUS_SERVICE_KM:
        daftar_buffer.append(("Service area (pendekatan lingkaran)", r, puskesmas, "service_area_%gkm.geojson" % r))

    for nama_b, r, data_b, nama_file in daftar_buffer:
        titik_b = [(x[2], x[3]) for x in data_b]
        persen = persen_cakupan(darat, titik_b, r)
        cetak("  %-36s radius %g km: tercakup %.1f%% | tidak tercakup %.1f%%" % (nama_b, r, persen, 100 - persen))
        cakupan.append([nama_b, r, round(persen, 2), round(100 - persen, 2)])
        fb = []
        for x in data_b:
            fb.append(
                {
                    "type": "Feature",
                    "properties": {"nama": x[0], "jenis": x[1], "radius_km": r},
                    "geometry": {"type": "Polygon", "coordinates": [lingkaran(x[2], x[3], r)]},
                }
            )
        simpan_json(nama_file, {"type": "FeatureCollection", "features": fb})

    gabungan = titik_p + titik_r
    persen_g = persen_cakupan(darat, gabungan, max(RADIUS_PUSKESMAS_KM))
    cetak("  Puskesmas + RS, radius %g km: tercakup %.1f%%" % (max(RADIUS_PUSKESMAS_KM), persen_g))
    cakupan.append(["Puskesmas + RS", max(RADIUS_PUSKESMAS_KM), round(persen_g, 2), round(100 - persen_g, 2)])

    with open("hasil_cakupan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kategori", "radius_km", "persen_tercakup", "persen_tidak_tercakup"])
        w.writerows(cakupan)

    cetak("")
    cetak("CATATAN KETERBATASAN:")
    cetak("- Buffer dan service area berupa lingkaran garis lurus, bukan jarak lewat jalan.")
    cetak("- Radius buffer mengikuti jurnal acuan (standar Yordania) sebagai pembanding.")
    cetak("- Persen cakupan dihitung dari titik grid %.1f km di atas daratan." % LANGKAH_GRID_KM)
    cetak("- Data fasilitas masih dari OSM dan Google Maps, belum data resmi Dinkes.")

    with open("ringkasan_analisis.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(HASIL_TEKS))
    print("")
    print("Selesai. Hasil tersimpan: fasilitas_gabungan.csv/.geojson, tabel_kecamatan.csv,")
    print("hasil_nn_ringkas.csv, hasil_nearest_neighbor.csv, hasil_cakupan.csv,")
    print("ringkasan_analisis.txt dan file buffer*.geojson / service_area*.geojson")


main()
