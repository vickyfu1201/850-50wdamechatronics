# -*- coding: utf-8 -*-
import json
import time
import random
import io
import streamlit as st

# 1. 網頁基本設定
st.set_page_config(
    page_title="職前訓練甄試線上模擬測驗系統",
    page_icon="🎯",
    layout="wide"
)

# 2. 載入題庫資料庫（動態讀取，無任何死板硬編碼題數）
@st.cache_data
def load_quiz_data():
    with open("quiz_database_gemini_format.json", "r", encoding="utf-8") as f:
        return json.load(f)

all_quiz_data = load_quiz_data()
TOTAL_DB_QUESTIONS = len(all_quiz_data)

# 分離通用學科與專業學科
GENERAL_KEYWORDS = ["智力", "通用", "國文", "語義", "數學", "空間", "商業", "時間"]
general_pool = [q for q in all_quiz_data if any(k in q.get("category", "") or k in q.get("sub_category", "") for k in GENERAL_KEYWORDS)]
prof_pool = [q for q in all_quiz_data if q not in general_pool]

# 3. 初始化全域 Session 狀態
if "seen_ids" not in st.session_state:
    st.session_state.seen_ids = set()
if "wrong_bank" not in st.session_state:
    st.session_state.wrong_bank = {}  # { q_id: question_dict }
if "exam_round" not in st.session_state:
    st.session_state.exam_round = 1
if "exam_cycle" not in st.session_state:
    st.session_state.exam_cycle = 1
if "quiz_mode" not in st.session_state:
    st.session_state.quiz_mode = "normal"  # "normal" 或 "retest_mistakes"
if "history_records" not in st.session_state:
    st.session_state.history_records = []  # 歷史成績單紀錄

# 4. 側邊欄配置
st.sidebar.title("🛠️ 測驗控制台")
st.sidebar.caption(f"📚 目前題庫實體總量：**{TOTAL_DB_QUESTIONS} 題**")
st.sidebar.caption(f"🧠 通用學科：{len(general_pool)} 題 ｜ ⚙️ 機電專業：{len(prof_pool)} 題")

# 身分登入（支援學員與管理員分流）
st.sidebar.header("👤 測驗者資訊")
user_name = st.sidebar.text_input("請輸入您的姓名或座號：", value="學員01")
is_admin = st.sidebar.checkbox("🔒 切換至管理員雲端後台", value=False)

st.sidebar.divider()

# 時間設定模式
st.sidebar.header("⏱️ 計時模式設定")
enable_timer = st.sidebar.toggle("啟用倒數限時模式", value=False, help="關閉時為【不計時自由練習】，適合查閱筆記與書籍，系統仍會精確統計作答累積秒數")

if enable_timer:
    quiz_duration = st.sidebar.slider("測驗限時 (分鐘)：", min_value=10, max_value=90, value=50, step=5)
    TOTAL_SECONDS = quiz_duration * 60
else:
    TOTAL_SECONDS = None
    st.sidebar.info("☕ **不計時自由練習模式**：無時間倒數交卷壓力，可從容翻書推導！")

st.sidebar.divider()

# 錯題本即時監控
wrong_count = len(st.session_state.wrong_bank)
st.sidebar.header("🚨 累積錯題消滅閉環")
st.sidebar.metric(label="目前待銷案錯題數", value=f"{wrong_count} 題")

# 5. 抽題演算法：50% 通用 + 50% 專業，做過絕不重複
def get_new_50_questions():
    # 篩選本循環尚未做過的題目
    unseen_gen = [q for q in general_pool if q["id"] not in st.session_state.seen_ids]
    unseen_prof = [q for q in prof_pool if q["id"] not in st.session_state.seen_ids]
    
    # 若題庫池中剩餘未測題目少於 25 題，自動開啟下一輪全新循環
    if len(unseen_gen) < 25 or len(unseen_prof) < 25:
        st.session_state.seen_ids = set()
        st.session_state.exam_cycle += 1
        unseen_gen = list(general_pool)
        unseen_prof = list(prof_pool)
        st.toast(f"🎉 題庫已全部刷完一遍，自動開啟【第 {st.session_state.exam_cycle} 輪】循環測驗！", icon="🔄")
    
    sample_gen_count = min(25, len(unseen_gen))
    sample_prof_count = min(25, len(unseen_prof))
    
    picked_gen = random.sample(unseen_gen, sample_gen_count)
    picked_prof = random.sample(unseen_prof, sample_prof_count)
    
    exam = picked_gen + picked_prof
    random.shuffle(exam)
    
    # 登記已做過 ID
    for q in exam:
        st.session_state.seen_ids.add(q["id"])
        
    return exam

def start_new_exam():
    st.session_state.active_questions = get_new_50_questions()
    st.session_state.current_index = 0
    st.session_state.user_answers = {}
    st.session_state.submitted = False
    st.session_state.start_time = time.time()
    st.session_state.time_up = False
    st.session_state.quiz_mode = "normal"

def start_mistakes_retest():
    st.session_state.active_questions = list(st.session_state.wrong_bank.values())
    st.session_state.current_index = 0
    st.session_state.user_answers = {}
    st.session_state.submitted = False
    st.session_state.start_time = time.time()
    st.session_state.time_up = False
    st.session_state.quiz_mode = "retest_mistakes"

# 初始化題目
if "active_questions" not in st.session_state:
    start_new_exam()

# 側邊欄重新抽題
if st.sidebar.button("🔄 重新抽題並開始測驗", use_container_width=True):
    if len(st.session_state.wrong_bank) > 0:
        st.sidebar.error("⚠️ 尚有錯題未銷案！請先啟動【錯題淘汰賽】全數答對後方能開啟新回測驗。")
    else:
        start_new_exam()
        st.rerun()

# 備份匯出功能（100% 繁體中文 UTF-8-SIG，徹底杜絕亂碼）
st.sidebar.divider()
st.sidebar.header("📥 學習紀錄匯出（無亂碼）")

export_data = {
    "user_name": user_name,
    "exam_round": st.session_state.exam_round,
    "exam_cycle": st.session_state.exam_cycle,
    "seen_ids_count": len(st.session_state.seen_ids),
    "wrong_bank_count": len(st.session_state.wrong_bank),
    "history_records": st.session_state.history_records,
    "wrong_bank_items": list(st.session_state.wrong_bank.values())
}
json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8-sig')
st.sidebar.download_button(
    label="💾 匯出個人學習進度檔 (JSON)",
    data=json_bytes,
    file_name=f"{user_name}_甄試學習進度_{time.strftime('%Y%m%d_%H%M')}.json",
    mime="application/json",
    use_container_width=True
)

# ----------------- 主介面顯示邏輯 -----------------

# 若為管理員後台模式
if is_admin:
    st.title("📊 職訓甄試雲端總後台管理中心")
    st.caption("全體測驗者成績總攬、高頻易錯題排行榜與大數據分析")
    st.divider()
    
    col_a1, col_a2, col_a3 = st.columns(3)
    col_a1.metric("題庫納管總量", f"{TOTAL_DB_QUESTIONS} 題")
    col_a2.metric("累計測驗次數", f"{len(st.session_state.history_records)} 次")
    col_a3.metric("全站待銷案錯題數", f"{wrong_count} 題")
    
    st.subheader("📋 學員歷次測驗成果清單")
    if st.session_state.history_records:
        st.dataframe(st.session_state.history_records, use_container_width=True)
    else:
        st.info("目前尚未有學員完成交卷紀錄。")
        
    st.divider()
    st.subheader("🔥 全國高頻易錯題排行榜 (Top 5)")
    all_wrong_ids = [q_id for q_id in st.session_state.wrong_bank.keys()]
    if all_wrong_ids:
        st.warning("⚠️ 以下為學員當前最常失分的高頻題型，請加強教學複習：")
        for idx, qid in enumerate(all_wrong_ids[:5], 1):
            q_obj = st.session_state.wrong_bank[qid]
            with st.expander(f"Top {idx}【{q_obj['category']}】{q_obj['question']}"):
                st.write(f"**標準答案**：({q_obj['answer']})")
                st.info(f"💡 **法規與解析依據**：{q_obj['explanation']}")
    else:
        st.success("🎉 目前學員錯題皆已全數掌握銷案！")
    st.stop()

# 一般測驗主介面
active_quiz = st.session_state.active_questions
total_questions = len(active_quiz)
current_idx = st.session_state.current_index

if total_questions == 0:
    st.success("🎉 恭喜！所有錯題均已全數答對並銷案！")
    if st.button("🚀 開始全新一回 50 題全真測驗", type="primary"):
        start_new_exam()
        st.rerun()
    st.stop()

item = active_quiz[current_idx]

# A. 作答中介面
if not st.session_state.submitted:
    st.title("🎯 職前訓練甄試線上全真模擬考")
    if st.session_state.quiz_mode == "retest_mistakes":
        st.warning(f"🚨 **目前為【第 {st.session_state.exam_round} 回錯題消滅淘汰賽】**（剩餘待消滅錯題：{total_questions} 題）")
        st.caption("提示：唯有在重測中確實答對該題，系統才會將其自錯題本中銷案！")
    else:
        st.info(f"📝 **【第 {st.session_state.exam_round} 回 全真模擬考】**（固定 50 題：25 題通用 ＋ 25 題機電專業）")
    st.divider()

    # 頂部狀態列：計時器與進度
    col_t1, col_t2 = st.columns([1, 1])
    if TOTAL_SECONDS is not None:
        elapsed_time = time.time() - st.session_state.start_time
        remaining_seconds = TOTAL_SECONDS - elapsed_time
        if remaining_seconds <= 0:
            st.session_state.submitted = True
            st.session_state.time_up = True
            st.rerun()
        mins, secs = divmod(max(0, int(remaining_seconds)), 60)
        t_str = f"{mins:02d}:{secs:02d}"
        with col_t1:
            if remaining_seconds < 300:
                st.error(f"⏳ 剩餘倒數時間：**{t_str}**（即將截止！）")
            else:
                st.warning(f"⏱️ 剩餘倒數時間：**{t_str}**")
    else:
        elapsed_sec = int(time.time() - st.session_state.start_time)
        e_m, e_s = divmod(elapsed_sec, 60)
        with col_t1:
            st.success(f"☕ 自由翻書練習中（累計耗時：{e_m} 分 {e_s} 秒）")

    with col_t2:
        st.info(f"📌 作答進度：第 **{current_idx + 1}** / **{total_questions}** 題")

    st.progress((current_idx + 1) / total_questions)
    st.subheader(f"【{item['category']} ｜ {item['sub_category']}】")
    st.markdown(f"#### **{current_idx + 1}. {item['question']}**")

    # 選項狀態保留
    saved_ans = st.session_state.user_answers.get(item['id'], None)
    default_opt_idx = None
    if saved_ans:
        for idx, opt in enumerate(item['options']):
            if opt.startswith(f"({saved_ans})"):
                default_opt_idx = idx
                break

    selected_option = st.radio(
        "請選擇正確答案：",
        options=item['options'],
        index=default_opt_idx if default_opt_idx is not None else 0,
        key=f"radio_{item['id']}"
    )

    if selected_option:
        st.session_state.user_answers[item['id']] = selected_option[1]

    st.divider()
    # 翻頁導航按鈕列
    b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
    with b_col1:
        if st.button("⬅️ 上一題", disabled=(current_idx == 0), use_container_width=True):
            st.session_state.current_index -= 1
            st.rerun()
    with b_col2:
        if st.button("下一題 ➡️", disabled=(current_idx == total_questions - 1), use_container_width=True):
            st.session_state.current_index += 1
            st.rerun()
    with b_col3:
        if st.button("🚀 完成交卷", type="primary", use_container_width=True):
            st.session_state.submitted = True
            st.rerun()

# B. 交卷成績結算與深度解析檢討頁面
else:
    used_seconds = int(time.time() - st.session_state.start_time)
    u_mins, u_secs = divmod(used_seconds, 60)
    time_spent_str = f"{u_mins} 分 {u_secs} 秒"

    if st.session_state.time_up:
        st.error("⏰ 測驗時間截止！系統已自動為您強制交卷。")
    else:
        st.balloons()
        st.header("🎉 測驗完成！成績與診斷報告結算")

    # 批改作答與錯題淘汰閉環處理
    correct_count = 0
    current_wrong_list = []

    for q in active_quiz:
        u_ans = st.session_state.user_answers.get(q['id'])
        if u_ans == q['answer']:
            correct_count += 1
            # 錯題淘汰賽模式下：若答對，則自錯題本中銷案除去！
            if q['id'] in st.session_state.wrong_bank:
                del st.session_state.wrong_bank[q['id']]
        else:
            current_wrong_list.append(q)
            # 納入累積錯題本
            st.session_state.wrong_bank[q['id']] = q

    score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0

    # 記錄成績至歷程
    st.session_state.history_records.append({
        "學員姓名": user_name,
        "回數": f"第 {st.session_state.exam_round} 回",
        "測驗模式": "全真模考" if st.session_state.quiz_mode == "normal" else "錯題淘汰賽",
        "總題數": total_questions,
        "答對題數": correct_count,
        "得分": score,
        "總耗時": time_spent_str,
        "交卷時間": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    # 數據呈現
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("最終測驗得分", f"{score} 分", delta=f"{correct_count}/{total_questions} 題")
    col_s2.metric("作答總耗時", time_spent_str)
    col_s3.metric("目前錯題本殘留題數", f"{len(st.session_state.wrong_bank)} 題")

    st.divider()

    # 捷徑操作按鈕區（閉環控制）
    st.subheader("⚡ 下一步學習操作")
    act_col1, act_col2 = st.columns(2)

    has_remaining_wrongs = len(st.session_state.wrong_bank) > 0

    with act_col1:
        if has_remaining_wrongs:
            st.error(f"⚠️ 本回尚有 **{len(st.session_state.wrong_bank)} 題** 答錯！依閉環規定，必須全數消滅才可解鎖新考卷。")
            if st.button("🔥 立即啟動【錯題消滅淘汰賽】重測", type="primary", use_container_width=True):
                start_mistakes_retest()
                st.rerun()
        else:
            st.success("🎯 恭喜！本回錯題已全數全對銷案！已解鎖新測驗資格。")
            if st.button("➡️ 抽取下一回全新 50 題全真模考", type="primary", use_container_width=True):
                st.session_state.exam_round += 1
                start_new_exam()
                st.rerun()

    with act_col2:
        if st.button("🔄 重新挑戰當前回數題目", use_container_width=True):
            st.session_state.current_index = 0
            st.session_state.user_answers = {}
            st.session_state.submitted = False
            st.session_state.start_time = time.time()
            st.session_state.time_up = False
            st.rerun()

    st.divider()

    # 深度解析與精準推導指引
    st.subheader("📋 試題檢討與精確推理指引（免翻書速查）")
    for idx, q in enumerate(active_quiz):
        u_ans = st.session_state.user_answers.get(q['id'], "未作答")
        is_ok = u_ans == q['answer']
        icon = "✅" if is_ok else "❌"
        
        with st.expander(f"{icon} 第 {idx + 1} 題：{q['question']} （您的答案：{u_ans} ｜ 標準答案：{q['answer']}）"):
            st.write(f"**類別分類**：{q['category']} - {q['sub_category']}")
            st.write("**所有選項**：")
            for opt in q['options']:
                st.write(f"- {opt}")
            st.write(f"**正確選項**：({q['answer']})")
            st.info(f"💡 **解題推導與法規依據**：\n\n{q['explanation']}")
