import argparse
import os
import sys
import xml.etree.ElementTree as ET
import math
from datetime import datetime
import matplotlib.pyplot as plt

# GPX Namespace definition
GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}
METERS_PER_DEGREE_AT_EQUATOR = 111320.0 
DEFAULT_HDOP = 4.0

def _get_weights(hdops):
    """Calculates weights as 1/HDOP^2."""
    weights = []
    for hdop in hdops:
        hdop = hdop if hdop > 0 else DEFAULT_HDOP
        weights.append(1.0 / (hdop ** 2))
    return weights

def calculate_weighted_mean(values, hdops):
    """Calculates the weighted mean."""
    if not values: return 0.0
    weights = _get_weights(hdops)
    weighted_sum = sum(w * x for w, x in zip(weights, values))
    sum_of_weights = sum(weights)
    return weighted_sum / sum_of_weights if sum_of_weights != 0 else 0.0

def calculate_weighted_sample_stddev(values, hdops, weighted_mean):
    """Calculates weighted sample standard deviation (N-1)."""
    if len(values) < 2: return 0.0
    weights = _get_weights(hdops)
    weighted_variance_num = sum(w * (x - weighted_mean)**2 for w, x in zip(weights, values))
    sum_w = sum(weights)
    if sum_w == 0: return 0.0
    n = len(values)
    # Corrected for sample bias: (Sum/Sum_w) * (N/(N-1))
    variance = (weighted_variance_num / sum_w) * (n / (n - 1))
    return math.sqrt(variance)

def convert_degrees_to_meters(degrees_lat, degrees_lon, mean_lat):
    """Converts degree differences to meters."""
    meters_lat = degrees_lat * METERS_PER_DEGREE_AT_EQUATOR
    meters_lon = degrees_lon * METERS_PER_DEGREE_AT_EQUATOR * math.cos(math.radians(mean_lat))
    return meters_lat, meters_lon

def calculate_empirical_cep(lat_data, lon_data, mean_lat, mean_lon, percentile=0.6826):
    """Numerically finds the radius containing a specific percentage of points."""
    if not lat_data: return 0.0
    distances_m = []
    cos_lat = math.cos(math.radians(mean_lat))
    for lat, lon in zip(lat_data, lon_data):
        dy = (lat - mean_lat) * METERS_PER_DEGREE_AT_EQUATOR
        dx = (lon - mean_lon) * METERS_PER_DEGREE_AT_EQUATOR * cos_lat
        distances_m.append(math.sqrt(dx**2 + dy**2))
    distances_m.sort()
    idx = min(len(distances_m) - 1, max(0, int(len(distances_m) * percentile)))
    return distances_m[idx]

def get_xml_element_text(element, tag, namespace):
    child = element.find(tag, namespace)
    return child.text.strip() if child is not None and child.text else None

def analyze_gpx_file(gpx_path):
    print(f"--- Analyzing GPX File: {os.path.basename(gpx_path)} ---")
    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error: Could not parse GPX file. {e}")
        return

    tracks = root.findall('gpx:trk', GPX_NS)
    if not tracks: return

    segment_evolution_data = []

    for trk_idx, trk in enumerate(tracks, 1):
        trk_name = get_xml_element_text(trk, 'gpx:name', GPX_NS) or f"Track {trk_idx}"
        segments = trk.findall('gpx:trkseg', GPX_NS)
        
        for seg_idx, trkseg in enumerate(segments, 1):
            lat_data, lon_data, hdop_data, times = [], [], [], []
            
            for pt in trkseg.findall('gpx:trkpt', GPX_NS):
                try:
                    lat, lon = float(pt.attrib.get('lat')), float(pt.attrib.get('lon'))
                    time_str = get_xml_element_text(pt, 'gpx:time', GPX_NS)
                    hdop_text = get_xml_element_text(pt, 'gpx:hdop', GPX_NS)
                    hdop = float(hdop_text) if hdop_text else DEFAULT_HDOP
                    
                    if hdop <= 4.0 and time_str:
                        dt = datetime.strptime(time_str.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
                        lat_data.append(lat)
                        lon_data.append(lon)
                        hdop_data.append(hdop)
                        times.append(dt)
                except: continue

            if len(lat_data) < 2: continue

            # 1. Calculate Final Stats
            mean_lat = calculate_weighted_mean(lat_data, hdop_data)
            mean_lon = calculate_weighted_mean(lon_data, hdop_data)
            std_lat = calculate_weighted_sample_stddev(lat_data, hdop_data, mean_lat)
            std_lon = calculate_weighted_sample_stddev(lon_data, hdop_data, mean_lon)
            std_lat_m, std_lon_m = convert_degrees_to_meters(std_lat, std_lon, mean_lat)
            
            num_cep = calculate_empirical_cep(lat_data, lon_data, mean_lat, mean_lon, 0.6826)
            theoretical_cep = math.sqrt(std_lat_m**2 + std_lon_m**2)

            print(f"\n[ {trk_name} - Segment {seg_idx} ]")
            print(f"  Points Analyzed: {len(lat_data)}")
            print(f"  Sample StdDev: Lat={std_lat_m:.2f}m, Lon={std_lon_m:.2f}m")
            print(f"  Numerical CEP (68.26%): {num_cep:.2f} m")
            print(f"  Theoretical CEP (Formulaic): {theoretical_cep:.2f} m")
            print(f"  Difference (Actual vs Theory): {abs(num_cep - theoretical_cep):.2f} m")

            # 2. Calculate CEP Evolution (from 30s onward)
            start_time = times[0]
            evol_x, evol_y = [], []
            for i in range(2, len(lat_data) + 1):
                elapsed = (times[i-1] - start_time).total_seconds()
                if elapsed >= 30:
                    # Current subset statistics
                    sub_lat, sub_lon, sub_hdop = lat_data[:i], lon_data[:i], hdop_data[:i]
                    m_lat = calculate_weighted_mean(sub_lat, sub_hdop)
                    m_lon = calculate_weighted_mean(sub_lon, sub_hdop)
                    cep = calculate_empirical_cep(sub_lat, sub_lon, m_lat, m_lon, 0.6826)
                    evol_x.append(elapsed)
                    evol_y.append(cep)
            
            if evol_x:
                segment_evolution_data.append((f"{trk_name} S{seg_idx}", evol_x, evol_y))

    # --- PLOTTING ---
    if segment_evolution_data:
        plt.figure(figsize=(10, 6))
        for label, x, y in segment_evolution_data:
            plt.plot(x, y, label=label)
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        plt.xlabel("Seconds from Start")
        plt.ylabel("Cumulative Numerical CEP (68.26%) [m]")
        plt.title("Evolution of GPS Precision (CEP) Over Time")
        plt.legend()
        plt.grid(True, which='both', linestyle='--', alpha=0.5)
        plt.savefig("cep_evolution.png")
        print(f"\nPlot saved as 'cep_evolution.png'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPX Weighted Mean and CEP Analysis")
    parser.add_argument("gpx_file", help="Path to GPX file")
    args = parser.parse_args()
    analyze_gpx_file(args.gpx_file)