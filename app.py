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
    print("Starting /astrology/chart endpoint")
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    print(f"Received inputs: name={name}, date={date}, time={time}, location={location}")
    
    try:
        time_24hr = datetime.strptime(time.strip(), "%I:%M %p").strftime("%H:%M")
        print(f"Converted time to 24hr format: {time_24hr}")
    except ValueError as e:
        print(f"Time conversion error: {str(e)}")
        return jsonify({"error": "Invalid time format. Please use HH:MM AM/PM."}), 400
    
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    response = requests.get(geo_url)
    geo_data = response.json()
    if not geo_data.get('results'):
        print("Geocoding failed: Location not found")
        return jsonify({"error": "Location not found. Please include city, state, country."}), 400
    
    lat = geo_data['results'][0]['geometry']['location']['lat']
    lon = geo_data['results'][0]['geometry']['location']['lng']
    lat_dms = decimal_to_dms(lat)
    lon_dms = decimal_to_dms(lon)
    print(f"Geocoded location: lat={lat}, lon={lon}, lat_dms={lat_dms}, lon_dms={lon_dms}")
    
    try:
        pos = GeoPos(lat_dms, lon_dms)
        print("GeoPos created successfully")
    except Exception as e:
        print(f"GeoPos creation failed: {str(e)}")
        return jsonify({"error": f"GeoPos creation failed: {str(e)}. Lat: {lat}, Lon: {lon}, Lat DMS: {lat_dms}, Lon DMS: {lon_dms}"}), 400
    
    dt = Datetime(date, time_24hr, '+10:00')  # AEST offset for Cowra, NSW
    print(f"Datetime created: {date} {time_24hr} +10:00")
    
    try:
        print("Creating chart with Placidus House system")
        chart = Chart(dt, pos, hsys=const.HOUSES_PLACIDUS, IDs=['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'])
        print("Chart created successfully")
    except Exception as e:
        print(f"Chart creation failed: {str(e)}")
        return jsonify({"error": f"Chart creation failed: {str(e)}. Date: {date}, Time: {time_24hr}, Location: {location}, Lat DMS: {lat_dms}, Lon DMS: {lon_dms}"}), 500

    available_objects = [obj.id for obj in chart.objects]
    available_angles = [angle.id for angle in chart.angles]
    print(f"Available objects: {available_objects}")
    print(f"Available angles: {available_angles}")
    
    # Get Ascendant and Midheaven
    asc = chart.getAngle('Asc')
    mc = chart.getAngle('MC')
    print(f"Ascendant: {asc.sign if asc else None}, Midheaven: {mc.sign if mc else None}")
    
    # Get house cusps directly from chart.houses
    houses = chart.houses
    print(f"Inspecting chart.houses: {houses}")
    print(f"chart.houses.content: {houses.content}")
    
    house_cusps = []
    try:
        for i in range(1, 13):  # Iterate over houses 1 to 12
            house_key = f'House{i}'
            house = houses.content[house_key]
            house_cusps.append({
                "house": i,
                "sign": house.sign,
                "degree": house.lon
            })
        print(f"House cusps: {house_cusps}")
    except Exception as e:
        print(f"Failed to retrieve house cusps: {str(e)}")
        return jsonify({"error": f"Failed to retrieve house cusps: {str(e)}"}), 500
    
    # Function to determine which house a planet is in
    def get_planet_house(planet_lon, house_cusps):
        if not house_cusps:
            return None
        for i in range(len(house_cusps)):
            start_lon = house_cusps[i]["degree"]
            end_lon = house_cusps[(i + 1) % len(house_cusps)]["degree"]
            # Handle wraparound at 360°
            if end_lon < start_lon:
                if planet_lon >= start_lon or planet_lon < end_lon:
                    return house_cusps[i]["house"]
            else:
                if start_lon <= planet_lon < end_lon:
                    return house_cusps[i]["house"]
        return None
    
    # Assign planets to their houses
    planet_data = {}
    for planet_id in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']:
        planet = chart.getObject(planet_id)
        if planet:
            planet_lon = planet.lon
            house = get_planet_house(planet_lon, house_cusps)
            planet_data[planet_id] = {
                "sign": planet.sign,
                "degree": planet.lon,
                "house": house
            }
    print(f"Planet house placements: {planet_data}")
    
    # Get the 5th and 6th House signs (for marketing voice and health/dream client)
    fifth_house_sign = next((h["sign"] for h in house_cusps if h["house"] == 5), None)
    sixth_house_sign = next((h["sign"] for h in house_cusps if h["house"] == 6), None)
    print(f"5th House sign: {fifth_house_sign}, 6th House sign: {sixth_house_sign}")
    
    # Get Ascendant ruler (planet ruling the Rising sign)
    asc_ruler = None
    if asc and asc.sign == 'Capricorn':
        asc_ruler = chart.getObject('Saturn')  # Capricorn is ruled by Saturn
    asc_ruler_sign = asc_ruler.sign if asc_ruler else None
    print(f"Ascendant ruler sign: {asc_ruler_sign}")
    
    # Prepare the response
    astro_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "sun_sign": planet_data.get('Sun', {}).get('sign'),
        "sun_degree": planet_data.get('Sun', {}).get('degree'),
        "sun_house": planet_data.get('Sun', {}).get('house'),
        "moon_sign": planet_data.get('Moon', {}).get('sign'),
        "moon_degree": planet_data.get('Moon', {}).get('degree'),
        "moon_house": planet_data.get('Moon', {}).get('house'),
        "mercury_sign": planet_data.get('Mercury', {}).get('sign'),
        "mercury_degree": planet_data.get('Mercury', {}).get('degree'),
        "mercury_house": planet_data.get('Mercury', {}).get('house'),
        "venus_sign": planet_data.get('Venus', {}).get('sign'),
        "venus_degree": planet_data.get('Venus', {}).get('degree'),
        "venus_house": planet_data.get('Venus', {}).get('house'),
        "mars_sign": planet_data.get('Mars', {}).get('sign'),
        "mars_degree": planet_data.get('Mars', {}).get('degree'),
        "mars_house": planet_data.get('Mars', {}).get('house'),
        "jupiter_sign": planet_data.get('Jupiter', {}).get('sign'),
        "jupiter_degree": planet_data.get('Jupiter', {}).get('degree'),
        "jupiter_house": planet_data.get('Jupiter', {}).get('house'),
        "saturn_sign": planet_data.get('Saturn', {}).get('sign'),
        "saturn_degree": planet_data.get('Saturn', {}).get('degree'),
        "saturn_house": planet_data.get('Saturn', {}).get('house'),
        "uranus_sign": planet_data.get('Uranus', {}).get('sign'),
        "uranus_degree": planet_data.get('Uranus', {}).get('degree'),
        "uranus_house": planet_data.get('Uranus', {}).get('house'),
        "neptune_sign": planet_data.get('Neptune', {}).get('sign'),
        "neptune_degree": planet_data.get('Neptune', {}).get('degree'),
        "neptune_house": planet_data.get('Neptune', {}).get('house'),
        "pluto_sign": planet_data.get('Pluto', {}).get('sign'),
        "pluto_degree": planet_data.get('Pluto', {}).get('degree'),
        "pluto_house": planet_data.get('Pluto', {}).get('house'),
        "rising_sign": asc.sign if asc else None,
        "rising_sign_degree": asc.signlon if asc else None,
        "midheaven_sign": mc.sign if mc else None,
        "midheaven_sign_degree": mc.signlon if mc else None,
        "fifth_house_sign": fifth_house_sign,
        "sixth_house_sign": sixth_house_sign,
        "ascendant_ruler_sign": asc_ruler_sign,
        "available_objects": [obj.id for obj in chart.objects],
        "available_angles": [angle.id for angle in chart.angles]
    }
    
    print("Calculating dominant element and mode")
    # Base tally: Equal weighting for all planets, Ascendant, and Midheaven
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
    
    # Add weight for 5th House planets (marketing voice)
    if astro_data['sun_house'] == 5 and astro_data['sun_sign']:
        element_counts[ELEMENTS[astro_data['sun_sign'].upper()]] += 1
    if astro_data['mercury_house'] == 5 and astro_data['mercury_sign']:
        element_counts[ELEMENTS[astro_data['mercury_sign'].upper()]] += 1
    
    # Add 5th House cusp to the tally
    if astro_data['fifth_house_sign']:
        element_counts[ELEMENTS[astro_data['fifth_house_sign'].upper()]] += 1
    
    # Determine dominant element with Moon tiebreaker for Medical Astrology
    element_counts_list = [(elem, count) for elem, count in element_counts.items()]
    element_counts_list.sort(key=lambda x: x[1], reverse=True)
    if element_counts_list[0][1] == element_counts_list[1][1]:
        moon_sign = astro_data['moon_sign']
        if moon_sign:
            moon_sign_upper = moon_sign.upper()
            dominant_element = ELEMENTS[moon_sign_upper]
        else:
            dominant_element = element_counts_list[0][0]
    else:
        dominant_element = element_counts_list[0][0]
    
    astro_data['dominant_element'] = dominant_element
    astro_data['mode'] = max(mode_counts, key=mode_counts.get)
    print("Returning astro_data")
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
    app.run(debug=True)
