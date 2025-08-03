import os
import csv
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

def get_column_indices(header):
	return {name: idx for idx, name in enumerate(header)}

def generate_ai_captions(csv_path, trip_folder):
	device = "cuda" if torch.cuda.is_available() else "cpu"

	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

	updated_rows = []
	with open(csv_path, "r", newline='', encoding='utf-8') as f:
		reader = csv.reader(f)
		rows = list(reader)

	header = rows[0]
	col_idx = get_column_indices(header)

	if "caption_ai" not in col_idx:
		header.append("caption_ai")
		col_idx["caption_ai"] = len(header) - 1

	updated_rows.append(header)

	for row in rows[1:]:
		image_path = os.path.join(trip_folder, row[col_idx["local_path"]])
		try:
			raw_image = Image.open(image_path).convert("RGB")
			inputs = processor(raw_image, return_tensors="pt").to(device)

			with torch.no_grad():
				output = model.generate(**inputs)
				caption = processor.decode(output[0], skip_special_tokens=True)

			row.append(caption)
		except Exception:
			row.append("")

		updated_rows.append(row)

	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerows(updated_rows)

if __name__ == "__main__":
	trip_folder = "data/trips/test_trip"
	csv_path = os.path.join(trip_folder, "labels.csv")
	generate_ai_captions(csv_path, trip_folder)
