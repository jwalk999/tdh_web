"""
File Name: weather_data.py

Author: Jonathan W (web port written with Claude)
Date Created: 11/19/2026
Last Update: 11/19/2026
Version: 1.0.0

Scope: Qt-free data layer for the web app. fetch_raw() makes the network calls (cached by the app), and
    build_view() turns the raw frames into the current/days/hours dicts the pages draw. The formatting helpers
    are the ones from main.py, with the Celsius switch passed in instead of read from the window.
"""

import random
from datetime import datetime

import pandas as pd
import requests

from alerts import get_alerts
from Config.global_params import f_to_c, get_weather_description, load_descriptions
from Forecasts import get_forecast_and_current
from quips import HIGH_F, LOW_F, NORMAL_F, V_HIGH_F, get_quip

FORECAST_DAYS = 10


# ===== FORMATTING =====
def _num(value, default: float = 0.0) -> float:
    """Returns ``value`` as a float, or ``default`` if it's missing or NaN (Open-Meteo leaves gaps far out)."""
    return default if value is None or pd.isna(value) else float(value)


def compass(degrees: float) -> str:
    """Turns a wind direction in degrees into an 8-point compass label, e.g. 225 -> "SW"."""
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(degrees / 45) % 8]


def uv_label(uv: float) -> str:
    """Turns a UV index into the WHO category name."""
    for limit, name in ((3, "low"), (6, "moderate"), (8, "high"), (11, "very high")):
        if uv < limit:
            return name
    return "extreme"


def bucket_name(temp_f: float) -> str:
    """Names the quips.py temperature bucket a reading falls in."""
    for limit, name in ((V_HIGH_F, "Too damn hot"), (HIGH_F, "Hot"), (NORMAL_F, "Normal"), (LOW_F, "Chilly")):
        if temp_f >= limit:
            return name
    return "Freezing"


def bucket_kicker(temp_f: float) -> str:
    """The small caption above the quip headline, e.g. "TOO DAMN HOT BUCKET · 95°F+"."""
    for limit, name in ((V_HIGH_F, "TOO DAMN HOT"), (HIGH_F, "HOT"), (NORMAL_F, "NORMAL"), (LOW_F, "CHILLY")):
        if temp_f >= limit:
            return f"{name} BUCKET · {limit}°F+"
    return f"FREEZING BUCKET · UNDER {LOW_F}°F"


def fmt_hour(stamp: pd.Timestamp) -> str:
    """Formats a timestamp as a short hour, e.g. "2 PM"."""
    return stamp.strftime("%I %p").lstrip("0")


def fmt_temp(temp_f: float, celsius: bool) -> str:
    """Formats a temperature with its unit, e.g. "99°F" or "37°C"."""
    return f"{f_to_c(temp_f):.0f}°C" if celsius else f"{temp_f:.0f}°F"


def fmt_deg(temp_f: float, celsius: bool) -> str:
    """Formats a temperature with just a degree sign, e.g. "99°"."""
    return f"{(f_to_c(temp_f) if celsius else temp_f):.0f}°"


def fmt_precip(precip_in: float, celsius: bool) -> str:
    """Formats a precipitation amount: whole millimetres for Celsius, inches to two decimals otherwise."""
    return f"{precip_in * 25.4:.0f} mm" if celsius else f"{precip_in:.2f} in"


def fmt_wind(mph: float, direction: str, celsius: bool) -> str:
    """Formats wind speed and direction, e.g. "SW 6 mph" or "SW 10 km/h"."""
    return f"{direction} {mph * 1.609:.0f} km/h" if celsius else f"{direction} {mph:.0f} mph"


# ===== DATA =====
def fetch_raw(location: dict) -> dict:
    """Fetches the forecast and alerts for a location. This is the part the app caches.

    Args:
        location: Dict with location_name, latitude, longitude and timezone keys.

    Returns:
        Dict with daily_df, hourly_df, now (current conditions), alerts and fetched_at keys.

    Raises:
        requests.exceptions.ConnectionError: If Open-Meteo cannot be reached.
    """
    daily_df, hourly_df, now = get_forecast_and_current(location, days=FORECAST_DAYS)
    # Alerts are a bonus; a failed NWS call shouldn't block the forecast
    try:
        alerts = get_alerts(location["latitude"], location["longitude"])
    except requests.RequestException:
        alerts = []
    return {
        "daily_df": daily_df,
        "hourly_df": hourly_df,
        "now": now,
        "alerts": alerts,
        "fetched_at": datetime.now().isoformat(timespec="minutes"),
    }


def build_view(location: dict, raw: dict) -> dict:
    """Turns the raw frames into the dicts the pages draw. Temperatures stay in °F.

    Quips are picked with a random seed taken from the location and fetch time, so they stay the same while
    the page reruns for a button click, and change when the data is refreshed.

    Args:
        location: Location dict used for the fetch.
        raw: Result of fetch_raw().

    Returns:
        Dict with current, days, hours, alerts, daily_df and hourly_df keys. ``current``, ``days`` and ``hours``
        have the same keys as the ones load_data() builds in main.py.
    """
    random.seed(f"{location['location_name']}|{raw['fetched_at']}")
    tz = location["timezone"]
    daily_df, hourly_df, now = raw["daily_df"], raw["hourly_df"], raw["now"]
    descriptions = load_descriptions()
    now_ts = pd.Timestamp.now(tz=tz)
    today = daily_df.iloc[0]

    past = hourly_df[hourly_df["Date"] <= now_ts]
    now_row = past.iloc[-1] if len(past) else hourly_df.iloc[0]

    temp_f = now["Temperature"]
    condition = get_weather_description(now["Weather Code"], descriptions, "day" if now["Is Day"] else "night")

    current = {
        "location": location["location_name"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "temp_f": temp_f,
        "feels_f": now["Feels Like"],
        "high_f": _num(today["Temperature High"], temp_f),
        "low_f": _num(today["Temperature Low"], temp_f),
        "humidity": now["Humidity"],
        "wind_mph": now["Wind Speed"],
        "wind_dir": compass(now["Wind Direction"]),
        "uv": now["UV Index"],
        "precip_chance": int(_num(now_row["Chance of Precipitation"])),
        "condition": condition,
        "sunrise": today["Sunrise"].strftime("%I:%M %p").lstrip("0"),
        "sunset": today["Sunset"].strftime("%I:%M %p").lstrip("0"),
        "quip": get_quip(temp_f, condition),
        "date": f"{now_ts:%A, %B} {now_ts.day}",
        "updated": now_ts.strftime("%I:%M %p").lstrip("0"),
    }

    days = []
    for i, row in enumerate(daily_df.to_dict("records")):
        high_f = _num(row["Temperature High"])
        day_condition = get_weather_description(_num(row["Weather Code"]), descriptions, "day")
        days.append({
            "day": "Today" if i == 0 else row["Date"].strftime("%a"),
            "date": f"{row['Date'].month}/{row['Date'].day}",
            "high_f": high_f,
            "low_f": _num(row["Temperature Low"]),
            "precip_chance": int(_num(row["Chance of Precipitation"])),
            "precip_in": _num(row["Precipitation"]),
            "condition": day_condition,
            "quip": get_quip(high_f, day_condition),
        })

    hours = [
        {
            "stamp": row["Date"],
            "temp_f": _num(row["Temperature"]),
            "feels_f": _num(row["Feels Like"]),
            "precip_chance": int(_num(row["Chance of Precipitation"])),
            "is_now": row["Date"].hour == now_ts.hour,
        }
        for row in hourly_df.to_dict("records")
    ]

    return {
        "current": current,
        "days": days,
        "hours": hours,
        "alerts": raw["alerts"],
        "daily_df": daily_df,
        "hourly_df": hourly_df,
    }
