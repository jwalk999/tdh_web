"""
File Name: app.py

Author: Jonathan W (web port written with Claude)
Date Created: 11/19/2026
Last Update: 11/19/2026
Version: 0.1.0-web

Scope: Streamlit version of Too Damn Hot!. Same pages as the desktop window (Now, Hourly, 10-Day, Alerts, Radar)
    with units, theme, heat threshold and location in the sidebar. Everything is read from the same modules the
    desktop app uses; only the drawing is different. Run it with: streamlit run app.py
"""

import gc
import io
import re
import threading
from html import escape
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

import theme
from Config.global_params import load_location
from Daily_Graph import make_daily_graphs
from geocoding import format_match, geocode, match_to_location
from Hourly_Graph import make_hourly_graphs
from quips import get_quip
from radar import radar_html
from weather_data import (
    bucket_kicker,
    build_view,
    fetch_raw,
    fmt_deg,
    fmt_hour,
    fmt_precip,
    fmt_temp,
    fmt_wind,
    uv_label,
)

HERE = Path(__file__).parent
GITHUB_URL = "https://github.com/jwalk999/TDH-Weather-Data-Visualizer"
PAGES = ["Now", "Hourly", "10-Day", "Alerts", "Radar"]
# Range the hourly bars are scaled across, in °F. Same as widgets.py.
BAR_MIN_F = 60
BAR_MAX_F = 115
SEVERITY_COLORS = {"Extreme": "hot", "Severe": "hot", "Moderate": "sunrise", "Minor": "sunrise"}
HEAT_TIPS = [
    "Drink water before you feel thirsty.",
    "Check on neighbors, older relatives and pets.",
    "Never leave anyone in a parked car. Not even for a minute.",
    "Do outdoor work before 10 AM or after 7 PM.",
]

st.set_page_config(
    page_title="Too Damn Hot!",
    page_icon=Image.open(HERE / "assets" / "hot-temperature.ico"),
    layout="wide",
)


_plot_lock = threading.Lock()


# ===== HELPERS =====
def html(markup: str) -> None:
    """Shows an HTML snippet. Newlines and indentation are removed first, because Markdown treats indented
    lines as code blocks.

    Args:
        markup: HTML to show. Text that came from outside (alerts, place names) must already be escaped.
    """
    st.markdown(re.sub(r"\n\s*", "", markup), unsafe_allow_html=True)


def _fraction(temp_f: float) -> float:
    """Position of a temperature along the hourly bar scale, 0.0 to 1.0."""
    return max(0.0, min(1.0, (temp_f - BAR_MIN_F) / (BAR_MAX_F - BAR_MIN_F)))


@st.cache_data(ttl=3600, show_spinner="Fetching the forecast...")
def cached_fetch(name: str, latitude: float, longitude: float, timezone: str) -> dict:
    """Fetches the forecast once an hour per place, which matches the desktop app's cache expiry.

    The arguments only make up the cache key and the request. Streamlit hashes them, so the same place on the
    same hour is shared by everyone visiting the site.

    Args:
        name: Display name.
        latitude: Decimal degrees.
        longitude: Decimal degrees.
        timezone: IANA timezone name.

    Returns:
        The dict from weather_data.fetch_raw().
    """
    location = {"location_name": name, "latitude": latitude, "longitude": longitude, "timezone": timezone}
    return fetch_raw(location)


def apply_page_style(colors: theme.Theme) -> None:
    """Injects the CSS that colors the page and the card, row and pill classes used below.

    Args:
        colors: The active theme.
    """
    fonts = "'Archivo', 'Segoe UI', Calibri, system-ui, sans-serif"
    st.markdown(
        f"""<style>
.stApp, [data-testid="stHeader"] {{ background: {colors.window}; color: {colors.text}; }}
[data-testid="stSidebar"] {{ background: {colors.surface}; border-right: 1px solid {colors.border}; }}
html, body, .stApp, .stApp p, .stApp label {{ font-family: {fonts}; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important; }}
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp span {{ color: {colors.text}; }}
.stApp [data-testid="stCaptionContainer"], .stApp small {{ color: {colors.muted}; }}
.tdh-title {{ font-size: 40px; font-weight: 900; line-height: 1.1; margin: 8px 0 0 0; }}
.tdh-sub {{ color: {colors.muted}; font-size: 15px; margin: 2px 0 14px 0; }}
.tdh-section {{ color: {colors.muted}; font-weight: bold; font-size: 15px; margin: 18px 0 6px 0; }}
.tdh-mono {{ font-family: Consolas, 'Courier New', monospace; font-size: 12px; color: {colors.muted}; }}
.tdh-card {{ background: {colors.surface}; border: 1px solid {colors.border}; border-radius: 8px; padding: 16px 20px; }}
.tdh-banner {{ background: {colors.accent}; color: {colors.highlighted_text}; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 14px; font-size: 15px; }}
.tdh-banner b, .tdh-banner span {{ color: {colors.highlighted_text}; }}
.tdh-hero {{ display: flex; flex-wrap: wrap; gap: 8px 40px; padding: 20px 24px; }}
.tdh-hero-left {{ flex: 0 0 auto; }}
.tdh-hero-right {{ flex: 1 1 320px; min-width: 260px; }}
.tdh-location {{ font-size: 26px; font-weight: 800; }}
.tdh-bigtemp {{ font-size: 110px; font-weight: 900; color: {colors.accent}; line-height: 1.05; }}
.tdh-bigtemp small {{ font-size: 36px; color: {colors.hot}; }}
.tdh-kicker {{ font-family: Consolas, monospace; font-size: 11px; color: {colors.muted}; }}
.tdh-quip {{ font-size: 38px; font-weight: 800; line-height: 1.15; margin: 4px 0 14px 0; }}
.tdh-stats {{ display: flex; flex-wrap: wrap; gap: 8px 28px; margin-bottom: 10px; }}
.tdh-stat span {{ display: block; }}
.tdh-stat .cap {{ color: {colors.muted}; font-size: 11px; text-transform: uppercase; }}
.tdh-stat .val {{ font-size: 19px; }}
.tdh-days {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; }}
.tdh-day {{ background: {colors.surface}; border: 1px solid {colors.border}; border-radius: 8px; padding: 10px 12px; }}
.tdh-day .d {{ color: {colors.muted}; font-weight: bold; }}
.tdh-day .hi {{ font-size: 22px; font-weight: bold; color: {colors.hot}; }}
.tdh-day .lo {{ color: {colors.cool}; }}
.tdh-day .pr {{ font-size: 13px; color: {colors.precip}; }}
.tdh-hour {{ display: grid; grid-template-columns: 56px 1fr 52px 96px 48px; gap: 14px; align-items: center;
    padding: 3px 8px; border-radius: 6px; }}
.tdh-hour.now {{ background: {colors.surface}; }}
.tdh-bar {{ position: relative; height: 18px; }}
.tdh-bar .fill {{ position: absolute; top: 3px; height: 12px; border-radius: 5px; min-width: 6px; }}
.tdh-bar .feels {{ position: absolute; top: 0; height: 18px; width: 2px; background: {colors.text}; opacity: .4; }}
.tdh-hour .t {{ text-align: right; font-weight: bold; font-size: 16px; }}
.tdh-hour .f {{ color: {colors.muted}; }}
.tdh-hour .p {{ text-align: right; font-size: 13px; color: {colors.precip}; }}
.tdh-row {{ display: grid; grid-template-columns: 84px 140px 1fr 140px; gap: 18px; align-items: center;
    padding: 10px 0; border-top: 1px solid {colors.border}; }}
.tdh-row .dn {{ font-size: 18px; font-weight: 800; }}
.tdh-row .dh {{ font-size: 38px; font-weight: 900; }}
.tdh-row .dl {{ font-size: 17px; color: {colors.cool}; margin-left: 6px; }}
.tdh-row .right {{ text-align: right; font-size: 13px; }}
.tdh-row .right .p {{ color: {colors.precip}; display: block; }}
.tdh-pill {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
.tdh-alert {{ margin-bottom: 10px; }}
.tdh-alert h3 {{ display: inline; margin-left: 10px; font-size: 18px; }}
.tdh-alert .quip {{ color: {colors.accent}; font-weight: bold; }}
.tdh-place {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 0;
    border-top: 1px solid {colors.border}; }}
@media (max-width: 700px) {{
  .tdh-bigtemp {{ font-size: 80px; }} .tdh-quip {{ font-size: 28px; }} .tdh-title {{ font-size: 30px; }}
  .tdh-row {{ grid-template-columns: 70px 100px 1fr; }} .tdh-row .right {{ display: none; }}
  .tdh-hour {{ grid-template-columns: 48px 1fr 44px 44px; }} .tdh-hour .f {{ display: none; }}
}}
</style>""",
        unsafe_allow_html=True,
    )


def page_head(title: str, subtitle: str = "") -> None:
    """Draws a page's big title and the muted line under it."""
    html(f"<div class='tdh-title'>{escape(title)}</div><div class='tdh-sub'>{escape(subtitle)}</div>")


# ===== SIDEBAR =====
def sidebar() -> tuple[dict, bool, int]:
    """Draws the sidebar and returns the user's choices.

    Returns:
        ``(location, use_celsius, heat_threshold_f)``. The location is kept in ``st.session_state`` for this
        visitor only; it is never written to config.json, so one visitor can't change another's place.
    """
    if "location" not in st.session_state:
        st.session_state["location"] = load_location()

    with st.sidebar:
        st.image(str(HERE / "assets" / "logo.jpg"))
        st.caption("The weather app with a personality disorder.")

        st.markdown("**Location**")
        st.write(st.session_state["location"]["location_name"])
        with st.form("place_search", clear_on_submit=False, border=False):
            query = st.text_input("City or postal code", placeholder="Hickory", label_visibility="collapsed")
            searched = st.form_submit_button("Search")
        if searched and query.strip():
            try:
                st.session_state["matches"] = geocode(query.strip(), limit=5) or []
                st.session_state["no_match"] = not st.session_state["matches"]
            except requests.RequestException:
                st.session_state["matches"] = []
                st.session_state["no_match"] = False
                st.error("Couldn't reach the location search. Try again in a minute.")
        if st.session_state.get("no_match"):
            st.warning("No places found.")
        matches = st.session_state.get("matches") or []
        if matches:
            names = [format_match(m) for m in matches]
            choice = st.selectbox("Which one?", names)
            if st.button("Use this place", type="primary"):
                picked = match_to_location(matches[names.index(choice)])
                st.session_state["location"] = {**load_location(), **picked}
                st.session_state["matches"] = []
                st.rerun()

        st.markdown("**Settings**")
        use_celsius = st.radio("Units", ["Fahrenheit", "Celsius"], horizontal=True) == "Celsius"
        st.selectbox("Theme", list(theme.THEMES), key="theme_select")
        heat_f = st.number_input("Heat alert at (feels-like °F)", min_value=80, max_value=130, value=105, step=1)

        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()
        st.caption(
            f"Forecast: Open-Meteo · Alerts: National Weather Service · [GitHub]({GITHUB_URL}) · "
            "Updates once an hour."
        )
    return st.session_state["location"], use_celsius, int(heat_f)


@st.cache_data(ttl=3600, max_entries=60, show_spinner=False)
def chart_png(name, lat, lon, tz, mode, celsius, theme_name) -> bytes:
    """Renders a chart once per place/mode/units/theme and shares the PNG with everyone."""
    raw = cached_fetch(name, lat, lon, tz)
    with _plot_lock:
        theme.set_theme(theme_name)
        if mode == "Hourly":
            fig = make_hourly_graphs(raw["hourly_df"], celsius=celsius)
        else:
            fig = make_daily_graphs(raw["daily_df"].head(7), celsius=celsius)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110)
        png = buf.getvalue()
    del fig
    gc.collect()
    return png


def active_theme() -> theme.Theme:
    return theme.THEMES[st.session_state.get("theme_select", theme.DEFAULT_THEME)]


# ===== PAGES =====
def peak_feels(hours: list[dict]) -> float | None:
    """Today's highest feels-like temperature in °F, or None if there are no hours."""
    return max((h["feels_f"] for h in hours), default=None)


def alert_banner(view: dict, celsius: bool, heat_f: int) -> None:
    """Shows the banner for the most severe NWS alert, or for the user's heat threshold when NWS has nothing."""
    alerts, peak = view["alerts"], peak_feels(view["hours"])
    if alerts:
        first = alerts[0]
        more = f" · +{len(alerts) - 1} more" if len(alerts) > 1 else ""
        until = f"Until {first['ends']}" if first["ends"] else "In effect"
        title, detail = first["event"], f"{until}{more}. See the Alerts page for details."
    elif peak is not None and peak >= heat_f:
        title = "Heat index alert"
        detail = f"Feels like up to {fmt_temp(peak, celsius)} today (your limit is {fmt_temp(heat_f, celsius)})"
    else:
        return
    html(f"<div class='tdh-banner'><b>{escape(title)}</b> <span>· {escape(detail)}</span></div>")


def page_now(view: dict, celsius: bool, heat_f: int) -> None:
    """The Now page: hero card, 7-day cards and the chart."""
    cur, colors = view["current"], active_theme()
    alert_banner(view, celsius, heat_f)

    unit = "°C" if celsius else "°F"
    number = f"{(fmt_deg(cur['temp_f'], celsius))[:-1]}"
    html(f"""
        <div class='tdh-card tdh-hero'>
          <div class='tdh-hero-left'>
            <div class='tdh-location'>{escape(cur['location'])}</div>
            <div class='tdh-sub'>{escape(cur['date'])} · updated {escape(cur['updated'])}</div>
            <div class='tdh-bigtemp'>{number}<small>{unit}</small></div>
            <div>{escape(cur['condition'])} · Feels like
              <b style='color:{colors.hot}'>{fmt_deg(cur['feels_f'], celsius)}</b></div>
            <div class='tdh-sub'>H <span style='color:{colors.hot}'>{fmt_deg(cur['high_f'], celsius)}</span> ·
              L <span style='color:{colors.cool}'>{fmt_deg(cur['low_f'], celsius)}</span></div>
          </div>
          <div class='tdh-hero-right'>
            <div class='tdh-kicker'>{escape(bucket_kicker(cur['temp_f']))}</div>
            <div class='tdh-quip'>{escape(cur['quip'])}</div>
            <div class='tdh-stats'>
              <div class='tdh-stat'><span class='cap'>Humidity</span>
                <span class='val'>{cur['humidity']:.0f}%</span></div>
              <div class='tdh-stat'><span class='cap'>Wind</span>
                <span class='val'>{fmt_wind(cur['wind_mph'], cur['wind_dir'], celsius)}</span></div>
              <div class='tdh-stat'><span class='cap'>UV index</span>
                <span class='val'>{cur['uv']:.0f} · {uv_label(cur['uv'])}</span></div>
              <div class='tdh-stat'><span class='cap'>Precip</span>
                <span class='val'>{cur['precip_chance']}%</span></div>
            </div>
            <span style='color:{colors.sunrise};font-size:15px'>● Sunrise {cur['sunrise']}</span>
            &nbsp;&nbsp;&nbsp;
            <span style='color:{colors.sunset};font-size:15px'>● Sunset {cur['sunset']}</span>
          </div>
        </div>
    """)

    html("<div class='tdh-section'>Next 7 days</div>")
    cards = "".join(
        f"<div class='tdh-day'><div class='d'>{escape(day['day'])}</div>"
        f"<div class='hi'>{fmt_deg(day['high_f'], celsius)}</div>"
        f"<div class='lo'>{fmt_deg(day['low_f'], celsius)}</div>"
        f"<div class='pr'>{day['precip_chance']}% · {fmt_precip(day['precip_in'], celsius)}</div></div>"
        for day in view["days"][:7]
    )
    html(f"<div class='tdh-days'>{cards}</div>")

    html("<div class='tdh-section'>Graph</div>")
    mode = st.radio("Graph", ["Daily", "Hourly"], horizontal=True, label_visibility="collapsed")
    loc = st.session_state["location"]
    png = chart_png(loc["location_name"], loc["latitude"], loc["longitude"], loc["timezone"],
                    mode, celsius, st.session_state["theme_select"])
    st.image(png, width="stretch")


def page_hourly(view: dict, celsius: bool) -> None:
    """The Hourly page: one heat-bar row per hour of today."""
    hours = view["hours"]
    summary = ""
    if hours:
        hottest = max(hours, key=lambda h: h["temp_f"])
        wettest = max(hours, key=lambda h: h["precip_chance"])
        summary = f"Peaks at {fmt_deg(hottest['temp_f'], celsius)} around {fmt_hour(hottest['stamp'])}."
        if wettest["precip_chance"] > 0:
            summary += f" Rain chance tops out at {wettest['precip_chance']}% near {fmt_hour(wettest['stamp'])}."
        else:
            summary += " No rain in sight. Not even a little."
    page_head("Hour by hour.", summary or "The bar is the temperature. The faint line is feels-like. Both are bad.")

    rows = []
    for hour in hours:
        fill = theme.heat_color(hour["temp_f"])
        rows.append(
            f"<div class='tdh-hour{' now' if hour['is_now'] else ''}'>"
            f"<span class='tdh-mono'>{fmt_hour(hour['stamp'])}</span>"
            f"<div class='tdh-bar'><div class='fill' style='width:{_fraction(hour['temp_f']) * 100:.1f}%;"
            f"background:{fill}'></div>"
            f"<div class='feels' style='left:{_fraction(hour['feels_f']) * 100:.1f}%'></div></div>"
            f"<span class='t'>{fmt_deg(hour['temp_f'], celsius)}</span>"
            f"<span class='f'>feels {fmt_deg(hour['feels_f'], celsius)}</span>"
            f"<span class='p'>{hour['precip_chance']}%</span></div>"
        )
    html("".join(rows))


def page_ten_day(view: dict, celsius: bool) -> None:
    """The 10-Day page: one row per day with a big high, the low and a quip."""
    days = view["days"]
    too_hot = sum(day["high_f"] >= 95 for day in days)
    page_head(
        "Ten days of this.",
        f"{too_hot} of {len(days)} days are in the too hot. Congratulations."
        if too_hot
        else "Not one day above 95 degrees. Suspicious.",
    )
    rows = "".join(
        f"<div class='tdh-row'>"
        f"<div><div class='dn'>{escape(day['day'])}</div><div class='tdh-mono'>{day['date']}</div></div>"
        f"<div><span class='dh' style='color:{theme.heat_color(day['high_f'])}'>"
        f"{fmt_deg(day['high_f'], celsius)}</span><span class='dl'>{fmt_deg(day['low_f'], celsius)}</span></div>"
        f"<div>{escape(day['quip'])}</div>"
        f"<div class='right'>{escape(day['condition'])}<span class='p'>{day['precip_chance']}% precip</span></div>"
        f"</div>"
        for day in days
    )
    html(rows)


def page_alerts(view: dict, celsius: bool, heat_f: int) -> None:
    """The Alerts page: NWS alert cards (or an all-clear), heat tips and the visitor's own threshold."""
    cur, alerts, colors = view["current"], view["alerts"], active_theme()
    count = len(alerts)
    page_head(
        "Alerts",
        f"{count} active for {cur['location']}" if count else f"Nothing active for {cur['location']}",
    )
    for alert in alerts:
        pill_color = getattr(colors, SEVERITY_COLORS.get(alert["severity"], "muted"))
        until = f" · until {escape(alert['ends'])}" if alert["ends"] else ""
        description = f"<p>{escape(alert['description'])}</p>" if alert["description"] else ""
        instruction = (
            f"<p style='color:{colors.muted}'>{escape(alert['instruction'])}</p>" if alert["instruction"] else ""
        )
        quip = escape(get_quip(cur["temp_f"], cur["condition"]))
        html(f"""
            <div class='tdh-card tdh-alert'>
              <span class='tdh-pill' style='background:{pill_color};color:{colors.highlighted_text}'>
                {escape(alert['severity'].upper())}</span>
              <h3>{escape(alert['event'])}</h3>
              <div class='tdh-sub'>{escape(alert['sender'])}{until}</div>
              {description}{instruction}
              <div class='quip'>“{quip}”</div>
            </div>
        """)
    if not count:
        html("<div class='tdh-sub'>No alerts. The atmosphere has temporarily suspended hostilities.</div>")

    peak = peak_feels(view["hours"])
    if count or (peak is not None and peak >= heat_f):
        html("<div class='tdh-section'>Don't die out there</div>")
        st.markdown("\n".join(f"- {tip}" for tip in HEAT_TIPS))
    st.caption(f"Your own heat alert: feels-like ≥ {fmt_temp(heat_f, celsius)}. Change it in the sidebar.")


def page_radar(view: dict) -> None:
    """The Radar page: the same Leaflet loop the desktop app shows, in an iframe."""
    cur = view["current"]
    page_head("Radar", "Radar loop, no API key needed. US: NEXRAD via Iowa Mesonet. Elsewhere: RainViewer.")
    st.iframe(radar_html(cur["latitude"], cur["longitude"], active_theme()), height=620)



# ===== MAIN =====
def main() -> None:
    """Draws the sidebar, loads the data for the chosen place and draws the chosen page."""
    location, celsius, heat_f = sidebar()
    apply_page_style(active_theme())

    page = st.radio("Page", PAGES, horizontal=True, label_visibility="collapsed")

    try:
        raw = cached_fetch(
            location["location_name"], location["latitude"], location["longitude"], location["timezone"]
        )
    except Exception as err:  # noqa: BLE001 - show the problem instead of a stack trace
        st.error(f"Couldn't load weather data: {err}")
        st.stop()
    view = build_view(location, raw)

    if page == "Now":
        page_now(view, celsius, heat_f)
    elif page == "Hourly":
        page_hourly(view, celsius)
    elif page == "10-Day":
        page_ten_day(view, celsius)
    elif page == "Alerts":
        page_alerts(view, celsius, heat_f)
    else:
        page_radar(view)


main()
