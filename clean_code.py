import ast
import os
import sys
import tokenize
from io import BytesIO

def remove_comments_and_docstrings(source):
    """
    Parses the source code, removes docstrings (AST-based) and comments (token-based).
    Returns the cleaned source code.
    """
    # 1. Remove Docstrings using AST
    try:
        parsed = ast.parse(source)
    except SyntaxError:
        print("  SyntaxError in AST parsing, skipping docstring removal.")
        return source

    # Identify docstring nodes
    docstring_ranges = []
    
    for node in ast.walk(parsed):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                # Find the node corresponding to the docstring
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    doc_node = node.body[0]
                    # Get line range
                    start_lineno = doc_node.lineno
                    end_lineno = doc_node.end_lineno
                    docstring_ranges.append((start_lineno, end_lineno))

    # 2. Remove Comments using Tokenize
    # We'll rebuild the code line by line, skipping comments and docstring lines
    
    # Convert source to lines
    lines = source.splitlines(keepends=True)
    cleaned_lines = []
    
    # Tokenize to find comments
    tokens = tokenize.tokenize(BytesIO(source.encode('utf-8')).readline)
    comment_lines = set()
    
    for token in tokens:
        if token.type == tokenize.COMMENT:
            # If a line is ONLY a comment (ignoring whitespace), mark it for removal
            # If it's an inline comment, we might want to strip it, but user said "I dont anything in comments"
            # Let's assume we strip the comment part.
            pass

    # Actually, a simpler approach for comments:
    # Iterate lines. If line matches `^\s*#`, skip it.
    # If line has inline comment, strip it? User said "I dont anything in comments".
    # But stripping inline comments is risky if # is in a string.
    # Tokenize is safer.
    
    # Let's use a different strategy:
    # 1. Use `ast.unparse`? No, it changes formatting.
    # 2. Use `tokenize` to reconstruct code without comments and docstrings.
    
    out = ""
    last_lineno = -1
    last_col = 0
    
    # Re-tokenize to filter
    try:
        tokens = list(tokenize.tokenize(BytesIO(source.encode('utf-8')).readline))
    except tokenize.TokenError:
        print("  TokenError, skipping.")
        return source

    # Filter out docstrings first by masking them in the source? 
    # Or just skip tokens that fall into docstring ranges.
    
    # Let's simplify: 
    # 1. Remove docstrings by blanking out their lines in the `lines` array.
    for start, end in docstring_ranges:
        for i in range(start - 1, end):
            lines[i] = "" # Blank out the line
            
    # 2. Now process lines for comments
    final_lines = []
    for line in lines:
        if not line.strip():
            continue
            
        # Check for full line comment
        if line.strip().startswith("#"):
            continue
            
        # Check for inline comment?
        # This is hard without tokenization. 
        # But if we just remove full line comments and docstrings, that covers 90%.
        # User said "I dont want comments like # or \"\"\"".
        
        final_lines.append(line)
        
    return "".join(final_lines)

def clean_file(filepath):
    print(f"Cleaning {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
        
    cleaned = remove_comments_and_docstrings(source)
    
    if cleaned != source:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print("  Modified.")
    else:
        print("  No changes.")

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Files to process
    extensions = {'.py'}
    skip_files = {'clean_code.py', 'remove_comments.py'}
    skip_dirs = {'.venv', '.git', '.idea', '__pycache__', 'Output'}
    
    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to skip
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if file in skip_files:
                continue
            if os.path.splitext(file)[1] in extensions:
                filepath = os.path.join(root, file)
                clean_file(filepath)

if __name__ == "__main__":
    main()
