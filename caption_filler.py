import csv
import os
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
# import nltk

# # Download NLTK POS Tagger (first run only)
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')

# def extract_nouns(text):
# 	words = nltk.word_tokenize(text)
# 	tags = nltk.pos_tag(words)
# 	nouns = [word.lower() for word, pos in tags if pos.startswith("NN")]
# 	return list(set(nouns))

def clean_row(row, fieldnames):
	# Keep only known fields, remove None keys or unexpected keys
	return {k: row[k] for k in fieldnames if k in row}

def is_empty_row(row):
	# Check if the row is completely empty (all fields None or empty strings)
	return all(v is None or str(v).strip() == "" for v in row.values())

def fill_captions(csv_path, image_folder):
	# Load BLIP model
	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

	# Load CSV
	rows = []
	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		fieldnames = reader.fieldnames

		# Ensure 'caption' and 'detected_objects' exist
		if 'caption' not in fieldnames:
			fieldnames.append('caption')
		if 'detected_objects' not in fieldnames:
			fieldnames.append('detected_objects')

		for row in reader:
			if is_empty_row(row):
				continue  # Skip blank lines
			
			image_path = os.path.join(image_folder, row['local_path'])
			if os.path.exists(image_path):
				try:
					image = Image.open(image_path).convert('RGB')
					inputs = processor(image, return_tensors="pt")
					out = model.generate(**inputs)
					caption = processor.decode(out[0], skip_special_tokens=True)

					row['caption'] = caption
					# row['detected_objects'] = ', '.join(extract_nouns(caption))
				except Exception as e:
					print("Failed on", image_path, e)
			else:
				print("Missing image:", image_path)

			cleaned_row = clean_row(row, fieldnames)
			rows.append(cleaned_row)

	# Write updated CSV
	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)

if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	fill_captions(csv_file, folder)
