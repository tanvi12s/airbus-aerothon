from flask import Flask, render_template, request, redirect, url_for
import heapq
import requests
import folium
from geopy.distance import geodesic
import pandas as pd 

app = Flask(__name__)

file_path = 'iata-icao.csv' 
df = pd.read_csv(file_path)

# Function to search for latitude and longitude by IATA code
def get_latitude_longitude_by_iata(iata_code):
    # Search for the row with the given IATA code
    row = df[df['iata'] == iata_code]
    
    # Check if the row exists
    if not row.empty:
        # Retrieve latitude and longitude
        latitude = row.iloc[0]['latitude']
        longitude = row.iloc[0]['longitude']
        return latitude, longitude
    else:
        return None, None

# Define the haversine function to calculate great-circle distance
def haversine(lat1, lon1, lat2, lon2):
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers

# Implement the A* algorithm
def a_star(graph, start, goal):
    open_set = [(0, start)]
    came_from = {}
    g_score = {airport: float('inf') for airport in graph}
    g_score[start] = 0
    f_score = {airport: float('inf') for airport in graph}
    f_score[start] = haversine(*graph[start]['coords'], *graph[goal]['coords'])

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]

        for neighbor, distance in graph[current]['connections']:
            tentative_g_score = g_score[current] + distance
            if tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + haversine(*graph[neighbor]['coords'], *graph[goal]['coords'])
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    departure_airport = request.form['departure_airport']
    arrival_airport = request.form['arrival_airport']
    
    # Retrieve latitude and longitude for the given airports
    latitude1, longitude1 = get_latitude_longitude_by_iata(departure_airport)
    latitude2, longitude2 = get_latitude_longitude_by_iata(arrival_airport)

    if latitude1 is None or longitude1 is None or latitude2 is None or longitude2 is None:
        return "Invalid airport code(s). Please try again."
    
    # Retrieve flight data from the API
    api_url = f"http://api.aviationstack.com/v1/flights?access_key=ACCESS_KEY&dep_iata={departure_airport}&arr_iata={arrival_airport}"
    res = requests.get(api_url).json()
    data = res["data"][0]

    # Extract information and create the graph
    graph = {
        data['departure']['iata']: {
            'coords': (float(latitude1), float(longitude1)),
            'connections': [
                (data['arrival']['iata'], haversine(float(latitude1), float(longitude1),
                                                     float(latitude2), float(longitude2)))
            ]
        },
        data['arrival']['iata']: {
            'coords': (float(latitude2), float(longitude2)),
            'connections': []
        }
    }

    # Define start and goal
    start = data['departure']['iata']
    goal = data['arrival']['iata']

    # Get the path using A* algorithm
    path = a_star(graph, start, goal)
    
    # Plot the route on the map using folium
    route_map = plot_route(path, graph)
    route_map.save('templates/route.html')
    
    return redirect(url_for('index'))

def plot_route(path, graph):
    m = folium.Map(location=graph[path[0]]['coords'], zoom_start=4)

    for i in range(len(path) - 1):
        start_coords = graph[path[i]]['coords']
        end_coords = graph[path[i+1]]['coords']
        folium.Marker(location=start_coords, popup=path[i]).add_to(m)
        folium.Marker(location=end_coords, popup=path[i+1]).add_to(m)
        folium.PolyLine(locations=[start_coords, end_coords], color='blue').add_to(m)

    return m

if __name__ == '__main__':
    app.run(debug=True)
