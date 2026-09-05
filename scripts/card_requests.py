"""Process trusted card Issues as data. No Issue text is executed."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'psa10-card-requests.json'


def normalize_url(value):
    value = value.strip()
    if len(value) > 2048 or re.search(r'[\s\\\x00-\x1f\x7f]', value):
        raise ValueError('SNKRDUNKの商品URLを1つ入力してください。')
    u = urlsplit(value)
    if (u.scheme != 'https' or u.netloc.lower() not in ('snkrdunk.com', 'www.snkrdunk.com')
            or not re.fullmatch(r'/apparels/[1-9][0-9]{0,11}/?', u.path)):
        raise ValueError('https://snkrdunk.com/apparels/数字 の商品URLを入力してください。')
    return 'https://snkrdunk.com' + u.path.rstrip('/')


def parse_body(body):
    match = re.search(r'^### SNKRDUNK URL\s*\n(.*?)(?=^### |\Z)', body or '', re.M | re.S)
    if not match:
        raise ValueError('カード追加フォームからURLを入力してください。')
    return normalize_url(match.group(1).strip())


def add_urls(path, urls):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        if fields != ['url']:
            raise ValueError('cards.csv のヘッダーが想定と異なります。')
        rows = list(reader)
    existing = {normalize_url(r['url']) for r in rows}
    added = []
    for url in urls:
        if url not in existing:
            rows.append({'url': url})
            existing.add(url)
            added.append(url)
    if added:
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return added


def api(path, data=None, method=None):
    req = Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + path,
                  data=None if data is None else json.dumps(data).encode(), method=method,
                  headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                           'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                           'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def pages(path):
    page = 1
    while True:
        batch = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        yield from batch
        if len(batch) < 100:
            break
        page += 1


def comment_once(number, message):
    marker = '<!-- psa10:' + hashlib.sha256(message.encode()).hexdigest()[:16] + ' -->'
    if not any(marker in (c.get('body') or '') for c in pages(f'/issues/{number}/comments')):
        api(f'/issues/{number}/comments', {'body': message + '\n\n' + marker})


def prepare():
    results = []
    # Scan every pending request: GitHub concurrency can replace a pending run.
    # The next run (including the daily update) always recovers unprocessed Issues.
    for issue in pages('/issues?state=open&sort=created&direction=asc'):
        if 'pull_request' in issue or not issue['title'].startswith('[カード追加]'):
            continue
        # Re-check current repository write permission; author_association alone is insufficient.
        login = issue['user']['login']
        permission = api(f'/collaborators/{login}/permission')['permission']
        if permission not in ('admin', 'maintain', 'write'):
            continue
        try:
            url = parse_body(issue.get('body'))
            results.append({'number': issue['number'], 'url': url, 'body': issue.get('body')})
        except ValueError as exc:
            comment_once(issue['number'], '追加できませんでした。' + str(exc) + '\nIssue本文を修正すると再実行されます。')
    add_urls(ROOT / 'cards.csv', [r['url'] for r in results])
    RESULTS.write_text(json.dumps(results), encoding='utf-8')


def report():
    if not RESULTS.exists():
        return
    with (ROOT / 'docs/history.csv').open(newline='', encoding='utf-8-sig') as f:
        available = {r['url'] for r in csv.DictReader(f)}
    for result in json.loads(RESULTS.read_text(encoding='utf-8')):
        number, url = result['number'], result['url']
        current = api(f'/issues/{number}')
        if current.get('body') != result['body'] or current['state'] != 'open':
            continue
        if url in available and os.environ.get('COLLECT_OUTCOME') == 'success':
            comment_once(number, '登録済みです（同じURLは重複追加しません）。PSA10相場を公開しました。\n' +
                         'https://husagusa.github.io/psa10-koutou-ranking/\n\n' +
                         '比較対象日の相場がない場合、上昇額・上昇率は「-」になります。')
            api(f'/issues/{number}', {'state': 'closed'}, 'PATCH')
        else:
            comment_once(number, 'URLを登録しましたが、PSA10相場の取得は完了していません。' +
                         'このIssueは開いたままにし、次回の毎日更新で再試行します。' +
                         '商品URLとPSA10の取引履歴をご確認ください。')


if __name__ == '__main__':
    {'prepare': prepare, 'report': report}[sys.argv[1]]()
