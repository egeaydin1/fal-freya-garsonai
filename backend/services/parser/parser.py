import re

def parse_sentences(text: str) -> list[str]:
	# Split only on sentence-ending punctuation
	parts = re.split(r"[.!?]+", text)

	# Clean, normalize, and remove empties
	sentences = []
	for part in parts:
		cleaned = part.strip()
		if cleaned:
			# Optional: capitalize first letter
			cleaned = cleaned[0].upper() + cleaned[1:]
			sentences.append(cleaned)

	return sentences

