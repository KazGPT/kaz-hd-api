from flask import Flask, request, jsonify
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos


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

    # Simulated Astro response
    astro_data = {
        "name": name,
        "date": date,
        "time": time,
        "location": location,
        "sun_sign": "Taurus",
        "moon_sign": "Cancer",
        "rising_sign": "Leo",
        "midheaven": "Aquarius",
        "dominant_element": "Earth",
        "mode": "Fixed"
    }

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
