from collections import Counter

from app.infra.tokenizer.tokenizer import RegexWordTokenizer
from app.infra.nlp.pymorphy_lemmatizer import PymorphyLemmatizer


class ReportProcessor:

    def __init__(self, tokenizer: RegexWordTokenizer, lemmizer: PymorphyLemmatizer):
        self.tokenizer = tokenizer
        self.lemmizer = lemmizer


    def process_line(self, line: str) -> Counter[str]:
        tokens = self.tokenizer.tokenize(line)
        c: Counter[str] = Counter()
        lemmatize = self.lemmizer.lemmatize

        for token in tokens:
            c[lemmatize(token)] += 1

        return c
