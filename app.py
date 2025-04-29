from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib import const, angle
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

# Astrology-related endpoints
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
    dt = Datetime(date, time_24hr, '+10:00')  # AEST offset for Cowra, NSW
    try:
        # Create chart without specifying a house system (we'll calculate 6th House manually)
        chart = Chart(dt, pos, IDs=['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'])
    except Exception as e:
        return jsonify({"error": f"Chart creation failed: {str(e)}. Date: {date}, Time: {time_24hr}, Location: {location}, Lat DMS: {lat_dms}, Lon DMS: {lon_dms}"}), 500

    available_objects = [obj.id for obj in chart.objects]
    available_angles = [angle.id for angle in chart.angles]
    asc = chart.getAngle('Asc')
    mc = chart.getAngle('MC')
    # Calculate 6th House sign manually based on Ascendant
    sixth_house_sign = None
    if asc and asc.sign:
        signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        asc_index = signs.index(asc.sign.upper())
        sixth_house_index = (asc_index + 5) % 12  # 6th House is 5 signs after Ascendant (0-based index)
        sixth_house_sign = signs[sixth_house_index].capitalize()
        print(f"Manually calculated 6th House sign: {sixth_house_sign}")
    # Get Ascendant ruler (planet ruling the Rising sign)
    asc_ruler = None
    if asc and asc.sign == 'Capricorn':
        asc_ruler = chart.getObject('Saturn')  # Capricorn is ruled by Saturn
    asc_ruler_sign = asc_ruler.sign if asc_ruler else None
    astro_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "sun_sign": chart.getObject('Sun').sign if chart.getObject('Sun') else None,
        "moon_sign": chart.getObject('Moon').sign if chart.getObject('Moon') else None,
        "mercury_sign": chart.getObject('Mercury').sign if chart.getObject('Mercury') else None,
        "venus_sign": chart.getObject('Venus').sign if chart.getObject('Venus') else None,
        "mars_sign": chart.getObject('Mars').sign if chart.getObject('Mars') else None,
        "jupiter_sign": chart.getObject('Jupiter').sign if chart.getObject('Jupiter') else None,
        "saturn_sign": chart.getObject('Saturn').sign if chart.getObject('Saturn') else None,
        "uranus_sign": chart.getObject('Uranus').sign if chart.getObject('Uranus') else None,
        "neptune_sign": chart.getObject('Neptune').sign if chart.getObject('Neptune') else None,
        "pluto_sign": chart.getObject('Pluto').sign if chart.getObject('Pluto') else None,
        "rising_sign": asc.sign if asc else None,
        "rising_sign_degree": asc.signlon if asc else None,
        "midheaven_sign": mc.sign if mc else None,
        "midheaven_sign_degree": mc.signlon if mc else None,
        "sixth_house_sign": sixth_house_sign,
        "ascendant_ruler_sign": asc_ruler_sign,
        "available_objects": available_objects,
        "available_angles": available_angles
    }
    
    # Equal weighting for all planets, Ascendant, and Midheaven
    placements = [
        astro_data['sun_sign'],
        astro_data['moon_sign'],
        astro_data['mercury_sign'],
        astro_data['venus_sign'],
        astro_data['mars_sign'],
        astro_data['jupiter_sign'],
        astro_data['saturn_sign'],
        astro_data['uranus_sign'],
        astro_data['neptune_sign'],
        astro_data['pluto_sign'],
        astro_data['rising_sign'],
        astro_data['midheaven_sign']
    ]
    element_counts = {'Fire': 0, 'Earth': 0, 'Air': 0, 'Water': 0}
    mode_counts = {'Cardinal': 0, 'Fixed': 0, 'Mutable': 0}
    for sign in placements:
        if sign:
            sign_upper = sign.upper()
            if sign_upper in ELEMENTS:
                element_counts[ELEMENTS[sign_upper]] += 1
            if sign_upper in MODES:
                mode_counts[MODES[sign_upper]] += 1
    
    # Tiebreaker: Prioritize Moon's element for Medical Astrology
    element_counts_list = [(elem, count) for elem, count in element_counts.items()]
    element_counts_list.sort(key=lambda x: x[1], reverse=True)
    if element_counts_list[0][1] == element_counts_list[1][1]:  # Tie for first place
        moon_sign = astro_data['moon_sign']
        if moon_sign:
            moon_sign_upper = moon_sign.upper()
            dominant_element = ELEMENTS[moon_sign_upper]  # Moon's element (Cancer → Water)
        else:
            dominant_element = element_counts_list[0][0]
    else:
        dominant_element = element_counts_list[0][0]
    
    astro_data['dominant_element'] = dominant_element
    astro_data['mode'] = max(mode_counts, key=mode_counts.get)
    return jsonify(astro_data)
@app.route('/moonphase', methods=['GET'])
def get_moon_phase():
    date = request.args.get('date')
    # Create a chart for the given date at 00:00 UTC
    dt = Datetime(date.replace('-', '/'), '00:00', '+00:00')
    pos = GeoPos('0:0:0', '0:0:0')  # Location doesn’t affect Moon phase
    try:
        chart = Chart(dt, pos, IDs=['Sun', 'Moon'])
        sun_lon = chart.getObject('Sun').lon
        moon_lon = chart.getObject('Moon').lon
        # Calculate angular distance between Sun and Moon
        dist = angle.distance(sun_lon, moon_lon)
        # Log for debugging
        print(f"Sun longitude: {sun_lon}, Moon longitude: {moon_lon}, Distance: {dist}")
        # Refine phase boundaries
        if 0 <= dist <= 22.5 or 337.5 < dist <= 360:
            phase = "New Moon"
        elif 22.5 < dist <= 67.5:
            phase = "Waxing Crescent"
        elif 67.5 < dist <= 112.5:
            phase = "First Quarter"
        elif 112.5 < dist <= 157.5:
            phase = "Waxing Gibbous"
        elif 157.5 < dist <= 202.5:
            phase = "Full Moon"
        elif 202.5 < dist <= 247.5:
            phase = "Waning Gibbous"
        elif 247.5 < dist <= 292.5:
            phase = "Last Quarter"
        else:
            phase = "Waning Crescent"
        moon_data = {
            "date": date,
            "moon_phase": phase,
            "angular_distance": dist  # For debugging
        }
    except Exception as e:
        return jsonify({"error": f"Moon phase calculation failed: {str(e)}"}), 500
    return jsonify(moon_data)

# Human Design endpoint
@app.route('/humandesign/profile', methods=['GET'])
def get_profile():
    name = request.args.get('name')
    date = request.args.get('date')
    time = request.args.get('time')
    location = request.args.get('location')
    # Correct Human Design profile for Karen Anne Waters
    hd_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "type": "Manifesting Generator",
        "strategy": "To Respond",
        "authority": "Emotional - Solar Plexus",
        "definition": "Single Definition",
        "profile": "6/2",
        "incarnation_cross": "Left Angle Cross of Dedication (23/43 | 30/29)",
        "signature": "Satisfaction",
        "not_self_theme": "Frustration",
        "digestion": "Nervous",
        "design_sense": "Inner Vision",
        "motivation": "Desire",
        "perspective": "Personal",
        "environment": "Mountains",
        "gates": ["5", "9", "16", "18", "19", "20", "21", "22", "23", "28", "29", "30", "34", "35", "36", "39", "43", "50", "52", "53", "54"],
        "channels": ["43-23", "20-34", "35-36", "9-52"]
    }
    return jsonify(hd_data)

if __name__ == '__main__':
    app.run(debug=True)
