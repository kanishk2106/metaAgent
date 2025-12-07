import re
def register(server):
    @server.tool()
    def summarize_text(
        text: str,
        max_preview_length: int = 200,
        max_text_length: int = 50_000
    ) -> dict:
        try:
            if not isinstance(text, str):
                return {"error": "Text must be a string"}
            if not text.strip():
                return {"error": "No text provided"}
            if len(text) > max_text_length:
                return {
                    "error": f"Text too long ({len(text)} chars). "
                             f"Max allowed is {max_text_length} characters."
                }
            lines = text.split("\n")
            words = re.findall(r"\b\w+\b", text)
            unique_words = {w.lower() for w in words}
            avg_word_length = (
                sum(len(w) for w in words) / len(words) if words else 0
            )
            preview = text[:max_preview_length]
            if len(text) > max_preview_length:
                preview = preview.rstrip() + "..."
            return {
                "success": True,
                "statistics": {
                    "total_characters": len(text),
                    "total_lines": len(lines),
                    "total_words": len(words),
                    "unique_words": len(unique_words),
                    "average_word_length": round(avg_word_length, 2),
                    "longest_line_length": max(len(line) for line in lines),
                },
                "preview": preview,
                "first_line": lines[0] if lines else "",
                "last_line": lines[-1] if lines else "",
                "message": "Text summarized successfully"
            }
        except Exception as e:
            return {"error": f"Error summarizing text: {str(e)}"}
