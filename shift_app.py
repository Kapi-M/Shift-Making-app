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
        selected_emp_id_for_dates = st.selectbox("従業員を選択", options=[emp['id'] for emp in st.session_state.employees], format_func=lambda x: next(emp['name'] for emp in st.session_state.employees if emp['id'] == x), key="emp_select_for_dates")
        if selected_emp_id_for_dates:
            employee_to_edit = next(emp for emp in st.session_state.employees if emp['id'] == selected_emp_id_for_dates)
            date_options = []
            if st.session_state.schedule_period_start and st.session_state.schedule_period_end and st.session_state.schedule_period_start <= st.session_state.schedule_period_end:
                current_date_opt = st.session_state.schedule_period_start
                while current_date_opt <= st.session_state.schedule_period_end: date_options.append(current_date_opt); current_date_opt += datetime.timedelta(days=1)
            if not date_options: st.warning("先に「2. タイムテーブル管理」でスケジュール期間を設定してください。")
            current_available_dates = employee_to_edit['available_dates']
            new_available_dates = st.multiselect(f"{employee_to_edit['name']}さんの勤務可能日を選択 (スケジュール期間内)", options=date_options, default=current_available_dates, format_func=lambda d: d.strftime("%Y-%m-%d (%a)"), key=f"available_dates_{selected_emp_id_for_dates}")
            if st.button(f"{employee_to_edit['name']}さんの勤務可能日を更新", key=f"update_dates_btn_{selected_emp_id_for_dates}"):
                employee_to_edit['available_dates'] = new_available_dates
                st.success(f"{employee_to_edit['name']}さんの勤務可能日を更新しました。")
st.subheader("登録済み従業員リスト")
if st.session_state.employees:
    emp_data_display = []
    for emp in st.session_state.employees:
        available_dates_str = ", ".join([d.strftime("%m/%d") for d in sorted(emp['available_dates'])]) if emp['available_dates'] else "未登録"
        emp_data_display.append({"ID": emp['id'], "名前": emp['name'], "希望日数": emp['desired_shifts'], "勤務可能日": available_dates_str})
    st.dataframe(pd.DataFrame(emp_data_display))
    emp_to_delete_id = st.selectbox("削除する従業員を選択 (注意: 即時削除されます)", options=[None] + [emp['id'] for emp in st.session_state.employees], format_func=lambda x: "選択してください" if x is None else next(emp['name'] for emp in st.session_state.employees if emp['id'] == x), key="emp_delete_select")
    if emp_to_delete_id and st.button("選択した従業員を削除", key="delete_emp_btn"):
        st.session_state.employees = [emp for emp in st.session_state.employees if emp['id'] != emp_to_delete_id]
        st.rerun()
else: st.info("まだ従業員が登録されていません。")


# --- 2. タイムテーブル管理セクション ---
st.header("2. タイムテーブル管理")
st.subheader("スケジュール期間設定")
col_period1, col_period2 = st.columns(2)
period_actually_changed = False # このランで期間が実際に変更されたかどうかのフラグ

# st.session_stateから現在の期間を読み込む (入力ウィジェットのデフォルト値用)
initial_period_start = st.session_state.schedule_period_start
initial_period_end = st.session_state.schedule_period_end

with col_period1:
    new_period_start_input = st.date_input("開始日", value=initial_period_start, key="period_start_input")
with col_period2:
    new_period_end_input = st.date_input("終了日", value=initial_period_end, key="period_end_input")

# 期間が変更されたかチェック
if new_period_start_input != initial_period_start or new_period_end_input != initial_period_end:
    st.session_state.schedule_period_start = new_period_start_input
    st.session_state.schedule_period_end = new_period_end_input
    period_actually_changed = True 

# --- デフォルトシフト適用ロジック (期間が実際に変更された場合のみ実行) ---
if period_actually_changed:
    if st.session_state.schedule_period_start <= st.session_state.schedule_period_end:
        default_shifts_config = {
            0: [("中学生自習対応・マナビス (18時開始)", 1)],  # Monday
            1: [("中学生自習対応・マナビス (18時開始)", 1)],  # Tuesday
            2: [("中学生自習対応・マナビス (16時半開始)", 1)],  # Wednesday
            3: [("小5ONLINE英語のサポート/中学生自習対応・マナビス", 1)],  # Thursday
            4: [("中学生自習対応・マナビス (18時開始)", 1)],  # Friday
            5: [("速読・自習室巡回", 1), ("自習対応・マナビス", 1)],  # Saturday
            6: [("中学生自習対応・マナビス (日曜昼)", 1)]  # Sunday
        }
        date_to_scan = st.session_state.schedule_period_start
        while date_to_scan <= st.session_state.schedule_period_end:
            if not st.session_state.timetable.get(date_to_scan): 
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
                            st.warning(f"デフォルト設定エラー(期間変更時): プリセット '{preset_name}' が見つかりません。")
            date_to_scan += datetime.timedelta(days=1)
    st.rerun() # 期間変更とデフォルト適用の反映のため再実行

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
            if selected_date_for_shift:
                st.markdown(f"**{selected_date_for_shift.strftime('%Y-%m-%d (%a)')} のシフト枠設定**")
                if selected_date_for_shift in st.session_state.timetable and st.session_state.timetable[selected_date_for_shift]:
                    st.write("既存のシフト枠:")
                    shifts_for_day = st.session_state.timetable[selected_date_for_shift][:] 
                    for i, shift_to_display in enumerate(shifts_for_day):
                        cols = st.columns([3,2,2,1,1])
                        cols[0].text(f"{shift_to_display['name']}")
                        cols[1].text(f"{shift_to_display['start_time'].strftime('%H:%M')}")
                        cols[2].text(f"- {shift_to_display['end_time'].strftime('%H:%M')}")
                        cols[3].text(f"{shift_to_display['required_people']}人")
                        button_key = f"delete_shift_{selected_date_for_shift.strftime('%Y%m%d')}_{shift_to_display['id']}"
                        if cols[4].button("削除", key=button_key):
                            st.session_state.timetable[selected_date_for_shift] = [s for s in st.session_state.timetable[selected_date_for_shift] if s['id'] != shift_to_display['id']]
                            if not st.session_state.timetable.get(selected_date_for_shift):
                                if selected_date_for_shift in st.session_state.timetable:
                                    del st.session_state.timetable[selected_date_for_shift]
                            st.rerun()
                
                with st.form(f"new_shift_form_{selected_date_for_shift}", clear_on_submit=True):
                    preset_options = ["手動入力"] + [p["name"] for p in SHIFT_PRESETS]
                    selected_preset_name = st.selectbox("シフトプリセットを選択 (または「手動入力」)", options=preset_options, key=f"preset_select_{selected_date_for_shift}")
                    final_shift_name_manual, default_manual_start_time, default_manual_end_time = "", datetime.time(9,0), datetime.time(17,0)
                    final_start_time_input_val, final_end_time_input_val = default_manual_start_time, default_manual_end_time

                    if selected_preset_name == "手動入力":
                        final_shift_name_manual = st.text_input("シフト名", key=f"manual_shift_name_{selected_date_for_shift}")
                        col_t1, col_t2 = st.columns(2)
                        final_start_time_input_val = col_t1.time_input("開始時刻", default_manual_start_time, key=f"manual_start_time_{selected_date_for_shift}")
                        final_end_time_input_val = col_t2.time_input("終了時刻", default_manual_end_time, key=f"manual_end_time_{selected_date_for_shift}")
                    else:
                        preset_details = next((p for p in SHIFT_PRESETS if p["name"] == selected_preset_name), None)
                        if preset_details: st.markdown(f"**選択中プリセット:** {preset_details['name']} ({preset_details['start_time'].strftime('%H:%M')} - {preset_details['end_time'].strftime('%H:%M')})")
                        else: # Should not happen if SHIFT_PRESETS is consistent
                            st.error("選択されたプリセット情報が見つかりません。「手動入力」を選択してください。")
                            selected_preset_name = "手動入力" # Fallback to manual

                    required_people = st.number_input("必要人数", min_value=1, step=1, key=f"req_people_{selected_date_for_shift}")
                    submitted_shift = st.form_submit_button("このシフト枠を追加")

                    if submitted_shift:
                        act_name, act_start, act_end = "", None, None
                        if selected_preset_name == "手動入力":
                            act_name, act_start, act_end = final_shift_name_manual, final_start_time_input_val, final_end_time_input_val
                            if not act_name: st.error("シフト名を入力してください。"); st.stop()
                        else:
                            preset = next((p for p in SHIFT_PRESETS if p["name"] == selected_preset_name), None)
                            if preset: act_name, act_start, act_end = preset["name"], preset["start_time"], preset["end_time"]
                            else: st.error("プリセットデータの再取得に失敗。"); st.stop()
                        
                        if act_start is None or act_end is None: st.error("時刻が未設定です。"); st.stop()
                        if act_start >= act_end: st.error("終了時刻は開始時刻より後に。"); st.stop()
                        
                        new_shift = {'id': str(uuid.uuid4()), 'name': act_name, 'start_time': act_start, 'end_time': act_end, 'required_people': required_people}
                        if selected_date_for_shift not in st.session_state.timetable: st.session_state.timetable[selected_date_for_shift] = []
                        st.session_state.timetable[selected_date_for_shift].append(new_shift)
                        st.success(f"{selected_date_for_shift.strftime('%Y-%m-%d')}に「{act_name}」シフトを追加。"); st.rerun()
        else: st.warning("スケジュール期間を正しく設定してください。")

st.subheader("設定済みタイムテーブル概要")
# (タイムテーブル概要表示コードは変更なしなので省略... 前回のコードを参照)
if st.session_state.timetable:
    timetable_display_data = []
    active_dates_in_period = [st.session_state.schedule_period_start + datetime.timedelta(days=x) for x in range((st.session_state.schedule_period_end - st.session_state.schedule_period_start).days + 1)] if st.session_state.schedule_period_start <= st.session_state.schedule_period_end else []
    sorted_timetable_keys = sorted(st.session_state.timetable.keys())
    for date_key in sorted_timetable_keys:
        if date_key in active_dates_in_period: 
            for shift in st.session_state.timetable[date_key]:
                timetable_display_data.append({"日付": date_key.strftime("%Y-%m-%d (%a)"), "シフト名": shift['name'], "時間": f"{shift['start_time'].strftime('%H:%M')} - {shift['end_time'].strftime('%H:%M')}", "必要人数": shift['required_people']})
    if timetable_display_data: st.dataframe(pd.DataFrame(timetable_display_data))
    else: st.info("期間内に設定されたシフト枠はありません。")
else: st.info("まだシフト枠が設定されていません。")

# --- 3. シフト自動生成と出力 ---
st.header("3. シフト自動生成と出力")
# (シフト自動生成と出力コードは変更なしなので省略... 前回のコードを参照)
if st.button("シフトを自動生成する", key="generate_shifts_btn"):
    if not st.session_state.employees: st.error("従業員が登録されていません。")
    elif not st.session_state.timetable: st.error("タイムテーブルが設定されていません。")
    else:
        with st.spinner("シフトを生成中です..."):
            employees_map = {emp['id']: emp.copy() for emp in st.session_state.employees} 
            for emp_id in employees_map: employees_map[emp_id]['actual_shifts'] = 0
            all_positions = []
            active_dates_keys = [d for d in st.session_state.timetable.keys() if st.session_state.schedule_period_start <= d <= st.session_state.schedule_period_end]
            for date_val in sorted(active_dates_keys): 
                if date_val in st.session_state.timetable: 
                    for shift_slot in st.session_state.timetable[date_val]:
                        for i in range(shift_slot['required_people']):
                            all_positions.append({'date': date_val, 'shift_id': shift_slot['id'], 'shift_name': shift_slot['name'], 'start_time': shift_slot['start_time'], 'end_time': shift_slot['end_time'], 'position_index': i, 'assigned_employee_id': None, 'assigned_employee_name': "未割当"})
            daily_assignment_tracker = defaultdict(lambda: defaultdict(bool)) 
            MAX_ITERATIONS = len(all_positions) * 2 
            for iteration in range(MAX_ITERATIONS):
                best_assignment, max_need_score = None, -float('inf') 
                unassigned_indices = [idx for idx, pos in enumerate(all_positions) if pos['assigned_employee_id'] is None]
                if not unassigned_indices: break 
                possible_assignments = []
                for emp_id, emp_details in employees_map.items():
                    need_score = emp_details['desired_shifts'] - emp_details['actual_shifts']
                    for pos_idx in unassigned_indices:
                        current_pos = all_positions[pos_idx]
                        if current_pos['date'] in emp_details['available_dates'] and not daily_assignment_tracker[emp_id][current_pos['date']]:
                            possible_assignments.append({'emp_id': emp_id, 'pos_idx': pos_idx, 'need_score': need_score})
                if not possible_assignments: break 
                possible_assignments.sort(key=lambda x: x['need_score'], reverse=True)
                best_assign_info = possible_assignments[0]
                assigned_emp_id, assigned_pos_idx = best_assign_info['emp_id'], best_assign_info['pos_idx']
                all_positions[assigned_pos_idx]['assigned_employee_id'] = assigned_emp_id
                all_positions[assigned_pos_idx]['assigned_employee_name'] = employees_map[assigned_emp_id]['name']
                employees_map[assigned_emp_id]['actual_shifts'] += 1
                daily_assignment_tracker[assigned_emp_id][all_positions[assigned_pos_idx]['date']] = True
            st.session_state.generated_schedule = pd.DataFrame(all_positions) if all_positions else pd.DataFrame() # 空の場合も考慮
            summary_data = [{"従業員名": emp['name'], "希望シフト数": emp['desired_shifts'], "実績シフト数": employees_map[emp['id']]['actual_shifts'], "差": employees_map[emp['id']]['actual_shifts'] - emp['desired_shifts']} for emp in st.session_state.employees]
            st.session_state.employee_summary = pd.DataFrame(summary_data) if summary_data else pd.DataFrame()
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
            schedule_pivot = display_df.pivot_table(index=['date_str', 'shift_name', 'start_time_str', 'end_time_str'], columns='position_index', values='assigned_employee_name', aggfunc='first').reset_index()
            schedule_pivot = schedule_pivot.rename(columns={'date_str':'日付', 'shift_name':'シフト名', 'start_time_str':'開始', 'end_time_str':'終了'})
            num_cols = len([col for col in schedule_pivot.columns if isinstance(col, int)])
            schedule_pivot = schedule_pivot.rename(columns={i: f'担当者{i+1}' for i in range(num_cols)})
            st.dataframe(schedule_pivot)
            excel_data = generate_excel(schedule_pivot, st.session_state.employee_summary)
            st.download_button(label="Excelファイルとしてダウンロード", data=excel_data, file_name=f"shift_schedule_{datetime.date.today().strftime('%Y%m%d')}.xlsx', mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_btn")
        except Exception as e:
            st.error(f"シフト表の表示整形中にエラーが発生しました: {e}")
            st.dataframe(display_df[['date_str', 'shift_name', 'start_time_str', 'end_time_str', 'assigned_employee_name']]) 
    st.subheader("従業員別シフト集計")
    if st.session_state.employee_summary is not None and not st.session_state.employee_summary.empty:
        st.dataframe(st.session_state.employee_summary)
    else:
        st.info("集計データがありません。")
else:
    st.info("「シフトを自動生成する」ボタンを押してシフトを作成してください。")

st.markdown("---")
st.markdown("開発中のアプリケーションです。不具合や改善点がある可能性があります。")
