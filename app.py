import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, date
import extra_streamlit_components as stx
from streamlit_calendar import calendar # 📅 ต้องเพิ่มบรรทัดนี้

# ================= CONFIGURATION =================
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    IMGBB_API_KEY = st.secrets.get("IMGBB_API_KEY", "0e31066455b60d727553d11e22761846") 
except FileNotFoundError:
    NOTION_TOKEN = "Please_Check_Secrets_File"
    IMGBB_API_KEY = "Please_Check_Secrets_File"

MEMBER_DB_ID = "271e6d24b97d80289175eef889a90a09" 
PROJECT_DB_ID = "26fe6d24b97d80e1bdb3c2452a31694c"

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ================= HELPER FUNCTIONS =================
@st.cache_data(show_spinner=False)
def get_page_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for prop_val in data["properties"].values():
                if prop_val["type"] == "title":
                    if prop_val["title"]: return prop_val["title"][0]["text"]["content"]
                    else: return "No Title"
        return "Unknown Page"
    except: return "Error Loading"

# 🔥 ฟังก์ชันดึงข้อมูลปฏิทิน (ฉบับแก้ไข: ย้าย URL ไปซ่อน เพื่อใช้กับ Dialog)
@st.cache_data(ttl=300)
def get_calendar_events():
    events = []
    target_start = date(2026, 1, 1)
    target_end = date(2026, 3, 31)
    
    url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    has_more = True
    next_cursor = None
    
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(url, json=payload, headers=headers)
            data = res.json()
            
            for page in data.get("results", []):
                props = page.get('properties', {})
                
                # 1. ชื่อ + ประเภท
                title = "Unknown Event"
                try: title = props.get("ชื่อกิจกรรม", {}).get("title", [])[0]["text"]["content"]
                except: pass
                
                event_type = "ทั่วไป"
                if 'ประเภทงาน' in props:
                    pt = props['ประเภทงาน']
                    if pt['type'] == 'select' and pt['select']: event_type = pt['select']['name']
                    elif pt['type'] == 'multi_select' and pt['multi_select']: event_type = pt['multi_select'][0]['name']
                
                # 2. วันที่
                event_date_str = None
                date_prop = props.get("วันที่จัดกิจกรรม") or props.get("วันที่จัดงาน")
                if date_prop: event_date_str = date_prop.get("date", {}).get("start")
                
                # 3. URL
                event_url = ""
                try: 
                    url_prop = props.get("URL")
                    if url_prop: event_url = url_prop.get("url", "")
                except: pass

                if event_date_str:
                    try:
                        e_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                        if target_start <= e_date <= target_end:
                            bg_color = "#FF4B4B"
                            if "งานย่อย" in str(event_type): bg_color = "#708090"
                            elif "งานใหญ่" in str(event_type): bg_color = "#FFD700"
                            
                            events.append({
                                "title": f"[{event_type}] {title}",
                                "start": event_date_str,
                                "backgroundColor": bg_color,
                                "borderColor": bg_color,
                                "allDay": True,
                                # ⚠️ ย้าย URL มาเก็บใน extendedProps (สำคัญมาก!)
                                "extendedProps": {
                                    "url": event_url if event_url else "#"
                                }
                            })
                    except: pass
            
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        except: break
    return events

@st.cache_data(ttl=300) 
def get_ranking_dataframe():
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    members = []
    has_more = True; next_cursor = None
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(url, json=payload, headers=headers).json()
            for page in res.get("results", []):
                props = page["properties"]
                score = 0
                sp = props.get("คะแนน Rank SS2") 
                if sp:
                    if sp['type'] == 'number': score = sp['number'] or 0
                    elif sp['type'] == 'rollup': score = sp['rollup'].get('number', 0) or 0
                    elif sp['type'] == 'formula': score = sp['formula'].get('number', 0) or 0
                name = ""
                try: name = props.get("ชื่อ", {}).get("title", [])[0]["text"]["content"]
                except: pass
                photo_url = None
                try: photo_url = props.get("Photo", {}).get("files", [])[0]["external"]["url"]
                except: pass
                group = "-"
                try: group = props.get("Rank Season 2 Group", {}).get("formula", {}).get("string") or "-"
                except: pass
                title = "-"
                try: title = props.get("Rank Season 2", {}).get("formula", {}).get("string") or "-"
                except: pass
                members.append({ "id": page["id"], "score": score, "name": name, "photo": photo_url, "group": group, "title": title })
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    if not members: return pd.DataFrame()
    df = pd.DataFrame(members)
    df = df.sort_values(by=["score", "name"], ascending=[False, True]).reset_index(drop=True)
    df.insert(0, 'อันดับ', df.index + 1)
    return df

@st.cache_data(ttl=300)
def get_participation_stats(user_id):
    all_main_project_ids = set()
    target_start = date(2026, 1, 1)
    target_end = date(2026, 3, 31)
    p_url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    has_more = True; next_cursor = None
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(p_url, json=payload, headers=headers).json()
            for page in res.get("results", []):
                props = page.get('properties', {})
                event_type = "ทั่วไป"
                if 'ประเภทงาน' in props:
                    pt = props['ประเภทงาน']
                    if pt['type'] == 'select' and pt['select']: event_type = pt['select']['name']
                    elif pt['type'] == 'multi_select' and pt['multi_select']: event_type = pt['multi_select'][0]['name']
                event_date_str = None
                date_prop = props.get("วันที่จัดกิจกรรม") or props.get("วันที่จัดงาน")
                if date_prop: event_date_str = date_prop.get("date", {}).get("start")
                is_date_in_range = False
                if event_date_str:
                    try:
                        e_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                        if target_start <= e_date <= target_end: is_date_in_range = True
                    except: pass
                if "งานย่อย" not in str(event_type) and is_date_in_range:
                    all_main_project_ids.add(page['id'])
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    total_main = len(all_main_project_ids)
    if total_main == 0: return 0, 0, 0.0
    h_url = f"https://api.notion.com/v1/databases/2b1e6d24b97d803786c2ec7011c995ef/query"
    payload_h = { "filter": { "property": "สมาชิกแรงค์", "relation": { "contains": user_id } } }
    attended = set()
    try:
        h_has_more = True; h_cursor = None
        while h_has_more:
            if h_cursor: payload_h["start_cursor"] = h_cursor
            h_res = requests.post(h_url, json=payload_h, headers=headers).json()
            for hp in h_res.get("results", []):
                pr = hp["properties"].get("ชื่องานแข่ง", {}).get("relation", [])
                if pr and pr[0]['id'] in all_main_project_ids: attended.add(pr[0]['id'])
            h_has_more = h_res.get("has_more", False)
            h_cursor = h_res.get("next_cursor")
    except: pass
    return len(attended), total_main, len(attended)/total_main if total_main else 0

def upload_image_to_imgbb(image_file):
    url = "https://api.imgbb.com/1/upload"
    payload = { "key": IMGBB_API_KEY }
    file_data = image_file.getvalue()
    try:
        response = requests.post(url, data=payload, files={'image': file_data}, timeout=20, verify=False)
        if response.status_code == 200 and response.json()['success']: return response.json()['data']['url']
    except: pass
    return None

def check_login(username, password):
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    payload = { "filter": { "and": [ { "property": "username", "formula": {"string": {"equals": username}} }, { "property": "Password", "rich_text": {"equals": password} } ] } }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200 and response.json().get('results'): return response.json()['results'][0]
    except: pass
    return None

def get_user_by_id(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def update_member_info(page_id, new_display_name, new_photo_url, new_password, new_birthday):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {}
    if new_display_name: properties["ชื่อ"] = {"title": [{"text": {"content": new_display_name}}]}
    if new_password: properties["Password"] = {"rich_text": [{"text": {"content": new_password}}]}
    if new_photo_url: properties["Photo"] = { "files": [{ "name": "pic", "type": "external", "external": {"url": new_photo_url} }] }
    if new_birthday: properties["วันเกิด"] = { "date": {"start": new_birthday.strftime("%Y-%m-%d")} }
    if not properties: return True
    return requests.patch(url, json={"properties": properties}, headers=headers).status_code == 200

# ================= UI PART =================
st.set_page_config(page_title="ระบบสมาชิก LSX Ranking", page_icon="🏆", layout="wide")
st.title("🧙‍♀️ ระบบสมาชิก LSX Ranking")
cookie_manager = stx.CookieManager()

if 'user_page' not in st.session_state: st.session_state['user_page'] = None
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'profile' # จัดการหน้าจอด้วยตัวแปรเดียว

# Auto Login
if st.session_state['user_page'] is None:
    time.sleep(0.5)
    cookie_user_id = cookie_manager.get(cookie="lsx_user_id")
    if cookie_user_id:
        with st.spinner("กำลังเข้าสู่ระบบอัตโนมัติ..."):
            user_data = get_user_by_id(cookie_user_id)
            if user_data:
                st.session_state['user_page'] = user_data
                st.success("🎉 ยินดีต้อนรับกลับมา!")
                time.sleep(1)
                st.rerun()
            else: cookie_manager.delete("lsx_user_id")

# --- LOGIN PAGE ---
if st.session_state['user_page'] is None:
    with st.form("login_form"):
        st.info("💡 Username คือ id ตามด้วย @lsxrank")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("จำฉันไว้ในระบบ (Remember me)")
        if st.form_submit_button("Login"):
            user_data = check_login(username, password)
            if user_data:
                st.session_state['user_page'] = user_data
                if remember_me: cookie_manager.set("lsx_user_id", user_data['id'], expires_at=datetime.now().replace(year=datetime.now().year + 1))
                st.rerun()
            else: st.error("Login failed")

# --- MAIN APP (LOGGED IN) ---
else:
    # 🏆 MODE 1: LEADERBOARD
    if st.session_state['view_mode'] == 'leaderboard':
        st.subheader("🏆 Leaderboard: อันดับรวมทั้งหมด")
        if st.button("⬅️ กลับหน้าข้อมูลส่วนตัว", key="back_lb"):
            st.session_state['view_mode'] = 'profile'
            st.rerun()
        
        with st.spinner("กำลังโหลดข้อมูลอันดับ..."):
            df_leaderboard = get_ranking_dataframe()
            if not df_leaderboard.empty:
                st.dataframe(
                    df_leaderboard[['อันดับ', 'photo', 'name', 'score', 'group', 'title']],
                    column_config={
                        "photo": st.column_config.ImageColumn("รูปโปรไฟล์"),
                        "อันดับ": st.column_config.NumberColumn("อันดับ", format="%d"),
                        "name": st.column_config.TextColumn("ชื่อสมาชิก"),
                        "score": st.column_config.NumberColumn("คะแนนรวม", format="%d ⭐"),
                        "group": st.column_config.TextColumn("Rank Group"),
                        "title": st.column_config.TextColumn("Rank Title"),
                    },
                    hide_index=True, use_container_width=True, height=600
                )
            else: st.warning("ไม่พบข้อมูลสมาชิก")
            
    # 📅 MODE 2: CALENDAR
    elif st.session_state['view_mode'] == 'calendar':
        
        # 1. สร้างตัวแปรกันลืม
        if 'last_clicked_event' not in st.session_state:
            st.session_state['last_clicked_event'] = None

        # 2. สร้างฟังก์ชัน Popup (เอาปุ่มปิดออกแล้ว)
        @st.dialog("รายละเอียดกิจกรรม")
        def show_event_popup(title, url):
            st.write(f"คุณต้องการเปิดหน้าเว็บของงาน **{title}** หรือไม่?")
            st.write("") 
            
            # เหลือแค่ปุ่มเดียว เต็มความกว้าง
            st.link_button("🚀 ไปที่หน้าเว็บ", url, type="primary", use_container_width=True)

        st.subheader("📅 ปฏิทินกิจกรรม (ม.ค. - มี.ค. 2026)")
        
        if st.button("⬅️ กลับหน้าข้อมูลส่วนตัว", key="back_cal"):
            st.session_state['view_mode'] = 'profile'
            st.session_state['last_clicked_event'] = None
            st.rerun()
            
        with st.spinner("กำลังโหลดปฏิทิน..."):
            events = get_calendar_events()
            
            calendar_options = {
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridMonth,listMonth"
                },
                "initialDate": "2026-01-01",
                "initialView": "dayGridMonth",
            }
            
            # รับค่าจากปฏิทิน
            cal_data = calendar(events=events, options=calendar_options, callbacks=['eventClick'])
            
            # 🔥 Logic เช็คการคลิก
            if cal_data.get("callback") == "eventClick":
                current_click_data = cal_data["eventClick"]["event"]
                
                # เช็คว่าเป็นคลิกใหม่หรือไม่
                if current_click_data != st.session_state['last_clicked_event']:
                    st.session_state['last_clicked_event'] = current_click_data
                    
                    clicked_title = current_click_data["title"]
                    clicked_url = current_click_data.get("extendedProps", {}).get("url")
                    
                    if clicked_url and clicked_url != "#":
                        show_event_popup(clicked_title, clicked_url)
                    else:
                        st.toast(f"ℹ️ กิจกรรม {clicked_title} ไม่มีลิงก์ URL")

    # 👤 MODE 3: PROFILE (หน้าหลัก)
    else:
        user_page = st.session_state['user_page']
        page_id = user_page['id']
        props = user_page['properties']
        
        # Calculate Rank
        with st.spinner(".."): df_all_ranks = get_ranking_dataframe()
        try:
            my_row = df_all_ranks[df_all_ranks['id'] == page_id].iloc[0]
            my_rank = my_row['อันดับ']; total_members = len(df_all_ranks)
        except: my_rank, total_members = "-", 0

        # Props
        try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
        except: current_display = ""
        try: current_photo_url = props["Photo"]["files"][0]["external"]["url"]
        except: current_photo_url = "https://via.placeholder.com/150"
        try: current_birth = datetime.strptime(props["วันเกิด"]["date"]["start"], "%Y-%m-%d").date()
        except: current_birth = None
        try: rank_group = props.get("Rank Season 2 Group", {}).get("formula", {}).get("string") or "-"
        except: rank_group = "-"
        try: rank_ss2 = props.get("Rank Season 2", {}).get("formula", {}).get("string") or "-"
        except: rank_ss2 = "-"
        try: score_ss2 = props.get("คะแนน Rank SS2", {}).get("rollup", {}).get("number", 0)
        except: score_ss2 = 0
        rank_history_ids = [r['id'] for r in props.get("สถิติการลง Rank ทั้งหมด", {}).get("relation", [])]
        reward_history_ids = [r['id'] for r in props.get("อันดับ 1-4 SS1", {}).get("relation", [])]

        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(current_photo_url, caption="รูปปัจจุบัน", width=150)
            st.divider()
            st.markdown(f"**🏆 Rank Group:** {rank_group}")
            st.markdown(f"**🎖️ Rank SS2:** {rank_ss2}")
            st.metric(label="⭐ คะแนน SS2", value=score_ss2)
            
            st.markdown("---")
            # ปุ่มดูอันดับ
            if st.button(f"🏆 อันดับที่ {my_rank} / {total_members}", use_container_width=True):
                st.session_state['view_mode'] = 'leaderboard'
                st.rerun()

            # 🔥 ปุ่มดูปฏิทิน (เพิ่มตรงนี้)
            if st.button("📅 ปฏิทินกิจกรรม", use_container_width=True):
                st.session_state['view_mode'] = 'calendar'
                st.rerun()

            with st.spinner(".."):
                attended, total_events, progress_val = get_participation_stats(page_id)
            st.markdown("**🔥 สถิติเข้าร่วมงานหลัก**")
            st.progress(progress_val)
            st.caption(f"เข้าร่วมแล้ว: {attended} / {total_events} งาน")

        with col2:
            st.subheader("📝 แก้ไขข้อมูลส่วนตัว")
            new_display = st.text_input("Display Name", value=current_display)
            new_birth_input = st.date_input("วันเกิด", value=current_birth if current_birth else date.today(), min_value=date(1900,1,1), max_value=date.today())
            st.markdown("---")
            uploaded_file = st.file_uploader("เลือกรูปโปรไฟล์ใหม่", type=['jpg', 'png'])
            if uploaded_file: st.image(uploaded_file, width=120)
            st.markdown("---")
            new_pass = st.text_input("รหัสผ่านใหม่", type="password")
            confirm_pass = st.text_input("ยืนยันรหัสผ่าน", type="password")
            if st.button("💾 บันทึกข้อมูล", type="primary"):
                error_flag = False
                final_photo_url = None
                if new_pass and new_pass != confirm_pass:
                    st.error("รหัสผ่านไม่ตรงกัน")
                    error_flag = True
                if uploaded_file and not error_flag:
                    with st.spinner("Uploading..."):
                        l = upload_image_to_imgbb(uploaded_file)
                        if l: final_photo_url = l
                        else: error_flag = True
                if not error_flag:
                    if update_member_info(page_id, new_display if new_display != current_display else None, final_photo_url, new_pass if new_pass else None, new_birth_input if new_birth_input != current_birth else None):
                        st.toast("✅ สำเร็จ!")
                        time.sleep(1)
                        get_ranking_dataframe.clear()
                        st.rerun()
                    else: st.error("บันทึกไม่สำเร็จ")

        st.markdown("---")
        st.header("📜 ประวัติ")
        h1, h2 = st.columns(2)
        with h1:
            st.subheader("⚔️ Rank History")
            if rank_history_ids:
                with st.container(height=300):
                    for rid in rank_history_ids: st.write(f"• {get_page_title(rid)}")
            else: st.info("-")
        with h2:
            st.subheader("🏆 SS1 Awards")
            if reward_history_ids:
                with st.container(height=300):
                    for rid in reward_history_ids: st.success(f"🏅 {get_page_title(rid)}")
            else: st.info("-")

        st.markdown("---")
        if st.button("Logout"):
            cookie_manager.delete("lsx_user_id") 
            st.session_state['user_page'] = None
            st.toast("👋 กำลังออกจากระบบ...")
            time.sleep(2)
            st.rerun()
