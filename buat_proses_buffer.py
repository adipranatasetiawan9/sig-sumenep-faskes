import json
import math
import os

LANGKAH_GRID_KM = 1.0


# =====================================================================
# 1. MEMBUAT grid_daratan.geojson (sel 1 km x 1 km di atas daratan)
# =====================================================================
def luas_ring(ring):
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = math.cos(math.radians(lat0)) * 111.32
    ky = 110.574
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * kx * ring[i + 1][1] * ky - ring[i + 1][0] * kx * ring[i][1] * ky
    return abs(a) / 2.0


def muat_poligon(nama_file, maks_titik=3000):
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
        for p in polys:
            cinc = [[(c[0], c[1]) for c in r] for r in p]
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
            hasil.append({"rings": ringan, "bbox": (min(xs), min(ys), max(xs), max(ys))})
    return hasil


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


def jarak_cepat(la1, lo1, la2, lo2):
    dx = (lo1 - lo2) * math.cos(math.radians((la1 + la2) / 2.0)) * 111.32
    dy = (la1 - la2) * 110.574
    return math.sqrt(dx * dx + dy * dy)


def buat_grid():
    for nama in ["batas_sumenep.geojson", "fasilitas_gabungan.geojson"]:
        if not os.path.exists(nama):
            print("File tidak ada:", nama, "(jalankan analisis_sumenep.py dan siapkan_batas.py dulu)")
            return False

    polys = muat_poligon("batas_sumenep.geojson")
    with open("fasilitas_gabungan.geojson", encoding="utf-8") as f:
        fas = json.load(f)
    pusk = []
    rumah = []
    for ft in fas["features"]:
        lon, lat = ft["geometry"]["coordinates"][0], ft["geometry"]["coordinates"][1]
        if ft["properties"].get("jenis") == "Puskesmas":
            pusk.append((lat, lon))
        elif ft["properties"].get("jenis") == "Rumah Sakit":
            rumah.append((lat, lon))

    minx = min(p["bbox"][0] for p in polys)
    miny = min(p["bbox"][1] for p in polys)
    maxx = max(p["bbox"][2] for p in polys)
    maxy = max(p["bbox"][3] for p in polys)

    fitur = []
    lat = miny
    while lat <= maxy:
        dlon = LANGKAH_GRID_KM / (111.32 * math.cos(math.radians(lat)))
        dlat = LANGKAH_GRID_KM / 110.574
        lon = minx
        while lon <= maxx:
            if any(dalam_poly(lon, lat, p) for p in polys):
                dp = min(jarak_cepat(lat, lon, a, b) for a, b in pusk) if pusk else 9999
                dr = min(jarak_cepat(lat, lon, a, b) for a, b in rumah) if rumah else 9999
                h_lat = dlat / 2.0
                h_lon = dlon / 2.0
                cincin = [
                    [round(lon - h_lon, 5), round(lat - h_lat, 5)],
                    [round(lon + h_lon, 5), round(lat - h_lat, 5)],
                    [round(lon + h_lon, 5), round(lat + h_lat, 5)],
                    [round(lon - h_lon, 5), round(lat + h_lat, 5)],
                    [round(lon - h_lon, 5), round(lat - h_lat, 5)],
                ]
                fitur.append(
                    {
                        "type": "Feature",
                        "properties": {"dP": round(dp, 2), "dR": round(dr, 2)},
                        "geometry": {"type": "Polygon", "coordinates": [cincin]},
                    }
                )
            lon += dlon
        lat += dlat

    with open("grid_daratan.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": fitur}, f)
    print("Tersimpan: grid_daratan.geojson (%d sel daratan)" % len(fitur))
    return True


# =====================================================================
# 2. MEMBUAT proses_buffer.html
# =====================================================================
HTML = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Proses Buffer Langkah demi Langkah - Kabupaten Sumenep</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #f2f5f9; color: #1d2733; line-height: 1.5; }
header { background: #1F3A5F; color: #fff; padding: 14px; }
header h1 { margin: 0; font-size: 17px; line-height: 1.3; }
header p { margin: 4px 0 0; font-size: 12.5px; opacity: 0.9; }
nav { display: flex; gap: 6px; overflow-x: auto; padding: 8px; background: #fff; border-bottom: 1px solid #d5dbe3; position: sticky; top: 0; z-index: 5; }
nav button { flex: 0 0 auto; border: 1px solid #1F3A5F; background: #fff; color: #1F3A5F; border-radius: 18px; padding: 6px 12px; font-size: 12.5px; }
nav button.aktif { background: #1F3A5F; color: #fff; }
#wrap { position: relative; }
#peta { width: 100%; height: 56vh; display: block; background: #dbeaf5; touch-action: none; }
#kontrol { position: absolute; left: 8px; top: 8px; display: flex; flex-direction: column; gap: 4px; }
#kontrol button { width: 34px; height: 34px; border: 1px solid #888; background: #fff; border-radius: 6px; font-size: 16px; font-weight: bold; color: #333; }
#utara { position: absolute; right: 10px; top: 8px; font-size: 12px; text-align: center; color: #333; background: rgba(255,255,255,.8); padding: 2px 6px; border-radius: 6px; }
#lebar { position: absolute; left: 8px; bottom: 6px; font-size: 11px; background: rgba(255,255,255,.85); padding: 2px 6px; border-radius: 6px; }
#panel { max-width: 900px; margin: 0 auto; padding: 12px; }
.kartu { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.kartu h2 { margin: 0 0 6px; font-size: 15.5px; color: #1F3A5F; }
.qgis { background: #eaf3ea; border-left: 4px solid #1a9850; padding: 8px 10px; font-size: 12.5px; border-radius: 4px; margin-top: 8px; }
.catatan { background: #fff8e6; border-left: 4px solid #f0ad4e; padding: 8px 10px; font-size: 12.5px; border-radius: 4px; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th { background: #1F3A5F; color: #fff; text-align: left; padding: 5px; }
td { padding: 5px; border-bottom: 1px solid #e3e8ee; vertical-align: top; }
.geser { overflow-x: auto; }
.leg span.k { display: inline-block; width: 12px; height: 12px; margin-right: 5px; vertical-align: middle; border: 1px solid #777; }
.leg label { display: block; font-size: 12.5px; margin: 3px 0; }
button.aksi { background: #1a9850; color: #fff; border: 0; border-radius: 8px; padding: 8px 14px; font-size: 13px; margin: 4px 6px 4px 0; }
code { background: #eef1f5; padding: 1px 4px; border-radius: 3px; font-size: 11.5px; word-break: break-all; }
.besar { font-size: 22px; font-weight: bold; color: #1F3A5F; }
.pesan { padding: 14px; color: #a33; }
input[type=range] { width: 100%; }
a { color: #1F3A5F; }
</style>
</head>
<body>
<header>
  <h1>Proses Pembuatan Buffer, Langkah demi Langkah</h1>
  <p>Seluruh gambar di halaman ini digambar langsung dari file GeoJSON yang dibuat dengan Python (bukan gambar ilustrasi). Geser untuk menggeser peta, cubit atau tombol + dan - untuk memperbesar.</p>
</header>
<nav id="nav"></nav>
<div id="wrap">
  <svg id="peta" xmlns="http://www.w3.org/2000/svg"></svg>
  <div id="kontrol">
    <button id="bplus">+</button><button id="bmin">-</button><button id="bmad">M</button><button id="bsem">S</button>
  </div>
  <div id="utara">&#8593; U</div>
  <div id="lebar"></div>
</div>
<div id="panel"><div class="pesan">Memuat data GeoJSON...</div></div>

<script>
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var COS = Math.cos(7.0 * Math.PI / 180);
  function X(lon) { return (lon - 113.0) * 111.32 * COS; }
  function Y(lat) { return (-5.0 - lat) * 110.574; }

  var FILES = [
    ["batas_kecamatan.geojson", "Batas kecamatan (poligon)"],
    ["fasilitas_gabungan.geojson", "Fasilitas kesehatan (titik)"],
    ["buffer_puskesmas_2km.geojson", "Buffer puskesmas 2 km (poligon)"],
    ["buffer_puskesmas_5km.geojson", "Buffer puskesmas 5 km (poligon)"],
    ["buffer_rs_20km.geojson", "Buffer rumah sakit 20 km (poligon)"],
    ["service_area_1km.geojson", "Wilayah layanan 1 km (poligon)"],
    ["grid_daratan.geojson", "Grid daratan 1 km x 1 km (poligon)"]
  ];
  var DATA = {};
  var UKURAN = {};

  var svg = document.getElementById("peta");
  var panel = document.getElementById("panel");
  var nav = document.getElementById("nav");
  var vb = { x: 0, y: 0, w: 100, h: 100 };

  function el(nama, atribut, induk) {
    var e = document.createElementNS(NS, nama);
    for (var k in atribut) { e.setAttribute(k, atribut[k]); }
    if (induk) { induk.appendChild(e); }
    return e;
  }

  // ---------------- gambar geometri ----------------
  function cincinPath(ring, cap) {
    var langkah = ring.length > cap ? Math.ceil(ring.length / cap) : 1;
    var d = "";
    for (var i = 0; i < ring.length; i += langkah) {
      d += (i === 0 ? "M" : "L") + X(ring[i][0]).toFixed(2) + "," + Y(ring[i][1]).toFixed(2);
    }
    return d + "Z";
  }
  function geomPath(g, cap) {
    var polys = g.type === "MultiPolygon" ? g.coordinates : (g.type === "Polygon" ? [g.coordinates] : []);
    var d = "";
    polys.forEach(function (poly) { poly.forEach(function (r) { d += cincinPath(r, cap); }); });
    return d;
  }
  function gabungPath(fc, cap) {
    var d = "";
    fc.features.forEach(function (f) { d += geomPath(f.geometry, cap); });
    return d;
  }

  // ---------------- lapisan ----------------
  var gDarat, gGrid, gBuf, gAnim, gLingkar, gTitik;
  var pathBuf = {};
  var titikEl = [];
  var puskesmas = [];
  var rumahSakit = [];
  var semuaFas = [];
  var cellPath = [];
  var cellDP = [];
  var cellDR = [];
  var pCov, pUnc;

  function bangunLapisan() {
    gDarat = el("g", {}, svg);
    gGrid = el("g", {}, svg);
    gBuf = el("g", {}, svg);
    gAnim = el("g", {}, svg);
    gLingkar = el("g", {}, svg);
    gTitik = el("g", {}, svg);

    if (DATA["batas_kecamatan.geojson"]) {
      DATA["batas_kecamatan.geojson"].features.forEach(function (f) {
        var p = el("path", { d: geomPath(f.geometry, 700), fill: "#f4f1e4", "fill-rule": "evenodd", stroke: "#8a8a8a", "stroke-width": "0.8", "vector-effect": "non-scaling-stroke" }, gDarat);
        var t = el("title", {}, p);
        t.textContent = "Kecamatan " + ((f.properties && f.properties.nama) || "");
      });
    }

    var warnaBuf = {
      "buffer_rs_20km.geojson": ["#d73027", 0.18],
      "buffer_puskesmas_5km.geojson": ["#f0a030", 0.40],
      "buffer_puskesmas_2km.geojson": ["#2b83ba", 0.50],
      "service_area_1km.geojson": ["#7b3294", 0.55]
    };
    ["buffer_rs_20km.geojson", "buffer_puskesmas_5km.geojson", "buffer_puskesmas_2km.geojson", "service_area_1km.geojson"].forEach(function (nm) {
      if (DATA[nm]) {
        pathBuf[nm] = el("path", { d: gabungPath(DATA[nm], 400), fill: warnaBuf[nm][0], "fill-opacity": warnaBuf[nm][1], stroke: warnaBuf[nm][0], "stroke-width": "0.8", "vector-effect": "non-scaling-stroke", display: "none" }, gBuf);
      }
    });

    var fas = DATA["fasilitas_gabungan.geojson"];
    fas.features.forEach(function (f) {
      var c = f.geometry.coordinates;
      var jenis = f.properties.jenis;
      var warna = jenis === "Rumah Sakit" ? "#d73027" : "#1a9850";
      var e = el("circle", { cx: X(c[0]).toFixed(3), cy: Y(c[1]).toFixed(3), r: 1, fill: warna, stroke: "#fff", "stroke-width": "1", "vector-effect": "non-scaling-stroke" }, gTitik);
      var item = { el: e, f: f, jenis: jenis, x: X(c[0]), y: Y(c[1]) };
      titikEl.push(item);
      semuaFas.push(item);
      if (jenis === "Puskesmas") { puskesmas.push(item); }
      if (jenis === "Rumah Sakit") { rumahSakit.push(item); }
    });

    if (DATA["grid_daratan.geojson"]) {
      DATA["grid_daratan.geojson"].features.forEach(function (f) {
        cellPath.push(cincinPath(f.geometry.coordinates[0], 10));
        cellDP.push(f.properties.dP);
        cellDR.push(f.properties.dR);
      });
      pUnc = el("path", { d: "", fill: "#b9b9b9", "fill-opacity": "0.75", stroke: "none" }, gGrid);
      pCov = el("path", { d: "", fill: "#2b83ba", "fill-opacity": "0.75", stroke: "none" }, gGrid);
    }
  }

  // ---------------- tampilan, geser, zoom ----------------
  function terapkan() {
    var r = svg.getBoundingClientRect();
    if (r.width < 10) { return; }
    vb.h = vb.w * r.height / r.width;
    svg.setAttribute("viewBox", vb.x + " " + vb.y + " " + vb.w + " " + vb.h);
    var kmPerPx = vb.w / r.width;
    titikEl.forEach(function (t) { t.el.setAttribute("r", (t.jenis === "Rumah Sakit" ? 6 : 4.5) * kmPerPx); });
    document.getElementById("lebar").textContent = "Lebar layar kira-kira " + Math.round(vb.w) + " km";
  }
  function kotak(lon0, lon1, lat0, lat1) {
    vb.x = X(lon0);
    vb.w = X(lon1) - X(lon0);
    var r = svg.getBoundingClientRect();
    var h = vb.w * r.height / r.width;
    var tengahY = (Y(lat0) + Y(lat1)) / 2;
    vb.y = tengahY - h / 2;
    terapkan();
  }
  function keMadura() { kotak(113.55, 114.20, -7.28, -6.80); }
  function keSemua() { kotak(113.50, 116.00, -7.30, -5.45); }
  function zoom(f, cx, cy) {
    vb.x = cx - (cx - vb.x) / f;
    vb.y = cy - (cy - vb.y) / f;
    vb.w = vb.w / f;
    terapkan();
  }
  function keKm(cx, cy) {
    var r = svg.getBoundingClientRect();
    return [vb.x + (cx - r.left) * vb.w / r.width, vb.y + (cy - r.top) * vb.h / r.height];
  }
  var ptr = {};
  svg.addEventListener("pointerdown", function (e) { svg.setPointerCapture(e.pointerId); ptr[e.pointerId] = { x: e.clientX, y: e.clientY }; });
  svg.addEventListener("pointermove", function (e) {
    if (!ptr[e.pointerId]) { return; }
    var ids = Object.keys(ptr);
    var r = svg.getBoundingClientRect();
    if (ids.length === 1) {
      vb.x -= (e.clientX - ptr[e.pointerId].x) * vb.w / r.width;
      vb.y -= (e.clientY - ptr[e.pointerId].y) * vb.w / r.width;
      ptr[e.pointerId] = { x: e.clientX, y: e.clientY };
      terapkan();
    } else if (ids.length === 2) {
      var a = ptr[ids[0]], b = ptr[ids[1]];
      var d0 = Math.hypot(a.x - b.x, a.y - b.y);
      ptr[e.pointerId] = { x: e.clientX, y: e.clientY };
      a = ptr[ids[0]]; b = ptr[ids[1]];
      var d1 = Math.hypot(a.x - b.x, a.y - b.y);
      if (d0 > 5 && d1 > 5) {
        var m = keKm((a.x + b.x) / 2, (a.y + b.y) / 2);
        zoom(d1 / d0, m[0], m[1]);
      }
    }
  });
  function lepas(e) { delete ptr[e.pointerId]; }
  svg.addEventListener("pointerup", lepas);
  svg.addEventListener("pointercancel", lepas);
  svg.addEventListener("wheel", function (e) { e.preventDefault(); var m = keKm(e.clientX, e.clientY); zoom(e.deltaY < 0 ? 1.25 : 0.8, m[0], m[1]); }, { passive: false });
  document.getElementById("bplus").onclick = function () { zoom(1.5, vb.x + vb.w / 2, vb.y + vb.h / 2); };
  document.getElementById("bmin").onclick = function () { zoom(1 / 1.5, vb.x + vb.w / 2, vb.y + vb.h / 2); };
  document.getElementById("bmad").onclick = keMadura;
  document.getElementById("bsem").onclick = keSemua;
  window.addEventListener("resize", terapkan);

  // ---------------- langkah ----------------
  var timer = null;
  function reset() {
    if (timer) { clearInterval(timer); timer = null; }
    gAnim.innerHTML = "";
    gLingkar.innerHTML = "";
    gGrid.style.display = "none";
    Object.keys(pathBuf).forEach(function (k) { pathBuf[k].setAttribute("display", "none"); });
    titikEl.forEach(function (t) { t.el.setAttribute("display", "inline"); t.el.setAttribute("opacity", "1"); });
  }
  function kb(n) { return (n / 1024).toFixed(0) + " KB"; }
  function jml(nama) { return DATA[nama] ? DATA[nama].features.length : 0; }
  function koma(x, d) { return Number(x).toFixed(d).replace(".", ","); }

  function langkah1() {
    reset();
    var baris = "";
    FILES.forEach(function (f) {
      if (DATA[f[0]]) {
        baris += "<tr><td><code>" + f[0] + "</code></td><td>" + f[1] + "</td><td>" + DATA[f[0]].features.length + "</td><td>" + kb(UKURAN[f[0]]) + "</td></tr>";
      }
    });
    var tb = "";
    var n = Math.min(8, semuaFas.length);
    for (var i = 0; i < n; i++) {
      var p = semuaFas[i].f.properties, c = semuaFas[i].f.geometry.coordinates;
      tb += "<tr><td>" + (i + 1) + "</td><td>" + p.nama + "</td><td>" + p.jenis + "</td><td>" + (p.kecamatan || "") + "</td><td>" + c[0].toFixed(5) + "</td><td>" + c[1].toFixed(5) + "</td></tr>";
    }
    panel.innerHTML =
      '<div class="kartu"><h2>Langkah 1. Data awal (sebelum buffer)</h2>' +
      "<p>Dua lapisan dibuka lebih dulu: <b>batas kecamatan</b> (poligon, " + jml("batas_kecamatan.geojson") + " fitur) dan <b>fasilitas kesehatan</b> (titik, " + semuaFas.length +
      " fitur: " + puskesmas.length + " puskesmas dan " + rumahSakit.length + " rumah sakit). Keduanya berformat GeoJSON dengan sistem koordinat WGS 84 (EPSG:4326), yaitu lintang dan bujur dalam derajat.</p>" +
      '<div class="geser"><table><tr><th>File</th><th>Isi</th><th>Fitur</th><th>Ukuran</th></tr>' + baris + "</table></div>" +
      '<h2 style="margin-top:10px">Tabel atribut fasilitas (' + n + " dari " + semuaFas.length + " baris)</h2>" +
      '<div class="geser"><table><tr><th>No</th><th>Nama</th><th>Jenis</th><th>Kecamatan</th><th>Bujur</th><th>Lintang</th></tr>' + tb + "</table></div>" +
      '<div class="qgis"><b>Padanan di QGIS:</b> Layer &gt; Add Layer &gt; Add Vector Layer, pilih file GeoJSON, lalu klik kanan lapisan &gt; Open Attribute Table.</div></div>' +
      '<div class="kartu leg"><span class="k" style="background:#1a9850"></span>Puskesmas &nbsp; <span class="k" style="background:#d73027"></span>Rumah sakit &nbsp; <span class="k" style="background:#f4f1e4"></span>Kecamatan</div>';
    keMadura();
  }

  function langkah2() {
    reset();
    rumahSakit.forEach(function (t) { t.el.setAttribute("opacity", "0.25"); });
    panel.innerHTML =
      '<div class="kartu"><h2>Langkah 2. Memilih fasilitas dan menetapkan jarak</h2>' +
      "<p>Dari " + semuaFas.length + " titik, yang dipilih untuk buffer puskesmas adalah titik berjenis <b>Puskesmas</b> (" + puskesmas.length + " titik). Rumah sakit (" + rumahSakit.length +
      " titik) diproses terpisah karena jangkauannya berbeda.</p>" +
      '<div class="geser"><table><tr><th>Kelompok</th><th>Jarak buffer</th><th>Alasan</th></tr>' +
      "<tr><td>Puskesmas</td><td>2 km dan 5 km</td><td>Rentang jarak pusat kesehatan di jurnal acuan (jari-jari minimum dan maksimum)</td></tr>" +
      "<tr><td>Rumah sakit</td><td>20 km</td><td>Jari-jari rumah sakit di jurnal acuan</td></tr>" +
      "<tr><td>Puskesmas</td><td>1 km</td><td>Pendekatan jalan kaki 15 menit (jurnal memakai jaringan jalan)</td></tr></table></div>" +
      '<div class="qgis"><b>Padanan di QGIS:</b> Select by Expression dengan rumus <code>"jenis" = \'Puskesmas\'</code>, lalu Export &gt; Save Selected Features As.</div>' +
      '<div class="catatan">Jarak mengikuti jurnal sebagai pembanding. Standar jarak Indonesia belum dipakai, dan hal ini sudah saya tanyakan kepada Bapak.</div></div>';
    keMadura();
  }

  function langkah3() {
    reset();
    var fb = DATA["buffer_puskesmas_2km.geojson"];
    if (!fb) { panel.innerHTML = '<div class="pesan">File buffer_puskesmas_2km.geojson tidak ditemukan.</div>'; return; }
    panel.innerHTML =
      '<div class="kartu"><h2>Langkah 3. Proses buffer 2 km, satu titik demi satu titik</h2>' +
      "<p>Untuk setiap puskesmas, dibuat lingkaran berjari-jari 2 km yang disimpan sebagai <b>poligon 36 sisi</b>. Tekan tombol untuk melihat prosesnya berjalan.</p>" +
      '<button class="aksi" id="mulai">Mulai proses</button><button class="aksi" id="selesai" style="background:#1F3A5F">Langsung selesai</button>' +
      '<p>Buffer ke-<span class="besar" id="no">0</span> dari ' + fb.features.length + "</p>" +
      '<div id="rinci" style="font-size:12.5px"></div>' +
      '<div class="qgis"><b>Padanan di QGIS:</b> Vector &gt; Geoprocessing Tools &gt; Buffer. Isi Distance = 2 kilometers dan Segments = 36. QGIS meminta sistem koordinat berproyeksi (misalnya UTM 49S, EPSG:32749), sedangkan skrip Python ini menghitung jarak langsung di permukaan bumi sehingga tidak perlu proyeksi.</div></div>';
    var i = 0;
    function tambah() {
      if (i >= fb.features.length) { if (timer) { clearInterval(timer); timer = null; } return; }
      var f = fb.features[i];
      el("path", { d: geomPath(f.geometry, 100), fill: "#2b83ba", "fill-opacity": "0.35", stroke: "#2b83ba", "stroke-width": "1", "vector-effect": "non-scaling-stroke" }, gAnim);
      var ring = f.geometry.coordinates[0];
      document.getElementById("no").textContent = i + 1;
      document.getElementById("rinci").innerHTML =
        "<b>" + f.properties.nama + "</b><br>Jumlah titik sudut poligon: " + ring.length + "<br>Tiga koordinat pertama: <code>" +
        ring.slice(0, 3).map(function (c) { return "[" + c[0] + ", " + c[1] + "]"; }).join(", ") + "</code>";
      i++;
    }
    document.getElementById("mulai").onclick = function () { gAnim.innerHTML = ""; i = 0; if (timer) { clearInterval(timer); } timer = setInterval(tambah, 350); };
    document.getElementById("selesai").onclick = function () { if (timer) { clearInterval(timer); timer = null; } gAnim.innerHTML = ""; i = 0; while (i < fb.features.length) { tambah(); } };
    keMadura();
  }

  function langkah4() {
    reset();
    var daftar = [
      ["buffer_puskesmas_5km.geojson", "Buffer puskesmas 5 km", "#f0a030", true],
      ["buffer_puskesmas_2km.geojson", "Buffer puskesmas 2 km", "#2b83ba", true],
      ["buffer_rs_20km.geojson", "Buffer rumah sakit 20 km", "#d73027", false],
      ["service_area_1km.geojson", "Wilayah layanan 1 km (pendekatan)", "#7b3294", false]
    ];
    var html = "";
    daftar.forEach(function (d, i) {
      if (DATA[d[0]]) {
        var jmlSudut = 0;
        DATA[d[0]].features.forEach(function (f) { jmlSudut += f.geometry.coordinates[0].length; });
        html += '<label><input type="checkbox" id="cb' + i + '"' + (d[3] ? " checked" : "") + '> <span class="k" style="display:inline-block;width:12px;height:12px;background:' + d[2] + ';opacity:.7"></span> ' + d[1] +
          " <small>(" + DATA[d[0]].features.length + " poligon, " + jmlSudut + " titik sudut)</small></label>";
        if (d[3]) { pathBuf[d[0]].setAttribute("display", "inline"); }
      }
    });
    panel.innerHTML =
      '<div class="kartu leg"><h2>Langkah 4. Hasil buffer</h2>' +
      "<p>Setelah semua titik diproses, hasilnya berupa lapisan poligon baru. Lingkaran yang saling tumpang tindih tampak menyatu. Centang untuk menyalakan atau mematikan lapisan.</p>" + html +
      '<div class="qgis"><b>Padanan di QGIS:</b> lapisan hasil Buffer. Untuk menyatukan lingkaran yang tumpang tindih menjadi satu bidang, gunakan Vector &gt; Geoprocessing Tools &gt; Dissolve.</div></div>';
    daftar.forEach(function (d, i) {
      var c = document.getElementById("cb" + i);
      if (c) { c.onchange = function () { pathBuf[d[0]].setAttribute("display", c.checked ? "inline" : "none"); }; }
    });
    keMadura();
  }

  function langkah5() {
    reset();
    if (!cellPath.length) { panel.innerHTML = '<div class="pesan">File grid_daratan.geojson tidak ditemukan. Jalankan buat_proses_buffer.py.</div>'; return; }
    gGrid.style.display = "inline";
    panel.innerHTML =
      '<div class="kartu"><h2>Langkah 5. Memotong dengan daratan dan menghitung cakupan</h2>' +
      "<p>Daratan Kabupaten Sumenep dibagi menjadi <b>" + cellPath.length + " sel</b> berukuran 1 km x 1 km (file <code>grid_daratan.geojson</code>). Tiap sel menyimpan atribut jarak ke puskesmas terdekat (<code>dP</code>) dan ke rumah sakit terdekat (<code>dR</code>). Sel yang jaraknya tidak lebih dari jari-jari buffer berarti <b>tercakup</b> (biru), selebihnya abu-abu.</p>" +
      '<label>Kelompok: <select id="kel"><option value="P">Puskesmas</option><option value="R">Rumah sakit</option></select></label>' +
      '<p style="margin:6px 0 0">Jari-jari buffer: <b id="rv">2</b> km</p><input type="range" id="rad" min="0.5" max="25" step="0.5" value="2">' +
      '<p>Sel tercakup: <span class="besar" id="nc">0</span> dari ' + cellPath.length + ' sel (sekitar <b id="km2">0</b> km2)</p>' +
      '<p>Persentase daratan tercakup: <span class="besar" id="pc">0</span> %</p>' +
      '<div class="qgis"><b>Padanan di QGIS:</b> Vector &gt; Geoprocessing Tools &gt; Clip (buffer dipotong dengan batas kabupaten), lalu hitung luas dengan Field Calculator <code>$area</code> dan bandingkan dengan luas daratan. Di sini dipakai grid karena QGIS tidak dapat dijalankan di HP, dan hasilnya setara dengan hitungan luas.</div>' +
      '<div class="catatan">Buffer berupa lingkaran garis lurus, belum menurut jalan. Persentase memakai luas daratan dari batas kabupaten.</div></div>';
    var sel = document.getElementById("kel");
    var rad = document.getElementById("rad");
    function hitung() {
      var r = parseFloat(rad.value);
      var arr = sel.value === "P" ? cellDP : cellDR;
      var titik = sel.value === "P" ? puskesmas : rumahSakit;
      var dCov = "", dUnc = "", n = 0;
      for (var i = 0; i < arr.length; i++) {
        if (arr[i] <= r) { dCov += cellPath[i]; n++; } else { dUnc += cellPath[i]; }
      }
      pCov.setAttribute("d", dCov);
      pUnc.setAttribute("d", dUnc);
      pCov.setAttribute("fill", sel.value === "P" ? "#2b83ba" : "#d73027");
      gLingkar.innerHTML = "";
      titik.forEach(function (t) {
        el("circle", { cx: t.x.toFixed(3), cy: t.y.toFixed(3), r: r, fill: "none", stroke: sel.value === "P" ? "#1c5f88" : "#9c1f18", "stroke-width": "1", "vector-effect": "non-scaling-stroke" }, gLingkar);
      });
      document.getElementById("rv").textContent = r;
      document.getElementById("nc").textContent = n;
      document.getElementById("km2").textContent = Math.round(n * 1.0);
      document.getElementById("pc").textContent = koma(100 * n / arr.length, 2);
    }
    rad.oninput = hitung;
    sel.onchange = function () { rad.value = sel.value === "P" ? 2 : 20; hitung(); };
    hitung();
    keMadura();
  }

  function parseCsv(t) {
    var baris = t.trim().split(/\r?\n/);
    var kolom = baris[0].split(",");
    return baris.slice(1).map(function (b) {
      var s = b.split(",");
      var o = {};
      kolom.forEach(function (k, i) { o[k] = s[i]; });
      return o;
    });
  }

  function langkah6() {
    reset();
    gGrid.style.display = "inline";
    if (pCov) { pCov.setAttribute("d", ""); }
    if (pUnc) { pUnc.setAttribute("d", ""); }
    Object.keys(pathBuf).forEach(function (k) { if (k !== "service_area_1km.geojson") { pathBuf[k].setAttribute("display", "inline"); } });
    panel.innerHTML = '<div class="kartu"><h2>Langkah 6. Hasil akhir</h2><p id="tabelcak">Memuat tabel...</p></div>';
    fetch("hasil_cakupan.csv").then(function (r) { return r.text(); }).then(function (t) {
      var rows = parseCsv(t);
      var tb = "";
      rows.forEach(function (r) {
        tb += "<tr><td>" + r.kategori + "</td><td>" + r.radius_km + "</td><td>" + koma(r.persen_tercakup, 2) + " %</td><td>" + koma(r.persen_tidak_tercakup, 2) + " %</td></tr>";
      });
      document.getElementById("tabelcak").outerHTML =
        '<div class="geser"><table><tr><th>Kategori</th><th>Radius (km)</th><th>Tercakup</th><th>Tidak tercakup</th></tr>' + tb + "</table></div>" +
        '<div class="catatan">Angka di tabel ini sama dengan hitungan geser pada Langkah 5, karena berasal dari data yang sama.</div>' +
        '<p><b>Unduh data asli:</b><br><a href="fasilitas_gabungan.geojson">fasilitas_gabungan.geojson</a><br><a href="buffer_puskesmas_2km.geojson">buffer_puskesmas_2km.geojson</a><br><a href="buffer_puskesmas_5km.geojson">buffer_puskesmas_5km.geojson</a><br><a href="buffer_rs_20km.geojson">buffer_rs_20km.geojson</a><br><a href="grid_daratan.geojson">grid_daratan.geojson</a></p>' +
        '<p>Halaman lain: <a href="galeri_peta.html">galeri peta (mengikuti gambar jurnal)</a> | <a href="peta_sumenep.html">peta interaktif</a> | <a href="index.html">ringkasan</a></p>';
    }).catch(function () {
      document.getElementById("tabelcak").textContent = "hasil_cakupan.csv tidak ditemukan.";
    });
    keMadura();
  }

  var DAFTAR = [
    ["1. Data awal", langkah1], ["2. Pilih dan jarak", langkah2], ["3. Proses buffer", langkah3],
    ["4. Hasil buffer", langkah4], ["5. Cakupan", langkah5], ["6. Hasil akhir", langkah6]
  ];
  function pilih(i) {
    var tombol = nav.querySelectorAll("button");
    for (var k = 0; k < tombol.length; k++) { tombol[k].className = k === i ? "aktif" : ""; }
    DAFTAR[i][1]();
  }
  DAFTAR.forEach(function (d, i) {
    var b = document.createElement("button");
    b.textContent = d[0];
    b.onclick = function () { pilih(i); };
    nav.appendChild(b);
  });

  // ---------------- muat data ----------------
  var janji = FILES.map(function (f) {
    return fetch(f[0]).then(function (r) {
      if (!r.ok) { throw new Error("tidak ada"); }
      return r.text();
    }).then(function (t) {
      UKURAN[f[0]] = t.length;
      DATA[f[0]] = JSON.parse(t);
    }).catch(function () { DATA[f[0]] = null; });
  });
  Promise.all(janji).then(function () {
    if (!DATA["fasilitas_gabungan.geojson"]) {
      panel.innerHTML = '<div class="pesan">File GeoJSON tidak terbaca. Buka halaman ini lewat server (python -m http.server 8000), jangan langsung dari file.</div>';
      return;
    }
    bangunLapisan();
    pilih(0);
  });
})();
</script>
</body>
</html>
"""


def tulis_halaman():
    with open("proses_buffer.html", "w", encoding="utf-8") as f:
        f.write(HTML)
    print("Tersimpan: proses_buffer.html")


def pasang_tombol_di_index():
    if not os.path.exists("index.html"):
        return
    with open("index.html", encoding="utf-8") as f:
        t = f.read()
    if "proses_buffer.html" in t:
        print("index.html sudah memuat tombol proses buffer.")
        return
    kunci = '<a class="tombol" href="peta_sumenep.html">Buka Peta Interaktif</a>'
    if kunci not in t:
        print("Tombol di index.html tidak dipasang (penanda tidak ditemukan).")
        return
    tambahan = (
        '\n  <a class="tombol" style="background:#1F3A5F" href="proses_buffer.html">Lihat Proses Buffer Langkah demi Langkah</a>'
        '\n  <a class="tombol" style="background:#7b3294" href="galeri_peta.html">Galeri Peta (mengikuti jurnal)</a>'
    )
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(t.replace(kunci, kunci + tambahan))
    print("Tombol proses buffer dan galeri dipasang di index.html")


def main():
    if buat_grid():
        tulis_halaman()
        pasang_tombol_di_index()
        print("Selesai. Buka: localhost:8000/proses_buffer.html")


main()
