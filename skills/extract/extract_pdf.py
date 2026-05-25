from __future__ import annotations

from pathlib import Path

from skills.extract.extract_txt import TextExtractor, TextExtractorError


class PdfExtractorError(TextExtractorError):
    pass


class PdfExtractor(TextExtractor):
    def _read_document_text(self, source_path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise PdfExtractorError(
                "pypdf is not installed. Please run `python -m pip install -r requirements-dev.txt`."
            ) from exc

        try:
            reader = PdfReader(str(source_path))
        except Exception as exc:
            raise PdfExtractorError(f"PDF document in {source_path} could not be read.") from exc

        text_parts: list[str] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                text_parts.append(page_text)

        if not text_parts:
            raise PdfExtractorError(f"PDF document in {source_path} did not contain extractable text.")

        return "\n\n".join(text_parts)
