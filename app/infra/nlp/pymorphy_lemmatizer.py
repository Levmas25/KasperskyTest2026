from functools import lru_cache

from pymorphy3 import MorphAnalyzer


class PymorphyLemmatizer:

    def __init__(self):
        self._morph = MorphAnalyzer(lang="ru")
        self._cached_normal_form = lru_cache(maxsize=200_000)(self._normal_form)


    def lemmatize(self, token: str) -> str:
        token = token.strip().lower()
        if not token:
            return token

        return self._cached_normal_form(token)

    def cache_info(self):
        return self._cached_normal_form.cache_info()

    def _normal_form(self, token: str) -> str:
        return self._morph.parse(token)[0].normal_form
