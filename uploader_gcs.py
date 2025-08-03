import os
import csv
import shutil
from google.cloud import storage


# ========== CONFIG ==========
GCS_BUCKET_NAME = "your-bucket-name"
BACKUP_DIR = "backup"
GCS_TRACKER_CSV = "uploaded_paths_gcs.csv"


# ========== HELPERS ==========
def ensure_dirs(path):
	dirname = os.path.dirname(path)
	if dirname and not os.path.exists(dirname):
		os.makedirs(dirname)


def load_csv_dict(csv_path):
	if not os.path.exists(csv_path):
		return []
	with open(csv_path, newline='', encoding='utf-8') as f:
		return list(csv.DictReader(f))


def save_csv_dict(csv_path, data, fieldnames):
	ensure_dirs(csv_path)
	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(data)


def append_to_csv(csv_path, new_rows, fieldnames):
	file_exists = os.path.exists(csv_path)
	with open(csv_path, "a", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		if not file_exists:
			writer.writeheader()
		writer.writerows(new_rows)


def upload_to_gcs(local_path, remote_path, bucket):
	blob = bucket.blob(remote_path)
	blob.upload_from_filename(local_path)
	return f"gs://{bucket.name}/{remote_path}"


def backup_local(local_path, trip_folder):
	rel_path = os.path.relpath(local_path, trip_folder)
	backup_path = os.path.join(BACKUP_DIR, rel_path)
	ensure_dirs(backup_path)
	shutil.copy2(local_path, backup_path)
	return backup_path


# ========== MAIN FUNCTION ==========
def upload_and_backup(csv_path):
	rows = load_csv_dict(csv_path)
	trip_folder = os.path.dirname(csv_path)
	gcs_client = storage.Client()
	bucket = gcs_client.bucket(GCS_BUCKET_NAME)

	updated_rows = []
	tracker_rows = []

	for row in rows:
		local_path = row.get("filepath")
		if not local_path or not os.path.exists(local_path):
			continue

		# Skip if already uploaded and backed up
		if row.get("cloud_path") and row.get("backup_path"):
			updated_rows.append(row)
			continue

		# Upload to GCS if not done
		cloud_path = row.get("cloud_path")
		if not cloud_path:
			rel_path = os.path.relpath(local_path, trip_folder)
			cloud_path = upload_to_gcs(local_path, rel_path, bucket)
			row["cloud_path"] = cloud_path

		# Backup locally if not done
		backup_path = row.get("backup_path")
		if not backup_path:
			backup_path = backup_local(local_path, trip_folder)
			row["backup_path"] = backup_path

		# Tracker entry
		tracker_rows.append({
			"filepath": local_path,
			"cloud_path": row["cloud_path"],
			"backup_path": row["backup_path"]
		})

		updated_rows.append(row)

	# Save updated labels.csv
	fieldnames = list(updated_rows[0].keys()) if updated_rows else []
	save_csv_dict(csv_path, updated_rows, fieldnames)

	# Append to GCS tracker
	if tracker_rows:
		append_to_csv(GCS_TRACKER_CSV, tracker_rows, ["filepath", "cloud_path", "backup_path"])


# Example usage
if __name__ == "__main__":
	csv_path = "data/trips/test_trip/labels.csv"
	upload_and_backup(csv_path)
