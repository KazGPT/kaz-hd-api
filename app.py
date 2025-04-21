from flask import Flask, request, jsonify

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
        "digestion": "Nervous",
        "environment": "Mountains",
        "sun_sign": "Taurus",
        "moon_sign": "Cancer"
    }

    return jsonify(hd_data)

if __name__ == '__main__':
  app.run(host="0.0.0.0", port=10000)

