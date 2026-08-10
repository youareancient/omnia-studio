import json
import re

colab_path = r'C:\Users\Pihu\Downloads\youtube-voiceover-studio\youtube-voiceover-studio\youtube_voiceover_studio_colab.ipynb'

with open(colab_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'STYLE_PREFIXES' in ''.join(cell['source']):
        source_str = ''.join(cell['source'])
        
        # Replace default dropdown value
        source_str = source_str.replace("value='2D Cartoon / Explainer'", "value='Photorealistic 8K'")
        
        # Replace build_zenn_image_prompt references
        source_str = source_str.replace('build_zenn_image_prompt', 'build_photorealistic_image_prompt')
        
        # Update Photorealistic 8K prefix string
        old_prefixes = "'Photorealistic 8K': 'Hyperrealistic 8K documentary photography, cinematic lighting, 35mm lens, depth of field, detailed. '"
        new_prefixes = ("'Photorealistic 8K': (\n"
                        "        'Hyperrealistic 8K ultra-detailed documentary photography, shot on 35mm lens, cinematic film lighting, '\n"
                        "        'shallow depth of field, photorealistic textures, 8k resolution, award-winning cinematography, hyper-detailed, '\n"
                        "        'natural ambient shadows, cinematic color grading, 16:9 widescreen aspect ratio. '\n"
                        "        'STRICT NO CARTOON RULE: ABSOLUTELY NO 2D CARTOONS, NO DRAWINGS, NO STICK FIGURES, NO WHITEBOARD ARTWORK, NO INFOGRAPHIC TEXTBOXES. '\n"
                        "    )")
        source_str = source_str.replace(old_prefixes, new_prefixes)
        
        # Update Presenter and Suffix
        source_str = source_str.replace("ZENN_CHARACTER_SNIPPET = (", "REALISTIC_PRESENTER_SNIPPET = (")
        source_str = source_str.replace("ZENN_SUFFIX = (", "REALISTIC_SUFFIX = (")
        
        old_char_body = (
            "    'Featuring the central recurring character: a simple hand-drawn expressive 2D stick figure guide with clean black ink outlines, '\n"
            "    'wearing a vibrant crimson-red backwards baseball cap, an eye-catching electric-blue oversized hoodie, deep indigo baggy jeans, '\n"
            "    'fresh white sneakers, and a prominent giant glowing metallic gold dollar-sign ($) medallion necklace, standing out as the colorful narrator. '\n"
            "    'STRICT NO LABELS RULE: DO NOT WRITE THE WORDS \"HOST\", \"HOST 3\", OR ANY POINTER ARROWS ON OR NEAR THE CHARACTER. '"
        )
        new_char_body = (
            "    'Featuring a charismatic realistic documentary presenter, dressed in sleek professional modern attire, '\n"
            "    'standing naturally in the frame with authentic camera presence, illuminated by soft cinematic studio lighting. '"
        )
        source_str = source_str.replace(old_char_body, new_char_body)
        
        old_suf_body = (
            "    'Showing a grand 2D hand-drawn physical environment. '\n"
            "    'ABSOLUTELY NO INFOGRAPHIC SLIDES, NO TOP CATEGORY HEADINGS, NO SPLIT-SCREEN DIAGRAM BOXES, AND NO CONNECTING ARROWS. '\n"
            "    'Professional YouTube economics explainer documentary aesthetic.'"
        )
        new_suf_body = (
            "    'A single cinematic full-frame 16:9 photorealistic 8K documentary shot. Masterpiece, sharp focus, professional film still.'"
        )
        source_str = source_str.replace(old_suf_body, new_suf_body)
        
        old_builder = (
            "def build_photorealistic_image_prompt(beat_text, style_name):\n"
            "    prefix = STYLE_PREFIXES.get(style_name, STYLE_PREFIXES['2D Cartoon / Explainer'])\n"
            "    clean_line = re.sub(r'\\s+', ' ', beat_text).strip()\n"
            "    money_match = re.search(r'(\\$?\\d+[\\d,.]*\\s*(million|billion|thousand|k|m)?)', clean_line, re.IGNORECASE)\n"
            "    money_callout = f' Hand-drawn financial text label showing \"{money_match.group(0).upper()}\".' if (money_match and len(money_match.group(0))>1) else ''\n"
            "    narrator_keywords = ['you', 'your', 'we', 'our', 'welcome', 'let\\'s', 'okay', 'so', 'look', 'here', 'problem', 'except']\n"
            "    has_narrator = any(re.search(rf'\\b{kw}\\b', clean_line, re.IGNORECASE) for kw in narrator_keywords)\n"
            "    char_str = ZENN_CHARACTER_SNIPPET if (has_narrator and '2D Cartoon' in style_name) else ''\n"
            "    return f'{prefix} {char_str}A single full-frame 16:9 2D cartoon physical location scene depicting: \"{clean_line}\". {money_callout} {ZENN_SUFFIX}'"
        )
        new_builder = (
            "def build_photorealistic_image_prompt(beat_text, style_name):\n"
            "    prefix = STYLE_PREFIXES.get(style_name, STYLE_PREFIXES['Photorealistic 8K'])\n"
            "    clean_line = re.sub(r'\\s+', ' ', beat_text).strip()\n"
            "    narrator_keywords = ['you', 'your', 'we', 'our', 'welcome', 'let\\'s', 'okay', 'so', 'look', 'here', 'problem', 'except']\n"
            "    has_narrator = any(re.search(rf'\\b{kw}\\b', clean_line, re.IGNORECASE) for kw in narrator_keywords)\n"
            "    pres_str = REALISTIC_PRESENTER_SNIPPET if (has_narrator and 'Photorealistic' in style_name) else ''\n"
            "    return f'{prefix} {pres_str}Depicting: \"{clean_line}\". {REALISTIC_SUFFIX}'"
        )
        source_str = source_str.replace(old_builder, new_builder)

        # Convert back to list of lines for notebook source
        lines = [line + '\n' for line in source_str.split('\n')]
        if lines and lines[-1] == '\n':
            lines.pop()
        cell['source'] = lines

with open(colab_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("SUCCESS: Updated youtube_voiceover_studio_colab.ipynb with Photorealistic 8K engine!")
