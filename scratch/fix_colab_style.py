import json

colab_path = r'C:\Users\Pihu\Downloads\youtube-voiceover-studio\youtube-voiceover-studio\youtube_voiceover_studio_colab.ipynb'

with open(colab_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'STYLE_PREFIXES' in ''.join(cell['source']):
        source_str = ''.join(cell['source'])
        
        # Correct STYLE_PREFIXES dict to include 'Clean Vector Economics (Milly / Cortex)'
        old_prefixes = "STYLE_PREFIXES = {\n"
        new_prefixes = (
            "STYLE_PREFIXES = {\n"
            "    'Clean Vector Economics (Milly / Cortex)': (\n"
            "        'Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork '\n"
            "        'with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. '\n"
            "        'Clean white background with generous negative space, keeping the composition uncluttered, highly readable, '\n"
            "        'and focused entirely on the main concept. Professional educational explainer style, balanced composition, '\n"
            "        'subtle flat shading, high contrast, modern vector finish, minimal distractions, no text, no logos, no watermarks. '\n"
            "    ),\n"
        )
        
        if "'Clean Vector Economics (Milly / Cortex)'" not in source_str:
            source_str = source_str.replace(old_prefixes, new_prefixes)
        
        lines = [line + '\n' for line in source_str.split('\n')]
        if lines and lines[-1] == '\n':
            lines.pop()
        cell['source'] = lines

with open(colab_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("SUCCESS: Added 'Clean Vector Economics (Milly / Cortex)' to STYLE_PREFIXES in youtube_voiceover_studio_colab.ipynb!")
