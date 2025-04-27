from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos

# Zodiac Elements
ELEMENTS = {
    'ARIES': 'Fire',
    'TAURUS': 'Earth',
    'GEMINI': 'Air',
    'CANCER': 'Water',
    'LEO': 'Fire',
    'VIRGO': 'Earth',
    'LIBRA': 'Air',
    'SCORPIO': 'Water',
    'SAGITTARIUS': 'Fire',
    'CAPRICORN': 'Earth',
    'AQUARIUS': 'Air',
    'PISCES': 'Water'
}

# Zodiac Modes
MODES = {
    'ARIES': 'Cardinal',
    'TAURUS': 'Fixed',
    'GEMINI': 'Mutable',
    'CANCER': 'Cardinal',
    'LEO': 'Fixed',
    'VIRGO': 'Mutable',
    'LIBRA': 'Cardinal',
    'SCORPIO': 'Fixed',
    'SAGITTARIUS': 'Mutable',
    'CAPRICORN': 'Cardinal',
    'AQUARIUS': 'Fixed',
    'PISCES': 'Mutable'
}


app = Flask(__name__)

@app.route('/humandesign/profile', methods=['GET'])
def get_profile():
    name = request.args.get('name')
    date = request.args.get('date')
    time = request.args.get('time')
    location = request.args.get('location')

    # Simulated HD response
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
        "gates": ["34", "20", "10", "57"],  # Example Gates
        "channels": ["34-20", "10-57"],      # Example Channels
        "defined_centres": ["Sacral", "G", "Throat"],   # Example Centres
        "undefined_centres": ["Root", "Solar Plexus", "Heart"],  # Example Centres
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
    date = request.args.get('date')
    time = request.args.get('time')
    location = request.args.get('location')

   # Create Datetime object properly
    dt = Datetime(date, time, '+10:00')

    # Create Sydney coordinates (GeoPos expects D:M:S)
    pos = GeoPos('-33:52:00', '151:12:00')

    # Create the full Chart object
    chart = Chart(dt, pos)

    # (rest of your astrology chart code continues here...)


    # Get core planetary points
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

    # Now Dominant Element + Mode Calculation
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

    
@app.route('/moonphase', methods=['GET'])
def get_moon_phase():
    date = request.args.get('date')

    # Simulated Moon Phase response
    moon_data = {
        "date": date,
        "moon_phase": "New Moon"   # Placeholder for now
    }

    return jsonify(moon_data)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
