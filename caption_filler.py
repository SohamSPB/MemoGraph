import csv
import os
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
# import nltk
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')

def clean_row(row, fieldnames):
	return {k: row[k] for k in fieldnames if k in row}

def is_empty_row(row):
	return all(v is None or str(v).strip() == "" for v in row.values())

# def extract_nouns(text):
# 	words = nltk.word_tokenize(text)
# 	tags = nltk.pos_tag(words)
# 	return [word.lower() for word, pos in tags if pos.startswith("NN")]

def generate_multiple_captions(image, processor, model, num_variations=3):
	captions = []
	inputs = processor(image, return_tensors="pt").to(model.device)
	for _ in range(num_variations):
		output = model.generate(**inputs, do_sample=True, top_k=50, max_length=40)
		caption = processor.decode(output[0], skip_special_tokens=True)
		captions.append(caption)
	return list(set(captions))  # remove duplicates

def fill_captions(csv_path, image_folder):
	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
	model.eval()

	rows = []
	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		fieldnames = reader.fieldnames

		if 'caption' not in fieldnames:
			fieldnames.append('caption')
		if 'caption_samples' not in fieldnames:
			fieldnames.append('caption_samples')
		if 'detected_objects' not in fieldnames:
			fieldnames.append('detected_objects')

		for row in reader:
			if is_empty_row(row):
				continue

			image_path = os.path.join(image_folder, row['local_path'])
			if os.path.exists(image_path):
				try:
					image = Image.open(image_path).convert('RGB')
					captions = generate_multiple_captions(image, processor, model, num_variations=4)
					row['caption'] = captions[0]
					row['caption_samples'] = "|".join(captions)

					# Optional object noun detection
					# all_nouns = []
					# for cap in captions:
					# 	all_nouns.extend(extract_nouns(cap))
					# row['detected_objects'] = ', '.join(sorted(set(all_nouns)))

				except Exception as e:
					print("Failed on", image_path, e)
			else:
				print("Missing image:", image_path)

			cleaned_row = clean_row(row, fieldnames)
			rows.append(cleaned_row)

	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)

if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	fill_captions(csv_file, folder)
