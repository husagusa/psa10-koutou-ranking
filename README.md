# PSA10高騰ランキング クラウド版

Macを起動していなくても、GitHub Actionsが毎日07:10（JST）ごろに
SNKRDUNKのPSA10相場を取得し、GitHub PagesでiPhoneから閲覧できます。

初回セットアップ:
1. ファイルをリポジトリのmainブランチへアップロード
2. Settings → Pages → SourceをGitHub Actionsに設定
3. Actions → Update PSA10 Rankings → Run workflowを実行
4. 完了後、公開URLをiPhoneで開く

注意:
- GitHub Actionsの定期実行は混雑時に遅れることがあります。
- SNKRDUNK側の画面構造が変わった場合、取得ロジック調整が必要です。
- 個人利用・低頻度アクセスを前提としています。


## 画面からカードを追加

1. ランキング画面の「＋カードを追加」を開き、SNKRDUNKの商品URLを貼り付けます。
2. 「GitHubで追加を確定する」で移動し、GitHubにログインして「Create」を押します。
3. ActionsがURLを検証し、cards.csvに重複なく登録して相場を取得・公開します。結果はIssueに記録されます。

所有者と書き込み権限のある共同管理者のみ自動登録できます。入力はHTTPSのsnkrdunk.com（wwwも可）の/apparels/数字に限定し、末尾のスラッシュ・共有用クエリ・フラグメントを除去します。ブラウザにGitHubトークンは保存しません。GitHub Actionsの一時トークンだけを使用します。

取得に失敗した申請は開いたまま残り、毎日の更新時に再試行します。URLが不正な場合はIssue本文を修正してください。既存のURLは追加し直しません。未処理Issueを毎回読み直すので、複数申請や待機中の実行の置き換えがあっても次回に回収できます。

### 公開設定

Settings → Pages → Build and deployment → Source を **GitHub Actions** に設定します。更新ワークフローがdocsを直接公開するため、ActionsのコミットでPagesが再構築されない問題を回避します。Actions → Update PSA10 Rankings → Run workflow で手動再実行できます。

毎日07:10 JSTのスケジュールは維持しています。履歴ファイルはdata/history.csvとdocs/history.csvです。前日は該当日のみ、7日・30日は対象日以前の直近日を比較する既存仕様を維持しています。比較日の相場がない場合は「-」になります。

検証: `python -m unittest discover -s tests -v`
