import streamlit as st
import pandas as pd
import datetime
import uuid # For unique IDs
from io import BytesIO
from collections import defaultdict
# shift_app.py の冒頭部分の check_password 関数内を修正

import streamlit as st

# --- ここからパスワード保護の例 (Secrets利用版) ---
def check_password():
    """パスワードが正しいかチェックし、正しければTrueを返す"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    # Streamlit CloudのSecretsから正しいパスワードを取得
    # Secretsに "APP_PASSWORD" というキーで設定した場合
    try:
        # st.secretsが辞書のように振る舞うか、属性としてアクセスできるかによる
        # 一般的には辞書形式でのアクセスが推奨される
        if "APP_PASSWORD" in st.secrets:
            correct_password_from_secrets = st.secrets["APP_PASSWORD"]
        else:
            # ローカル開発時など、Secretsが設定されていない場合のフォールバック
            # またはエラー処理
            st.error("管理者: アプリケーションのSecretsにAPP_PASSWORDが設定されていません。")
            # ローカルテスト用にデフォルトパスワードを設定することも可能ですが、本番ではSecretsを使うべきです
            # correct_password_from_secrets = "local_test_password" # 例: ローカルテスト用
            return False # Secretsがない場合はログイン不可とするのが安全
            
    except Exception as e:
        # st.secretsが存在しない場合 (ローカル実行時でsecretsファイルがない場合など)
        st.warning(f"Secretsの読み込みに失敗しました。ローカル環境ですか？ ({e})")
        # ローカルテスト用にデフォルトパスワードを設定することも可能
        # correct_password_from_secrets = "local_test_password" # 例: ローカルテスト用
        # 本番環境ではSecretsが設定されている前提
        # このフォールバックはローカルでのテストを容易にするためですが、
        # 本番デプロイ時はStreamlit Cloud側でSecretsが正しく設定されている必要があります。
        # ここでは、ローカルでst.secretsがない場合も考慮して、仮のパスワードを設定するか、エラーにします。
        # 今回はエラーにせず、仮のパスワード（またはログイン不可）を想定します。
        # より安全なのは、Secretsがない場合はログインさせないことです。
        if hasattr(st, 'secrets') and "APP_PASSWORD" in st.secrets: # 再度確認
             correct_password_from_secrets = st.secrets["APP_PASSWORD"]
        else: # ローカル環境やSecrets未設定を想定
            st.info("パスワード認証のセットアップ中です。ローカルテスト用の仮パスワードを使用します。")
            correct_password_from_secrets = "local_default" # ← ローカルテスト用の仮パスワード。本番では使われません。


    user_password = st.text_input("パスワードを入力してください:", type="password", key="password_input_secrets")
    if st.button("ログイン", key="login_button_secrets"):
        if user_password == correct_password_from_secrets:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")
            st.session_state.password_correct = False # 念のため
    return False

if not check_password():
    st.stop()
# --- パスワード保護の例ここまで ---

# --- これ以降に、これまでのシフト管理アプリのメインコードを記述 ---
# st.title("シフト管理アプリケーション (Streamlit版)")
# ... (残りのアプリコードは変更なし) ...
# --- アプリケーションのタイトル ---
st.title("シフト管理アプリケーション (Streamlit版)")

# --- 初期化: st.session_stateに必要なキーが存在しない場合に設定 ---
if 'employees' not in st.session_state:
    st.session_state.employees = [] # {'id': str, 'name': str, 'desired_shifts': int, 'available_dates': [datetime.date]}

if 'timetable' not in st.session_state:
    st.session_state.timetable = {} # {datetime.date: [{'id': str, 'name': str, 'start_time': datetime.time, 'end_time': datetime.time, 'required_people': int}]}

if 'schedule_period_start' not in st.session_state:
    st.session_state.schedule_period_start = datetime.date.today()

if 'schedule_period_end' not in st.session_state:
    st.session_state.schedule_period_end = datetime.date.today() + datetime.timedelta(days=6) # デフォルトで1週間

if 'generated_schedule' not in st.session_state:
    st.session_state.generated_schedule = None

if 'employee_summary' not in st.session_state:
    st.session_state.employee_summary = None

# --- Helper Functions ---
def generate_excel(schedule_df, summary_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if schedule_df is not None and not schedule_df.empty:
            schedule_df.to_excel(writer, sheet_name='シフト表', index=False)
        if summary_df is not None and not summary_df.empty:
            summary_df.to_excel(writer, sheet_name='従業員別集計', index=False)
    processed_data = output.getvalue()
    return processed_data

# --- 1. 従業員管理セクション ---
st.header("1. 従業員管理")

# 従業員追加フォーム
with st.expander("従業員を追加する"):
    with st.form("new_employee_form", clear_on_submit=True):
        emp_name = st.text_input("従業員名", key="emp_name_input")
        desired_shifts = st.number_input("希望シフト日数", min_value=0, step=1, key="desired_shifts_input")
        submitted_emp = st.form_submit_button("従業員を追加")

        if submitted_emp and emp_name:
            emp_id = str(uuid.uuid4())
            st.session_state.employees.append({
                'id': emp_id,
                'name': emp_name,
                'desired_shifts': desired_shifts,
                'available_dates': []
            })
            st.success(f"{emp_name}さんを追加しました。次に勤務可能日を登録してください。")

# 勤務可能日登録
if st.session_state.employees:
    with st.expander("勤務可能日を登録・編集する"):
        selected_emp_id_for_dates = st.selectbox(
            "従業員を選択",
            options=[emp['id'] for emp in st.session_state.employees],
            format_func=lambda x: next(emp['name'] for emp in st.session_state.employees if emp['id'] == x),
            key="emp_select_for_dates"
        )
        if selected_emp_id_for_dates:
            employee_to_edit = next(emp for emp in st.session_state.employees if emp['id'] == selected_emp_id_for_dates)

            # 勤務可能日の入力 (st.multiselectを使用)
            # まず、スケジュール期間内の日付リストを生成
            date_options = []
            if st.session_state.schedule_period_start and st.session_state.schedule_period_end and \
               st.session_state.schedule_period_start <= st.session_state.schedule_period_end:
                current_date_opt = st.session_state.schedule_period_start
                while current_date_opt <= st.session_state.schedule_period_end:
                    date_options.append(current_date_opt)
                    current_date_opt += datetime.timedelta(days=1)

            if not date_options:
                st.warning("先に「2. タイムテーブル管理」でスケジュール期間を設定してください。")

            current_available_dates = employee_to_edit['available_dates']
            new_available_dates = st.multiselect(
                f"{employee_to_edit['name']}さんの勤務可能日を選択 (スケジュール期間内)",
                options=date_options,
                default=current_available_dates,
                format_func=lambda d: d.strftime("%Y-%m-%d (%a)"),
                key=f"available_dates_{selected_emp_id_for_dates}" # ユニークキー
            )
            if st.button(f"{employee_to_edit['name']}さんの勤務可能日を更新", key=f"update_dates_btn_{selected_emp_id_for_dates}"):
                employee_to_edit['available_dates'] = new_available_dates
                st.success(f"{employee_to_edit['name']}さんの勤務可能日を更新しました。")


# 従業員リスト表示
st.subheader("登録済み従業員リスト")
if st.session_state.employees:
    emp_data_display = []
    for emp in st.session_state.employees:
        available_dates_str = ", ".join([d.strftime("%m/%d") for d in sorted(emp['available_dates'])]) if emp['available_dates'] else "未登録"
        emp_data_display.append({
            "ID": emp['id'],
            "名前": emp['name'],
            "希望日数": emp['desired_shifts'],
            "勤務可能日": available_dates_str
        })
    st.dataframe(pd.DataFrame(emp_data_display))

    # 従業員削除 (シンプルな実装)
    emp_to_delete_id = st.selectbox(
        "削除する従業員を選択 (注意: 即時削除されます)",
        options=[None] + [emp['id'] for emp in st.session_state.employees],
        format_func=lambda x: "選択してください" if x is None else next(emp['name'] for emp in st.session_state.employees if emp['id'] == x),
        key="emp_delete_select"
    )
    if emp_to_delete_id and st.button("選択した従業員を削除", key="delete_emp_btn"):
        st.session_state.employees = [emp for emp in st.session_state.employees if emp['id'] != emp_to_delete_id]
        st.rerun() # 画面を再描画してリストを更新
else:
    st.info("まだ従業員が登録されていません。")

# --- 2. タイムテーブル管理セクション ---
st.header("2. タイムテーブル管理")

# スケジュール期間設定
st.subheader("スケジュール期間設定")
col_period1, col_period2 = st.columns(2)
with col_period1:
    new_period_start = st.date_input("開始日", value=st.session_state.schedule_period_start, key="period_start_input")
with col_period2:
    new_period_end = st.date_input("終了日", value=st.session_state.schedule_period_end, key="period_end_input")

if new_period_start != st.session_state.schedule_period_start or new_period_end != st.session_state.schedule_period_end:
    st.session_state.schedule_period_start = new_period_start
    st.session_state.schedule_period_end = new_period_end
    # 期間が変更されたら、期間外のタイムテーブルデータをクリアする（またはユーザーに確認する）
    # ここでは簡略化のため、そのまま保持するが、実際の運用では注意が必要
    st.rerun()


st.info(f"現在のスケジュール期間: {st.session_state.schedule_period_start.strftime('%Y-%m-%d')} ～ {st.session_state.schedule_period_end.strftime('%Y-%m-%d')}")

# シフト枠設定
with st.expander("シフト枠を設定・編集する"):
    if st.session_state.schedule_period_start > st.session_state.schedule_period_end:
        st.error("スケジュール期間の終了日は開始日以降に設定してください。")
    else:
        # 日付選択
        num_days = (st.session_state.schedule_period_end - st.session_state.schedule_period_start).days + 1
        if num_days > 0 :
            date_list_for_timetable = [st.session_state.schedule_period_start + datetime.timedelta(days=x) for x in range(num_days)]
            selected_date_for_shift = st.selectbox(
                "シフト枠を設定する日付を選択",
                options=date_list_for_timetable,
                format_func=lambda d: d.strftime("%Y-%m-%d (%a)"),
                key="date_select_for_shift"
            )

            if selected_date_for_shift:
                st.markdown(f"**{selected_date_for_shift.strftime('%Y-%m-%d (%a)')} のシフト枠設定**")

                # その日の既存シフト枠表示
                if selected_date_for_shift in st.session_state.timetable and st.session_state.timetable[selected_date_for_shift]:
                    st.write("既存のシフト枠:")
                    for i, shift in enumerate(st.session_state.timetable[selected_date_for_shift]):
                        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns([2,2,2,1,1])
                        col_s1.text(f"{shift['name']}")
                        col_s2.text(f"{shift['start_time'].strftime('%H:%M')}")
                        col_s3.text(f"- {shift['end_time'].strftime('%H:%M')}")
                        col_s4.text(f"{shift['required_people']}人")
                        if col_s5.button("削除", key=f"delete_shift_{selected_date_for_shift}_{shift['id']}"):
                            st.session_state.timetable[selected_date_for_shift] = [s for s in st.session_state.timetable[selected_date_for_shift] if s['id'] != shift['id']]
                            if not st.session_state.timetable[selected_date_for_shift]: # リストが空になったらキー自体を削除
                                del st.session_state.timetable[selected_date_for_shift]
                            st.rerun()


                # 新しいシフト枠追加フォーム
                with st.form(f"new_shift_form_{selected_date_for_shift}", clear_on_submit=True):
                    shift_name = st.text_input("シフト名 (例: 早番, 遅番)", key=f"shift_name_{selected_date_for_shift}")
                    col_time1, col_time2 = st.columns(2)
                    start_time = col_time1.time_input("開始時刻", datetime.time(9, 0), key=f"start_time_{selected_date_for_shift}")
                    end_time = col_time2.time_input("終了時刻", datetime.time(17, 0), key=f"end_time_{selected_date_for_shift}")
                    required_people = st.number_input("必要人数", min_value=1, step=1, key=f"req_people_{selected_date_for_shift}")
                    submitted_shift = st.form_submit_button("このシフト枠を追加")

                    if submitted_shift and shift_name:
                        if start_time >= end_time:
                            st.error("終了時刻は開始時刻より後に設定してください。")
                        else:
                            shift_id = str(uuid.uuid4())
                            new_shift = {
                                'id': shift_id,
                                'name': shift_name,
                                'start_time': start_time,
                                'end_time': end_time,
                                'required_people': required_people
                            }
                            if selected_date_for_shift not in st.session_state.timetable:
                                st.session_state.timetable[selected_date_for_shift] = []
                            st.session_state.timetable[selected_date_for_shift].append(new_shift)
                            st.success(f"{selected_date_for_shift.strftime('%Y-%m-%d')}に「{shift_name}」シフトを追加しました。")
                            st.rerun() # フォーム送信後にリストを更新するため
        else:
            st.warning("スケジュール期間を正しく設定してください。")


# タイムテーブル全体表示 (簡易)
st.subheader("設定済みタイムテーブル概要")
if st.session_state.timetable:
    timetable_display_data = []
    sorted_dates = sorted(st.session_state.timetable.keys())
    for date_key in sorted_dates:
        if date_key >= st.session_state.schedule_period_start and date_key <= st.session_state.schedule_period_end:
            for shift in st.session_state.timetable[date_key]:
                timetable_display_data.append({
                    "日付": date_key.strftime("%Y-%m-%d (%a)"),
                    "シフト名": shift['name'],
                    "時間": f"{shift['start_time'].strftime('%H:%M')} - {shift['end_time'].strftime('%H:%M')}",
                    "必要人数": shift['required_people']
                })
    if timetable_display_data:
        st.dataframe(pd.DataFrame(timetable_display_data))
    else:
        st.info("期間内に設定されたシフト枠はありません。")
else:
    st.info("まだシフト枠が設定されていません。")


# --- 3. シフト自動生成と出力 ---
st.header("3. シフト自動生成と出力")

if st.button("シフトを自動生成する", key="generate_shifts_btn"):
    if not st.session_state.employees:
        st.error("従業員が登録されていません。先に従業員を登録してください。")
    elif not st.session_state.timetable:
        st.error("タイムテーブルが設定されていません。先にタイムテーブルを設定してください。")
    else:
        with st.spinner("シフトを生成中です..."):
            # --- コアアルゴリズム ---
            employees_map = {emp['id']: emp.copy() for emp in st.session_state.employees} # .copy()で変更を分離
            for emp_id in employees_map: # 実際の割り当て数を初期化
                employees_map[emp_id]['actual_shifts'] = 0

            # 1. 割り当てるべき全ポジションのリストを作成
            all_positions = []
            active_dates_in_timetable = sorted([d for d in st.session_state.timetable.keys() if st.session_state.schedule_period_start <= d <= st.session_state.schedule_period_end])

            for date_val in active_dates_in_timetable:
                if date_val in st.session_state.timetable:
                    for shift_slot in st.session_state.timetable[date_val]:
                        for i in range(shift_slot['required_people']):
                            all_positions.append({
                                'date': date_val,
                                'shift_id': shift_slot['id'],
                                'shift_name': shift_slot['name'],
                                'start_time': shift_slot['start_time'],
                                'end_time': shift_slot['end_time'],
                                'position_index': i, # 同一シフト内の何番目の枠か
                                'assigned_employee_id': None,
                                'assigned_employee_name': "未割当"
                            })

            # 2. 従業員の日毎の割り当てを追跡する辞書
            daily_assignment_tracker = defaultdict(lambda: defaultdict(bool)) # emp_id -> date -> True/False

            # 3. 割り当て処理 (シンプルな欲張り法)
            #    希望シフト数と実績の差が大きい従業員を優先
            #    何回かループして割り当てを試みる (改善の余地あり)
            MAX_ITERATIONS = sum(shift['required_people'] for date_shifts in st.session_state.timetable.values() for shift in date_shifts) * 2 # 適当な上限

            for iteration in range(MAX_ITERATIONS):
                best_assignment = None
                max_need_score = -float('inf') # より多くシフトが必要な人

                # 未割り当てのポジションを探す
                unassigned_positions_indices = [idx for idx, pos in enumerate(all_positions) if pos['assigned_employee_id'] is None]
                if not unassigned_positions_indices:
                    break # 全て割り当て済みか、これ以上割り当て不可

                for pos_idx in unassigned_positions_indices:
                    current_pos = all_positions[pos_idx]
                    date_of_pos = current_pos['date']

                    # このポジションに割り当て可能な従業員を探す
                    for emp_id, emp_details in employees_map.items():
                        if date_of_pos in emp_details['available_dates'] and not daily_assignment_tracker[emp_id][date_of_pos]:
                            # この従業員の「必要度」を計算
                            need_score = emp_details['desired_shifts'] - emp_details['actual_shifts']
                            if need_score > max_need_score:
                                max_need_score = need_score
                                best_assignment = (emp_id, pos_idx)
                            # TODO: 同点の場合の処理 (例: 残り勤務可能日が少ない人など)

                if best_assignment:
                    assigned_emp_id, assigned_pos_idx = best_assignment
                    all_positions[assigned_pos_idx]['assigned_employee_id'] = assigned_emp_id
                    all_positions[assigned_pos_idx]['assigned_employee_name'] = employees_map[assigned_emp_id]['name']

                    employees_map[assigned_emp_id]['actual_shifts'] += 1
                    daily_assignment_tracker[assigned_emp_id][all_positions[assigned_pos_idx]['date']] = True
                else:
                    # このイテレーションで割り当てられるものがなかった
                    break

            st.session_state.generated_schedule = pd.DataFrame(all_positions)

            # 従業員サマリー作成
            summary_data = []
            for emp_id, emp_details in employees_map.items():
                summary_data.append({
                    "従業員名": emp_details['name'],
                    "希望シフト数": emp_details['desired_shifts'],
                    "実績シフト数": emp_details['actual_shifts'],
                    "差": emp_details['actual_shifts'] - emp_details['desired_shifts']
                })
            st.session_state.employee_summary = pd.DataFrame(summary_data)
            st.success("シフト生成が完了しました！")


if st.session_state.generated_schedule is not None:
    st.subheader("生成されたシフト表")
    # シフト表の表示形式を改善 (例: pivot_table)
    # ここではDataFrameをそのまま表示
    display_df = st.session_state.generated_schedule.copy()
    display_df['date'] = display_df['date'].apply(lambda x: x.strftime("%Y-%m-%d (%a)"))
    display_df['start_time'] = display_df['start_time'].apply(lambda x: x.strftime("%H:%M"))
    display_df['end_time'] = display_df['end_time'].apply(lambda x: x.strftime("%H:%M"))

    # 表示用に整形（ピボットテーブルなど）
    # 簡単な例：日付とシフト名でグループ化し、担当者を表示
    if not display_df.empty:
        try:
            # シフト表を整形
            schedule_pivot = display_df.pivot_table(
                index=['date', 'shift_name', 'start_time', 'end_time'],
                columns='position_index', # 従業員を横に並べる
                values='assigned_employee_name',
                aggfunc='first' # 複数の値がある場合（通常はないはず）
            ).reset_index()

            # カラム名を '担当者1', '担当者2', ... のように変更
            num_担当者_cols = len([col for col in schedule_pivot.columns if isinstance(col, int)])
            rename_cols = {i: f'担当者{i+1}' for i in range(num_担当者_cols)}
            schedule_pivot = schedule_pivot.rename(columns=rename_cols)

            st.dataframe(schedule_pivot)

            excel_data = generate_excel(schedule_pivot, st.session_state.employee_summary)
            st.download_button(
                label="Excelファイルとしてダウンロード",
                data=excel_data,
                file_name=f"shift_schedule_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel_btn"
            )
        except Exception as e:
            st.error(f"シフト表の表示整形中にエラーが発生しました: {e}")
            st.dataframe(display_df[['date', 'shift_name', 'start_time', 'end_time', 'assigned_employee_name']]) # エラー時は素のデータを表示

    st.subheader("従業員別シフト集計")
    st.dataframe(st.session_state.employee_summary)

else:
    st.info("「シフトを自動生成する」ボタンを押してシフトを作成してください。")

st.markdown("---")
st.markdown("開発中のアプリケーションです。不具合や改善点がある可能性があります。")
