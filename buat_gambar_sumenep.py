import csv
import html
import json
import math
import os

# =====================================================================
# PENGATURAN
# =====================================================================
RADIUS_PUSKESMAS_KM = [2, 5]
RADIUS_RS_KM = 20
RADIUS_SERVICE_KM = 1.0
LEBAR_PANEL = 400

# (bujur_min, bujur_maks, lintang_min, lintang_maks)
WILAYAH = {
    "madura": (113.55, 114.20, -7.28, -6.80),
    "kabupaten": (113.50, 116.00, -7.30, -5.45),
}
NAMA_WILAYAH = {
    "madura": "Daratan Madura bagian Sumenep",
    "kabupaten": "Seluruh Kabupaten Sumenep (daratan dan kepulauan)",
}
CAP_TITIK = {"madura": 900, "kabupaten": 250}

WARNA_P = "#1a9850"
WARNA_R = "#d73027"
WARNA_B2 = "#2b83ba"
WARNA_B5 = "#f0a030"
WARNA_RS = "#d73027"
WARNA_SA = "#7b3294"


def baca_geojson(nama_file):
    if os.path.exists(nama_file):
        with open(nama_file, encoding="utf-8") as f:
            return json.load(f)
    return {"type": "FeatureCollection", "features": []}


def baca_csv(nama_file):
    if not os.path.exists(nama_file):
        return []
    with open(nama_file, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fmt(x, d=2):
    return ("%." + str(d) + "f") % float(x)


def koma(x, d=2):
    return fmt(x, d).replace(".", ",")


def esc(s):
    return html.escape(str(s), quote=True)


# =====================================================================
# DATA
# =====================================================================
fas = baca_geojson("fasilitas_gabungan.geojson")
kec = baca_geojson("batas_kecamatan.geojson")

puskesmas = []
rs = []
for f in fas["features"]:
    lon, lat = f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1]
    p = f["properties"]
    item = (p.get("nama", ""), lon, lat)
    if p.get("jenis") == "Puskesmas":
        puskesmas.append(item)
    elif p.get("jenis") == "Rumah Sakit":
        rs.append(item)


def ringkas(ring, cap):
    if len(ring) <= cap:
        return ring
    k = int(math.ceil(len(ring) / float(cap)))
    r = ring[::k]
    if r[0] != r[-1]:
        r.append(r[0])
    return r


def siapkan_kecamatan(cap):
    hasil = []
    for fit in kec["features"]:
        g = fit.get("geometry") or {}
        if g.get("type") == "MultiPolygon":
            polys = g["coordinates"]
        elif g.get("type") == "Polygon":
            polys = [g["coordinates"]]
        else:
            continue
        daftar = []
        for poly in polys:
            cinc = [ringkas([(c[0], c[1]) for c in r], cap) for r in poly]
            xs = [c[0] for c in cinc[0]]
            ys = [c[1] for c in cinc[0]]
            daftar.append({"rings": cinc, "bbox": (min(xs), min(ys), max(xs), max(ys))})
        nama = (fit.get("properties") or {}).get("nama", "")
        hasil.append((nama, daftar))
    return hasil


def luas_ring(ring):
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(a) / 2.0


# =====================================================================
# PROYEKSI DAN PANEL PETA
# =====================================================================
def proyeksi(ext, lebar):
    lon0, lon1, lat0, lat1 = ext
    latmid = (lat0 + lat1) / 2.0
    kmlon = 111.32 * math.cos(math.radians(latmid))
    px_km = lebar / ((lon1 - lon0) * kmlon)
    tinggi = (lat1 - lat0) * 110.574 * px_km

    def p(lon, lat):
        return ((lon - lon0) * kmlon * px_km, (lat1 - lat) * 110.574 * px_km)

    return p, px_km, tinggi


def dalam_ext(lon, lat, ext, margin=0.0):
    return (ext[0] - margin) <= lon <= (ext[1] + margin) and (ext[2] - margin) <= lat <= (ext[3] + margin)


def lapis_darat(kec_siap, ext, p):
    bagian = []
    for nama, daftar in kec_siap:
        d = []
        for poly in daftar:
            b = poly["bbox"]
            if b[2] < ext[0] or b[0] > ext[1] or b[3] < ext[2] or b[1] > ext[3]:
                continue
            for r in poly["rings"]:
                pts = []
                for i, (lo, la) in enumerate(r):
                    x, y = p(lo, la)
                    pts.append(("M" if i == 0 else "L") + "%.1f,%.1f" % (x, y))
                d.append("".join(pts) + "Z")
        if d:
            bagian.append('<path d="%s" fill="#f4f1e4" fill-rule="evenodd" stroke="#8a8a8a" stroke-width="0.5"/>' % "".join(d))
    return "".join(bagian)


def lapis_label_kecamatan(kec_siap, ext, p, ukuran):
    bagian = []
    for nama, daftar in kec_siap:
        if not daftar:
            continue
        terbesar = max(daftar, key=lambda q: luas_ring(q["rings"][0]))
        r = terbesar["rings"][0]
        lon = sum(c[0] for c in r) / len(r)
        lat = sum(c[1] for c in r) / len(r)
        if dalam_ext(lon, lat, ext):
            x, y = p(lon, lat)
            bagian.append(
                '<text x="%.1f" y="%.1f" font-size="%s" text-anchor="middle" fill="#333" '
                'stroke="#ffffff" stroke-width="2" paint-order="stroke">%s</text>' % (x, y, ukuran, esc(nama))
            )
    return "".join(bagian)


def lapis_buffer(titik, radius_km, warna, opasitas, p, px_km, ext):
    isi = []
    for nama, lon, lat in titik:
        if dalam_ext(lon, lat, ext, margin=radius_km / 100.0 + 0.2):
            x, y = p(lon, lat)
            isi.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y, radius_km * px_km, warna))
    return '<g opacity="%s">%s</g>' % (opasitas, "".join(isi))


def lapis_titik(titik, jenis, p, ext, ukuran=3.3):
    isi = []
    for nama, lon, lat in titik:
        if not dalam_ext(lon, lat, ext):
            continue
        x, y = p(lon, lat)
        if jenis == "puskesmas":
            isi.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="#ffffff" stroke-width="0.8"/>' % (x, y, ukuran, WARNA_P))
        else:
            s = ukuran + 1.8
            isi.append(
                '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="#ffffff" stroke-width="0.8"/>'
                % (x, y - s, x + s, y, x, y + s, x - s, y, WARNA_R)
            )
    return "".join(isi)


def panah_utara(x, y):
    return (
        '<g transform="translate(%.1f,%.1f)"><polygon points="0,-14 5,2 0,-2 -5,2" fill="#333"/>'
        '<text x="0" y="14" font-size="9" text-anchor="middle" fill="#333">U</text></g>' % (x, y)
    )


def skala(x, y, px_km, km):
    pj = px_km * km
    return (
        '<g transform="translate(%.1f,%.1f)"><line x1="0" y1="0" x2="%.1f" y2="0" stroke="#333" stroke-width="2"/>'
        '<line x1="0" y1="-3" x2="0" y2="3" stroke="#333"/><line x1="%.1f" y1="-3" x2="%.1f" y2="3" stroke="#333"/>'
        '<text x="%.1f" y="-5" font-size="9" text-anchor="middle" fill="#333">%d km</text></g>'
        % (x, y, pj, pj, pj, pj / 2.0, km)
    )


def legenda(x, y, butir):
    tinggi = 8 + 14 * len(butir)
    lebar = 150
    s = ['<g transform="translate(%.1f,%.1f)">' % (x, y)]
    s.append('<rect x="0" y="0" width="%d" height="%d" fill="#ffffff" fill-opacity="0.9" stroke="#999" stroke-width="0.6"/>' % (lebar, tinggi))
    for i, (tipe, warna, teks) in enumerate(butir):
        cy = 12 + 14 * i
        if tipe == "titik":
            s.append('<circle cx="10" cy="%d" r="3.3" fill="%s" stroke="#fff" stroke-width="0.8"/>' % (cy, warna))
        elif tipe == "rs":
            s.append('<polygon points="10,%d 15,%d 10,%d 5,%d" fill="%s"/>' % (cy - 5, cy, cy + 5, cy, warna))
        elif tipe == "zona":
            s.append('<rect x="4" y="%d" width="13" height="8" fill="%s" fill-opacity="0.5" stroke="%s" stroke-width="0.8"/>' % (cy - 4, warna, warna))
        elif tipe == "batas":
            s.append('<rect x="4" y="%d" width="13" height="8" fill="#f4f1e4" stroke="#8a8a8a" stroke-width="0.8"/>' % (cy - 4))
        s.append('<text x="24" y="%d" font-size="9.5" fill="#222">%s</text>' % (cy + 3, esc(teks)))
    s.append("</g>")
    return "".join(s), tinggi


def panel_peta(nid, x, y, lebar, nama_w, kec_siap, lapisan, judul, butir, label_kec=False, panjang_skala=None):
    ext = WILAYAH[nama_w]
    p, px_km, tinggi = proyeksi(ext, lebar)
    s = []
    s.append('<g transform="translate(%.1f,%.1f)">' % (x, y))
    s.append('<defs><clipPath id="c%s"><rect x="0" y="0" width="%d" height="%.1f"/></clipPath></defs>' % (nid, lebar, tinggi))
    s.append('<g clip-path="url(#c%s)">' % nid)
    s.append('<rect x="0" y="0" width="%d" height="%.1f" fill="#dbeaf5"/>' % (lebar, tinggi))
    s.append(lapis_darat(kec_siap, ext, p))
    for fn in lapisan:
        s.append(fn(p, px_km, ext))
    if label_kec:
        ukuran = "7" if nama_w == "madura" else "6"
        s.append(lapis_label_kecamatan(kec_siap, ext, p, ukuran))
    s.append("</g>")
    s.append('<rect x="0" y="0" width="%d" height="%.1f" fill="none" stroke="#333" stroke-width="1"/>' % (lebar, tinggi))
    s.append(panah_utara(lebar - 18, 24))
    km = panjang_skala or (10 if nama_w == "madura" else 50)
    s.append(skala(lebar - 14 - px_km * km, tinggi - 10, px_km, km))
    if butir:
        lg, tg = legenda(6, tinggi - tg_hitung(butir) - 6, butir)
        s.append(lg)
    s.append('<rect x="0" y="%.1f" width="%d" height="18" fill="#e5f0dc" stroke="#333" stroke-width="0.6"/>' % (tinggi, lebar))
    s.append('<text x="%.1f" y="%.1f" font-size="10.5" text-anchor="middle" fill="#111">%s</text>' % (lebar / 2.0, tinggi + 12.5, esc(judul)))
    s.append("</g>")
    return "".join(s), tinggi + 18


def tg_hitung(butir):
    return 8 + 14 * len(butir)


def bungkus_svg(judul, isi, lebar, tinggi, catatan=""):
    kepala = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'font-family="Helvetica, Arial, sans-serif">' % (lebar, tinggi, lebar, tinggi)
    )
    s = [kepala, '<rect width="100%" height="100%" fill="#ffffff"/>']
    s.append('<text x="%d" y="22" font-size="13" font-weight="bold" text-anchor="middle" fill="#111">%s</text>' % (lebar / 2, esc(judul)))
    s.append(isi)
    if catatan:
        s.append('<text x="%d" y="%d" font-size="9.5" text-anchor="middle" fill="#555">%s</text>' % (lebar / 2, tinggi - 8, esc(catatan)))
    s.append("</svg>")
    return "".join(s)


def tulis(nama_file, svg):
    with open(nama_file, "w", encoding="utf-8") as f:
        f.write(svg)


# =====================================================================
# GAMBAR PETA (per wilayah tampilan)
# =====================================================================
def buat_gambar_peta(nama_w, kec_siap):
    L = LEBAR_PANEL
    jarak = 16
    atas = 38
    hasil = []
    sumber = "Sumber letak: OpenStreetMap dan Google Maps. Batas: batas-admin.geoit.dev. Wilayah: " + NAMA_WILAYAH[nama_w]

    def lp_titik_p(p, px, ext):
        return lapis_titik(puskesmas, "puskesmas", p, ext)

    def lp_titik_r(p, px, ext):
        return lapis_titik(rs, "rs", p, ext)

    # ---- Gambar 1: wilayah kajian
    isi, t = panel_peta("a1", 20, atas, L, nama_w, kec_siap, [], "Peta wilayah kajian: batas kecamatan",
                        [("batas", "", "Batas kecamatan")], label_kec=True)
    hasil.append(("gambar_1_wilayah_kajian_%s.svg" % nama_w,
                  bungkus_svg("Gambar 1. Peta wilayah kajian Kabupaten Sumenep (27 kecamatan)", isi, L + 40, atas + t + 30, sumber)))

    # ---- Gambar 2: sebaran fasilitas (dua panel)
    a, ta = panel_peta("a2", 20, atas, L, nama_w, kec_siap, [lp_titik_p], "(a) Sebaran puskesmas",
                       [("titik", WARNA_P, "Puskesmas")])
    b, tb = panel_peta("b2", 20 + L + jarak, atas, L, nama_w, kec_siap, [lp_titik_r], "(b) Sebaran rumah sakit",
                       [("rs", WARNA_R, "Rumah sakit")])
    hasil.append(("gambar_2_sebaran_fasilitas_%s.svg" % nama_w,
                  bungkus_svg("Gambar 2. Sebaran puskesmas dan rumah sakit di Kabupaten Sumenep", a + b, 2 * L + jarak + 40, atas + max(ta, tb) + 30, sumber)))

    # ---- Gambar 3: proses buffer (empat tahap)
    r2, r5 = RADIUS_PUSKESMAS_KM[0], RADIUS_PUSKESMAS_KM[1]

    def lp_b5(p, px, ext):
        return lapis_buffer(puskesmas, r5, WARNA_B5, 0.40, p, px, ext)

    def lp_b2(p, px, ext):
        return lapis_buffer(puskesmas, r2, WARNA_B2, 0.50, p, px, ext)

    p1, t1 = panel_peta("a3", 20, atas, L, nama_w, kec_siap, [lp_titik_p], "(a) Tahap 1: sebelum buffer (letak puskesmas)",
                        [("titik", WARNA_P, "Puskesmas")])
    p2, t2 = panel_peta("b3", 20 + L + jarak, atas, L, nama_w, kec_siap, [lp_b2, lp_titik_p], "(b) Tahap 2: buffer %g km" % r2,
                        [("titik", WARNA_P, "Puskesmas"), ("zona", WARNA_B2, "Buffer %g km" % r2)])
    y2 = atas + max(t1, t2) + jarak
    p3, t3 = panel_peta("c3", 20, y2, L, nama_w, kec_siap, [lp_b5, lp_titik_p], "(c) Tahap 3: buffer %g km" % r5,
                        [("titik", WARNA_P, "Puskesmas"), ("zona", WARNA_B5, "Buffer %g km" % r5)])
    p4, t4 = panel_peta("d3", 20 + L + jarak, y2, L, nama_w, kec_siap, [lp_b5, lp_b2, lp_titik_p],
                        "(d) Tahap 4: gabungan buffer %g km dan %g km" % (r2, r5),
                        [("titik", WARNA_P, "Puskesmas"), ("zona", WARNA_B2, "Buffer %g km" % r2), ("zona", WARNA_B5, "Buffer %g km" % r5)])
    hasil.append(("gambar_3_proses_buffer_%s.svg" % nama_w,
                  bungkus_svg("Gambar 3. Proses pembuatan buffer puskesmas, dari sebelum hingga selesai", p1 + p2 + p3 + p4,
                              2 * L + jarak + 40, y2 + max(t3, t4) + 30, sumber)))

    # ---- Gambar 4: buffer rumah sakit
    def lp_b_rs(p, px, ext):
        return lapis_buffer(rs, RADIUS_RS_KM, WARNA_RS, 0.25, p, px, ext)

    isi, t = panel_peta("a4", 20, atas, L, nama_w, kec_siap, [lp_b_rs, lp_titik_r], "Buffer rumah sakit %g km" % RADIUS_RS_KM,
                        [("rs", WARNA_R, "Rumah sakit"), ("zona", WARNA_RS, "Buffer %g km" % RADIUS_RS_KM)])
    hasil.append(("gambar_4_buffer_rumah_sakit_%s.svg" % nama_w,
                  bungkus_svg("Gambar 4. Buffer rumah sakit di Kabupaten Sumenep", isi, L + 40, atas + t + 30, sumber)))

    # ---- Gambar 5: wilayah layanan (pendekatan)
    def lp_sa(p, px, ext):
        return lapis_buffer(puskesmas, RADIUS_SERVICE_KM, WARNA_SA, 0.55, p, px, ext)

    isi, t = panel_peta("a5", 20, atas, L, nama_w, kec_siap, [lp_sa, lp_titik_p],
                        "Wilayah layanan %g km (pendekatan lingkaran)" % RADIUS_SERVICE_KM,
                        [("titik", WARNA_P, "Puskesmas"), ("zona", WARNA_SA, "Layanan %g km" % RADIUS_SERVICE_KM)])
    hasil.append(("gambar_5_wilayah_layanan_%s.svg" % nama_w,
                  bungkus_svg("Gambar 5. Wilayah layanan puskesmas (pendekatan jarak jalan kaki 15 menit)", isi, L + 40, atas + t + 30,
                              "Catatan: berupa lingkaran garis lurus, belum menurut jaringan jalan. " + sumber)))
    return hasil


# =====================================================================
# GRAFIK CAKUPAN
# =====================================================================
def buat_grafik_cakupan():
    baris = baca_csv("hasil_cakupan.csv")
    if not baris:
        return None
    W, H = 720, 400
    kiri, bawah, atas, kanan = 60, 90, 60, 20
    area_h = H - bawah - atas
    area_w = W - kiri - kanan
    s = []
    for v in range(0, 101, 20):
        y = atas + area_h * (1 - v / 100.0)
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#ddd"/>' % (kiri, y, kiri + area_w, y))
        s.append('<text x="%d" y="%.1f" font-size="10" text-anchor="end" fill="#555">%d%%</text>' % (kiri - 6, y + 3, v))
    n = len(baris)
    lebar_grup = area_w / float(n)
    for i, r in enumerate(baris):
        a = float(r["persen_tercakup"])
        b = float(r["persen_tidak_tercakup"])
        x0 = kiri + i * lebar_grup + lebar_grup * 0.15
        bw = lebar_grup * 0.32
        for j, (nilai, warna) in enumerate([(a, "#4575b4"), (b, "#fdae61")]):
            h = area_h * nilai / 100.0
            x = x0 + j * (bw + 3)
            y = atas + area_h - h
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x, y, bw, h, warna))
            s.append('<text x="%.1f" y="%.1f" font-size="10" text-anchor="middle" fill="#222">%s%%</text>' % (x + bw / 2.0, y - 4, koma(nilai, 1)))
        nama = r["kategori"]
        if nama.startswith("Service area"):
            nama = "Layanan"
        label = "%s %s km" % (nama, ("%g" % float(r["radius_km"])))
        s.append('<text x="%.1f" y="%d" font-size="10" text-anchor="middle" fill="#222">%s</text>' % (kiri + i * lebar_grup + lebar_grup / 2.0, atas + area_h + 16, esc(label)))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333"/>' % (kiri, atas + area_h, kiri + area_w, atas + area_h))
    s.append('<rect x="%d" y="%d" width="12" height="12" fill="#4575b4"/><text x="%d" y="%d" font-size="11" fill="#222">Persentase wilayah daratan yang terjangkau</text>' % (kiri, H - 38, kiri + 18, H - 28))
    s.append('<rect x="%d" y="%d" width="12" height="12" fill="#fdae61"/><text x="%d" y="%d" font-size="11" fill="#222">Persentase wilayah daratan yang tidak terjangkau</text>' % (kiri + 300, H - 38, kiri + 318, H - 28))
    return bungkus_svg("Gambar 6. Persentase wilayah yang terjangkau dan tidak terjangkau", "".join(s), W, H,
                       "Dihitung dari titik-titik berjarak 1 km di atas daratan; lingkaran garis lurus.")


# =====================================================================
# GAMBAR TETANGGA TERDEKAT (LONCENG)
# =====================================================================
def kurva(x0, y0, w, h, z=None):
    def pdf(t):
        return math.exp(-t * t / 2.0) / math.sqrt(2 * math.pi)

    xmin, xmax = -4.0, 4.0
    puncak = pdf(0)

    def px(t):
        return x0 + (t - xmin) / (xmax - xmin) * w

    def py(v):
        return y0 + h - v / puncak * (h * 0.92)

    def luas_path(a, b, warna):
        langkah = 60
        titik = []
        for i in range(langkah + 1):
            t = a + (b - a) * i / float(langkah)
            titik.append("%.1f,%.1f" % (px(t), py(pdf(t))))
        return '<polygon points="%.1f,%.1f %s %.1f,%.1f" fill="%s" stroke="none"/>' % (px(a), y0 + h, " ".join(titik), px(b), y0 + h, warna)

    s = []
    s.append(luas_path(-4.0, -1.96, "#9ec1e6"))
    s.append(luas_path(-1.96, 1.96, "#fff3a3"))
    s.append(luas_path(1.96, 4.0, "#ee9a9a"))
    titik = []
    for i in range(121):
        t = xmin + (xmax - xmin) * i / 120.0
        titik.append("%.1f,%.1f" % (px(t), py(pdf(t))))
    s.append('<polyline points="%s" fill="none" stroke="#333" stroke-width="1.4"/>' % " ".join(titik))
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#333"/>' % (x0, y0 + h, x0 + w, y0 + h))
    s.append('<text x="%.1f" y="%.1f" font-size="9.5" text-anchor="middle" fill="#2c5d8f">mengelompok</text>' % (px(-3.0), y0 + h + 13))
    s.append('<text x="%.1f" y="%.1f" font-size="9.5" text-anchor="middle" fill="#7a6a00">acak</text>' % (px(0), y0 + h + 13))
    s.append('<text x="%.1f" y="%.1f" font-size="9.5" text-anchor="middle" fill="#a33">menyebar</text>' % (px(3.0), y0 + h + 13))
    if z is not None:
        luar = abs(z) > 3.9
        zz = max(-3.9, min(3.9, z))
        s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000" stroke-width="2" stroke-dasharray="4 3"/>' % (px(zz), y0 + 6, px(zz), y0 + h))
        teks = "z = %s%s" % (koma(z, 2), " (di luar skala)" if luar else "")
        geser = -4 if zz > 1.0 else 4
        anchor = "end" if zz > 1.0 else "start"
        s.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" text-anchor="%s" fill="#000">%s</text>' % (px(zz) + geser, y0 + 16, anchor, teks))
    return "".join(s)


def buat_gambar_nn():
    baris = baca_csv("hasil_nn_ringkas.csv")
    pilihan = []
    for wil in ["Daratan Madura saja", "Seluruh kabupaten"]:
        for kat in ["Puskesmas", "Semua fasilitas"]:
            for r in baris:
                if r["wilayah"] == wil and r["kategori"] == kat:
                    pilihan.append(r)
    if not pilihan:
        return None
    PW, PH = 380, 230
    jarak = 16
    atas = 38
    kolom = 2
    s = []
    for i, r in enumerate(pilihan):
        cx = 20 + (i % kolom) * (PW + jarak)
        cy = atas + (i // kolom) * (PH + 60 + jarak)
        s.append('<g transform="translate(%d,%d)">' % (cx, cy))
        s.append('<rect x="0" y="0" width="%d" height="%d" fill="#ffffff" stroke="#333" stroke-width="0.8"/>' % (PW, PH + 60))
        s.append('<text x="8" y="16" font-size="10" fill="#222">Rasio tetangga terdekat (NNR): %s</text>' % koma(r["NNR"], 3))
        s.append('<text x="8" y="30" font-size="10" fill="#222">z = %s ; p = %s</text>' % (koma(r["z"], 3), koma(r["p"], 4)))
        s.append(kurva(15, 40, PW - 30, PH - 70, float(r["z"])))
        s.append('<rect x="0" y="%d" width="%d" height="42" fill="#e5f0dc" stroke="#333" stroke-width="0.6"/>' % (PH + 18, PW))
        huruf = "abcd"[i]
        s.append('<text x="%d" y="%d" font-size="10.5" text-anchor="middle" fill="#111">(%s) %s, %s (n = %s)</text>' % (PW / 2, PH + 34, huruf, esc(r["kategori"]), esc(r["wilayah"]), esc(r["n"])))
        s.append('<text x="%d" y="%d" font-size="10.5" font-weight="bold" text-anchor="middle" fill="#111">NNR %s : %s</text>' % (PW / 2, PH + 50, koma(r["NNR"], 3), esc(r["pola"])))
        s.append("</g>")
    baris_n = (len(pilihan) + 1) // 2
    tinggi = atas + baris_n * (PH + 60 + jarak) + 20
    return bungkus_svg("Gambar 7. Hasil analisis tetangga terdekat (nearest neighbor)", "".join(s), 2 * PW + jarak + 40, tinggi,
                       "Indeks di bawah 1 mengelompok, sekitar 1 acak, di atas 1 menyebar (|z| lebih dari 1,96 berarti bermakna).")


# =====================================================================
# PROGRAM UTAMA
# =====================================================================
def main():
    if not kec["features"]:
        print("batas_kecamatan.geojson tidak ditemukan. Jalankan gabung_kecamatan.py dulu.")
        return
    if not puskesmas:
        print("fasilitas_gabungan.geojson tidak ditemukan atau kosong. Jalankan analisis_sumenep.py dulu.")
        return

    daftar_file = []
    for nama_w in ["madura", "kabupaten"]:
        kec_siap = siapkan_kecamatan(CAP_TITIK[nama_w])
        for nama_file, svg in buat_gambar_peta(nama_w, kec_siap):
            tulis(nama_file, svg)
            daftar_file.append(nama_file)
            print("Tersimpan:", nama_file)

    g6 = buat_grafik_cakupan()
    if g6:
        tulis("gambar_6_grafik_cakupan.svg", g6)
        daftar_file.append("gambar_6_grafik_cakupan.svg")
        print("Tersimpan: gambar_6_grafik_cakupan.svg")
    g7 = buat_gambar_nn()
    if g7:
        tulis("gambar_7_tetangga_terdekat.svg", g7)
        daftar_file.append("gambar_7_tetangga_terdekat.svg")
        print("Tersimpan: gambar_7_tetangga_terdekat.svg")

    # ---------------- halaman galeri ----------------
    urutan = [
        ("Gambar 1", "Peta wilayah kajian", "Padanan Gambar 2 jurnal (peta wilayah kajian Irbid)", "gambar_1_wilayah_kajian_%s.svg"),
        ("Gambar 2", "Sebaran puskesmas dan rumah sakit", "Padanan Gambar 4 jurnal (sebaran pusat kesehatan dan rumah sakit)", "gambar_2_sebaran_fasilitas_%s.svg"),
        ("Gambar 3", "Proses buffer puskesmas: sebelum, tengah, dan selesai", "Padanan Gambar 6 jurnal (zona buffer pusat kesehatan)", "gambar_3_proses_buffer_%s.svg"),
        ("Gambar 4", "Buffer rumah sakit", "Padanan Gambar 7 jurnal (buffer rumah sakit 20 km)", "gambar_4_buffer_rumah_sakit_%s.svg"),
        ("Gambar 5", "Wilayah layanan (pendekatan)", "Padanan Gambar 8 jurnal (service area)", "gambar_5_wilayah_layanan_%s.svg"),
    ]
    h = []
    for kode, nama, padanan, pola in urutan:
        h.append("<section><h2>%s. %s</h2><p class=\"pd\">%s</p>" % (kode, esc(nama), esc(padanan)))
        for nw, label in [("madura", "Tampilan daratan Madura"), ("kabupaten", "Tampilan seluruh kabupaten")]:
            nf = pola % nw
            if os.path.exists(nf):
                h.append("<h3>%s</h3><a href=\"%s\"><img src=\"%s\" alt=\"%s\"></a>" % (label, nf, nf, esc(nama)))
        h.append("</section>")
    for kode, nama, padanan, nf in [
        ("Gambar 6", "Grafik persentase wilayah terjangkau", "Padanan grafik pada Gambar 6 jurnal", "gambar_6_grafik_cakupan.svg"),
        ("Gambar 7", "Hasil tetangga terdekat", "Padanan Gambar 5 jurnal (nilai NNR)", "gambar_7_tetangga_terdekat.svg"),
    ]:
        if os.path.exists(nf):
            h.append("<section><h2>%s. %s</h2><p class=\"pd\">%s</p><a href=\"%s\"><img src=\"%s\" alt=\"%s\"></a></section>" % (kode, esc(nama), esc(padanan), nf, nf, esc(nama)))

    halaman = (
        "<!DOCTYPE html><html lang=\"id\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Galeri Peta Fasilitas Kesehatan Kabupaten Sumenep</title><style>"
        "body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#f2f5f9;color:#1d2733;line-height:1.5}"
        "header{background:#1F3A5F;color:#fff;padding:18px 14px}header h1{margin:0;font-size:19px}header p{margin:4px 0 0;font-size:13px;opacity:.9}"
        "main{max-width:900px;margin:0 auto;padding:12px}section{background:#fff;border-radius:10px;padding:12px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}"
        "h2{margin:0 0 2px;font-size:16px;color:#1F3A5F}h3{margin:12px 0 6px;font-size:13.5px}.pd{margin:0;font-size:12.5px;color:#55606e}"
        "img{width:100%;height:auto;border:1px solid #ccd}a.kembali{display:block;margin:10px 0;color:#1F3A5F}"
        "</style></head><body><header><h1>Galeri Peta: Aksesibilitas Fasilitas Kesehatan Kabupaten Sumenep</h1>"
        "<p>Urutan gambar mengikuti jurnal acuan Obeidat &amp; Alourd (2024). Ketuk gambar untuk memperbesar.</p></header><main>"
        "<a class=\"kembali\" href=\"index.html\">&larr; Kembali ke ringkasan</a>" + "".join(h) + "</main></body></html>"
    )
    with open("galeri_peta.html", "w", encoding="utf-8") as f:
        f.write(halaman)
    print("Tersimpan: galeri_peta.html")
    print("Selesai. Jumlah gambar:", len(daftar_file))


main()
