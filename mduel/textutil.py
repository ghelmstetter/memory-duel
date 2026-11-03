"""Text helpers: word tokens for word-matching search, and a rough token count."""
import re

STOP = set("""a an the and or of to in on at for from by with is are was were be been it its this that these those
as do does did which who whom what when where why how about into than then there their his her he she they them our
we you your i me my will would could should can may might not no if so up out over after before all any each more most
some such only own same very just also has have had during until since now every said say says here year years
im it's i'm can't don't""".split())


def stem(w):
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def tokens(s):
    return [stem(w) for w in re.findall(r"[a-z0-9$áéíóúñ]+", s.lower()) if w not in STOP and len(w) > 1]


def approx_tokens(s):
    """About 4 characters per token for English text: close enough for meters and estimates."""
    return max(1, round(len(s) / 4))
