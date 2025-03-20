import streamlit as st
import requests
from PIL import Image
import io
import base64
from io import BytesIO

# API URL
BASE_URL = "http://localhost:8000"  # Change this to your API URL

st.set_page_config(page_title="Face Recognition Demo", layout="wide")
st.title("Face Recognition System")

# Initialize session state
if 'profiles' not in st.session_state:
    st.session_state.profiles = []
if 'selected_profile' not in st.session_state:
    st.session_state.selected_profile = None

# Function to load profiles
def load_profiles():
    try:
        response = requests.get(f"{BASE_URL}/profiles")
        if response.status_code == 200:
            st.session_state.profiles = response.json()
            return True
        else:
            st.error(f"Error loading profiles: {response.text}")
            return False
    except Exception as e:
        st.error(f"Error connecting to API: {e}")
        return False

# Function to display image from URL
def display_image(url, caption=None, width=200):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            st.image(image, caption=caption, width=width)
        else:
            st.warning(f"Could not load image: {url}")
    except Exception as e:
        st.warning(f"Error displaying image: {e}")

# Sidebar
st.sidebar.title("Controls")

# Refresh profiles
if st.sidebar.button("Refresh Profiles"):
    load_profiles()

# Create tabs
tab1, tab2, tab3 = st.tabs(["Create Profile", "View Profiles", "Upload Group Photo"])

# Tab 1: Create Profile
with tab1:
    st.header("Create a New Profile")
    
    name = st.text_input("Name")
    uploaded_file = st.file_uploader("Upload a clear face photo", type=["jpg", "jpeg", "png"])
    
    if st.button("Create Profile") and name and uploaded_file:
        try:
            files = {"file": uploaded_file}
            data = {"name": name}
            
            with st.spinner("Creating profile..."):
                response = requests.post(f"{BASE_URL}/profiles", files=files, data=data)
                
                if response.status_code == 200:
                    profile = response.json()
                    st.success(f"Profile created for {profile['name']}")
                    st.subheader("Profile Image")
                    display_image(profile['profile_image_s3'], profile['name'])
                    
                    # Refresh profiles list
                    load_profiles()
                else:
                    st.error(f"Error creating profile: {response.text}")
        except Exception as e:
            st.error(f"Error: {e}")

# Tab 2: View Profiles
with tab2:
    st.header("View Profiles")
    
    # Load profiles if not loaded
    if not st.session_state.profiles:
        load_profiles()
    
    if not st.session_state.profiles:
        st.info("No profiles found. Create a profile first.")
    else:
        # Create profile selection
        profile_names = [profile["name"] for profile in st.session_state.profiles]
        selected_name = st.selectbox("Select Profile", profile_names)
        
        # Find selected profile details
        selected_profile = next((p for p in st.session_state.profiles if p["name"] == selected_name), None)
        
        if selected_profile:
            # Display profile details
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Profile Image")
                display_image(selected_profile["profile_image_s3"], selected_profile["name"])
                
                if st.button("Re-match Faces"):
                    with st.spinner("Matching faces..."):
                        response = requests.post(f"{BASE_URL}/match_faces/{selected_profile['profile_id']}")
                        if response.status_code == 200:
                            updated_profile = response.json()
                            # Update the profile in session state
                            for i, p in enumerate(st.session_state.profiles):
                                if p["profile_id"] == updated_profile["profile_id"]:
                                    st.session_state.profiles[i] = updated_profile
                            st.success("Faces re-matched successfully")
                            st.rerun()
                        else:
                            st.error(f"Error matching faces: {response.text}")
            
            with col2:
                st.subheader("Matched Images")
                if not selected_profile["matched_images"]:
                    st.info("No matched images found for this profile")
                else:
                    # Create a grid for matched images
                    num_images = len(selected_profile["matched_images"])
                    cols = st.columns(min(3, num_images))
                    
                    for i, image_url in enumerate(selected_profile["matched_images"]):
                        with cols[i % 3]:
                            display_image(image_url, f"Match {i+1}")

# Tab 3: Upload Group Photo
with tab3:
    st.header("Upload Group Photo")
    
    uploaded_group = st.file_uploader("Upload a group photo", type=["jpg", "jpeg", "png"])
    
    if st.button("Detect Faces") and uploaded_group:
        try:
            files = {"file": uploaded_group}
            data = {"description": "Group photo"}
            
            with st.spinner("Detecting faces..."):
                response = requests.post(f"{BASE_URL}/upload_image", files=files, data=data)
                
                if response.status_code == 200:
                    detected_faces = response.json()
                    st.success(f"Detected {len(detected_faces)} faces")
                    
                    # Display original image
                    st.subheader("Uploaded Group Photo")
                    group_image = Image.open(uploaded_group)
                    st.image(group_image, width=600)
                    
                    # Show detected faces info
                    st.subheader("Detected Faces")
                    
                    if not detected_faces:
                        st.info("No faces detected in the image")
                    else:
                        # Create two columns for each face
                        for i, face in enumerate(detected_faces):
                            col1, col2 = st.columns([1, 3])
                            
                            with col1:
                                st.write(f"**Face {i+1}**")
                                if face.get("matched_profile_id"):
                                    # Find matching profile name
                                    matched_profile = next((p for p in st.session_state.profiles if p["profile_id"] == face["matched_profile_id"]), None)
                                    if matched_profile:
                                        st.success(f"Matched: {matched_profile['name']}")
                                        st.write(f"Confidence: {face.get('confidence', 0):.2f}%")
                                else:
                                    st.warning("No match found")
                            
                            with col2:
                                # Display the group image where this face was detected
                                display_image(face["s3_path"], "Group photo")
                    
                    # Refresh profiles to update matched images
                    load_profiles()
                else:
                    st.error(f"Error detecting faces: {response.text}")
        except Exception as e:
            st.error(f"Error: {e}")

# Initial load of profiles
if not st.session_state.profiles:
    load_profiles()