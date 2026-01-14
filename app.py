import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, date
import extra_streamlit_components as stx

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

@st.cache_data(ttl=300) 
def get_ranking_data(current_user_id):
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    members = []
    has_more = True
    next_cursor = None
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200: break
            data = response.json()
            for page in data.get("results", []):
                props = page["properties"]
                score = 0
                score_prop = props.get("คะแนน Rank SS2") 
                if score_prop:
                    if score_prop['type'] == 'number': score = score_prop['number'] or 0
                    elif score_prop['type'] == 'rollup': score = score_prop['rollup'].get('number', 0) or 0
                    elif score_prop['type'] == 'formula': score = score_prop['formula'].get('number', 0) or 0
                name = ""
                try: name = props.get("ชื่อ", {}).get("title", [])[0]["text"]["content"]
                except: pass
                members.append({ "id": page["id"], "score": score, "name": name })
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        except: break
    
    if not members: return "-", "-"
    df = pd.DataFrame(members)
    df = df.sort_values(by=["score", "name"], ascending=[False, True]).reset_index(drop=True)
    try:
        rank = df[df['id'] == current_user_id].index[0] + 1
        return rank, len(df)
    except: return "-", len(df)

@st.cache_data(ttl=300)
def get_participation_stats(user_id):
    all_main_project_ids = set()
    target_start = date(2026, 1, 1)
    target_end = date(2026, 3, 31)
    
    p_url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    has_more = True
    next_cursor = None
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(p_url, json=payload, headers=headers)
            data = res.json()
            for page in data.get("results", []):
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
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        except: break

    total_main = len(all_main_project_ids)
    if total_main == 0: return 0, 0, 0.0

    h_url = f"https://api.notion.com/v1/databases/2b1e6d24b97d803786c2ec7011c995ef/query"
    payload_h = { "filter": { "property": "สมาชิกแรงค์", "relation": { "contains": user_id } } }
    attended = set()
    try:
        h_has_more = True
        h_cursor = None
        while h_has_more:
            if h_cursor: payload_h["start_cursor"] = h_cursor
            h_res = requests.post(h_url, json=payload_h, headers=headers)
            h_data = h_res.json()
            for hp in h_data.get("results", []):
                pr = hp["properties"].get("ชื่องานแข่ง", {}).get("relation", [])
                if pr and pr[0]['id'] in all_main_project_ids: attended.add(pr[0]['id'])
            h_has_more = h_data.get("has_more", False)
            h_cursor = h_data.get("next_cursor")
    except: pass
    
    return len(attended), total_main, len(attended)/total_main

def upload_image_to_imgbb(image_file):
    url = "https://api.imgbb.com/1/upload"
    payload = { "key": IMGBB_API_KEY }
    file_data = image_file.getvalue()
    try:
        response = requests.post(url, data=payload, files={'image': file_data}, timeout=20, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data['success']: return data['data']['url']
    except: pass
    return None

def check_login(username, password):
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                { "property": "username", "formula": {"string": {"equals": username}} },
                { "property": "Password", "rich_text": {"equals": password} }
            ]
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        if response.status_code == 200 and data.get('results'):
            return data['results'][0]
    except: pass
    return None

def get_user_by_id(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json() 
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
    payload = {"properties": properties}
    response = requests.patch(url, json=payload, headers=headers)
    return response.status_code == 200

# ================= UI PART =================
st.set_page_config(page_title="ระบบสมาชิก LSX Ranking", page_icon="🏆")
st.title("🧙‍♀️ ระบบสมาชิก LSX Ranking")


# 🔥 แก้ไข: ประกาศ Cookie Manager ตรงนี้เลย (ไม่ต้องมี decorator หรือ function ห่อ)
cookie_manager = stx.CookieManager()

# 2. เช็คสถานะ Session
if 'user_page' not in st.session_state:
    st.session_state['user_page'] = None

# 🔥 3. Auto Login Logic
if st.session_state['user_page'] is None:
    time.sleep(0.5) # รอ Cookie โหลดนิดนึง
    cookie_user_id = cookie_manager.get(cookie="lsx_user_id")
    
    if cookie_user_id:
        with st.spinner("กำลังเข้าสู่ระบบอัตโนมัติ..."):
            user_data = get_user_by_id(cookie_user_id)
            if user_data:
                st.session_state['user_page'] = user_data
                st.success("🎉 ยินดีต้อนรับกลับมา!")
                time.sleep(1)
                st.rerun() 
            else:
                cookie_manager.delete("lsx_user_id")

# --- LOGIN PAGE ---
if st.session_state['user_page'] is None:
    with st.form("login_form"):
        st.info("💡 Username คือ id ตามด้วย @lsxrank")
        st.info("💡 ตรวจสอบ id ได้ที่ >> https://bbxlopburisaraburi.notion.site/2d2e6d24b97d8156a52bd2794a36d90e?v=2d2e6d24b97d81c3bace000c671d914a&source=copy_link")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        remember_me = st.checkbox("จำฉันไว้ในระบบ (Remember me)")
        
        if st.form_submit_button("Login"):
            user_data = check_login(username, password)
            if user_data:
                st.session_state['user_page'] = user_data
                if remember_me:
                    cookie_manager.set("lsx_user_id", user_data['id'], expires_at=datetime.now().replace(year=datetime.now().year + 1))
                st.rerun()
            else:
                st.error("Login failed: ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# --- EDIT PAGE (LOGGED IN) ---
else:
    user_page = st.session_state['user_page']
    page_id = user_page['id']
    props = user_page['properties']
    
    # 1. Get Data
    try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
    except: current_display = ""
    try: current_photo_url = props["Photo"]["files"][0]["external"]["url"]
    except: current_photo_url = "https://via.placeholder.com/150"
    try:
        birth_str = props["วันเกิด"]["date"]["start"]
        current_birth = datetime.strptime(birth_str, "%Y-%m-%d").date()
    except: current_birth = None

    try: rank_group = props.get("Rank Season 2 Group", {}).get("formula", {}).get("string") or "-"
    except: rank_group = "-"
    try: rank_ss2 = props.get("Rank Season 2", {}).get("formula", {}).get("string") or "-"
    except: rank_ss2 = "-"
    try: score_ss2 = props.get("คะแนน Rank SS2", {}).get("rollup", {}).get("number", 0)
    except: score_ss2 = 0

    rank_history_ids = [r['id'] for r in props.get("สถิติการลง Rank ทั้งหมด", {}).get("relation", [])]
    reward_history_ids = [r['id'] for r in props.get("อันดับ 1-4 SS1", {}).get("relation", [])]

    # --- UI ---
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image(current_photo_url, caption="รูปปัจจุบัน", width=150)
        st.divider()
        st.markdown(f"**🏆 Rank Group:** {rank_group}")
        st.markdown(f"**🎖️ Rank SS2:** {rank_ss2}")
        st.metric(label="⭐ คะแนน SS2", value=score_ss2)
        
        with st.spinner(".."):
            my_rank, total_members = get_ranking_data(page_id)
        st.markdown(f"""<div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; text-align: center; margin-top: 5px; margin-bottom: 10px;">
                <span style="font-size: 14px; color: #555;">อันดับปัจจุบัน</span><br>
                <span style="font-size: 24px; font-weight: bold; color: #ff4b4b;">{my_rank}</span> 
                <span style="font-size: 16px; color: #555;">/ {total_members}</span></div>""", unsafe_allow_html=True)

        with st.spinner(".."):
            attended, total_events, progress_val = get_participation_stats(page_id)
        st.markdown("**🔥 สถิติเข้าร่วมงานหลัก**")
        st.progress(progress_val)
        st.caption(f"เข้าร่วมแล้ว: {attended} / {total_events} งาน")

    with col2:
        st.subheader("📝 แก้ไขข้อมูล")
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
                    get_ranking_data.clear()
                    get_participation_stats.clear()
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
    
    # 🔥 แก้ไขปุ่ม Logout: เพิ่มเวลาหน่วง (time.sleep)
    if st.button("Logout"):
        # 1. สั่งลบ Cookie
        cookie_manager.delete("lsx_user_id")
        
        # 2. เคลียร์ข้อมูลใน Session
        st.session_state['user_page'] = None
        
        # 3. แจ้งเตือน
        st.toast("👋 กำลังออกจากระบบ...")
        
        # 4. ⚠️ สำคัญมาก: รอ 2 วินาที ให้ Browser ลบ Cookie เสร็จก่อน
        time.sleep(2)
        
        # 5. โหลดหน้าใหม่
        st.rerun()
