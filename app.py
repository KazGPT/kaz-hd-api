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
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure logging
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

# Human Design gate boundaries (degrees for 64 gates)
GATE_BOUNDARIES = [(i * 5.625, (i + 1) * 5.625) for i in range(64)]

# Line boundaries within each gate (degrees for lines 1-6)
LINE_BOUNDARIES = [(i * 0.9375, (i + 1) * 0.9375) for i in range(6)]  # 5.625/6 = 0.9375 degrees per line

# Full list of Human Design channels
CHANNELS = {
    (1, 8): '1-8 (Inspiration)', (2, 14): '2-14 (Keeper of Keys)', (3, 60): '3-60 (Mutation)',
    (4, 63): '4-63 (Logic)', (5, 15): '5-15 (Rhythm)', (6, 59): '6-59 (Intimacy)',
    (7, 31): '7-31 (Leadership)', (9, 52): '9-52 (Concentration)', (10, 20): '10-20 (Awakening)',
    (10, 34): '10-34 (Exploration)', (10, 57): '10-57 (Perfected Form)', (11, 56): '11-56 (Curiosity)',
    (12, 22): '12-22 (Openness)', (13, 33): '13-33 (Witness)', (15, 5): '15-5 (Rhythm)',  # Duplicate for clarity
    (16, 48): '16-48 (Talent)', (17, 62): '17-62 (Opinion)', (18, 58): '18-58 (Judgment)',
    (19, 49): '19-49 (Synthesis)', (20, 34): '20-34 (Charisma)', (20, 57): '20-57 (Awakening)',
    (21, 45): '21-45 (Money Line)', (23, 43): '23-43 (Structuring)', (24, 61): '24-61 (Awareness)',
    (25, 51): '25-51 (Initiation)', (26, 44): '26-44 (Surrender)', (27, 50): '27-50 (Preservation)',
    (28, 38): '28-38 (Struggle)', (29, 46): '29-46 (Discovery)', (30, 41): '30-41 (Recognition)',
    (32, 54): '32-54 (Transformation)', (35, 36): '35-36 (Transitoriness)', (37, 40): '37-40 (Community)',
    (39, 55): '39-55 (Emoting)', (47, 64): '47-64 (Abstraction)', (53, 42): '53-42 (Cycles)'
}

# Center connections (gates that define each center)
CENTER_GATES = {
    'Head': [61, 63, 64], 'Ajna': [4, 11, 17, 24, 43, 47], 'Throat': [16, 20, 23, 31, 33, 35, 45, 56, 62],
    'G': [1, 2, 7, 10, 13, 15, 25, 46], 'Heart': [21, 26, 40, 51], 'Sacral': [3, 5, 9, 14, 29, 34, 42, 59],
    'Spleen': [18, 28, 32, 44, 48, 50, 57], 'SolarPlexus': [6, 30, 36, 37, 39, 49, 55], 'Root': [38, 41, 52, 53, 54, 58, 60]
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

# Full Human Design calculation
def calculate_human_design(date, time, lat, lon):
    try:
        # Parse birth date and time
        dt = datetime.strptime(f"{date.replace('/', '-')} {time}", "%Y-%m-%d %I:%M %p")
        jd_natal = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        
        # Calculate design date (~88 days prior)
        design_dt = dt - timedelta(days=88)
        jd_design = swe.julday(design_dt.year, design_dt.month, design_dt.day, design_dt.hour + design_dt.minute/60.0)
        
        # Planets for Personality (natal) and Design
        planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Node']
        personality_positions = {}
        design_positions = {}
        personality_gates = {}
        design_gates = {}
        
        # Calculate planetary positions and gates
        for planet in planets:
            planet_id = getattr(swe, planet.upper()) if planet != 'Node' else swe.MEAN_NODE
            # Personality (natal)
            pos = swe.calc_ut(jd_natal, planet_id)[0] % 360
            personality_positions[planet] = pos
            for i, (start, end) in enumerate(GATE_BOUNDARIES):
                if start <= pos < end:
                    gate = i + 1
                    # Calculate line (1-6) within the gate
                    gate_start = start
                    pos_in_gate = pos - gate_start
                    for j, (line_start, line_end) in enumerate(LINE_BOUNDARIES):
                        if line_start <= pos_in_gate < line_end:
                            personality_gates[planet] = (gate, j + 1)
                            break
                    break
            # Design
            pos = swe.calc_ut(jd_design, planet_id)[0] % 360
            design_positions[planet] = pos
            for i, (start, end) in enumerate(GATE_BOUNDARIES):
                if start <= pos < end:
                    gate = i + 1
                    gate_start = start
                    pos_in_gate = pos - gate_start
                    for j, (line_start, line_end) in enumerate(LINE_BOUNDARIES):
                        if line_start <= pos_in_gate < line_end:
                            design_gates[planet] = (gate, j + 1)
                            break
                    break
        
        # Combine gates (without lines for uniqueness)
        all_gates = set([gate for gate, line in personality_gates.values()] + [gate for gate, line in design_gates.values()])
        
        # Calculate centers
        centers = {
            'Head': False, 'Ajna': False, 'Throat': False, 'G': False, 'Heart': False,
            'Sacral': False, 'Spleen': False, 'SolarPlexus': False, 'Root': False
        }
        for center, gates in CENTER_GATES.items():
            if any(gate in all_gates for gate in gates):
                centers[center] = True
        
        # Calculate channels
        channels = []
        for (gate1, gate2), channel_name in CHANNELS.items():
            if gate1 in all_gates and gate2 in all_gates:
                channels.append(channel_name)
        
        # Determine Type, Signature, Not-Self Theme
        if centers['Sacral'] and centers['Throat']:
            type_ = 'Manifesting Generator'
            strategy = 'To Respond'
            signature = 'Satisfaction'
            not_self = 'Frustration'
        elif centers['Sacral']:
            type_ = 'Generator'
            strategy = 'To Respond'
            signature = 'Satisfaction'
            not_self = 'Frustration'
        elif centers['Throat'] or centers['Heart'] or centers['G']:
            type_ = 'Manifestor'
            strategy = 'To Initiate'
            signature = 'Peace'
            not_self = 'Anger'
        elif not any(centers.values()):
            type_ = 'Reflector'
            strategy = 'To Wait a Lunar Cycle'
            signature = 'Surprise'
            not_self = 'Disappointment'
        else:
            type_ = 'Projector'
            strategy = 'To Wait for Invitation'
            signature = 'Success'
            not_self = 'Bitterness'
        
        # Determine Authority
        if centers['SolarPlexus']:
            authority = 'Emotional - Solar Plexus'
        elif centers['Sacral'] and not centers['SolarPlexus']:
            authority = 'Sacral'
        elif centers['Spleen'] and not (centers['SolarPlexus'] or centers['Sacral']):
            authority = 'Splenic'
        elif centers['Heart'] and not (centers['SolarPlexus'] or centers['Sacral'] or centers['Spleen']):
            authority = 'Ego'
        elif centers['G'] and not (centers['SolarPlexus'] or centers['Sacral'] or centers['Spleen'] or centers['Heart']):
            authority = 'Self-Projected'
        elif type_ == 'Reflector':
            authority = 'Lunar'
        else:
            authority = 'None'
        
        # Profile (Sun/Earth lines)
        sun_gate, sun_line = personality_gates.get('Sun', (1, 1))
        earth_gate, earth_line = personality_gates.get('Node', (1, 1))  # Approximate Earth via Node
        profile = f"{sun_line}/{earth_line}"
        
        # Incarnation Cross (Sun/Earth gates with lines)
        cross = f"Left Angle Cross of Dedication ({sun_gate}.{sun_line}/{earth_gate}.{earth_line})" if sun_gate == 23 else "Right Angle Cross of Planning"
        
        # Definition (based on channel connections)
        definition = 'Single Definition' if len(channels) <= 2 else 'Split Definition'
        
        # Design Sense (approximated via Ajna gates)
        design_sense = 'Inner Vision' if any(gate in CENTER_GATES['Ajna'] for gate in all_gates) else 'Outer Vision'
        
        # Digestion, Motivation, Perspective, Environment (simplified)
        digestion = 'Nervous' if 32 in all_gates else 'Calm'
        motivation = 'Desire' if 30 in all_gates else 'Hope'
        perspective = 'Personal' if 10 in all_gates else 'Collective'
        environment = 'Mountains' if 15 in all_gates else 'Valleys'
        
        return {
            'type': type_,
            'strategy': strategy,
            'authority': authority,
            'signature': signature,
            'not_self_theme': not_self,
            'centers': centers,
            'gates': list(all_gates),
            'channels': channels,
            'profile': profile,
            'incarnation_cross': cross,
            'definition': definition,
            'design_sense': design_sense,
            'motivation': motivation,
            'perspective': perspective,
            'environment': environment
        }
    except Exception as e:
        logger.error(f"Human Design calculation failed: {str(e)}")
        return None

# Astrology-related endpoints
@app.route('/astrology/chart', methods=['GET'])
def get_astrology_chart():
    logger.info("Starting /astrology/chart endpoint")
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    logger.info(f"Received inputs: name={name}, date={date}, time={time}, location={location}")
    
    try:
        time_24hr = datetime.strptime(time.strip(), "%I:%M %p").strftime("%H:%M")
        logger.info(f"Converted time to 24hr format: {time_24hr}")
    except ValueError as e:
        logger.error(f"Time conversion error: {str(e)}")
        return jsonify({"error": "Invalid time format. Please use HH:MM AM/PM."}), 400
    
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    try:
        response = requests.get(geo_url)
        geo_data = response.json()
        if not geo_data.get('results'):
            logger.error("Geocoding failed: Location not found")
            return jsonify({"error": "Location not found. Please include city, state, country."}), 400
        lat = geo_data['results'][0]['geometry']['location']['lat']
        lon = geo_data['results'][0]['geometry']['location']['lng']
        lat_dms = decimal_to_dms(lat)
        lon_dms = decimal_to_dms(lon)
        logger.info(f"Geocoded location: lat={lat}, lon={lon}, lat_dms={lat_dms}, lon_dms={lon_dms}")
    except Exception as e:
        logger.error(f"Geocoding failed: {str(e)}")
        return jsonify({"error": f"Geocoding failed: {str(e)}"}), 500
    
    try:
        pos = GeoPos(lat_dms, lon_dms)
        logger.info("GeoPos created successfully")
    except Exception as e:
        logger.error(f"GeoPos creation failed: {str(e)}")
        return jsonify({"error": f"GeoPos creation failed: {str(e)}"}), 400
    
    dt = Datetime(date, time_24hr, '+10:00')  # AEST offset
    logger.info(f"Datetime created: {date} {time_24hr} +10:00")
    
    try:
        chart = Chart(dt, pos, hsys=const.HOUSES_PLACIDUS, IDs=['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'MeanNode', 'TrueNode', 'Lilith'])
        logger.info("Chart created successfully")
    except Exception as e:
        logger.error(f"Chart creation failed: {str(e)}")
        return jsonify({"error": f"Chart creation failed: {str(e)}"}), 500

    available_objects = [obj.id for obj in chart.objects]
    available_angles = [angle.id for angle in chart.angles]
    logger.info(f"Available objects: {available_objects}, angles: {available_angles}")
    
    # Get Ascendant and Midheaven
    asc = chart.getAngle('Asc')
    mc = chart.getAngle('MC')
    
    # Determine Ascendant ruler
    ruler_map = {
        'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury', 'Cancer': 'Moon',
        'Leo': 'Sun', 'Virgo': 'Mercury', 'Libra': 'Venus', 'Scorpio': 'Pluto',
        'Sagittarius': 'Jupiter', 'Capricorn': 'Saturn', 'Aquarius': 'Uranus', 'Pisces': 'Neptune'
    }
    asc_ruler = chart.getObject(ruler_map.get(asc.sign, 'Sun')) if asc else None
    asc_ruler_sign = asc_ruler.sign if asc_ruler else None
    
    # Get house cusps
    houses = chart.houses
    house_cusps = []
    try:
        for i in range(1, 13):
            house_key = f'House{i}'
            house = houses.content[house_key]
            house_cusps.append({
                "house": i,
                "sign": house.sign,
                "degree": house.lon
            })
        logger.info(f"House cusps: {house_cusps}")
    except Exception as e:
        logger.error(f"Failed to retrieve house cusps: {str(e)}")
        return jsonify({"error": f"Failed to retrieve house cusps: {str(e)}"}), 500
    
    # Function to determine planet's house
    def get_planet_house(planet_lon, house_cusps):
        for i in range(len(house_cusps)):
            start_lon = house_cusps[i]["degree"]
            end_lon = house_cusps[(i + 1) % len(house_cusps)]["degree"]
            if end_lon < start_lon:
                if planet_lon >= start_lon or planet_lon < end_lon:
                    return house_cusps[i]["house"]
            else:
                if start_lon <= planet_lon < end_lon:
                    return house_cusps[i]["house"]
        return None
    
    # Assign planets to houses
    planet_data = {}
    for planet_id in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'MeanNode', 'TrueNode', 'Lilith']:
        planet = chart.getObject(planet_id)
        if planet:
            planet_lon = planet.lon
            house = get_planet_house(planet_lon, house_cusps)
            planet_data[planet_id] = {
                "sign": planet.sign,
                "degree": planet.lon,
                "house": house
            }
    
    # Calculate aspects (simplified: conjunction, trine, square, opposition)
    aspects = []
    planet_lons = {pid: data['degree'] for pid, data in planet_data.items()}
    for p1 in planet_data.keys():
        for p2 in planet_data.keys():
            if p1 >= p2:
                continue
            dist = angle.distance(planet_lons[p1], planet_lons[p2])
            if 0 <= dist <= 10:
                aspects.append(f"{p1} conjunction {p2}")
            elif 110 <= dist <= 130:
                aspects.append(f"{p1} trine {p2}")
            elif 80 <= dist <= 100:
                aspects.append(f"{p1} square {p2}")
            elif 170 <= dist <= 190:
                aspects.append(f"{p1} opposition {p2}")
    
    # Calculate Syzygy (prior New/Full Moon)
    syzygy_date = dt.date
    syzygy_phase = "Unknown"
    days_back = 0
    while days_back < 29.5:  # Lunar cycle length
        test_date = dt.date - timedelta(days=days_back)
        test_dt = Datetime(str(test_date), '00:00', '+00:00')
        test_pos = GeoPos('0:0:0', '0:0:0')
        test_chart = Chart(test_dt, test_pos, IDs=['Sun', 'Moon'])
        sun_lon = test_chart.getObject('Sun').lon
        moon_lon = test_chart.getObject('Moon').lon
        dist = angle.distance(sun_lon, moon_lon)
        if 0 <= dist <= 10 or 350 <= dist <= 360:
            syzygy_date = test_date
            syzygy_phase = "New Moon"
            break
        elif 170 <= dist <= 190:
            syzygy_date = test_date
            syzygy_phase = "Full Moon"
            break
        days_back += 1
    
    # Calculate Part of Fortune (simplified)
    sun_lon = planet_data.get('Sun', {}).get('degree', 0)
    moon_lon = planet_data.get('Moon', {}).get('degree', 0)
    asc_lon = asc.lon if asc else 0
    fortune_lon = (sun_lon - moon_lon + asc_lon) % 360
    fortune_sign = next(sign for sign, (start, end) in const.SIGN_ARIES.items() if start <= fortune_lon < end)
    fortune_house = get_planet_house(fortune_lon, house_cusps)
    
    # Calculate Vertex (simplified, approximated)
    vertex_lon = (asc_lon + 180) % 360  # Opposite Ascendant
    vertex_sign = next(sign for sign, (start, end) in const.SIGN_ARIES.items() if start <= vertex_lon < end)
    vertex_house = get_planet_house(vertex_lon, house_cusps)
    
    # Get 5th and 6th House signs
    fifth_house_sign = next((h["sign"] for h in house_cusps if h["house"] == 5), None)
    sixth_house_sign = next((h["sign"] for h in house_cusps if h["house"] == 6), None)
    
    # Calculate dominant element and mode
    placements = [
        planet_data.get('Sun', {}).get('sign'),
        planet_data.get('Moon', {}).get('sign'),
        planet_data.get('Mercury', {}).get('sign'),
        planet_data.get('Venus', {}).get('sign'),
        planet_data.get('Mars', {}).get('sign'),
        planet_data.get('Jupiter', {}).get('sign'),
        planet_data.get('Saturn', {}).get('sign'),
        planet_data.get('Uranus', {}).get('sign'),
        planet_data.get('Neptune', {}).get('sign'),
        planet_data.get('Pluto', {}).get('sign'),
        asc.sign if asc else None,
        mc.sign if mc else None,
        planet_data.get('MeanNode', {}).get('sign'),
        planet_data.get('TrueNode', {}).get('sign'),
        planet_data.get('Lilith', {}).get('sign'),
        planet_data.get('Chiron', {}).get('sign'),
        syzygy_phase  # Include Syzygy sign
    ]
    element_counts = {'Fire': 0, 'Earth': 0, 'Air': 0, 'Water': 0}
    mode_counts = {'Cardinal': 0, 'Fixed': 0, 'Mutable': 0}
    for sign in placements:
        if sign and sign in ELEMENTS:
            sign_upper = sign.upper()
            element_counts[ELEMENTS[sign_upper]] += 1
            mode_counts[MODES[sign_upper]] += 1
    
    # Weight 6th house planets
    for planet, data in planet_data.items():
        if data.get('house') == 6 and data.get('sign'):
            element_counts[ELEMENTS[data['sign'].upper()]] += 1
    
    # Weight 6th house cusp
    if sixth_house_sign:
        element_counts[ELEMENTS[sixth_house_sign.upper()]] += 1
    
    # Determine dominant element with Moon tiebreaker
    element_counts_list = [(elem, count) for elem, count in element_counts.items()]
    element_counts_list.sort(key=lambda x: x[1], reverse=True)
    dominant_element = element_counts_list[0][0]
    if element_counts_list[0][1] == element_counts_list[1][1]:
        moon_sign = planet_data.get('Moon', {}).get('sign')
        dominant_element = ELEMENTS[moon_sign.upper()] if moon_sign else dominant_element
    
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
        "ascendant_ruler_sign": asc_ruler_sign,
        "fifth_house_sign": fifth_house_sign,
        "sixth_house_sign": sixth_house_sign,
        "dominant_element": dominant_element,
        "mode": max(mode_counts, key=mode_counts.get),
        "lilith_sign": planet_data.get('Lilith', {}).get('sign'),
        "lilith_degree": planet_data.get('Lilith', {}).get('degree'),
        "lilith_house": planet_data.get('Lilith', {}).get('house'),
        "chiron_sign": planet_data.get('Chiron', {}).get('sign'),
        "chiron_degree": planet_data.get('Chiron', {}).get('degree'),
        "chiron_house": planet_data.get('Chiron', {}).get('house'),
        "syzygy_date": str(syzygy_date),
        "syzygy_phase": syzygy_phase,
        "north_node_sign": planet_data.get('TrueNode', {}).get('sign'),
        "north_node_degree": planet_data.get('TrueNode', {}).get('degree'),
        "north_node_house": planet_data.get('TrueNode', {}).get('house'),
        "part_of_fortune_sign": fortune_sign,
        "part_of_fortune_house": fortune_house,
        "vertex_sign": vertex_sign,
        "vertex_house": vertex_house,
        "aspects": aspects,
        "available_objects": available_objects,
        "available_angles": available_angles
    }
    
    logger.info("Returning astro_data")
    return jsonify(astro_data)

@app.route('/moonphase', methods=['GET'])
def get_moon_phase():
    logger.info("Starting /moonphase endpoint")
    start_date = request.args.get('date')
    range_query = request.args.get('range', 'single')  # 'single' or '6week'
    
    try:
        dates = [start_date]
        if range_query == '6week':
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            dates = [(start_dt + timedelta(days=d)).strftime('%Y-%m-%d') for d in [0, 7, 14, 21, 28, 35]]
        
        moon_phases = []
        for date in dates:
            dt = Datetime(date.replace('-', '/'), '00:00', '+00:00')
            pos = GeoPos('0:0:0', '0:0:0')
            chart = Chart(dt, pos, IDs=['Sun', 'Moon'])
            sun_lon = chart.getObject('Sun').lon
            moon_lon = chart.getObject('Moon').lon
            dist = angle.distance(sun_lon, moon_lon)
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
            moon_phases.append({
                "date": date,
                "moon_phase": phase,
                "angular_distance": dist
            })
        logger.info(f"Moon phases calculated: {moon_phases}")
        return jsonify(moon_phases if range_query == '6week' else moon_phases[0])
    except Exception as e:
        logger.error(f"Moon phase calculation failed: {str(e)}")
        return jsonify({"error": f"Moon phase calculation failed: {str(e)}"}), 500

@app.route('/humandesign/profile', methods=['GET'])
def get_profile():
    logger.info("Starting /humandesign/profile endpoint")
    name = request.args.get('name')
    date = request.args.get('date').replace('-', '/')
    time = request.args.get('time')
    location = request.args.get('location')
    
    # Geocode location
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    try:
        response = requests.get(geo_url)
        geo_data = response.json()
        if not geo_data.get('results'):
            logger.error("Geocoding failed: Location not found")
            return jsonify({"error": "Location not found. Please include city, state, country."}), 400
        lat = geo_data['results'][0]['geometry']['location']['lat']
        lon = geo_data['results'][0]['geometry']['location']['lng']
        logger.info(f"Geocoded location: lat={lat}, lon={lon}")
    except Exception as e:
        logger.error(f"Geocoding failed: {str(e)}")
        return jsonify({"error": f"Geocoding failed: {str(e)}"}), 500
    
    # Calculate Human Design
    hd_data = calculate_human_design(date, time, lat, lon)
    if not hd_data:
        logger.error("Human Design calculation failed")
        return jsonify({"error": "Failed to calculate Human Design profile"}), 500
    
    hd_data.update({
        "name": name,
        "date": date,
        "time": time,
        "location": location
    })
    logger.info(f"Returning HD data: {hd_data}")
    return jsonify(hd_data)

@app.route('/cycle/plan', methods=['GET'])
def get_cycle_plan():
    logger.info("Starting /cycle/plan endpoint")
    name = request.args.get('name')
    start_date = request.args.get('start_date')  # Programme start date
    cycle_type = request.args.get('cycle_type')  # regular, irregular, none
    symptoms = request.args.get('symptoms', '')  # e.g., "fatigue, anxiety"
    birth_date = request.args.get('birth_date').replace('-', '/')
    birth_time = request.args.get('birth_time')
    birth_location = request.args.get('birth_location')
    
    # Validate inputs
    if not all([name, start_date, cycle_type, birth_date, birth_time, birth_location]):
        logger.error("Missing required parameters")
        return jsonify({"error": "Missing required parameters: name, start_date, cycle_type, birth_date, birth_time, birth_location"}), 400
    
    # Fetch API data
    try:
        # Fetch 6-week moon phase range
        moon_response = requests.get(f"https://kaz-hd-api.onrender.com/moonphase?date={start_date}&range=6week")
        moon_data = moon_response.json()
        if isinstance(moon_data, dict) and 'error' in moon_data:
            logger.error(f"Moon phase fetch failed: {moon_data['error']}")
            return jsonify({"error": f"Moon phase fetch failed: {moon_data['error']}"}), 500
        
        hd_response = requests.get(f"https://kaz-hd-api.onrender.com/humandesign/profile?name={name}&date={birth_date}&time={birth_time}&location={birth_location}")
        hd_data = hd_response.json()
        if 'error' in hd_data:
            logger.error(f"HD fetch failed: {hd_data['error']}")
            return jsonify({"error": f"HD fetch failed: {hd_data['error']}"}), 500
        
        astro_response = requests.get(f"https://kaz-hd-api.onrender.com/astrology/chart?name={name}&date={birth_date}&time={birth_time}&location={birth_location}")
        astro_data = astro_response.json()
        if 'error' in astro_data:
            logger.error(f"Astro fetch failed: {astro_data['error']}")
            return jsonify({"error": f"Astro fetch failed: {astro_data['error']}"}), 500
    except Exception as e:
        logger.error(f"API fetch failed: {str(e)}")
        return jsonify({"error": f"API fetch failed: {str(e)}"}), 500
    
    # Generate 6-week plan
    themes = ['Grounding', 'Nourish', 'Ignite', 'Calm', 'Empower', 'Celebrate']
    cycle_plan = []
    
    for week, (theme, moon_phase_data) in enumerate(zip(themes, moon_data), 1):
        moon_phase = moon_phase_data['moon_phase']
        
        # Base practices per theme and lunar phase
        breathwork = "4-7-8 breathwork"
        nutrition = "Mindful eating: quinoa salad, fork in lap"
        movement = "Gentle yoga, 10 min"
        eft_ritual = f"Tap 'I am cradled in my {theme}' for 3 min"
        clean_living = "Sip 2L filtered water, use RAWW cleanser"
        ritual = "Journal with intention"
        
        # Adjust based on theme and lunar phase
        if theme == 'Grounding':
            if moon_phase == 'New Moon':
                ritual = "Set intentions with Cedarwood diffusion (doTERRA, [Insert doTERRA link])"
            elif moon_phase == 'Waxing Crescent':
                breathwork = "Start meditation with Lavender diffusion (doTERRA, [Insert doTERRA link])"
        elif theme == 'Nourish':
            if moon_phase == 'Waxing Moon':
                nutrition = "Mindful eating: quinoa salad near water"
                ritual = "Gratitude journal under Waxing Moon’s glow"
        elif theme == 'Ignite':
            if moon_phase == 'Full Moon':
                ritual = "Journal passion goals with Clary Sage diffusion (doTERRA, [Insert doTERRA link])"
                movement = "Dance freely, 15 min"
        elif theme == 'Calm':
            if moon_phase == 'Waning Moon':
                breathwork = "Rhythmic breathwork for release"
                eft_ritual = f"Tap 'I release with ease' for 3 min"
        elif theme == 'Empower':
            if moon_phase == 'Full Moon':
                ritual = "Share wellness wisdom with Full Moon’s glow"
                eft_ritual = f"Tap 'I shine with my purpose' for 3 min"
        elif theme == 'Celebrate':
            if moon_phase == 'New Moon':
                ritual = "Set long-term intentions with Cedarwood diffusion (doTERRA, [Insert doTERRA link])"
                eft_ritual = f"Tap 'I celebrate my journey' for 3 min"
        
        # Personalize with HD and Astro
        hd_type = hd_data.get('type', '')
        authority = hd_data.get('authority', '')
        gates = hd_data.get('gates', [])
        channels = hd_data.get('channels', [])
        environment = hd_data.get('environment', '')
        moon_sign = astro_data.get('moon_sign', '')
        lilith_sign = astro_data.get('lilith_sign', '')
        aspects = astro_data.get('aspects', [])
        
        if hd_type in ["Generator", "Manifesting Generator"]:
            movement += "; add dynamic flow to avoid frustration"
        if authority == "Emotional - Solar Plexus":
            eft_ritual += "; journal 'What am I feeling?' for clarity"
        if 5 in gates:
            breathwork = "Rhythmic 4-7-8 breathwork to honour Gate 5"
        if '43-23' in channels and theme == 'Empower':
            ritual += "; write and share your insights"
        if environment == 'Mountains':
            breathwork += f" in a {environment} space"
        
        if moon_sign == 'Cancer':
            nutrition += "; nurture with water-based rituals"
        if lilith_sign == 'Pisces' and theme in ['Calm', 'Empower']:
            ritual += "; creative release with art journaling"
        if 'Moon trine Neptune' in aspects and theme == 'Calm':
            clean_living += "; dreamy Lavender diffusion (doTERRA, [Insert doTERRA link])"
        
        # Adjust for symptoms
        if "fatigue" in symptoms.lower():
            movement = "Restorative yoga, 10 min"
            clean_living += "; rest with lavender oil (doTERRA, [Insert doTERRA link])"
        if "anxiety" in symptoms.lower():
            eft_ritual += "; tap 'I soften into ease' for 3 min"
        
        plan = {
            "week": week,
            "theme": theme,
            "moon_phase": moon_phase,
            "breathwork": breathwork,
            "nutrition": nutrition,
            "movement": movement,
            "eft_ritual": eft_ritual,
            "clean_living": clean_living,
            "ritual": ritual,
            "tracker": f"Reflect: How does your {moon_sign} feel in {theme}? Honour your {hd_type} energy.",
            "community": f"Join a Kaz workshop ([Insert booking link]) for {theme} wisdom"
        }
        cycle_plan.append(plan)
    
    logger.info(f"Generated 6-week cycle plan: {cycle_plan}")
    return jsonify({
        "name": name,
        "cycle_plan": cycle_plan
    })

if __name__ == '__main__':
    app.run(debug=True)
