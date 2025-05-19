from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib import const, angle
from urllib.parse import quote
import requests
import os
from datetime import datetime, timedelta
import logging
import swisseph as swe

app = Flask(__name__)
# Set ephemeris path for Swiss Ephemeris
swe.set_ephe_path(os.path.join(os.path.dirname(__file__), 'ephe'))
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# Human Design gate boundaries
GATE_BOUNDARIES = [(i * 5.625, (i + 1) * 5.625) for i in range(64)]
LINE_BOUNDARIES = [(i * 0.9375, (i + 1) * 0.9375) for i in range(6)]
CHANNELS = {(1, 8): '1-8', (2, 14): '2-14', (3, 60): '3-60', (4, 63): '4-63', (5, 15): '5-15', (6, 59): '6-59',
            (7, 31): '7-31', (9, 52): '9-52', (10, 20): '10-20', (10, 34): '10-34', (10, 57): '10-57',
            (11, 56): '11-56', (12, 22): '12-22', (13, 33): '13-33', (16, 48): '16-48', (17, 62): '17-62',
            (18, 58): '18-58', (19, 49): '19-49', (20, 34): '20-34', (21, 45): '21-45', (23, 43): '23-43',
            (24, 61): '24-61', (25, 51): '25-51', (26, 44): '26-44', (27, 50): '27-50', (28, 38): '28-38',
            (29, 46): '29-46', (30, 41): '30-41', (32, 54): '32-54', (35, 36): '35-36', (37, 40): '37-40',
            (39, 55): '39-55', (47, 64): '47-64', (53, 42): '53-42'}
CENTER_GATES = {
    'Head': [61, 63, 64], 'Ajna': [4, 11, 17, 24, 43, 47], 'Throat': [16, 20, 23, 31, 33, 35, 45, 56, 62],
    'G': [1, 2, 7, 10, 13, 15, 25, 46], 'Heart': [21, 26, 40, 51], 'Sacral': [3, 5, 9, 14, 29, 34, 42, 59],
    'Spleen': [18, 28, 32, 44, 48, 50, 57], 'SolarPlexus': [6, 30, 36, 37, 39, 49, 55], 'Root': [38, 41, 52, 53, 54, 58, 60]
}

def decimal_to_dms(decimal):
    is_negative = decimal < 0
    decimal = abs(decimal)
    degrees = int(decimal)
    minutes_float = (decimal - degrees) * 60
    minutes = int(minutes_float)
    seconds = int((minutes_float - minutes) * 60)
    return f"{'-' if is_negative else ''}{degrees}:{minutes}:{seconds}"

def calculate_human_design(date, time, lat, lon):
    try:
        dt = datetime.strptime(f"{date.replace('/', '-')} {time}", "%Y-%m-%d %H:%M")
        jd_natal = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        design_dt = dt - timedelta(days=88)
        jd_design = swe.julday(design_dt.year, design_dt.month, design_dt.day, design_dt.hour + dt.minute/60.0)
        planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Node']
        personality_positions = {}
        design_positions = {}
        personality_gates = {}
        design_gates = {}
        for planet in planets:
            planet_id = getattr(swe, planet.upper()) if planet != 'Node' else swe.MEAN_NODE
            pos = swe.calc_ut(jd_natal, planet_id)[0]  # Get longitude
            personality_positions[planet] = pos % 360  # Ensure float for modulo
            for i, (start, end) in enumerate(GATE_BOUNDARIES):
                if start <= (pos % 360) < end:
                    gate = i + 1
                    gate_start = start
                    pos_in_gate = (pos % 360) - gate_start
                    for j, (line_start, line_end) in enumerate(LINE_BOUNDARIES):
                        if line_start <= pos_in_gate < line_end:
                            personality_gates[planet] = (gate, j + 1)
                            break
                    break
            pos = swe.calc_ut(jd_design, planet_id)[0]  # Get longitude
            design_positions[planet] = pos % 360  # Ensure float for modulo
            for i, (start, end) in enumerate(GATE_BOUNDARIES):
                if start <= (pos % 360) < end:
                    gate = i + 1
                    gate_start = start
                    pos_in_gate = (pos % 360) - gate_start
                    for j, (line_start, line_end) in enumerate(LINE_BOUNDARIES):
                        if line_start <= pos_in_gate < line_end:
                            design_gates[planet] = (gate, j + 1)
                            break
                    break
        all_gates = set([gate for gate, _ in personality_gates.values()] + [gate for gate, _ in design_gates.values()])
        centers = {center: any(gate in all_gates for gate in gates) for center, gates in CENTER_GATES.items()}
        channels = [f"{g1}-{g2}" for (g1, g2), _ in CHANNELS.items() if g1 in all_gates and g2 in all_gates]
        type_ = 'Manifesting Generator' if centers['Sacral'] and centers['Throat'] else 'Generator' if centers['Sacral'] else 'Manifestor' if centers['Throat'] or centers['Heart'] or centers['G'] else 'Projector'
        strategy = 'To Respond' if centers['Sacral'] else 'To Initiate' if centers['Throat'] or centers['Heart'] or centers['G'] else 'To Wait for Invitation'
        authority = 'Emotional - Solar Plexus' if centers['SolarPlexus'] else 'Sacral' if centers['Sacral'] and not centers['SolarPlexus'] else 'Splenic' if centers['Spleen'] and not (centers['SolarPlexus'] or centers['Sacral']) else 'None'
        sun_gate, sun_line = personality_gates.get('Sun', (1, 1))
        earth_gate, earth_line = personality_gates.get('Node', (1, 1))
        profile = f"{sun_line}/{earth_line}"
        incarnation_cross = f"Left Angle Cross of Dedication ({sun_gate}/{earth_gate})" if sun_gate == 23 else "Right Angle Cross of Planning"
        digestion = 'Nervous' if 32 in all_gates else 'Calm'
        motivation = 'Desire' if 30 in all_gates else 'Hope'
        perspective = 'Personal' if 10 in all_gates else 'Collective'
        environment = 'Mountains' if 15 in all_gates else 'Valleys'
        return {
            'type': type_, 'strategy': strategy, 'authority': authority, 'definition': 'Single Definition' if len(channels) <= 2 else 'Split Definition',
            'profile': profile, 'incarnation_cross': incarnation_cross, 'signature': 'Satisfaction' if centers['Sacral'] else 'Peace' if centers['Throat'] or centers['Heart'] or centers['G'] else 'Success',
            'not_self_theme': 'Frustration' if centers['Sacral'] else 'Anger' if centers['Throat'] or centers['Heart'] or centers['G'] else 'Bitterness',
            'digestion': digestion, 'motivation': motivation, 'perspective': perspective, 'environment': environment, 'gates': list(all_gates), 'channels': channels
        }
    except Exception as e:
        logger.error(f"Human Design calculation failed: {str(e)}")
        return None

@app.route('/v1/humandesign/profile', methods=['GET'])
def get_profile():
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    try:
        response = requests.get(geo_url)
        geo_data = response.json()
        if not geo_data.get('results'):
            return jsonify({"error": "Location not found. Please include city, state, country."}), 400
        lat = geo_data['results'][0]['geometry']['location']['lat']
        lon = geo_data['results'][0]['geometry']['location']['lng']
        lat_dms = decimal_to_dms(lat)
        lon_dms = decimal_to_dms(lon)
    except Exception as e:
        return jsonify({"error": f"Geocoding failed: {str(e)}"}), 500
    hd_data = calculate_human_design(date, time, lat, lon)
    if hd_data:
        hd_data.update({'name': name, 'date': date, 'time': time, 'location': location})
        return jsonify(hd_data)
    return jsonify({"error": "Human Design calculation failed"}), 500

@app.route('/v1/astrology/chart', methods=['GET'])
def get_astrology_chart():
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    try:
        response = requests.get(geo_url)
        geo_data = response.json()
        if not geo_data.get('results'):
            return jsonify({"error": "Location not found. Please include city, state, country."}), 400
        lat = geo_data['results'][0]['geometry']['location']['lat']
        lon = geo_data['results'][0]['geometry']['location']['lng']
        lat_dms = decimal_to_dms(lat)
        lon_dms = decimal_to_dms(lon)
        pos = GeoPos(lat_dms, lon_dms)
    except Exception as e:
        return jsonify({"error": f"Geocoding failed: {str(e)}"}), 500
    dt = Datetime(date, time, '+10:00')  # AEST offset
    chart = Chart(dt, pos, hsys=const.HOUSES_PLACIDUS, IDs=['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'MeanNode', 'Lilith'])
    asc = chart.getAngle('Asc')
    mc = chart.getAngle('MC')
    house_cusps = [{'house': i, 'sign': chart.houses.content[f'House{i}'].sign, 'degree': chart.houses.content[f'House{i}'].lon} for i in range(1, 13)]
    def get_planet_house(planet_lon):
        for i in range(len(house_cusps)):
            start_lon = house_cusps[i]['degree']
            end_lon = house_cusps[(i + 1) % len(house_cusps)]['degree']
            if end_lon < start_lon:
                if planet_lon >= start_lon or planet_lon < end_lon:
                    return house_cusps[i]['house']
            else:
                if start_lon <= planet_lon < end_lon:
                    return house_cusps[i]['house']
        return None
    planet_data = {pid: {'sign': chart.getObject(pid).sign, 'degree': chart.getObject(pid).lon, 'house': get_planet_house(chart.getObject(pid).lon)} for pid in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'MeanNode', 'Lilith'] if chart.getObject(pid)}
    placements = [planet_data.get(pid, {}).get('sign') for pid in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'MeanNode', 'Lilith'] if planet_data.get(pid)] + [asc.sign if asc else None, mc.sign if mc else None]
    element_counts = {elem: sum(1 for sign in placements if sign and ELEMENTS.get(sign.upper()) == elem) for elem in ['Fire', 'Earth', 'Air', 'Water']}
    mode_counts = {mode: sum(1 for sign in placements if sign and MODES.get(sign.upper()) == mode) for mode in ['Cardinal', 'Fixed', 'Mutable']}
    dominant_element = max(element_counts, key=element_counts.get) if element_counts else 'Unknown'
    mode = max(mode_counts, key=mode_counts.get) if mode_counts else 'Unknown'
    fifth_house = next((h['sign'] for h in house_cusps if h['house'] == 5), None)
    sixth_house = next((h['sign'] for h in house_cusps if h['house'] == 6), None)
    return jsonify({
        'name': name, 'date': date, 'time': time, 'location': location,
        'sun_sign': planet_data.get('Sun', {}).get('sign'), 'moon_sign': planet_data.get('Moon', {}).get('sign'),
        'rising_sign': asc.sign if asc else None, 'dominant_element': dominant_element, 'mode': mode,
        'chiron': planet_data.get('Chiron', {}).get('sign'), 'lilith': planet_data.get('Lilith', {}).get('sign'),
        'sixth_house': sixth_house, 'fifth_house': fifth_house
    })

@app.route('/v1/moonphase', methods=['GET'])
def get_moon_phase():
    date = request.args.get('date')
    range_query = request.args.get('range', 'single')
    dates = [date] if range_query == 'single' else [(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=i*7)).strftime('%Y-%m-%d') for i in range(6)]
    moon_phases = []
    for d in dates:
        dt = Datetime(d.replace('-', '/'), '00:00', '+00:00')
        pos = GeoPos('0:0:0', '0:0:0')
        chart = Chart(dt, pos, IDs=['Sun', 'Moon'])
        sun_lon = chart.getObject('Sun').lon
        moon_lon = chart.getObject('Moon').lon
        dist = angle.distance(sun_lon, moon_lon)
        phase = "New Moon" if 0 <= dist <= 45 else "Waxing Crescent" if 45 < dist <= 90 else "First Quarter" if 90 < dist <= 135 else "Waxing Gibbous" if 135 < dist <= 180 else "Full Moon" if 180 <= dist <= 225 else "Waning Gibbous" if 225 < dist <= 270 else "Last Quarter" if 270 < dist <= 315 else "Waning Crescent"
        tcm_energy = "Rest & Renewal" if phase == "New Moon" else "Growth & Building" if phase in ["Waxing Crescent", "First Quarter"] else "Expansion & Harvest" if phase in ["Waxing Gibbous", "Full Moon"] else "Release & Cleansing" if phase in ["Waning Gibbous", "Last Quarter"] else "Deep Rest"
        moon_phases.append({'date': d, 'moon_phase': phase, 'angular_distance': dist, 'tcm_energy': tcm_energy})
    return jsonify(moon_phases if range_query == '6week' else moon_phases[0])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
