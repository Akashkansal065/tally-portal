import re
from typing import Optional, Union, List, Any

def collapse_string(s: Optional[str]) -> str:
    """Strips all non-alphanumeric characters and lowercases the string."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())

def matches_search(target: Union[str, List[Any], None], query: Optional[str]) -> bool:
    """
    Intelligent search matcher matching query against target string or list of attributes.
    Supports:
    - Direct substring matches
    - Space/punctuation insensitive matches (e.g. 'tri ply' matches 'Triply')
    - Reverse space/punctuation matches (e.g. 'honeycomb' matches 'honey comb')
    - Multi-token and out-of-order matches (e.g. 'cooker tri ply' matches 'Triply Aura Cooker')
    - Number-boundary aware matching (e.g. '5' matches '5 Ltr', not '2.5 Ltr')
    """
    if not query:
        return True
    q_clean = str(query).strip().lower()
    if not q_clean:
        return True
    if not target:
        return False

    if isinstance(target, (list, tuple)):
        target_text = " ".join(str(x) for x in target if x)
    else:
        target_text = str(target)
    t_lower = target_text.lower()

    # 1. Direct substring
    if q_clean in t_lower:
        return True

    # 2. Collapsed
    q_col = collapse_string(q_clean)
    t_col = collapse_string(t_lower)
    if q_col and q_col in t_col:
        return True

    # 3. Multi-token
    q_tokens = re.findall(r"\d+(?:\.\d+)?|[a-z]+", q_clean)
    if not q_tokens:
        return False

    t_tokens = re.findall(r"\d+(?:\.\d+)?|[a-z]+", t_lower)
    t_token_set = set(t_tokens)

    def token_matches(tok: str) -> bool:
        if not tok:
            return False
        if re.search(r"\d", tok):
            if tok in t_token_set:
                return True
            escaped = re.escape(tok)
            return bool(re.search(r"(?<![\d.])" + escaped + r"(?![\d.])", t_lower))
        if tok in t_token_set:
            return True
        for tt in t_tokens:
            if tt.startswith(tok) or (len(tok) >= 3 and tok in tt):
                return True
        return tok in t_col

    idx = 0
    while idx < len(q_tokens):
        tok = q_tokens[idx]
        if token_matches(tok):
            idx += 1
            continue
        if idx + 1 < len(q_tokens):
            merged_pair = tok + q_tokens[idx + 1]
            if token_matches(merged_pair):
                idx += 2
                continue
        if idx + 2 < len(q_tokens):
            merged_triplet = tok + q_tokens[idx + 1] + q_tokens[idx + 2]
            if token_matches(merged_triplet):
                idx += 3
                continue
        return False
    return True
