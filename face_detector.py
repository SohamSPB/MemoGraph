import os
import csv
import face_recognition

def detect_faces(image_path):
	try:
		image = face_recognition.load_image_file(image_path)
		face_locations = face_recognition.face_locations(image)
		return len(face_locations) > 0
	except Exception as e:
		print("Failed to process", image_path, e)
		return False

def process_csv(csv_path, image_folder):
	updated_rows = []

	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		fieldnames = reader.fieldnames

		if "faces_detected" not in fieldnames:
			fieldnames.append("faces_detected")

		for row in reader:
			image_path = os.path.join(image_folder, row['local_path'])
			face_found = 0

			if os.path.exists(image_path):
				if detect_faces(image_path):
					face_found = 1

			row["faces_detected"] = face_found
			updated_rows.append(row)

	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(updated_rows)

if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	process_csv(csv_file, folder)
