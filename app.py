import streamlit as st
import requests
import time
import uuid
import pandas as pd
from datetime import datetime, date, timedelta
import extra_streamlit_components as stx
from streamlit_calendar import calendar
import pytz 

# ================= CONFIGURATION =================
# ✅ ต้องเป็นคำสั่งแรกสุด ห้ามย้าย
st.set_page_config(page_title="LSX Ranking", page_icon="🏆", layout="wide")

# 🔥 จัดการ Timezone ให้เป็นไทยเสมอ
THAI_TZ = pytz.timezone('Asia/Bangkok')

def get_thai_date():
    return datetime.now(THAI_TZ).date()

try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    IMGBB_API_KEY = st.secrets.get("IMGBB_API_KEY", "0e31066455b60d727553d11e22761846") 
except FileNotFoundError:
    NOTION_TOKEN = "Please_Check_Secrets_File"
    IMGBB_API_KEY = "Please_Check_Secrets_File"

# 📌 ID
MEMBER_DB_ID = "271e6d24b97d80289175eef889a90a09" 
PROJECT_DB_ID = "26fe6d24b97d80e1bdb3c2452a31694c"
NEWS_DB_ID = "280e6d24b97d806fa7c8e8bd4ca717f8" 

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
def get_latest_news(limit=5, category_filter=None):
    url = f"https://api.notion.com/v1/databases/{NEWS_DB_ID}/query"
    payload = {
        "page_size": limit, 
        "sorts": [ { "property": "วันที่ประกาศ", "direction": "descending" } ]
    }
    news_list = []
    try:
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                
                category = "ข่าวสาร"
                try:
                    cat_prop = props.get("ประเภท")
                    if cat_prop['type'] == 'select' and cat_prop['select']:
                        category = cat_prop['select']['name']
                    elif cat_prop['type'] == 'multi_select' and cat_prop['multi_select']:
                        category = cat_prop['multi_select'][0]['name']
                except: pass

                if category_filter and category_filter != category:
                    continue

                topic = "ไม่มีหัวข้อ"
                try: topic = props.get("หัวข้อ", {}).get("title", [])[0]["text"]["content"]
                except: pass
                
                content = "-"
                try: 
                    content_list = props.get("เนื้อหา", {}).get("rich_text", [])
                    content = "".join([t["text"]["content"] for t in content_list])
                except: pass
                
                link = None
                try: link = props.get("URL", {}).get("url")
                except: pass
                
                show_date = "Unknown Date"
                try: 
                    d_str = props.get("วันที่ประกาศ", {}).get("date", {}).get("start")
                    if d_str:
                        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        show_date = d_obj.strftime("%d/%m/%Y")
                except: pass

                image_urls = []
                try:
                    img_files = props.get("ภาพประกอบ", {}).get("files", [])
                    for file in img_files:
                        url = ""
                        if file['type'] == 'external': url = file['external']['url']
                        elif file['type'] == 'file': url = file['file']['url']
                        if url: image_urls.append(url)
                except: pass
                
                news_list.append({ 
                    "id": page["id"],
                    "topic": topic, 
                    "content": content, 
                    "url": link, 
                    "date": show_date,
                    "category": category,
                    "image_urls": image_urls
                })
    except: pass
    return news_list

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
                            display_tag = event_type
                            if "งานย่อย" in str(event_type): 
                                bg_color = "#708090" 
                                display_tag = "Side Event"
                            elif "งานใหญ่" in str(event_type): 
                                bg_color = "#FFD700" 
                                display_tag = "Main Event"
                            
                            events.append({
                                "title": f"[{display_tag}] {title}", 
                                "start": event_date_str,
                                "backgroundColor": bg_color, 
                                "borderColor": bg_color, 
                                "allDay": True,
                                "extendedProps": { "url": event_url if event_url else "#" }
                            })
                    except: pass
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    return events

@st.cache_data(ttl=300)
def get_upcoming_event():
    url = f"https://api.notion.com/v1/databases/{PROJECT_DB_ID}/query"
    today_str = get_thai_date().strftime("%Y-%m-%d")
    payload = {
        "filter": { "property": "วันที่จัดกิจกรรม", "date": { "on_or_after": today_str } },
        "sorts": [ { "property": "วันที่จัดกิจกรรม", "direction": "ascending" } ],
        "page_size": 1
    }
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if res.get("results"):
            page = res["results"][0]
            props = page.get('properties', {})
            title = props.get("ชื่อกิจกรรม", {}).get("title", [])[0]["text"]["content"]
            d_str = props.get("วันที่จัดกิจกรรม", {}).get("date", {}).get("start")
            event_type = "ทั่วไป"
            if 'ประเภทงาน' in props:
                pt = props['ประเภทงาน']
                if pt['type'] == 'select' and pt['select']: event_type = pt['select']['name']
                elif pt['type'] == 'multi_select' and pt['multi_select']: event_type = pt['multi_select'][0]['name']
            
            event_url = ""
            try: event_url = props.get("URL", {}).get("url", "")
            except: pass
            
            return {"title": title, "date": d_str, "type": event_type, "url": event_url}
    except: pass
    return None

@st.cache_data(ttl=300)
def get_ranking_dataframe():
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    members = []
    has_more = True; next_cursor = None
    
    today = date.today()

    while has_more:
        payload = { "page_size": 100 }
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            res = requests.post(url, json=payload, headers=headers).json()
            for page in res.get("results", []):
                props = page["properties"]
                
                # --- ข้อมูลพื้นฐาน ---
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

                # --- คำนวณอายุ ---
                age = 99 # ค่า Default แก่สุดไว้ก่อนถ้าไม่มีวันเกิด
                try:
                    b_str = props.get("วันเกิด", {}).get("date", {}).get("start")
                    if b_str:
                        b_date = datetime.strptime(b_str, "%Y-%m-%d").date()
                        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
                except: pass

                # --- Rank SS2 (Normal) ---
                score = 0
                sp = props.get("คะแนน Rank SS2") 
                if sp:
                    if sp['type'] == 'number': score = sp['number'] or 0
                    elif sp['type'] == 'rollup': score = sp['rollup'].get('number', 0) or 0
                    elif sp['type'] == 'formula': score = sp['formula'].get('number', 0) or 0
                
                rank_val = 9999
                try:
                    r_list = props.get("อันดับ Rank SS2", {}).get("rich_text", [])
                    if r_list:
                        r_text = r_list[0]["text"]["content"]
                        if "/" in r_text: rank_val = int(r_text.split('/')[0])
                        else: rank_val = int(r_text)
                except: pass

                # --- Rank SS2 (Junior) ---
                score_jr = 0
                sp_jr = props.get("คะแนน Rank SS2 Junior") 
                if sp_jr:
                    if sp_jr['type'] == 'number': score_jr = sp_jr['number'] or 0
                    elif sp_jr['type'] == 'rollup': score_jr = sp_jr['rollup'].get('number', 0) or 0
                    elif sp_jr['type'] == 'formula': score_jr = sp_jr['formula'].get('number', 0) or 0

                rank_jr_val = 9999
                rank_jr_str = "-"
                try:
                    r_jr_list = props.get("อันดับ Rank SS2 Junior", {}).get("rich_text", [])
                    if r_jr_list:
                        r_text = r_jr_list[0]["text"]["content"]
                        rank_jr_str = r_text
                        if "/" in r_text: rank_jr_val = int(r_text.split('/')[0])
                        else: rank_jr_val = int(r_text)
                except: pass

                members.append({ 
                    "id": page["id"], 
                    "name": name, 
                    "photo": photo_url, 
                    "group": group, 
                    "title": title,
                    "age": age,
                    # Normal
                    "score": score, 
                    "rank_num": rank_val,
                    # Junior
                    "score_jr": score_jr,
                    "rank_jr_num": rank_jr_val,
                    "rank_jr_str": rank_jr_str
                })
            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")
        except: break
    
    # ✅ ป้องกัน KeyError: กำหนด Columns เสมอ
    cols = ['id', 'name', 'photo', 'group', 'title', 'age', 'score', 'rank_num', 'score_jr', 'rank_jr_num', 'rank_jr_str']
    if not members: 
        return pd.DataFrame(columns=cols + ['อันดับ', 'อันดับ Junior'])
    
    df = pd.DataFrame(members)
    
    # เพิ่มคอลัมน์แสดงผล (Mapping)
    df['อันดับ'] = df['rank_num'] 
    df['อันดับ Junior'] = df['rank_jr_num']
    
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
    if photo_url: properties["Photo"] = { "files": [{ "name": "profile.jpg", "type": "external", "external": {"url": photo_url} }] }
    if province: properties["มาจากจังหวัด"] = { "multi_select": [{ "name": province }] }
    payload = { "parent": { "database_id": MEMBER_DB_ID }, "properties": properties }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200: return response.json()
        else: return None
    except: return None

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

# ================= GLOBAL DIALOGS =================

@st.dialog("📰 รายละเอียด")
def show_news_popup(item):
    st.subheader(item['topic'])
    cat_style = ""
    if "ประกาศ" in item['category']: cat_style = "color: #FF4B4B; font-weight: bold;"
    elif "กฎ" in item['category']: cat_style = "color: #2E86C1; font-weight: bold;"
    else: cat_style = "color: gray;"
    st.markdown(f"🗓️ {item['date']} | 🏷️ <span style='{cat_style}'>{item['category']}</span>", unsafe_allow_html=True)
    st.markdown("---")
    if item['image_urls']:
        st.image(item['image_urls'], use_container_width=True)
        if len(item['image_urls']) > 1:
             st.caption(f"ทั้งหมด {len(item['image_urls'])} รูปภาพ")
        st.write("")
    st.write(item['content'])
    if item['url']:
        st.markdown("---")
        st.link_button("🔗 Link ต้นทาง", item['url'], use_container_width=True)

@st.dialog("รายละเอียดกิจกรรม")
def show_event_popup(title, url):
    st.write(f"คุณต้องการเปิดหน้าเว็บของงาน **{title}** หรือไม่?")
    st.write("") 
    st.link_button("🚀 ไปที่หน้าเว็บ", url, type="primary", use_container_width=True)

# ================= UI START =================
st.title("🏆LSX Ranking")

cookie_manager = stx.CookieManager(key="lsx_cookie_manager")

if 'user_page' not in st.session_state: 
    st.session_state['user_page'] = None
if 'selected_menu' not in st.session_state: 
    st.session_state['selected_menu'] = "🏠 หน้าแรก (Dashboard)"
if 'auth_mode' not in st.session_state: 
    st.session_state['auth_mode'] = 'login' 
if 'last_clicked_event' not in st.session_state: 
    st.session_state['last_clicked_event'] = None

if 'cookie_checked' not in st.session_state:
    st.session_state['cookie_checked'] = False

if not st.session_state['cookie_checked']:
    time.sleep(0.5) 
    cookie_user_id = cookie_manager.get(cookie="lsx_user_id")
    if cookie_user_id:
        user_data = get_user_by_id(cookie_user_id)
        if user_data:
            st.session_state['user_page'] = user_data
    st.session_state['cookie_checked'] = True

# ================= SIDEBAR =================
with st.sidebar:
    st.header("📌 เมนูหลัก")
    if st.session_state['user_page']:
        try: user_name = st.session_state['user_page']['properties']['ชื่อ']['title'][0]['text']['content']
        except: user_name = "Member"
        st.success(f"👤 {user_name}")
    
    menu_options = ["🏠 หน้าแรก (Dashboard)", "🏆 ตารางอันดับ", "📢 ประกาศ/ข่าวสาร", "📜 กฎระเบียบและข้อบังคับ", "📅 ปฏิทินกิจกรรม", "📸 แกลเลอรี", "🔐 ระบบสมาชิก / ข้อมูลส่วนตัว"]
    
    def update_menu():
        st.session_state['selected_menu'] = st.session_state['menu_selection']
        st.session_state['calendar_force_key'] = str(uuid.uuid4())

    if 'calendar_force_key' not in st.session_state:
        st.session_state['calendar_force_key'] = str(uuid.uuid4())

    try: default_index = menu_options.index(st.session_state['selected_menu'])
    except ValueError: default_index = 0
        
    st.radio(
        "ไปยังหน้า:", 
        menu_options, 
        index=default_index, 
        key="menu_selection", 
        on_change=update_menu
    )
    st.write("---")
    st.caption("LSX Ranking System v2.0")

# ================= PAGE CONTENT =================

# 🏠 PAGE: DASHBOARD
if st.session_state['selected_menu'] == "🏠 หน้าแรก (Dashboard)":
    st.header("🏠 หน้าแรก (Dashboard)")
    
    col_d1, col_d2 = st.columns([2, 1])
    
    with col_d1:
        # ใช้ Tabs แบ่งระหว่าง Top 10 ปกติ และ Top 10 Junior
        tab_top_main, tab_top_jr = st.tabs(["🏆 Top 10 Players", "👶 Top 10 Junior (<=13 ปี)"])
        
        with st.spinner("โหลดอันดับ..."):
            df_dash = get_ranking_dataframe()
            
            # --- TAB 1: Normal Top 10 ---
            with tab_top_main:
                st.subheader("🏆 Top 10 Players")
                if not df_dash.empty and 'score' in df_dash.columns:
                    # ✅ เรียงเหมือนเดิม: คะแนน (มาก->น้อย) -> ชื่อ (ก->ฮ)
                    df_normal = df_dash.sort_values(by=["score", "name"], ascending=[False, True]).reset_index(drop=True)
                    df_top10 = df_normal.head(10)
                    
                    st.dataframe(df_top10[['อันดับ', 'photo', 'name', 'score', 'group']],
                        column_config={ 
                            "photo": st.column_config.ImageColumn("รูป", width="small"), 
                            "อันดับ": st.column_config.NumberColumn("Rank", format="%d"), 
                            "name": st.column_config.TextColumn("Player"), 
                            "score": st.column_config.NumberColumn("Score", format="%d ⭐"), 
                            "group": st.column_config.TextColumn("Group") 
                        },
                        hide_index=True, use_container_width=True, height=450)
                else: st.info("กำลังประมวลผลอันดับ... (หรือยังไม่มีข้อมูล)")

            # --- TAB 2: Junior Top 10 ---
            with tab_top_jr:
                st.subheader("👶 Top 10 Junior")
                if not df_dash.empty and 'age' in df_dash.columns:
                    # ✅ กรองอายุ <= 13
                    df_jr = df_dash[df_dash['age'] <= 13].copy()
                    
                    if not df_jr.empty:
                        # ✅ เรียง Junior: คะแนน Junior (มาก->น้อย) -> ชื่อ (ก->ฮ)
                        df_jr = df_jr.sort_values(by=["score_jr", "name"], ascending=[False, True]).reset_index(drop=True)
                        df_top10_jr = df_jr.head(10)
                        
                        st.dataframe(df_top10_jr[['อันดับ Junior', 'photo', 'name', 'score_jr', 'age']],
                            column_config={ 
                                "photo": st.column_config.ImageColumn("รูป", width="small"), 
                                "อันดับ Junior": st.column_config.NumberColumn("Rank Jr.", format="%d"), 
                                "name": st.column_config.TextColumn("Player"), 
                                "score_jr": st.column_config.NumberColumn("Score Jr.", format="%d 🍼"),
                                "age": st.column_config.NumberColumn("อายุ", format="%d ปี")
                            },
                            hide_index=True, use_container_width=True, height=450)
                    else:
                        st.info("ไม่มีผู้เล่นรุ่น Junior (อายุ <= 13 ปี)")
                else: st.info("กำลังประมวลผลอันดับ... (กรุณาลองกดปุ่ม C เพื่อ Clear Cache)")

    with col_d2:
        # --- กิจกรรมถัดไป ---
        st.subheader("📅 กิจกรรมถัดไป")
        with st.spinner("กำลังโหลดกิจกรรมถัดไป..."):
            next_event = get_upcoming_event()
            if next_event:
                with st.container(border=True):
                    if next_event['url']: st.markdown(f"### [{next_event['title']}]({next_event['url']})")
                    else: st.markdown(f"### {next_event['title']}")
                    
                    try:
                        d_obj = datetime.strptime(next_event['date'], "%Y-%m-%d").date()
                        d_nice = d_obj.strftime("%d %b %Y")
                        days_left = (d_obj - get_thai_date()).days
                    except: d_nice = next_event['date']; days_left = 99
                    st.write(f"🗓️ **วันที่:** {d_nice}")
                    st.write(f"🏷️ **ประเภท:** {next_event['type']}")
                    if days_left == 0: st.error("🔥 วันนี้!")
                    elif days_left > 0: st.info(f"⏳ อีก {days_left} วัน")
                    else: st.warning("จบแล้ว")
                    
                    if next_event['url']: st.link_button("🚀 ไปที่หน้าเว็บ", next_event['url'], use_container_width=True)
            else: st.info("ยังไม่มีกิจกรรมเร็วๆ นี้")

        # --- รูปภาพล่าสุด ---
        st.write("") 
        st.subheader("📸 รูปภาพล่าสุด")
        gallery = get_photo_gallery()
        if gallery:
            latest = gallery[0]
            with st.container(border=True):
                st.write(f"**{latest['title']}**")
                st.caption(f"🗓️ {latest['date_str']}")
                st.link_button("🖼️ ดูอัลบั้มนี้", latest['photo_url'], use_container_width=True)
        else:
            st.info("ยังไม่มีรูปภาพ")

    # --- ส่วนประกาศ ---
    st.write("---")
    st.subheader("📢 ประกาศล่าสุด")
    with st.spinner("กำลังโหลดข่าว..."):
        news_items = get_latest_news(limit=1)
        if news_items:
            for item in news_items:
                with st.container(border=True):
                    st.markdown(f"**{item['topic']}**")
                    cat_color = "gray"
                    if "ประกาศ" in item['category']: cat_color = "red"
                    elif "กฎ" in item['category']: cat_color = "#2E86C1"
                    st.markdown(f"<span style='color:{cat_color}; font-size:12px;'>🏷️ {item['category']}</span>", unsafe_allow_html=True)
                    
                    short_content = (item['content'][:150] + '...') if len(item['content']) > 150 else item['content']
                    st.write(short_content)
                    st.caption(f"🗓️ {item['date']}")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("อ่านต่อ...", key=f"dash_read_{item['id']}"):
                            show_news_popup(item)
                    with c2:
                        if item['url']: st.link_button("🔗 Link ต้นทาง", item['url'], use_container_width=True)
        else: st.info("ไม่มีประกาศใหม่")

# 🏆 PAGE: LEADERBOARD
elif st.session_state['selected_menu'] == "🏆 ตารางอันดับ":
    st.subheader("🏆 Leaderboard")
    
    with st.spinner("กำลังโหลดข้อมูลอันดับ..."):
        df_leaderboard = get_ranking_dataframe()
        
    if not df_leaderboard.empty:
        # สร้าง Tabs แยกประเภท
        tab_lb_main, tab_lb_jr = st.tabs(["🏆 อันดับรวม (Normal)", "👶 อันดับ Junior (<=13 ปี)"])
        
        # --- TAB 1: Normal Rank ---
        with tab_lb_main:
            st.subheader("🏆 ตารางอันดับรวม")
            # ✅ เรียงเหมือนเดิม: คะแนน (มาก->น้อย) -> ชื่อ (ก->ฮ)
            df_main = df_leaderboard.sort_values(by=["score", "name"], ascending=[False, True]).reset_index(drop=True)
            
            st.dataframe(df_main[['อันดับ', 'photo', 'name', 'score', 'group', 'title']],
                column_config={ 
                    "photo": st.column_config.ImageColumn("รูปโปรไฟล์"), 
                    "อันดับ": st.column_config.NumberColumn("อันดับ", format="%d"), 
                    "name": st.column_config.TextColumn("ชื่อสมาชิก"), 
                    "score": st.column_config.NumberColumn("คะแนนรวม", format="%d ⭐"), 
                    "group": st.column_config.TextColumn("Rank Group"), 
                    "title": st.column_config.TextColumn("Rank Title") 
                },
                hide_index=True, use_container_width=True, height=600)

        # --- TAB 2: Junior Rank ---
        with tab_lb_jr:
            st.subheader("👶 ตารางอันดับ Junior")
            
            # ✅ กรองเฉพาะอายุ <= 13 ปี
            df_jr = df_leaderboard[df_leaderboard['age'] <= 13].copy()
            
            if not df_jr.empty:
                # ✅ เรียง Junior: คะแนน Junior (มาก->น้อย) -> ชื่อ (ก->ฮ)
                df_jr = df_jr.sort_values(by=["score_jr", "name"], ascending=[False, True]).reset_index(drop=True)
                
                st.dataframe(df_jr[['อันดับ Junior', 'photo', 'name', 'score_jr', 'age']],
                    column_config={ 
                        "photo": st.column_config.ImageColumn("รูปโปรไฟล์"), 
                        "อันดับ Junior": st.column_config.NumberColumn("อันดับ Jr.", format="%d"), 
                        "name": st.column_config.TextColumn("ชื่อสมาชิก"), 
                        "score_jr": st.column_config.NumberColumn("คะแนน Jr.", format="%d 🍼"),
                        "age": st.column_config.NumberColumn("อายุ", format="%d ปี")
                    },
                    hide_index=True, use_container_width=True, height=600)
            else:
                st.info("ยังไม่มีข้อมูลผู้เล่นรุ่น Junior (อายุไม่เกิน 13 ปี)")

    else: st.warning("ไม่พบข้อมูลสมาชิก")

# 📢 PAGE: NEWS (FULL)
elif st.session_state['selected_menu'] == "📢 ประกาศ/ข่าวสาร":
    st.subheader("📢 ประกาศและข่าวสารทั้งหมด")
    with st.spinner("กำลังโหลดข่าวสาร..."):
        all_news = get_latest_news(limit=50)
        if all_news:
            for item in all_news:
                with st.container(border=True):
                    c_head, c_cat = st.columns([3, 1])
                    with c_head: st.markdown(f"### {item['topic']}")
                    with c_cat:
                        cat_color = "#808080"
                        if "ประกาศ" in item['category']: cat_color = "#FF4B4B"
                        elif "กฎ" in item['category']: cat_color = "#2E86C1"
                        st.markdown(f"<div style='text-align:right;'><span style='background-color:{cat_color}; padding: 4px 10px; border-radius: 5px; color: white;'>{item['category']}</span></div>", unsafe_allow_html=True)
                    
                    st.caption(f"🗓️ วันที่ประกาศ: {item['date']}")
                    st.markdown("---")
                    
                    short_content = (item['content'][:200] + '...') if len(item['content']) > 200 else item['content']
                    st.write(short_content)
                    
                    if st.button("📖 อ่านเนื้อหาฉบับเต็ม", key=f"news_full_{item['id']}"):
                        show_news_popup(item)

        else: st.info("ยังไม่มีประกาศ")

# 📜 PAGE: RULES (NEW)
elif st.session_state['selected_menu'] == "📜 กฎระเบียบและข้อบังคับ":
    st.subheader("📜 กฎระเบียบและข้อบังคับ")
    with st.spinner("กำลังโหลดกฎระเบียบ..."):
        rules_news = get_latest_news(limit=100, category_filter="กฎ")
        if rules_news:
            for item in rules_news:
                with st.container(border=True):
                    c_head, c_cat = st.columns([3, 1])
                    with c_head: st.markdown(f"### {item['topic']}")
                    with c_cat:
                        st.markdown(f"<div style='text-align:right;'><span style='background-color:#2E86C1; padding: 4px 10px; border-radius: 5px; color: white;'>{item['category']}</span></div>", unsafe_allow_html=True)
                    
                    st.caption(f"🗓️ วันที่ประกาศ: {item['date']}")
                    st.markdown("---")
                    
                    short_content = (item['content'][:200] + '...') if len(item['content']) > 200 else item['content']
                    st.write(short_content)
                    
                    if st.button("📖 อ่านเนื้อหาฉบับเต็ม", key=f"rule_full_{item['id']}"):
                        show_news_popup(item)
        else: st.info("ยังไม่มีข้อมูลกฎระเบียบ")

# 📅 PAGE: CALENDAR
elif st.session_state['selected_menu'] == "📅 ปฏิทินกิจกรรม":
    st.subheader("📅 ปฏิทินกิจกรรม (ม.ค. - มี.ค. 2026)")
    
    with st.spinner("กำลังโหลดปฏิทิน..."): 
        events = get_calendar_events()
    
    calendar_options = { 
        "headerToolbar": { "left": "today prev,next", "center": "title", "right": "dayGridMonth,listMonth" }, 
        "initialDate": "2026-01-01", 
        "initialView": "dayGridMonth",
        "height": 750,
    }
    
    try:
        cal_key = f"cal_force_{st.session_state.get('calendar_force_key', 'default')}"
        cal_data = calendar(events=events, options=calendar_options, callbacks=['eventClick'], key=cal_key)
        
        if cal_data.get("callback") == "eventClick":
            current_click_data = cal_data["eventClick"]["event"]
            if current_click_data != st.session_state['last_clicked_event']:
                st.session_state['last_clicked_event'] = current_click_data
                clicked_title = current_click_data["title"]
                clicked_url = current_click_data.get("extendedProps", {}).get("url")
                if clicked_url and clicked_url != "#": 
                    # ✅ เรียกใช้ Dialog ที่ประกาศไว้ข้างบน (Global)
                    show_event_popup(clicked_title, clicked_url)
                else: 
                    st.toast(f"ℹ️ กิจกรรม {clicked_title} ไม่มีลิงก์ URL")
                    
    except Exception as e:
        st.error(f"❌ Error: {e}")

# 📸 PAGE: GALLERY
elif st.session_state['selected_menu'] == "📸 แกลเลอรี":
    st.subheader("📸 แกลเลอรีรูปภาพกิจกรรม")
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

# 🔐 PAGE: MEMBER SYSTEM
elif st.session_state['selected_menu'] == "🔐 ระบบสมาชิก / ข้อมูลส่วนตัว":
    
    if st.session_state['user_page'] is None:
        
        if st.session_state['auth_mode'] == 'login':
            st.subheader("🔐 เข้าสู่ระบบ")
            with st.form("login_form"):
                st.info("💡 Username คือ id ตามด้วย @lsxrank")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                remember_me = st.checkbox("จำฉันไว้ในระบบ (Remember me)")
                c1, c2 = st.columns(2)
                with c1: submitted = st.form_submit_button("Login", use_container_width=True)
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
                if st.button("📝 สมัครสมาชิกใหม่"): st.session_state['auth_mode'] = 'register'; st.rerun()
            else: st.warning(f"⚠️ ปิดรับสมัครสมาชิกแล้ว (สิ้นสุดเมื่อ {REGISTRATION_DEADLINE.strftime('%d %b %Y')})")

        else: # Register
            st.subheader("📝 สมัครสมาชิกใหม่")
            if st.button("⬅️ กลับไปหน้า Login"): st.session_state['auth_mode'] = 'login'; st.rerun()
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
                
                if st.form_submit_button("ยืนยันการสมัคร", type="primary"):
                    if not reg_display_name or not reg_email or not reg_pass: st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
                    elif not reg_province: st.error("กรุณาเลือกจังหวัด")
                    elif not reg_birthday: st.error("กรุณาระบุวันเกิด")
                    elif reg_pass != reg_confirm_pass: st.error("รหัสผ่านไม่ตรงกัน")
                    elif not reg_photo: st.error("กรุณาอัปโหลดรูปโปรไฟล์")
                    else:
                        with st.spinner("กำลังตรวจสอบชื่อ..."):
                            if check_duplicate_name(reg_display_name): st.error("ชื่อนี้มีผู้ใช้งานแล้ว")
                            else:
                                with st.spinner("กำลังอัปโหลดรูป..."):
                                    url = upload_image_to_imgbb(reg_photo)
                                    if url:
                                        with st.spinner("กำลังสร้างบัญชี..."):
                                            new_user = create_new_member(reg_display_name, reg_email, reg_pass, reg_birthday, url, reg_province)
                                            if new_user:
                                                real_user = None
                                                try: real_user = new_user["properties"]["username"]["formula"]["string"]
                                                except: pass
                                                if not real_user:
                                                    time.sleep(1); real_user = get_username_from_created_page(new_user['id'])
                                                if not real_user: real_user = f"{new_user['id']}@lsxrank"
                                                st.success("🎉 สมัครสมาชิกสำเร็จ!")
                                                st.balloons()
                                                st.success(f"Username: **{real_user}**")
                                                st.code(real_user)
                                                st.warning("จดจำ Username ไว้ใช้ Login ครั้งต่อไป")
                                    else: st.error("อัปโหลดรูปไม่สำเร็จ")

    # Login Success -> Profile Page
    else:
        user_page = st.session_state['user_page']
        page_id = user_page['id']
        props = user_page['properties']
        
        try: current_password_chk = props["Password"]["rich_text"][0]["text"]["content"]
        except: current_password_chk = ""
        if current_password_chk == "lsx":
            st.warning("⚠️ **ความปลอดภัย:** กรุณาเปลี่ยนรหัสผ่านใหม่ก่อนใช้งานต่อ")
            with st.container(border=True):
                st.subheader("🔐 เปลี่ยนรหัสผ่าน")
                f_pass = st.text_input("รหัสผ่านใหม่", type="password", key="fp1")
                f_conf = st.text_input("ยืนยันรหัสผ่านใหม่", type="password", key="fp2")
                if st.button("บันทึกรหัสผ่าน", type="primary"):
                    if not f_pass: st.error("กรุณากรอกรหัสผ่าน")
                    elif f_pass != f_conf: st.error("รหัสผ่านไม่ตรงกัน")
                    elif f_pass == "lsx": st.error("ห้ามใช้รหัสเดิม")
                    else:
                        if update_member_info(page_id, None, None, f_pass, None, None):
                            st.toast("✅ สำเร็จ!"); time.sleep(1); st.session_state['user_page'] = get_user_by_id(page_id); st.rerun()
                        else: st.error("ผิดพลาด")
            st.stop()

        try: rank_list = props.get("อันดับ Rank SS2", {}).get("rich_text", [])
        except: rank_list = []
        full_rank_str = rank_list[0]["text"]["content"] if rank_list else "-"
        
        try: stats_str = props.get("สถิติเข้าร่วม SS2", {}).get("rich_text", [])[0]["text"]["content"]
        except: stats_str = "0/0"
        try: attended, total_events = map(int, stats_str.split("/")); progress_val = attended/total_events if total_events>0 else 0
        except: attended, total_events, progress_val = 0, 0, 0.0

        try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
        except: current_display = ""
        try: current_photo = props["Photo"]["files"][0]["external"]["url"]
        except: current_photo = "https://via.placeholder.com/150"
        try: current_birth = datetime.strptime(props["วันเกิด"]["date"]["start"], "%Y-%m-%d").date()
        except: current_birth = None
        try: current_prov = props["มาจากจังหวัด"]["multi_select"][0]["name"]
        except: current_prov = None
        
        # --- ดึงข้อมูล Junior เพิ่มเติม ---
        try: rank_jr_list = props.get("อันดับ Rank SS2 Junior", {}).get("rich_text", [])
        except: rank_jr_list = []
        full_rank_jr_str = rank_jr_list[0]["text"]["content"] if rank_jr_list else "-"
        
        try: score_jr = props.get("คะแนน Rank SS2 Junior", {}).get("rollup", {}).get("number", 0)
        except: score_jr = 0

        # คำนวณอายุ
        user_age = 0
        if current_birth:
            today = date.today()
            user_age = today.year - current_birth.year - ((today.month, today.day) < (current_birth.month, current_birth.day))

        # --- ส่วนแสดงผล ---
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(current_photo, width=150)
            st.divider()
            
            st.markdown(f"**👤 Name:** {current_display}")
            st.markdown(f"**🎂 Age:** {user_age} ปี")
            st.caption(f"📍 {current_prov if current_prov else '-'}")
            
            st.markdown("---")
            if st.button("Logout", type="secondary"):
                try: cookie_manager.delete("lsx_user_id")
                except: pass
                st.session_state['user_page'] = None
                st.session_state['auth_mode'] = 'login'
                st.toast("👋 Logout Success"); time.sleep(1); st.rerun()

        with col2:
            # ใช้ Tabs แยกข้อมูล
            tab_pf_info, tab_pf_jr, tab_pf_edit = st.tabs(["📊 ข้อมูล Rank SS2", "👶 Rank Junior", "📝 แก้ไขข้อมูล"])
            
            # Tab 1: Rank SS2 (Normal)
            with tab_pf_info:
                st.subheader("🏆 Rank Season 2")
                try: rank_group = props.get("Rank Season 2 Group", {}).get("formula", {}).get("string") or "-"
                except: rank_group = "-"
                try: rank_ss2 = props.get("Rank Season 2", {}).get("formula", {}).get("string") or "-"
                except: rank_ss2 = "-"
                try: score_ss2 = props.get("คะแนน Rank SS2", {}).get("rollup", {}).get("number", 0)
                except: score_ss2 = 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Group", rank_group)
                m2.metric("Rank", rank_ss2)
                m3.metric("Score", f"{score_ss2} ⭐")
                
                if st.button(f"ดูตารางอันดับรวม (ที่ {full_rank_str})", use_container_width=True):
                    st.session_state['selected_menu'] = '🏆 ตารางอันดับ'; st.rerun() 
                
                st.markdown("---")
                st.markdown("**🔥 สถิติการเข้าร่วม**")
                st.progress(progress_val)
                st.caption(f"{stats_str} งาน")

                st.subheader("📜 Rank History (Normal)")
                try: r_ids = [r['id'] for r in props.get("สถิติการลง Rank ทั้งหมด", {}).get("relation", [])]
                except: r_ids = []
                if r_ids:
                    with st.container(height=200):
                        for i in r_ids: st.write(f"• {get_page_title(i)}")
                else: st.info("-")

            # Tab 2: Rank Junior (NEW)
            with tab_pf_jr:
                st.subheader("👶 Rank Season 2 (Junior)")
                
                if user_age > 13:
                    st.warning(f"⚠️ อายุของคุณคือ {user_age} ปี (เกินเกณฑ์ Junior 13 ปี)")
                
                mj1, mj2 = st.columns(2)
                mj1.metric("Junior Rank", full_rank_jr_str)
                mj2.metric("Junior Score", f"{score_jr} 🍼")
                
                st.markdown("---")
                st.subheader("📜 Rank History (Junior)")
                try: r_jr_ids = [r['id'] for r in props.get("สถิติการลง Rank Junior ทั้งหมด", {}).get("relation", [])]
                except: r_jr_ids = [] 
                
                if r_jr_ids:
                    with st.container(height=200):
                        for i in r_jr_ids: st.write(f"• {get_page_title(i)}")
                else: st.info("ไม่มีประวัติการแข่ง Junior")

            # Tab 3: Edit Profile
            with tab_pf_edit:
                st.subheader("📝 แก้ไขข้อมูลส่วนตัว")
                n_name = st.text_input("Display Name", value=current_display)
                n_birth = st.date_input("วันเกิด", value=current_birth if current_birth else date.today(), min_value=date(1900,1,1), max_value=date.today())
                
                prov_opts = get_province_options()
                idx = prov_opts.index(current_prov) if current_prov in prov_opts else None
                n_prov = st.selectbox("มาจากจังหวัด", prov_opts, index=idx, placeholder="เลือกจังหวัด...")
                
                st.markdown("---")
                up_file = st.file_uploader("รูปโปรไฟล์ใหม่", type=['jpg','png'])
                if up_file: st.image(up_file, width=100)
                st.markdown("---")
                n_p1 = st.text_input("เปลี่ยนรหัสผ่าน (ถ้ามี)", type="password")
                n_p2 = st.text_input("ยืนยันรหัสผ่าน", type="password")
                
                if st.button("💾 บันทึกการแก้ไข", type="primary"):
                    err = False; final_url = None
                    if n_p1 and n_p1 != n_p2: st.error("รหัสผ่านไม่ตรงกัน"); err = True
                    if up_file and not err:
                        with st.spinner("Uploading..."):
                            l = upload_image_to_imgbb(up_file)
                            if l: final_url = l
                            else: err = True
                    if not err:
                        if update_member_info(page_id, n_name if n_name!=current_display else None, final_url, n_p1 if n_p1 else None, n_birth if n_birth!=current_birth else None, n_prov if n_prov!=current_prov else None):
                            st.toast("✅ บันทึกสำเร็จ!"); time.sleep(1); st.session_state['user_page'] = get_user_by_id(page_id); st.rerun()
                        else: st.error("บันทึกไม่สำเร็จ")

st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #888; font-size: 14px;'>Created by LovelyToonZ</div>", unsafe_allow_html=True)
