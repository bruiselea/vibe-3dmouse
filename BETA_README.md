# SpaceMouse Codex Bridge 0.1.0-beta.1

Windows 11 x64と3Dconnexion SpaceMouse Compact向けの身内検証版です。
Codexを起動するとSpaceMouse入力をCodex Micro互換HIDへ送り、Codex終了後に公式3DxWareへ戻します。

## 必要環境

- Windows 11 x64 build 22000以降
- OpenAI Codex Windowsアプリ
- 3Dconnexion SpaceMouse Compact (VID 256F / PID C635)

## 注意

- ベータ用証明書をPCの信頼ストアへ登録します。信頼できる配布元から受け取ったSetup.exeだけを使用してください。
- 通常画面を閉じるとタスクトレイへ移動します。完全に停止する場合はトレイメニューの「終了」を使います。
- 設定とログは `%LOCALAPPDATA%\SpaceMouseCodex` に保存されます。
- アンインストール後も割り当て設定は再導入用に保持されます。

問題が起きた場合は、ダッシュボードの「ログを開く」から `app.log` を共有してください。

