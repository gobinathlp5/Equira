from flask import Flask, render_template, request, jsonify
import json
import math
import requests
import os

app = Flask(__name__)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'hospitals.json')
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def load_hospitals():
    """Loads hospital data from the JSON file."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {DATA_FILE} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Failed to decode {DATA_FILE}.")
        return []

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points 
    on the Earth's surface using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['GET'])
def search_hospitals():
    user_lat = request.args.get('lat')
    user_lon = request.args.get('lon')
    query = request.args.get('query')
    emergency_type = request.args.get('type', 'all').lower()

    # 1. Handle Geocoding if lat/lon not provided
    if not user_lat or not user_lon:
        if not query:
            return jsonify({"error": "Please provide a location or enable GPS."}), 400
        
        # Call OpenStreetMap Nominatim API
        # IMPORTANT: User-Agent is required by OSM policy
        headers = {'User-Agent': 'RuralHealthApp/1.0 (educational_project)'}
        params = {'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'in'}
        
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=headers)
            data = resp.json()
            if not data:
                return jsonify({"error": "Location not found. Try a nearby city name."}), 404
            
            user_lat = float(data[0]['lat'])
            user_lon = float(data[0]['lon'])
        except Exception as e:
            return jsonify({"error": "Geocoding service unavailable."}), 500
    else:
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except ValueError:
            return jsonify({"error": "Invalid GPS coordinates."}), 400

    # 2. Filter and Sort Hospitals
    hospitals = load_hospitals()
    results = []
    
    for hosp in hospitals:
        dist = haversine_distance(user_lat, user_lon, hosp['latitude'], hosp['longitude'])
        
        # Filter: Within 50km radius
        if dist > 50:
            continue

        # Filter: Emergency Type
        if emergency_type != 'all':
            specialties = [s.lower() for s in hosp.get('specialties', [])]
            # Include if it matches specialty OR if it's a general emergency and the hospital has emergency services
            if emergency_type not in specialties and not (hosp['emergency_services'] and emergency_type == 'accident'):
                continue

        hosp_data = hosp.copy()
        hosp_data['distance'] = round(dist, 2)
        results.append(hosp_data)

    # Sort by distance
    results.sort(key=lambda x: x['distance'])

    return jsonify({
        "user_location": {"lat": user_lat, "lon": user_lon},
        "hospitals": results
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)
