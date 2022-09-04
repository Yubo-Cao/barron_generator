from yaml import load, Loader
from pathlib import Path

out_dir = Path("~/out").expanduser()
out_dir.mkdir(exist_ok=True)


def format_type(type):
    return "(" + ", ".join(t + "." for t in type) + ")"


def format_synonyms(synonyms):
    synonyms = "\n".join(
        f"""{format_type(vocab["type"])} {vocab["vocab"]}""" for vocab in synonyms
    )
    synonyms = (
        f"""
{synonyms}
"""
        if synonyms
        else ""
    )
    return synonyms


def format_card(vocab):
    return f"""{vocab["vocab"]}
<SEP>
{format_type(vocab['type'])} {'；'.join(vocab["def"]["cn"])} | {'; '.join(vocab["def"]["en"])}
{format_synonyms(vocab.get("synonyms", []))}
{vocab['example_sentence']}
<CARD>"""


with open("refined_formatted.yml") as f:
    sections = load(f, Loader)
    for section in sections:
        formatted = []
        for vocab in section["vocabs"]:
            try:
                formatted.append(format_card(vocab))
            except:
                print(vocab)
        with open(out_dir / f"{section['index']}-{section['start']}-{section['end']}.txt", "w") as f:
            f.write("\n".join(formatted))
