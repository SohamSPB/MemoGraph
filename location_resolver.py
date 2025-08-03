import os
import csv
from geopy.geocoders import Nominatim
from time import sleep

def resolve_location(lat, lon, geolocator):
	try:
		location = geolocator.reverse((lat, lon), language='en', timeout=10)
		if location:
			return location.address
	except:
		return None
	return None

def infer_trip_name_from_path(csv_path):
	# Use the folder name where CSV is located as trip hint
	folder = os.path.dirname(csv_path)
	trip_name = os.path.basename(folder).replace("_", " ")
	return trip_name

def fill_location(csv_path, trip_name_hint=None):
	geolocator = Nominatim(user_agent="photo_manager_location")

	if not trip_name_hint:
		trip_name_hint = infer_trip_name_from_path(csv_path)

	rows = []
	with open(csv_path, "r", newline='') as f:
		reader = csv.reader(f)
		headers = next(reader)

		col_index = {name: idx for idx, name in enumerate(headers)}

		gps_lat_idx = col_index.get("gps_lat")
		gps_lon_idx = col_index.get("gps_lon")
		location_idx = col_index.get("location_inferred")

		for row in reader:
			lat = row[gps_lat_idx]
			lon = row[gps_lon_idx]
			location_inferred = row[location_idx]

			if location_inferred.strip() == "":
				if lat != "" and lon != "":
					loc = resolve_location(float(lat), float(lon), geolocator)
					if loc:
						row[location_idx] = loc
					else:
						row[location_idx] = trip_name_hint
					sleep(1)  # Respect Nominatim limits
				else:
					row[location_idx] = trip_name_hint

			rows.append(row)

	with open(csv_path, "w", newline='') as f:
		writer = csv.writer(f)
		writer.writerow(headers)
		writer.writerows(rows)

# Example usage
if __name__ == "__main__":
	csv_path = "data/trips/test_trip/labels.csv"
	fill_location(csv_path)
