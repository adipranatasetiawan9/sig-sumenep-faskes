import csv
import html
import json
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


titik = baca_geojson("fasilitas_gabungan.geojson")
buf3 = baca_geojson("buffer_3km.geojson")
buf5 = baca_geojson("buffer_5km.geojson")
batas = baca_geojson("batas_kecamatan.geojson")

# ---------------------------------------------------------------
# 1. PETA INTERAKTIF
# ---------------------------------------------------------------
HTML_PETA = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Peta Fasilitas Kesehatan Kabupaten Pamekasan</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<style>
html, body { height: 100%; margin: 0; }
#peta { height: 100%; background: #eef2f5; }
.legenda { background: rgba(255,255,255,0.95); padding: 8px 10px; border-radius: 6px; font: 12.5px sans-serif; line-height: 1.65; box-shadow: 0 1px 4px rgba(0,0,0,0.3); }
.legenda b { display: block; margin-bottom: 2px; }
.dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; border: 1px solid #fff; box-shadow: 0 0 0 1px #888; }
.label-fas { background: rgba(255,255,255,0.88); border: none; box-shadow: none; font: 11px sans-serif; padding: 1px 4px; color: #222; }
.sembunyi-label .label-fas { display: none; }
.tombol-reset a { font-size: 20px; line-height: 30px; width: 30px; height: 30px; text-align: center; text-decoration: none; display: block; color: #333; background: #fff; }
</style>
</head>
<body>
<div id="peta"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
var TITIK = __TITIK__;
var BUF3 = __BUF3__;
var BUF5 = __BUF5__;
var BATAS = __BATAS__;

var peta = L.map("peta", { zoomControl: true }).setView([-7.12, 113.50], 10);

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

var warna = { "Puskesmas": "#1a9850", "Rumah Sakit": "#d73027", "Klinik/Lainnya": "#4575b4" };

function singkat(n) {
  return n.replace(/^Puskesmas /, "Pusk. ").replace(/^Rumah Sakit( Umum)? /, "RS ");
}

var lapisBuf5 = L.geoJSON(BUF5, { style: { color: "#f39c12", weight: 1, fillColor: "#f39c12", fillOpacity: 0.10 } });
var lapisBuf3 = L.geoJSON(BUF3, { style: { color: "#2b83ba", weight: 1, fillColor: "#2b83ba", fillOpacity: 0.16 } });

var lapisTitik = L.geoJSON(TITIK, {
  pointToLayer: function (f, ll) {
    var w = warna[f.properties.jenis] || "#555555";
    return L.circleMarker(ll, { radius: 7, color: "#ffffff", weight: 1.5, fillColor: w, fillOpacity: 0.95 });
  },
  onEachFeature: function (f, layer) {
    layer.bindPopup("<b>" + f.properties.nama + "</b><br>" + f.properties.jenis);
    layer.bindTooltip(singkat(f.properties.nama), {
      permanent: true, direction: "right", offset: [8, 0], className: "label-fas"
    });
  }
});

var overlay = {};
if (BATAS.features.length > 0) {
  var lapisBatas = L.geoJSON(BATAS, {
    style: { color: "#555555", weight: 1.5, fill: false, dashArray: "4 3" },
    onEachFeature: function (f, layer) {
      var p = f.properties || {};
      var nama = p.nama || p.NAMOBJ || p.WADMKC || p.NAME_3 || p.name || "";
      if (nama) { layer.bindTooltip(nama, { sticky: true }); }
    }
  });
  lapisBatas.addTo(peta);
  overlay["Batas kecamatan"] = lapisBatas;
}
lapisBuf5.addTo(peta);
lapisBuf3.addTo(peta);
lapisTitik.addTo(peta);
overlay["Buffer 5 km"] = lapisBuf5;
overlay["Buffer 3 km"] = lapisBuf3;
overlay["Fasilitas kesehatan"] = lapisTitik;

L.control.layers({
  "OpenStreetMap": petaOsm,
  "Humanitarian OSM": petaHot,
  "Citra satelit (Esri)": petaSatelit,
  "Tanpa peta dasar (polos)": petaPolos
}, overlay, { collapsed: true, position: "topright" }).addTo(peta);

L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(peta);

// ---- zoom otomatis ke Pamekasan ----
var semua = [];
TITIK.features.forEach(function (f) {
  semua.push([f.geometry.coordinates[1], f.geometry.coordinates[0]]);
});
var batasTampil = semua.length > 0
  ? L.latLngBounds(semua).pad(0.25)
  : L.latLngBounds([[-7.35, 113.25], [-6.85, 113.75]]);

function aturLabel() {
  var kotak = document.getElementById("peta");
  if (peta.getZoom() < 11) { kotak.classList.add("sembunyi-label"); }
  else { kotak.classList.remove("sembunyi-label"); }
}

function zoomKePamekasan() {
  peta.invalidateSize();
  peta.fitBounds(batasTampil, { maxZoom: 13 });
  aturLabel();
}

peta.on("zoomend", aturLabel);
zoomKePamekasan();
setTimeout(zoomKePamekasan, 300);
window.addEventListener("load", zoomKePamekasan);

// ---- tombol "kembali ke Pamekasan" ----
var Tombol = L.Control.extend({
  options: { position: "topleft" },
  onAdd: function () {
    var b = L.DomUtil.create("div", "leaflet-bar tombol-reset");
    b.innerHTML = '<a href="#" title="Zoom ke Pamekasan" role="button">&#8962;</a>';
    L.DomEvent.disableClickPropagation(b);
    L.DomEvent.on(b, "click", function (e) {
      L.DomEvent.preventDefault(e);
      zoomKePamekasan();
    });
    return b;
  }
});
new Tombol().addTo(peta);

// ---- legenda dengan jumlah ----
var hitung = {};
TITIK.features.forEach(function (f) {
  var j = f.properties.jenis;
  hitung[j] = (hitung[j] || 0) + 1;
});
var leg = L.control({ position: "bottomright" });
leg.onAdd = function () {
  var d = L.DomUtil.create("div", "legenda");
  d.innerHTML =
    "<b>Fasilitas Kesehatan Kab. Pamekasan (" + TITIK.features.length + ")</b>" +
    '<span class="dot" style="background:#1a9850"></span>Puskesmas (' + (hitung["Puskesmas"] || 0) + ")<br>" +
    '<span class="dot" style="background:#d73027"></span>Rumah Sakit (' + (hitung["Rumah Sakit"] || 0) + ")<br>" +
    '<span class="dot" style="background:#4575b4"></span>Klinik/Lainnya (' + (hitung["Klinik/Lainnya"] || 0) + ")";
  return d;
};
leg.addTo(peta);
</script>
</body>
</html>
"""

HTML_PETA = HTML_PETA.replace("__TITIK__", json.dumps(titik))
HTML_PETA = HTML_PETA.replace("__BUF3__", json.dumps(buf3))
HTML_PETA = HTML_PETA.replace("__BUF5__", json.dumps(buf5))
HTML_PETA = HTML_PETA.replace("__BATAS__", json.dumps(batas))

with open("peta_pamekasan.html", "w", encoding="utf-8") as f:
    f.write(HTML_PETA)

# ---------------------------------------------------------------
# 2. MENU AWAL (index.html)
# ---------------------------------------------------------------
fasilitas = baca_csv("fasilitas_gabungan.csv")
nn = {}
for r in baca_csv("hasil_nearest_neighbor.csv"):
    nn[r["nama"]] = r

jumlah = {"Puskesmas": 0, "Rumah Sakit": 0, "Klinik/Lainnya": 0}
for r in fasilitas:
    jumlah[r["jenis"]] = jumlah.get(r["jenis"], 0) + 1

baris = ""
total_jarak = 0.0
n_jarak = 0
for i, r in enumerate(fasilitas, 1):
    info = nn.get(r["nama"])
    if info:
        tetangga = html.escape(info["tetangga_terdekat"]) + " (" + info["jarak_km"] + " km)"
        total_jarak += float(info["jarak_km"])
        n_jarak += 1
    else:
        tetangga = "-"
    baris += "<tr><td>%d</td><td>%s</td><td>%s</td><td>%.5f, %.5f</td><td>%s</td></tr>\n" % (
        i, html.escape(r["nama"]), html.escape(r["jenis"]),
        float(r["lat"]), float(r["lon"]), tetangga,
    )

rata = "-"
if n_jarak > 0:
    rata = "%.2f km" % (total_jarak / n_jarak)

unduhan = ""
for nama_file in [
    "fasilitas_gabungan.csv",
    "fasilitas_gabungan.geojson",
    "buffer_3km.geojson",
    "buffer_5km.geojson",
    "hasil_nearest_neighbor.csv",
    "data_manual.csv",
]:
    if os.path.exists(nama_file):
        unduhan += '<li><a href="%s">%s</a></li>\n' % (nama_file, nama_file)

HTML_INDEX = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analisis Aksesibilitas Fasilitas Kesehatan Pamekasan</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #f2f5f9; color: #1d2733; line-height: 1.55; }
header { background: #1F3A5F; color: #fff; padding: 22px 16px; }
header h1 { margin: 0 0 4px; font-size: 20px; line-height: 1.3; }
header p { margin: 0; font-size: 13.5px; opacity: 0.9; }
main { max-width: 760px; margin: 0 auto; padding: 14px; }
.kartu { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 6px 0 14px; }
.angka { background: #fff; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.angka b { display: block; font-size: 26px; color: #1F3A5F; }
.angka span { font-size: 12.5px; color: #55606e; }
.tombol { display: block; text-align: center; background: #1a9850; color: #fff; text-decoration: none; padding: 14px; border-radius: 10px; font-weight: 600; font-size: 16px; margin-bottom: 18px; }
section { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
h2 { margin: 0 0 8px; font-size: 16px; color: #1F3A5F; }
.geser { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; min-width: 560px; }
th { background: #1F3A5F; color: #fff; text-align: left; padding: 6px; }
td { padding: 6px; border-bottom: 1px solid #e3e8ee; vertical-align: top; }
tr:nth-child(even) td { background: #f7f9fc; }
ul { margin: 6px 0 0; padding-left: 20px; }
li { margin: 3px 0; }
footer { text-align: center; font-size: 12px; color: #6a7685; padding: 8px 14px 24px; }
</style>
</head>
<body>
<header>
  <h1>Analisis Aksesibilitas Fasilitas Kesehatan di Kabupaten Pamekasan</h1>
  <p>Tugas Sistem Informasi Geografis Lanjut. Acuan: Obeidat &amp; Alourd (2024), Int. J. for Equity in Health 23:52.</p>
</header>
<main>
  <div class="kartu">
    <div class="angka"><b>__TOTAL__</b><span>Total fasilitas</span></div>
    <div class="angka"><b>__PUSKESMAS__</b><span>Puskesmas</span></div>
    <div class="angka"><b>__RS__</b><span>Rumah sakit</span></div>
    <div class="angka"><b>__KLINIK__</b><span>Klinik/lainnya</span></div>
  </div>

  <a class="tombol" href="peta_pamekasan.html">Buka Peta Interaktif</a>

  <section>
    <h2>Ringkasan</h2>
    <p style="margin:0">Data fasilitas diambil dari OpenStreetMap dan dilengkapi koordinat puskesmas dari Google Maps. Rata-rata jarak ke tetangga terdekat: <b>__RATA__</b>.</p>
  </section>

  <section>
    <h2>Daftar Fasilitas dan Tetangga Terdekat</h2>
    <div class="geser">
    <table>
      <tr><th>No</th><th>Nama</th><th>Jenis</th><th>Koordinat (lat, lon)</th><th>Tetangga terdekat</th></tr>
__BARIS__
    </table>
    </div>
  </section>

  <section>
    <h2>Unduh / Buka Data</h2>
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
HTML_INDEX = HTML_INDEX.replace("__KLINIK__", str(jumlah.get("Klinik/Lainnya", 0)))
HTML_INDEX = HTML_INDEX.replace("__RATA__", rata)
HTML_INDEX = HTML_INDEX.replace("__BARIS__", baris)
HTML_INDEX = HTML_INDEX.replace("__UNDUHAN__", unduhan)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML_INDEX)

print("Selesai: peta_pamekasan.html dan index.html")
print("Jumlah titik:", len(titik["features"]))
if len(batas["features"]) > 0:
    print("Batas kecamatan: dimuat,", len(batas["features"]), "fitur")
else:
    print("Batas kecamatan: belum ada (opsional: batas_kecamatan.geojson)")
