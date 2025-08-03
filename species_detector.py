import csv
import os
import torch
import clip
from PIL import Image

# Predefined species lists (expand as needed)
species_prompts = {
	"birds": ["Sparrow", "Pigeon", "Eagle", "Vulture", "Kingfisher", "Bulbul", "Indian Roller", "Crow", "Peacock", "Parrot", "Owl", "Woodpecker", "Hornbill", "Duck"],
	"plants": ["Rose", "Lotus", "Tulsi", "Bamboo", "Ficus", "Fern", "Banana plant", "Sunflower"],
	"insects": ["Butterfly", "Bee", "Dragonfly", "Ant", "Beetle", "Grasshopper"],
	"animals": ["Dog", "Cat", "Elephant", "Tiger", "Leopard", "Horse", "Cow", "Goat", "Sheep", "Yak", "Deer"]
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
		confidences = similarity.tolist()

	matches = [(all_species[i], conf) for i, conf in enumerate(confidences) if conf > 20.0]
	matches.sort(key=lambda x: -x[1])
	return [match for match, _ in matches]

def process_csv(csv_path, image_folder):
	updated_rows = []

	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		fieldnames = reader.fieldnames

		# Safety check: Remove None and deduplicate
		fieldnames = [f for f in fieldnames if f is not None]
		if "species_tags" not in fieldnames:
			fieldnames.append("species_tags")

		for row in reader:
			# Clean keys: remove any unexpected ones
			clean_row = {k: v for k, v in row.items() if k in fieldnames and k is not None}
			species_tags = []

			caption = clean_row.get("caption", "").lower()

			if any(kw in caption for kw in ["bird", "flower", "plant", "tree", "insect", "animal", "dog", "cat", "forest"]):
				image_path = os.path.join(image_folder, clean_row.get('local_path', ''))
				if os.path.exists(image_path):
					try:
						tags = detect_species(image_path)
						species_tags = tags[:3] if tags else []
					except Exception as e:
						print("Failed to process", image_path, e)

			clean_row["species_tags"] = ", ".join(species_tags)
			updated_rows.append(clean_row)

	with open(csv_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(updated_rows)

if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_file = os.path.join(folder, "labels.csv")
	process_csv(csv_file, folder)
