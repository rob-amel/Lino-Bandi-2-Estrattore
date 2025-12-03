import streamlit as st
import pandas as pd
import re
from datetime import datetime
from io import BytesIO 
from pypdf import PdfReader 
import json
import os

# --- LIBRERIA E SETUP GEMINI ---
# Per usare l'API, devi installare: pip install google-genai
from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- CONFIGURAZIONE E STILE ---

st.set_page_config(page_title="📋 Lino Estrattore AI (Gemini Free Tier)", layout="wide")

# --- RECUPERO CHIAVI API ---
# Questa sezione recupera la chiave API di Gemini dai secrets di Streamlit.
try:
    # Prova a prendere la chiave da Streamlit Secrets
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, Exception):
    # Se non è presente, usa la variabile d'ambiente (utile per testing locale)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "dummy_key") 
    st.warning("⚠️ Chiave GEMINI_API_KEY non trovata nei secrets. L'API potrebbe fallire.")


# --- FUNZIONE DI ESTrazione AI (CORE DEL BOT) ---

def estrai_dettagli_con_gemini(testo_bando, file_name):
    """
    Analizza il testo grezzo di un bando usando Gemini 2.5 Flash per estrarre
    informazioni strutturate in formato JSON.
    """
    
    # 1. Configurazione del Cliente Gemini
    try:
        # Client si auto-autentica con la chiave in GEMINI_API_KEY
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        # Questo avviene se la chiave è vuota o non valida
        st.error("Errore di configurazione API Gemini: verifica la chiave in secrets.toml.")
        return None

    # 2. Schema JSON Desiderato (Output)
    # Definiamo la struttura JSON che vogliamo che Gemini segua
    output_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "Categoria": types.Schema(type=types.Type.STRING, description="Una categoria generale (es. Sociale, Ambientale, Culturale)"),
            "Titolo bando": types.Schema(type=types.Type.STRING, description=f"Titolo principale del bando (stimato da {file_name})"),
            "Donatore": types.Schema(type=types.Type.STRING, description="Nome dell'ente erogatore (es. Fondazione Cariplo, Commissione Europea)"),
            "Totale finanziamento": types.Schema(type=types.Type.STRING, description="Budget totale del bando, se specificato (con valuta)"),
            "Importo max per proposta": types.Schema(type=types.Type.STRING, description="Importo massimo richiedibile per singolo progetto (con valuta)"),
            "Co-finanziamento previsto": types.Schema(type=types.Type.STRING, description="Sintesi del requisito di co-finanziamento (es. Sì, 10% cash, No)"),
            "Durata min/max progetti": types.Schema(type=types.Type.STRING, description="Durata ammissibile dei progetti (es. 12-36 mesi)"),
            "Area di implementazione": types.Schema(type=types.Type.STRING, description="Area geografica di interesse (es. Italia, Regione Puglia, Global)"),
            "Deadline presentazione proposta": types.Schema(type=types.Type.STRING, description="Data e ora di scadenza (formato leggibile)"),
            "Consorzio/ATS/partenariato": types.Schema(type=types.Type.STRING, description="Sintesi del requisito di partenariato (es. Obbligatorio, Ammesso, Non richiesto)"),
            "Obiettivi bando / proposte": types.Schema(type=types.Type.STRING, description="Sintesi concisa degli obiettivi che il bando si propone di raggiungere"),
            "Settori target": types.Schema(type=types.Type.STRING, description="Elenco di settori o temi specifici (es. Clima, Inclusione sociale, Educazione)"),
            "Attività previste (if any)": types.Schema(type=types.Type.STRING, description="Sintesi delle principali attività ammissibili (es. Formazione, Costruzione, Ricerca)"),
            "Gruppi target": types.Schema(type=types.Type.STRING, description="A chi sono rivolte le azioni (es. Giovani, Donne, Piccole Imprese)"),
            "Tematiche trasversali": types.Schema(type=types.Type.STRING, description="Temi orizzontali (es. Sostenibilità, Parità di genere)"),
            "Criteri di eleggibilità": types.Schema(type=types.Type.STRING, description="Sintesi dei requisiti chiave del proponente (es. Registrazione in loco, Esperienza specifica)"),
            "Documentazione richiesta": types.Schema(type=types.Type.STRING, description="Elenco conciso dei documenti richiesti per la presentazione"),
            "Criteri di valutazione": types.Schema(type=types.Type.STRING, description="Sintesi dei principali criteri di punteggio")
        },
        required=["Titolo bando", "Deadline presentazione proposta", "Donatore", "Obiettivi bando / proposte"]
    )
    
    # 3. Istruzioni (Prompt) per Gemini
    prompt_istruzioni = f"""
    Sei un analista esperto di bandi e devi estrarre le informazioni chiave dal seguente documento.
    Il nome del file di origine è: {file_name}.
    
    Analizza il testo qui sotto e compila tutti i campi dello schema JSON fornito.
    Se un campo non è presente nel testo, usa il valore 'NA'.
    Sintetizza in modo conciso tutti i campi testuali, in italiano.

    TESTO DEL BANDO:
    ---
    {testo_bando[:32000]} 
    ---
    """
    # Limita l'input a ~32k caratteri per sicurezza, anche se Gemini Flash supporta di più.

    # 4. Chiamata all'API
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Veloce ed efficiente per l'estrazione dati (Gratuito)
            contents=prompt_istruzioni,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=output_schema,
            ),
        )

        # Il testo di risposta è una stringa JSON
        json_string = response.text.strip()
        
        # Pulizia: a volte il modello aggiunge Markdown (```json)
        if json_string.startswith("```json"):
            json_string = json_string[7:]
        if json_string.endswith("```"):
            json_string = json_string[:-3]
            
        risultati = json.loads(json_string)
        return risultati

    except APIError as e:
        st.error(f"Errore API Gemini: La chiamata è fallita. Causa: {e}")
        st.warning("Potresti aver esaurito la quota gratuita, la tua chiave API potrebbe non essere valida, o l'input è troppo lungo.")
        return None
    except json.JSONDecodeError:
        st.error("Errore: Gemini non ha restituito un JSON valido. Riprova.")
        return None


# --- FUNZIONE PER ESTRARRE TESTO DAL PDF (NON MODIFICATA) ---

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

# --- LOGO E TITOLO ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        st.image("logo_amelia.png", width=80) 
    except FileNotFoundError:
        st.markdown(" ") # Placeholder per mantenere l'allineamento
with col_title:
    st.title("📋 Lino Estrattore AI (Powered by Gemini)")

st.markdown("""
Questa applicazione utilizza l'AI di **Gemini 2.5 Flash** per un'estrazione dati estremamente accurata dai PDF. 
L'uso rientra nel piano gratuito (Free Tier) per un utilizzo normale.
""")
st.markdown("---")

# 1. Configurazione della Sessione (omessa per brevità, si usa la stessa logica precedente)

# Inizializzazione della session_state (essenziale per il deploy)
if 'uploaded_pdfs' not in st.session_state:
    st.session_state['uploaded_pdfs'] = []
    
if 'filename_output' not in st.session_state:
    st.session_state['filename_output'] = f'Sintesi_Bandi_AI_{datetime.now().strftime("%Y%m%d")}'

# 2. Form per Upload e Aggiunta (omessa per brevità)
with st.form("pdf_upload_form"):
    
    st.subheader("Aggiungi i File PDF per l'Analisi (Max 5)")
    uploaded_file = st.file_uploader(
        "Carica un file PDF:", 
        type="pdf", 
        accept_multiple_files=False,
        disabled=(len(st.session_state['uploaded_pdfs']) >= 5)
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        add_button = st.form_submit_button("➕ Aggiungi File all'Analisi")
    with col2:
        clear_button = st.form_submit_button("❌ Rimuovi TUTTI i File")

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
    
    for i, file_info in enumerate(st.session_state['uploaded_pdfs']):
        file_name = file_info['name']
        file_bytes = file_info['data']
        
        progress_text = f"Analisi file {i + 1} di {len(st.session_state['uploaded_pdfs'])}: **{file_name}**"
        progress_bar.progress((i + 1) / len(st.session_state['uploaded_pdfs']), text=progress_text)
        
        pdf_stream = BytesIO(file_bytes)
        final_text = estrai_testo_da_pdf(pdf_stream)
        
        if final_text:
            # 1. CHIAMATA A GEMINI
            risultati_bando = estrai_dettagli_con_gemini(final_text, file_name)
            
            if risultati_bando:
                 risultati_finali.append(risultati_bando)
            else:
                 # Gestione fallimento API
                 st.warning(f"⚠️ Estrazione AI fallita per {file_name}. Record saltato.")
            
        else:
            st.warning(f"⚠️ Estrazione testo fallita per {file_name}. Record ignorato.")
            
    progress_bar.empty()
    
    if risultati_finali:
        # Converti in DataFrame e gestisci gli NA come valori vuoti per l'Excel
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
