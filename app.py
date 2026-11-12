import json
import time
import random
from datetime import datetime
import streamlit as st

# 1. 頁面配置
st.set_page_config(
    page_title="職前訓練甄試 850 題全真模考與錯題消滅閉環系統",
    page_icon="🎓",
    layout="wide"
)

# 2. 載入題庫
@st.cache_data
def load_all_quiz_data():
    with open("quiz_database_gemini_format.json", "r", encoding="utf-8") as f:
        return json.load(f)

ALL_QUIZ_DATA = load_all_quiz_data()

# 劃分 17 回，每回 25 題通用 + 25 題理工 = 50 題
@st.cache_data
def partition_17_rounds(data):
    gen_list = [q for q in data if "通用" in q.get("category", "")]
    prof_list = [q for q in data if "理工" in q.get("category", "")]
    
    rounds = {}
    for r in range(1, 18):
        gen_slice = gen_list[(r - 1) * 25 : r * 25]
        prof_slice = prof_list[(r - 1) * 25 : r * 25]
        rounds[f"Round_{r}"] = gen_slice + prof_slice
    return rounds

ROUND_SETS = partition_17_rounds(ALL_QUIZ_DATA)

# 3. 狀態管理
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "current_round" not in st.session_state:
    st.session_state.current_round = 1
if "round_wrong_bank" not in st.session_state:
    st.session_state.round_wrong_bank = {}
if "round_history" not in st.session_state:
    st.session_state.round_history = {}
if "question_error_stats" not in st.session_state:
    st.session_state.question_error_stats = {}
if "central_db" not in st.session_state:
    st.session_state.central_db = {}

if "active_exam_questions" not in st.session_state:
    st.session_state.active_exam_questions = []
if "current_q_index" not in st.session_state:
    st.session_state.current_q_index = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()
if "exam_mode" not in st.session_state:
    st.session_state.exam_mode = "main"

# 4. 雲端後台同步函式
def record_to_central_db(user_id, round_name, score, time_spent, wrong_count):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rec = {
        "user_id": user_id,
        "round": round_name,
        "score": score,
        "time_spent_seconds": time_spent,
        "remaining_wrong": wrong_count,
        "timestamp": now_str
    }
    if user_id not in st.session_state.central_db:
        st.session_state.central_db[user_id] = []
    st.session_state.central_db[user_id].append(rec)

# 5. 側邊欄
st.sidebar.title("🎓 甄試全真模考系統")

view_mode = st.sidebar.selectbox("系統切換", ["測驗學員端", "管理員雲端後台"])

if view_mode == "管理員雲端後台":
    st.title("🛡️ 雲端中央管理後台 (總資料庫視角)")
    st.caption("所有測驗者之作答數據、每回得分、作答耗時與錯題次數全部即時匯集於此。")
    
    col1, col2, col3 = st.columns(3)
    total_users = len(st.session_state.central_db)
    total_records = sum(len(r) for r in st.session_state.central_db.values())
    col1.metric("註冊測驗者總人數", f"{total_users} 人")
    col2.metric("累積提交考卷總回數", f"{total_records} 次")
    col3.metric("資料庫實體題庫量", f"{len(ALL_QUIZ_DATA)} 題 (17回)")

    st.subheader("📋 全體測驗者作答歷程明細")
    if total_users == 0:
        st.info("目前尚無學員交卷紀錄，數據將在學員交卷後自動匯流至本後台。")
    else:
        grid_data = []
        for uid, records in st.session_state.central_db.items():
            for r_item in records:
                grid_data.append({
                    "學員姓名/學號": r_item["user_id"],
                    "考卷期別": r_item["round"],
                    "得分": f"{r_item['score']} 分",
                    "答題耗時": f"{r_item['time_spent_seconds'] // 60}分 {r_item['time_spent_seconds'] % 60}秒",
                    "殘留錯題數": r_item["remaining_wrong"],
                    "交卷時間": r_item["timestamp"]
                })
        st.dataframe(grid_data, use_container_width=True)

    st.subheader("⚠️ 高頻易錯題排行榜 (Top 10)")
    sorted_errs = sorted(st.session_state.question_error_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    if sorted_errs:
        q_dict_all = {q["id"]: q for q in ALL_QUIZ_DATA}
        err_table = []
        for qid, count in sorted_errs:
            q_info = q_dict_all.get(qid, {})
            err_table.append({
                "題號 ID": qid,
                "累積答錯次數": f"{count} 次",
                "專業分類": q_info.get("sub_category", ""),
                "題目摘要": q_info.get("question", "")[:45] + "..."
            })
        st.table(err_table)
    else:
        st.caption("尚無錯題統計數據。")

    st.divider()
    st.subheader("📦 匯出中央總數據庫")
    central_json = json.dumps(st.session_state.central_db, ensure_ascii=False, indent=2)
    st.download_button(
        "💾 下載中央資料庫備份 (JSON)",
        data=central_json,
        file_name="central_database_backup.json",
        mime="application/json"
    )
    st.stop()

# 測驗者模式
if not st.session_state.is_logged_in:
    st.sidebar.subheader("👤 測驗者登入")
    input_user = st.sidebar.text_input("請輸入姓名或學號：", placeholder="例如：李志豪 或 202601")
    if st.sidebar.button("🚀 開始測驗", type="primary", use_container_width=True):
        if input_user.strip():
            st.session_state.user_name = input_user.strip()
            st.session_state.is_logged_in = True
            st.rerun()
        else:
            st.sidebar.error("請輸入姓名或學號！")
    st.sidebar.divider()
    st.sidebar.info("💡 **規範說明**：\n• 真實題庫 850 題地毯式複習\n• 17 回嚴格不重複 (每回50題)\n• 專業50% + 通用50%\n• 錯題強制淘汰閉環 (全對才能解鎖下一回)")
    st.stop()

st.sidebar.success(f"目前學員：**{st.session_state.user_name}**")
if st.sidebar.button("🚪 登出 / 切換學員"):
    st.session_state.is_logged_in = False
    st.rerun()

st.sidebar.divider()
st.sidebar.header("📊 17 回地毯式進度")
curr_r = st.session_state.current_round
wrong_num = len(st.session_state.round_wrong_bank)

st.sidebar.markdown(f"**當前進度：【第 {curr_r} 回】 / 共 17 回**")
if wrong_num > 0:
    st.sidebar.error(f"⚠️ 第 {curr_r} 回尚有 **{wrong_num} 題錯題** 待消滅！")
    st.sidebar.caption(f"🔒 系統已鎖定：必須將第 {curr_r} 回錯題全數答對，方可開啟第 {curr_r + 1} 回新測驗。")
else:
    st.sidebar.success(f"✅ 第 {curr_r} 回無任何錯題殘留！")

st.sidebar.divider()
st.sidebar.header("⏱️ 測驗時間模式")
timer_enabled = st.sidebar.toggle("啟用 60 分鐘倒數計時", value=False)
st.sidebar.caption("💡 關閉計時為『不計時自由翻書模式』，系統仍會全程精確記錄作答總耗時以供學習診斷。")

user_data = {
    "user_name": st.session_state.user_name,
    "current_round": st.session_state.current_round,
    "round_history": st.session_state.round_history,
    "remaining_wrong_count": len(st.session_state.round_wrong_bank)
}
st.sidebar.download_button(
    "📥 匯出個人學習報告 (JSON)",
    data=json.dumps(user_data, ensure_ascii=False, indent=2),
    file_name=f"quiz_record_{st.session_state.user_name}.json",
    mime="application/json",
    use_container_width=True
)

# 6. 測驗引擎與閉環切換
def init_main_round(round_num):
    round_key = f"Round_{round_num}"
    st.session_state.active_exam_questions = ROUND_SETS[round_key].copy()
    random.shuffle(st.session_state.active_exam_questions)
    st.session_state.current_q_index = 0
    st.session_state.user_answers = {}
    st.session_state.submitted = False
    st.session_state.start_time = time.time()
    st.session_state.exam_mode = "main"

def init_wrong_retest():
    st.session_state.active_exam_questions = list(st.session_state.round_wrong_bank.values())
    random.shuffle(st.session_state.active_exam_questions)
    st.session_state.current_q_index = 0
    st.session_state.user_answers = {}
    st.session_state.submitted = False
    st.session_state.start_time = time.time()
    st.session_state.exam_mode = "retest_wrong"

if not st.session_state.active_exam_questions:
    if len(st.session_state.round_wrong_bank) > 0:
        init_wrong_retest()
    else:
        init_main_round(st.session_state.current_round)

active_list = st.session_state.active_exam_questions
total_q = len(active_list)
idx = st.session_state.current_q_index
curr_round_num = st.session_state.current_round

if st.session_state.exam_mode == "main":
    st.title(f"📝 職前訓練甄試全真模考【第 {curr_round_num} 回】")
    st.caption(f"全卷配比：50 題 (理工專業 25 題 + 智力與國數 25 題) ｜ 測驗者：{st.session_state.user_name}")
else:
    st.title(f"🚨 第 {curr_round_num} 回【錯題消滅淘汰賽】")
    st.warning(f"本輪尚有 **{total_q} 題錯題**。答對即刻銷案剔除，答錯繼續保留於錯題本，直至全數答對方能解鎖下一回！")

st.divider()

# 7. 答題介面
if not st.session_state.submitted:
    elapsed = int(time.time() - st.session_state.start_time)
    e_mins, e_secs = divmod(elapsed, 60)
    
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        if timer_enabled:
            remain = max(0, 3600 - elapsed)
            r_m, r_s = divmod(remain, 60)
            if remain <= 0:
                st.session_state.submitted = True
                st.rerun()
            st.error(f"⏳ 剩餘時間：**{r_m:02d}:{r_s:02d}**")
        else:
            st.success(f"☕ 自由翻書練習中（已用時：{e_mins}分 {e_secs}秒）")
    with col_t2:
        st.info(f"📌 當前題號：第 **{idx + 1}** / {total_q} 題")

    st.progress((idx + 1) / total_q)
    
    item = active_list[idx]
    st.subheader(f"【{item['category']} ➔ {item['sub_category']}】")
    st.markdown(f"#### **第 {idx + 1} 題：{item['question']}**")
    
    saved_choice = st.session_state.user_answers.get(item["id"], None)
    default_opt_idx = 0
    if saved_choice:
        for opt_i, opt_text in enumerate(item["options"]):
            if opt_text.startswith(f"({saved_choice})"):
                default_opt_idx = opt_i
                break
                
    chosen = st.radio(
        "請選擇答案：",
        options=item["options"],
        index=default_opt_idx,
        key=f"radio_{item['id']}_{st.session_state.exam_mode}_{idx}"
    )
    if chosen:
        st.session_state.user_answers[item["id"]] = chosen[1]

    st.write("")
    btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
    with btn_c1:
        if st.button("⬅️ 上一題", disabled=(idx == 0), use_container_width=True):
            st.session_state.current_q_index -= 1
            st.rerun()
    with btn_c2:
        if st.button("下一題 ➡️", disabled=(idx == total_q - 1), use_container_width=True):
            st.session_state.current_q_index += 1
            st.rerun()
    with btn_c3:
        if st.button("🚀 完成交卷", type="primary", use_container_width=True):
            st.session_state.submitted = True
            st.rerun()

# 8. 成果結算、錯題淘汰與推理解析指引
else:
    elapsed_total = int(time.time() - st.session_state.start_time)
    mins_tot, secs_tot = divmod(elapsed_total, 60)
    
    correct_count = 0
    for q in active_list:
        ans_u = st.session_state.user_answers.get(q["id"], "未作答")
        if ans_u == q["answer"]:
            correct_count += 1
            if q["id"] in st.session_state.round_wrong_bank:
                del st.session_state.round_wrong_bank[q["id"]]
        else:
            st.session_state.question_error_stats[q["id"]] = st.session_state.question_error_stats.get(q["id"], 0) + 1
            st.session_state.round_wrong_bank[q["id"]] = q

    score = int((correct_count / total_q) * 100)
    round_label = f"Round_{curr_round_num}"
    if st.session_state.exam_mode == "main":
        st.session_state.round_history[round_label] = {
            "score": score,
            "time_spent": elapsed_total,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    record_to_central_db(
        user_id=st.session_state.user_name,
        round_name=round_label if st.session_state.exam_mode == "main" else f"{round_label}_錯題特訓",
        score=score,
        time_spent=elapsed_total,
        wrong_count=len(st.session_state.round_wrong_bank)
    )

    st.balloons()
    st.header("🎯 測驗成績與診斷報告")
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("本次得分", f"{score} 分")
    m_col2.metric("答對率", f"{correct_count} / {total_q} 題")
    m_col3.metric("作答總耗時", f"{mins_tot}分 {secs_tot}秒")
    m_col4.metric("本回待消滅錯題", f"{len(st.session_state.round_wrong_bank)} 題")

    st.divider()

    # 錯題消滅閉環控制
    st.subheader("🔄 錯題消滅閉環控制")
    remaining_errors = len(st.session_state.round_wrong_bank)
    
    if remaining_errors > 0:
        st.error(f"⚠️ 第 {curr_round_num} 回尚有 **{remaining_errors} 題錯題** 未完全答對！依照閉環規定，**禁止進入第 {curr_round_num + 1} 回**。")
        if st.button(f"🔥 立即開啟第 {curr_round_num} 回【{remaining_errors} 題錯題重測淘汰賽】", type="primary", use_container_width=True):
            init_wrong_retest()
            st.rerun()
    else:
        st.success(f"🎉 太棒了！第 {curr_round_num} 回的 50 題已【全數完全答對且消滅】！")
        if curr_round_num < 17:
            next_r = curr_round_num + 1
            if st.button(f"➡️ 解鎖並抽題進入【第 {next_r} 回】全新 50 題全真模考", type="primary", use_container_width=True):
                st.session_state.current_round = next_r
                st.session_state.round_wrong_bank = {}
                init_main_round(next_r)
                st.rerun()
        else:
            st.balloons()
            st.success("🏆 恭喜大滿貫！您已地毯式完成全數 17 回（850 題）之全真模擬考與錯題消滅！")

    st.divider()

    # 試題推理解析指引
    st.subheader("💡 試題推理解析與步驟指引（免翻書標準依據）")
    for q_i, q_item in enumerate(active_list):
        user_choice = st.session_state.user_answers.get(q_item["id"], "未作答")
        is_ok = (user_choice == q_item["answer"])
        tag = "✅ 【答對】" if is_ok else "❌ 【答錯】"
        
        with st.expander(f"{tag} 第 {q_i + 1} 題：{q_item['question'][:45]}... (您的答案: {user_choice} / 正確答案: {q_item['answer']})"):
            st.markdown(f"**完整題幹**：{q_item['question']}")
            st.markdown(f"**專業分類**：{q_item['category']} ➔ `{q_item['sub_category']}`")
            st.markdown("**選項內容**：")
            for o in q_item["options"]:
                st.markdown(f"- {o}")
            st.markdown(f"**標準答案**：`({q_item['answer']})`")
            st.info(f"{q_item['explanation']}")
