import streamlit as st
import requests
import time
from datetime import datetime, date

# ================= CONFIGURATION =================
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    IMGBB_API_KEY = st.secrets.get("IMGBB_API_KEY", "0e31066455b60d727553d11e22761846") 
except FileNotFoundError:
    # แก้ไขให้ปลอดภัย (ไม่ใส่ Key จริงใน Code เผื่อเผลอเอาขึ้น GitHub)
    NOTION_TOKEN = "Please_Check_Secrets_File"
    IMGBB_API_KEY = "Please_Check_Secrets_File"

MEMBER_DB_ID = "271e6d24b97d80289175eef889a90a09" 

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ================= HELPER FUNCTION: GET RELATION NAME =================
@st.cache_data(show_spinner=False)
def get_page_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for prop_val in data["properties"].values():
                if prop_val["type"] == "title":
                    if prop_val["title"]:
                        return prop_val["title"][0]["text"]["content"]
                    else:
                        return "No Title"
        return "Unknown Page"
    except:
        return "Error Loading"

# ================= FUNCTION: IMGBB UPLOAD =================
def upload_image_to_imgbb(image_file):
    url = "https://api.imgbb.com/1/upload"
    payload = { "key": IMGBB_API_KEY }
    file_data = image_file.getvalue()
    try:
        response = requests.post(url, data=payload, files={'image': file_data}, timeout=20, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data['success']: return data['data']['url']
            else: st.error(f"imgbb Error: {data}")
        else: st.error(f"Upload Failed: {response.status_code}")
    except Exception as e: st.error(f"Connection Error: {e}")
    return None

# ================= FUNCTION: NOTION LOGIN =================
# ก๊อปไปวางทับฟังก์ชัน check_login เดิม
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
    
    # --- ส่วน Debug (จับผิด) ---
    st.write("🕵️‍♀️ **กำลังตรวจสอบ...**")
    
    # 1. เช็คว่าใช้ Token ตัวไหน (โชว์แค่ 4 ตัวหน้าพอ เพื่อความปลอดภัย)
    token_preview = NOTION_TOKEN[:4] + "..." if NOTION_TOKEN else "None"
    st.write(f"🔑 ใช้ Token ขึ้นต้นด้วย: `{token_preview}`")
    
    # 2. ลองยิงไปหา Notion
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        st.write(f"📡 สถานะการเชื่อมต่อ (Status Code): `{response.status_code}`")
        
        # ถ้า Error 401 = Token ผิด/ไม่มีสิทธิ์
        if response.status_code == 401:
            st.error("❌ Token ไม่ถูกต้อง (Unauthorized) - กรุณาเช็คใน secrets.toml")
            st.json(data) # โชว์ข้อความฟ้องจาก Notion
            
        # ถ้า Error 404 = Database ID ผิด หรือ บอทหาห้องไม่เจอ
        elif response.status_code == 404:
            st.error("❌ หา Database ไม่เจอ - อย่าลืม Invite Bot เข้า Database นะคะ!")
            
        # ถ้า 200 (สำเร็จ) แต่หาUserไม่เจอ
        elif response.status_code == 200:
            if not data.get('results'):
                st.warning("⚠️ เชื่อมต่อได้...แต่ค้นหาไม่เจอ (Username/Password อาจผิด)")
                st.write("Notion ตอบกลับมาว่า:", data)
            else:
                st.success("✅ Log in สำเร็จ")
                return data['results'][0]
                
    except Exception as e:
        st.error(f"💥 โปรแกรม Error: {e}")
        
    return None

def update_member_info(page_id, new_display_name, new_photo_url, new_password, new_birthday):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {}

    if new_display_name:
        properties["ชื่อ"] = {"title": [{"text": {"content": new_display_name}}]}
    if new_password:
        properties["Password"] = {"rich_text": [{"text": {"content": new_password}}]}
    if new_photo_url:
        properties["Photo"] = { "files": [{ "name": "pic", "type": "external", "external": {"url": new_photo_url} }] }
    if new_birthday:
        properties["วันเกิด"] = { "date": {"start": new_birthday.strftime("%Y-%m-%d")} }

    if not properties: return True
    payload = {"properties": properties}
    response = requests.patch(url, json=payload, headers=headers)
    return response.status_code == 200

# ================= UI PART =================
st.set_page_config(page_title="ระบบสมาชิก LSX Ranking", page_icon="🏆")

if 'user_page' not in st.session_state:
    st.session_state['user_page'] = None

st.title("🧙‍♀️ ระบบสมาชิก LSX Ranking")

# --- LOGIN ---
if st.session_state['user_page'] is None:
    with st.form("login_form"):
        st.info("💡 Username คือ id ตามด้วย @lsxrank")
        st.info("💡 ตรวจสอบ id ได้ที่ >> https://bbxlopburisaraburi.notion.site/2d2e6d24b97d8156a52bd2794a36d90e?v=2d2e6d24b97d81c3bace000c671d914a&source=copy_link")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            user_data = check_login(username, password)
            if user_data:
                st.session_state['user_page'] = user_data
                st.rerun()
            else:
                st.error("Login failed")

# --- EDIT PAGE ---
else:
    user_page = st.session_state['user_page']
    page_id = user_page['id']
    props = user_page['properties']
    
    # Get Current Data
    try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
    except: current_display = ""
    try: current_photo_url = props["Photo"]["files"][0]["external"]["url"]
    except: current_photo_url = "https://via.placeholder.com/150"
    try:
        birth_str = props["วันเกิด"]["date"]["start"]
        current_birth = datetime.strptime(birth_str, "%Y-%m-%d").date()
    except: current_birth = None

    # Get Relations
    rank_history_ids = [r['id'] for r in props.get("สถิติการลง Rank ทั้งหมด", {}).get("relation", [])]
    reward_history_ids = [r['id'] for r in props.get("อันดับ 1-4 SS1", {}).get("relation", [])]

    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(current_photo_url, caption="รูปปัจจุบัน", width=150)

    with col2:
        st.subheader("📝 แก้ไขข้อมูล")
        
        new_display = st.text_input("Display Name", value=current_display)
        
        # --- ⚠️ แก้ไขตรงนี้: เพิ่ม min_value ให้เลือกปีย้อนหลังได้ถึง 1900 ---
        min_date = date(1900, 1, 1)
        max_date = date.today()
        
        new_birth_input = st.date_input(
            "วันเกิด (Birthday)", 
            value=current_birth if current_birth else max_date,
            min_value=min_date, # อนุญาตให้เลือกได้ตั้งแต่ปี 1900
            max_value=max_date  # ห้ามเลือกเกินวันปัจจุบัน
        )
        
        st.markdown("---")
        st.markdown("##### 📸 อัปโหลดรูปโปรไฟล์ใหม่")
        uploaded_file = st.file_uploader("เลือกไฟล์รูปภาพ (jpg, png)", type=['jpg', 'png', 'jpeg'])
        if uploaded_file: st.image(uploaded_file, width=120)

        st.markdown("---")
        new_pass = st.text_input("รหัสผ่านใหม่ (เว้นว่างถ้าไม่เปลี่ยน)", type="password")
        confirm_pass = st.text_input("ยืนยันรหัสผ่าน", type="password")
        
        if st.button("💾 บันทึกข้อมูลทั้งหมด", type="primary"):
            error_flag = False
            final_photo_url = None
            if new_pass and new_pass != confirm_pass:
                st.error("❌ รหัสผ่านไม่ตรงกัน")
                error_flag = True
            
            if uploaded_file and not error_flag:
                with st.spinner("กำลังอัปโหลดรูปภาพ..."):
                    img_link = upload_image_to_imgbb(uploaded_file)
                    if img_link: final_photo_url = img_link
                    else: error_flag = True

            if not error_flag:
                p_name = new_display if new_display != current_display else None
                p_photo = final_photo_url 
                p_pass = new_pass if new_pass else None
                p_birth = new_birth_input if new_birth_input != current_birth else None
                
                if update_member_info(page_id, p_name, p_photo, p_pass, p_birth):
                    st.toast("✅ บันทึกสำเร็จ!")
                    time.sleep(1)
                    st.session_state['user_page'] = None
                    st.rerun()
                else: st.error("บันทึก Notion ล้มเหลว")

    st.markdown("---")
    st.header("📜 ประวัติและสถิติ")
    h_col1, h_col2 = st.columns(2)
    
    with h_col1:
        st.subheader("⚔️ สถิติการลง Rank")
        if rank_history_ids:
            with st.spinner("กำลังโหลด..."):
                with st.container(height=300):
                    for rid in rank_history_ids:
                        st.write(f"• {get_page_title(rid)}")
        else: st.info("ไม่มีประวัติ")

    with h_col2:
        st.subheader("🏆 รางวัล (SS1)")
        if reward_history_ids:
            with st.spinner("กำลังโหลด..."):
                 with st.container(height=300):
                    for rid in reward_history_ids:
                        st.success(f"🏅 {get_page_title(rid)}")
        else: st.info("ไม่มีรางวัล")

    st.markdown("---")
    if st.button("Logout"):
        st.session_state['user_page'] = None
        st.rerun()



