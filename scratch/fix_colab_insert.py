import json

colab_path = r'C:\Users\Pihu\Downloads\youtube-voiceover-studio\youtube-voiceover-studio\youtube_voiceover_studio_colab.ipynb'

with open(colab_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'STYLE_PREFIXES = {' in ''.join(cell['source']):
        src = cell['source']
        for i, line in enumerate(src):
            if 'STYLE_PREFIXES = {' in line:
                new_entry = [
                    "    'Clean Vector Economics (Milly / Cortex)': (\n",
                    "        'Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork '\n",
                    "        'with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. '\n",
                    "        'Clean white background with generous negative space, keeping the composition uncluttered, highly readable, '\n",
                    "        'and focused entirely on the main concept. Professional educational explainer style, balanced composition, '\n",
                    "        'subtle flat shading, high contrast, modern vector finish, minimal distractions, no text, no logos, no watermarks. '\n",
                    "    ),\n"
                ]
                src[i+1:i+1] = new_entry
                break

with open(colab_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("SUCCESS: Inserted 'Clean Vector Economics (Milly / Cortex)' into STYLE_PREFIXES dict!")
