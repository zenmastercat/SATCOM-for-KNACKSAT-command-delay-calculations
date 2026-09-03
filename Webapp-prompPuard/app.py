from datetime import datetime, timedelta
import math
from flask import Flask, jsonify, request
from flask_cors import CORS
import pytz
from skyfield.api import EarthSatellite, load, wgs84

app = Flask(__name__)
CORS(app)

ts = load.timescale()

DEFAULT_SAT_NAME = "KNACKSAT-2"
DEFAULT_TLE_LINE1 = (
    "1 67683U 98067XZ  26243.45609269  .00053825  00000-0  49349-3 0  9993"
)
DEFAULT_TLE_LINE2 = (
    "2 67683  51.6250 273.9102 0007537 104.1040 256.0794 15.67179025 32053"
)

LOCAL_TZ = pytz.timezone("Asia/Bangkok")
SEARCH_DAYS = 30
MIN_SAT_ELEVATION_DEG = 70.0
SUN_ELEVATION_MIN_DEG = 20.0
SUN_ELEVATION_MAX_DEG = 90.0
MIN_GS_ELEVATION_DEG = 20.0
SPEED_OF_LIGHT_KM_S = 299792.458
EARTH_RADIUS_KM = 6371.0

# KNACKSAT-2 ASEANSAT High Ground Resolution Camera Payload FOV
CAMERA_FOV_DEG = 6.0


def time_to_datetime(t):
    dt = t.utc_datetime()
    return dt[0] if isinstance(dt, list) else dt


def extract_time_list(times, events):
    if len(events) == 0:
        return [], []
    if not hasattr(times, "shape") or times.shape == ():
        return [times], list(events)
    return [times[i] for i in range(len(events))], list(events)


def generate_orbit_path(satellite, start_dt, end_dt, step_seconds=30):
    path = []
    curr = start_dt
    while curr <= end_dt:
        t = ts.from_datetime(curr)
        geocentric = satellite.at(t)
        subpoint = wgs84.subpoint_of(geocentric)
        path.append([
            round(float(subpoint.latitude.degrees), 4),
            round(float(subpoint.longitude.degrees), 4),
        ])
        curr += timedelta(seconds=step_seconds)
    return path


def find_photo_windows(satellite, target_loc):
    eph = load("de421.bsp")
    sun, earth = eph["sun"], eph["earth"]

    t0 = ts.now()
    t1 = ts.from_datetime(time_to_datetime(t0) + timedelta(days=SEARCH_DAYS))

    times, events = satellite.find_events(
        target_loc, t0, t1, altitude_degrees=MIN_SAT_ELEVATION_DEG
    )
    time_list, event_list = extract_time_list(times, events)

    candidates = []
    for t, event in zip(time_list, event_list):
        if event != 1:
            continue

        observer = earth + target_loc
        alt, az, distance = observer.at(t).observe(sun).apparent().altaz()
        sun_elev = float(alt.degrees)

        if SUN_ELEVATION_MIN_DEG <= sun_elev <= SUN_ELEVATION_MAX_DEG:
            candidates.append((t, sun_elev))

    return candidates


def find_last_uplink_before(satellite, before_time, ground_station):
    before_dt = time_to_datetime(before_time)
    search_start = ts.from_datetime(before_dt - timedelta(days=SEARCH_DAYS))

    times, events = satellite.find_events(
        ground_station,
        search_start,
        before_time,
        altitude_degrees=MIN_GS_ELEVATION_DEG,
    )
    time_list, event_list = extract_time_list(times, events)
    culminations = [t for t, event in zip(time_list, event_list) if event == 1]
    return culminations[-1] if culminations else None


def find_next_uplink_after(satellite, after_time, ground_station):
    after_dt = time_to_datetime(after_time)
    search_end = ts.from_datetime(after_dt + timedelta(days=SEARCH_DAYS))

    times, events = satellite.find_events(
        ground_station,
        after_time,
        search_end,
        altitude_degrees=MIN_GS_ELEVATION_DEG,
    )
    time_list, event_list = extract_time_list(times, events)
    culminations = [t for t, event in zip(time_list, event_list) if event == 1]
    return culminations[0] if culminations else None


def signal_delay_seconds(satellite, location, t):
    difference = satellite - location
    topocentric = difference.at(t)
    distance_km = float(topocentric.distance().km)
    return distance_km / SPEED_OF_LIGHT_KM_S


def format_countdown(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "Expired"
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"


@app.route("/api/realtime-telemetry", methods=["GET", "POST"])
def realtime_telemetry():
    data = request.json or {} if request.method == "POST" else request.args

    norad_id = str(data.get("norad_id", "67683"))
    sat_name = str(data.get("satellite_name", DEFAULT_SAT_NAME))

    t_lat = float(data.get("target_lat", 48.8566))
    t_lon = float(data.get("target_lon", 2.3522))
    u_lat = float(data.get("uplink_lat", 13.7563))
    u_lon = float(data.get("uplink_lon", 100.5018))

    target_loc = wgs84.latlon(t_lat, t_lon)
    ground_station_loc = wgs84.latlon(u_lat, u_lon)

    satellite = EarthSatellite(
        DEFAULT_TLE_LINE1, DEFAULT_TLE_LINE2, sat_name, ts
    )

    now_ts = ts.now()
    now_utc = time_to_datetime(now_ts)
    now_bkk = now_utc.astimezone(LOCAL_TZ)

    geocentric = satellite.at(now_ts)
    subpoint = wgs84.subpoint_of(geocentric)
    sat_alt_km = float(subpoint.elevation.km)

    gamma = math.acos(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + sat_alt_km))
    rf_footprint_radius_m = round(EARTH_RADIUS_KM * gamma * 1000)

    half_fov_rad = math.radians(CAMERA_FOV_DEG / 2.0)
    camera_swath_radius_m = round(sat_alt_km * math.tan(half_fov_rad) * 1000)

    past_orbit_path = generate_orbit_path(
        satellite, now_utc - timedelta(minutes=45), now_utc, step_seconds=30
    )
    future_orbit_path = generate_orbit_path(
        satellite, now_utc, now_utc + timedelta(minutes=90), step_seconds=30
    )

    candidates = find_photo_windows(satellite, target_loc)

    card_delay = "N/A"
    card_uplink = "No Pass Found"
    card_target = "No Pass Found"
    card_transit = "N/A"
    card_return = "No Pass Found"
    card_sun = "N/A"
    target_pass_path = []

    if len(candidates) > 0:
        next_photo_time, next_sun_elev = candidates[0]
        photo_utc = time_to_datetime(next_photo_time)
        photo_bkk = photo_utc.astimezone(LOCAL_TZ)

        card_target = photo_bkk.strftime("%Y-%m-%d %H:%M:%S")
        card_sun = f"{next_sun_elev:.1f}°"

        # Expanded to a FULL ORBIT REVOLUTION (~96 min pass) around peak imaging time
        target_pass_path = generate_orbit_path(
            satellite,
            photo_utc - timedelta(minutes=48),
            photo_utc + timedelta(minutes=48),
            step_seconds=20,
        )

        uplink_time = find_last_uplink_before(
            satellite, next_photo_time, ground_station_loc
        )

        if uplink_time is not None:
            uplink_utc = time_to_datetime(uplink_time)
            uplink_bkk = uplink_utc.astimezone(LOCAL_TZ)
            card_uplink = uplink_bkk.strftime("%Y-%m-%d %H:%M:%S")

            delay_s = signal_delay_seconds(
                satellite, ground_station_loc, uplink_time
            )
            card_delay = f"{delay_s * 1000.0:.2f} ms"
            card_transit = format_countdown(photo_utc - uplink_utc)

        return_time = find_next_uplink_after(
            satellite, next_photo_time, ground_station_loc
        )

        if return_time is not None:
            return_utc = time_to_datetime(return_time)
            return_bkk = return_utc.astimezone(LOCAL_TZ)
            card_return = return_bkk.strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({
        "timestamp_bkk": now_bkk.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "satellite": {"norad_id": norad_id, "name": sat_name},
        "current_sat_position": {
            "lat": round(float(subpoint.latitude.degrees), 4),
            "lon": round(float(subpoint.longitude.degrees), 4),
            "alt_km": round(sat_alt_km, 2),
            "rf_footprint_radius_m": rf_footprint_radius_m,
            "camera_swath_radius_m": camera_swath_radius_m,
            "camera_fov_deg": CAMERA_FOV_DEG,
        },
        "telemetry": {
            "command_delay": card_delay,
            "next_uplink_pass": card_uplink,
            "next_target_pass": card_target,
            "transit_duration": card_transit,
            "return_to_uplink": card_return,
            "sun_elevation": card_sun,
        },
        "orbit_paths": {
            "past_orbit": past_orbit_path,
            "future_orbit": future_orbit_path,
            "target_pass_orbit": target_pass_path,
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)