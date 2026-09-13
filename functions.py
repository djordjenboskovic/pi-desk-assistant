"""
Function-calling tools exposed to GPT.

Time (anywhere in the world), weather (anywhere, or local by default), and
alarms.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import subprocess

import requests

# Single source of truth for the speaker's PipeWire sink name -- every other
# file that needs it imports it from here, so swapping speakers is a
# one-line change instead of a four-file hunt. Update this when you swap
# hardware (find the real value with: pactl list short sinks)
SPEAKER_SINK = "alsa_output.usb-Jieli_Technology_USB_Composite_Device_1597819991056D53-01.analog-stereo"

_location_cache = None  # (lat, lon, display_name, timezone) -- cached after first lookup


def _get_local_info():
    """Auto-detects the current location via free IP geolocation -- no
    manual coordinates to maintain, and it stays correct even if the Pi
    ever moves somewhere new. Cached for the life of the process, since
    the location isn't expected to change mid-session; restart the
    assistant if you actually do move it somewhere else."""
    global _location_cache
    if _location_cache is not None:
        return _location_cache

    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        data = resp.json()
        display = f"{data['city']}, {data['regionName']}"
        _location_cache = (data["lat"], data["lon"], display, data["timezone"])
    except Exception:
        # Fallback if the lookup fails (e.g. no internet yet at startup) --
        # update this to your actual area as a safety net.
        _location_cache = (40.0946, -75.3634, "King of Prussia, PA", "America/New_York")

    return _location_cache

FUNCTION_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "Get the current time. If the user asks for the time "
                "somewhere specific (a city, country, or region), pass that "
                "place's IANA timezone name. If they just ask what time it "
                "is with no location mentioned, leave timezone empty to get "
                "local time where this assistant is physically running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "IANA timezone name, e.g. 'Asia/Tokyo', "
                            "'Europe/Belgrade', 'America/New_York'. Leave "
                            "empty (or omit) for local time."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get the current weather for a place. If the user asks "
                "about weather somewhere specific (a city, country, or "
                "region), pass that place's name. If they just ask about "
                "the weather with no location mentioned, leave location "
                "empty to get weather where this assistant is physically located."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "A place name, e.g. 'Tokyo', 'Belgrade, Serbia', "
                            "'Paris, France'. Leave empty (or omit) for the "
                            "local weather here."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": (
                "Get a multi-day weather forecast (highs/lows, chance of "
                "rain or snow) for a place, looking a few days ahead. Use "
                "this instead of get_weather when the user asks about "
                "future days, not the current conditions right now. If no "
                "location is mentioned, leave location empty for the local forecast."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "A place name, e.g. 'Tokyo', 'Belgrade, Serbia'. "
                            "Leave empty (or omit) for the local forecast here."
                        ),
                    },
                    "days": {
                        "type": "integer",
                        "description": "How many days ahead to look, 1-7. Defaults to 3 if not specified.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": (
                "Set an alarm. Provide either an absolute time or how many "
                "minutes from now, not both."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "time_str": {
                        "type": "string",
                        "description": "24-hour time like '07:30'. Omit if using minutes_from_now instead.",
                    },
                    "minutes_from_now": {
                        "type": "integer",
                        "description": "e.g. 2 for 'in 2 minutes'. Omit if using time_str instead.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_alarm",
            "description": "Cancel the next upcoming alarm (one that hasn't gone off yet).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alarms",
            "description": "List all currently set alarms.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_volume",
            "description": (
                "Get the current speaker volume as a percentage, 0-100. Call "
                "this before making a relative change (e.g. 'turn it up a "
                "bit', 'make it a little quieter') so you know the starting point."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the speaker volume as a percentage, 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "percent": {"type": "integer", "description": "Volume level, 0-100."},
                },
                "required": ["percent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_brightness",
            "description": (
                "Get the current touchscreen brightness as a percentage, "
                "0-100. Call this before making a relative change (e.g. "
                "'make it a bit dimmer', 'brighten it slightly') so you "
                "know the starting point."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set the touchscreen brightness as a percentage, 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "percent": {"type": "integer", "description": "Brightness level, 0-100."},
                },
                "required": ["percent"],
            },
        },
    },
]


def get_current_time(timezone: str = "") -> str:
    try:
        if timezone:
            now = datetime.now(ZoneInfo(timezone))
            return now.strftime(f"%I:%M %p on %A, %B %d -- {timezone}")
        _, _, display, local_tz = _get_local_info()
        now = datetime.now(ZoneInfo(local_tz))
        return now.strftime(f"%I:%M %p on %A, %B %d -- {display}")
    except Exception:
        return (
            f"I don't recognize the timezone '{timezone}'. "
            "Try a major city or region name instead."
        )


_alarms = []  # sorted list of datetime objects


def set_alarm(time_str: str = "", minutes_from_now: int = None) -> str:
    now = datetime.now()

    if minutes_from_now is not None:
        target = now + timedelta(minutes=minutes_from_now)
    elif time_str:
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception:
            return f"I couldn't understand the time '{time_str}'. Use 24-hour format like 07:30."
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
    else:
        return "I need either a specific time or how many minutes from now."

    _alarms.append(target)
    _alarms.sort()
    day_note = "" if target.date() == now.date() else " tomorrow"
    return f"Alarm set for {target.strftime('%I:%M %p')}{day_note}."


def cancel_alarm() -> str:
    if not _alarms:
        return "You don't have any alarms set."
    removed = _alarms.pop(0)
    return f"Cancelled your alarm for {removed.strftime('%I:%M %p')}."


def list_alarms() -> str:
    if not _alarms:
        return "You don't have any alarms set."
    times = ", ".join(a.strftime("%I:%M %p") for a in _alarms)
    return f"Your alarms: {times}"


def pop_due_alarm():
    """Called from the main loop -- returns and removes the next alarm if
    it's due, or None if nothing's due yet."""
    if _alarms and _alarms[0] <= datetime.now():
        return _alarms.pop(0)
    return None


def snooze(minutes: int = 5) -> str:
    """Not a GPT-callable tool -- snoozing only makes sense while an alarm
    is actively ringing, which is handled directly by wake_loop.py's
    keyword check, not through a normal conversational tool call."""
    _alarms.append(datetime.now() + timedelta(minutes=minutes))
    _alarms.sort()
    return f"Snoozed for {minutes} minutes."


_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with rime",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "light rain", 63: "moderate rain", 65: "heavy rain",
    71: "light snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with heavy hail",
}


def _geocode(location: str):
    """Turns a place name into (lat, lon, display_name) using Open-Meteo's
    free geocoding lookup -- same no-API-key service as the weather API."""
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1},
        timeout=5,
    )
    results = resp.json().get("results")
    if not results:
        return None
    r = results[0]
    display = r["name"]
    if r.get("admin1"):
        display += f", {r['admin1']}"
    if r.get("country"):
        display += f", {r['country']}"
    return r["latitude"], r["longitude"], display


def get_weather(location: str = "") -> str:
    if location:
        geocoded = _geocode(location)
        if geocoded is None:
            return f"I couldn't find a place called '{location}'."
        lat, lon, display = geocoded
    else:
        lat, lon, display, _ = _get_local_info()

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code",
                "temperature_unit": "fahrenheit",
            },
            timeout=5,
        )
        current = resp.json()["current"]
        temp = current["temperature_2m"]
        condition = _WEATHER_CODES.get(current["weather_code"], "unknown conditions")
        return f"{temp}°F and {condition} in {display}"
    except Exception:
        return f"I couldn't get the weather for {display} right now."


def get_forecast(location: str = "", days: int = 3) -> str:
    if location:
        geocoded = _geocode(location)
        if geocoded is None:
            return f"I couldn't find a place called '{location}'."
        lat, lon, display = geocoded
    else:
        lat, lon, display, _ = _get_local_info()

    days = max(1, min(days, 7))

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=5,
        )
        daily = resp.json()["daily"]
        lines = []
        for i in range(len(daily["time"])):
            date = daily["time"][i]
            hi = daily["temperature_2m_max"][i]
            lo = daily["temperature_2m_min"][i]
            condition = _WEATHER_CODES.get(daily["weather_code"][i], "unknown conditions")
            rain_chance = daily["precipitation_probability_max"][i]
            lines.append(f"{date}: {condition}, high {hi}°F / low {lo}°F, {rain_chance}% chance of precipitation")
        return f"Forecast for {display}: " + "; ".join(lines)
    except Exception:
        return f"I couldn't get the forecast for {display} right now."


BACKLIGHT_PATH = "/sys/class/backlight/11-0045/brightness"
BACKLIGHT_MAX = 255
BACKLIGHT_MIN = 25  # floor (~10%) -- slider's lowest position stays dim but visible, never fully off


def set_volume(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    subprocess.run(["pactl", "set-sink-volume", SPEAKER_SINK, f"{percent}%"])
    return f"Volume set to {percent}%."


def get_volume() -> int:
    try:
        result = subprocess.run(
            ["pactl", "get-sink-volume", SPEAKER_SINK],
            capture_output=True, text=True,
        )
        import re
        match = re.search(r"(\d+)%", result.stdout)
        return int(match.group(1)) if match else 50
    except Exception:
        return 50


def set_brightness(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    value = round(BACKLIGHT_MIN + (percent / 100) * (BACKLIGHT_MAX - BACKLIGHT_MIN))
    with open(BACKLIGHT_PATH, "w") as f:
        f.write(str(value))
    return f"Brightness set to {percent}%."


def get_brightness() -> int:
    try:
        with open(BACKLIGHT_PATH) as f:
            value = int(f.read().strip())
        percent = round((value - BACKLIGHT_MIN) / (BACKLIGHT_MAX - BACKLIGHT_MIN) * 100)
        return max(0, min(100, percent))
    except Exception:
        return 100


_DISPATCH = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
    "get_forecast": get_forecast,
    "set_alarm": set_alarm,
    "cancel_alarm": cancel_alarm,
    "list_alarms": list_alarms,
    "get_volume": get_volume,
    "set_volume": set_volume,
    "get_brightness": get_brightness,
    "set_brightness": set_brightness,
}


def call_function(name, args):
    return _DISPATCH[name](**args)
