
import hmac
import html
import json
import os
import re
import uuid
from urllib.parse import urlparse

import streamlit as st

st.set_page_config(page_title="rescue-day")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA_FILE = os.path.join(BASE_DIR, "data.json")  # only used for the one-time import
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")  # only used for the one-time import
BUCKET = "materials"

ALLOWED_TYPES = [
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "txt", "md", "csv", "png", "jpg", "jpeg",
]

# ---------- Look and feel ----------
CSS = """
:root {
  --bg: #FAF3E0;
  --card: #FFFCF3;
  --border: #D6C7A5;
  --text: #161616;
  --red: #C62828;
  --blue: #1D4ED8;
  --orange: #D96A00;
  --shadow: 0 1px 2px rgba(70,50,10,.06), 0 6px 16px rgba(70,50,10,.07);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #000000;
    --card: #0D0D0D;
    --border: #2E2E2E;
    --text: #FFFFFF;
    --red: #FF5A5A;
    --blue: #5C9DFF;
    --orange: #FFA133;
    --shadow: none;
  }
}
html, body, .stApp, .stApp button, .stApp input, .stApp textarea {
  font-family: 'Segoe UI', system-ui, sans-serif !important;
}
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stAppDeployButton"], footer { display: none !important; }
.stApp .block-container, .stApp [data-testid="stMainBlockContainer"] {
  max-width: 960px; padding-top: 2rem; padding-bottom: 4rem;
}
.stApp, .stApp p, .stApp label, .stApp li, .stApp small,
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stWidgetLabel"] p { color: var(--text) !important; }
.stApp a { color: var(--text) !important; text-decoration: underline; text-underline-offset: 3px; font-weight: 600; }
.stApp a:hover { color: var(--blue) !important; }
.stApp [data-testid^="stBaseLinkButton"] { text-decoration: none !important; }
.stApp hr { border-color: var(--border) !important; }
[data-testid="stSidebar"] { background: var(--card) !important; border-right: 1px solid var(--border); }
.brand { padding-bottom: 1rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border); }
.brand-name { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; color: var(--text); }
.brand-tag { font-size: 0.8rem; margin-top: 0.3rem; color: var(--text); }
.hd { font-weight: 800; letter-spacing: -0.01em; line-height: 1.2; margin: 0 0 0.75rem 0; }
.hd-subject, .hd-unit, .hd-topic { border-left: 6px solid currentColor; padding-left: 0.8rem; }
.hd-subject { font-size: 2.3rem; color: var(--red) !important; margin-bottom: 1.25rem; }
.hd-unit { font-size: 1.3rem; color: var(--blue) !important; }
.hd-topic { font-size: 1.9rem; color: var(--orange) !important; }
.hd-section { font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text) !important; }
.hd-plain { font-size: 2rem; color: var(--text) !important; }
[class*="st-key-card_"] {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  box-shadow: var(--shadow); padding: 1.1rem 1.25rem; margin-bottom: 0.9rem;
}
.stApp [data-testid^="stBaseButton"], .stApp [data-testid^="stBaseLinkButton"] {
  background: var(--card) !important; border: 1px solid var(--border) !important;
  border-radius: 8px !important; font-weight: 600;
}
.stApp [data-testid^="stBaseButton"]:hover, .stApp [data-testid^="stBaseLinkButton"]:hover {
  border-color: var(--text) !important;
}
.stApp [data-testid^="stBaseButton"] p, .stApp [data-testid^="stBaseLinkButton"] p { color: var(--text) !important; }
.stApp div[data-baseweb="input"], .stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="select"] > div {
  background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 8px !important;
}
.stApp div[data-baseweb="base-input"] { background: transparent !important; }
.stApp input, .stApp textarea {
  color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; background: transparent !important;
}
.stApp div[data-baseweb="select"] * { color: var(--text) !important; }
.stApp [data-testid="stExpander"] details {
  border: 1px solid var(--border) !important; border-radius: 10px !important; background: transparent !important;
}
.stApp [data-testid="stForm"] {
  border: 1px solid var(--border) !important; border-radius: 10px !important; background: transparent !important;
}
.stApp [data-testid="stFileUploaderDropzone"] {
  background: var(--card) !important; border: 1px dashed var(--border) !important; border-radius: 10px !important;
}
.stApp [data-testid="stFileUploader"] * { color: var(--text) !important; }
.stApp [data-testid="stAlert"] { border: 1px solid var(--border); border-radius: 10px; }
"""
st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)


def heading(text, kind):
    """kind is one of: subject, unit, topic, section, plain."""
    st.markdown(
        f'<div class="hd hd-{kind}">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


# ---------- Connection to Supabase ----------
@st.cache_resource
def _client_holder():
    return {"client": None, "last_used": 0.0}


def _make_client():
    from supabase import create_client

    url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    try:
        # Give up on a stuck request after 8 seconds instead of waiting for minutes
        from supabase.lib.client_options import ClientOptions

        options = ClientOptions(postgrest_client_timeout=8, storage_client_timeout=30)
        return create_client(url, key, options=options)
    except Exception:
        return create_client(url, key)


def get_client():
    """Reuses a connection while you're active, but starts a fresh one after
    20 idle seconds, because idle connections can quietly die."""
    import time

    holder = _client_holder()
    now = time.time()
    if holder["client"] is None or now - holder["last_used"] > 20:
        holder["client"] = _make_client()
    holder["last_used"] = now
    return holder["client"]


def run(action):
    """Runs a database or storage action. If it fails, retries once on a fresh connection."""
    try:
        return action(get_client())
    except Exception:
        _client_holder()["client"] = None
        return action(get_client())


try:
    get_client()
except Exception:
    st.error("The site is not connected to Supabase yet. "
             "Check SUPABASE_URL and SUPABASE_KEY in .streamlit/secrets.toml.")
    st.stop()


# ---------- Saving and loading ----------
def tidy(data):
    """Makes sure every topic has the lists we expect."""
    for units in data.values():
        for topics in units.values():
            for topic_data in topics.values():
                topic_data.setdefault("materials", [])
                topic_data["videos"] = [
                    {"title": "", "url": v} if isinstance(v, str) else v
                    for v in topic_data.get("videos", [])
                ]
                topic_data.pop("summary", None)
    return data


# Remembered for 5 minutes so pages load fast. Saving clears it right away.
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data():
    res = run(lambda c: c.table("site_data").select("content").eq("id", 1).execute())
    rows = res.data or []
    content = rows[0]["content"] if rows else {}
    if isinstance(content, str):
        content = json.loads(content)
    return content or {}


def load_data():
    try:
        return tidy(fetch_data())
    except Exception as e:
        st.error("Could not load the content from the database. Please try again in a moment.")
        st.code(str(e))
        st.stop()


def save_data(data):
    try:
        run(lambda c: c.table("site_data").upsert({"id": 1, "content": data}).execute())
    except Exception as e:
        st.error("Could not save to the database. Nothing was changed. Please try again.")
        st.code(str(e))
        st.stop()
    fetch_data.clear()


# A private link to a file, good for an hour. Remembered for 30 minutes.
@st.cache_data(ttl=1800, show_spinner=False)
def file_url(stored_name):
    res = run(lambda c: c.storage.from_(BUCKET).create_signed_url(stored_name, 3600))
    url = res.get("signedURL") or res.get("signedUrl")
    if not url:
        raise RuntimeError("No link returned")
    if url.startswith("/"):
        base = st.secrets["SUPABASE_URL"].rstrip("/")
        url = base + (url if url.startswith("/storage/v1") else "/storage/v1" + url)
    return url


def import_local_data():
    """One-time copy of the data.json and uploads folder from this computer."""
    with open(LOCAL_DATA_FILE, "r", encoding="utf-8") as f:
        local = tidy(json.load(f))

    for units in local.values():
        for topics in units.values():
            for topic_data in topics.values():
                kept = []
                for m in topic_data["materials"]:
                    path = os.path.join(UPLOAD_DIR, m["file"])
                    if not os.path.exists(path):
                        continue
                    with open(path, "rb") as f:
                        blob = f.read()
                    new_key = re.sub(r"[^A-Za-z0-9._-]", "_", m["file"])
                    run(lambda c: c.storage.from_(BUCKET).upload(new_key, blob))
                    m["file"] = new_key
                    m["size"] = len(blob)
                    kept.append(m)
                topic_data["materials"] = kept
    save_data(local)


# ---------- Admin login ----------
def get_admin_password():
    """Reads ADMIN_PASSWORD from the secrets. None means nobody can edit."""
    try:
        return str(st.secrets.get("ADMIN_PASSWORD", "")) or None
    except Exception:
        return None


def admin_panel():
    """Draws the login or logout box. Returns True only when the admin is logged in."""
    password = get_admin_password()
    if not password:
        return False  # no password set up: the site is read-only for everyone

    if st.session_state.get("is_admin"):
        st.sidebar.caption("Admin mode is on")
        if st.sidebar.button("Log out", key="admin_logout"):
            st.session_state["is_admin"] = False
            st.rerun()
        return True

    with st.sidebar.expander("Admin login"):
        with st.form("admin_login", clear_on_submit=True):
            entered = st.text_input("Password", type="password", key="admin_pw")
            ok = st.form_submit_button("Log in")
        if ok:
            if hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
    return False


# ---------- Helpers ----------
def add_form(label, key, existing):
    """A small form that clears itself. Returns the new name, or None."""
    with st.form(key, clear_on_submit=True):
        name = st.text_input(label, key=f"{key}_input")
        submitted = st.form_submit_button("Add")
    if submitted:
        name = name.strip()
        if not name:
            st.warning("Please type a name first.")
        elif name in existing:
            st.warning("That one already exists.")
        else:
            return name
    return None


def clean_youtube_url(text):
    """Returns a proper https link if it's a YouTube link, otherwise None."""
    text = text.strip()
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    host = (urlparse(text).hostname or "").lower()
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return text
    return None


def parse_links(text):
    """One link per line. A line can also be 'Title | link'."""
    good, bad = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        title = ""
        if "|" in line:
            title, line = [part.strip() for part in line.rsplit("|", 1)]
        url = clean_youtube_url(line)
        if url:
            good.append({"title": title, "url": url})
        else:
            bad.append(line)
    return good, bad


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


# ---------- Videos section ----------
# A fragment reruns by itself, so adding or removing something
# doesn't reload the whole page.
@st.fragment
def videos_section(subject, unit, topic, admin):
    prefix = f"{subject}|{unit}|{topic}"
    data = load_data()
    videos = data[subject][unit][topic]["videos"]

    with st.container(key="card_videos"):
        heading("Videos", "section")
        if not videos:
            st.caption("No videos yet.")

        for i, video in enumerate(videos):
            label = (video["title"] or f"Video {i + 1}").replace("[", "(").replace("]", ")")
            link_text = f"**{i + 1}.** [{label}]({video['url']})"
            if admin:
                col_link, col_del = st.columns([8, 2], vertical_alignment="center")
                col_link.markdown(link_text)
                if col_del.button("Remove", key=f"delv_{prefix}_{i}"):
                    videos.pop(i)
                    save_data(data)
                    st.rerun(scope="fragment")
            else:
                st.markdown(link_text)

        if not admin:
            return  # viewers stop here: no add form

        flash = st.session_state.pop("flash_videos", None)
        if flash:
            st.warning(flash)

        with st.form(f"form_video_{prefix}", clear_on_submit=True):
            text = st.text_area(
                "Add video links",
                key=f"text_{prefix}",
                height=110,
                placeholder="One link per line.\nOptional title: Limits intro | https://youtu.be/xxxx",
            )
            submitted = st.form_submit_button("Add")

        if submitted:
            new_videos, rejected = parse_links(text)
            known = {v["url"] for v in videos}
            fresh = []
            for v in new_videos:
                if v["url"] not in known:
                    known.add(v["url"])
                    fresh.append(v)

            messages = []
            if not new_videos and not rejected:
                messages.append("Paste at least one link first.")
            if rejected:
                messages.append("Not a YouTube link, skipped: " + ", ".join(rejected) + ".")
            if new_videos and not fresh:
                messages.append("Those links were already added.")

            if fresh:
                videos.extend(fresh)
                save_data(data)
            if messages:
                st.session_state["flash_videos"] = " ".join(messages)
            st.rerun(scope="fragment")


# ---------- Materials section ----------
@st.fragment
def materials_section(subject, unit, topic, admin):
    prefix = f"{subject}|{unit}|{topic}"
    data = load_data()
    materials = data[subject][unit][topic]["materials"]

    with st.container(key="card_materials"):
        heading("Materials", "section")
        if not materials:
            st.caption("No files yet.")

        for m in materials:
            if admin:
                col_name, col_open, col_del = st.columns([6, 2, 2], vertical_alignment="center")
            else:
                col_name, col_open = st.columns([8, 2], vertical_alignment="center")
                col_del = None

            col_name.markdown(m["name"])
            if m.get("size"):
                col_name.caption(human_size(m["size"]))
            try:
                col_open.link_button("Open", m.get("url") or file_url(m["file"]))
            except Exception:
                col_open.caption("Unavailable")

            if col_del is not None and col_del.button("Remove", key=f"delm_{m['file']}"):
                try:
                    run(lambda c: c.storage.from_(BUCKET).remove([m["file"]]))
                except Exception:
                    pass
                materials.remove(m)
                save_data(data)
                st.rerun(scope="fragment")

        if not admin:
            return  # viewers stop here: no upload form

        flash = st.session_state.pop("flash_files", None)
        if flash:
            st.warning(flash)

       material_type = st.radio("What do you want to add?", ["📁 Upload Files", "🔗 Add a Web Link"], key=f"type_{prefix}")

    if material_type == "📁 Upload Files":
        with st.form(f"form_files_{prefix}", clear_on_submit=True):
            files = st.file_uploader(
                "Add files (PDF, Word, PowerPoint, Excel, text, images)",
                accept_multiple_files=True,
                type=ALLOWED_TYPES,
                key=f"files_{prefix}"
            )
            submitted = st.form_submit_button("Upload")
            
            if submitted:
                if not files:
                    st.session_state["flash_files"] = "Choose at least one file first."
                    st.rerun(scope="fragment")
                else:
                    added, failed = 0, []
                    for upload in files:
                        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", upload.name)
                        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                        blob = upload.getvalue()
                        try:
                            run(lambda c: c.storage.from_(BUCKET).upload(stored_name, blob))
                        except Exception:
                            failed.append(upload.name)
                            continue
                        materials.append({"name": upload.name, "file": stored_name, "size": len(blob)})
                        added += 1
                    
                    if added:
                        save_data(data)
                    if failed:
                        st.session_state["flash_files"] = "Could not upload: " + ", ".join(failed) + ". Files over about 50 MB can be rejected on the free plan."
                    st.rerun(scope="fragment")

    else:
        with st.form(f"form_link_{prefix}", clear_on_submit=True):
            link_name = st.text_input("Title of the link (e.g., 'Unit 1 Notes Drive Link'):")
            link_url = st.text_input("Paste the URL here:")
            submitted_link = st.form_submit_button("Save Link")
            
            if submitted_link:
                if not link_name or not link_url:
                    st.session_state["flash_files"] = "Please provide both a title and a URL."
                else:
                    materials.append({"name": link_name, "url": link_url})
                    save_data(data)
                st.rerun(scope="fragment")
                   


# ---------- App ----------
data = load_data()

# If something was just added, jump to it. This must happen before the dropdowns are drawn.
for key, value in st.session_state.pop("jump", {}).items():
    st.session_state[key] = value

# Sidebar: brand, subjects, admin login
st.sidebar.markdown(
    '<div class="brand"><div class="brand-name">rescue-day</div>'
    '<div class="brand-tag">Your study material, organised</div></div>',
    unsafe_allow_html=True,
)

subject = None
if data:
    subject = st.sidebar.selectbox("Subject", list(data.keys()), key="subject")

admin = admin_panel()

if admin and not data and os.path.exists(LOCAL_DATA_FILE):
    with st.sidebar.expander("Import from this computer"):
        st.caption("Copies the subjects, links and files you already added into the online database.")
        if st.button("Import now", key="import_local"):
            with st.spinner("Importing..."):
                try:
                    import_local_data()
                except Exception as e:
                    st.error("Import failed.")
                    st.code(str(e))
                else:
                    st.rerun()

if admin:
    with st.sidebar.expander("Add a subject", expanded=not data):
        new_subject = add_form("Subject name", "form_subject", data)
        if new_subject:
            data[new_subject] = {}
            save_data(data)
            st.session_state["jump"] = {"subject": new_subject}
            st.rerun()

if not subject:
    heading("Welcome to rescue-day", "plain")
    if admin:
        st.write("Start by adding your first subject in the sidebar.")
    else:
        st.write("Nothing has been added yet. Please check back soon.")
    st.stop()

heading(subject, "subject")

# Step 1: units
units = data[subject]
unit = None
with st.container(key="card_units"):
    heading("Units", "unit")
    if units:
        unit = st.selectbox(
            "Unit", list(units.keys()), key=f"unit_{subject}", label_visibility="collapsed"
        )
    else:
        st.caption("No units yet.")
    if admin:
        with st.expander(f"Add a unit to {subject}", expanded=not units):
            new_unit = add_form("Unit name", f"form_unit_{subject}", units)
            if new_unit:
                units[new_unit] = {}
                save_data(data)
                st.session_state["jump"] = {f"unit_{subject}": new_unit}
                st.rerun()

if not unit:
    st.info("Add your first unit above to continue." if admin else "Nothing here yet. Please check back soon.")
    st.stop()

# Step 2: topics
topics = units[unit]
topic = None
with st.container(key="card_topics"):
    heading("Topics", "topic")
    if topics:
        topic = st.selectbox(
            "Topic", list(topics.keys()), key=f"topic_{subject}_{unit}", label_visibility="collapsed"
        )
    else:
        st.caption("No topics yet.")
    if admin:
        with st.expander(f"Add a topic to {unit}", expanded=not topics):
            new_topic = add_form("Topic name", f"form_topic_{subject}_{unit}", topics)
            if new_topic:
                topics[new_topic] = {"videos": [], "materials": []}
                save_data(data)
                st.session_state["jump"] = {f"topic_{subject}_{unit}": new_topic}
                st.rerun()

if not topic:
    st.info("Add your first topic above to continue." if admin else "Nothing here yet. Please check back soon.")
    st.stop()

# Step 3: content
st.divider()
heading(topic, "topic")
st.caption(f"{subject} > {unit}")

videos_section(subject, unit, topic, admin)
materials_section(subject, unit, topic, admin)