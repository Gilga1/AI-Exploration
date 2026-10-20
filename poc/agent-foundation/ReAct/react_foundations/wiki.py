"""Wikipedia tool environment from ReAct §3.1 — local corpus or live Wikipedia."""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ABBREV_END = re.compile(r"\b[A-Za-z]\.$")


def split_sentences(page: str) -> list[str]:
    """Split like the original ReAct env (`split('. ')`), but glue U.S.-style abbreviations."""
    paragraphs = [p.strip() for p in page.split("\n") if p.strip()]
    fragments: list[str] = []
    for paragraph in paragraphs:
        fragments.extend(part.strip() for part in paragraph.split(". ") if part.strip())
    sentences: list[str] = []
    for fragment in fragments:
        text = fragment if fragment[-1] in ".!?" else fragment + "."
        if sentences and ABBREV_END.search(sentences[-1]):
            sentences[-1] = sentences[-1] + " " + text
        else:
            sentences.append(text)
    return sentences


def first_sentences(page: str, n: int = 5) -> str:
    return " ".join(split_sentences(page)[:n])


def sentences_containing(page: str, keyword: str) -> list[str]:
    key = keyword.lower()
    return [sentence for sentence in split_sentences(page) if key in sentence.lower()]


def clean_wikipedia_text(text: str) -> str:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return text.encode().decode("unicode-escape").encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError):
        return text


@dataclass
class StepResult:
    observation: str
    reward: float
    done: bool
    info: dict[str, Any]


class WikiEnv:
    """search[entity] / lookup[string] / finish[answer] — paper §3.1 action space."""

    def __init__(self) -> None:
        self.page: str | None = None
        self.observation = ""
        self.lookup_keyword: str | None = None
        self.lookup_list: list[str] = []
        self.lookup_cnt = 0
        self.steps = 0
        self.answer: str | None = None

    def reset(self) -> str:
        self.page = None
        self.observation = (
            "Interact with Wikipedia using search[], lookup[], and finish[].\n"
        )
        self.lookup_keyword = None
        self.lookup_list = []
        self.lookup_cnt = 0
        self.steps = 0
        self.answer = None
        return self.observation

    def _info(self) -> dict[str, Any]:
        return {"steps": self.steps, "answer": self.answer}

    def search(self, entity: str) -> str:
        raise NotImplementedError

    def step(self, action: str) -> StepResult:
        raw = action.strip()
        done = False
        reward = 0.0
        if self.answer is not None:
            return StepResult(self.observation, reward, True, self._info())

        lowered = raw[:1].lower() + raw[1:] if raw else raw
        if lowered.startswith("search[") and lowered.endswith("]"):
            entity = lowered[len("search[") : -1]
            self.observation = self.search(entity)
            self.lookup_keyword = None
            self.lookup_list = []
            self.lookup_cnt = 0
        elif lowered.startswith("lookup[") and lowered.endswith("]"):
            keyword = lowered[len("lookup[") : -1]
            if self.lookup_keyword != keyword:
                self.lookup_keyword = keyword
                self.lookup_list = (
                    sentences_containing(self.page, keyword) if self.page else []
                )
                self.lookup_cnt = 0
            if self.lookup_cnt >= len(self.lookup_list):
                self.observation = "No more results.\n"
            else:
                total = len(self.lookup_list)
                hit = self.lookup_list[self.lookup_cnt]
                self.observation = f"(Result {self.lookup_cnt + 1} / {total}) {hit}"
                self.lookup_cnt += 1
        elif lowered.startswith("finish[") and lowered.endswith("]"):
            self.answer = lowered[len("finish[") : -1]
            done = True
            self.observation = "Episode finished.\n"
        elif lowered.startswith("think[") and lowered.endswith("]"):
            self.observation = "Nice thought."
        else:
            self.observation = f"Invalid action: {raw}"

        self.steps += 1
        return StepResult(self.observation, reward, done, self._info())


class LocalWikiEnv(WikiEnv):
    """Deterministic Wikipedia stand-in for tests and offline notebooks."""

    def __init__(self, pages: dict[str, str]) -> None:
        super().__init__()
        self.pages = pages
        self._index = {title.lower(): title for title in pages}

    @classmethod
    def from_fixture(cls, path: Path | None = None) -> "LocalWikiEnv":
        fixture = path or Path(__file__).resolve().parent.parent / "fixtures" / "local_wiki.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        return cls(payload["pages"])

    def search(self, entity: str) -> str:
        key = entity.strip().lower()
        if key in self._index:
            title = self._index[key]
            self.page = self.pages[title]
            return first_sentences(self.page)
        close = get_close_matches(entity, list(self.pages), n=5, cutoff=0.3)
        if not close:
            lowered = entity.lower()
            close = [title for title in self.pages if lowered in title.lower()][:5]
        if close:
            return f"Could not find {entity}. Similar: {close}."
        return f"Could not find {entity}. Similar: []."


class LiveWikipediaEnv(WikiEnv):
    """Live Wikipedia with the paper's search/lookup/finish semantics.

    HTML `index.php?search=` is what the original notebook used. Some hosts
    (including this one) get 403 on that endpoint, so we fall back to the
    MediaWiki API which returns the same titles + plaintext extracts.
    """

    SEARCH_URL = "https://en.wikipedia.org/w/index.php"
    API_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, session: requests.Session | None = None, timeout: float = 20.0) -> None:
        super().__init__()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update(
            {
                "User-Agent": (
                    "ai-exploration-react-study/0.1 "
                    "(https://github.com/gilga1/ai-exploration; ReAct paper reproduction)"
                )
            }
        )

    def search(self, entity: str) -> str:
        try:
            return self._search_html(entity)
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code not in {403, 429}:
                raise
            return self._search_api(entity)

    def _search_html(self, entity: str) -> str:
        response = self.session.get(
            self.SEARCH_URL,
            params={"search": entity},
            timeout=self.timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result_divs = soup.find_all("div", {"class": "mw-search-result-heading"})
        if result_divs:
            titles = [clean_wikipedia_text(div.get_text().strip()) for div in result_divs]
            self.page = None
            return f"Could not find {entity}. Similar: {titles[:5]}."

        blocks = [p.get_text().strip() for p in soup.find_all("p") + soup.find_all("ul")]
        if any("may refer to:" in block for block in blocks):
            return self.search(f"[{entity}]")

        page_parts: list[str] = []
        for block in blocks:
            if len(block.split()) <= 2:
                continue
            cleaned = clean_wikipedia_text(block)
            page_parts.append(cleaned if cleaned.endswith("\n") else cleaned + "\n")
        self.page = "".join(page_parts)
        return first_sentences(self.page)

    def _search_api(self, entity: str) -> str:
        query = self.session.get(
            self.API_URL,
            params={
                "action": "query",
                "format": "json",
                "redirects": 1,
                "titles": entity,
                "prop": "extracts",
                "explaintext": 1,
            },
            timeout=self.timeout,
        )
        query.raise_for_status()
        pages = list(query.json()["query"]["pages"].values())
        page = pages[0]
        if "missing" not in page and page.get("extract"):
            if "may refer to:" in page["extract"].lower():
                return self.search(f"[{entity}]")
            self.page = page["extract"]
            return first_sentences(self.page)

        search = self.session.get(
            self.API_URL,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": entity,
                "srlimit": 5,
            },
            timeout=self.timeout,
        )
        search.raise_for_status()
        titles = [hit["title"] for hit in search.json()["query"]["search"]]
        self.page = None
        return f"Could not find {entity}. Similar: {titles[:5]}."


@dataclass
class HotpotTask:
    question: str
    answer: str
    example_id: str = ""
    hops: list[str] = field(default_factory=list)


def load_hotpot_mini(path: Path | None = None) -> list[HotpotTask]:
    fixture = path or Path(__file__).resolve().parent.parent / "fixtures" / "hotpotqa_mini.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return [
        HotpotTask(
            question=row["question"],
            answer=row["answer"],
            example_id=row["id"],
            hops=list(row.get("hops", [])),
        )
        for row in payload["examples"]
    ]
