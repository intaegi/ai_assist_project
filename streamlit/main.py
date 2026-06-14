import streamlit as st

# データフレームの準備
import pandas as pd
df = pd.DataFrame({
    '1列目' : [1, 2, 3, 4],
    '2列目' : [10, 20, 30, 40]
})

# タイトルとテキストを記入
st.title('Streamlit 基礎')
st.write('Hello Lims World!')

# 動的なテーブル
st.dataframe(df)

# 静的なテーブル
st.table(df)

# 10 行 3 列のデータフレームを準備
import numpy as np
df = pd.DataFrame(
    np.random.rand(10,3),
    columns = ['a', 'b', 'c']
)

# 折れ線グラフ
st.line_chart(df)
# 面グラフ
st.area_chart(df)
# 棒グラフ
st.bar_chart(df)

# セレクトボックス
option = st.selectbox(
    '好きな数字を入力してください。',
    list(range(1, 11))
)
'あなたの好きな数字は' , option , 'です。'

# テキスト入力による値の動的変更
text = st.text_input('あなたの好きなスポーツを教えて下さい。')
'あなたの好きなスポーツ：' , text


# スライダーによる値の動的変更
condition = st.slider('あなたの今の調子は？', 0, 100, 50)
'コンディション：' , condition

col1, col2, col3 = st.columns(3)
col1.metric("Temperature", "70 °F", "1.2 °F")
col2.metric("Wind", "9 mph", "-8%")
col3.metric("Humidity", "86%", "4%")


# 1.
# 上から下に並ぶのが基本ですが、横並びにしたい場合や、タブで分けたい場合は、専用の「レイアウト関数」を使います。
# 横に分割する (st.columns): 画面を2列や3列に分ける
# タブで分ける (st.tabs): パネルを切り替えるタブを作れる
# サイドバー (st.sidebar): 画面の左側にメニューや設定をまとめられます。
# ==========================================
# ① st.sidebar （サイドバー：画面の左側）
# ==========================================
# with st.sidebar:
#     st.title("設定メニュー")
#     st.write("ここに置いたものは左側に固定されます。")
    
#     # サイドバーの中に入力欄を作る
#     user_name = st.text_input("あなたのお名前は？", key="sidebar_name")
#     condition = st.slider("今の体調は？", 0, 100, 80, key="sidebar_slider")

# # メイン画面のタイトル
# st.title(f"ようこそ！ {user_name} さん")
# # ==========================================
# # ② st.tabs （タブ：画面の切り替え）
# # ==========================================
# # タブの名前をリストで指定して、それぞれのタブの変数を作ります
# tab1, tab2 = st.tabs(["メイン操作", "データ分析"])

# # 「メイン操作」タブの中身
# with tab1:
#     st.header("メインの操作画面です")
#     st.write("ここに普段使うボタンや入力欄を並べます。")
    
#     # ==========================================
#     # ③ st.columns （カラム：横並び）
#     # ==========================================
#     st.write("---")
#     st.subheader("横並びのレイアウト（st.columns）")
    
#     # 画面を横に「3分割」します
#     col1, col2, col3 = st.columns(3)
    
#     with col1:
#         st.success("1列目（左）")
#         sport = st.selectbox("好きなスポーツ", ["野球", "サッカー", "ポーカー"], key="main_sport")
        
#     with col2:
#         st.info("2列目（中央）")
#         st.write(f"選ばれたのは: **{sport}**")
        
#     with col3:
#         st.warning("3列目（右）")
#         st.write(f"現在の体調は: **{condition}%**")
# # 「データ分析」タブの中身
# with tab2:
#     st.header("分析レポート画面です")
#     st.write("タブを切り替えることで、画面をスッキリ整理できます。")
#     # 例として簡単な折れ線グラフを表示してみます
#     st.line_chart([10, 30, 20, 50, 40])

# キカガク_吉原（よしはら） 12:46 PM
# 2.
# Streamlitの仕様変更によって、自分で書いたCSSのクラス名が効かなくなることがあるため、公式の関数やテーマ設定で表現できないかまずは検討することをおすすめします。