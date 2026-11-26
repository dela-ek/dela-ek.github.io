from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

root = Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = set()
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id' and value:
                self.ids.add(value)
            if key in ('href', 'src') and value:
                self.refs.append(value)

pages = {}
for path in root.rglob('*.html'):
    parser = Page()
    parser.feed(path.read_text(encoding='utf-8'))
    pages[path.resolve()] = parser
errors = []
for path, parser in pages.items():
    for ref in parser.refs:
        url = urlsplit(ref)
        if url.scheme or url.netloc:
            continue
        target = ((root / unquote(url.path.lstrip('/'))) if url.path.startswith('/') else (path.parent / unquote(url.path)) if url.path else path).resolve()
        if target.is_dir():
            target = target / 'index.html'
        if not target.is_file():
            errors.append(f'{path.relative_to(root)}: missing {ref}')
        elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
            errors.append(f'{path.relative_to(root)}: missing anchor {ref}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Checked internal links and anchors in {len(pages)} HTML pages.')
