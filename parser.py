import logging
from pathlib import Path
import pyparsing as pp
import pprint
from docx import Document
import pyperclip
from yaml import Loader, dump, Dumper, load
from string import punctuation
import re
import sys
from itertools import chain

log = logging.Logger("parser")
log.addHandler(logging.StreamHandler(sys.stdout))
fh = logging.FileHandler("parser.log")
fh.setLevel(logging.DEBUG)
log.addHandler(fh)

# chinese_char
chinese_char = pp.Regex(r"[\u4e00-\u9fa5]")
# punctuation
cjk_punct = pp.Char(
    r"""（）＊＋，－／：＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､　、〃〈〉《》「」『』【】〔〕〖
    〗〘〙〚〛〜〝〞〟〰〾〿–—‘’‛“”„‟…‧﹏﹑﹔·[」﹂”』’》）］｝〕〗〙〛〉】。！？｡!?.．︀；
    ;"'”’""".replace(
        "\n", ""
    )
)
latin_punct = pp.Char(punctuation)
punct = cjk_punct | latin_punct
latin_term_punct = pp.Char(".?!")
cjk_term_punct = pp.Char("？！。")
term_punct = cjk_term_punct | latin_term_punct
# word
cjk_word = pp.Combine(pp.OneOrMore(chinese_char), adjacent=False)
latin_word = pp.Word(pp.alphas8bit + pp.alphas)
number = pp.Word(pp.nums)
word = cjk_word | latin_word | number
# period
period = pp.Char(".").suppress()
# quote
quote = (
    "'" + ~pp.FollowedBy("s") + ... + "'"
    | pp.dbl_quoted_string
    | pp.QuotedString("“", endQuoteChar="”")
    | pp.QuotedString("‘", endQuoteChar="’")
)
# paren
paren = pp.QuotedString("(", endQuoteChar=")") | pp.QuotedString("（", endQuoteChar="）")

# type of vocab, e.g., N., V., ADJ., ADV., etc.
type_of_vocab = pp.delimited_list(
    pp.one_of("N V ADJ ADV PREP n v adj adv prep") + period,
    delim=",",
)("type")
# vocab itself, e.g., abandon
vocab = pp.SkipTo(pp.White()[...] + type_of_vocab)("vocab")
# chinese definition, e.g., /中文，解释/
chinese_def = (
    "/"
    + pp.delimited_list(
        pp.original_text_for((word | punct + ~pp.PrecededBy(pp.Char("，/")))[...]),
        delim="，",
    )("chinese_def")
    + "/"
)
# english definition, e.g., wretched; lacking pride.
english_def = (
    pp.delimitedList(
        pp.original_text_for(
            pp.OneOrMore(
                latin_word
                | pp.White()
                | quote
                | paren
                | punct + ~pp.PrecededBy(latin_term_punct | ";", 1000)
            )[...]
        ),
        delim=";",
    )
    + period
)("english_def")
# synonym
sec_mean = pp.Opt("(secondary meaning)").suppress()
synonyms = (
    pp.Group(
        sec_mean
        + pp.original_text_for(word[1, 2])("vocab")
        + pp.Char(",").suppress()
        + type_of_vocab
        + pp.Opt(pp.Char(";")).suppress()
        + sec_mean
    ).ignore_whitespace()
    * (
        1,
        None,
    )
)("synonyms")
# also
also = pp.Literal("also") + type_of_vocab("also_type")
# and
and_t = pp.Literal("and") + type_of_vocab("and_type")
# example_sentnce
example_sentence = pp.original_text_for(
    pp.SkipTo(
        punct | quote | paren,
        1000,
        fail_on=and_t | also | synonyms,
    )[1, ...]
)("example_sentence")

# for an entry
entry_rule = (
    vocab
    + type_of_vocab
    + chinese_def
    + english_def
    + pp.White()[...]
    + example_sentence
    + pp.Opt(synonyms)
    + pp.Opt(also)
    + pp.Opt(and_t)
    + pp.White()[...]
    + pp.StringEnd()
)

# word list rule
section_rule = "Word List" + number + latin_word("start") + "-" + latin_word("end")


def to_check(word, msg=""):
    with open("to_check.txt", "a+") as f:
        f.write(word["vocab"] + " " + msg + "\n")


def parse_word(words):
    words = re.split(
        r"(?<=[\.?!\"']\s)\b(?=\w+\s*(?:ADJ|ADV|V|N|PREP)\.\s*\/)(?!ADV|ADJ|V|N|PREP)",
        words,
    )
    print(words)
    results = [
        entry_rule.parseString(word.strip().strip("*")).as_dict()
        for word in words
        if len(word) >= 5
    ]
    for result in results:
        if not "example_sentence" in result:
            raise pp.ParseException("No example sentence found")
        if "also_type" in result:
            result["type"] += result["also_type"]
            del result["also_type"]
        if "and_type" in result:
            result["type"] += result["and_type"]
            del result["and_type"]
        if len(set(result["type"])) != len(result["type"]):
            to_check(result, "duplicate type")
    return results


def parse_clipboard():
    pprint.pprint(parse_word(pyperclip.paste()))


def parse_doc():
    doc = Document(Path("~/barron.docx").expanduser())
    pars = [p.text for p in doc.paragraphs]
    idx = 5  # 5
    word_list_idx = 1
    results = [{}]

    while idx < len(pars):
        par = pars[idx]
        if par.startswith("Word List"):
            try:
                result = section_rule.parseString(par).as_dict()
            except pp.ParseException:
                log.error(f"Error parsing section {word_list_idx}")
                result = {}
            result["index"] = word_list_idx
            results += [result]
            idx += 1
            word_list_idx += 1
        else:
            peek_idx = idx + 1
            while peek_idx < len(pars) and peek_idx - idx <= 5:
                try:
                    results[-1].setdefault("vocabs", []).extend(parse_word(par))
                except pp.ParseException:
                    par += " " + pars[peek_idx]
                    peek_idx += 1
                else:
                    idx = peek_idx
                    break
            else:
                if idx >= 1:
                    # backtrack to the see if it works
                    par = pars[idx - 1] + " " + pars[idx]
                    peek_idx = idx + 1
                    while peek_idx < len(pars) and peek_idx - idx <= 5:
                        try:
                            results[-1]["vocabs"][-1:] = parse_word(par)
                        except pp.ParseException:
                            par += " " + pars[peek_idx]
                            peek_idx += 1
                        else:
                            idx = peek_idx
                            break
                    else:
                        log.error(f"Failed to parse {idx}")
                        idx += 1
                else:
                    log.error(f"Failed to parse {idx}")
                    idx += 1
    with open("barron.yml", "w") as f:
        dump(results, f, Dumper)


# parse_doc()
# parse_clipboard()
refine_rule = (
    example_sentence
    + pp.Opt(synonyms)
    + pp.Opt(also)
    + pp.Opt(and_t)
    + pp.White()[...]
    + pp.StringEnd()
)


def parse_refine():
    with open("formatted.yml") as f:
        results = load(f, Loader)
        for result in results:
            for vocab in result["vocabs"]:
                r = {}
                try:
                    r = refine_rule.parseString(vocab["example_sentence"]).as_dict()
                    r["example_sentence"] = re.sub("\s+", " ", r["example_sentence"])
                    if "also_type" in r:
                        r["type"] += r["also_type"]
                        del r["also_type"]
                    if "and_type" in r:
                        r["type"] += r["and_type"]
                        del r["and_type"]
                    vocab["type"].extend(r.get("type", []))
                    if r.get("type", None):
                        del r["type"]
                    if len(set(vocab["type"])) != len(vocab["type"]):
                        to_check(vocab, "duplicate type")
                    vocab.update(r)
                except Exception as e:
                    log.error(f"Failed to parse {vocab.get('vocab', vocab)}")
                    log.error(repr(e))
                try:
                    cn_def, en_def = vocab["chinese_def"], vocab["english_def"]
                    if not isinstance(cn_def, list):
                        cn_def = [cn_def]
                    if not isinstance(en_def, list):
                        en_def = [en_def]
                    cn_def = list(chain(*[re.split(r"\s*[;；]\s*", d) for d in cn_def]))
                    en_def = list(chain(*[re.split(r"\s*[;；]\s*", d) for d in en_def]))
                    del vocab["chinese_def"]
                    del vocab["english_def"]
                    vocab["def"] = {
                        "cn": [re.sub(r"\s+", " ", d.strip()) for d in cn_def if d],
                        "en": [d.strip() for d in en_def if d],
                    }
                except Exception as e:
                    log.error(f"Failed to handle definitions")
                    log.error(repr(e))
        with open("refined_formatted.yml", "w") as f:
            dump(results, f, Dumper, allow_unicode=True)

parse_refine()