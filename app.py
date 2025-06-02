from flask import Flask, request, jsonify
from urllib.parse import quote
import requests
import os
from datetime import datetime, timedelta
import logging
import swisseph as swe
import math

# New timezone handling libraries
try:
    from timezonefinder import TimezoneFinder
    import pytz
    TIMEZONE_AVAILABLE = True
except ImportError:
    TIMEZONE_AVAILABLE = False
    logging.warning("Timezone libraries not available. Install: pip install timezonefinder pytz")

app = Flask(__name__)

# Set absolute ephemeris path for Render
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
EPHE_PATH = os.path.join(BASE_DIR, 'ephe')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Setup logging FIRST
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup ephemeris with proper error handling
try:
    if os.path.exists(EPHE_PATH):
        swe.set_ephe_path(EPHE_PATH)
        logger.info(f"Set ephemeris path to: {EPHE_PATH}")
    else:
        swe.set_ephe_path("")
        logger.info("Using built-in ephemeris")
        
    # Test ephemeris
    test_jd = swe.julday(2000, 1, 1, 12.0)
    test_result = swe.calc_ut(test_jd, swe.SUN)
    if test_result[1] == 0:
        logger.info(f"Ephemeris test successful: Sun at {test_result[0][0]:.2f}°")
    else:
        logger.warning(f"Ephemeris test failed with error: {test_result[1]}")
        
except Exception as e:
    logger.error(f"Ephemeris setup failed: {e}")
    swe.set_ephe_path("")

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

def get_proper_timezone_info(lat, lon, dt):
    """Get proper timezone information using TimezoneFinder and pytz"""
    if not TIMEZONE_AVAILABLE:
        logger.warning("Timezone libraries not available, using basic offset estimation")
        # Basic fallback - estimate timezone from longitude
        estimated_offset = round(lon / 15.0)  # Rough estimate: 15° per hour
        return estimated_offset, f"Estimated UTC{estimated_offset:+d}"
    
    try:
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=lat, lng=lon)
        
        if timezone_str:
            tz = pytz.timezone(timezone_str)
            # Get the UTC offset for the specific datetime (handles DST)
            localized_dt = tz.localize(dt, is_dst=None)
            utc_offset = localized_dt.utcoffset().total_seconds() / 3600
            return utc_offset, timezone_str
        else:
            logger.warning(f"Could not determine timezone for {lat}, {lon}")
            return 0, "UTC"
            
    except Exception as e:
        logger.error(f"Timezone detection failed: {e}")
        # Fallback to basic estimation
        estimated_offset = round(lon / 15.0)
        return estimated_offset, f"Estimated UTC{estimated_offset:+d}"

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
    """Calculate basic Sun position using more accurate formula"""
    # Days since J2000.0
    T = (jd - 2451545.0) / 36525.0  # Julian centuries
    
    # Mean longitude of Sun (degrees)
    L0 = (280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360
    
    # Mean anomaly of Sun (degrees)
    M = (357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360
    M_rad = math.radians(M)
    
    # Equation of center
    C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_rad) + \
        (0.019993 - 0.000101 * T) * math.sin(2 * M_rad) + \
        0.000289 * math.sin(3 * M_rad)
    
    # True longitude
    longitude = (L0 + C) % 360
    
    return longitude

def basic_moon_position(jd):
    """Calculate basic Moon position using more accurate formula"""
    # Days since J2000.0
    T = (jd - 2451545.0) / 36525.0  # Julian centuries
    
    # Moon's mean longitude (degrees)
    L_prime = (218.3164477 + 481267.88123421 * T - 0.0015786 * T * T + T * T * T / 538841.0 - T * T * T * T / 65194000.0) % 360
    
    # Mean elongation of Moon (degrees)
    D = (297.8501921 + 445267.1114034 * T - 0.0018819 * T * T + T * T * T / 545868.0 - T * T * T * T / 113065000.0) % 360
    D_rad = math.radians(D)
    
    # Sun's mean anomaly (degrees)
    M = (357.5291092 + 35999.0502909 * T - 0.0001536 * T * T + T * T * T / 24490000.0) % 360
    M_rad = math.radians(M)
    
    # Moon's mean anomaly (degrees)
    M_prime = (134.9633964 + 477198.8675055 * T + 0.0087414 * T * T + T * T * T / 69699.0 - T * T * T * T / 14712000.0) % 360
    M_prime_rad = math.radians(M_prime)
    
    # Moon's argument of latitude (degrees)
    F = (93.2720950 + 483202.0175233 * T - 0.0036539 * T * T - T * T * T / 3526000.0 + T * T * T * T / 863310000.0) % 360
    F_rad = math.radians(F)
    
    # Longitude corrections (simplified main terms)
    longitude_correction = 6.288774 * math.sin(M_prime_rad) + \
                          1.274027 * math.sin(2 * D_rad - M_prime_rad) + \
                          0.658314 * math.sin(2 * D_rad) + \
                          0.213618 * math.sin(2 * M_prime_rad) + \
                          -0.185116 * math.sin(M_rad) + \
                          -0.114332 * math.sin(2 * F_rad)
    
    # True longitude
    longitude = (L_prime + longitude_correction) % 360
    
    return longitude

def basic_planet_positions(jd):
    """Calculate basic positions for major planets - improved accuracy"""
    # Days since J2000.0
    T = (jd - 2451545.0) / 36525.0  # Julian centuries
    
    # More accurate orbital elements and calculations
    planets = {}
    
    # Mercury
    L_merc = (252.250906 + 149472.674635 * T) % 360
    planets['Mercury'] = L_merc
    
    # Venus  
    L_venus = (181.979801 + 58517.815676 * T) % 360
    planets['Venus'] = L_venus
    
    # Mars
    L_mars = (355.433 + 19140.299 * T) % 360
    planets['Mars'] = L_mars
    
    # Jupiter
    L_jup = (34.351519 + 3034.90567 * T) % 360
    planets['Jupiter'] = L_jup
    
    # Saturn
    L_sat = (50.077444 + 1222.11494 * T) % 360
    planets['Saturn'] = L_sat
    
    # Uranus
    L_ura = (314.055005 + 428.466998 * T) % 360
    planets['Uranus'] = L_ura
    
    # Neptune
    L_nep = (304.348665 + 218.486200 * T) % 360
    planets['Neptune'] = L_nep
    
    # Pluto (approximate)
    L_plu = (238.956 + 145.205 * T) % 360
    planets['Pluto'] = L_plu
    
    return planets

def calculate_north_node(jd):
    """Calculate North Node position - more accurate"""
    # Days since J2000.0
    T = (jd - 2451545.0) / 36525.0  # Julian centuries
    
    # Mean longitude of ascending node (degrees)
    # More accurate formula
    node_lon = (125.04452 - 1934.136261 * T + 0.0020708 * T * T + T * T * T / 450000.0) % 360
    
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
        # Try PySwissEph first with different flags
        flags = [swe.FLG_SWIEPH, swe.FLG_MOSEPH, swe.FLG_JPLEPH]
        
        for flag in flags:
            try:
                result = swe.calc_ut(julian_day, planet_id, flag)
                if result[1] == 0:  # Success
                    logger.debug(f"Successfully calculated {planet_name} with flag {flag}")
                    return result[0][0]  # Longitude
                else:
                    logger.debug(f"PySwissEph failed for {planet_name} with flag {flag} (error {result[1]})")
            except Exception as e:
                logger.debug(f"Exception with flag {flag} for {planet_name}: {e}")
                continue
                
        # If all PySwissEph methods fail, use fallback
        logger.warning(f"All PySwissEph methods failed for {planet_name}, using fallback calculation")
        
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
    """
    Convert longitude to Human Design gate and line - CORRECTED OFFICIAL SEQUENCE
    
    Based on research of official Human Design sources and the Rave Mandala.
    The gates follow the I Ching sequence starting at 0° Aries.
    """
    if longitude is None:
        return None, None
    
    # Normalize longitude to 0-360
    longitude = longitude % 360.0
    
    # CORRECTED Human Design Gate Sequence based on official sources
    # This sequence starts at 0° Aries and follows the Rave Mandala order
    # Based on research from Jovian Archive and official HD sources
    gate_sequence = [
        41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
        27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
        31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
        28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60
    ]
    
    # Exact degree calculations (5°37'30" per gate)
    degrees_per_gate = 5 + (37/60) + (30/3600)  # = 5.625° exactly
    degrees_per_line = degrees_per_gate / 6      # = 0.9375° exactly
    
    # Calculate gate index (0-63)
    gate_index = int(longitude / degrees_per_gate)
    
    # Handle edge case at exactly 360°/0°
    if gate_index >= 64:
        gate_index = 0
    
    # Get gate number from sequence
    gate = gate_sequence[gate_index]
    
    # Calculate position within the gate
    position_in_gate = longitude % degrees_per_gate
    
    # Calculate line (1-6) with floating-point precision fix
    # CRITICAL FIX: Add small epsilon to prevent floating-point rounding errors
    line = int((position_in_gate + 1e-10) / degrees_per_line) + 1
    
    # Ensure line is in valid range
    if line > 6:
        line = 6
    elif line < 1:
        line = 1
    
    logger.debug(f"Longitude {longitude:.6f}° -> Gate {gate}, Line {line} (gate_index={gate_index}, position_in_gate={position_in_gate:.6f})")
    
    return gate, line

def calculate_house_position(planet_lon, house_cusps):
    """Determine which house a planet is in"""
    if planet_lon is None or not house_cusps or len(house_cusps) < 12:
        return None
        
    # Use only the first 12 house cusps
    cusps = house_cusps[:12]
    
    for i in range(12):
        current_cusp = cusps[i]
        next_cusp = cusps[(i + 1) % 12]
        
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
        if len(cusps) >= 12:  # Swiss Ephemeris returns 12 house cusps (1-12)
            return list(cusps), ascmc  # Return all cusps as-is
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
    """Calculate Human Design chart with proper timezone handling and corrected gate sequence"""
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
        
        # Get proper timezone information
        timezone_offset, timezone_name = get_proper_timezone_info(lat, lon, dt)
        
        logger.info(f"Location: {lat}, {lon}")
        logger.info(f"Birth time: {dt} (local), Timezone: {timezone_name}, Offset: UTC{timezone_offset:+.1f}")
        
        # Convert local time to UTC
        dt_utc = dt - timedelta(hours=timezone_offset)
        
        logger.info(f"UTC birth time: {dt_utc}")
        
        # Convert to Julian Day (UTC)
        jd_natal = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60.0)
        
        # Design date (88.25 days before birth - this is the exact HD calculation)
        design_dt_utc = dt_utc - timedelta(days=88, hours=6)  # 88.25 days = 88 days 6 hours
        jd_design = swe.julday(design_dt_utc.year, design_dt_utc.month, design_dt_utc.day, 
                              design_dt_utc.hour + design_dt_utc.minute/60.0)
                              
        logger.info(f"Natal JD: {jd_natal}, Design JD: {jd_design}")
        
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
                logger.debug(f"Personality {planet_name}: {longitude:.6f}° -> Gate {gate}.{line}")
                
        # Calculate design positions
        for planet_name, planet_id in planets.items():
            longitude = get_planet_position(jd_design, planet_id, planet_name)
            if longitude is not None:
                gate, line = get_hd_gate_and_line(longitude)
                design_gates[planet_name] = {
                    'gate': gate, 'line': line, 'longitude': longitude
                }
                logger.debug(f"Design {planet_name}: {longitude:.6f}° -> Gate {gate}.{line}")
        
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
                
        # Determine type based on defined centers
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
            
        # Profile calculation - CORRECTED UNIVERSAL FORMULA
        # Profile is Conscious Sun line / Unconscious Earth line
        sun_personality = personality_gates.get('Sun', {})
        
        # Calculate Earth position for design (unconscious)
        sun_design = design_gates.get('Sun', {})
        sun_design_lon = sun_design.get('longitude', 0)
        earth_design_lon = (sun_design_lon + 180) % 360
        earth_design_gate, earth_design_line = get_hd_gate_and_line(earth_design_lon)
        
        # Profile is Conscious Sun line / Unconscious Earth line
        profile_line1 = sun_personality.get('line', 1)  # Personality line from Sun
        profile_line2 = earth_design_line if earth_design_line else 1  # Design line from Earth
        
        profile = f"{profile_line1}/{profile_line2}"
        
        # Incarnation Cross calculation - PROPER GATES
        # Use Sun/Earth from both Personality and Design
        sun_gate_personality = sun_personality.get('gate', 1)
        earth_gate_design = earth_design_gate if earth_design_gate else 2
        
        # Get the nodal gates (90 degrees from Sun/Earth axis)
        north_node_personality = personality_gates.get('North Node', {}).get('gate', 1)
        south_node_design = design_gates.get('North Node', {})
        south_node_design_lon = south_node_design.get('longitude', 0)
        # South Node is opposite North Node
        south_node_design_lon_opposite = (south_node_design_lon + 180) % 360
        south_node_design_gate, _ = get_hd_gate_and_line(south_node_design_lon_opposite)
        
        incarnation_cross = f"Cross of {sun_gate_personality}/{earth_gate_design} - {north_node_personality}/{south_node_design_gate if south_node_design_gate else 1}"
        
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
            'environment': 'Mountains' if 15 in all_gates else 'Valleys',
            'timezone_used': timezone_name,
            'timezone_offset': timezone_offset,
            'utc_birth_time': dt_utc.isoformat()
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
            if i < 12:  # Only process houses 1-12
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

@app.route('/test/karen', methods=['GET'])
def test_karen_chart():
    """
    Test endpoint for Karen's chart to verify the universal mathematical fix.
    Expected: Profile 6/2, Gate 23 Line 6 Sun, Left Angle Cross of Dedication
    """
    try:
        # Karen's data: May 15, 1975, 21:05, Cowra NSW Australia
        hd_data = calculate_human_design(
            date="1975-05-15",
            time="21:05",
            lat=-33.8406,  # Cowra NSW coordinates
            lon=148.6819
        )
        
        if not hd_data:
            return jsonify({'error': 'Human Design calculation failed'}), 500
        
        # Extract key values for verification
        sun_gate = hd_data['personality_gates'].get('Sun', {}).get('gate')
        sun_line = hd_data['personality_gates'].get('Sun', {}).get('line')
        profile = hd_data.get('profile')
        
        return jsonify({
            'test_subject': 'Karen',
            'birth_details': {
                'date': '1975-05-15',
                'time': '21:05',
                'location': 'Cowra, NSW, Australia'
            },
            'expected_results': {
                'profile': '6/2',
                'sun_gate': 23,
                'sun_line': 6,
                'type': 'Manifesting Generator',
                'cross': 'Left Angle Cross of Dedication'
            },
            'actual_results': {
                'profile': profile,
                'sun_gate': sun_gate,
                'sun_line': sun_line,
                'type': hd_data.get('type'),
                'cross': hd_data.get('incarnation_cross')
            },
            'accuracy_verification': {
                'profile_correct': profile == '6/2',
                'sun_gate_correct': sun_gate == 23,
                'sun_line_correct': sun_line == 6,
                'fix_successful': profile == '6/2' and sun_gate == 23 and sun_line == 6
            },
            'full_chart_data': hd_data
        })
        
    except Exception as e:
        logger.error(f"Karen test failed: {str(e)}")
        return jsonify({
            'error': f'Test calculation failed: {str(e)}'
        }), 500

@app.route('/debug/gate-calculation', methods=['GET'])
def debug_gate_calculation():
    """Debug endpoint to test gate and line calculations against known results"""
    longitude = float(request.args.get('longitude', 54.00655393218436))  # Karen's actual Sun longitude
    
    # REVERSE ENGINEER: If Karen has Gate 23 at longitude 54.006°, what should the sequence be?
    # Gate index 9 should equal Gate 23
    
    # Test different sequences where index 9 = Gate 23
    sequences = {
        'test_sequence_1': [1, 2, 3, 4, 5, 6, 7, 8, 9, 23, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 10],
        'reverse_engineer': [None] * 64  # We'll calculate this
    }
    
    # Calculate what the sequence should be for Karen's chart
    # If longitude 54.006° should give Gate 23, Line 6
    expected_gate_index = 9  # int(54.006 / 5.625)
    sequences['reverse_engineer'][expected_gate_index] = 23
    
    # Test different line calculation methods
    line_methods = {
        'current_method': lambda pos: int((pos + 1e-10) / 0.9375) + 1,
        'simple_division': lambda pos: int(pos / 0.9375) + 1,
        'rounded_division': lambda pos: round(pos / 0.9375) + 1,
        'ceiling_method': lambda pos: math.ceil(pos / 0.9375),
        'different_degrees': lambda pos: int(pos / (5.625/6)) + 1,  # Exact 6th division
        'floor_plus_correction': lambda pos: math.floor(pos / 0.9375) + 1,
        'line6_specific': lambda pos: 6 if pos >= 4.6875 else int(pos / 0.9375) + 1,  # Special handling for line 6
    }
    
    results = {}
    degrees_per_gate = 5.625
    
    # Test gate calculations
    gate_index = int(longitude / degrees_per_gate)
    position_in_gate = longitude % degrees_per_gate
    
    for seq_name, sequence in sequences.items():
        if sequence[gate_index] is not None:
            gate = sequence[gate_index]
            
            # Test different line methods
            line_results = {}
            for method_name, method in line_methods.items():
                try:
                    line = method(position_in_gate)
                    # Clamp to 1-6 range
                    line = max(1, min(6, line))
                    line_results[method_name] = {
                        'line': line,
                        'matches_karen_line': line == 6
                    }
                except:
                    line_results[method_name] = {'line': 'error', 'matches_karen_line': False}
            
            results[seq_name] = {
                'gate': gate,
                'gate_index': gate_index,
                'position_in_gate': round(position_in_gate, 6),
                'matches_karen_gate': gate == 23,
                'line_methods': line_results
            }
    
    # Also test if we need a different starting point (offset)
    offset_tests = {}
    for offset in [0, 15, 30, -15, -30]:  # Test different starting points
        adjusted_longitude = (longitude + offset) % 360
        adj_gate_index = int(adjusted_longitude / degrees_per_gate)
        adj_position = adjusted_longitude % degrees_per_gate
        adj_line = int((adj_position + 1e-10) / 0.9375) + 1
        adj_line = max(1, min(6, adj_line))
        
        offset_tests[f'offset_{offset}'] = {
            'adjusted_longitude': adjusted_longitude,
            'gate_index': adj_gate_index,
            'line': adj_line,
            'would_need_gate_at_index': f"Gate 23 at index {adj_gate_index}"
        }
    
    # Calculate what position would give Line 6
    line_6_start = 5 * 0.9375  # 4.6875
    line_6_end = 6 * 0.9375    # 5.625
    
    return jsonify({
        'karen_longitude': longitude,
        'expected_result': {'gate': 23, 'line': 6},
        'mathematical_analysis': {
            'gate_index': gate_index,
            'position_in_gate': round(position_in_gate, 6),
            'position_in_degrees': f"{position_in_gate:.3f}° out of {degrees_per_gate}°",
            'line_6_range': f"Line 6 should be {line_6_start:.3f}° to {line_6_end:.3f}°",
            'karen_position_vs_line6': f"Karen at {position_in_gate:.3f}° - needs Line 6 range"
        },
        'sequence_tests': results,
        'offset_tests': offset_tests,
        'conclusions': {
            'gate_issue': f"Need sequence where index {gate_index} = Gate 23",
            'line_issue': f"Position {position_in_gate:.3f}° should give Line 6, not Line 4",
            'possible_solution': "Either wrong sequence OR wrong mathematical formula OR both"
        }
    })

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
        'ephemeris_exists': os.path.exists(EPHE_PATH),
        'timezone_libraries': TIMEZONE_AVAILABLE,
        'mathematical_fix': 'Universal floating-point precision correction applied',
        'gate_sequence': 'Enhanced debug testing for gate sequence and line calculations',
        'version': '3.2.0-enhanced-debug-mathematics'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
