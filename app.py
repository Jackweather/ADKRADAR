import matplotlib
matplotlib.use("Agg")  # Use non-GUI backend for safe background plotting

import pyart
import fsspec
from metpy.plots import ctables
import matplotlib.pyplot as plt
import warnings
from datetime import datetime as dt
import numpy as np
import json
import os
import glob
import threading
import time
from flask import Flask, render_template, jsonify

warnings.filterwarnings("ignore")

app = Flask(__name__)

# Global variable to track radar generation status
generation_status = {"status": "Idle", "last_updated": ""}
# Global variable to track recently generated radar images
recent_images = []

def generate_radar_images():
    global generation_status, recent_images
    while True:
        try:
            generation_status["status"] = "Generating radar images..."
            generation_status["last_updated"] = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            recent_images.clear()  # Clear the list of recent images for this cycle

            datTime = dt.utcnow()
            year = datTime.strftime("%Y")
            month = datTime.strftime("%m")
            day = datTime.strftime("%d")
            hour = datTime.strftime("%H")
            timeStr = f'{year}{month}{day}{hour}'

            fs = fsspec.filesystem("s3", anon=True)

            stations = ['KLWX', 'KCCX', 'KJKL', 'KENX', 'KBGM', 'KTYX', 'KCXX', 'KBUF', 'KOKX', 'KFCX']
            output_dir = "static/radar"
            os.makedirs(output_dir, exist_ok=True)

            for site in stations:
                pattern = f's3://noaa-nexrad-level2/{year}/{month}/{day}/{site}/{site}{year}{month}{day}_*'
                files = sorted(fs.glob(pattern), reverse=True)

                if not files:
                    print(f"No files found for station {site}. Skipping...")
                    continue

                latest_file = files[0]
                print(f"Processing station {site}: {latest_file}")

                radar = pyart.io.read_nexrad_archive(f's3://{latest_file}')

                reflectivity_data = radar.fields['reflectivity']['data']
                reflectivity_data = np.ma.masked_less(reflectivity_data, 5)
                radar.fields['reflectivity']['data'] = reflectivity_data

                ref_norm, ref_cmap = ctables.registry.get_with_steps('NWSReflectivity', 5, 5)

                fig = plt.figure(figsize=(16, 16))
                ax = fig.add_subplot(1, 1, 1)

                display = pyart.graph.RadarMapDisplay(radar)

                display.plot_ppi(
                    'reflectivity',
                    0,
                    ax=ax,
                    cmap=ref_cmap,
                    norm=ref_norm,
                    vmin=15,
                    vmax=75,
                    colorbar_flag=False,
                    title=''
                )

                ax.set_axis_off()
                fig.patch.set_alpha(0)
                ax.patch.set_alpha(0)

                output_file = f"{output_dir}/{site}_Reflectivity_{timeStr}.png"
                plt.savefig(output_file, dpi=600, bbox_inches='tight', pad_inches=0, transparent=True)
                plt.close()

                print(f"Saved radar image to: {output_file}")

                # Add the generated image to the recent images list
                recent_images.append({
                    "station": site,
                    "image": output_file.replace('\\', '/'),
                    "timestamp": timeStr
                })

                gate_lats = radar.gate_latitude['data']
                gate_lons = radar.gate_longitude['data']

                flat_lats = gate_lats.flatten()
                flat_lons = gate_lons.flatten()

                bounds = {
                    "min_lat": float(np.min(flat_lats)),
                    "max_lat": float(np.max(flat_lats)),
                    "min_lon": float(np.min(flat_lons)),
                    "max_lon": float(np.max(flat_lons))
                }

                print(f"Geographic bounds of radar sweep for {site}: {bounds}")

                bounds_file = f"{output_dir}/{site}_Reflectivity_{timeStr}_bounds.json"
                with open(bounds_file, 'w') as f:
                    json.dump(bounds, f)

                print(f"Saved geographic bounds to: {bounds_file}")
            generation_status["status"] = "Idle"
        except Exception as e:
            generation_status["status"] = f"Error: {e}"
            print(f"Error in radar image generation: {e}")
        finally:
            # Ensure the function waits for 5 minutes before restarting
            time.sleep(5 * 60)


@app.route('/status')
def status():
    return jsonify(generation_status)


@app.route('/recent-images')
def recent_images_route():
    return jsonify(recent_images)


def get_latest_radar_image(station_id):
    radar_dir = os.path.join('static', 'radar')
    pattern = os.path.join(radar_dir, f"{station_id}_Reflectivity_*.png")
    files = glob.glob(pattern)
    if not files:
        return None
    latest_file = max(files, key=os.path.getmtime)
    return '/' + latest_file.replace('\\', '/')


@app.route('/')
def index():
    stations = [
        {
            'id': 'KLWX',
            'lat': 38.97611237,
            'lon': -77.48750305,
            'bounds': [
                [34.84664293135119, -82.80239033783172],
                [43.10558009613012, -72.17260865799442]
            ],
        },
        {
            'id': 'KCCX',
            'lat': 40.92316818,
            'lon': -78.00372314,
            'bounds': [
                [36.7934961034473, -83.47281512714993],
                [45.052827879608266, -72.53464276292041]
            ],
        },
        {
            'id': 'KJKL',
            'lat': 37.59083176,
            'lon': -83.31305695,
            'bounds': [
                [33.46135540824945, -88.52720127885047],
                [41.72030030972457, -78.09891722192692]
            ],
        },
        {
            'id': 'KENX',
            'lat': 42.58655548,
            'lon': -74.06408691,
            'bounds': [
                [38.457080718757574, -79.67698036449032],
                [46.71602144898151, -68.45119092906985]
            ],
        },
        {
            'id': 'KBGM',
            'lat': 42.19969559,
            'lon': -75.98472595,
            'bounds': [
                [38.07022598117396, -81.5630192883354],
                [46.329154213920454, -70.40643144099836]
            ],
        },
        {
            'id': 'KTYX',
            'lat': 43.75569534,
            'lon': -75.67986298,
            'bounds': [
                [39.62602639385995, -81.4018462239696],
                [47.885361249069334, -69.95786833537181]
            ],
        },
        {
            'id': 'KCXX',
            'lat': 44.51100159,
            'lon': -73.16642761,
            'bounds': [
                [40.381133240418805, -78.962610989264],
                [48.64086714911371, -67.37025417510782]
            ],
        },
        {
            'id': 'KBUF',
            'lat': 42.94878769,
            'lon': -78.73677826,
            'bounds': [
                [38.8185378506761, -84.38376230288945],
                [47.07903820864557, -73.08978881930115]
            ],
        },
        {
            'id': 'KOKX',
            'lat': 40.86552811,
            'lon': -72.86391449,
            'bounds': [
                [36.73585731888025, -78.32822702710388],
                [44.99519571758983, -67.39961517721764]
            ],
        },
        {
              'id': 'KFCX',
              'lat': 37.0243988,
              'lon': -80.27397156,
              'bounds': [
                  [32.894726263234276, -85.44936594328767],
                  [41.15426188081905, -75.09859179072811]
    ],
}

        
    ]  

    for s in stations:
        latest_img = get_latest_radar_image(s['id'])
        s['image_url'] = latest_img if latest_img else ''

    return render_template("index.html", stations=stations)



if __name__ == '__main__':
    # Start radar generation in a daemon thread (runs in background)
    thread = threading.Thread(target=generate_radar_images, daemon=True)
    thread.start()

    # Run Flask app
    # Use gunicorn if deployed on Render or similar platforms
    import os
    port = int(os.environ.get("PORT", 5000))  # Render sets the PORT environment variable
    app.run(host="0.0.0.0", port=port, debug=True)
