import os
import json
import requests
from PIL import Image

# --- CONFIGURATION ---
DECKLIST_ID = 38353
DOWNLOAD_FOLDER = f"deck_{DECKLIST_ID}_cards"
PDF_OUTPUT_FILE = f"Deck_{DECKLIST_ID}_Print_Sheet.pdf"

# Print Size Configuration (300 DPI)
TARGET_DPI = 300
TARGET_CARD_HEIGHT_PX = 1047
TARGET_CARD_WIDTH_PX = 748

# Page Layout (Standard Letter Size 8.5" x 11" @ 300 DPI)
PAGE_WIDTH_PX = 2550  # 8.5 * 300
PAGE_HEIGHT_PX = 3300 # 11.0 * 300

# Layout Grid (3 cards wide for now)
CARDS_PER_ROW = 3
CARDS_PER_COL = 3
TOTAL_CARDS_PER_PAGE = CARDS_PER_ROW * CARDS_PER_COL # 9 cards

# Margins and Spacing
MARGIN_PX = 150 # Margin on all sides
# Calculate spacing to evenly fill the page width/height
SPACING_X = (PAGE_WIDTH_PX - (CARDS_PER_ROW * TARGET_CARD_WIDTH_PX) - 2 * MARGIN_PX) // (CARDS_PER_ROW - 1)
SPACING_Y = (PAGE_HEIGHT_PX - (CARDS_PER_COL * TARGET_CARD_HEIGHT_PX) - 2 * MARGIN_PX) // (CARDS_PER_COL - 1)

API_CARDS_ENDPOINT = f"https://marvelcdb.com/api/public/cards"
DECKLIST_ENDPOINT = f"https://marvelcdb.com/api/public/decklist/{DECKLIST_ID}"

def get_json_data(url, description):
    """Fetches JSON data from a given URL with error handling."""
    print(f"Fetching {description} from {url}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {description}: {e}")
        return None

def get_all_card_data():
    """Fetches all card data and returns a map of code to sanitized name."""
    all_cards_list = get_json_data(API_CARDS_ENDPOINT, "all card data for name lookup")
    if not all_cards_list:
        return {}
    # Map code to sanitized name (which matches the end of the filename)
    return {
        card['code']: card['name'].replace(' ', '_').replace('/', '').replace(':', '')
        for card in all_cards_list
    }

def generate_print_pdf(deck_id, deck_folder, output_file):
    print(f"--- Generating Print Sheet for Deck ID {deck_id} ---")
    
    # --- 1. FETCH DECK SLOTS (Quantities) ---
    deck_data = get_json_data(DECKLIST_ENDPOINT, "decklist for layout")
    if not deck_data or not deck_data.get('slots'):
        print("Error: Could not retrieve deck slots for PDF generation.")
        return
    card_slots = deck_data['slots']

    # Initialize variables for page layout
    all_pages = []
    current_page = Image.new('RGB', (PAGE_WIDTH_PX, PAGE_HEIGHT_PX), 'white')
    card_index = 0
    
    # --- 2. GET CARD NAMES & BUILD FILENAME MAP ---
    card_name_map = get_all_card_data()
    
    # Build map from SANITIZED NAME to FILENAME (Handles the CODE_NAME.EXT format)
    name_to_filename = {}
    for filename in os.listdir(deck_folder):
        if '_' in filename:
            # Assumes the format is CODE_NAME.EXT (or CODE_NAME-WITH-DASHES.EXT)
            # Take everything AFTER the first underscore (the name part)
            name_part_with_ext = filename.split('_', 1)[-1] 
            
            # Remove the file extension (.jpg or .png)
            sanitized_name = name_part_with_ext.rsplit('.', 1)[0]
            
            # Store the map: { 'Energy': '01088_Energy.jpg' }
            name_to_filename[sanitized_name] = filename

    # --- 3. ITERATE & PLACE CARDS ---
    for card_code, quantity in card_slots.items():
        
        original_card_name = card_name_map.get(card_code, None)
        if not original_card_name:
            print(f"Skipping card {card_code}: Name data not found.")
            continue
            
        # Find the sanitized name to use as a key
        sanitized_name_key = original_card_name.replace(' ', '_').replace('/', '').replace(':', '')
        
        try:
            filename = name_to_filename[sanitized_name_key]
            image_path = os.path.join(deck_folder, filename)
        except KeyError:
            print(f"Skipping card {card_code}: Image file not found for name '{sanitized_name_key}'.")
            continue
            
        # Place copies on pages
        for i in range(quantity):
            # Calculate grid position
            col = (card_index % TOTAL_CARDS_PER_PAGE) % CARDS_PER_ROW
            row = (card_index % TOTAL_CARDS_PER_PAGE) // CARDS_PER_ROW
            
            # Calculate pixel position
            x_pos = MARGIN_PX + col * (TARGET_CARD_WIDTH_PX + SPACING_X)
            y_pos = MARGIN_PX + row * (TARGET_CARD_HEIGHT_PX + SPACING_Y)
            
            # Open, Resize, and Paste Image
            try:
                card_img = Image.open(image_path)
                card_img = card_img.resize((TARGET_CARD_WIDTH_PX, TARGET_CARD_HEIGHT_PX))
                
                current_page.paste(card_img, (x_pos, y_pos))
                print(f"  Placed copy {i+1}/{quantity} of {filename} on page {len(all_pages) + 1}")
                card_index += 1
            except Exception as e:
                print(f"Error processing image {filename}: {e}")
                continue

            # Check if page is full (Appends full page and resets current_page)
            if card_index > 0 and card_index % TOTAL_CARDS_PER_PAGE == 0:
                all_pages.append(current_page.copy()) # Save a copy of the finished page
                current_page = Image.new('RGB', (PAGE_WIDTH_PX, PAGE_HEIGHT_PX), 'white') # Start new page

    # --- 4. FINAL PAGE APPEND FIX ---
    # Only append the last page if it has content (i.e., the loop did not end on a full page)
    # Total number of cards placed: card_index
    cards_on_final_page = card_index % TOTAL_CARDS_PER_PAGE
    
    if cards_on_final_page > 0:
        all_pages.append(current_page)
    elif card_index == 0:
        # Edge case: appends a blank page if the deck was empty
        all_pages.append(current_page)


    # --- 5. SAVE PDF ---
    if all_pages:
        # Only save the PDF if pages were actually created
        all_pages[0].save(
            output_file, 
            save_all=True, 
            append_images=all_pages[1:], 
            resolution=TARGET_DPI,
            quality=95
        )
        print(f"\nSuccessfully created PDF with {len(all_pages)} pages: {output_file}")
    else:
        print("No images were processed or placed.")

# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    # Ensure the download folder exists before trying to list its contents
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
        print(f"Created directory: {DOWNLOAD_FOLDER}. Please run the download script first.")
    
    generate_print_pdf(DECKLIST_ID, DOWNLOAD_FOLDER, PDF_OUTPUT_FILE)