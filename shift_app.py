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
    {"name": "中学生自習対応・マナビス (16時半開始)", "start_time": datetime.time(16, 30), "end_time": datetime.time(21, 40)}, # 水曜デフォルト用
    {"name": "中学生自習対応・マナビス (日曜昼)", "start_time": datetime.time(13, 30), "end_time": datetime.time(18, 0)},
    # 木曜日の新しいデフォルトシフト用のプリセット
    {"name": "小5ONLINE英語のサポート/中学生自習対応・マナビス", "start_time": datetime.time(18, 0), "end_time": datetime.time(21, 40)},
    # 他にも必要なプリセットがあれば追加
]

# --- ここからパスワード保護の関数 (Secrets利用版) ---
def check_password():
    """パスワードが正しいかチェックし、正しければTrueを返す"""
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

# --- 初期化: st.session_stateに必要なキーが存在しない場合に設定 ---
if 'employees' not in st.session_state:
    st.session_state.employees = [] 

if 'timetable' not in st.session_state:
    st.session_state.timetable = {} 

if 'schedule_period_start' not in st.session_state:
    st.session_state.schedule_period_start = datetime.date.today()

if 'schedule_period_end' not in st.session_state:
    st.session_state.schedule_period_end = datetime.date.today() + datetime.timedelta(days=6)

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
                key=f"available_dates_{selected_emp_id_for_dates}"
            )
            if st.button(f"{employee_to_edit['name']}さんの勤務可能日を更新", key=f"update_dates_btn_{selected_emp_id_for_dates}"):
                employee_to_edit['available_dates'] = new_available_dates
                st.success(f"{employee_to_edit['name']}さんの勤務可能日を更新しました。")

st.subheader("登録済み従業員リスト")
if st.session_state.employees:
    emp_data_display = []
    for emp in st.session_state.employees:
        available_dates_str = ", ".join([d.strftime("%m/%d") for d in sorted(emp['available_dates'])]) if emp['available_dates'] else "未登録"
        emp_data_display.append({
            "ID": emp['id'], "名前": emp['name'], "希望日数": emp['desired_shifts'], "勤務可能日": available_dates_str
        })
    st.dataframe(pd.DataFrame(emp_data_display))
    emp_to_delete_id = st.selectbox(
        "削除する従業員を選択 (注意: 即時削除されます)",
        options=[None] + [emp['id'] for emp in st.session_state.employees],
        format_func=lambda x: "選択してください" if x is None else next(emp['name'] for emp in st.session_state.employees if emp['id'] == x),
        key="emp_delete_select"
    )
    if emp_to_delete_id and st.button("選択した従業員を削除", key="delete_emp_btn"):
        st.session_state.employees = [emp for emp in st.session_state.employees if emp['id'] != emp_to_delete_id]
        st.rerun()
else:
    st.info("まだ従業員が登録されていません。")

# --- 2. タイムテーブル管理セクション ---
st.header("2. タイムテーブル管理")
st.subheader("スケジュール期間設定")
col_period1, col_period2 = st.columns(2)
period_changed = False
# st.session_stateから現在の期間を読み込む
current_start = st.session_state.schedule_period_start
current_end = st.session_state.schedule_period_end

with col_period1:
    new_period_start = st.date_input("開始日", value=current_start, key="period_start_input")
with col_period2:
    new_period_end = st.date_input("終了日", value=current_end, key="period_end_input")

# 期間が変更されたかチェック
if new_period_start != current_start or new_period_end != current_end:
    st.session_state.schedule_period_start = new_period_start
    st.session_state.schedule_period_end = new_period_end
    period_changed = True 

# --- デフォルトシフト適用ロジック ---
if st.session_state.schedule_period_start <= st.session_state.schedule_period_end:
    default_shifts_config = {
        0: [("中学生自習対応・マナビス (18時開始)", 1)],  # Monday
        1: [("中学生自習対応・マナビス (18時開始)", 1)],  # Tuesday
        2: [("中学生自習対応・マナビス (16時半開始)", 1)],  # Wednesday (NEW)
        3: [("小5ONLINE英語のサポート/中学生自習対応・マナビス", 1)],  # Thursday (MODIFIED)
        4: [("中学生自習対応・マナビス (18時開始)", 1)],  # Friday
        5: [("速読・自習室巡回", 1), ("自習対応・マナビス", 1)],  # Saturday
        6: [("中学生自習対応・マナビス (日曜昼)", 1)]  # Sunday
    }

    date_to_scan = st.session_state.schedule_period_start
    while date_to_scan <= st.session_state.schedule_period_end:
        if not st.session_state.timetable.get(date_to_scan): # その日にシフトがなければデフォルト適用
            day_of_week = date_to_scan.weekday()
            default_presets_for_day = default_shifts_config.get(day_of_week, [])
            if default_presets_for_day:
                st.session_state.timetable[date_to_scan] = [] 
                for preset_name, req_people in default_presets_for_day:
                    preset_details = next((p for p in SHIFT_PRESETS if p["name"] == preset_name), None)
                    if preset_details:
                        new_default_shift = {
                            'id': str(uuid.uuid4()), 'name': preset_details["name"],
                            'start_time': preset_details["start_time"], 'end_time': preset_details["end_time"],
                            'required_people': req_people
                        }
                        st.session_state.timetable[date_to_scan].append(new_default_shift)
                    else:
                        st.warning(f"デフォルト設定エラー: プリセット '{preset_name}' がSHIFT_PRESETSリストに見つかりません。")
        date_to_scan += datetime.timedelta(days=1)

if period_changed: 
    st.rerun()

st.info(f"現在のスケジュール期間: {st.session_state.schedule_period_start.strftime('%Y-%m-%d')} ～ {st.session_state.schedule_period_end.strftime('%Y-%m-%d')}")

with st.expander("シフト枠を設定・編集する"):
    if st.session_state.schedule_period_start > st.session_state.schedule_period_end:
        st.error("スケジュール期間の終了日は開始日以降に設定してください。")
    else:
        num_days = (st.session_state.schedule_period_end - st.session_state.schedule_period_start).days + 1
        if num_days > 0 :
            date_list_for_timetable = [st.session_state.schedule_period_start + datetime.timedelta(days=x) for x in range(num_days)]
            selected_date_for_shift = st.selectbox(
                "シフト枠を設定する日付を選択", options=date_list_for_timetable,
                format_func=lambda d: d.strftime("%Y-%m-%d (%a)"), key="date_select_for_shift"
            )
          # (「2. タイムテーブル管理」セクション > with st.expander("シフト枠を設定・編集する"): の中)
# ...
            if selected_date_for_shift:
                st.markdown(f"**{selected_date_for_shift.strftime('%Y-%m-%d (%a)')} のシフト枠設定**")
                # 既存シフト枠の表示と削除機能
                if selected_date_for_shift in st.session_state.timetable and st.session_state.timetable[selected_date_for_shift]:
                    st.write("--- デバッグ情報: 既存シフト枠表示開始 ---")
                    st.write(f"対象日付: {selected_date_for_shift}")
                    st.write(f"現在のタイムテーブル（対象日付）: {st.session_state.timetable[selected_date_for_shift]}")
                    
                    st.write("既存のシフト枠:")
                    shifts_for_day = st.session_state.timetable[selected_date_for_shift][:] 
                    
                    for i, shift_to_display in enumerate(shifts_for_day):
                        cols = st.columns([3,2,2,1,1])
                        cols[0].text(f"{shift_to_display['name']}")
                        cols[1].text(f"{shift_to_display['start_time'].strftime('%H:%M')}")
                        cols[2].text(f"- {shift_to_display['end_time'].strftime('%H:%M')}")
                        cols[3].text(f"{shift_to_display['required_people']}人")
                        
                        # ボタンのキーをより確実にユニークにするため日付も文字列フォーマット
                        button_key = f"delete_shift_{selected_date_for_shift.strftime('%Y%m%d')}_{shift_to_display['id']}"
                        
                        if cols[4].button("削除", key=button_key):
                            st.write(f"--- デバッグ情報: 「削除」ボタン '{button_key}' が押されました ---")
                            st.write(f"削除しようとしているシフトID: {shift_to_display['id']}")
                            st.write(f"削除しようとしているシフト名: {shift_to_display['name']}")
                            st.write(f"削除前のタイムテーブル（対象日付）: {st.session_state.timetable[selected_date_for_shift]}")

                            # 削除ロジック
                            original_list = st.session_state.timetable[selected_date_for_shift]
                            filtered_list = [s for s in original_list if s['id'] != shift_to_display['id']]
                            st.session_state.timetable[selected_date_for_shift] = filtered_list
                            
                            st.write(f"削除後のタイムテーブル（対象日付）: {st.session_state.timetable.get(selected_date_for_shift, '日付エントリなし')}")

                            if not st.session_state.timetable.get(selected_date_for_shift): # リストが空になった場合
                                if selected_date_for_shift in st.session_state.timetable: # キーが存在すれば削除
                                    del st.session_state.timetable[selected_date_for_shift]
                                st.write(f"--- デバッグ情報: 日付 {selected_date_for_shift} のエントリをtimetableから削除しました ---")
                            
                            st.success(f"シフト '{shift_to_display['name']}' の削除処理を実行しました。画面を再読み込みします。")
                            st.rerun()
                    st.write("--- デバッグ情報: 既存シフト枠表示終了 ---")
# ...
                
                with st.form(f"new_shift_form_{selected_date_for_shift}", clear_on_submit=True):
                    preset_options = ["手動入力"] + [p["name"] for p in SHIFT_PRESETS]
                    selected_preset_name = st.selectbox(
                        "シフトプリセットを選択 (または「手動入力」)",
                        options=preset_options,
                        key=f"preset_select_{selected_date_for_shift}"
                    )
                    final_shift_name_manual = "" 
                    default_manual_start_time = datetime.time(9, 0)
                    default_manual_end_time = datetime.time(17, 0)
                    final_start_time_input_val = default_manual_start_time
                    final_end_time_input_val = default_manual_end_time

                    if selected_preset_name == "手動入力":
                        final_shift_name_manual = st.text_input("シフト名 (例: 早番, 遅番)", key=f"manual_shift_name_{selected_date_for_shift}")
                        col_time1, col_time2 = st.columns(2)
                        final_start_time_input_val = col_time1.time_input("開始時刻", default_manual_start_time, key=f"manual_start_time_{selected_date_for_shift}")
                        final_end_time_input_val = col_time2.time_input("終了時刻", default_manual_end_time, key=f"manual_end_time_{selected_date_for_shift}")
                    else:
                        selected_preset_details = next((p for p in SHIFT_PRESETS if p["name"] == selected_preset_name), None)
                        if selected_preset_details:
                            st.markdown(f"**選択中プリセット:** {selected_preset_details['name']} ({selected_preset_details['start_time'].strftime('%H:%M')} - {selected_preset_details['end_time'].strftime('%H:%M')})")
                        else: 
                            st.error("選択されたプリセットが見つかりません。「手動入力」モードで入力してください。")
                            final_shift_name_manual = st.text_input("シフト名 (プリセットエラーのため手動入力)", key=f"manual_shift_name_error_{selected_date_for_shift}")
                            col_time1, col_time2 = st.columns(2)
                            final_start_time_input_val = col_time1.time_input("開始時刻 (プリセットエラーのため手動入力)", default_manual_start_time, key=f"manual_start_time_error_{selected_date_for_shift}")
                            final_end_time_input_val = col_time2.time_input("終了時刻 (プリセットエラーのため手動入力)", default_manual_end_time, key=f"manual_end_time_error_{selected_date_for_shift}")
                            selected_preset_name = "手動入力" 

                    required_people = st.number_input("必要人数", min_value=1, step=1, key=f"req_people_{selected_date_for_shift}")
                    submitted_shift = st.form_submit_button("このシフト枠を追加")

                    if submitted_shift:
                        actual_shift_name = ""
                        actual_start_time = None
                        actual_end_time = None
                        if selected_preset_name == "手動入力":
                            actual_shift_name = final_shift_name_manual
                            actual_start_time = final_start_time_input_val
                            actual_end_time = final_end_time_input_val
                            if not actual_shift_name: 
                                st.error("シフト名を入力してください。")
                                st.stop() 
                        else: 
                            preset_data = next((p for p in SHIFT_PRESETS if p["name"] == selected_preset_name), None)
                            if preset_data: 
                                actual_shift_name = preset_data["name"]
                                actual_start_time = preset_data["start_time"]
                                actual_end_time = preset_data["end_time"]
                            else: 
                                st.error("プリセットデータの取得に失敗しました。")
                                st.stop()
                        if actual_start_time is None or actual_end_time is None:
                             st.error("開始時刻または終了時刻が設定されていません。")
                             st.stop()
                        if actual_start_time >= actual_end_time:
                            st.error("終了時刻は開始時刻より後に設定してください。")
                        else:
                            shift_id = str(uuid.uuid4())
                            new_shift = {
                                'id': shift_id, 'name': actual_shift_name,
                                'start_time': actual_start_time, 'end_time': actual_end_time,
                                'required_people': required_people
                            }
                            if selected_date_for_shift not in st.session_state.timetable:
                                st.session_state.timetable[selected_date_for_shift] = []
                            st.session_state.timetable[selected_date_for_shift].append(new_shift)
                            st.success(f"{selected_date_for_shift.strftime('%Y-%m-%d')}に「{actual_shift_name}」シフトを追加しました。")
                            st.rerun()
        else:
            st.warning("スケジュール期間を正しく設定してください。")

st.subheader("設定済みタイムテーブル概要")
if st.session_state.timetable:
    timetable_display_data = []
    active_dates_in_period = [st.session_state.schedule_period_start + datetime.timedelta(days=x) for x in range((st.session_state.schedule_period_end - st.session_state.schedule_period_start).days + 1)]
    sorted_timetable_keys = sorted(st.session_state.timetable.keys())
    for date_key in sorted_timetable_keys:
        if date_key in active_dates_in_period: 
            for shift in st.session_state.timetable[date_key]:
                timetable_display_data.append({
                    "日付": date_key.strftime("%Y-%m-%d (%a)"), "シフト名": shift['name'],
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
            employees_map = {emp['id']: emp.copy() for emp in st.session_state.employees} 
            for emp_id in employees_map: 
                employees_map[emp_id]['actual_shifts'] = 0
            all_positions = []
            active_dates_in_timetable_keys = [d for d in st.session_state.timetable.keys() if st.session_state.schedule_period_start <= d <= st.session_state.schedule_period_end]
            for date_val in sorted(active_dates_in_timetable_keys): 
                if date_val in st.session_state.timetable: 
                    for shift_slot in st.session_state.timetable[date_val]:
                        for i in range(shift_slot['required_people']):
                            all_positions.append({
                                'date': date_val, 'shift_id': shift_slot['id'],
                                'shift_name': shift_slot['name'], 'start_time': shift_slot['start_time'],
                                'end_time': shift_slot['end_time'], 'position_index': i, 
                                'assigned_employee_id': None, 'assigned_employee_name': "未割当"
                            })
            daily_assignment_tracker = defaultdict(lambda: defaultdict(bool)) 
            num_total_positions = len(all_positions)
            MAX_ITERATIONS = num_total_positions * 2 
            for iteration in range(MAX_ITERATIONS):
                best_assignment = None
                max_need_score = -float('inf') 
                unassigned_positions_indices = [idx for idx, pos in enumerate(all_positions) if pos['assigned_employee_id'] is None]
                if not unassigned_positions_indices: break 
                possible_assignments = []
                for emp_id, emp_details in employees_map.items():
                    need_score = emp_details['desired_shifts'] - emp_details['actual_shifts']
                    for pos_idx in unassigned_positions_indices:
                        current_pos = all_positions[pos_idx]
                        date_of_pos = current_pos['date']
                        if date_of_pos in emp_details['available_dates'] and not daily_assignment_tracker[emp_id][date_of_pos]:
                            possible_assignments.append({'emp_id': emp_id, 'pos_idx': pos_idx, 'need_score': need_score})
                if not possible_assignments: break 
                possible_assignments.sort(key=lambda x: x['need_score'], reverse=True)
                best_assignment_info = possible_assignments[0]
                assigned_emp_id = best_assignment_info['emp_id']
                assigned_pos_idx = best_assignment_info['pos_idx']
                all_positions[assigned_pos_idx]['assigned_employee_id'] = assigned_emp_id
                all_positions[assigned_pos_idx]['assigned_employee_name'] = employees_map[assigned_emp_id]['name']
                employees_map[assigned_emp_id]['actual_shifts'] += 1
                daily_assignment_tracker[assigned_emp_id][all_positions[assigned_pos_idx]['date']] = True
            st.session_state.generated_schedule = pd.DataFrame(all_positions)
            summary_data = []
            for emp_id, emp_details in employees_map.items():
                summary_data.append({
                    "従業員名": emp_details['name'], "希望シフト数": emp_details['desired_shifts'],
                    "実績シフト数": emp_details['actual_shifts'], "差": emp_details['actual_shifts'] - emp_details['desired_shifts']
                })
            st.session_state.employee_summary = pd.DataFrame(summary_data)
            st.success("シフト生成が完了しました！")

if st.session_state.generated_schedule is not None:
    st.subheader("生成されたシフト表")
    display_df = st.session_state.generated_schedule.copy()
    if not display_df.empty:
        display_df = display_df.sort_values(by=['date', 'start_time', 'shift_name']) 
        display_df['date_str'] = display_df['date'].apply(lambda x: x.strftime("%Y-%m-%d (%a)"))
        display_df['start_time_str'] = display_df['start_time'].apply(lambda x: x.strftime("%H:%M"))
        display_df['end_time_str'] = display_df['end_time'].apply(lambda x: x.strftime("%H:%M"))
        try:
            schedule_pivot = display_df.pivot_table(
                index=['date_str', 'shift_name', 'start_time_str', 'end_time_str'], 
                columns='position_index', values='assigned_employee_name', aggfunc='first' 
            ).reset_index()
            schedule_pivot = schedule_pivot.rename(columns={'date_str':'日付', 'shift_name':'シフト名', 'start_time_str':'開始', 'end_time_str':'終了'})
            num_담당자_cols = len([col for col in schedule_pivot.columns if isinstance(col, int)])
            rename_cols = {i: f'担当者{i+1}' for i in range(num_담당자_cols)}
            schedule_pivot = schedule_pivot.rename(columns=rename_cols)
            st.dataframe(schedule_pivot)
            excel_data = generate_excel(schedule_pivot, st.session_state.employee_summary)
            st.download_button(
                label="Excelファイルとしてダウンロード", data=excel_data,
                file_name=f"shift_schedule_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel_btn"
            )
        except Exception as e:
            st.error(f"シフト表の表示整形中にエラーが発生しました: {e}")
            st.dataframe(display_df[['date_str', 'shift_name', 'start_time_str', 'end_time_str', 'assigned_employee_name']]) 
    st.subheader("従業員別シフト集計")
    st.dataframe(st.session_state.employee_summary)
else:
    st.info("「シフトを自動生成する」ボタンを押してシフトを作成してください。")

st.markdown("---")
st.markdown("開発中のアプリケーションです。不具合や改善点がある可能性があります。")
