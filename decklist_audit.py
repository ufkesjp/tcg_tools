import streamlit as st
import requests
import re
import time 

# --- Configuration ---
st.set_page_config(page_title="EDHREC Deck Auditor", layout="wide", page_icon="🎴")

# --- Helper Functions ---
@st.cache_data(show_spinner=False, ttl=3600)
def get_scryfall_data(card_name):
    """Fetches card art and price from Scryfall with rate limiting."""
    time.sleep(0.1) 
    url = f"https://api.scryfall.com/cards/named?fuzzy={card_name}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Extract Image
            if 'image_uris' in data:
                img = data['image_uris']['normal']
            elif 'card_faces' in data:
                img = data['card_faces'][0]['image_uris']['normal']
            else:
                img = "https://errors.scryfall.com/unknown.jpg"
            
            # Extract Price
            price = data.get('prices', {}).get('usd')
            price_str = f"${price}" if price else "Price N/A"
            
            return {"img": img, "price": price_str}
        return {"img": "https://errors.scryfall.com/unknown.jpg", "price": "N/A"}
    except:
        return {"img": "https://errors.scryfall.com/unknown.jpg", "price": "Error"}

def get_edhrec_data(commander_name):
    name = re.sub(r'[^a-z0-9\s-]', '', commander_name.lower()).replace(" ", "-")
    url = f"https://json.edhrec.com/pages/commanders/{name}.json"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def clean_card_name(line):
    line = re.sub(r'^\d+x?\s+', '', line).strip()
    return re.sub(r'\s*\([^)]*\).*$', '', line).strip()

def display_card_grid(card_list, cols=4, progress_label="Loading cards..."):
    if not card_list:
        st.write("No cards to display.")
        return
    
    total_cards = len(card_list)
    progress_bar = st.progress(0, text=progress_label)
    
    for i in range(0, total_cards, cols):
        row = card_list[i : i + cols]
        st_cols = st.columns(cols)
        for idx, card_name in enumerate(row):
            card_info = get_scryfall_data(card_name)
            with st_cols[idx]:
                st.image(card_info["img"], use_container_width=True)
                st.caption(f"**{card_name}**")
                st.write(f"Price: {card_info['price']}")
        
        percent_complete = min((i + cols) / total_cards, 1.0)
        progress_bar.progress(percent_complete, text=progress_label)
    
    progress_bar.empty()

# --- Sidebar (Cleaned) ---
with st.sidebar:
    st.header("📋 Deck Input")
    commander = st.text_input("Commander Name", placeholder="e.g. Atraxa, Praetors' Voice")
    decklist_raw = st.text_area("Cards in the 99", height=500)
    
    user_deck = [clean_card_name(l) for l in decklist_raw.split('\n') if l.strip()]

# --- Main App ---
if not commander or not user_deck:
    st.title("🎴 Commander Deck Auditor")
    st.info("Please enter your Commander and Decklist in the sidebar to begin.")
else:
    with st.spinner(f"Fetching EDHREC data..."):
        data = get_edhrec_data(commander)

    if not data:
        st.error(f"Commander '{commander}' not found.")
    else:
        cardlists = data.get('container', {}).get('json_dict', {}).get('cardlists', [])
        edhrec_names = {c['name'] for cl in cardlists for c in cl.get('cardviews', [])}
        
        tab1, tab2 = st.tabs(["💎 Suggestions for Your Deck", "🖼️ Uniqueness of Brew"])

        with tab1:
            st.header(f"Recommendations for {commander} from EDHREC")
            target_cats = [
                "New Cards", "High Synergy Cards", "Top Cards", "Game Changes", "Creatures", 
                "Instants", "Sorceries", "Utility Artifacts", "Enchantments", 
                "Battles", "Planeswalkers", "Utility Lands", "Artifacts", "Lands"
            ]
            all_missing = []
            
            for cl in cardlists:
                header = cl.get('header', '')
                if header in target_cats:
                    missing = [c['name'] for c in cl.get('cardviews', []) if c['name'] not in user_deck]
                    if missing:
                        all_missing.extend(missing)
                        with st.expander(f"Missing {header} ({len(missing)})"):
                            if st.toggle(f"View Visuals for {header}", key=f"tg_{header}"):
                                display_card_grid(missing, cols=4, progress_label=f"Fetching {header}...")
                            else:
                                for m in missing:
                                    st.write(f"➕ {m}")
            
            if all_missing:
                st.divider()
                export_text = "\n".join([f"1 {x}" for x in set(all_missing)])
                st.download_button("Download Missing Cards (.txt)", export_text, file_name="missing.txt")

        with tab2:
            st.header("Visual Deck Audit")
            matches = sorted([c for c in user_deck if c in edhrec_names])
            unique = sorted([c for c in user_deck if c not in edhrec_names])
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Match Score", f"{(len(matches)/len(user_deck))*100:.1f}%")
            m2.metric("Staples Found", len(matches))
            m3.metric("Unique Picks", len(unique))
            
            st.divider()
            with st.expander("✅ Cards Matching EDHREC Recommendations", expanded=True):
                display_card_grid(matches, progress_label="Loading your staples...")
            
            with st.expander("🧪 Your Unique Picks", expanded=True):
                st.info("These card choices make your deck unique! They are not included in the EDHREC page for this commander.")
                display_card_grid(unique, progress_label="Loading your unique picks...")
