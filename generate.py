from yaml import load, Loader
from pathlib import Path
from quizlet_helper import Card, StudySet, Folder, User, log
from playwright.sync_api import sync_playwright


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


def format_card(vocab) -> Card:
    return Card(
        vocab["vocab"],
        f"""{format_type(vocab['type'])} {'；'.join(vocab["def"]["cn"])} | {'; '.join(vocab["def"]["en"])}
{format_synonyms(vocab.get("synonyms", []))}
{vocab['example_sentence']}""",
    )


with (
    sync_playwright() as playwright,
    open("vocab.yml", "r") as vocab,
    open("auth.yml", "r") as auth,
):
    auth = load(auth, Loader=Loader)
    sections = load(vocab, Loader)
    
    browser = playwright.chromium.launch(headless=False)
    user = User(username=auth["username"], password=auth["password"], browser=browser)
    folder = Folder(user, name="barron")
    folder.created = True

    for section in sections:
        try:
            formatted = []
            for vocab in section["vocabs"]:
                formatted.append(format_card(vocab))
            name = f"{section['index']}: {section['start']}-{section['end']}"
            set = StudySet(
                user=user,
                folders=[folder],
                name=name,
                cards=formatted,
                definition_lang="英语",
                word_lang="中文（简体）",
            )
            set.create()
            set.page.close()
        except Exception as e:
            log.error(f"Error while creating study set for {section['index']}: {e}")
