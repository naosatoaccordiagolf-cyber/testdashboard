# UENO DAILY

上野・御徒町の天気・飲食店・ニュースをまとめるカード型ダッシュボード。

公開手順：Settings > Pages > Source を GitHub Actions に変更し、Actions から Update and publish Ueno Daily を実行する。毎朝7時 JST に更新予定。無料プランで公開する場合は、公開可能な内容のみであることを確認し Public に変更する。

データ取得元：Open-Meteo、OpenStreetMap Overpass、Google News RSS。取得失敗時は前回データを表示する。店舗情報は営業状況を保証しない。ニュースはRSS順。