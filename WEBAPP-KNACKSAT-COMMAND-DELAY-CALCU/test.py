

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from datetime import datetime, timedelta
# import math

# app = Flask(__name__)
# CORS(app)

# # Physical Constants
# SPEED_OF_LIGHT = 299792458.0  # m/s
# EARTH_RADIUS = 6371000.0      # meters

# # Satellite profiles (Altitude in meters, Ground Speed in m/s)
# SATELLITES = {
#     "ISS": {"altitude": 408000.0, "speed": 7660.0},
#     "KNACKSAT": {"altitude": 500000.0, "speed": 7600.0},
#     "NOAA-19": {"altitude": 850000.0, "speed": 7400.0}
# }

# def haversine_distance(lat1, lon1, lat2, lon2):
#     """Surface distance between two coordinates in meters."""
#     phi1, phi2 = math.radians(lat1), math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lon2 - lon1)

#     a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
#     return 2 * EARTH_RADIUS * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# def latlon_to_ecef(lat, lon, alt=0.0):
#     """Converts geodetic coordinates to 3D Cartesian coordinates."""
#     r = EARTH_RADIUS + alt
#     rad_lat, rad_lon = math.radians(lat), math.radians(lon)
#     x = r * math.cos(rad_lat) * math.cos(rad_lon)
#     y = r * math.cos(rad_lat) * math.sin(rad_lon)
#     z = r * math.sin(rad_lat)
#     return x, y, z

# def format_delay_hhmmss(seconds):
#     """Formats float seconds into HH:MM:SS.ms string."""
#     td = timedelta(seconds=seconds)
#     total_sec = int(td.total_seconds())
#     hours, remainder = divmod(total_sec, 3600)
#     minutes, secs = divmod(remainder, 60)
#     millis = int((seconds - int(seconds)) * 1000)
#     return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

# @app.route('/api/calculate', methods=['POST'])
# def calculate_pass():
#     data = request.json or {}
    
#     # Inputs
#     uplink_lat = float(data.get('uplink_lat', 13.7563))
#     uplink_lon = float(data.get('uplink_lon', 100.5018))
#     target_lat = float(data.get('target_lat', 48.8566))
#     target_lon = float(data.get('target_lon', 2.3522))
#     sat_name = data.get('sat_id', 'ISS')
#     pass_time_str = data.get('pass_datetime')  # ISO Format: YYYY-MM-DDTHH:MM

#     sat_info = SATELLITES.get(sat_name, SATELLITES["ISS"])
#     sat_alt = sat_info["altitude"]
#     sat_speed = sat_info["speed"]

#     # 1. Calculate Surface Distance
#     surface_dist = haversine_distance(uplink_lat, uplink_lon, target_lat, target_lon)

#     # 2. Estimate Target Pass Day & Time
#     uplink_dt = datetime.fromisoformat(pass_time_str) if pass_time_str else datetime.utcnow()
#     transit_time_sec = surface_dist / sat_speed
#     target_pass_dt = uplink_dt + timedelta(seconds=transit_time_sec)

#     # 3. Compute 3D Slant Distances (Assuming satellite overhead at pass)
#     u_x, u_y, u_z = latlon_to_ecef(uplink_lat, uplink_lon, 0)
#     s_x, s_y, s_z = latlon_to_ecef(uplink_lat, uplink_lon, sat_alt)
#     t_x, t_y, t_z = latlon_to_ecef(target_lat, target_lon, 0)

#     d1 = math.sqrt((s_x - u_x)**2 + (s_y - u_y)**2 + (s_z - u_z)**2)
#     d2 = math.sqrt((t_x - s_x)**2 + (t_y - s_y)**2 + (t_z - s_z)**2)

#     # 4. Signal Propagation Delays (t = d / c)
#     t1_sec = d1 / SPEED_OF_LIGHT
#     t2_sec = d2 / SPEED_OF_LIGHT
#     total_delay_sec = t1_sec + t2_sec

#     return jsonify({
#         "satellite": sat_name,
#         "uplink_pass_time": uplink_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
#         "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
#         "target_pass_day": target_pass_dt.strftime("%A"),
#         "transit_duration_hhmmss": format_delay_hhmmss(transit_time_sec),
#         "surface_distance_km": round(surface_dist / 1000, 2),
#         "signal_delays": {
#             "uplink_delay_t1": format_delay_hhmmss(t1_sec),
#             "downlink_delay_t2": format_delay_hhmmss(t2_sec),
#             "total_signal_delay": format_delay_hhmmss(total_delay_sec),
#             "total_delay_raw_ms": round(total_delay_sec * 1000, 3)
#         }
#     })

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)


# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from datetime import datetime, timedelta, timezone
# import math
# import requests

# app = Flask(__name__)
# CORS(app)

# # Physical Constants
# SPEED_OF_LIGHT = 299792458.0  # Speed of light in m/s (c)
# EARTH_RADIUS = 6371000.0      # Earth radius in meters

# def haversine_distance(lat1, lon1, lat2, lon2):
#     """Calculates great-circle surface distance in meters."""
#     phi1, phi2 = math.radians(lat1), math.radians(lat2)
#     dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
#     a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
#     return 2 * EARTH_RADIUS * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# def latlon_to_ecef(lat, lon, alt_meters=0.0):
#     """Converts Latitude, Longitude, Altitude into 3D Cartesian coordinates (ECEF)."""
#     r = EARTH_RADIUS + alt_meters
#     rad_lat, rad_lon = math.radians(lat), math.radians(lon)
#     x = r * math.cos(rad_lat) * math.cos(rad_lon)
#     y = r * math.cos(rad_lat) * math.sin(rad_lon)
#     z = r * math.sin(rad_lat)
#     return x, y, z

# def format_delay_hhmmss(seconds):
#     """Formats float seconds into HH:MM:SS.ms string format."""
#     td = timedelta(seconds=seconds)
#     total_sec = int(td.total_seconds())
#     hours, remainder = divmod(total_sec, 3600)
#     minutes, secs = divmod(remainder, 60)
#     millis = int((seconds - int(seconds)) * 1000)
#     return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

# @app.route('/api/realtime-telemetry', methods=['POST'])
# def get_realtime_telemetry():
#     data = request.json or {}
    
#     uplink_lat = float(data.get('uplink_lat', 13.7563))
#     uplink_lon = float(data.get('uplink_lon', 100.5018))
#     target_lat = float(data.get('target_lat', 48.8566))
#     target_lon = float(data.get('target_lon', 2.3522))
#     norad_id = data.get('norad_id', '25544')  # Default: ISS (25544)

#     # 1. Fetch live real-time position from WhereTheISS API
#     sat_lat, sat_lon, sat_alt_m, sat_speed_ms = 0.0, 0.0, 408000.0, 7660.0
#     sat_name = "ISS (NORAD 25544)"
    
#     try:
#         resp = requests.get(f'https://api.wheretheiss.at/v1/satellites/{norad_id}', timeout=3)
#         if resp.status_code == 200:
#             sat_data = resp.json()
#             sat_lat = float(sat_data['latitude'])
#             sat_lon = float(sat_data['longitude'])
#             sat_alt_m = float(sat_data['altitude']) * 1000.0  # km to meters
#             sat_speed_ms = (float(sat_data['velocity']) * 1000.0) / 3600.0  # km/h to m/s
#             sat_name = sat_data.get('name', 'SATELLITE').upper() + f" ({norad_id})"
#     except Exception as e:
#         # Fallback coordinates if API network request times out
#         sat_lat, sat_lon = 15.0, 100.0

#     # 2. Calculate 3D Slant Distances
#     u_x, u_y, u_z = latlon_to_ecef(uplink_lat, uplink_lon, 0)
#     s_x, s_y, s_z = latlon_to_ecef(sat_lat, sat_lon, sat_alt_m)
#     t_x, t_y, t_z = latlon_to_ecef(target_lat, target_lon, 0)

#     d1 = math.sqrt((s_x - u_x)**2 + (s_y - u_y)**2 + (s_z - u_z)**2)  # Uplink -> Sat
#     d2 = math.sqrt((t_x - s_x)**2 + (t_y - s_y)**2 + (t_z - s_z)**2)  # Sat -> Target

#     # 3. Calculate Signal Propagation Delays (t = d / c)
#     t1_sec = d1 / SPEED_OF_LIGHT
#     t2_sec = d2 / SPEED_OF_LIGHT
#     total_delay_sec = t1_sec + t2_sec

#     # 4. Predict Time and Day Satellite Passes Over Target
#     now_utc = datetime.now(timezone.utc)
#     dist_sat_to_target = haversine_distance(sat_lat, sat_lon, target_lat, target_lon)
#     time_to_target_sec = dist_sat_to_target / sat_speed_ms if sat_speed_ms > 0 else 0
#     target_pass_dt = now_utc + timedelta(seconds=time_to_target_sec)

#     return jsonify({
#         "satellite": sat_name,
#         "sat_position": {
#             "lat": round(sat_lat, 4),
#             "lon": round(sat_lon, 4),
#             "alt_km": round(sat_alt_m / 1000.0, 2)
#         },
#         "current_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
#         "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
#         "target_pass_day": target_pass_dt.strftime("%A"),
#         "time_until_target_pass_hhmmss": format_delay_hhmmss(time_to_target_sec),
#         "surface_dist_to_target_km": round(dist_sat_to_target / 1000.0, 2),
#         "signal_delays": {
#             "uplink_delay_t1": format_delay_hhmmss(t1_sec),
#             "downlink_delay_t2": format_delay_hhmmss(t2_sec),
#             "total_signal_delay": format_delay_hhmmss(total_delay_sec),
#             "total_delay_raw_ms": round(total_delay_sec * 1000, 4)
#         }
#     })

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)


from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import math
import requests

app = Flask(__name__)
CORS(app)

# Physical Constants
SPEED_OF_LIGHT = 299792458.0  # m/s
EARTH_RADIUS = 6371000.0      # meters

# Searchable Satellite Database
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

def haversine_distance(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * EARTH_RADIUS * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def latlon_to_ecef(lat, lon, alt_meters=0.0):
    r = EARTH_RADIUS + alt_meters
    rad_lat, rad_lon = math.radians(lat), math.radians(lon)
    x = r * math.cos(rad_lat) * math.cos(rad_lon)
    y = r * math.cos(rad_lat) * math.sin(rad_lon)
    z = r * math.sin(rad_lat)
    return x, y, z

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
        filtered = [s for s in SATELLITE_DATABASE if query in s['name'].lower() or query in s['id']]
        return jsonify(filtered)
    return jsonify(SATELLITE_DATABASE)

@app.route('/api/manual-calculate', methods=['POST'])
def manual_calculate():
    data = request.json or {}
    uplink_lat = float(data.get('uplink_lat', 13.7563))
    uplink_lon = float(data.get('uplink_lon', 100.5018))
    target_lat = float(data.get('target_lat', 48.8566))
    target_lon = float(data.get('target_lon', 2.3522))
    norad_id = data.get('norad_id', '25544')
    pass_time_str = data.get('pass_datetime')

    sat_info = next((s for s in SATELLITE_DATABASE if s['id'] == norad_id), SATELLITE_DATABASE[0])
    sat_alt_m = sat_info['altitude_km'] * 1000.0
    sat_speed_ms = sat_info['speed_kms'] * 1000.0

    surface_dist = haversine_distance(uplink_lat, uplink_lon, target_lat, target_lon)
    uplink_dt = datetime.fromisoformat(pass_time_str) if pass_time_str else datetime.now(timezone.utc)
    transit_time_sec = surface_dist / sat_speed_ms
    target_pass_dt = uplink_dt + timedelta(seconds=transit_time_sec)

    u_x, u_y, u_z = latlon_to_ecef(uplink_lat, uplink_lon, 0)
    s_x, s_y, s_z = latlon_to_ecef(uplink_lat, uplink_lon, sat_alt_m)
    t_x, t_y, t_z = latlon_to_ecef(target_lat, target_lon, 0)

    d1 = math.sqrt((s_x - u_x)**2 + (s_y - u_y)**2 + (s_z - u_z)**2)
    d2 = math.sqrt((t_x - s_x)**2 + (t_y - s_y)**2 + (t_z - s_z)**2)

    t1_sec = d1 / SPEED_OF_LIGHT
    t2_sec = d2 / SPEED_OF_LIGHT
    total_delay_sec = t1_sec + t2_sec

    return jsonify({
        "mode": "Manual",
        "satellite": sat_info['name'],
        "uplink_pass_time": uplink_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_day": target_pass_dt.strftime("%A"),
        "transit_duration_hhmmss": format_delay_hhmmss(transit_time_sec),
        "surface_distance_km": round(surface_dist / 1000.0, 2),
        "signal_delays": {
            "uplink_delay_t1": format_delay_hhmmss(t1_sec),
            "downlink_delay_t2": format_delay_hhmmss(t2_sec),
            "total_signal_delay": format_delay_hhmmss(total_delay_sec),
            "total_delay_raw_ms": round(total_delay_sec * 1000, 4)
        }
    })

@app.route('/api/realtime-telemetry', methods=['POST'])
def realtime_telemetry():
    data = request.json or {}
    uplink_lat = float(data.get('uplink_lat', 13.7563))
    uplink_lon = float(data.get('uplink_lon', 100.5018))
    target_lat = float(data.get('target_lat', 48.8566))
    target_lon = float(data.get('target_lon', 2.3522))
    norad_id = data.get('norad_id', '25544')

    sat_info = next((s for s in SATELLITE_DATABASE if s['id'] == norad_id), SATELLITE_DATABASE[0])
    sat_lat, sat_lon, sat_alt_m, sat_speed_ms = 0.0, 0.0, sat_info['altitude_km'] * 1000.0, sat_info['speed_kms'] * 1000.0
    sat_name = sat_info['name']

    try:
        resp = requests.get(f'https://api.wheretheiss.at/v1/satellites/{norad_id}', timeout=2)
        if resp.status_code == 200:
            sat_data = resp.json()
            sat_lat = float(sat_data['latitude'])
            sat_lon = float(sat_data['longitude'])
            sat_alt_m = float(sat_data['altitude']) * 1000.0
            sat_speed_ms = (float(sat_data['velocity']) * 1000.0) / 3600.0
            sat_name = sat_data.get('name', sat_name).upper() + f" ({norad_id})"
    except Exception:
        sat_lat, sat_lon = 15.0, 100.0

    u_x, u_y, u_z = latlon_to_ecef(uplink_lat, uplink_lon, 0)
    s_x, s_y, s_z = latlon_to_ecef(sat_lat, sat_lon, sat_alt_m)
    t_x, t_y, t_z = latlon_to_ecef(target_lat, target_lon, 0)

    d1 = math.sqrt((s_x - u_x)**2 + (s_y - u_y)**2 + (s_z - u_z)**2)
    d2 = math.sqrt((t_x - s_x)**2 + (t_y - s_y)**2 + (t_z - s_z)**2)

    t1_sec = d1 / SPEED_OF_LIGHT
    t2_sec = d2 / SPEED_OF_LIGHT
    total_delay_sec = t1_sec + t2_sec

    now_utc = datetime.now(timezone.utc)
    dist_sat_to_target = haversine_distance(sat_lat, sat_lon, target_lat, target_lon)
    time_to_target_sec = dist_sat_to_target / sat_speed_ms if sat_speed_ms > 0 else 0
    target_pass_dt = now_utc + timedelta(seconds=time_to_target_sec)

    return jsonify({
        "mode": "Realtime",
        "satellite": sat_name,
        "sat_position": {
            "lat": round(sat_lat, 4),
            "lon": round(sat_lon, 4),
            "alt_km": round(sat_alt_m / 1000.0, 2)
        },
        "current_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_time": target_pass_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "target_pass_day": target_pass_dt.strftime("%A"),
        "time_until_target_pass_hhmmss": format_delay_hhmmss(time_to_target_sec),
        "surface_dist_to_target_km": round(dist_sat_to_target / 1000.0, 2),
        "signal_delays": {
            "uplink_delay_t1": format_delay_hhmmss(t1_sec),
            "downlink_delay_t2": format_delay_hhmmss(t2_sec),
            "total_signal_delay": format_delay_hhmmss(total_delay_sec),
            "total_delay_raw_ms": round(total_delay_sec * 1000, 4)
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)