from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import math
import requests

app = Flask(__name__)
CORS(app)

# --- WGS-84 Ellipsoid & Physical Constants ---
SPEED_OF_LIGHT = 299792458.0          # m/s
EARTH_ROTATION_RATE = 7.2921151467e-5 # rad/s
WGS84_A = 6378137.0                   # Semi-major axis in meters
WGS84_F = 1.0 / 298.257223563         # Flattening
WGS84_E2 = 2 * WGS84_F - WGS84_F**2   # First eccentricity squared

SATELLITE_DATABASE = [
    {"id": "25544", "name": "ISS (International Space Station)", "altitude_km": 408, "speed_kms": 7.66},
    {"id": "20580", "name": "HST (Hubble Space Telescope)", "altitude_km": 535, "speed_kms": 7.59},
    {"id": "25994", "name": "TERRA (EOS AM-1)", "altitude_km": 705, "speed_kms": 7.50},
    {"id": "27424", "name": "AQUA (EOS PM-1)", "altitude_km": 705, "speed_kms": 7.50},
    {"id": "33591", "name": "NOAA-19", "altitude_km": 850, "speed_kms": 7.40},
    {"id": "40069", "name": "KNACKSAT (CubeSat)", "altitude_km": 500, "speed_kms": 7.60},
    {"id": "43013", "name": "SENTINEL-2B", "altitude_km": 786, "speed_kms": 7.46},
    {"id": "49260", "name": "LANDSAT 9", "altitude_km": 705, "speed_kms": 7.50}
]

def geodetic_to_ecef(lat_deg, lon_deg, alt_meters=0.0):
    phi, lam = math.radians(lat_deg), math.radians(lon_deg)
    N = WGS84_A / math.sqrt(1.0 - WGS84_E2 * (math.sin(phi)**2))
    x = (N + alt_meters) * math.cos(phi) * math.cos(lam)
    y = (N + alt_meters) * math.cos(phi) * math.sin(lam)
    z = (N * (1.0 - WGS84_E2) + alt_meters) * math.sin(phi)
    return x, y, z

def sagnac_light_time_correction(p1_ecef, p2_ecef):
    dx, dy, dz = p2_ecef[0] - p1_ecef[0], p2_ecef[1] - p1_ecef[1], p2_ecef[2] - p1_ecef[2]
    raw_dist = math.sqrt(dx**2 + dy**2 + dz**2)
    sagnac_delta = (EARTH_ROTATION_RATE / SPEED_OF_LIGHT) * (p1_ecef[0] * p2_ecef[1] - p2_ecef[0] * p1_ecef[1])
    corrected_dist = raw_dist + sagnac_delta
    return corrected_dist, corrected_dist / SPEED_OF_LIGHT

def saastamoinen_tropospheric_delay(lat_deg, lon_deg, station_ecef, sat_ecef):
    phi, lam = math.radians(lat_deg), math.radians(lon_deg)
    dx, dy, dz = sat_ecef[0] - station_ecef[0], sat_ecef[1] - station_ecef[1], sat_ecef[2] - station_ecef[2]
    u = math.cos(phi) * math.cos(lam) * dx + math.cos(phi) * math.sin(lam) * dy + math.sin(phi) * dz
    slant_range = math.sqrt(dx**2 + dy**2 + dz**2)
    elev_deg = math.degrees(math.asin(u / slant_range)) if slant_range > 0 else 0
    if elev_deg < 3.0: elev_deg = 3.0
    E = math.radians(elev_deg)
    zenith_delay = 0.002277 * 1013.25
    mapping_func = 1.0 / (math.sin(E) + (0.0026 / (math.tan(E) + 0.001)))
    return (zenith_delay * mapping_func) / SPEED_OF_LIGHT, round(elev_deg, 2)

def format_delay_hhmmss(seconds):
    td = timedelta(seconds=abs(seconds))
    total_sec = int(td.total_seconds())
    hours, remainder = divmod(total_sec, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    prefix = "-" if seconds < 0 else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}.{abs(millis):03d}"

@app.route('/api/satellites', methods=['GET'])
def get_satellites():
    query = request.args.get('q', '').lower()
    if query:
        return jsonify([s for s in SATELLITE_DATABASE if query in s['name'].lower() or query in s['id']])
    return jsonify(SATELLITE_DATABASE)

@app.route('/api/manual-calculate', methods=['POST'])
def manual_calculate():
    data = request.json or {}
    u_lat, u_lon = float(data.get('uplink_lat', 13.7563)), float(data.get('uplink_lon', 100.5018))
    t_lat, t_lon = float(data.get('target_lat', 48.8566)), float(data.get('target_lon', 2.3522))
    norad_id = data.get('norad_id', '25544')
    pass_time_str = data.get('pass_datetime')

    sat_info = next((s for s in SATELLITE_DATABASE if s['id'] == norad_id), SATELLITE_DATABASE[0])
    sat_alt_m = sat_info['altitude_km'] * 1000.0
    sat_speed_ms = sat_info['speed_kms'] * 1000.0

    # Approximating pass geometry over uplink station
    u_ecef = geodetic_to_ecef(u_lat, u_lon, 0)
    s_ecef = geodetic_to_ecef(u_lat, u_lon, sat_alt_m)
    t_ecef = geodetic_to_ecef(t_lat, t_lon, 0)

    d1, t1_vac = sagnac_light_time_correction(u_ecef, s_ecef)
    d2, t2_vac = sagnac_light_time_correction(s_ecef, t_ecef)
    tropo_t1, e1 = saastamoinen_tropospheric_delay(u_lat, u_lon, u_ecef, s_ecef)
    tropo_t2, e2 = saastamoinen_tropospheric_delay(t_lat, t_lon, t_ecef, s_ecef)

    t1_total, t2_total = t1_vac + tropo_t1, t2_vac + tropo_t2
    total_delay = t1_total + t2_total

    uplink_dt = datetime.fromisoformat(pass_time_str) if pass_time_str else datetime.now(timezone.utc)
    surface_dist_m = math.sqrt((t_ecef[0]-u_ecef[0])**2 + (t_ecef[1]-u_ecef[1])**2 + (t_ecef[2]-u_ecef[2])**2)
    transit_sec = surface_dist_m / sat_speed_ms
    target_pass_dt = uplink_dt + timedelta(seconds=transit_sec)

    return jsonify({
        "mode": "Manual",
        "satellite": sat_info['name'],
        "uplink_pass_time": uplink_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_day": target_pass_dt.strftime("%A"),
        "transit_duration_hhmmss": format_delay_hhmmss(transit_sec),
        "elevation_angles": {"uplink": e1, "target": e2},
        "signal_delays": {
            "uplink_delay_t1": format_delay_hhmmss(t1_total),
            "downlink_delay_t2": format_delay_hhmmss(t2_total),
            "total_signal_delay": format_delay_hhmmss(total_delay),
            "tropospheric_ns": round((tropo_t1 + tropo_t2) * 1e9, 2),
            "total_delay_raw_ms": round(total_delay * 1000.0, 5)
        }
    })

@app.route('/api/realtime-telemetry', methods=['POST'])
def realtime_telemetry():
    data = request.json or {}
    u_lat, u_lon = float(data.get('uplink_lat', 13.7563)), float(data.get('uplink_lon', 100.5018))
    t_lat, t_lon = float(data.get('target_lat', 48.8566)), float(data.get('target_lon', 2.3522))
    norad_id = data.get('norad_id', '25544')

    sat_info = next((s for s in SATELLITE_DATABASE if s['id'] == norad_id), SATELLITE_DATABASE[0])
    sat_lat, sat_lon, sat_alt_m, sat_speed_ms = 0.0, 0.0, sat_info['altitude_km'] * 1000.0, sat_info['speed_kms'] * 1000.0
    sat_name = sat_info['name']

    try:
        resp = requests.get(f'https://api.wheretheiss.at/v1/satellites/{norad_id}', timeout=3)
        if resp.status_code == 200:
            sd = resp.json()
            sat_lat, sat_lon = float(sd['latitude']), float(sd['longitude'])
            sat_alt_m = float(sd['altitude']) * 1000.0
            sat_speed_ms = (float(sd['velocity']) * 1000.0) / 3600.0
            sat_name = sd.get('name', sat_name).upper() + f" ({norad_id})"
    except Exception:
        sat_lat, sat_lon = 15.0, 100.0

    u_ecef = geodetic_to_ecef(u_lat, u_lon, 0)
    t_ecef = geodetic_to_ecef(t_lat, t_lon, 0)
    s_ecef = geodetic_to_ecef(sat_lat, sat_lon, sat_alt_m)

    d1, t1_vac = sagnac_light_time_correction(u_ecef, s_ecef)
    d2, t2_vac = sagnac_light_time_correction(s_ecef, t_ecef)
    tropo_t1, e1 = saastamoinen_tropospheric_delay(u_lat, u_lon, u_ecef, s_ecef)
    tropo_t2, e2 = saastamoinen_tropospheric_delay(t_lat, t_lon, t_ecef, s_ecef)

    t1_total, t2_total = t1_vac + tropo_t1, t2_vac + tropo_t2
    total_delay = t1_total + t2_total

    now_utc = datetime.now(timezone.utc)
    dist_to_target = math.sqrt((t_ecef[0]-s_ecef[0])**2 + (t_ecef[1]-s_ecef[1])**2 + (t_ecef[2]-s_ecef[2])**2)
    time_to_target_sec = dist_to_target / sat_speed_ms if sat_speed_ms > 0 else 0
    target_pass_dt = now_utc + timedelta(seconds=time_to_target_sec)

    return jsonify({
        "mode": "Realtime",
        "satellite": sat_name,
        "sat_position": {"lat": round(sat_lat, 4), "lon": round(sat_lon, 4), "alt_km": round(sat_alt_m / 1000.0, 2)},
        "current_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_day": target_pass_dt.strftime("%A"),
        "time_until_target_pass_hhmmss": format_delay_hhmmss(time_to_target_sec),
        "elevation_angles": {"uplink": e1, "target": e2},
        "signal_delays": {
            "uplink_delay_t1": format_delay_hhmmss(t1_total),
            "downlink_delay_t2": format_delay_hhmmss(t2_total),
            "total_signal_delay": format_delay_hhmmss(total_delay),
            "tropospheric_ns": round((tropo_t1 + tropo_t2) * 1e9, 2),
            "total_delay_raw_ms": round(total_delay * 1000.0, 5)
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)