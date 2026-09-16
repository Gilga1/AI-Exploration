"""Recorded Thought/Action continuations for the mini benchmark (no API key)."""

from __future__ import annotations

# Each ReAct value is a list of model continuations after `Thought i:`.
REACT_SCRIPTS: dict[str, list[str]] = {
    "Which magazine was started first, Arthur's Magazine or First for Women?": [
        "I need to search Arthur's Magazine and First for Women, and find which started first.\nAction 1: Search[Arthur's Magazine]",
        "Arthur's Magazine was started in 1844. I need to search First for Women next.\nAction 2: Search[First for Women]",
        "First for Women was started in 1989. 1844 < 1989, so Arthur's Magazine started first.\nAction 3: Finish[Arthur's Magazine]",
    ],
    "In which city is the company that created the iPhone headquartered?": [
        "I need to search iPhone, find the company that created it, then find that company's headquarters city.\nAction 1: Search[iPhone]",
        "The iPhone was designed by Apple Inc. I should search Apple Inc. for the headquarters.\nAction 2: Search[Apple Inc.]",
        "Apple is headquartered in Cupertino, California, so the city is Cupertino.\nAction 3: Finish[Cupertino]",
    ],
    "Who wrote the novel that features the character Atticus Finch?": [
        "I should search Atticus Finch and find which novel he appears in, then find the author.\nAction 1: Search[Atticus Finch]",
        "Atticus Finch is a character in Harper Lee's novel To Kill a Mockingbird, so the author is Harper Lee.\nAction 2: Finish[Harper Lee]",
    ],
    "The author of Pride and Prejudice was born in which country?": [
        "I need to search Pride and Prejudice, find the author, then find where that author was born.\nAction 1: Search[Pride and Prejudice]",
        "Pride and Prejudice is a novel by Jane Austen. I should search Jane Austen.\nAction 2: Search[Jane Austen]",
        "Jane Austen was an English novelist born in Steventon, Hampshire, so the country is England.\nAction 3: Finish[England]",
    ],
    "What ocean borders the country whose capital is Nairobi?": [
        "I need to search Nairobi to find the country, then find which ocean borders that country.\nAction 1: Search[Nairobi]",
        "Nairobi is the capital of Kenya. I should search Kenya for its ocean border.\nAction 2: Search[Kenya]",
        "Kenya has a coastline on the Indian Ocean, so the answer is the Indian Ocean.\nAction 3: Finish[Indian Ocean]",
    ],
    "Who painted the ceiling of the Sistine Chapel?": [
        "I should search Sistine Chapel and find who painted the ceiling.\nAction 1: Search[Sistine Chapel]",
        "Michelangelo painted the chapel's ceiling between 1508 and 1512, so the answer is Michelangelo.\nAction 2: Finish[Michelangelo]",
    ],
    "What is the atomic number of the chemical element named after the planet Uranus?": [
        "The element named after Uranus should be uranium. I will search Uranium for the atomic number.\nAction 1: Search[Uranium]",
        "Uranium has atomic number 92, so the answer is 92.\nAction 2: Finish[92]",
    ],
    "Which company acquired YouTube?": [
        "I should search YouTube and find which company acquired it.\nAction 1: Search[YouTube]",
        "Google acquired YouTube in 2006, so the company is Google.\nAction 2: Finish[Google]",
    ],
}

COT_SCRIPTS: dict[str, str] = {
    "Which magazine was started first, Arthur's Magazine or First for Women?": (
        "Let's think step by step. Arthur's Magazine was started in 1844. "
        "First for Women was started in 1989. 1844 < 1989, so the answer is Arthur's Magazine."
    ),
    "In which city is the company that created the iPhone headquartered?": (
        "The iPhone was created by Apple. Apple is headquartered in Cupertino. "
        "So the answer is Cupertino."
    ),
    "Who wrote the novel that features the character Atticus Finch?": (
        "Atticus Finch is in To Kill a Mockingbird by Harper Lee. So the answer is Harper Lee."
    ),
    "The author of Pride and Prejudice was born in which country?": (
        "Pride and Prejudice was written by Jane Austen, who was English. So the answer is England."
    ),
    "What ocean borders the country whose capital is Nairobi?": (
        "Nairobi is the capital of Kenya, which borders the Indian Ocean. So the answer is Indian Ocean."
    ),
    "Who painted the ceiling of the Sistine Chapel?": (
        "Michelangelo painted the Sistine Chapel ceiling. So the answer is Michelangelo."
    ),
    "What is the atomic number of the chemical element named after the planet Uranus?": (
        "Uranium is named after Uranus and has atomic number 92. So the answer is 92."
    ),
    "Which company acquired YouTube?": (
        "Google acquired YouTube. So the answer is Google."
    ),
}

STANDARD_SCRIPTS: dict[str, str] = {
    "Which magazine was started first, Arthur's Magazine or First for Women?": "Arthur's Magazine",
    "In which city is the company that created the iPhone headquartered?": "Cupertino",
    "Who wrote the novel that features the character Atticus Finch?": "Harper Lee",
    "The author of Pride and Prejudice was born in which country?": "England",
    "What ocean borders the country whose capital is Nairobi?": "Indian Ocean",
    "Who painted the ceiling of the Sistine Chapel?": "Michelangelo",
    "What is the atomic number of the chemical element named after the planet Uranus?": "92",
    "Which company acquired YouTube?": "Google",
}

# CoT hallucination on the paper's running example (Figure 1 contrast).
COT_HALLUCINATED_MAGAZINES = (
    "Let's think step by step. First for Women is a well-known magazine that started "
    "in the 19th century. Arthur's Magazine started much later. So the answer is First for Women."
)

# Broken Act policy: search the full question, then finish with a guess — no thoughts.
WEAK_ACT_SCRIPTS: dict[str, list[str]] = {
    "Which magazine was started first, Arthur's Magazine or First for Women?": [
        "Search[Which magazine was started first]",
        "Finish[First for Women]",
    ]
}


def act_scripts() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for question, blocks in REACT_SCRIPTS.items():
        actions: list[str] = []
        for index, block in enumerate(blocks, start=1):
            marker = f"Action {index}:"
            if marker in block:
                actions.append(block.split(marker, 1)[1].strip())
            else:
                actions.append(block.strip())
        out[question] = actions
    return out
