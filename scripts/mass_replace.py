import os

def replace_in_file(filepath):
    with open(filepath, 'r') as file:
        content = file.read()
        
    original = content
    content = content.replace("Blindspot", "Blindspot")
    content = content.replace("", "")
    content = content.replace('version="1.0.0"', 'version="1.0.0"')
    
    if content != original:
        with open(filepath, 'w') as file:
            file.write(content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('/Users/dinesh/Vibeathon/blindspot'):
    if '.git' in root or 'node_modules' in root or '__pycache__' in root or '.venv' in root:
        continue
    for file in files:
        if file.endswith(('.py', '.md', '.html', '.sh', '.toml')):
            replace_in_file(os.path.join(root, file))
