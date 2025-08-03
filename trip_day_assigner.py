import os
import csv
from datetime import datetime

def infer_trip_name_from_path(csv_path):
	folder = os.path.dirname(csv_path)
	trip_name = os.path.basename(folder).replace("_", " ")
	return trip_name

def assign_days(csv_path):
	rows = []
	with open(csv_path, "r", newline='') as f:
		reader = csv.reader(f)
		headers = next(reader)

		col_index = {name: idx for idx, name in enumerate(headers)}
		dt_idx = col_index.get("datetime_original")
		day_idx = col_index.get("day_number")

		datetimes = []

		for row in reader:
			dt_raw = row[dt_idx].strip()
			if dt_raw != "":
				try:
					dt = datetime.strptime(dt_raw, "%Y:%m:%d %H:%M:%S")
					datetimes.append((dt, row))
				except:
					datetimes.append((None, row))
			else:
				datetimes.append((None, row))

	# Find the earliest date as trip start
	valid_dates = [dt for dt, _ in datetimes if dt is not None]

	if len(valid_dates) == 0:
		print("No valid datetime found in CSV.")
		return

	trip_start = min(valid_dates)

	# Assign day numbers
	for dt, row in datetimes:
		if dt is None:
			row[day_idx] = ""
		else:
			day_number = (dt.date() - trip_start.date()).days + 1
			row[day_idx] = str(day_number)
		rows.append(row)

	# Write back
	with open(csv_path, "w", newline='') as f:
		writer = csv.writer(f)
		writer.writerow(headers)
		writer.writerows(rows)

	trip_name = infer_trip_name_from_path(csv_path)
	print("Trip day numbers assigned for", trip_name)

# Example usage
if __name__ == "__main__":
	csv_path = "data/trips/test_trip/labels.csv"
	assign_days(csv_path)
