# app.py

from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
import requests
import os

app = Flask(__name__)

# Zodiac Elements
ELEMENTS = {
    'ARIES': 'Fire', 'TAURUS': 'Earth', 'GEMINI': 'Air', 'CANCER': 'Water',
    'LEO': 'Fire', 'VIRGO': 'Earth', 'LIBRA': 'Air', 'SCORPIO': 'Water',
    'SAGITTARIUS': 'Fire', 'CAPRICORN': 'Earth', 'AQUARIUS': 'Air', 'PISCES': 'Water'
}

# Zodiac Modes
MODES = {
    'ARIES': 'Cardinal', 'TAURUS': 'Fixed', 'GEMINI': 'Mutable', 'CANCER': 'Cardinal',
    'LEO': 'Fixed', 'VIRGO': 'Mutable', 'LIBRA': 'Cardinal', 'SCORPIO': 'Fixed',
    'SAGITTARIUS': 'Mutable', 'CAPRICORN': 'Cardinal', 'AQUARIUS': 'Fixed', 'PISCES': 'Mutable'
}

# YOUR GOOGLE API KEY
GOOGLE_API_KEY = 'AIzaSyBt8ZnaQxmwYVu1lfyR6RYrPxdMItGa4eA'  # <— your key here

@app.route('/astrology/chart', methods=['GET'])
def get_astrology_chart():
    name = request.args.get('name')
    date = request.args.get('date')
    time = request.args.get('time')
    location = request.args.get('location')

    # Format date correctly for Flatlib
    date_formatted = date.replace('-', '/')

    # Call Google Geocoding API
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={GOOGLE_API_KEY}"
    response = requests.get(geo_url)
    geo_data = response.json()

    if not geo_data['results']:
        return jsonify({"error": "Location not found"}), 400

    lat = geo_data['results'][0]['geometry']['location']['lat']
    lon = geo_data['results'][0]['geometry']['location']['lng']

    # Create Flatlib DateTime and GeoPos
    dt = Datetime(date_formatted, time, '+10:00')  # ✅ correct now
    pos = GeoPos(str(lat), str(lon))

    # Create the Chart
    chart = Chart(dt, pos)

    # Gather key astro points
    sun = chart.get('SUN')
    moon = chart.get('MOON')
    mercury = chart.get('MER')
    venus = chart.get('VEN')
    mars = chart.get('MAR')
    jupiter = chart.get('JUP')
    saturn = chart.get('SAT')
    uranus = chart.get('URA')
    neptune = chart.get('NEP')
    pluto = chart.get('PLU')
    ascendant = chart.get('ASC')
    midheaven = chart.get('MC')

    # Build astro data
    astro_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "sun_sign": sun.sign,
        "moon_sign": moon.sign,
        "mercury_sign": mercury.sign,
        "venus_sign": venus.sign,
        "mars_sign": mars.sign,
        "jupiter_sign": jupiter.sign,
        "saturn_sign": saturn.sign,
        "uranus_sign": uranus.sign,
        "neptune_sign": neptune.sign,
        "pluto_sign": pluto.sign,
        "rising_sign": ascendant.sign,
        "midheaven_sign": midheaven.sign
    }

    # Calculate dominant Element and Mode
    placements = [
        sun.sign, moon.sign, mercury.sign, venus.sign, mars.sign,
        jupiter.sign, saturn.sign, uranus.sign, neptune.sign, pluto.sign,
        ascendant.sign, midheaven.sign
    ]

    element_counts = {'Fire': 0, 'Earth': 0, 'Air': 0, 'Water': 0}
    mode_counts = {'Cardinal': 0, 'Fixed': 0, 'Mutable': 0}

    for sign in placements:
        sign_upper = sign.upper()
        if sign_upper in ELEMENTS:
            element_counts[ELEMENTS[sign_upper]] += 1
        if sign_upper in MODES:
            mode_counts[MODES[sign_upper]] += 1

    dominant_element = max(element_counts, key=element_counts.get)
    dominant_mode = max(mode_counts, key=mode_counts.get)

    astro_data['dominant_element'] = dominant_element
    astro_data['mode'] = dominant_mode

    return jsonify(astro_data)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
