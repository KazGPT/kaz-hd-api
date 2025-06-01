from flask import Flask, request, jsonify
from urllib.parse import quote
import requests
import os
from datetime import datetime, timedelta
import logging
import swisseph as swe
import math

app = Flask(__name__)

# Set absolute ephemeris path for Render
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
EPHE_PATH = os.path.join(BASE_DIR, 'ephe')

# Try to set ephemeris path, but don't fail if it doesn't exist
try:
    if os.path.exists(EPHE_PATH):
        swe.set_ephe_path(EPHE_PATH)
    else:
        # Use built-in ephemeris
        swe.set_ephe_path("")
except Exception as e:
    logging.warning(f"Could not set ephemeris path: {e}")
    swe.set_ephe_path("")

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Zodiac Elements and Modes (Tropical Zodiac)
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

# Human Design Centers and their associated gates
CENTER_GATES = {
    'Head': [61, 63, 64],
    'Ajna': [4, 11, 17, 24, 43, 47],
    'Throat': [16, 20, 23, 31, 33, 35, 45, 56, 62],
    'G': [1, 2, 7, 10, 13, 15, 25, 46],
    'Heart': [21, 26, 40, 51],
    'Sacral': [3, 5, 9, 14, 29, 34, 42, 59],
    'Spleen': [18, 28, 32, 44, 48, 50, 57],
    'SolarPlexus': [6, 30, 36, 37, 39, 49, 55],
    'Root': [38, 41, 52, 53, 54, 58, 60]
}

# Human Design Channels (simplified selection)
CHANNELS = {
    (1, 8): 'Inspiration', (2, 14): 'The Beat', (3, 60): 'Mutation',
    (4, 63): 'Logic', (5, 15): 'Rhythm', (6, 59): 'Mating',
    (7, 31): 'Leadership', (9, 52): 'Concentration', (10, 20): 'Awakening',
    (11, 56): 'Curiosity', (12, 22): 'Openness', (13, 33): 'Prodigal',
    (16, 48): 'Wavelength', (17, 62): 'Acceptance', (18, 58): 'Judgment',
    (19, 49): 'Synthesis', (21, 45): 'Money Line', (23, 43): 'Structuring',
    (24, 61): 'Awareness', (25, 51): 'Initiation', (26, 44): 'Surrender',
    (27, 50): 'Preservation', (28, 38): 'Struggle', (29, 46): 'Discovery',
    (30, 41): 'Recognition', (32, 54): 'Transformation', (35, 36): 'Transitoriness',
    (37, 40): 'Community', (39, 55): 'Emoting', (47, 64): 'Abstraction',
    (53, 42): 'Maturation'
}

def decimal_to_dms(decimal):
    """Convert decimal degrees to degrees:minutes:seconds format"""
    is_negative = decimal < 0
    decimal = abs(decimal)
    degrees = int(decimal)
    minutes_float = (decimal - degrees) * 60
    minutes = int(minutes_float)
    seconds = int((minutes_float - minutes) * 60)
    return f"{'-' if is_negative else ''}{degrees}:{minutes}:{seconds}"

def get_sign_from_longitude(longitude):
    """Get zodiac sign from longitude"""
    if longitude is None:
        return None
    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    index = int(longitude / 30) % 12
    return signs[index]

def julian_day_from_date(year, month, day, hour=12.0):
    """Calculate Julian Day Number"""
    if month <= 2:
        year -= 1
        month += 12
    
    a = int(year / 100)
    b = 2 - a + int(a / 4)
    
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5
    jd += hour / 24.0
    return jd

def basic_sun_position(jd):
    """Calculate basic Sun position using simplified formula"""
    # Days since J2000.0
    n = jd - 2451545.0
    
    # Mean longitude of Sun
    L = (280.460 + 0.9856474 * n) % 360
    
    # Mean anomaly
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    
    # Ecliptic longitude
    longitude = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360
    
    return longitude

def basic_moon_position(jd):
    """Calculate basic Moon position using simplified formula"""
    # Days since J2000.0
    n = jd - 2451545.0
    
    # Moon's mean longitude
    L = (218.316 + 13.176396 * n) % 360
    
    # Mean anomaly
    M = math.radians((134.963 + 13.064993 * n) % 360)
    
    # Mean elongation
    D = math.radians((297.850 + 12.190749 * n) % 360)
    
    # Argument of latitude
    F = math.radians((93.272 + 13.229350 * n) % 360)
    
    # Longitude correction
    longitude = L + 6.289 * math.sin(M) + 1.274 * math.sin(2*D - M) + 0.658 * math.sin(2*D)
    longitude = longitude % 360
    
    return longitude

def basic_planet_positions(jd):
    """Calculate basic positions for major planets"""
    # Days since J2000.0
    n = jd - 2451545.0
    
    # Simplified orbital elements and calculations
    planets = {
        'Mercury': (252.25 + 4.092317 * n) % 360,
        'Venus': (181.98 + 1.602136 * n) % 360,
        'Mars': (355.43 + 0.524033 * n) % 360,
        'Jupiter': (34.35 + 0.083129 * n) % 360,
        'Saturn': (50.08 + 0.033493 * n) % 360,
        'Uranus': (314.05 + 0.011733 * n) % 360,
        'Neptune': (304.35 + 0.006000 * n) % 360,
        'Pluto': (238.96 + 0.003982 * n) % 360
    }
    
    return planets

def calculate_north_node(jd):
    """Calculate North Node position"""
    # Days since J2000.0
    n = jd - 2451545.0
    
    # Mean longitude of ascending node
    node_lon = (125.045 - 0.052954 * n) % 360
    
    return node_lon

def fallback_planet_calculation(julian_day, planet_name):
    """Fallback calculation when PySwissEph fails"""
    try:
        if planet_name == 'Sun':
            return basic_sun_position(julian_day)
        elif planet_name == 'Moon':
            return basic_moon_position(julian_day)
        elif planet_name == 'North Node':
            return calculate_north_node(julian_day)
        else:
            planets = basic_planet_positions(julian_day)
            return planets.get(planet_name, None)
    except Exception as e:
        logger.error(f"Fallback calculation failed for {planet_name}: {e}")
        return None

def get_planet_position(julian_day, planet_id, planet_name="Unknown"):
    """Get planet position with ultimate fallback to basic calculations"""
    try:
        # Try PySwissEph first
        result = swe.calc_ut(julian_day, planet_id)
        if result[1] == 0:  # Success
            return result[0][0]  # Longitude
        else:
            logger.warning(f"PySwissEph failed for {planet_name} (error {result[1]}), using fallback calculation")
            
            # Use fallback calculation
            fallback_lon = fallback_planet_calculation(julian_day, planet_name)
            if fallback_lon is not None:
                return fallback_lon
            else:
                logger.error(f"Both PySwissEph and fallback failed for {planet_name}")
                return None
                
    except Exception as e:
        logger.warning(f"PySwissEph exception for {planet_name}: {e}, using fallback")
        
        # Use fallback calculation
        fallback_lon = fallback_planet_calculation(julian_day, planet_name)
        return fallback_lon

def get_hd_gate_and_line(longitude):
    """Convert longitude to Human Design gate and line"""
    if longitude is None:
        return None, None
    
    # Normalize longitude to 0-360
    lon = longitude % 360
    
    # Each gate spans 5.625 degrees (360/64)
    gate = int(lon / 5.625) + 1
    if gate > 64:
        gate = 64
    
    # Calculate position within the gate
    gate_start = (gate - 1) * 5.625
    position_in_gate = lon - gate_start
    
    # Each line spans 0.9375 degrees (5.625/6)
    line = int(position_in_gate / 0.9375) + 1
    if line > 6:
        line = 6
    if line < 1:
        line = 1
        
    return gate, line

def calculate_house_position(planet_lon, house_cusps):
    """Determine which house a planet is in"""
    if planet_lon is None or not house_cusps:
        return None
        
    for i in range(12):
        current_cusp = house_cusps[i]
        next_cusp = house_cusps[(i + 1) % 12]
        
        # Handle houses that cross 0 degrees
        if next_cusp < current_cusp:
            if planet_lon >= current_cusp or planet_lon < next_cusp:
                return i + 1
        else:
            if current_cusp <= planet_lon < next_cusp:
                return i + 1
                
    return 1  # Fallback to first house

def calculate_house_cusps(julian_day, latitude, longitude):
    """Calculate house cusps using Placidus system"""
    try:
        # Calculate houses
        cusps, ascmc = swe.houses(julian_day, latitude, longitude, b'P')  # Placidus
        if len(cusps) >= 13:  # Ensure we have enough cusps
            return list(cusps[1:13]), ascmc  # Remove first element (0), return cusps 1-12
        else:
            logger.error(f"Not enough house cusps returned: {len(cusps)}")
            return None, None
    except Exception as e:
        logger.error(f"House calculation failed: {e}")
        return None, None

def get_geocoding_data(location):
    """Get latitude and longitude from location string"""
    if not GOOGLE_API_KEY:
        return None, None, "Google API key not configured"
    
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(location)}&key={GOOGLE_API_KEY}"
    try:
        response = requests.get(geo_url, timeout=10)
        geo_data = response.json()
        
        if not geo_data.get('results'):
            return None, None, "Location not found. Please include city, state, country."
            
        location_data = geo_data['results'][0]['geometry']['location']
        return location_data['lat'], location_data['lng'], None
        
    except requests.RequestException as e:
        return None, None, f"Geocoding request failed: {str(e)}"
    except Exception as e:
        return None, None, f"Geocoding failed: {str(e)}"

def calculate_human_design(date, time, lat, lon):
    """Calculate Human Design chart"""
    try:
        # Parse datetime - handle both 12-hour and 24-hour formats
        time_clean = time.strip()
        
        # Try different time formats
        dt = None
        date_clean = date.replace('/', '-')
        
        # Try 12-hour format first (09:05 PM)
        try:
            dt = datetime.strptime(f"{date_clean} {time_clean}", "%Y-%m-%d %I:%M %p")
        except ValueError:
            pass
            
        # Try 24-hour format (21:05)
        if dt is None:
            try:
                dt = datetime.strptime(f"{date_clean} {time_clean}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
                
        # Try without seconds
        if dt is None:
            try:
                dt = datetime.strptime(f"{date_clean} {time_clean}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
                
        if dt is None:
            raise ValueError(f"Could not parse time format: {time_clean}")
        
        # Convert to Julian Day (UTC)
        jd_natal = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        
        # Design date (88.25 days before birth for more accuracy)
        design_dt = dt - timedelta(days=88, hours=6)  # 88.25 days = 88 days 6 hours
        jd_design = swe.julday(design_dt.year, design_dt.month, design_dt.day, 
                              design_dt.hour + design_dt.minute/60.0)
        
        # Planets to calculate
        planets = {
            'Sun': swe.SUN,
            'Moon': swe.MOON,
            'Mercury': swe.MERCURY,
            'Venus': swe.VENUS,
            'Mars': swe.MARS,
            'Jupiter': swe.JUPITER,
            'Saturn': swe.SATURN,
            'Uranus': swe.URANUS,
            'Neptune': swe.NEPTUNE,
            'Pluto': swe.PLUTO,
            'North Node': swe.MEAN_NODE
        }
        
        personality_gates = {}
        design_gates = {}
        
        # Calculate personality positions (natal)
        for planet_name, planet_id in planets.items():
            longitude = get_planet_position(jd_natal, planet_id, planet_name)
            if longitude is not None:
                gate, line = get_hd_gate_and_line(longitude)
                personality_gates[planet_name] = {
                    'gate': gate, 'line': line, 'longitude': longitude
                }
                
        # Calculate design positions
        for planet_name, planet_id in planets.items():
            longitude = get_planet_position(jd_design, planet_id, planet_name)
            if longitude is not None:
                gate, line = get_hd_gate_and_line(longitude)
                design_gates[planet_name] = {
                    'gate': gate, 'line': line, 'longitude': longitude
                }
        
        # Get all active gates
        all_gates = set()
        for planet_data in personality_gates.values():
            if planet_data.get('gate'):
                all_gates.add(planet_data['gate'])
        for planet_data in design_gates.values():
            if planet_data.get('gate'):
                all_gates.add(planet_data['gate'])
            
        # Determine defined centers
        centers = {}
        for center, gates in CENTER_GATES.items():
            centers[center] = any(gate in all_gates for gate in gates)
            
        # Determine active channels
        active_channels = []
        for (gate1, gate2), channel_name in CHANNELS.items():
            if gate1 in all_gates and gate2 in all_gates:
                active_channels.append(f"{gate1}-{gate2} ({channel_name})")
                
        # Determine type based on defined centers (corrected logic)
        sacral_defined = centers.get('Sacral', False)
        throat_defined = centers.get('Throat', False)
        heart_defined = centers.get('Heart', False)
        g_defined = centers.get('G', False)
        
        if sacral_defined and throat_defined:
            # Check if it's a direct connection
            type_name = 'Manifesting Generator'
            strategy = 'To Respond'
            signature = 'Satisfaction'
            not_self = 'Frustration'
        elif sacral_defined:
            type_name = 'Generator'
            strategy = 'To Respond'
            signature = 'Satisfaction'
            not_self = 'Frustration'
        elif throat_defined and (heart_defined or g_defined):
            type_name = 'Manifestor'
            strategy = 'To Initiate'
            signature = 'Peace'
            not_self = 'Anger'
        elif not sacral_defined and not throat_defined and not heart_defined:
            type_name = 'Reflector'
            strategy = 'To Wait a Lunar Cycle'
            signature = 'Surprise'
            not_self = 'Disappointment'
        else:
            type_name = 'Projector'
            strategy = 'To Wait for Invitation'
            signature = 'Success'
            not_self = 'Bitterness'
            
        # Determine authority
        if centers.get('SolarPlexus'):
            authority = 'Emotional - Solar Plexus'
        elif centers.get('Sacral') and not centers.get('SolarPlexus'):
            authority = 'Sacral'
        elif centers.get('Spleen') and not (centers.get('SolarPlexus') or centers.get('Sacral')):
            authority = 'Splenic'
        elif centers.get('Heart') and not (centers.get('SolarPlexus') or centers.get('Sacral') or centers.get('Spleen')):
            authority = 'Ego'
        elif centers.get('G') and not (centers.get('SolarPlexus') or centers.get('Sacral') or centers.get('Spleen') or centers.get('Heart')):
            authority = 'Self-Projected'
        else:
            authority = 'Mental - Outer Authority'
            
        # Profile calculation (corrected)
        sun_personality = personality_gates.get('Sun', {})
        earth_design = design_gates.get('North Node', {})
        
        # Use the actual lines from the gates
        profile_line1 = sun_personality.get('line', 1)  # Personality line from Sun
        profile_line2 = earth_design.get('line', 1)     # Design line from Earth (North Node)
        
        profile = f"{profile_line1}/{profile_line2}"
        
        # Incarnation Cross calculation (corrected)
        sun_gate = sun_personality.get('gate', 1)
        earth_gate = earth_design.get('gate', 2)
        
        # Get the opposite gates for full cross
        sun_opposite = (sun_gate + 31) % 64 + 1 if (sun_gate + 31) % 64 != 0 else 64
        earth_opposite = (earth_gate + 31) % 64 + 1 if (earth_gate + 31) % 64 != 0 else 64
        
        incarnation_cross = f"Cross of {sun_gate}/{earth_gate} - {sun_opposite}/{earth_opposite}"
        
        # Definition
        if len(active_channels) == 0:
            definition = 'No Definition'
        elif len(active_channels) <= 2:
            definition = 'Single Definition'
        else:
            definition = 'Split Definition'
        
        return {
            'type': type_name,
            'strategy': strategy,
            'authority': authority,
            'profile': profile,
            'definition': definition,
            'incarnation_cross': incarnation_cross,
            'signature': signature,
            'not_self_theme': not_self,
            'centers': centers,
            'gates': sorted(list(all_gates)),
            'channels': active_channels,
            'personality_gates': personality_gates,
            'design_gates': design_gates,
            'digestion': 'Calm' if 32 in all_gates else 'Nervous',
            'environment': 'Mountains' if 15 in all_gates else 'Valleys'
        }
        
    except Exception as e:
        logger.error(f"Human Design calculation failed: {str(e)}")
        return None

def calculate_astrology_chart(date, time, lat, lon, timezone_offset=0):
    """Calculate tropical astrology chart using pure PySwissEph"""
    try:
        # Parse datetime - handle both 12-hour and 24-hour formats
        time_clean = time.strip()
        date_clean = date.replace('/', '-')
        
        # Try different time formats
        dt = None
        
        # Try 12-hour format first (09:05 PM)
        try:
            dt = datetime.strptime(f"{date_clean} {time_clean}", "%Y-%m-%d %I:%M %p")
        except ValueError:
            pass
            
        # Try 24-hour format (21:05)
        if dt is None:
            try:
                dt = datetime.strptime(f"{date_clean} {time_clean}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass
                
        if dt is None:
            raise ValueError(f"Could not parse time format: {time_clean}")
        
        # Adjust for timezone (convert to UTC)
        dt_utc = dt - timedelta(hours=timezone_offset)
        jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60.0)
        
        # Calculate house cusps and angles
        house_cusps, ascmc = calculate_house_cusps(jd, lat, lon)
        if house_cusps is None:
            return None
            
        # Extract angles
        ascendant = ascmc[0]
        midheaven = ascmc[1]
        descendant = (ascendant + 180) % 360
        ic = (midheaven + 180) % 360
        
        # Standard planets
        planets = {
            'Sun': swe.SUN,
            'Moon': swe.MOON,
            'Mercury': swe.MERCURY,
            'Venus': swe.VENUS,
            'Mars': swe.MARS,
            'Jupiter': swe.JUPITER,
            'Saturn': swe.SATURN,
            'Uranus': swe.URANUS,
            'Neptune': swe.NEPTUNE,
            'Pluto': swe.PLUTO
        }
        
        planet_data = {}
        
        # Calculate planet positions
        for planet_name, planet_id in planets.items():
            longitude = get_planet_position(jd, planet_id, planet_name)
            if longitude is not None:
                planet_data[planet_name] = {
                    'sign': get_sign_from_longitude(longitude),
                    'degree': round(longitude, 2),
                    'house': calculate_house_position(longitude, house_cusps)
                }
        
        # Calculate Chiron
        chiron_lon = get_planet_position(jd, swe.CHIRON, 'Chiron')
        if chiron_lon is not None:
            planet_data['Chiron'] = {
                'sign': get_sign_from_longitude(chiron_lon),
                'degree': round(chiron_lon, 2),
                'house': calculate_house_position(chiron_lon, house_cusps)
            }
        
        # Calculate Lilith (Mean Black Moon)
        lilith_lon = get_planet_position(jd, swe.MEAN_APOG, 'Lilith')
        if lilith_lon is not None:
            planet_data['Lilith'] = {
                'sign': get_sign_from_longitude(lilith_lon),
                'degree': round(lilith_lon, 2),
                'house': calculate_house_position(lilith_lon, house_cusps)
            }
        
        # Calculate dominant element and mode
        all_signs = []
        for planet in planet_data.values():
            if planet.get('sign'):
                all_signs.append(planet['sign'])
        
        # Add angles
        asc_sign = get_sign_from_longitude(ascendant)
        mc_sign = get_sign_from_longitude(midheaven)
        if asc_sign:
            all_signs.append(asc_sign)
        if mc_sign:
            all_signs.append(mc_sign)
            
        element_counts = {'Fire': 0, 'Earth': 0, 'Air': 0, 'Water': 0}
        mode_counts = {'Cardinal': 0, 'Fixed': 0, 'Mutable': 0}
        
        for sign in all_signs:
            if sign and sign.upper() in ELEMENTS:
                element_counts[ELEMENTS[sign.upper()]] += 1
            if sign and sign.upper() in MODES:
                mode_counts[MODES[sign.upper()]] += 1
                
        dominant_element = max(element_counts, key=element_counts.get) if any(element_counts.values()) else 'Unknown'
        dominant_mode = max(mode_counts, key=mode_counts.get) if any(mode_counts.values()) else 'Unknown'
        
        # House information
        house_info = []
        for i, cusp in enumerate(house_cusps):
            house_info.append({
                'house': i + 1,
                'sign': get_sign_from_longitude(cusp),
                'degree': round(cusp, 2)
            })
        
        return {
            'planets': planet_data,
            'angles': {
                'ascendant': {'sign': asc_sign, 'degree': round(ascendant, 2)},
                'midheaven': {'sign': mc_sign, 'degree': round(midheaven, 2)},
                'descendant': {'sign': get_sign_from_longitude(descendant), 'degree': round(descendant, 2)},
                'ic': {'sign': get_sign_from_longitude(ic), 'degree': round(ic, 2)}
            },
            'houses': house_info,
            'dominant_element': dominant_element,
            'dominant_mode': dominant_mode,
            'element_counts': element_counts,
            'mode_counts': mode_counts
        }
        
    except Exception as e:
        logger.error(f"Astrology calculation failed: {str(e)}")
        return None

def calculate_moon_phase(date):
    """Calculate moon phase for a given date"""
    try:
        dt = datetime.strptime(date.replace('/', '-'), "%Y-%m-%d")
        jd = swe.julday(dt.year, dt.month, dt.day, 12.0)  # Noon
        
        # Get Sun and Moon positions with robust calculation
        sun_lon = get_planet_position(jd, swe.SUN, "Sun")
        moon_lon = get_planet_position(jd, swe.MOON, "Moon")
        
        if sun_lon is None or moon_lon is None:
            logger.error("Failed to calculate Sun or Moon position for moon phase")
            return None
            
        # Calculate angular distance
        distance = (moon_lon - sun_lon) % 360
        
        # Determine phase
        if 0 <= distance < 45:
            phase = "New Moon"
            tcm_energy = "Rest & Renewal"
        elif 45 <= distance < 90:
            phase = "Waxing Crescent"
            tcm_energy = "Growth & Building"
        elif 90 <= distance < 135:
            phase = "First Quarter"
            tcm_energy = "Growth & Building"
        elif 135 <= distance < 180:
            phase = "Waxing Gibbous"
            tcm_energy = "Expansion & Harvest"
        elif 180 <= distance < 225:
            phase = "Full Moon"
            tcm_energy = "Expansion & Harvest"
        elif 225 <= distance < 270:
            phase = "Waning Gibbous"
            tcm_energy = "Release & Cleansing"
        elif 270 <= distance < 315:
            phase = "Last Quarter"
            tcm_energy = "Release & Cleansing"
        else:
            phase = "Waning Crescent"
            tcm_energy = "Deep Rest"
            
        return {
            'date': date,
            'moon_phase': phase,
            'angular_distance': round(distance, 1),
            'tcm_energy': tcm_energy,
            'sun_longitude': round(sun_lon, 2),
            'moon_longitude': round(moon_lon, 2)
        }
        
    except Exception as e:
        logger.error(f"Moon phase calculation failed: {str(e)}")
        return None

# API ENDPOINTS

@app.route('/debug/ephe', methods=['GET'])
def debug_ephemeris():
    """Debug endpoint to check ephemeris files"""
    ephe_status = {
        'ephe_path': EPHE_PATH,
        'path_exists': os.path.exists(EPHE_PATH),
        'files': {}
    }
    
    # Check individual files
    required_files = ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1']
    for fname in required_files:
        fpath = os.path.join(EPHE_PATH, fname)
        ephe_status['files'][fname] = {
            'exists': os.path.exists(fpath),
            'size': os.path.getsize(fpath) if os.path.exists(fpath) else 0
        }
    
    # Test calculation
    try:
        test_jd = swe.julday(2023, 6, 1, 12.0)
        sun_lon = get_planet_position(test_jd, swe.SUN, "Sun")
        ephe_status['test_calculation'] = {
            'success': sun_lon is not None,
            'sun_longitude': sun_lon
        }
    except Exception as e:
        ephe_status['test_calculation'] = {
            'success': False,
            'error': str(e)
        }
    
    return jsonify(ephe_status)

@app.route('/v1/humandesign/profile', methods=['GET'])
def get_human_design_profile():
    """Get Human Design profile"""
    try:
        # Get parameters
        name = request.args.get('name', 'Unknown')
        date = request.args.get('date')
        time = request.args.get('time')
        location = request.args.get('location')
        
        if not all([date, time, location]):
            return jsonify({"error": "Missing required parameters: date, time, location"}), 400
        
        # Get coordinates
        lat, lon, error = get_geocoding_data(location)
        if error:
            return jsonify({"error": error}), 400
            
        # Calculate Human Design
        hd_data = calculate_human_design(date, time, lat, lon)
        if not hd_data:
            return jsonify({"error": "Human Design calculation failed"}), 500
            
        # Add request info
        hd_data.update({
            'name': name,
            'date': date,
            'time': time,
            'location': location,
            'coordinates': {'latitude': lat, 'longitude': lon}
        })
        
        return jsonify(hd_data)
        
    except Exception as e:
        logger.error(f"Human Design endpoint error: {str(e)}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500

@app.route('/v1/astrology/chart', methods=['GET'])
def get_astrology_chart():
    """Get tropical astrology chart"""
    try:
        # Get parameters
        name = request.args.get('name', 'Unknown')
        date = request.args.get('date')
        time = request.args.get('time')
        location = request.args.get('location')
        timezone_offset = float(request.args.get('timezone_offset', 0))  # Hours from UTC
        
        if not all([date, time, location]):
            return jsonify({"error": "Missing required parameters: date, time, location"}), 400
        
        # Get coordinates
        lat, lon, error = get_geocoding_data(location)
        if error:
            return jsonify({"error": error}), 400
            
        # Calculate astrology chart
        chart_data = calculate_astrology_chart(date, time, lat, lon, timezone_offset)
        if not chart_data:
            return jsonify({"error": "Astrology chart calculation failed"}), 500
            
        # Add request info
        result = {
            'name': name,
            'date': date,
            'time': time,
            'location': location,
            'timezone_offset': timezone_offset,
            'coordinates': {'latitude': lat, 'longitude': lon},
            **chart_data
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Astrology endpoint error: {str(e)}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500

@app.route('/v1/moonphase', methods=['GET'])
def get_moon_phase():
    """Get moon phase information"""
    try:
        date = request.args.get('date')
        range_query = request.args.get('range', 'single')
        
        if not date:
            return jsonify({"error": "Missing required parameter: date"}), 400
        
        if range_query == 'single':
            phase_data = calculate_moon_phase(date)
            if not phase_data:
                return jsonify({"error": "Moon phase calculation failed"}), 500
            return jsonify(phase_data)
            
        elif range_query == '6week':
            # Calculate for 6 weeks (42 days)
            start_date = datetime.strptime(date.replace('/', '-'), "%Y-%m-%d")
            moon_phases = []
            
            for i in range(0, 42, 7):  # Weekly intervals
                current_date = start_date + timedelta(days=i)
                date_str = current_date.strftime('%Y-%m-%d')
                phase_data = calculate_moon_phase(date_str)
                if phase_data:
                    moon_phases.append(phase_data)
                    
            return jsonify(moon_phases)
            
        else:
            return jsonify({"error": "Invalid range parameter. Use 'single' or '6week'"}), 400
            
    except Exception as e:
        logger.error(f"Moon phase endpoint error: {str(e)}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'ephemeris_path': EPHE_PATH,
        'ephemeris_exists': os.path.exists(EPHE_PATH)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
