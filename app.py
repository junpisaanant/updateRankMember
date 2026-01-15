import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, date
import extra_streamlit_components as stx
from streamlit_calendar import calendar

# ================= CONFIGURATION =================
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    IMGBB_API_KEY = st.secrets.get("IMGBB_API_KEY", "0e31066455b60d727553d11e22761846") 
except FileNotFoundError:
    NOTION_TOKEN = "Please_Check_Secrets_File"
    IMGBB_API_KEY = "Please_Check_Secrets_File"

MEMBER_DB_ID = "271e6d24b97d80289175eef889a90a09" 
PROJECT_DB_ID = "26fe6d24b97d80e1bdb3c2452a31694c"

# วันปิดรับสมัคร
REGISTRATION_DEADLINE = datetime(2026, 1, 18, 23, 59, 59)

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

@st.cache_data(ttl=3600)
def get_province_options():
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            props = res.json().get("properties", {})
            if "มาจากจังหวัด" in props:
                options = props["มาจากจังหวัด"].get("multi_select", {}).get("options", [])
                return [opt["name"] for opt in options]
    except: pass
    return []

@st.cache_data(ttl=300)
def get_photo_gallery():
    gallery_items = []
    url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    has_more = True; next_cursor = None
    while has_more:
        payload = { "page_size": 100 }
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(url, json=payload, headers=headers).json()
            for page in res.get("results", []):
                props = page.get('properties', {})
                photo_url = ""
                try: 
                    p_url_prop = props.get("Photo URL") 
                    if p_url_prop: photo_url = p_url_prop.get("url", "")
                except: pass
                
                if photo_url:
                    if not photo_url.startswith(("http://", "https://")): photo_url = f"https://{photo_url}"
                    title = "Unknown Event"
                    try: title = props.get("ชื่อกิจกรรม", {}).get("title", [])[0]["text"]["content"]
                    except: pass
                    
                    event_date = None
                    date_prop = props.get("วันที่จัดกิจกรรม") or props.get("วันที่จัดงาน")
                    if date_prop: 
                        d_obj = date_prop.get("date")
                        if d_obj:
                            d_str = d_obj.get("start")
                            if d_str:
                                try: event_date = datetime.strptime(d_str, "%Y-%m-%d").date()
                                except: pass
                                
                    gallery_items.append({
                        "title": title, "date": event_date, 
                        "date_str": event_date.strftime("%d %b %Y") if event_date else "ไม่ระบุวันที่",
                        "photo_url": photo_url
                    })
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    gallery_items.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    return gallery_items

@st.cache_data(ttl=300)
def get_calendar_events():
    events = []
    target_start = date(2026, 1, 1)
    target_end = date(2026, 3, 31)
    url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    has_more = True; next_cursor = None
    while has_more:
        payload = { "page_size": 100 }
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(url, json=payload, headers=headers).json()
            for page in res.get("results", []):
                props = page.get('properties', {})
                title = "Unknown Event"
                try: title = props.get("ชื่อกิจกรรม", {}).get("title", [])[0]["text"]["content"]
                except: pass
                event_type = "ทั่วไป"
                if 'ประเภทงาน' in props:
                    pt = props['ประเภทงาน']
                    if pt['type'] == 'select' and pt['select']: event_type = pt['select']['name']
                    elif pt['type'] == 'multi_select' and pt['multi_select']: event_type = pt['multi_select'][0]['name']
                
                event_date_str = None
                date_prop = props.get("วันที่จัดกิจกรรม") or props.get("วันที่จัดงาน")
                if date_prop: 
                    d_obj = date_prop.get("date")
                    if d_obj: event_date_str = d_obj.get("start")
                
                event_url = ""
                try: 
                    url_prop = props.get("URL")
                    if url_prop: event_url = url_prop.get("url", "")
                except: pass
                if event_url and not event_url.startswith(("http://", "https://")): event_url = f"https://{event_url}"
                
                if event_date_str:
                    try:
                        e_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                        if target_start <= e_date <= target_end:
                            bg_color = "#FF4B4B"
                            if "งานย่อย" in str(event_type): bg_color = "#708090"
                            elif "งานใหญ่" in str(event_type): bg_color = "#FFD700"
                            events.append({
                                "title": f"[{event_type}] {title}", "start": event_date_str,
                                "backgroundColor": bg_color, "borderColor": bg_color, "allDay": True,
                                "extendedProps": { "url": event_url if event_url else "#" }
                            })
                    except: pass
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    return events

@st.cache_data(ttl=300) 
def get_ranking_dataframe():
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    members = []
    has_more = True; next_cursor = None
    while has_more:
        payload = { "page_size": 100 }
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
                
                rank_val = 9999
                try:
                    r_list = props.get("อันดับ Rank SS2", {}).get("rich_text", [])
                    if r_list:
                        r_text = r_list[0]["text"]["content"]
                        if "/" in r_text: rank_val = int(r_text.split('/')[0])
                        else: rank_val = int(r_text)
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
                
                members.append({ 
                    "id": page["id"], "score": score, "name": name, 
                    "photo": photo_url, "group": group, "title": title,
                    "rank_num": rank_val 
                })
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    
    if not members: return pd.DataFrame()
    df = pd.DataFrame(members)
    df = df.sort_values(by=["rank_num", "score"], ascending=[True, False]).reset_index(drop=True)
    df['อันดับ'] = df['rank_num'] 
    return df

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

def check_duplicate_name(display_name):
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    payload = { "filter": { "property": "ชื่อ", "title": { "equals": display_name } } }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            results = response.json().get('results', [])
            return len(results) > 0
    except: pass
    return False

def create_new_member(display_name, email, password, birth_date, photo_url, province):
    url = "https://api.notion.com/v1/pages"
    
    properties = {
        "ชื่อ": { "title": [{"text": {"content": display_name}}] },
        "Email": { "rich_text": [{"text": {"content": email}}] }, 
        "Password": { "rich_text": [{"text": {"content": password}}] }, 
        "วันเกิด": { "date": { "start": birth_date.strftime("%Y-%m-%d") } }
    }
    
    if photo_url:
        properties["Photo"] = { "files": [{ "name": "profile.jpg", "type": "external", "external": {"url": photo_url} }] }
    
    if province:
        properties["มาจากจังหวัด"] = { "multi_select": [{ "name": province }] }
    
    payload = {
        "parent": { "database_id": MEMBER_DB_ID },
        "properties": properties
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"❌ Notion Error ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"❌ System Error: {e}")
        return None

def get_username_from_created_page(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            user_formula = data["properties"].get("username", {}).get("formula", {})
            return user_formula.get("string")
    except: pass
    return None

def get_user_by_id(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def update_member_info(page_id, new_display_name, new_photo_url, new_password, new_birthday, new_province):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {}
    if new_display_name: properties["ชื่อ"] = {"title": [{"text": {"content": new_display_name}}]}
    if new_password: properties["Password"] = {"rich_text": [{"text": {"content": new_password}}]}
    if new_photo_url: properties["Photo"] = { "files": [{ "name": "pic", "type": "external", "external": {"url": new_photo_url} }] }
    if new_birthday: properties["วันเกิด"] = { "date": {"start": new_birthday.strftime("%Y-%m-%d")} }
    if new_province: properties["มาจากจังหวัด"] = { "multi_select": [{ "name": new_province }] }

    if not properties: return True
    return requests.patch(url, json={"properties": properties}, headers=headers).status_code == 200

# ================= UI PART =================
st.set_page_config(page_title="ระบบสมาชิก LSX Ranking", page_icon="🏆", layout="wide")
st.title("🧙‍♀️ ระบบสมาชิก LSX Ranking")
cookie_manager = stx.CookieManager()

if 'user_page' not in st.session_state: st.session_state['user_page'] = None
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = 'profile' 
if 'auth_mode' not in st.session_state: st.session_state['auth_mode'] = 'login' 

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

# ================= LOGIN / REGISTER FLOW =================
if st.session_state['user_page'] is None:
    
    # [PAGE] LOGIN
    if st.session_state['auth_mode'] == 'login':
        with st.form("login_form"):
            st.info("💡 Username คือ id ตามด้วย @lsxrank")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            remember_me = st.checkbox("จำฉันไว้ในระบบ (Remember me)")
            
            c1, c2 = st.columns(2)
            with c1:
                submitted = st.form_submit_button("Login", use_container_width=True)
            with c2: pass 
        
        if submitted:
            user_data = check_login(username, password)
            if user_data:
                st.session_state['user_page'] = user_data
                if remember_me: cookie_manager.set("lsx_user_id", user_data['id'], expires_at=datetime.now().replace(year=datetime.now().year + 1))
                st.rerun()
            else: st.error("Login failed: Username หรือ Password ไม่ถูกต้อง")
            
        st.markdown("---")
        st.write("ยังไม่มีบัญชีใช่ไหม?")
        
        if datetime.now() <= REGISTRATION_DEADLINE:
            if st.button("📝 สมัครสมาชิกใหม่"):
                st.session_state['auth_mode'] = 'register'
                st.rerun()
        else:
            st.warning(f"⚠️ ปิดรับสมัครสมาชิกแล้ว (สิ้นสุดเมื่อ {REGISTRATION_DEADLINE.strftime('%d %b %Y')})")

    # [PAGE] REGISTER
    else:
        st.subheader("📝 สมัครสมาชิกใหม่")
        if st.button("⬅️ กลับไปหน้า Login"):
            st.session_state['auth_mode'] = 'login'
            st.rerun()
            
        with st.form("register_form"):
            reg_display_name = st.text_input("Display Name (ชื่อที่ใช้แสดงผล)")
            reg_email = st.text_input("Email")
            
            province_options = get_province_options()
            reg_province = st.selectbox("มาจากจังหวัด", options=province_options, index=None, placeholder="เลือกจังหวัด...")
            
            reg_birthday = st.date_input("วันเกิด", value=None, min_value=date(1900,1,1), max_value=date.today())
            reg_photo = st.file_uploader("รูปโปรไฟล์ (แนะนำสี่เหลี่ยมจัตุรัส)", type=['jpg', 'png'])
            
            p1, p2 = st.columns(2)
            with p1: reg_pass = st.text_input("Password", type="password")
            with p2: reg_confirm_pass = st.text_input("ยืนยัน Password", type="password")
            
            reg_submit = st.form_submit_button("ยืนยันการสมัคร", type="primary")
            
            if reg_submit:
                if not reg_display_name or not reg_email or not reg_pass:
                    st.error("กรุณากรอกข้อมูลที่จำเป็นให้ครบถ้วน")
                elif not reg_province:
                    st.error("กรุณาเลือกจังหวัด")
                elif not reg_birthday:
                    st.error("กรุณาระบุวันเกิด")
                elif reg_pass != reg_confirm_pass:
                    st.error("รหัสผ่านไม่ตรงกัน")
                elif not reg_photo:
                    st.error("กรุณาอัปโหลดรูปโปรไฟล์")
                else:
                    with st.spinner("กำลังตรวจสอบชื่อ..."):
                        if check_duplicate_name(reg_display_name):
                            st.error(f"ชื่อ '{reg_display_name}' มีผู้ใช้งานแล้ว กรุณาใช้ชื่ออื่น")
                        else:
                            final_photo_url = None
                            with st.spinner("กำลังอัปโหลดรูปภาพ..."):
                                final_photo_url = upload_image_to_imgbb(reg_photo)
                            
                            if not final_photo_url:
                                st.error("อัปโหลดรูปภาพไม่สำเร็จ กรุณาลองใหม่")
                            else:
                                with st.spinner("กำลังสร้างบัญชี..."):
                                    new_user = create_new_member(reg_display_name, reg_email, reg_pass, reg_birthday, final_photo_url, reg_province)
                                
                                if new_user:
                                    real_username = None
                                    try: 
                                        real_username = new_user["properties"]["username"]["formula"]["string"]
                                    except: pass
                                    
                                    if not real_username:
                                        time.sleep(1) 
                                        real_username = get_username_from_created_page(new_user['id'])
                                    
                                    if not real_username:
                                        real_username = f"{new_user['id']}@lsxrank"

                                    st.success("🎉 สมัครสมาชิกสำเร็จ!")
                                    st.balloons()
                                    st.markdown("### 🔐 บัญชีของคุณ")
                                    st.success(f"Username: **{real_username}**")
                                    st.code(real_username, language="text") 
                                    st.warning("⚠️ กรุณาจดจำ Username และรหัสผ่านให้ดี (ใช้สำหรับ Login ครั้งต่อไป)")
                                else:
                                    st.error("เกิดข้อผิดพลาดในการบันทึกข้อมูล")

# ================= LOGGED IN =================
else:
    user_page = st.session_state['user_page']
    page_id = user_page['id']
    props = user_page['properties']
    
    # 🔥🔥🔥 FORCE CHANGE PASSWORD LOGIC 🔥🔥🔥
    # เช็คว่ารหัสผ่านปัจจุบันเป็น 'lsx' หรือไม่
    try: current_password_chk = props["Password"]["rich_text"][0]["text"]["content"]
    except: current_password_chk = ""
    
    if current_password_chk == "lsx":
        st.warning("⚠️ **ความปลอดภัย:** ระบบตรวจพบรหัสผ่านเริ่มต้น กรุณาเปลี่ยนรหัสผ่านใหม่ก่อนใช้งานต่อ")
        with st.container(border=True):
            st.subheader("🔐 เปลี่ยนรหัสผ่าน")
            force_new_pass = st.text_input("รหัสผ่านใหม่", type="password", key="fp1")
            force_confirm_pass = st.text_input("ยืนยันรหัสผ่านใหม่", type="password", key="fp2")
            
            if st.button("ยืนยันการเปลี่ยนรหัสผ่าน", type="primary", use_container_width=True):
                if not force_new_pass:
                    st.error("กรุณากรอกรหัสผ่าน")
                elif force_new_pass != force_confirm_pass:
                    st.error("รหัสผ่านไม่ตรงกัน")
                elif force_new_pass == "lsx":
                    st.error("กรุณาตั้งรหัสผ่านอื่นที่ไม่ใช่ lsx")
                else:
                    with st.spinner("กำลังบันทึก..."):
                        # อัปเดตเฉพาะรหัสผ่าน (ช่องอื่นส่ง None)
                        if update_member_info(page_id, None, None, force_new_pass, None, None):
                            st.toast("✅ เปลี่ยนรหัสผ่านสำเร็จ! กำลังรีโหลด...", icon="🔄")
                            # ดึงข้อมูลใหม่มาอัปเดตใน Session
                            new_user_data = get_user_by_id(page_id)
                            if new_user_data:
                                st.session_state['user_page'] = new_user_data
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("เกิดข้อผิดพลาด กรุณาลองใหม่")
        
        # 🛑 หยุดการทำงาน ไม่ให้โหลดหน้า Profile ด้านล่าง
        st.stop()

    # 🏆 MODE 1: LEADERBOARD
    if st.session_state['view_mode'] == 'leaderboard':
        st.subheader("🏆 Leaderboard: อันดับรวมทั้งหมด")
        if st.button("⬅️ กลับหน้าข้อมูลส่วนตัว", key="back_lb"):
            st.session_state['view_mode'] = 'profile'
            st.rerun()
        with st.spinner("กำลังโหลดข้อมูลอันดับ..."):
            df_leaderboard = get_ranking_dataframe()
            if not df_leaderboard.empty:
                st.dataframe(df_leaderboard[['อันดับ', 'photo', 'name', 'score', 'group', 'title']],
                    column_config={ 
                        "photo": st.column_config.ImageColumn("รูปโปรไฟล์"), 
                        "อันดับ": st.column_config.NumberColumn("อันดับ", format="%d"), 
                        "name": st.column_config.TextColumn("ชื่อสมาชิก"), 
                        "score": st.column_config.NumberColumn("คะแนนรวม", format="%d ⭐"), 
                        "group": st.column_config.TextColumn("Rank Group"), 
                        "title": st.column_config.TextColumn("Rank Title") 
                    },
                    hide_index=True, use_container_width=True, height=600)
            else: st.warning("ไม่พบข้อมูลสมาชิก")
            
    # 📅 MODE 2: CALENDAR
    elif st.session_state['view_mode'] == 'calendar':
        if 'last_clicked_event' not in st.session_state: st.session_state['last_clicked_event'] = None
        @st.dialog("รายละเอียดกิจกรรม")
        def show_event_popup(title, url):
            st.write(f"คุณต้องการเปิดหน้าเว็บของงาน **{title}** หรือไม่?")
            st.write("") 
            st.link_button("🚀 ไปที่หน้าเว็บ", url, type="primary", use_container_width=True)
        st.subheader("📅 ปฏิทินกิจกรรม (ม.ค. - มี.ค. 2026)")
        if st.button("⬅️ กลับหน้าข้อมูลส่วนตัว", key="back_cal"):
            st.session_state['view_mode'] = 'profile'
            st.session_state['last_clicked_event'] = None
            st.rerun()
        with st.spinner("กำลังโหลดปฏิทิน..."):
            events = get_calendar_events()
            calendar_options = { "headerToolbar": { "left": "today prev,next", "center": "title", "right": "dayGridMonth,listMonth" }, "initialDate": "2026-01-01", "initialView": "dayGridMonth" }
            cal_data = calendar(events=events, options=calendar_options, callbacks=['eventClick'])
            if cal_data.get("callback") == "eventClick":
                current_click_data = cal_data["eventClick"]["event"]
                if current_click_data != st.session_state['last_clicked_event']:
                    st.session_state['last_clicked_event'] = current_click_data
                    clicked_title = current_click_data["title"]
                    clicked_url = current_click_data.get("extendedProps", {}).get("url")
                    if clicked_url and clicked_url != "#": show_event_popup(clicked_title, clicked_url)
                    else: st.toast(f"ℹ️ กิจกรรม {clicked_title} ไม่มีลิงก์ URL")

    # 📸 MODE 3: PHOTO GALLERY
    elif st.session_state['view_mode'] == 'gallery':
        st.subheader("📸 แกลเลอรีรูปภาพกิจกรรม")
        if st.button("⬅️ กลับหน้าข้อมูลส่วนตัว", key="back_gal"):
            st.session_state['view_mode'] = 'profile'
            st.rerun()
        with st.spinner("กำลังโหลดรูปภาพ..."):
            gallery_items = get_photo_gallery()
            if not gallery_items: st.info("ยังไม่มีข้อมูลรูปภาพกิจกรรม")
            else:
                cols = st.columns(2)
                for i, item in enumerate(gallery_items):
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.write(f"**{item['title']}**")
                            st.caption(f"🗓️ {item['date_str']}")
                            st.link_button("🖼️ ดูอัลบั้มรูป", item['photo_url'], use_container_width=True)

    # 👤 MODE 4: PROFILE
    else:
        try:
            rank_list = props.get("อันดับ Rank SS2", {}).get("rich_text", [])
            full_rank_str = rank_list[0]["text"]["content"] if rank_list else "-"
        except: full_rank_str = "-"

        try:
            stats_list = props.get("สถิติเข้าร่วม SS2", {}).get("rich_text", [])
            stats_str = stats_list[0]["text"]["content"] if stats_list else "0/0"
        except: stats_str = "0/0"
        
        try:
            attended_str, total_str = stats_str.split("/")
            attended = int(attended_str)
            total_events = int(total_str)
            progress_val = attended / total_events if total_events > 0 else 0.0
        except:
            attended, total_events, progress_val = 0, 0, 0.0

        try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
        except: current_display = ""
        try: current_photo_url = props["Photo"]["files"][0]["external"]["url"]
        except: current_photo_url = "https://via.placeholder.com/150"
        try: current_birth = datetime.strptime(props["วันเกิด"]["date"]["start"], "%Y-%m-%d").date()
        except: current_birth = None
        try: current_province = props["มาจากจังหวัด"]["multi_select"][0]["name"]
        except: current_province = None

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
            st.markdown(f"📍 **จังหวัด:** {current_province if current_province else '-'}")
            st.markdown("---")
            if st.button(f"🏆 อันดับที่ {full_rank_str}", use_container_width=True):
                st.session_state['view_mode'] = 'leaderboard'; st.rerun()
            if st.button("📅 ปฏิทินกิจกรรม", use_container_width=True):
                st.session_state['view_mode'] = 'calendar'; st.rerun()
            if st.button("📸 แกลเลอรีรูปภาพ", use_container_width=True):
                st.session_state['view_mode'] = 'gallery'; st.rerun()
            st.markdown("**🔥 สถิติเข้าร่วมงานหลัก**")
            st.progress(progress_val)
            st.caption(f"เข้าร่วมแล้ว: {stats_str} งาน")
            
        with col2:
            st.subheader("📝 แก้ไขข้อมูลส่วนตัว")
            new_display = st.text_input("Display Name", value=current_display)
            new_birth_input = st.date_input("วันเกิด", value=current_birth if current_birth else date.today(), min_value=date(1900,1,1), max_value=date.today())
            
            province_options = get_province_options()
            current_prov_idx = province_options.index(current_province) if current_province in province_options else None
            new_province = st.selectbox("มาจากจังหวัด", options=province_options, index=current_prov_idx, placeholder="เลือกจังหวัด...")

            st.markdown("---")
            uploaded_file = st.file_uploader("เลือกรูปโปรไฟล์ใหม่", type=['jpg', 'png'])
            if uploaded_file: st.image(uploaded_file, width=120)
            st.markdown("---")
            new_pass = st.text_input("รหัสผ่านใหม่", type="password")
            confirm_pass = st.text_input("ยืนยันรหัสผ่าน", type="password")
            if st.button("💾 บันทึกข้อมูล", type="primary"):
                error_flag = False; final_photo_url = None
                if new_pass and new_pass != confirm_pass: st.error("รหัสผ่านไม่ตรงกัน"); error_flag = True
                if uploaded_file and not error_flag:
                    with st.spinner("Uploading..."):
                        l = upload_image_to_imgbb(uploaded_file)
                        if l: final_photo_url = l
                        else: error_flag = True
                if not error_flag:
                    if update_member_info(page_id, new_display if new_display != current_display else None, final_photo_url, new_pass if new_pass else None, new_birth_input if new_birth_input != current_birth else None, new_province if new_province != current_province else None):
                        st.toast("✅ สำเร็จ!"); time.sleep(1); get_ranking_dataframe.clear(); st.rerun()
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

st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(
    """
    <div style='text-align: center; color: #888; font-size: 14px; margin-bottom: 20px;'>
        Created by LovelyToonZ
    </div>
    """,
    unsafe_allow_html=True
)
