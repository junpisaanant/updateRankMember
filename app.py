import streamlit as st
import requests
import time

# ================= CONFIGURATION =================
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    IMGBB_API_KEY = st.secrets.get("IMGBB_API_KEY", "0e31066455b60d727553d11e22761846") 
except FileNotFoundError:
    NOTION_TOKEN = "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"
    IMGBB_API_KEY = "0e31066455b60d727553d11e22761846" 

MEMBER_DB_ID = "271e6d24b97d80289175eef889a90a09" 

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ================= FUNCTION: IMGBB UPLOAD =================
def upload_image_to_imgbb(image_file):
    url = "https://api.imgbb.com/1/upload"
    payload = { "key": IMGBB_API_KEY }
    file_data = image_file.getvalue()
    
    try:
        response = requests.post(
            url, 
            data=payload, 
            files={'image': file_data}, 
            timeout=20, 
            verify=False
        )
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                return data['data']['url']
            else:
                st.error(f"imgbb Error: {data}")
        else:
            st.error(f"Upload Failed: {response.status_code} | {response.text}")
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
    return None

# ================= FUNCTION: NOTION LOGIN =================
def check_login(username, password):
    url = f"https://api.notion.com/v1/databases/{MEMBER_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "username",
                    "formula": {"string": {"equals": username}}
                },
                {
                    "property": "Password",
                    "rich_text": {"equals": password}
                }
            ]
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    if data.get('results'): return data['results'][0]
    return None

def update_member_info(page_id, new_display_name, new_photo_url, new_password):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {}

    if new_display_name:
        properties["ชื่อ"] = {"title": [{"text": {"content": new_display_name}}]}
    
    if new_password:
        properties["Password"] = {"rich_text": [{"text": {"content": new_password}}]}

    if new_photo_url:
        properties["Photo"] = {
            "files": [
                { "name": "pic", "type": "external", "external": {"url": new_photo_url} }
            ]
        }

    if not properties: return True
    payload = {"properties": properties}
    response = requests.patch(url, json=payload, headers=headers)
    return response.status_code == 200

# ================= UI PART =================
st.set_page_config(page_title="Member Portal", page_icon="🔐")

if 'user_page' not in st.session_state:
    st.session_state['user_page'] = None

st.title("🔐 แก้ไขข้อมูลสมาชิก")

# --- LOGIN ---
if st.session_state['user_page'] is None:
    with st.form("login_form"):
        st.info("💡 Username คือ id ตามด้วย @lsxrank")
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
    
    try: current_display = props["ชื่อ"]["title"][0]["text"]["content"]
    except: current_display = ""
    try: current_photo_url = props["Photo"]["files"][0]["external"]["url"]
    except: current_photo_url = "https://via.placeholder.com/150"

    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(current_photo_url, caption="รูปปัจจุบัน", width=150)

    with col2:
        st.subheader("📝 แก้ไขข้อมูล")
        
        # 1. ชื่อ
        new_display = st.text_input("Display Name", value=current_display)
        
        st.markdown("---")
        
        # 2. อัปโหลดรูป (ตัด Tab ออกแล้ว เหลือแค่อัปโหลดอย่างเดียว)
        st.markdown("##### 📸 อัปโหลดรูปโปรไฟล์ใหม่")
        uploaded_file = st.file_uploader("เลือกไฟล์รูปภาพ (jpg, png)", type=['jpg', 'png', 'jpeg'])
        
        if uploaded_file:
            st.image(uploaded_file, width=120, caption="ตัวอย่างรูปที่จะใช้")

        st.markdown("---")
        
        # 3. รหัสผ่าน
        new_pass = st.text_input("รหัสผ่านใหม่ (เว้นว่างถ้าไม่เปลี่ยน)", type="password")
        confirm_pass = st.text_input("ยืนยันรหัสผ่าน", type="password")
        
        # ปุ่มบันทึก
        if st.button("💾 บันทึกข้อมูลทั้งหมด", type="primary"):
            error_flag = False
            final_photo_url = None # ตัวแปรเก็บลิ้งก์ใหม่ (ถ้ามี)
            
            # เช็ค Password
            if new_pass and new_pass != confirm_pass:
                st.error("❌ รหัสผ่านไม่ตรงกัน")
                error_flag = True
            
            # เช็ค Upload
            if uploaded_file and not error_flag:
                with st.spinner("กำลังอัปโหลดรูปภาพ..."):
                    img_link = upload_image_to_imgbb(uploaded_file)
                    if img_link:
                        final_photo_url = img_link
                    else:
                        error_flag = True # แจ้ง error ไปแล้วใน func

            # บันทึก Notion
            if not error_flag:
                # เตรียมข้อมูล
                p_name = new_display if new_display != current_display else None
                p_photo = final_photo_url # ถ้ามีลิ้งก์ใหม่ ก็ส่งไป
                p_pass = new_pass if new_pass else None
                
                if update_member_info(page_id, p_name, p_photo, p_pass):
                    st.toast("✅ บันทึกสำเร็จ!")
                    time.sleep(1)
                    st.session_state['user_page'] = None
                    st.rerun()
                else:
                    st.error("บันทึก Notion ล้มเหลว")

    if st.button("Logout"):
        st.session_state['user_page'] = None
        st.rerun()