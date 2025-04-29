from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from urllib.parse import quote
import requests
import os
from datetime import datetime

app = Flask(__name__)
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Zodiac Elements and Modes
ELEMENTS = {
    'ARIES': 'Fire', 'TAURUS': 'Earth', 'GEMINI': 'Air', 'CANCER': 'Water',
    'LEO': 'Fire', 'VIRGO': 'Earth', 'LIBRA': 'Air', 'SCORPIO': 'Water',
    'SAGITTARIUS': 'Fire', 'CAPRICORN': 'Earth', 'AQUARIUS': 'Air', 'PISCES': 'Water'
}
MODES = {
    'ARIES': 'Cardinal', 'TAURUS': 'Fixed', 'GEMINI': 'Mutable', 'CANCER': 'Cardinal',
    'LEO': 'Fixed', 'VIRGO': 'Mutable', 'LIBRA': 'Cardinal', 'SCORPIO': 'Fixed',
    'SAGITTARIUS': 'Mutable', 'CAPRICORN': 'Cardinal', 'AQUARIUS': 'Fixed', 'PISCES': 'Mutable'
}

# Utility to convert Decimal Degrees to D:M:S
def decimal_to_dms(decimal):
    is_negative = decimal < 0
    decimal = abs(decimal)
    degrees = int(decimal)
    minutes_float = (decimal - degrees) * 60
    minutes = int(minutes_float)
    seconds = int((minutes_float - minutes) * 60)
    dms = f"{'-' if is_negative else ''}{degrees}:{minutes}:{seconds}"
    return dms

@app.route('/humandesign/profile', methods=['GET'])
def get_profile():
    name = request.args.get('name')
    date = request.args.get('date')
    time = request.args.get('time')
    location = request.args.get('location')
    # Simulated Human Design profile
    hd_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "type": "Manifesting Generator",
        "strategy": "To Respond",
        "authority": "Emotional - Solar Plexus",
        "profile": "6/2",
        "definition": "Split Definition",
        "incarnation_cross": "Right Angle Cross of the Sleeping Phoenix",
        "signature": "Satisfaction",
        "not_self_theme": "Frustration",
        "digestion": "Nervous",
        "motivation": "Hope",
        "perspective": "Personal",
        "environment": "Mountains",
        "gates": ["34", "20", "10", "57"],
        "channels": ["34-20", "10-57"],
        "defined_centres": ["Sacral", "G", "Throat"],
        "undefined_centres": ["Root", "Solar Plexus", "Heart"],
        "sun_sign": "Taurus",
        "moon_sign": "Cancer",
        "rising_sign": "Leo",
        "midheaven": "Aquarius",
        "dominant_element": "Earth",
        "mode": "Fixed"
    }
    return jsonify(hd_data)

@app.route('/astrology/chart', methods=['GET'])
def get_astrology_chart():
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    try:
        time_24hr = datetime.strptime(time.strip(), "%I:%M %p").strftime("%H:%M")
    except ValueError:
        return jsonify({"error": "Invalid time format. Please use HH:MM AM/PM."}), 400
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    response = requests.get(geo_url)
    geo_data = response.json()
    if not geo_data.get('results'):
        return jsonify({"error": "Location not found. Please include city, state, country."}), 400
    lat = geo_data['results'][0]['geometry']['location']['lat']
    lon = geo_data['results'][0]['geometry']['location']['lng']
    lat_dms = decimal_to_dms(lat)
    lon_dms = decimal_to_dms(lon)
    try:
        pos = GeoPos(lat_dms, lon_dms)
    except Exception as e:
        return jsonify({"error": f"GeoPos creation failed: {str(e)}. Lat: {lat}, Lon: {lon}, Lat DMS: {lat_dms}, Lon DMS: {lon_dms}"}), 400
    dt = Datetime(date, time_24hr, '+00:00')
    try:
        chart = Chart(dt, pos, IDs=['Sun', 'Moon'])
        available_objects = [obj.id for obj in chart.objects]
        return jsonify({"message": "Chart created", "available_objects": available_objects})
    except Exception as e:
        return jsonify({"error": f"Chart creation failed: {str(e)}. Date: {date}, Time: {time_24hr}, Location: {location}, Lat DMS: {lat_dms}, Lon DMS: {lon_dms}"}), 500

@app.route('/moonphase', methods=['GET'])
def get_moon_phase():
    date = request.args.get('date')
    moon_data = {
        "date": date,
        "moon_phase": "New Moon"  # Placeholder for now
    }
    return jsonify(moon_data)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)

