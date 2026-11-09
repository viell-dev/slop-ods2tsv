"""Check local inline/reference links and GitHub-style headings in maintained Markdown."""
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from validation import require


EXCLUDED = {"artifacts", "target", "dist", "results", ".git", ".venv"}
DESTINATION = r'(<[^>\n]+>|[^\s)]+)'
QUOTE_MARKER = r" {0,3}>[ \t]?"


def markdown_files(root):
    paths = [*root.glob("*.md")]
    for directory in ("docs", "licenses", "research", ".github"):
        paths.extend((root / directory).rglob("*.md"))
    return sorted(path for path in paths
                  if not EXCLUDED.intersection(path.relative_to(root).parts) and not path.is_symlink())


def markdown_prose(text):
    """Omit fenced code and normalize quote prefixes for link/heading checks."""
    lines = []
    fence = None
    depth = 0
    for line in text.splitlines():
        prefix = re.match(f"(?:{QUOTE_MARKER})*", line)[0]
        if fence and prefix.count(">") < depth:
            # Leaving the containing quote also ends its unclosed fenced block.
            fence = None
        # Extra markers inside code are literal; only remove the opening fence's quote depth.
        body = re.sub(f"^(?:{QUOTE_MARKER}){{{depth}}}", "", line) if fence else line[len(prefix):]
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", body)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
        elif match and (match[1][0] != "`" or "`" not in match[2]):
            # Backtick-fence info cannot contain backticks (CommonMark 0.31.2, section 4.5).
            fence = match[1]
            depth = prefix.count(">")
        else:
            lines.append(body)
    return "\n".join(lines)


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value and (key == "id" or (tag == "a" and key == "name")):
                self.anchors.add(value)


def heading_anchors(text):
    parser = Anchors()
    parser.feed(text)
    anchors = parser.anchors
    generated = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        heading = match[1] if match else None
        if heading is None and index + 1 < len(lines) and line.strip():
            if re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1]):
                heading = line.strip()
        if heading is None:
            continue
        heading = re.sub(r"!?\[([^]]+)\]\([^)]*\)", r"\1", heading)
        heading = unescape(re.sub(r"<[^>]+>", "", heading)).lower()
        slug = "".join(character for character in heading
                       if character in "_- " or not unicodedata.category(character).startswith(("P", "S")))
        slug = slug.replace(" ", "-")
        suffix = 0
        anchor = slug
        while anchor in generated:
            suffix += 1
            anchor = f"{slug}-{suffix}"
        generated.add(anchor)
        anchors.add(anchor)
    return anchors


def local_links(text):
    # Read only the destination; link text, titles and closing syntax are separate.
    for match in re.finditer(r'\]\(\s*' + DESTINATION, text):
        yield match[1].strip("<>")
    # Checking every definition also covers shortcut and collapsed reference links.
    for match in re.finditer(r'^ {0,3}\[[^]\n]+\]:\s*' + DESTINATION, text, re.M):
        yield match[1].strip("<>")


def check_links(root):
    for source in markdown_files(root):
        text = markdown_prose(source.read_text(encoding="utf-8"))
        for link in local_links(text):
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            target = source.parent / unquote(parts.path) if parts.path else source
            context = f"Broken local link in {source.relative_to(root)}: {link}"
            require(target.exists(), context + " (missing file)")
            if parts.fragment:
                require(target.suffix.lower() == ".md", context + " (unsupported non-Markdown fragment)")
                anchors = heading_anchors(markdown_prose(target.read_text(encoding="utf-8")))
                require(unquote(parts.fragment) in anchors, context + " (missing section)")
