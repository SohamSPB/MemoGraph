import os
import csv
import hashlib
import piexif
import exifread

def get_md5(file_path):
	hash_md5 = hashlib.md5()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def clean_exif_string(byte_str):
	return byte_str.decode(errors='ignore').strip('\x00').strip()

def get_exif_piexif(image_path):
	try:
		exif_dict = piexif.load(image_path)
		return exif_dict
	except:
		return {}

def get_datetime(exif_dict):
	try:
		dt = clean_exif_string(exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal])
		return dt
	except:
		return ""

def get_device_model(exif_dict):
	try:
		make = clean_exif_string(exif_dict['0th'].get(piexif.ImageIFD.Make, b""))
		model = clean_exif_string(exif_dict['0th'].get(piexif.ImageIFD.Model, b""))
		return (make + " " + model).strip()
	except:
		return ""

def convert_gps(coord, ref):
	d, m, s = coord
	deg = d[0]/d[1] + (m[0]/m[1])/60 + (s[0]/s[1])/3600
	if ref in [b'S', b'W']:
		deg = -deg
	return deg

def get_gps(exif_dict):
	try:
		gps_info = exif_dict['GPS']
		lat = convert_gps(gps_info[piexif.GPSIFD.GPSLatitude], gps_info[piexif.GPSIFD.GPSLatitudeRef])
		lon = convert_gps(gps_info[piexif.GPSIFD.GPSLongitude], gps_info[piexif.GPSIFD.GPSLongitudeRef])
		return lat, lon
	except:
		return None, None

def extract_exif_fallback(image_path):
	try:
		with open(image_path, 'rb') as f:
			tags = exifread.process_file(f, details=False)
			dt = str(tags.get('EXIF DateTimeOriginal', '')).strip()
			make = str(tags.get('Image Make', '')).strip()
			model = str(tags.get('Image Model', '')).strip()

			gps_lat = tags.get('GPS GPSLatitude')
			gps_lat_ref = tags.get('GPS GPSLatitudeRef')
			gps_lon = tags.get('GPS GPSLongitude')
			gps_lon_ref = tags.get('GPS GPSLongitudeRef')

			def convert(coord, ref):
				parts = [float(x.num) / float(x.den) for x in coord.values]
				deg = parts[0] + parts[1]/60 + parts[2]/3600
				if ref.values[0] in ['S', 'W']:
					deg = -deg
				return deg

			lat = lon = None
			if gps_lat and gps_lon:
				lat = convert(gps_lat, gps_lat_ref)
				lon = convert(gps_lon, gps_lon_ref)

			device = (make + " " + model).strip()
			return dt, device, lat, lon
	except:
		return "", "", None, None

def scan_images(trip_folder, output_csv):
	rows = []
	for root, dirs, files in os.walk(trip_folder):
		for file in files:
			if file.lower().endswith((".jpg", ".jpeg", ".tiff", ".png", ".jfif")):
				full_path = os.path.join(root, file)
				md5sum = get_md5(full_path)

				exif_dict = get_exif_piexif(full_path)

				if exif_dict == {} or ('Exif' not in exif_dict or piexif.ExifIFD.DateTimeOriginal not in exif_dict['Exif']):
					datetime, device, lat, lon = extract_exif_fallback(full_path)
				else:
					datetime = get_datetime(exif_dict)
					device = get_device_model(exif_dict)
					lat, lon = get_gps(exif_dict)

				rel_path = os.path.relpath(full_path, trip_folder)

				row = [
					file, rel_path, md5sum, datetime, device, lat, lon,
					"",   # location_inferred
					"",   # day_number
					"",   # detected_objects
					"",   # species_tags
					"",   # faces_detected
					"",   # people_tags
					"",   # caption
					""    # notes
				]

				rows.append(row)

	headers = [
		"image_name", "local_path", "md5sum", "datetime_original", "device_model", "gps_lat", "gps_lon",
		"location_inferred", "day_number", "detected_objects", "species_tags",
		"faces_detected", "people_tags", "caption", "caption_ai", "notes"
	]

	with open(output_csv, "w", newline='') as f:
		writer = csv.writer(f)
		writer.writerow(headers)
		writer.writerows(rows)

# Example usage
if __name__ == "__main__":
	input_folder = "data/trips/test_trip"
	output_csv = os.path.join(input_folder, "labels.csv")
	scan_images(input_folder, output_csv)
