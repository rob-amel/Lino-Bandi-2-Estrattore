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

# L'impostazione "centered" qui è cruciale per i contenuti principali, ma non per il logo
st.set_page_config(page_title="📋 Lino Estrattore AI (Gemini)", layout="centered")

# --- RECUPERO CHIAVI API (come prima) ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, Exception):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "dummy_key") 
    st.warning("⚠️ Chiave GEMINI_API_KEY non trovata nei secrets. L'API potrebbe fallire.")


# --- FUNZIONE DI ESTRAZIONE AI (estrai_dettagli_con_gemini) (omessa per brevità, resta IDENTICA) ---
# ... (Inserisci qui la funzione estrai_dettagli_con_gemini completa) ...

# --------------------------------------------------------------------------------------
# ---------------------------------- INIZIO DEL CODICE ---------------------------------
# --------------------------------------------------------------------------------------

# --- FUNZIONE PER ESTRARRE TESTO DAL PDF (omessa per brevità) ---
def estrai_testo_da_pdf(pdf_file_obj):
    """Estrae il testo da tutte le pagine di un oggetto file PDF caricato."""
    try:
        reader = PdfReader(pdf_file_obj)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"❌ Errore durante la lettura del PDF: {type(e).__name__}. Il file potrebbe essere protetto o corrotto.")
        return None

# --- INTERFACCIA STREAMLIT (Frontend) ---

# --- LOGO E TITOLO CENTRATI ---
# Creiamo due colonne per l'allineamento. Lo slot centrale (vuoto) simula la centralità.
col_left, col_logo, col_title, col_right = st.columns([1, 1, 4, 1])

with col_logo:
    try:
        # Immagine di piccole dimensioni
        st.image("logo_amel.png", width=70) 
    except FileNotFoundError:
        pass

with col_title:
    # Ridotto a subheader per un look più pulito, o lasciato titolo se preferisci
    st.header("Lino Estrattore AI")

st.markdown("---")

# Spiegazione e Promemoria (Centrato e compatto)
st.markdown("""
<div style='text-align: center;'>
    Questa applicazione utilizza l'AI di **Gemini 2.5 Flash** per un'estrazione dati estremamente accurata dai PDF.<br>
    L'uso rientra nel piano gratuito (Free Tier) per un utilizzo normale.
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# 1. Configurazione della Sessione
if 'uploaded_pdfs' not in st.session_state:
    st.session_state['uploaded_pdfs'] = []
if 'filename_output' not in st.session_state:
    st.session_state['filename_output'] = f'Sintesi_Bandi_AI_{datetime.now().strftime("%Y%m%d")}'

# 2. Form per Upload e Aggiunta
# Usiamo un container per limitare la larghezza del form (solo testo, non codice)
with st.container(border=True):
    st.subheader("Aggiungi i File PDF per l'Analisi (Max 5)")
    
    # ... (Il resto del codice del form di upload e clear) ...
    uploaded_file = st.file_uploader(
        "Carica un file PDF:", 
        type="pdf", 
        accept_multiple_files=False,
        disabled=(len(st.session_state['uploaded_pdfs']) >= 5)
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        add_button = st.button("➕ Aggiungi File all'Analisi", key="add_btn") # Modificato in st.button fuori dal form per chiarezza
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
    
    # ... (Il resto della logica di estrazione e download, come prima) ...
    if not st.session_state['uploaded_pdfs']:
        st.error("Carica almeno un file PDF per procedere.")
        st.stop()
        
    risultati_finali = []
    
    progress_bar = st.progress(0, text=f"Analisi di {len(st.session_state['uploaded_pdfs'])} file PDF in corso (Chiamata API Gemini)...")
    
    for i, file_info in enumerate(st.session_state['uploaded_pdfs']):
        file_name = file_info['name']
        file_bytes = file_info['data']
        
        progress_text = f"Analisi file {i + 1} di {len(st.session_state['uploaded_pdfs'])}: **{file_name}**"
        progress_bar.progress((i + 1) / len(st.session_state['uploaded_pdfs']), text=progress_text)
        
        pdf_stream = BytesIO(file_bytes)
        final_text = estrai_testo_da_pdf(pdf_stream)
        
        if final_text:
            risultati_bando = estrai_dettagli_con_gemini(final_text, file_name)
            
            if risultati_bando:
                 risultati_finali.append(risultati_bando)
            else:
                 st.warning(f"⚠️ Estrazione AI fallita per {file_name}. Record saltato.")
            
        else:
            st.warning(f"⚠️ Estrazione testo fallita per {file_name}. Record ignorato.")
            
    progress_bar.empty()
    
    if risultati_finali:
        df_final = pd.DataFrame(risultati_finali).replace('NA', '', regex=True)
        
        st.success(f"✅ Analisi completata per {len(risultati_finali)} bandi con AI.")
        st.dataframe(df_final, use_container_width=True)
        
        # Logica di Download
        output = BytesIO()
        df_final.to_excel(output, index=False, engine='xlsxwriter') 
        excel_data = output.getvalue() 
        
        nome_file_finale = f'{st.session_state.filename_output_key.replace(" ", "_")}.xlsx' 

        st.download_button(
            label="Scarica il Report Sintetico (Excel)",
            data=excel_data, 
            file_name=nome_file_finale,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        st.error("⚠️ Nessun dato è stato estratto con successo.")

