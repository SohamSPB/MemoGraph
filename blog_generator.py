import csv
import os
import json
from datetime import datetime
from collections import defaultdict


def load_csv(csv_path):
	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		rows = list(reader)
	return rows


def group_by_day(rows):
	daywise = defaultdict(list)
	for row in rows:
		dt_str = row.get('datetime_original', '').strip()
		try:
			dt = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
			day_key = dt.strftime('%Y-%m-%d')
			row['_datetime'] = dt
			daywise[day_key].append(row)
		except:
			continue
	return dict(sorted(daywise.items()))


def describe_species(species):
	if not species:
		return ""
	if len(species) == 1:
		return "We spotted a " + species[0] + "."
	elif len(species) == 2:
		return "We saw a " + species[0] + " and a " + species[1] + "."
	else:
		return "We encountered species like " + ", ".join(species[:-1]) + ", and " + species[-1] + "."


def generate_day_paragraph(date, rows, day_number):
	rows.sort(key=lambda x: x['_datetime'])
	first = rows[0]
	last = rows[-1]

	# Basic captions
	captions = [r.get('caption', '').strip() for r in rows if r.get('caption')]
	# Detailed captions from AI
	ai_captions = [r.get('caption_ai', '').strip() for r in rows if r.get('caption_ai')]
	locations = list({r.get('location_inferred', '').strip() for r in rows if r.get('location_inferred')})
	species = set()
	for r in rows:
		tags = r.get('species_tags', '').strip()
		if tags:
			species.update([s.strip() for s in tags.split(',') if s.strip()])

	time_start = first['_datetime'].strftime('%I:%M %p')
	time_end = last['_datetime'].strftime('%I:%M %p')
	start_loc = first.get('location_inferred', 'an unknown place')
	end_loc = last.get('location_inferred', start_loc)

	paragraph = "**Day {0} – {1}**\n".format(day_number, date)
	paragraph += "Our journey began around {0} from {1}, and we concluded the day by {2} near {3}. ".format(
		time_start, start_loc, time_end, end_loc
	)

	if ai_captions:
		sample = " ".join(ai_captions[:2]) + ("..." if len(ai_captions) > 2 else "")
		paragraph += "Some scenes we captured include: {0} ".format(sample)
	elif captions:
		sample = " ".join(captions[:3]) + ("..." if len(captions) > 3 else "")
		paragraph += "Moments captured include: {0} ".format(sample)

	paragraph += describe_species(sorted(species)) + "\n\n"
	return paragraph


def generate_blog(csv_path, output_md_path, summary_json_path):
	rows = load_csv(csv_path)
	daywise = group_by_day(rows)
	blog_lines = ["# Trip Blog", ""]
	trip_summary = []

	for i, (day, day_rows) in enumerate(daywise.items()):
		day_num = i + 1
		summary = generate_day_paragraph(day, day_rows, day_num)
		blog_lines.append(summary)
		trip_summary.append({
			"date": day,
			"day_number": day_num,
			"num_photos": len(day_rows),
			"locations": list({r.get('location_inferred', '').strip() for r in day_rows if r.get('location_inferred')}),
			"species_spotted": sorted({s.strip() for r in day_rows for s in r.get('species_tags', '').split(',') if s.strip()}),
			"caption_samples": [r.get('caption_ai') or r.get('caption') for r in day_rows if r.get('caption_ai') or r.get('caption')][:3]
		})

	with open(output_md_path, 'w', encoding='utf-8') as f:
		f.write('\n'.join(blog_lines))

	with open(summary_json_path, 'w', encoding='utf-8') as f:
		json.dump(trip_summary, f, indent=2)


# Example usage
if __name__ == "__main__":
	folder = "data/trips/test_trip"
	csv_path = os.path.join(folder, "labels.csv")
	blog_path = os.path.join(folder, "blog.md")
	summary_path = os.path.join(folder, "trip_summary.json")

	generate_blog(csv_path, blog_path, summary_path)
