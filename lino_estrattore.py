import streamlit as st
import pandas as pd
import re
from datetime import datetime
from io import BytesIO 
from pypdf import PdfReader # Libreria per la lettura dei PDF

# --- FUNZIONE DI ANALISI DEL TESTO AVANZATA (CORE DEL BOT) ---

def estrai_dettagli_da_testo_grezzo(testo_bando, file_name):
    """
    Analizza il testo grezzo di un bando usando espressioni regolari e liste di parole chiave
    per estrarre informazioni strutturate nella nuova lista dettagliata.
    """
    
    # Inizializzazione del dizionario dei risultati
    # Tutti i campi sono inizializzati a 'NA'
    risultati = {
        "Titolo bando": file_name.replace(".pdf", "").replace("_", " ").title(),
        "Categoria": "NA",
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
    
    # Liste estese di parole chiave (per migliorare l'estrazione RegEx)
    
    # ----------------------------------------------------
    # 1. ESTRAZIONE DATI NUMERICI E TEMPORALI (REGULAR EXPRESSIONS)
    # ----------------------------------------------------
    
    # -- Deadline --
    mesi_it_en = r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|september|october|november|december)'
    date_pattern = rf'(scadenza|deadline|termine|data di chiusura)[^a-z]*(\d{{1,2}}[\/\-\.]\d{{1,2}}[\/\-\.]\d{{2,4}}|\d{{1,2}}\s{mesi_it_en}\s\d{{2,4}}|\d{{4}}[\-\/]\d{{1,2}}[\-\/]\d{{1,2}})'
    date_matches = re.search(date_pattern, text, re.IGNORECASE)
    if date_matches:
        risultati["Deadline presentazione proposta"] = date_matches.group(2).strip() 

    # -- Importo Max per Proposta / Totale Finanziamento (simil-RegEx per numeri) --
    
    # Pattern più generale per catturare numeri grandi con valute (€, $, CHF, GBP, Euro)
    amount_pattern = r'(\d{{1,3}}(?:[,\.]\d{{3}})*(?:[,\.]\d{{1,2}})?)\s*(€|euro|EUR|milioni|\$|USD|CHF|GBP)'
    amount_matches = re.findall(amount_pattern, text, re.IGNORECASE)

    if amount_matches:
        # Tenta di identificare l'importo massimo, spesso è il più grande o il primo significativo
        # Questo è un tentativo euristico, non garantito.
        
        # Converte i risultati in numeri per confronto
        numeric_amounts = []
        for val, currency in amount_matches:
            # Pulisce i separatori di migliaia e decimali (gestione euristica IT/EN)
            cleaned_val = val.replace('.', '').replace(',', '') # Togli tutti i separatori inizialmente
            
            # Se ha una virgola, trattala come decimale IT
            if ',' in val:
                 cleaned_val = val.replace('.', '').replace(',', '.') # Es: 1.000,00 -> 1000.00
            # Se ha un punto come decimale, rimuovi le virgole
            elif '.' in val and len(val.split('.')[-1]) == 2:
                 pass # Lascia com'è (formato EN)
                 
            try:
                numeric_amounts.append(float(cleaned_val))
            except ValueError:
                continue

        # Se ci sono importi significativi, assegna i primi trovati
        if len(amount_matches) > 0:
            valore = amount_matches[0][0].replace('.', '_').replace(',', '.').replace('_', ',')
            simbolo = amount_matches[0][1]
            risultati["Importo max per proposta"] = f"Max {valore} {simbolo}"
        
        if len(amount_matches) > 1:
            valore = amount_matches[1][0].replace('.', '_').replace(',', '.').replace('_', ',')
            simbolo = amount_matches[1][1]
            risultati["Totale finanziamento"] = f"Totale {valore} {simbolo}"
            
    # -- Durata (es: 12 mesi, 1-3 anni) --
    durata_pattern = r'(durata (del progetto)?|periodo di attuazione)[:\s]*(\d{1,2}[\s\-\/]\d{1,2}|fino a \d{1,2}|massimo \d{1,2})\s*(mesi|anni)'
    durata_matches = re.search(durata_pattern, text, re.IGNORECASE)
    if durata_matches:
        risultati["Durata min/max progetti"] = durata_matches.group(3).strip() + " " + durata_matches.group(4)
        
    # ----------------------------------------------------
    # 2. ESTRAZIONE BASATA SU PAROLE CHIAVE (SETTORE, AREA, CONSORZIO, CO-FIN)
    # ----------------------------------------------------

    # Liste dei donatori più comuni (euristica)
    KEY_DONATORI = ['european union', 'commissione europea', 'fondazione cariplo', 'fondazione crt', 'fondazione cdp', 'unhcr', 'unicef', 'usaid', 'aics', 'ministero degli affari esteri']

    # Cerca co-finanziamento e partenariato/consorzio
    if any(k in text for k in ['co-finanziamento', 'cofinanziamento', 'co-funding']):
        risultati["Co-finanziamento previsto"] = "Sì (Cercare %)"
    
    if any(k in text for k in ['consorzio', 'ats', 'associazione temporanea di scopo', 'partenariato', 'partnership', 'joint application']):
        risultati["Consorzio/ATS/partenariato"] = "Obbligatorio/Ammesso"

    # Area Geografica (ricerca di enti amministrativi o aree vaste)
    KEY_GEOGRAFIA = ['regione puglia', 'lombardia', 'veneto', 'campania', 'sicilia', 'italia', 'ue', 'europa', 'global', 'nazionale']
    found_geografia = set(key.capitalize() for key in KEY_GEOGRAFIA if key in text)
    if found_geografia:
        risultati["Area di implementazione"] = "; ".join(found_geografia)
        
    # Donatore
    found_donatori = set(key.title() for key in KEY_DONATORI if key in text)
    if found_donatori:
        risultati["Donatore"] = "; ".join(found_donatori)
        
    # ----------------------------------------------------
    # 3. ESTRAZIONE TESTO CONTESTUALE (più difficile senza AI)
    # ----------------------------------------------------
    
    # Per i campi testuali lunghi (Obiettivi, Criteri di eleggibilità, ecc.), 
    # cerchiamo i titoli delle sezioni nel PDF e catturiamo il testo successivo
    
    # Euristiche per catturare il testo dopo i titoli comuni
    def extract_section(title_list, max_chars=300):
        for title in title_list:
            # Cerca il titolo e cattura i successivi N caratteri o fino al prossimo titolo
            pattern = re.escape(title) + r'[:\s]*(.*?)(\n\d\.\s|\n[A-Z]\.\s|Criteri|Documentazione|Obiettivi|Settori|$)'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted_text = match.group(1).strip()
                # Pulizia grossolana
                extracted_text = re.sub(r'\s+', ' ', extracted_text) 
                return extracted_text[:max_chars].strip() + ("..." if len(extracted_text) > max_chars else "")
        return "NA (Ricerca Manuale)"

    risultati["Obiettivi bando / proposte"] = extract_section(['Obiettivi del Bando', 'Finalità', 'Scope', 'Goals', 'Priorità tematiche'])
    risultati["Criteri di eleggibilità"] = extract_section(['Criteri di eleggibilità', 'Eligibility Criteria', 'Chi può partecipare', 'Requisiti dei proponenti'])
    risultati["Documentazione richiesta"] = extract_section(['Documentazione richiesta', 'Documenti da allegare', 'Required Documents', 'Modalità di presentazione'])
    risultati["Criteri di valutazione"] = extract_section(['Criteri di valutazione', 'Evaluation Criteria', 'Punteggio massimo', 'Metodologia di selezione'])
    
    # Estrazione settori target (parole chiave raggruppate)
    KEY_SETTORI = ['clima', 'ambiente', 'biodiversità', 'inclusione', 'sociale', 'cultura', 'migrazione', 'salute', 'energia rinnovabile']
    found_settori = set(key.capitalize() for key in KEY_SETTORI if key in text)
    if found_settori:
        risultati["Settori target"] = "; ".join(found_settori)
    
    # Gruppi target
    KEY_GRUPPI = ['donne', 'giovani', 'minori', 'anziani', 'disabili', 'migranti', 'rifugiati', 'comunità locali', 'popolazioni vulnerabili']
    found_gruppi = set(key.capitalize() for key in KEY_GRUPPI if key in text)
    if found_gruppi:
        risultati["Gruppi target"] = "; ".join(found_gruppi)

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
        # Nota: L'errore è mostrato nell'interfaccia Streamlit, qui restituiamo None
        return None

# --- INTERFACCIA STREAMLIT (Frontend) ---

st.set_page_config(page_title="📋 Lino Estrattore Multi-Bando", layout="wide")

st.title("📋 Lino Estrattore Multi-Bando (Analisi PDF Gratuita)")

st.markdown("""
Carica fino a **5 file PDF** (uno per volta) e l'applicazione estrarrà le informazioni chiave basandosi su regole di testo avanzate e le sintetizzerà in un file Excel unico.
""")
st.markdown("---")

# 1. Configurazione della Sessione
if 'uploaded_pdfs' not in st.session_state:
    st.session_state['uploaded_pdfs'] = []
    
# Variabile per il nome del file Excel di output
if 'filename_output' not in st.session_state:
    st.session_state['filename_output'] = f'Sintesi_Bandi_{datetime.now().strftime("%Y%m%d")}'

# 2. Form per Upload e Aggiunta
with st.form("pdf_upload_form"):
    
    st.subheader("Aggiungi i File PDF (Max 5)")
    
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
            st.success(f"File aggiunto: {uploaded_file.name}. Totale: {len(st.session_state['uploaded_pdfs'])}.")
        else:
            st.warning("Hai raggiunto il limite massimo di 5 PDF.")
        st.rerun() # Riavvia per pulire l'uploader

    # Logica di pulizia
    if clear_button:
        st.session_state['uploaded_pdfs'] = []
        st.info("Lista file svuotata.")
        st.rerun() # Riavvia per pulire lo stato

# 3. Stato attuale dei file in coda
st.subheader(f"File in Coda per l'Analisi: {len(st.session_state['uploaded_pdfs'])}/5")
if st.session_state['uploaded_pdfs']:
    file_names = [f['name'] for f in st.session_state['uploaded_pdfs']]
    st.markdown("* " + "\n* ".join(file_names))
else:
    st.info("Nessun file PDF caricato. Carica i file e clicca 'Aggiungi File all'Analisi'.")
    
st.markdown("---")

# 4. Esecuzione e Download
filename_input = st.text_input(
    "Dai un nome al tuo file Excel di output:", 
    value=st.session_state['filename_output'],
    key='filename_output_key' # Aggiorna la session_state con il valore
)

if st.button("▶️ ESTRAI e GENERATE REPORT EXCEL", type="primary", disabled=(len(st.session_state['uploaded_pdfs']) == 0)):
    
    if not st.session_state['uploaded_pdfs']:
        st.error("Carica almeno un file PDF per procedere.")
        st.stop()
        
    risultati_finali = []
    
    # Inizializza la barra di progresso
    progress_bar = st.progress(0, text=f"Analisi di {len(st.session_state['uploaded_pdfs'])} file PDF in corso...")
    
    for i, file_info in enumerate(st.session_state['uploaded_pdfs']):
        file_name = file_info['name']
        file_bytes = file_info['data']
        
        progress_text = f"Analisi file {i + 1} di {len(st.session_state['uploaded_pdfs'])}: {file_name}"
        progress_bar.progress((i + 1) / len(st.session_state['uploaded_pdfs']), text=progress_text)
        
        # 1. Lettura del PDF dai bytes
        pdf_stream = BytesIO(file_bytes)
        final_text = estrai_testo_da_pdf(pdf_stream)
        
        if final_text:
            # 2. Estrazione dei dettagli
            risultati_bando = estrai_dettagli_da_testo_grezzo(final_text, file_name)
            risultati_finali.append(risultati_bando)
        else:
            # Aggiungi un record vuoto se l'estrazione del testo è fallita
            risultati_falliti = {k: "FALLITO (Testo non leggibile)" for k in risultati_finali[0].keys()} if risultati_finali else {}
            risultati_falliti["Titolo bando"] = file_name
            risultati_finali.append(risultati_falliti)
            
    progress_bar.empty()
    
    if risultati_finali:
        df_final = pd.DataFrame(risultati_finali)
        st.success(f"✅ Analisi completata per {len(risultati_finali)} bandi. Ecco il report sintetico:")
        
        # Visualizzazione Tabella
        st.dataframe(df_final, use_container_width=True)
        
        # Logica di Download
        output = BytesIO()
        df_final.to_excel(output, index=False, engine='xlsxwriter') 
        excel_data = output.getvalue() 
        
        # Prendi il nome del file dall'input (salvato nella session_state)
        nome_file_finale = f'{st.session_state.filename_output_key.replace(" ", "_")}.xlsx' 

        st.download_button(
            label="Scarica il Report Sintetico (Excel)",
            data=excel_data, 
            file_name=nome_file_finale,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        st.error("⚠️ Nessun dato è stato estratto correttamente. Controlla i file PDF.")