import streamlit as st
import os
import tempfile
import base64
from utils.pdf_processor import pdf_to_images, overlay_text, draw_bounding_boxes
from utils.llm_helper import detect_form_fields
from utils.sarvam_helper import speak_text, transcribe_audio_bytes, clean_transcribed_value
from utils.config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_VISION_MODEL, SARVAM_API_KEY

st.set_page_config(page_title="PDF Form Filler (Voice Enabled)", layout="wide")

st.title("🤖 AI PDF Form Filler with Voice")
st.markdown("Upload a PDF, let AI find the blanks, fill them in using **voice** or text, and download the result!")

sarvam_api_key = SARVAM_API_KEY

with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption(f"**Model:** `{OPENROUTER_MODEL}`")
    if OPENROUTER_VISION_MODEL != OPENROUTER_MODEL:
        st.caption(f"**Vision model:** `{OPENROUTER_VISION_MODEL}`")
    if not OPENROUTER_API_KEY:
        st.warning("OPENROUTER_API_KEY is not set in .env")

    st.divider()

    st.header("🎤 Voice Settings")

    voice_language = st.selectbox(
        "Voice Language",
        options=["hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN", "gu-IN", "pa-IN"],
        index=0,
        help="Language for Text-to-Speech and Speech-to-Text (default: Hindi)"
    )

    voice_speaker = st.selectbox(
        "TTS Voice",
        options=["anushka", "manisha", "vidya", "arya", "priya", "neha", "kavya", "abhilash", "karun", "hitesh", "rahul", "amit", "dev"],
        index=0,
        help="Voice for Text-to-Speech"
    )

    if not sarvam_api_key:
        st.info("Set SARVAM_API_KEY in .env to enable voice features.")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

# Session state initialization
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}  # {page_idx: [fields]}
if 'voice_mode' not in st.session_state:
    st.session_state.voice_mode = False
if 'current_voice_field' not in st.session_state:
    st.session_state.current_voice_field = 0
if 'voice_field_values' not in st.session_state:
    st.session_state.voice_field_values = {}

def play_audio_in_browser(audio_bytes):
    """Play audio in the browser using HTML5 audio element."""
    b64_audio = base64.b64encode(audio_bytes).decode()
    audio_html = f'''
    <audio autoplay>
        <source src="data:audio/wav;base64,{b64_audio}" type="audio/wav">
    </audio>
    '''
    st.markdown(audio_html, unsafe_allow_html=True)

def get_all_fields_flat():
    """Get all fields as a flat list with page info."""
    all_fields = []
    for page_idx, fields in st.session_state.form_data.items():
        for j, field in enumerate(fields):
            field_copy = field.copy()
            field_copy['page'] = page_idx
            field_copy['field_index'] = j
            all_fields.append(field_copy)
    return all_fields

if uploaded_file and OPENROUTER_API_KEY:
    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    # Process button
    if st.button("📄 Analyze PDF"):
        with st.spinner("Converting PDF to images and analyzing with AI..."):
            try:
                images = pdf_to_images(tmp_path)
                st.session_state.form_data = {}
                st.session_state.pdf_path = tmp_path
                st.session_state.current_voice_field = 0
                st.session_state.voice_field_values = {}
                
                progress_bar = st.progress(0)
                for i, img in enumerate(images):
                    st.text(f"Processing page {i+1}/{len(images)}...")
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as img_tmp:
                        img.save(img_tmp.name)
                        img_path = img_tmp.name
                    
                    # Call LLM
                    fields = detect_form_fields(img_path)
                    
                    st.session_state.form_data[i] = fields
                    progress_bar.progress((i + 1) / len(images))
                    
                    os.unlink(img_path)
                
                st.success("✅ Analysis Complete!")
                
                if not st.session_state.form_data or all(not v for v in st.session_state.form_data.values()):
                    st.warning("No fields were detected. Check your LLM's vision capabilities/response.")

            except Exception as e:
                st.error(f"Error processing PDF: {e}")

    # Display Form
    if st.session_state.get('form_data'):
        st.divider()
        
        # Voice Fill Mode Toggle
        col_header1, col_header2 = st.columns([2, 1])
        with col_header1:
            st.subheader("📝 Fill in the Details")
        with col_header2:
            voice_enabled = st.toggle("🎤 Voice Fill Mode", value=st.session_state.voice_mode, disabled=not sarvam_api_key)
            st.session_state.voice_mode = voice_enabled
            if not sarvam_api_key and voice_enabled:
                st.warning("Add Sarvam API key in sidebar")
        
        # ============ VOICE FILL MODE ============
        if st.session_state.voice_mode and sarvam_api_key:
            st.info("🎙️ **Voice Fill Mode Active** - Follow the prompts to fill each field by speaking!")
            
            all_fields = get_all_fields_flat()
            
            if all_fields:
                current_idx = st.session_state.current_voice_field
                
                if current_idx < len(all_fields):
                    current_field = all_fields[current_idx]
                    field_label = current_field.get('label', f"Field {current_idx + 1}")
                    
                    st.markdown(f"### 🎯 Field {current_idx + 1} of {len(all_fields)}: **{field_label}**")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        # Play TTS prompt
                        if st.button("🔊 Play Prompt", key=f"tts_{current_idx}"):
                            with st.spinner("Generating voice prompt..."):
                                try:
                                    prompt_text = f"कृपया {field_label} बताइए"
                                    audio_bytes = speak_text(prompt_text, sarvam_api_key, voice_language, voice_speaker)
                                    play_audio_in_browser(audio_bytes)
                                    st.success("Prompt played!")
                                except Exception as e:
                                    st.error(f"TTS Error: {e}")
                        
                        # Audio recorder
                        try:
                            from audio_recorder_streamlit import audio_recorder
                            
                            st.markdown("**🎤 Record your response** (auto-transcribes when done):")
                            audio_data = audio_recorder(
                                text="",
                                recording_color="#e74c3c",
                                neutral_color="#3498db",
                                icon_size="3x",
                                key=f"recorder_{current_idx}"
                            )
                            
                            # Auto-transcribe and clean when new audio is recorded
                            if audio_data is not None and len(audio_data) > 1000:  # Min 1KB to ensure valid audio
                                # Check if this is new audio (not already processed)
                                audio_hash = hash(audio_data)
                                last_hash_key = f"last_audio_hash_{current_idx}"
                                
                                if st.session_state.get(last_hash_key) != audio_hash:
                                    st.session_state[last_hash_key] = audio_hash
                                    
                                    # Show audio player
                                    st.audio(audio_data, format="audio/wav")
                                    
                                    with st.spinner("🎯 Transcribing and formatting..."):
                                        try:
                                            # Step 1: Transcribe (Hindi speech to text)
                                            raw_transcript = transcribe_audio_bytes(audio_data, sarvam_api_key, voice_language)
                                            st.info(f"📝 Raw transcription: *{raw_transcript}*")
                                            
                                            # Step 2: Clean and format using LLM (translate to English & format)
                                            cleaned_value = clean_transcribed_value(
                                                raw_text=raw_transcript,
                                                field_label=field_label,
                                            )
                                            
                                            st.session_state.voice_field_values[current_idx] = cleaned_value
                                            st.success(f"✅ Cleaned value: **{cleaned_value}**")
                                            
                                        except Exception as e:
                                            st.error(f"Error: {e}")
                                else:
                                    # Show previously processed value
                                    if current_idx in st.session_state.voice_field_values:
                                        st.audio(audio_data, format="audio/wav")
                                        st.success(f"✅ Value: **{st.session_state.voice_field_values[current_idx]}**")
                            elif audio_data is not None:
                                st.warning("⏳ Recording too short. Please record again.")
                        
                        except ImportError:
                            st.warning("Audio recorder not installed. Using text fallback.")
                            manual_input = st.text_input(f"Enter value for {field_label}", key=f"manual_{current_idx}")
                            if manual_input:
                                st.session_state.voice_field_values[current_idx] = manual_input
                        
                        # Show current value
                        if current_idx in st.session_state.voice_field_values:
                            st.info(f"Current value: **{st.session_state.voice_field_values[current_idx]}**")
                        
                        # Navigation
                        nav_col1, nav_col2, nav_col3 = st.columns(3)
                        with nav_col1:
                            if st.button("⬅️ Previous", disabled=current_idx == 0):
                                st.session_state.current_voice_field = max(0, current_idx - 1)
                                st.rerun()
                        with nav_col2:
                            if st.button("➡️ Next"):
                                st.session_state.current_voice_field = min(len(all_fields) - 1, current_idx + 1)
                                st.rerun()
                        with nav_col3:
                            if st.button("✅ Done"):
                                st.session_state.current_voice_field = len(all_fields)
                                st.rerun()
                    
                    with col2:
                        # Show current page with field highlighted
                        page_idx = current_field['page']
                        if 'pdf_path' in st.session_state:
                            images = pdf_to_images(st.session_state.pdf_path)
                            if page_idx < len(images):
                                img_with_boxes = draw_bounding_boxes(images[page_idx], [current_field])
                                st.image(img_with_boxes, caption=f"Page {page_idx+1} - Current Field", use_column_width=True)
                
                else:
                    # All fields done
                    st.success("🎉 All fields completed! Review and generate your PDF below.")
                    
                    st.markdown("### Review Values:")
                    for idx, field in enumerate(all_fields):
                        value = st.session_state.voice_field_values.get(idx, "")
                        label = field.get('label', f"Field {idx + 1}")
                        st.write(f"- **{label}**: {value if value else '(empty)'}")
                    
                    if st.button("🔄 Start Over"):
                        st.session_state.current_voice_field = 0
                        st.session_state.voice_field_values = {}
                        st.rerun()
        
        # ============ MANUAL/TEXT MODE ============
        else:
            all_user_inputs = []
            
            for page_idx, fields in st.session_state.form_data.items():
                if not fields:
                    st.info(f"No fields detected on page {page_idx + 1}")
                    continue
                    
                with st.expander(f"📄 Page {page_idx + 1}", expanded=True):
                    col1, col2 = st.columns([1, 1])
                    
                    with col2:
                        if 'pdf_path' in st.session_state:
                            images = pdf_to_images(st.session_state.pdf_path)
                            if page_idx < len(images):
                                img_with_boxes = draw_bounding_boxes(images[page_idx], fields)
                                st.image(img_with_boxes, caption=f"Page {page_idx+1} (Detected Fields)", use_column_width=True)
                    
                    with col1:
                        for j, field in enumerate(fields):
                            label = field.get('label', f"Field {j+1}")
                            user_val = st.text_input(label, key=f"p{page_idx}_f{j}")
                            
                            field['value'] = user_val
                            field['page'] = page_idx
                            all_user_inputs.append(field)

        # Generate Button
        st.divider()
        if st.button("📥 Generate Filled PDF", type="primary"):
            if 'pdf_path' in st.session_state:
                with st.spinner("Generating PDF..."):
                    # Collect all inputs (from voice or text mode)
                    if st.session_state.voice_mode:
                        all_fields = get_all_fields_flat()
                        for idx, field in enumerate(all_fields):
                            field['value'] = st.session_state.voice_field_values.get(idx, "")
                        final_inputs = all_fields
                    else:
                        final_inputs = []
                        for page_idx, fields in st.session_state.form_data.items():
                            for j, field in enumerate(fields):
                                key = f"p{page_idx}_f{j}"
                                field['value'] = st.session_state.get(key, "")
                                field['page'] = page_idx
                                final_inputs.append(field)
                    
                    output_path = st.session_state.pdf_path.replace(".pdf", "_filled.pdf")
                    final_path = overlay_text(st.session_state.pdf_path, final_inputs, output_path)
                    
                    with open(final_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Filled PDF",
                            data=f,
                            file_name="filled_form.pdf",
                            mime="application/pdf"
                        )
            else:
                st.error("Session expired, please re-upload.")

