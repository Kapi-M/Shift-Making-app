import streamlit as st
import pandas as pd
import datetime
import uuid # For unique IDs
from io import BytesIO
from collections import defaultdict

# --- シフトプリセットの定義 ---
SHIFT_PRESETS = [
    {"name": "早番", "start_time": datetime.time(9, 0), "end_time": datetime.time(17, 0)},
    {"name": "遅番", "start_time": datetime.time(13, 0), "end_time": datetime.time(21, 0)},
    {"name": "通し", "start_time": datetime.time(9, 0), "end_time": datetime.time(21, 0)},
    {"name": "中抜け", "start_time": datetime.time(10, 0), "end_time": datetime.time(19, 0)},
    {"name": "中学生自習対応・マナビス (18時開始)", "start_time": datetime.time(18, 0), "end_time": datetime.time(21, 40)}, 
    {"name": "速読・自習室巡回", "start_time": datetime.time(9, 0), "end_time": datetime.time(12, 30)}, 
    {"name": "自習対応・マナビス", "start_time": datetime.time(15, 30), "end_time": datetime.time(21, 0)}, 
    {"name": "中学生自習対応・マナビス (16時半開始)", "start_time": datetime.time(16, 30), "end_time": datetime.time(21, 40)}, 
    {"name": "中学生自習対応・マナビス (日曜昼)", "start_time": datetime.time(13, 30), "end_time": datetime.time(18, 0)},
    {"name": "小5ONLINE英語のサポート/中学生自習対応・マナビス", "start_time": datetime.time(18, 0), "end_time": datetime.time(21, 40)},
]

# --- ここからパスワード保護の関数 (Secrets利用版) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    correct_password_from_secrets = None
    try:
        if hasattr(st, 'secrets') and "APP_PASSWORD" in st.secrets:
            correct_password_from_secrets = st.secrets["APP_PASSWORD"]
        else:
            if not hasattr(st, 'secrets'): 
                st.info("ローカル環境: Secretsファイルが見つかりません。テスト用の仮パスワードを使用します。")
                correct_password_from_secrets = "local_default" 
            elif "APP_PASSWORD" not in st.secrets: 
                st.error("管理者: アプリケーションのSecretsにAPP_PASSWORDが設定されていません。")
                return False
    except Exception as e:
        st.warning(f"Secretsの読み込み中に予期せぬエラーが発生しました: {e}")
        st.info("ローカル環境ですか？ テスト用の仮パスワードを使用します。")
        correct_password_from_secrets = "local_default" 
    if correct_password_from_secrets is None: 
        st.error("パスワード設定に問題があります。管理者に連絡してください。")
        return False
    user_password = st.text_input("パスワードを入力してください:", type="password", key="password_input_secrets")
    if st.button("ログイン", key="login_button_secrets"):
        if user_password == correct_password_from_secrets:
            st.session_state.password_correct = True
            st.rerun() 
        else:
            st.error("パスワードが正しくありません。")
            st.session_state.password_correct = False 
    return False

if not check_password():
    st.stop() 
# --- パスワード保護ここまで ---

# --- アプリケーションのタイトル ---
st.title("シフト管理アプリケーション (Streamlit版)")

# --- 初期化: st.session_state ---
if 'employees' not in st.session_state: st.session_state.employees = [] 
if 'timetable' not in st.session_state: st.session_state.timetable = {} 
if 'schedule_period_start' not in st.session_state: st.session_state.schedule_period_start = datetime.date.today()
if 'schedule_period_end' not in st.session_state: st.session_state.schedule_period_end = datetime.date.today() + datetime.timedelta(days=6)
if 'generated_schedule' not in st.session_state: st.session_state.generated_schedule = None
if 'employee_summary' not in st.session_state: st.session_state.employee_summary = None

# --- Helper Functions ---
def generate_excel(schedule_df, summary_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if schedule_df is not None and not schedule_df.empty: schedule_df.to_excel(writer, sheet_name='シフト表', index=False)
        if summary_df is not None and not summary_df.empty: summary_df.to_excel(writer, sheet_name='従業員別集計', index=False)
    return output.getvalue()

# --- 1. 従業員管理 ---
st.header("1. 従業員管理")
# (従業員管理のUIコードは変更なしなので省略しています... 前回のコードを参照してください)
with st.expander("従業員を追加する"):
    with st.form("new_employee_form", clear_on_submit=True):
        emp_name = st.text_input("従業員名", key="emp_name_input")
        desired_shifts = st.number_input("希望シフト日数", min_value=0, step=1, key="desired_shifts_input")
        submitted_emp = st.form_submit_button("従業員を追加")
        if submitted_emp and emp_name:
            emp_id = str(uuid.uuid4())
            st.session_state.employees.append({'id': emp_id, 'name': emp_name, 'desired_shifts': desired_shifts, 'available_dates': []})
            st.success(f"{emp_name}さんを追加しました。次に勤務可能日を登録してください。")
if st.session_state.employees:
    with st.expander("勤務可能日を登録・編集する"):
        selected_emp_id_for_dates = st.selectbox("従業員を選択", options=[emp['id'] for emp in st.session_state
