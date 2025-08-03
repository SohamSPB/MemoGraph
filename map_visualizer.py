import csv
import os
import folium
from folium.plugins import MarkerCluster

def load_geo_points(csv_path, image_folder):
	points = []
	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			lat = row.get("gps_lat")
			lon = row.get("gps_lon")
			if lat and lon:
				try:
					lat, lon = float(lat), float(lon)
					caption = row.get("caption", "")
					img_path = os.path.join(image_folder, row.get("local_path", ""))
					if os.path.exists(img_path):
						img_html = "<img src='{0}' width='150'/>".format(img_path.replace("\\", "/"))
					else:
						img_html = ""
					popup_html = "<b>{0}</b><br/>{1}".format(caption, img_html)
					points.append((lat, lon, popup_html))
				except:
					continue
	return points

def create_map(points, output_path):
	if not points:
		print("No GPS-tagged photos found.")
		return
	center = points[0][:2]
	m = folium.Map(location=center, zoom_start=12)
	mc = MarkerCluster().add_to(m)

	for lat, lon, popup in points:
		folium.Marker(location=[lat, lon], popup=popup).add_to(mc)

	m.save(output_path)
	print("Map saved to:", output_path)

# Example usage
if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	map_file = os.path.join(folder, "trip_map.html")

	points = load_geo_points(csv_file, folder)
	create_map(points, map_file)
