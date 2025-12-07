from docx import Document
import os
def register(server):
    @server.tool()
    def create_document(filename: str, title: str = None, author: str = None) -> dict:
        try:
            filename = os.path.abspath(filename)
            if not filename.endswith(".docx"):
                return {"error": "Filename must end with .docx"}
            if os.path.exists(filename):
                return {"error": f"File already exists: {filename}"}
            parent_dir = os.path.dirname(filename)
            if parent_dir and parent_dir.strip() and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            doc = Document()
            core = doc.core_properties
            if title:
                core.title = title
            if author:
                core.author = author
            doc.save(filename)
            return {
                "success": True,
                "filename": filename,
                "absolute_path": filename,
                "title": title if title else "",
                "author": author if author else "",
                "message": f"Created new Word document at {filename}"
            }
        except Exception as e:
            return {"error": f"Failed to create document: {str(e)}"}
