import os
import csv
import torch
import clip
from PIL import Image

def get_column_indices(header):
	return {name: idx for idx, name in enumerate(header)}

def label_images(csv_path, trip_folder):
	device = "cuda" if torch.cuda.is_available() else "cpu"
	model, preprocess = clip.load("ViT-B/32", device=device)

	# # Define candidate labels
	# concepts = [
	#     "a single bird", "a flock of birds", "a flower", "a blooming flower", "a green plant", "a tree", 
	#     "a mountain range", "a snowy mountain", "a lake", "a calm lake", "a scenic landscape",
	#     "a person", "a group of people", "a waterfall", "a dense forest", "an insect", "a wild animal", 
	#     "a domestic cat", "a domestic dog", "a night sky", "stars", "the Milky Way", 
	#     "a galaxy", "a nebula", "a star cluster", "an astrophotography image", "the moon", 
	#     "the sun", "a solar eclipse", "Andromeda galaxy", "Orion nebula", "deep sky object",
	#     "a sunrise", "a sunset", "a cityscape", "a modern building", "a historical monument", 
	#     "a food dish", "a traditional meal", "a campsite"
	# ]

	# Define candidate labels
	concepts = [
		# Nature and people
		"a bird", "a flower", "a plant", "a tree", "a mountain", "a lake", "a landscape",
		"a person", "a group of people", "a waterfall", "a forest", "an insect", "an animal", "a cat", "a dog",
		
		# Astro specific
		"a night sky", "stars", "the Milky Way", "the galaxy", "a nebula", "a star cluster",
		"an astrophotography photo", "the moon", "the sun", "an eclipse", "the Andromeda galaxy", "the Orion nebula", "deep sky objects",
		
		# Other scenes
		"a sunrise", "a sunset", "a cityscape", "a building", "a monument", "a food dish"
	]
	
	text_tokens = clip.tokenize(concepts).to(device)

	updated_rows = []
	with open(csv_path, "r", newline='', encoding='utf-8') as f:
		reader = csv.reader(f)
		rows = list(reader)

	header = rows[0]
	col_idx = get_column_indices(header)

	# Ensure required columns exist, or append them
	for col in ["detected_objects", "species_tags"]:
		if col not in col_idx:
			header.append(col)
			col_idx[col] = len(header) - 1

	updated_rows.append(header)

	for row in rows[1:]:
		image_path = os.path.join(trip_folder, row[col_idx["local_path"]])
		try:
			image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
			with torch.no_grad():
				image_features = model.encode_image(image)
				text_features = model.encode_text(text_tokens)

				# Compute cosine similarity
				image_features /= image_features.norm(dim=-1, keepdim=True)
				text_features /= text_features.norm(dim=-1, keepdim=True)

				similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

				# Select top matches
				topk = similarity[0].topk(5)
				top_labels = [concepts[i] for i in topk.indices.cpu().numpy()]

				# Separate species tags and general objects
				species = []
				objects = []

				for label in top_labels:
					if any(x in label for x in ["bird", "flower", "insect", "animal", "cat", "dog", "plant"]):
						species.append(label)
					elif any(x in label for x in ["galaxy", "nebula", "Milky Way", "stars", "astrophotography", "star cluster", "eclipse", "moon"]):
						species.append(label)
					else:
						objects.append(label)
				
				row += ["; ".join(objects), "; ".join(species)]

		except Exception:
			# Fallback if image can't be processed
			row += ["", ""]

		updated_rows.append(row)

	# Write back to CSV
	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerows(updated_rows)

if __name__ == "__main__":
	trip_folder = "data/trips/test_trip"
	csv_path = os.path.join(trip_folder, "labels.csv")
	label_images(csv_path, trip_folder)
