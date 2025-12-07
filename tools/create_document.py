from docx import Document
def create_document(filename: str, title: str = None, author: str = None):
    doc = Document()
    if title or author:
        core_properties = doc.core_properties
        if title:
            core_properties.title = title
        if author:
            core_properties.author = author
    doc.save(filename)
    return {"result": None}
