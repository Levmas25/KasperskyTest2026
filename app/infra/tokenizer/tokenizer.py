import re


class RegexWordTokenizer:
    WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")

    def tokenize(self, text: str) -> list[str]:
        return self.WORD_RE.findall(text)