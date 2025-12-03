import streamlit as st
import pandas as pd
import re
from datetime import datetime
from io import BytesIO 
from pypdf import PdfReader 
import numpy as np # Importiamo numpy per gestire NaN

# --- CONFIGURAZIONE E STILE ---

st.set_page_config(page_title="📋 Lino Bandi 2 - L'Estrattore", layout="centered")

# --- FUNZIONE DI ANALISI DEL TESTO AVANZATA (CORE DEL BOT) ---

def estrai_dettagli_da_testo_grezzo(testo_bando, file_name):
    """
    Analizza il testo grezzo di un bando usando espressioni regolari e liste di parole chiave
    per estrarre informazioni strutturate.
    """
    
    # Inizializzazione del dizionario dei risultati con campi ordinati
    risultati = {
        "Categoria": "NA",
        "Titolo bando": file_name.replace(".pdf", "").replace("_", " ").title(),
        "Donatore": "NA",
        "Totale finanziamento": "NA",
        "Importo max per proposta": "NA",
        "Co-finanziamento previsto": "NA",
        "Durata min/max progetti": "NA",
        "Area di implementazione": "NA",
        "Deadline presentazione proposta": "NA",
        "Consorzio/ATS/partenariato": "NA",
        "Obiettivi bando / proposte": "NA",
        "Settori target": "NA",
        "Attività previste (if any)": "NA",
        "Gruppi target": "NA",
        "Tematiche trasversali": "NA",
        "Criteri di eleggibilità": "NA",
        "Documentazione richiesta": "NA",
        "Criteri di valutazione": "NA"
    }
    
    text = testo_bando.lower()
    
    # ----------------------------------------------------
    # 1. ESTRAZIONE DATI NUMERICI E TEMPORALI (REGULAR EXPRESSIONS)
    # ----------------------------------------------------
    
    # -- Deadline -- (Più robusta: cerca anche "entro il" o "data limite")
    mesi_it_en = r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|september|october|november|december)'
    date_pattern = rf'(scadenza|deadline|termine|chiusura|data limite|entro il)[:\s]*(.*?)(\d{{1,2}}[\/\-\.]\d{{1,2}}[\/\-\.]\d{{2,4}}|\d{{1,2}}\s{mesi_it_en}\s\d{{2,4}}|\d{{4}}[\-\/]\d{{1,2}}[\-\/]\d{{1,2}})'
    date_matches = re.search(date_pattern, text, re.IGNORECASE)
    if date_matches:
        # Prende il gruppo di cattura 3 (la data pulita)
        risultati["Deadline presentazione proposta"] = date_matches.group(3).strip() 

    # -- Importo Max per Proposta / Totale Finanziamento --
    
    # Pattern: cerca numeri con separatori (., o ,) seguiti da valuta.
    amount_pattern = r'(\$|€|euro|EUR|CHF|GBP)\s*(\d{{1,3}}[,\.]\d{{3}}(?:[,\.]\d{{3}})*(?:[,\.]\d{{1,2}})?|\d{{1,3}}(?:[,\.]\d{{3}})*(?:[,\.]\d{{1,2}})?)\s*(milioni)?'
    amount_matches = re.findall(amount_pattern, text, re.IGNORECASE)

    if amount_matches:
        # La logica per distinguere Totale e Max è euristica. Usiamo il primo trovato per Max e il secondo per Totale.
        
        # Funzione helper per formattare il valore
        def format_amount(match_tuple):
            currency = match_tuple[0]
            value = match_tuple[1].replace('.', 'XXX').replace(',', '.').replace('XXX', ',') # Inverte separatori IT/EN per uniformità
            milioni = match_tuple[2]
            return f"{currency} {value}{' Milioni' if milioni else ''}"

        if len(amount_matches) >= 1:
            risultati["Importo max per proposta"] = format_amount(amount_matches[0])
        
        if len(amount_matches) >= 2:
             risultati["Totale finanziamento"] = format_amount(amount_matches[1])

    # -- Durata --
    durata_pattern = r'(durata (del progetto)?|periodo di attuazione)[:\s]*(\d{1,2}[\s\-\/]\d{1,2}|fino a \d{1,2}|massimo \d{1,2})\s*(mesi|anni)'
    durata_matches = re.search(durata_pattern, text, re.IGNORECASE)
    if durata_matches:
        risultati["Durata min/max progetti"] = durata_matches.group(3).strip() + " " + durata_matches.group(4)
        
    # ----------------------------------------------------
    # 2. ESTRAZIONE BASATA SU PAROLE CHIAVE (BOOSTER DI PRECISIONE)
    # ----------------------------------------------------

    # Liste dei donatori più comuni (euristica estesa)
    KEY_DONATORI = ['european union', 'commissione europea', 'fondazione cariplo', 'fondazione crt', 'fondazione cdp', 'unhcr', 'unicef', 'usaid', 'aics', 'ministero degli affari esteri', 'onu', 'undp', 'unep', 'fondazione con il sud', 'bandi inps']
    
    # Co-finanziamento e Partenariato
    if any(k in text for k in ['co-finanziamento', 'cofinanziamento', 'co-funding', 'matched funding', 'own contribution']):
        risultati["Co-finanziamento previsto"] = "Sì (Cercare % e Tipo)"
    
    if any(k in text for k in ['consorzio', 'ats', 'associazione temporanea di scopo', 'partenariato', 'partnership', 'joint application', 'rete di soggetti']):
        risultati["Consorzio/ATS/partenariato"] = "Obbligatorio/Ammesso (Cercare dettagli)"

    # Area Geografica (più specifica)
    KEY_GEOGRAFIA = ['regione puglia', 'lombardia', 'veneto', 'campania', 'sicilia', 'italia', 'ue', 'europa', 'global', 'nazionale', 'africa', 'balcani', 'asia']
    found_geografia = set(key.capitalize() for key in KEY_GEOGRAFIA if key in text)
    if found_geografia:
        risultati["Area di implementazione"] = "; ".join(found_geografia)
        
    # Donatore (più robusta: cerca Donatore, non solo nel testo, ma anche come titolo)
    found_donatori = set()
    for key in KEY_DONATORI:
        if key in text:
            # Aggiunge il donatore solo se non è una keyword generica come 'ministero'
            if len(key.split()) > 1 or 'fondazione' in key:
                 found_donatori.add(key.title())
    if found_donatori:
        risultati["Donatore"] = "; ".join(found_donatori)
        
    # ----------------------------------------------------
    # 3. ESTRAZIONE TESTO CONTESTUALE (Migliorata con Delimitatori robusti)
    # ----------------------------------------------------
    
    TITLES_END = ['criteri', 'documentazione', 'obiettivi', 'settori', 'attività', 'gruppi target', 'tematiche trasversali', 'contatto', 'scadenza', 'deadline', 'ammontare', 'importo', 'capitolo']

    def extract_section(title_list, max_chars=400):
        """Estrae testo tra un titolo di sezione e l'inizio del successivo."""
        
        # Pattern di fine: cerca un numero/lettera/romano con punto, oppure una delle parole chiave TITLES_END
        end_pattern_keywords = '|'.join(TITLES_END)
        # Cerca: \n [Opzionale Spazi] [Numero/Lettera/Romano/Doppio Punto] [Punto] [Spazio] OPPURE una delle Keyword TITLES_END
        end_pattern = rf'(?:\n\s*(?:\d+|[A-Z]|\d+\.\d+|[IVXLCDM]+)\.|\n\s*(?:{end_pattern_keywords}))'
        
        for title in title_list:
            # Pattern: (Titolo richiesto) seguito da (caratteri in modo non avido) fino a (un delimitatore di fine)
            pattern = re.escape(title) + r'[:\s]*(.*?)' + end_pattern
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            
            if match:
                extracted_text = match.group(1).strip()
                # Pulizia grossolana
                extracted_text = re.sub(r'\s+', ' ', extracted_text) 
                extracted_text = re.sub(r'^- ', '', extracted_text).strip()
                
                return extracted_text[:max_chars].strip() + ("..." if len(extracted_text) > max_chars else "")
        return "NA"

    # Nuove euristiche migliorate per i campi
    risultati["Obiettivi bando / proposte"] = extract_section(['Obiettivi del Bando', 'Finalità', 'Scope', 'Goals', 'Priorità tematiche', 'Cosa finanzia', 'oggetto del bando'])
    risultati["Criteri di eleggibilità"] = extract_section(['Criteri di eleggibilità', 'Eligibility Criteria', 'Chi può partecipare', 'Requisiti dei proponenti', 'beneficiari ammissibili', 'soggetti ammissibili'])
    risultati["Documentazione richiesta"] = extract_section(['Documentazione richiesta', 'Documenti da allegare', 'Required Documents', 'Modalità di presentazione', 'Annex', 'Allegati'])
    risultati["Criteri di valutazione"] = extract_section(['Criteri di valutazione', 'Evaluation Criteria', 'Punteggio massimo', 'Metodologia di selezione', 'Selezione delle proposte'])
    risultati["Attività previste (if any)"] = extract_section(['Attività previste', 'Actions', 'Azioni ammissibili', 'Attività ammissibili', 'spese ammissibili'])
    risultati["Tematiche trasversali"] = extract_section(['Tematiche trasversali', 'Cross-cutting themes', 'Approccio di genere', 'Parità', 'Sostenibilità ambientale'])
    risultati["Gruppi target"] = extract_section(['Gruppi target', 'Destinatari', 'Beneficiari diretti', 'popolazione di riferimento'])
    
    # Estrazione settori target (parole chiave raggruppate)
    KEY_SETTORI = ['clima', 'ambiente', 'biodiversità', 'inclusione', 'sociale', 'cultura', 'migrazione', 'salute', 'energia rinnovabile', 'agricoltura', 'sviluppo rurale', 'educazione']
    found_settori = set(key.capitalize() for key in KEY_SETTORI if key in text)
    if found_settori:
        risultati["Settori target"] = "; ".join(found_settori)
        
    # Assegna una Categoria generale
    if 'ambiente' in text or 'clima' in text:
        risultati["Categoria"] = "Ambientale/Clima"
    elif 'sociale' in text or 'inclusione' in text or 'povertà' in text:
        risultati["Categoria"] = "Sociale/Inclusione"
    elif 'cultura' in text or 'arte' in text:
        risultati["Categoria"] = "Culturale/Educazione"
    
    return risultati

# --- FUNZIONE PER ESTRARRE TESTO DAL PDF ---

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
try:
    st.image("logo_amel.png", width=200) 
except FileNotFoundError:
    st.warning("⚠️ Logo 'logo_amel.png' non trovato. Assicurati che sia nella cartella principale.")

st.title("📋 Lino Bandi 2 - L'Estrattore")
st.markdown("---")

st.markdown("""
Questa applicazione analizza il contenuto di **file PDF** o testo incollato e ne estrae le informazioni chiave in un report Excel.
Le funzioni di estrazione sono basate su **regole di testo avanzate** per massimizzare la precisione, ma l'accuratezza dipende dalla formattazione del bando.
""")
st.markdown("---")

# 1. Configurazione della Sessione
if 'uploaded_pdfs' not in st.session_state:
    st.session_state['uploaded_pdfs'] = []
    
if 'filename_output' not in st.session_state:
    st.session_state['filename_output'] = f'Sintesi_Bandi_{datetime.now().strftime("%Y%m%d")}'

# 2. Form per Upload e Aggiunta
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

    # Logica di aggiunta
    if add_button and uploaded_file is not None:
        if len(st.session_state['uploaded_pdfs']) < 5:
            # Salviamo il nome e i bytes per l'analisi successiva
            file_info = {
                'name': uploaded_file.name,
                'data': uploaded_file.getvalue()
            }
            st.session_state['uploaded_pdfs'].append(file_info)
            st.success(f"File aggiunto: **{uploaded_file.name}**. Totale: **{len(st.session_state['uploaded_pdfs'])}**.")
        else:
            st.warning("Hai raggiunto il limite massimo di 5 PDF.")
        st.rerun() 

    # Logica di pulizia
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
    st.info("Nessun file PDF caricato. Carica i file e clicca 'Aggiungi File all'Analisi'.")
    
st.markdown("---")

# 4. Esecuzione e Download
filename_input = st.text_input(
    "Dai un nome al tuo file Excel di output:", 
    value=st.session_state.get('filename_output', f'Sintesi_Bandi_{datetime.now().strftime("%Y%m%d")}'),
    key='filename_output_key' 
)

if st.button("▶️ ESTRAI e GENERA REPORT EXCEL", type="primary", disabled=(len(st.session_state['uploaded_pdfs']) == 0)):
    
    if not st.session_state['uploaded_pdfs']:
        st.error("Carica almeno un file PDF per procedere.")
        st.stop()
        
    risultati_finali = []
    
    progress_bar = st.progress(0, text=f"Analisi di {len(st.session_state['uploaded_pdfs'])} file PDF in corso...")
    
    for i, file_info in enumerate(st.session_state['uploaded_pdfs']):
        file_name = file_info['name']
        file_bytes = file_info['data']
        
        progress_text = f"Analisi file {i + 1} di {len(st.session_state['uploaded_pdfs'])}: **{file_name}**"
        progress_bar.progress((i + 1) / len(st.session_state['uploaded_pdfs']), text=progress_text)
        
        pdf_stream = BytesIO(file_bytes)
        final_text = estrai_testo_da_pdf(pdf_stream)
        
        if final_text:
            risultati_bando = estrai_dettagli_da_testo_grezzo(final_text, file_name)
            risultati_finali.append(risultati_bando)
        else:
            # Gestione del fallimento (se la lista ha già elementi, usiamo le chiavi del primo)
            default_keys = list(risultati_finali[0].keys()) if risultati_finali else list(risultati.keys())
            risultati_falliti = {k: "FALLITO (Testo non leggibile)" for k in default_keys}
            risultati_falliti["Titolo bando"] = file_name
            risultati_finali.append(risultati_falliti)
            
    progress_bar.empty()
    
    if risultati_finali:
        # Converti in DataFrame e gestisci gli NA come valori vuoti per l'Excel
        df_final = pd.DataFrame(risultati_finali).replace('NA', '', regex=True)
        
        # --- SUCCESSO ---
        try:
            st.image("success_icon.jpg", width=100) 
        except FileNotFoundError:
            st.success(f"✅ Analisi completata per {len(risultati_finali)} bandi.")
        
        st.dataframe(df_final, use_container_width=True)
        
        # Logica di Download
        output = BytesIO()
        # Usiamo 'xlsxwriter' che è stato aggiunto ai requisiti
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
        try:
            st.image("fail_icon.webp", width=300) 
        except FileNotFoundError:
            pass
        st.error("⚠️ Nessun dato è stato estratto correttamente. Controlla i file PDF.")



