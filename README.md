# PSA10高騰ランキング クラウド版

Macを起動していなくても、GitHub Actionsが毎日07:10（JST）ごろに
SNKRDUNKのPSA10相場を取得し、GitHub PagesでiPhoneから閲覧できます。

初回セットアップ:
1. GitHubで新しいリポジトリを作る
2. このZIPの中身をすべてリポジトリへアップロード
3. Actions → Update PSA10 Rankings → Run workflow を1回実行
4. 成功後、Settings → Pages
5. Source: Deploy from a branch
6. Branch: main / Folder: /docs
7. Save
8. 数分後に表示されるURLをiPhoneで開く

カード追加:
cards.csv にURLを1行追加するだけです。

注意:
- GitHub Actionsの定期実行は混雑時に遅れることがあります。
- SNKRDUNK側の画面構造が変わった場合、取得ロジック調整が必要です。
- 個人利用・低頻度アクセスを前提としています。
