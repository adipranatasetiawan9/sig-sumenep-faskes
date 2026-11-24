import json
import math
import os
import time
import urllib.parse
import urllib.request

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

CACHE = "kecamatan_cache.json"
KOTAK_CADANGAN = (-7.30, 113.60, -5.40, 115.80)


def kirim(query, putaran_maks=2):
    data = urllib.parse.urlencode({"data": query}).encode()
    for putaran in range(putaran_maks):
        for server in SERVERS:
            try:
                req = urllib.request.Request(
                    server, data=data, headers={"User-Agent": "tugas-sig-sumenep"}
                )
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.loads(r.read().decode())
            except Exception as e:
                print("   gagal:", server.split("/")[2], "-", e)
        if putaran < putaran_maks - 1:
            print("   menunggu 10 detik lalu coba lagi...")
            time.sleep(10)
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
        return None
    total = sum(luas_km2(c) for c in cincin)
    return {
        "type": "Feature",
        "properties": {"nama": nama, "osm_id": rel.get("id"), "luas_km2_osm": round(total, 2)},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[p[0], p[1]] for p in c]] for c in cincin],
        },
    }


def titik_dalam(x, y, ring):
    dalam = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            xp = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xp:
                dalam = not dalam
        j = i
    return dalam


def muat_cincin_kabupaten():
    if not os.path.exists("batas_sumenep.geojson"):
        return None
    with open("batas_sumenep.geojson", encoding="utf-8") as f:
        d = json.load(f)
    hasil = []
    for fit in d["features"]:
        for poly in fit["geometry"]["coordinates"]:
            hasil.append(poly[0])
    return hasil


def hitung_kotak(cincin_kab):
    if not cincin_kab:
        return KOTAK_CADANGAN
    xs = []
    ys = []
    for r in cincin_kab:
        for p in r:
            xs.append(p[0])
            ys.append(p[1])
    return (min(ys) - 0.02, min(xs) - 0.02, max(ys) + 0.02, max(xs) + 0.02)


def pusat_kecamatan(fitur):
    cincin_list = [poly[0] for poly in fitur["geometry"]["coordinates"]]
    terbesar = max(cincin_list, key=luas_km2)
    x = sum(p[0] for p in terbesar) / len(terbesar)
    y = sum(p[1] for p in terbesar) / len(terbesar)
    return x, y


def baca_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def simpan_cache(cache):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def main():
    cincin_kab = muat_cincin_kabupaten()
    s, w, n, e = hitung_kotak(cincin_kab)
    kotak = "%.4f,%.4f,%.4f,%.4f" % (s, w, n, e)
    print("Kotak pencarian:", kotak)

    strategi = [
        (
            "A. admin_level 6 di dalam kotak",
            '[out:json][timeout:180];\n'
            'rel["boundary"="administrative"]["admin_level"="6"](%s);\n'
            'out tags;' % kotak,
        ),
        (
            "B. nama diawali Kecamatan di dalam kotak",
            '[out:json][timeout:180];\n'
            'rel["boundary"="administrative"]["name"~"^Kecamatan |^Kec[.] "](%s);\n'
            'out tags;' % kotak,
        ),
    ]

    print("")
    print("=== LANGKAH 1: DAFTAR KECAMATAN ===")
    daftar = []
    for nama_s, query in strategi:
        print("Cara", nama_s)
        hasil = kirim(query)
        if hasil is None:
            print("  semua server gagal untuk cara ini")
            continue
        if hasil.get("remark"):
            print("  pesan server:", hasil["remark"])
        sudah = set()
        temp = []
        for el in hasil.get("elements", []):
            if el.get("type") != "relation" or el["id"] in sudah:
                continue
            sudah.add(el["id"])
            nm = el.get("tags", {}).get("name", "(tanpa nama)")
            if nm.lower().startswith("kecamatan "):
                nm = nm[10:]
            temp.append((el["id"], nm))
        print("  ditemukan:", len(temp))
        if temp:
            daftar = temp
            break
        time.sleep(2)

    if not daftar:
        print("")
        print("Kedua cara kosong. Kirim layar ini ke Claude.")
        return

    cache = baca_cache()
    print("")
    print("=== LANGKAH 2: AMBIL BENTUK BATAS, SATU PER SATU ===")
    gagal = []
    for i, (rid, nama) in enumerate(daftar, 1):
        if str(rid) in cache:
            print("(%d/%d) %s : sudah ada" % (i, len(daftar), nama))
            continue
        print("(%d/%d) %s ..." % (i, len(daftar), nama))
        q = '[out:json][timeout:120];\nrel(%d);\nout geom;' % rid
        h = kirim(q)
        if h is None or not h.get("elements"):
            gagal.append(nama)
            print("   -> belum berhasil, dilewati dulu")
            continue
        fit = fitur_dari_relasi(h["elements"][0], nama)
        if fit is None:
            gagal.append(nama)
            print("   -> bentuk gagal dirangkai")
            continue
        cache[str(rid)] = fit
        simpan_cache(cache)
        time.sleep(2)

    print("")
    print("=== LANGKAH 3: SARING YANG BENAR-BENAR DI SUMENEP ===")
    terpilih = []
    tetangga = []
    for rid, nama in daftar:
        fit = cache.get(str(rid))
        if fit is None:
            continue
        if cincin_kab is None:
            terpilih.append(fit)
            continue
        x, y = pusat_kecamatan(fit)
        if any(titik_dalam(x, y, r) for r in cincin_kab):
            terpilih.append(fit)
        else:
            tetangga.append(nama)

    if not terpilih:
        print("Belum ada kecamatan yang berhasil. Jalankan lagi nanti.")
        return

    with open("batas_kecamatan.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": terpilih}, f, ensure_ascii=False)

    nama_list = sorted(x["properties"]["nama"] for x in terpilih)
    print("Kecamatan tersimpan:", len(terpilih), "(target 27)")
    print("Nama:", ", ".join(nama_list))
    if tetangga:
        print("Dibuang karena di luar Sumenep:", ", ".join(tetangga))
    if gagal:
        print("")
        print("BELUM BERHASIL:", ", ".join(gagal))
        print("Jalankan lagi nanti, yang sudah berhasil tidak diulang.")
    print("Tersimpan: batas_kecamatan.geojson")


main()
