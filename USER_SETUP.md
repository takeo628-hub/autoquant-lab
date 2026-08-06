# あなたにしかできない一回きりの設定（合計約20分）

システムの生成・更新・記事執筆は全自動ですが、アカウント作成だけは本人しかできません。

## 1. GitHub Pages公開（約10分・無料）
1. https://github.com で無料アカウント作成（既にあればスキップ）
2. 新規リポジトリ `autoquant-lab` を **Public** で作成（READMEは追加しない）
3. PowerShellで:
   ```
   cd C:\Users\yukur\auto_media
   git remote add origin https://github.com/<あなたのID>/autoquant-lab.git
   git push -u origin main
   ```
   （初回はブラウザ認証が出ます）
4. GitHubのリポジトリ → Settings → Pages → Source: 「Deploy from a branch」、
   Branch: `main` / フォルダ: `/docs` → Save
5. 数分後 `https://<あなたのID>.github.io/autoquant-lab/` で公開されます
6. 公開URLが決まったら generator.py の `BASE_URL = ""` にそのURLを設定
   （次回のAIループが自動でやるので、私に伝えるだけでもOK）

以降は毎朝08:25のタスクが記事生成→push→公開まで全自動で行います。

## 2. A8.net登録（約10分・無料）— 収益化の本命
1. https://www.a8.net で無料登録（サイトURLは上記GitHub PagesのURL）
2. プログラム検索で「moomoo証券」「楽天証券」等を検索し提携申請
   （口座開設1件あたり数千円〜1万円程度の成果報酬）
3. 承認されたら広告リンクURLを `affiliate.json` に貼る → 全記事に自動反映

## 3. 後日でよいもの
- Google Search Console（検索流入の計測。Pages URLで登録するだけ）
- Google AdSense(審査に独自ドメインが有利。月次で費用対効果を判断。年約¥1,500)
- X(Twitter)アカウント（social_queue/ に投稿文が毎日自動生成済み。手動コピペでも可）

## 費用まとめ
- 必須: **¥0**（GitHub Pages・A8とも無料）
- 任意: 独自ドメイン 年約¥1,500（AdSense本格化する場合のみ）
