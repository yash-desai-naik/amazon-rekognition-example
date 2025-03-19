import streamlit as st
import requests
import json
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
from io import BytesIO

# Configure the API endpoint
API_ENDPOINT = "http://127.0.0.1:8000"  # Change to your API endpoint

# Set page title and layout
st.set_page_config(
    page_title="Face Recognition Dashboard",
    page_icon="👤",
    layout="wide"
)

# Create sessions state for variables we need to persist
if 'current_image_id' not in st.session_state:
    st.session_state.current_image_id = None

if 'current_detected_faces' not in st.session_state:
    st.session_state.current_detected_faces = []

if 'face_names' not in st.session_state:
    st.session_state.face_names = {}

if 'selected_face' not in st.session_state:
    st.session_state.selected_face = None

if 'uploaded_image' not in st.session_state:
    st.session_state.uploaded_image = None

# Functions for API interaction
def health_check():
    try:
        response = requests.get(f"{API_ENDPOINT}/health")
        return response.status_code == 200
    except Exception:
        return False

def upload_individual_face(image_bytes, name):
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    data = {'name': name}
    response = requests.post(f"{API_ENDPOINT}/upload", files=files, data=data)
    return response.json()

def recognize_face(image_bytes):
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    response = requests.post(f"{API_ENDPOINT}/recognize", files=files)
    return response.json()

def detect_faces_in_group(image_bytes):
    files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
    response = requests.post(f"{API_ENDPOINT}/detect-faces", files=files)
    return response.json()

def name_faces(image_id, face_mappings):
    data = {
        "image_id": image_id,
        "face_mappings": face_mappings
    }
    response = requests.post(f"{API_ENDPOINT}/name-faces", json=data)
    return response.json()

def list_faces():
    response = requests.get(f"{API_ENDPOINT}/faces")
    return response.json()

def list_group_photos():
    response = requests.get(f"{API_ENDPOINT}/group-photos")
    return response.json()

def get_group_photo_details(image_id):
    response = requests.get(f"{API_ENDPOINT}/group-photos/{image_id}")
    return response.json()

def delete_face(face_id):
    response = requests.delete(f"{API_ENDPOINT}/faces/{face_id}")
    return response.json()

# Helper functions
def draw_bounding_box(image, bounding_box, label=None):
    draw = ImageDraw.Draw(image)
    
    # Extract bounding box coordinates
    width, height = image.size
    left = int(bounding_box['Left'] * width)
    top = int(bounding_box['Top'] * height)
    right = int(left + (bounding_box['Width'] * width))
    bottom = int(top + (bounding_box['Height'] * height))
    
    # Draw rectangle
    draw.rectangle(((left, top), (right, bottom)), outline="red", width=3)
    
    # Draw label if provided
    if label:
        try:
            # Try to use a font if available
            font = ImageFont.truetype("arial.ttf", 15)
        except IOError:
            font = ImageFont.load_default()
        
        text_width, text_height = draw.textsize(label, font=font) if hasattr(draw, 'textsize') else (len(label) * 8, 15)
        draw.rectangle(((left, top - text_height - 4), (left + text_width + 4, top)), fill="red")
        draw.text((left + 2, top - text_height - 2), label, fill="white", font=font)
    
    return image

def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

# Sidebar navigation
st.sidebar.title("Face Recognition")
api_status = "✅ Connected" if health_check() else "❌ Disconnected"
st.sidebar.markdown(f"API Status: {api_status}")

nav_selection = st.sidebar.radio(
    "Navigation",
    ["Individual Face Recognition", "Group Photo Processing", "Face Database"]
)

# Main content area
st.title("Face Recognition Dashboard")

# Check API connection
if not health_check():
    st.error("Cannot connect to the API. Please make sure the API is running and accessible.")
    st.stop()

# Individual Face Recognition Page
if nav_selection == "Individual Face Recognition":
    st.header("Individual Face Recognition")
    
    tabs = st.tabs(["Upload New Face", "Recognize Face"])
    
    with tabs[0]:
        st.subheader("Upload an Individual Face")
        
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"], key="upload_individual")
        name = st.text_input("Person's Name")
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)
        
        if st.button("Upload Face") and uploaded_file is not None and name:
            with st.spinner("Uploading..."):
                image_bytes = uploaded_file.getvalue()
                result = upload_individual_face(image_bytes, name)
                
                if "face_id" in result:
                    st.success(f"Face uploaded successfully! Face ID: {result['face_id']}")
                else:
                    st.error(f"Error: {result.get('error', 'Unknown error')}")
    
    with tabs[1]:
        st.subheader("Recognize a Face")
        
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"], key="recognize_face")
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)
        
        if st.button("Recognize") and uploaded_file is not None:
            with st.spinner("Processing..."):
                image_bytes = uploaded_file.getvalue()
                result = recognize_face(image_bytes)
                
                if "results" in result and result["count"] > 0:
                    st.success(f"Found {result['count']} matching face(s)!")
                    
                    for i, face in enumerate(result["results"]):
                        st.write(f"**Match {i+1}:**")
                        st.write(f"- Name: {face['name']}")
                        st.write(f"- Confidence: {face['confidence']:.2f}%")
                        st.write(f"- Face ID: {face['face_id']}")
                        st.write("---")
                elif "results" in result and result["count"] == 0:
                    st.warning("No matching faces found.")
                else:
                    st.error(f"Error: {result.get('error', 'Unknown error')}")

# Group Photo Processing Page
elif nav_selection == "Group Photo Processing":
    st.header("Group Photo Processing")
    
    tabs = st.tabs(["Upload Group Photo", "Name Detected Faces", "View Group Photos"])
    
    with tabs[0]:
        st.subheader("Upload a Group Photo")
        
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"], key="upload_group")
        
        if uploaded_file is not None:
            st.session_state.uploaded_image = Image.open(uploaded_file)
            st.image(st.session_state.uploaded_image, caption="Uploaded Group Photo", use_column_width=True)
        
        if st.button("Detect Faces") and uploaded_file is not None:
            with st.spinner("Processing..."):
                image_bytes = uploaded_file.getvalue()
                result = detect_faces_in_group(image_bytes)
                
                if "image_id" in result:
                    st.session_state.current_image_id = result["image_id"]
                    st.session_state.current_detected_faces = result["faces"]
                    st.session_state.face_names = {face["face_id"]: "" for face in result["faces"]}
                    
                    # Draw bounding boxes on image
                    if st.session_state.uploaded_image:
                        image_with_boxes = st.session_state.uploaded_image.copy()
                        for i, face in enumerate(result["faces"]):
                            box = face["bounding_box"]
                            image_with_boxes = draw_bounding_box(image_with_boxes, box, f"Face {i+1}")
                        
                        st.image(image_with_boxes, caption=f"Detected {result['face_count']} Faces", use_column_width=True)
                        st.success(f"Successfully detected {result['face_count']} faces! Image ID: {result['image_id']}")
                        
                        # Show instructions for next step
                        st.info("Go to the 'Name Detected Faces' tab to assign names to these faces.")
                else:
                    st.error(f"Error: {result.get('error', 'Unknown error')}")
    
    with tabs[1]:
        st.subheader("Name Detected Faces")
        
        if not st.session_state.current_image_id or not st.session_state.current_detected_faces:
            st.info("Please upload and process a group photo first.")
        else:
            st.write(f"Image ID: {st.session_state.current_image_id}")
            st.write(f"Detected Faces: {len(st.session_state.current_detected_faces)}")
            
            # Draw image with boxes
            if st.session_state.uploaded_image:
                image_with_boxes = st.session_state.uploaded_image.copy()
                for i, face in enumerate(st.session_state.current_detected_faces):
                    box = face["bounding_box"]
                    image_with_boxes = draw_bounding_box(image_with_boxes, box, f"Face {i+1}")
                
                st.image(image_with_boxes, caption="Faces to Name", use_column_width=True)
            
            # Create form to name faces
            with st.form("name_faces_form"):
                st.write("Enter names for the faces you want to identify:")
                
                for i, face in enumerate(st.session_state.current_detected_faces):
                    face_id = face["face_id"]
                    st.session_state.face_names[face_id] = st.text_input(
                        f"Face {i+1}", 
                        value=st.session_state.face_names.get(face_id, ""),
                        key=f"face_{face_id}"
                    )
                
                submit_button = st.form_submit_button("Save Names")
                
                if submit_button:
                    # Filter out empty names
                    face_mappings = [
                        {"face_id": face_id, "name": name} 
                        for face_id, name in st.session_state.face_names.items() 
                        if name.strip()
                    ]
                    
                    if face_mappings:
                        with st.spinner("Saving names..."):
                            result = name_faces(st.session_state.current_image_id, face_mappings)
                            
                            if result.get("success"):
                                st.success(f"Successfully named {result['named_faces']} faces!")
                            else:
                                st.error(f"Error: {result.get('error', 'Unknown error')}")
                    else:
                        st.warning("No names provided. Please enter at least one name.")
    
    with tabs[2]:
        st.subheader("View Group Photos")
        
        if st.button("Refresh Group Photos"):
            st.experimental_rerun()
        
        with st.spinner("Loading group photos..."):
            try:
                result = list_group_photos()
                
                if "photos" in result and result["count"] > 0:
                    st.write(f"Found {result['count']} group photos.")
                    
                    # Create a selection box for group photos
                    photo_options = {f"{photo['image_id']} ({photo['face_count']} faces)": photo['image_id'] 
                                      for photo in result["photos"]}
                    
                    selected_option = st.selectbox(
                        "Select a group photo to view:",
                        options=list(photo_options.keys()),
                        index=0
                    )
                    
                    selected_image_id = photo_options[selected_option]
                    
                    # Get details for the selected image
                    if selected_image_id:
                        photo_details = get_group_photo_details(selected_image_id)
                        
                        if "image_id" in photo_details:
                            st.write(f"Image ID: {photo_details['image_id']}")
                            st.write(f"Face Count: {photo_details['face_count']}")
                            
                            # Display named faces
                            if photo_details["named_faces"]:
                                st.write("Named Faces:")
                                for face in photo_details["named_faces"]:
                                    st.write(f"- {face['name']} (ID: {face['face_id']})")
                            else:
                                st.write("No named faces for this photo.")
                else:
                    st.info("No group photos found. Upload some group photos first.")
            except Exception as e:
                st.error(f"Error loading group photos: {str(e)}")

# Face Database Page
elif nav_selection == "Face Database":
    st.header("Face Database")
    
    if st.button("Refresh Database"):
        st.experimental_rerun()
    
    with st.spinner("Loading face database..."):
        try:
            result = list_faces()
            
            if "faces" in result and result["count"] > 0:
                st.success(f"Found {result['count']} faces in the database.")
                
                # Create a DataFrame for better display
                face_data = pd.DataFrame([{
                    "Name": face["name"],
                    "Face ID": face["face_id"]
                } for face in result["faces"]])
                
                st.dataframe(face_data)
                
                # Add delete functionality
                st.subheader("Delete a Face")
                
                delete_options = {face["name"]: face["face_id"] for face in result["faces"]}
                selected_face = st.selectbox(
                    "Select a face to delete:",
                    options=list(delete_options.keys()),
                    index=0
                )
                
                if st.button("Delete Selected Face"):
                    with st.spinner("Deleting..."):
                        face_id = delete_options[selected_face]
                        delete_result = delete_face(face_id)
                        
                        if "message" in delete_result:
                            st.success(f"Successfully deleted {selected_face}!")
                            st.experimental_rerun()
                        else:
                            st.error(f"Error: {delete_result.get('error', 'Unknown error')}")
            else:
                st.info("No faces found in the database. Add some faces first.")
        except Exception as e:
            st.error(f"Error loading face database: {str(e)}")

# Add footer
st.markdown("---")
st.markdown("Face Recognition Dashboard - Powered by AWS Rekognition")