#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils_text.py

Lightweight text helpers for cleaning captions and species lists so that
CSV fields, blogs, and map popups read more naturally.
"""

from __future__ import annotations

import re
from typing import Iterable, List


_MULTISPACE_RE = re.compile(r"\s+")


def clean_caption(text: str | None) -> str:
	"""
	Apply simple heuristics to tidy up a caption:
	- Strip leading/trailing whitespace.
	- Collapse multiple spaces.
	- Fix duplicated determiners ("a an", "an a").
	- Remove immediate repetition of the last word.
	- Trim trailing punctuation.
	- Capitalize first character if it is a letter.
	"""
	if not text:
		return ""

	s = text.strip()
	if not s:
		return ""

	# Collapse whitespace
	s = _MULTISPACE_RE.sub(" ", s)

	# Fix "a an" / "an a" patterns
	s = re.sub(r"\b(a|an)\s+(a|an)\s+", r"\2 ", s, flags=re.IGNORECASE)

	# Remove immediate repetition of the last word (e.g., "valley valley")
	parts = s.split(" ")
	if len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
		parts = parts[:-1]
		s = " ".join(parts)

	# Trim repeated trailing punctuation
	s = re.sub(r"[,\.;:]+$", "", s).strip()

	if not s:
		return ""

	# Capitalize first character if it is a letter
	if s[0].islower():
		s = s[0].upper() + s[1:]

	return s


def clean_caption_list(texts: Iterable[str]) -> List[str]:
	"""Apply clean_caption to a list and drop empties, preserving order and uniqueness."""
	seen = set()
	out: List[str] = []
	for t in texts:
		c = clean_caption(t)
		if not c:
			continue
		if c in seen:
			continue
		seen.add(c)
		out.append(c)
	return out


def combine_captions_for_day(captions: Iterable[str], max_items: int = 2) -> str:
	"""
	Combine up to max_items cleaned captions into a short summary string.
	Uses '; ' as separator and appends '...' if there are more.
	"""
	cleaned = clean_caption_list(captions)
	if not cleaned:
		return ""
	head = cleaned[:max_items]
	summary = "; ".join(head)
	if len(cleaned) > max_items:
		summary += "..."
	return summary


def clean_species_list(species: Iterable[str]) -> List[str]:
	"""
	Filter and normalize a list of species-like strings for human-facing text.
	- Strips whitespace.
	- Removes obvious non-biological labels such as 'astrophotography photo',
	  'galaxy', 'nebula', etc.
	- Deduplicates while preserving order.
	"""
	bad_substrings = (
		"photo",
		"photograph",
		"astrophotography",
		"galaxy",
		"nebula",
		"night sky",
	)

	seen = set()
	out: List[str] = []
	for s in species:
		name = (s or "").strip()
		if not name:
			continue
		low = name.lower()
		if any(bad in low for bad in bad_substrings):
			continue
		if name in seen:
			continue
		seen.add(name)
		out.append(name)
	return out

