@echo off
cd /d C:\Users\yukur\auto_media
call claude -p "C:\Users\yukur\auto_media\BUSINESS_PROTOCOL.md を読んで事業改善ループを1サイクル実行して。手順: (1) サイトビルドと日次記事生成が壊れていないか確認し（generator.py --daily を実行、media.logも確認）、壊れていれば修復最優先。(2) 常設記事を1本追加する（C:\Users\yukur\trading_v2 の実データ・実検証を素材に。法務ガードレール厳守: 事前推奨禁止・免責明記・誇大表現禁止）。(3) BACKLOGから実験を1件進める。(4) git commit し、BUSINESS_PROTOCOL.mdと自動メモリを更新する。金商法ガードレールに抵触する変更は一切禁止。" --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >> ai_business_loop.log 2>&1
