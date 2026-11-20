"""
File Name: radar.py

Author: Jonathan W (web port written with Claude)
Date Created: 11/19/2026
Last Update: 11/19/2026
Version: 1.0.0-web

Scope: The Leaflet radar page from widgets.py as a plain HTML string, so Streamlit can show it in an iframe.
    No Qt needed. Placeholders are swapped with str.replace.
"""


RADAR_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#map{height:100%;margin:0;background:%BG%}
#stamp{position:absolute;left:12px;bottom:12px;z-index:1000;padding:6px 10px;border-radius:6px;
  background:%BG%;color:%TEXT%;font:13px sans-serif;opacity:.92}
</style>
</head><body><div id="map"></div><div id="stamp">Loading radar…</div><script>
const LAT = %LAT%, LON = %LON%;
const map = L.map('map').setView([LAT, LON], 7);
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_%CANVAS%_Gray_';
L.tileLayer(ESRI + 'Base/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 16, attribution: 'Basemap &copy; Esri'
}).addTo(map);
// Labels get their own pane above the radar so they're never buried
map.createPane('labels');
map.getPane('labels').style.zIndex = 650;
map.getPane('labels').style.pointerEvents = 'none';
L.tileLayer(ESRI + 'Reference/MapServer/tile/{z}/{y}/{x}', {maxZoom: 16, pane: 'labels'}).addTo(map);
L.circleMarker([LAT, LON], {radius: 7, color: '%ACCENT%', fillColor: '%ACCENT%', fillOpacity: 1}).addTo(map);
const stamp = document.getElementById('stamp');

function animate(layers, labels) {
  let i = layers.length - 1;
  layers[i].setOpacity(0.85); stamp.textContent = labels[i];
  setInterval(() => {
    layers[i].setOpacity(0); i = (i + 1) % layers.length;
    layers[i].setOpacity(0.85); stamp.textContent = labels[i];
  }, 700);
}

// Rough NEXRAD coverage box (lower 48, Alaska, Hawaii, Puerto Rico)
const inUS = LAT > 17 && LAT < 72 && LON > -170 && LON < -64;

if (inUS) {
  const offsets = [50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0];  // minutes ago, oldest first
  const layers = offsets.map(m => L.tileLayer(
    'https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913' +
      (m ? '-m' + String(m).padStart(2, '0') + 'm' : '') + '/{z}/{x}/{y}.png',
    {opacity: 0, attribution: 'NEXRAD via Iowa Environmental Mesonet'}
  ).addTo(map));
  animate(layers, offsets.map(m => m ? m + ' min ago' : 'Now'));
} else {
  fetch('https://api.rainviewer.com/public/weather-maps.json').then(r => r.json()).then(data => {
    const frames = data.radar.past;
    const layers = frames.map(f => L.tileLayer(data.host + f.path + '/256/{z}/{x}/{y}/2/1_1.png', {
      opacity: 0, maxNativeZoom: 7, attribution: 'Radar &copy; RainViewer'
    }).addTo(map));
    animate(layers, frames.map(f => new Date(f.time * 1000).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})));
  }).catch(() => { stamp.textContent = 'Radar unavailable right now'; });
}
</script></body></html>"""


def radar_html(latitude: float, longitude: float, colors) -> str:
    """Builds the radar page for a location, using the current theme's colors.

    Args:
        latitude: Decimal degrees.
        longitude: Decimal degrees.
        colors: A theme.Theme-like object with window, text and accent colors.

    Returns:
        A complete HTML document.
    """
    is_light = colors.name == "Daylight"
    return (
        RADAR_HTML.replace("%LAT%", f"{latitude:.4f}")
        .replace("%LON%", f"{longitude:.4f}")
        .replace("%CANVAS%", "Light" if is_light else "Dark")
        .replace("%BG%", colors.window)
        .replace("%TEXT%", colors.text)
        .replace("%ACCENT%", colors.accent)
    )
