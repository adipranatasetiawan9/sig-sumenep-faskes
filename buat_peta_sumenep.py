import csv
import html
import json
import math
import os


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


def sederhana(geo, maks=300):
    for fit in geo.get("features", []):
        g = fit.get("geometry") or {}
        if g.get("type") == "MultiPolygon":
            polys = g["coordinates"]
        elif g.get("type") == "Polygon":
            polys = [g["coordinates"]]
        else:
            continue
        for poly in polys:
            for i, ring in enumerate(poly):
                r2 = [[round(c[0], 5), round(c[1], 5)] for c in ring]
                if len(r2) > maks:
                    k = int(math.ceil(len(r2) / float(maks)))
                    r2 = r2[::k]
                    if r2[0] != r2[-1]:
                        r2.append(r2[0])
                poly[i] = r2
    return geo


titik = baca_geojson("fasilitas_gabungan.geojson")
kec = sederhana(baca_geojson("batas_kecamatan.geojson"))
b2 = baca_geojson("buffer_puskesmas_2km.geojson")
b5 = baca_geojson("buffer_puskesmas_5km.geojson")
brs = baca_geojson("buffer_rs_20km.geojson")
sa = baca_geojson("service_area_1km.geojson")

# ---------------------------------------------------------------
# 1. PETA INTERAKTIF
# ---------------------------------------------------------------
HTML_PETA = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Peta Fasilitas Kesehatan Kabupaten Sumenep</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<style>
html, body { height: 100%; margin: 0; }
#peta { height: 100%; background: #eef2f5; }
.legenda { background: rgba(255,255,255,0.95); padding: 8px 10px; border-radius: 6px; font: 12.5px sans-serif; line-height: 1.65; box-shadow: 0 1px 4px rgba(0,0,0,0.3); }
.legenda b { display: block; margin-bottom: 2px; }
.dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; border: 1px solid #fff; box-shadow: 0 0 0 1px #888; }
.label-fas { background: rgba(255,255,255,0.88); border: none; box-shadow: none; font: 11px sans-serif; padding: 1px 4px; color: #222; }
.sembunyi-label .label-fas { display: none; }
.tombol a { font: bold 14px sans-serif; line-height: 30px; width: 30px; height: 30px; text-align: center; text-decoration: none; display: block; color: #333; background: #fff; }
</style>
</head>
<body>
<div id="peta"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
var TITIK = __TITIK__;
var KEC = __KEC__;
var B2 = __B2__;
var B5 = __B5__;
var BRS = __BRS__;
var SA = __SA__;

var peta = L.map("peta", { zoomControl: true }).setView([-7.05, 113.85], 10);

var petaOsm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
});
var petaHot = L.tileLayer("https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png", {
  subdomains: "abc", maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors, Humanitarian OSM"
});
var petaSatelit = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Tiles &copy; Esri"
});
var petaPolos = L.layerGroup();
petaOsm.addTo(peta);

var warna = { "Puskesmas": "#1a9850", "Rumah Sakit": "#d73027", "Klinik/Lainnya": "#4575b4", "Pustu/Poskesdes": "#984ea3" };

function singkat(n) {
  return n.replace(/^Puskesmas /, "Pusk. ").replace(/^Rumah Sakit( Umum)? /, "RS ");
}

var lapisKec = L.geoJSON(KEC, {
  style: { color: "#444444", weight: 1.2, fillColor: "#ffffff", fillOpacity: 0.05, dashArray: "4 3" },
  onEachFeature: function (f, layer) {
    var p = f.properties || {};
    var nama = p.nama || "";
    if (nama) { layer.bindTooltip("Kec. " + nama, { sticky: true }); }
  }
});
var lapisBRS = L.geoJSON(BRS, { style: { color: "#d73027", weight: 1, fillColor: "#d73027", fillOpacity: 0.07 } });
var lapisB5 = L.geoJSON(B5, { style: { color: "#f39c12", weight: 1, fillColor: "#f39c12", fillOpacity: 0.12 } });
var lapisB2 = L.geoJSON(B2, { style: { color: "#2b83ba", weight: 1, fillColor: "#2b83ba", fillOpacity: 0.20 } });
var lapisSA = L.geoJSON(SA, { style: { color: "#7b3294", weight: 1, fillColor: "#7b3294", fillOpacity: 0.25 } });

var lapisTitik = L.geoJSON(TITIK, {
  pointToLayer: function (f, ll) {
    var w = warna[f.properties.jenis] || "#555555";
    return L.circleMarker(ll, { radius: 7, color: "#ffffff", weight: 1.5, fillColor: w, fillOpacity: 0.95 });
  },
  onEachFeature: function (f, layer) {
    var p = f.properties;
    layer.bindPopup("<b>" + p.nama + "</b><br>" + p.jenis + "<br>Kecamatan: " + (p.kecamatan || "-"));
    layer.bindTooltip(singkat(p.nama), {
      permanent: true, direction: "right", offset: [8, 0], className: "label-fas"
    });
  }
});

lapisKec.addTo(peta);
lapisB5.addTo(peta);
lapisTitik.addTo(peta);

L.control.layers({
  "OpenStreetMap": petaOsm,
  "Humanitarian OSM": petaHot,
  "Citra satelit (Esri)": petaSatelit,
  "Tanpa peta dasar (polos)": petaPolos
}, {
  "Batas kecamatan": lapisKec,
  "Buffer RS 20 km": lapisBRS,
  "Buffer puskesmas 5 km": lapisB5,
  "Buffer puskesmas 2 km": lapisB2,
  "Service area 1 km (pendekatan)": lapisSA,
  "Fasilitas kesehatan": lapisTitik
}, { collapsed: true, position: "topright" }).addTo(peta);

L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(peta);

var MADURA = [[-7.28, 113.55], [-6.80, 114.20]];
var SEMUA = [[-7.30, 113.50], [-5.45, 116.00]];

function aturLabel() {
  var kotak = document.getElementById("peta");
  if (peta.getZoom() < 11) { kotak.classList.add("sembunyi-label"); }
  else { kotak.classList.remove("sembunyi-label"); }
}

function keMadura() { peta.invalidateSize(); peta.fitBounds(MADURA); aturLabel(); }
function keSemua() { peta.invalidateSize(); peta.fitBounds(SEMUA); aturLabel(); }

peta.on("zoomend", aturLabel);
keMadura();
setTimeout(keMadura, 300);

var Tombol = L.Control.extend({
  options: { position: "topleft" },
  onAdd: function () {
    var b = L.DomUtil.create("div", "leaflet-bar tombol");
    b.innerHTML = '<a href="#" id="t-madura" title="Zoom ke daratan Madura">M</a><a href="#" id="t-semua" title="Zoom ke seluruh Sumenep">S</a>';
    L.DomEvent.disableClickPropagation(b);
    L.DomEvent.on(b.querySelector("#t-madura"), "click", function (e) { L.DomEvent.preventDefault(e); keMadura(); });
    L.DomEvent.on(b.querySelector("#t-semua"), "click", function (e) { L.DomEvent.preventDefault(e); keSemua(); });
    return b;
  }
});
new Tombol().addTo(peta);

var hitung = {};
TITIK.features.forEach(function (f) {
  var j = f.properties.jenis;
  hitung[j] = (hitung[j] || 0) + 1;
});
var leg = L.control({ position: "bottomright" });
leg.onAdd = function () {
  var d = L.DomUtil.create("div", "legenda");
  var isi = "<b>Fasilitas Kesehatan Kab. Sumenep (" + TITIK.features.length + ")</b>";
  Object.keys(hitung).forEach(function (j) {
    isi += '<span class="dot" style="background:' + (warna[j] || "#555") + '"></span>' + j + " (" + hitung[j] + ")<br>";
  });
  isi += "<small>M = daratan Madura, S = seluruh kabupaten</small>";
  d.innerHTML = isi;
  return d;
};
leg.addTo(peta);
</script>
</body>
</html>
"""

HTML_PETA = HTML_PETA.replace("__TITIK__", json.dumps(titik))
HTML_PETA = HTML_PETA.replace("__KEC__", json.dumps(kec))
HTML_PETA = HTML_PETA.replace("__B2__", json.dumps(b2))
HTML_PETA = HTML_PETA.replace("__B5__", json.dumps(b5))
HTML_PETA = HTML_PETA.replace("__BRS__", json.dumps(brs))
HTML_PETA = HTML_PETA.replace("__SA__", json.dumps(sa))

with open("peta_sumenep.html", "w", encoding="utf-8") as f:
    f.write(HTML_PETA)

# ---------------------------------------------------------------
# 2. HALAMAN RINGKASAN (index.html)
# ---------------------------------------------------------------
def tabel(judul_kolom, baris):
    h = "<div class=\"geser\"><table><tr>"
    for k in judul_kolom:
        h += "<th>%s</th>" % html.escape(k)
    h += "</tr>\n"
    for b in baris:
        h += "<tr>" + "".join("<td>%s</td>" % html.escape(str(x)) for x in b) + "</tr>\n"
    h += "</table></div>"
    return h


fasilitas = baca_csv("fasilitas_gabungan.csv")
jumlah = {}
for r in fasilitas:
    jumlah[r["jenis"]] = jumlah.get(r["jenis"], 0) + 1

kec_rows = []
for r in baca_csv("tabel_kecamatan.csv"):
    kec_rows.append([
        r["kecamatan"], r["puskesmas"], r["rumah_sakit"], r["semua_fasilitas"],
        r["penduduk"] or "-", r["puskesmas_per_100rb"] or "-",
    ])
tabel_kec = tabel(["Kecamatan", "Puskesmas", "RS", "Semua", "Penduduk", "Puskesmas/100rb"], kec_rows)

nn_rows = []
for r in baca_csv("hasil_nn_ringkas.csv"):
    nn_rows.append([r["wilayah"], r["kategori"], r["n"], r["d_obs_km"], r["d_exp_km"], r["NNR"], r["z"], r["p"], r["pola"]])
tabel_nn = tabel(["Wilayah", "Kategori", "n", "d obs (km)", "d harapan (km)", "NNR", "z", "p", "Pola"], nn_rows)

cak_rows = []
for r in baca_csv("hasil_cakupan.csv"):
    cak_rows.append([r["kategori"], r["radius_km"], r["persen_tercakup"], r["persen_tidak_tercakup"]])
tabel_cak = tabel(["Kategori", "Radius (km)", "Tercakup (%)", "Tidak tercakup (%)"], cak_rows)

daftar_fas = []
for i, r in enumerate(fasilitas, 1):
    daftar_fas.append([i, r["nama"], r["jenis"], r.get("kecamatan", ""), "%.5f, %.5f" % (float(r["lat"]), float(r["lon"]))])
tabel_fas = tabel(["No", "Nama", "Jenis", "Kecamatan", "Koordinat"], daftar_fas)

unduhan = ""
for nama_file in [
    "fasilitas_gabungan.csv", "fasilitas_gabungan.geojson", "tabel_kecamatan.csv",
    "hasil_nn_ringkas.csv", "hasil_cakupan.csv", "hasil_nearest_neighbor.csv",
    "buffer_puskesmas_2km.geojson", "buffer_puskesmas_5km.geojson",
    "buffer_rs_20km.geojson", "service_area_1km.geojson",
    "ringkasan_analisis.txt", "data_manual_sumenep.csv",
]:
    if os.path.exists(nama_file):
        unduhan += '<li><a href="%s">%s</a></li>\n' % (nama_file, nama_file)

HTML_INDEX = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aksesibilitas Fasilitas Kesehatan Kabupaten Sumenep</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #f2f5f9; color: #1d2733; line-height: 1.55; }
header { background: #1F3A5F; color: #fff; padding: 22px 16px; }
header h1 { margin: 0 0 4px; font-size: 20px; line-height: 1.3; }
header p { margin: 0; font-size: 13.5px; opacity: 0.9; }
main { max-width: 860px; margin: 0 auto; padding: 14px; }
.kartu { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 6px 0 14px; }
.angka { background: #fff; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.angka b { display: block; font-size: 26px; color: #1F3A5F; }
.angka span { font-size: 12.5px; color: #55606e; }
.tombol { display: block; text-align: center; background: #1a9850; color: #fff; text-decoration: none; padding: 14px; border-radius: 10px; font-weight: 600; font-size: 16px; margin-bottom: 18px; }
section { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
h2 { margin: 0 0 8px; font-size: 16px; color: #1F3A5F; }
.geser { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; min-width: 520px; }
th { background: #1F3A5F; color: #fff; text-align: left; padding: 6px; }
td { padding: 6px; border-bottom: 1px solid #e3e8ee; vertical-align: top; }
tr:nth-child(even) td { background: #f7f9fc; }
ul { margin: 6px 0 0; padding-left: 20px; }
li { margin: 3px 0; }
.catatan { background: #fff8e6; border-left: 4px solid #f0ad4e; }
footer { text-align: center; font-size: 12px; color: #6a7685; padding: 8px 14px 24px; }
</style>
</head>
<body>
<header>
  <h1>Analisis Aksesibilitas Fasilitas Kesehatan di Kabupaten Sumenep</h1>
  <p>Tugas Sistem Informasi Geografis Lanjut. Acuan metode: Obeidat &amp; Alourd (2024), Int. J. for Equity in Health 23:52 (doi:10.1186/s12939-024-02120-8).</p>
</header>
<main>
  <div class="kartu">
    <div class="angka"><b>__TOTAL__</b><span>Total fasilitas</span></div>
    <div class="angka"><b>__PUSKESMAS__</b><span>Puskesmas</span></div>
    <div class="angka"><b>__RS__</b><span>Rumah sakit</span></div>
    <div class="angka"><b>__KLINIK__</b><span>Klinik/lainnya</span></div>
  </div>

  <a class="tombol" href="peta_sumenep.html">Buka Peta Interaktif</a>

  <section>
    <h2>1. Tabel per Kecamatan</h2>
    __TABEL_KEC__
  </section>

  <section>
    <h2>2. Nearest Neighbor</h2>
    __TABEL_NN__
    <p style="font-size:12.5px;margin:8px 0 0">NNR di bawah 1 berarti mengelompok, sekitar 1 berarti acak, di atas 1 berarti menyebar. Hasil &quot;seluruh kabupaten&quot; terpengaruh jarak Pulau Masalembu yang sangat jauh, sehingga hasil &quot;daratan Madura&quot; lebih mudah dibandingkan dengan jurnal acuan.</p>
  </section>

  <section>
    <h2>3. Persen Cakupan Wilayah (Buffer)</h2>
    __TABEL_CAK__
  </section>

  <section class="catatan">
    <h2>Catatan Keterbatasan</h2>
    <ul>
      <li>Buffer dan service area berupa lingkaran garis lurus, belum jarak lewat jalan.</li>
      <li>Radius buffer mengikuti jurnal acuan (standar Yordania) sebagai pembanding, belum standar Indonesia.</li>
      <li>Data fasilitas dari OpenStreetMap dan Google Maps, belum data resmi Dinas Kesehatan. Pustu dan poskesdes belum dimasukkan, sehingga cakupan kemungkinan lebih rendah dari kenyataan.</li>
      <li>Data rumah sakit dan data penduduk per kecamatan masih dilengkapi.</li>
    </ul>
  </section>

  <section>
    <h2>Daftar Fasilitas</h2>
    __TABEL_FAS__
  </section>

  <section>
    <h2>Unduh Data</h2>
    <ul>
__UNDUHAN__
    </ul>
  </section>
</main>
<footer>Dibuat dengan Python di Termux. Peta dasar membutuhkan koneksi internet.</footer>
</body>
</html>
"""

HTML_INDEX = HTML_INDEX.replace("__TOTAL__", str(len(fasilitas)))
HTML_INDEX = HTML_INDEX.replace("__PUSKESMAS__", str(jumlah.get("Puskesmas", 0)))
HTML_INDEX = HTML_INDEX.replace("__RS__", str(jumlah.get("Rumah Sakit", 0)))
HTML_INDEX = HTML_INDEX.replace("__KLINIK__", str(jumlah.get("Klinik/Lainnya", 0) + jumlah.get("Pustu/Poskesdes", 0)))
HTML_INDEX = HTML_INDEX.replace("__TABEL_KEC__", tabel_kec)
HTML_INDEX = HTML_INDEX.replace("__TABEL_NN__", tabel_nn)
HTML_INDEX = HTML_INDEX.replace("__TABEL_CAK__", tabel_cak)
HTML_INDEX = HTML_INDEX.replace("__TABEL_FAS__", tabel_fas)
HTML_INDEX = HTML_INDEX.replace("__UNDUHAN__", unduhan)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML_INDEX)

print("Selesai: peta_sumenep.html dan index.html")
print("Jumlah titik:", len(titik["features"]))
print("Batas kecamatan:", len(kec["features"]), "fitur")
