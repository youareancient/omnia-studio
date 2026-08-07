import re

def split_script_into_scenes(raw_text):
    # Split by newlines and sentence punctuation (. ! ?)
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    raw_sentences = []
    for line in lines:
        sents = re.split(r'(?<=[.!?])\s+', line)
        for s in sents:
            if s.strip():
                raw_sentences.append(s.strip())
                
    scenes = []
    for sent in raw_sentences:
        words = sent.split()
        if len(words) <= 10:
            scenes.append(sent)
        else:
            # Sub-split long sentences at commas, dashes or clauses
            clauses = re.split(r'(?<=[,;:—])\s+', sent)
            curr = []
            for c in clauses:
                curr.extend(c.split())
                if len(curr) >= 7:
                    scenes.append(" ".join(curr))
                    curr = []
            if curr:
                scenes.append(" ".join(curr))
                
    return scenes

test_text = """Okay, so you want to own a data center.

You find some land, build a giant warehouse, fill it with computers, plug the whole thing into the electrical grid, and then, somehow, companies pay you millions of dollars to keep their computers running inside your building.

Sounds pretty simple.

Except there's one small problem.

Your building isn't really a building.

It's a giant machine for turning electricity into money.

And if that machine stops working for even a few minutes, you could have a very expensive problem on your hands."""

scenes = split_script_into_scenes(test_text)
print(f"Total scenes generated: {len(scenes)}")
for i, s in enumerate(scenes, 1):
    print(f"Scene {i}: {s}")
