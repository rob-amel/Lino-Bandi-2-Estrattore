import streamlit as st
import pandas as pd
import re
from datetime import datetime
from io import BytesIO 
from pypdf import PdfReader 
import json
import os
from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- CONFIGURAZIONE E STILE ---

# Manteniamo "centered" per la maggior parte dei contenuti.
st.set_page_config(page_title="📋 Lino Estrattore AI (Gemini)", layout="centered")

# --- RECUPERO CHIAVI API (come prima) ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, Exception):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "dummy_key") 
    st.warning("⚠️ Chiave GEMINI_API_KEY non trovata nei secrets. L'API potrebbe fallire.")


# --- FUNZIONE DI ESTRAZIONE AI (estrai_dettagli_con_gemini) (omessa per brevità) ---
# ... (Inserisci qui la funzione estrai_dettagli_con_gemini completa) ...

# --- FUNZIONE PER ESTRARE TESTO DAL PDF (omessa per brevità) ---
def estrai_testo_da_pdf(pdf_file_obj):
    """Estrae il testo da tutte le pagine di un oggetto file PDF caricato."""
    try:
        reader = PdfReader(pdf_file_obj)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        # Aggiungo un f-string per mantenere il codice pulito se l'utente ha solo il corpo della funzione.
        pass # In un'applicazione completa ci sarebbe la gestione errore

# --- INTERFACCIA STREAMLIT (Frontend) ---

# --- LOGO E TITOLO ALLINEATI A SINISTRA ---

# Usiamo 2 colonne: 1 per il logo, 4 per il titolo.
col_logo, col_title = st.columns([1.5, 5]) 

with col_logo:
    try:
        # Logo più grande
        st.image("logo_amel.png", width=100) 
    except FileNotFoundError:
        pass

with col_title:
    # Titolo con emoji
    st.title("📋 Lino Bandi 2 - L'Estrattore")

st.markdown("---")

# --- NUOVA INTRODUZIONE FORMATTATA ESATTAMENTE COME RICHIESTO ---
st.markdown("""
**Ciao! Lino Bandi ti da nuovamente il benvenuto e vuole aiutarti a 
fare una rapida sintesi dei bandi che hai trovato!**

Caricane massimo 5 in PDF e scarica il file! Troverai tutte le info 
necessarie per capire di che si tratta e decidere i prossimi passi.
""")

# Sottolineatura importante sull'AI
st.info("""
L'applicazione si appoggia sul sistema **Gemini AI Flash 2.5** e 
pertanto può commettere errori.
""")
st.markdown("---")


# 1. Configurazione della Sessione
if 'uploaded_pdfs' not in st.session_state:
    st.session_state['uploaded_pdfs'] = []
if 'filename_output' not in st.session_state:
    st.session_state['filename_output'] = f'Sintesi_Bandi_AI_{datetime.now().strftime("%Y%m%d")}'

# 2. Form per Upload e Aggiunta
# Il resto dell'app mantiene la centratura e il layout compatto
with st.container(border=True):
    st.subheader("Aggiungi i File PDF per l'Analisi (Max 5)")
    
    uploaded_file = st.file_uploader(
        "Carica un file PDF:", 
        type="pdf", 
        accept_multiple_files=False,
        disabled=(len(st.session_state['uploaded_pdfs']) >= 5)
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        add_button = st.button("➕ Aggiungi File all'Analisi", key="add_btn") 
    with col2:
        clear_button = st.button("❌ Rimuovi TUTTI i File", key="clear_btn")

    if add_button and uploaded_file is not None:
        if len(st.session_state['uploaded_pdfs']) < 5:
            file_info = {'name': uploaded_file.name, 'data': uploaded_file.getvalue()}
            st.session_state['uploaded_pdfs'].append(file_info)
            st.success(f"File aggiunto: **{uploaded_file.name}**. Totale: **{len(st.session_state['uploaded_pdfs'])}**.")
        else:
            st.warning("Hai raggiunto il limite massimo di 5 PDF.")
        st.rerun() 

    if clear_button:
        st.session_state['uploaded_pdfs'] = []
        st.info("Lista file svuotata.")
        st.rerun()

# 3. Stato attuale dei file in coda
st.subheader(f"File in Coda: {len(st.session_state['uploaded_pdfs'])}/5")
if st.session_state['uploaded_pdfs']:
    file_names = [f['name'] for f in st.session_state['uploaded_pdfs']]
    st.markdown("* " + "\n* ".join(file_names))
else:
    st.info("Nessun file PDF caricato.")
    
st.markdown("---")

# 4. Esecuzione e Download
filename_input = st.text_input(
    "Dai un nome al tuo file Excel di output:", 
    value=st.session_state.get('filename_output', f'Sintesi_Bandi_AI_{datetime.now().strftime("%Y%m%d")}'),
    key='filename_output_key' 
)

if st.button("▶️ ESTRAI e GENERA REPORT EXCEL con AI", type="primary", disabled=(len(st.session_state['uploaded_pdfs']) == 0)):
    
    if not st.session_state['uploaded_pdfs']:
        st.error("Carica almeno un file PDF per procedere.")
        st.stop()
        
    risultati_finali = []
    
    progress_bar = st.progress(0, text=f"Analisi di {len(st.session_state['uploaded_pdfs'])} file PDF in corso (Chiamata API Gemini)...")
    
    # ... (il resto della logica di estrazione e download, come prima) ...
    # (Per un codice completo e funzionante, qui dovrebbe essere inserita la logica completa di estrazione)
    
    progress_bar.empty()
    
    if risultati_finali:
        # Questa parte è solo dimostrativa, assicurati di avere la logica di estrazione completa inserita sopra.
        st.success(f"✅ Analisi completata per {len(risultati_finali)} bandi con AI.")
        # ... download logic ...
    else:
        st.error("⚠️ Nessun dato è stato estratto con successo.")
