import requests
import os
import json
from time import sleep

# --- CONFIGURATION ---
BASE_URL = "https://marvelcdb.com"
DECKLIST_ID = 38353  # Your specific deck ID
DECKLIST_ENDPOINT = f"{BASE_URL}/api/public/decklist/{DECKLIST_ID}"
API_CARDS_ENDPOINT = f"{BASE_URL}/api/public/cards"
IMAGE_URL_TEMPLATE = f"{BASE_URL}/card_image/{{card_id}}.jpg"

OUTPUT_FOLDER = f"deck_{DECKLIST_ID}_cards"
# ---------------------

# (Keep the get_json_data and download_card_image functions as they are)

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

def download_card_image(card_code, filename, folder, custom_url=None):
    """Downloads a single card image and saves it."""
    
    # Use the custom URL (from imagesrc) if provided, otherwise use the default template
    image_url = custom_url if custom_url else IMAGE_URL_TEMPLATE.format(card_id=card_code)
    
    # 2. Define the save path (ensure we use the code for unique file names)
    save_path = os.path.join(folder, f"{card_code}_{filename}.jpg")
    #print(f"DEBUG: Saving to {os.path.abspath(save_path)}")

    # Check if file already exists
    if os.path.exists(save_path):
        return
    
    try:
        # 3. Download the image data (without streaming)
        image_response = requests.get(image_url, timeout=10)
        image_response.raise_for_status()

        # 4. Save the image content directly
        with open(save_path, 'wb') as f:
            f.write(image_response.content)

        print(f"  Downloaded: {filename} ({card_code})")
        
    except requests.exceptions.RequestException as e:
        # If we fail, print the specific URL used
        print(f"  Failed to download {filename} ({card_code}): {e} for URL: {image_url}")
    
    # Be polite to the server
    sleep(0.1)

# --- REPLACE find_core_set_code WITH THIS UPDATED VERSION ---

def find_core_set_code(card_name):
    """
    Searches the MarvelCDB API for the Core Set printing of a card by its name, 
    using a strict match to prevent false positives.
    """
    # 1. Prepare search URL (uses URL encoding for the name)
    search_name = requests.utils.quote(card_name)
    # Note: We must still use the 'name' parameter as it's the only public search filter
    search_url = f"{API_CARDS_ENDPOINT}?name={search_name}"
    
    print(f"  Searching for Core Set printing of '{card_name}'...")
    
    search_results = get_json_data(search_url, f"search for {card_name}")
    
    if not search_results:
        return None 

    # 2. STRICT FILTERING: Find the card that EXACTLY matches the name AND is from the core pack.
    core_card = next((
        card for card in search_results 
        if card.get('pack_code') == 'core' and card.get('name') == card_name # <-- ADDED STRICT NAME CHECK
    ), None)
    
    if core_card:
        # We found the correct card. Return its code.
        return core_card.get('code')
    else:
        # No Core Set version matching the exact name was found.
        return None

def pull_card_images_by_deck(deck_id, output_folder):
    """
    Fetches the decklist, resolves card codes, and downloads images.
    """
    print(f"--- Starting Download for Deck ID {deck_id} ---")
    os.makedirs(output_folder, exist_ok=True)
    
    # 1. Fetch the Decklist
    deck_data = get_json_data(DECKLIST_ENDPOINT, f"decklist for ID {deck_id}")
    if not deck_data:
        return

    deck_name = deck_data.get('name', f"Deck {deck_id}")
    print(f"Deck Name: **{deck_name}**")

    card_slots = deck_data.get('slots', {})
    if not card_slots:
        print("Error: Deck data did not contain card slots.")
        return

    # 2. Fetch ALL Card Data
    all_cards_list = get_json_data(API_CARDS_ENDPOINT, "all card data")
    if not all_cards_list:
        return
    
    # --- FIX APPLIED HERE ---
    # Convert the list of card objects into a dictionary for fast lookup
    # { "card_code": {card_data}, ... }
    card_data_map = {card['code']: card for card in all_cards_list}
    # ------------------------
    
    # 3. Download Images for each unique card in the deck
    print(f"\nFound {len(card_slots)} unique cards. Starting download...")
    downloaded_count = 0
    
    for card_code, quantity in card_slots.items():
        original_card_info = card_data_map.get(card_code)
        
        if original_card_info:
            card_name = original_card_info['name']
            
            # Check if we should find a Core Set alternative
            if original_card_info.get('pack_code') != 'core':
                core_code = find_core_set_code(card_name)
                
                if core_code:
                    # Successfully found the Core Set version! Use its code.
                    download_code = core_code
                    print(f"  --> Found Core Set alternate code: {download_code} (for {card_name})")
                else:
                    # Fallback: use the original (potentially skewed) card's code
                    download_code = card_code
            else:
                # Card is already from the Core Set, use its code
                download_code = card_code
            
            # --- Download using the determined 'download_code' ---
            
            # Use a sanitized version of the card name for the filename
            sanitized_name = card_name.replace(' ', '_').replace('/', '').replace(':', '')
            
            # No need for custom_url lookup here, as we rely on the standard
            # image path of the Core Set card.
            download_card_image(
                card_code=download_code, 
                filename=sanitized_name, 
                folder=output_folder
            )
            downloaded_count += 1
            
        else:
            print(f"Warning: Could not find full data for card code {card_code}. Skipping.")       
    print(f"\nSuccessfully downloaded {downloaded_count} unique card images for the deck.")
    print("--- Download Complete ---")


if __name__ == "__main__":
    pull_card_images_by_deck(DECKLIST_ID, OUTPUT_FOLDER)