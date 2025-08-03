import csv
import os
import torch
import clip
from PIL import Image

# Predefined species lists (expand as needed)
species_prompts = {
	"birds": [
		"Sparrow", "Pigeon", "Eagle", "Vulture", "Kingfisher", "Bulbul", "Indian Roller", 
		"Crow", "Peacock", "Parrot", "Owl", "Woodpecker", "Hornbill", "Duck"
	],
	"plants": [
		"Rose", "Lotus", "Tulsi", "Bamboo", "Ficus", "Fern", "Banana plant", "Sunflower"
	],
	"insects": [
		"Butterfly", "Bee", "Dragonfly", "Ant", "Beetle", "Grasshopper"
	],
	"animals": [
		"Dog", "Cat", "Elephant", "Tiger", "Leopard", "Horse", "Cow", "Goat", "Sheep", "Yak", "Deer"
	]
}

# Flatten species list for CLIP
all_species = []
for category, items in species_prompts.items():
	all_species.extend(items)

# Initialize CLIP
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

def detect_species(image_path):
	image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
	text = clip.tokenize(all_species).to(device)

	with torch.no_grad():
		image_features = model.encode_image(image)
		text_features = model.encode_text(text)

		image_features /= image_features.norm(dim=-1, keepdim=True)
		text_features /= text_features.norm(dim=-1, keepdim=True)

		similarity = (100.0 * image_features @ text_features.T).squeeze(0)
		best_idx = similarity.argmax().item()
		best_match = all_species[best_idx]
		confidence = similarity[best_idx].item()

	return best_match, confidence

def process_csv(csv_path, image_folder):
	updated_rows = []

	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		fieldnames = reader.fieldnames

		if "species_tags" not in fieldnames:
			fieldnames.append("species_tags")

		for row in reader:
			caption = row.get("caption", "").lower()
			species_tag = ""

			# Check if caption contains relevant keywords
			if any(kw in caption for kw in ["bird", "flower", "plant", "tree", "insect", "animal", "dog", "cat"]):
				image_path = os.path.join(image_folder, row['local_path'])
				if os.path.exists(image_path):
					try:
						match, conf = detect_species(image_path)
						# Set threshold to avoid wrong matches (adjust as needed)
						if conf > 20.0:
							species_tag = match
						else:
							# Fallback to generic
							if "bird" in caption:
								species_tag = "bird"
							elif "flower" in caption or "plant" in caption or "tree" in caption:
								species_tag = "plant"
							elif "insect" in caption:
								species_tag = "insect"
							elif "animal" in caption or "dog" in caption or "cat" in caption:
								species_tag = "animal"
					except Exception as e:
						print("Failed to process", image_path, e)

			row["species_tags"] = species_tag
			updated_rows.append(row)

	# Write back to CSV
	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(updated_rows)

if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	process_csv(csv_file, folder)
