import json
import re

colab_path = r'C:\Users\Pihu\Downloads\youtube-voiceover-studio\youtube-voiceover-studio\youtube_voiceover_studio_colab.ipynb'

with open(colab_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'STYLE_PREFIXES' in ''.join(cell['source']):
        source_str = ''.join(cell['source'])
        
        # Replace default dropdown value
        source_str = source_str.replace("value='Photorealistic 8K'", "value='Clean Vector Economics (Milly / Cortex)'")
        
        # Add new style to STYLE_PREFIXES
        old_prefixes_start = "STYLE_PREFIXES = {\n"
        new_prefixes_start = (
            "STYLE_PREFIXES = {\n"
            "    'Clean Vector Economics (Milly / Cortex)': (\n"
            "        'Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork '\n"
            "        'with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. '\n"
            "        'Clean white background with generous negative space, keeping the composition uncluttered, highly readable, '\n"
            "        'and focused entirely on the main concept. Professional educational explainer style, balanced composition, '\n"
            "        'subtle flat shading, high contrast, modern vector finish, minimal distractions, no text, no logos, no watermarks. '\n"
            "    ),\n"
        )
        if "'Clean Vector Economics" not in source_str:
            source_str = source_str.replace(old_prefixes_start, new_prefixes_start)
            
        # Update prompt generator to default to Clean Vector Economics (Milly / Cortex)
        source_str = source_str.replace("STYLE_PREFIXES['Photorealistic 8K']", "STYLE_PREFIXES['Clean Vector Economics (Milly / Cortex)']")

        lines = [line + '\n' for line in source_str.split('\n')]
        if lines and lines[-1] == '\n':
            lines.pop()
        cell['source'] = lines

with open(colab_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("SUCCESS: Updated youtube_voiceover_studio_colab.ipynb with Clean Vector Economics (Milly / Cortex) style!")
