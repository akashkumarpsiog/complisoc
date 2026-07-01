PUBLICATION_THRESHOLD = 0.70


def calculate_final_confidence(gemini_confidence: float, groq_agreement: float) -> float:
    return round((gemini_confidence * 0.6) + (groq_agreement * 0.4), 4)


def publication_status(final_confidence: float) -> str:
    return "published" if final_confidence >= PUBLICATION_THRESHOLD else "manual_review"

