from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from urllib.parse import quote
import requests
import os

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

from datetime import datetime  # Add this at the top with your imports

...

@app.route('/astrology/chart', methods=['GET'])
def get_astrology_chart():
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')

    # Convert 12-hour AM/PM time to 24-hour format
    try:
        time_24hr = datetime.strptime(time.strip(), "%I:%M %p").strftime("%H:%M")
    except ValueError:
        return jsonify({"error": "Invalid time format. Please use HH:MM AM/PM."}), 400

    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    response = requests.get(geo_url)
    geo_data = response.json()

    if not geo_data.get('results'):
        return jsonify({"error": "Location not found"}), 400

    lat = geo_data['results'][0]['geometry']['location']['lat']
    lon = geo_data['results'][0]['geometry']['location']['lng']

    pos = GeoPos(decimal_to_dms(lat), decimal_to_dms(lon))
    dt = Datetime(date, time_24hr, '+00:00')
    chart = Chart(dt, pos, IDs='NATAL')


    # Prepare astro data
    astro_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "sun_sign": chart.getObject('SUN').sign,
        "moon_sign": chart.getObject('MOON').sign,
        "mercury_sign": chart.getObject('MER').sign,
        "venus_sign": chart.getObject('VEN').sign,
        "mars_sign": chart.getObject('MAR').sign,
        "jupiter_sign": chart.getObject('JUP').sign,
        "saturn_sign": chart.getObject('SAT').sign,
        "uranus_sign": chart.getObject('URA').sign,
        "neptune_sign": chart.getObject('NEP').sign,
        "pluto_sign": chart.getObject('PLU').sign,
        "rising_sign": chart.getObject('ASC').sign,
        "midheaven_sign": chart.getObject('MC').sign
    }

    # Calculate dominant element and mode
    placements = list(astro_data.values())[4:-2]
    element_counts = {'Fire': 0, 'Earth': 0, 'Air': 0, 'Water': 0}
    mode_counts = {'Cardinal': 0, 'Fixed': 0, 'Mutable': 0}

    for sign in placements:
        sign_upper = sign.upper()
        if sign_upper in ELEMENTS:
            element_counts[ELEMENTS[sign_upper]] += 1
        if sign_upper in MODES:
            mode_counts[MODES[sign_upper]] += 1

    astro_data['dominant_element'] = max(element_counts, key=element_counts.get)
    astro_data['mode'] = max(mode_counts, key=mode_counts.get)

    return jsonify(astro_data)

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

