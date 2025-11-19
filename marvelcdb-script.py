import requests
import os
import json
from time import sleep

# --- CONFIGURATION ---
BASE_URL = "https://marvelcdb.com"
DECKLIST_ID = 38353  # Your specific deck ID
DECKLIST_ENDPOINT = f"{BASE_URL}/api/public/decklist/{DECKLIST_ID}"
API_CARDS_ENDPOINT = f"{BASE_URL}/api/public/cards"
#IMAGE_URL_TEMPLATE = f"{BASE_URL}/card_image/{{card_id}}.jpg"
IMAGE_URL_TEMPLATE = f"{BASE_URL}/bundles/cards/{{card_id}}.png"

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
    
    image_url = custom_url if custom_url else IMAGE_URL_TEMPLATE.format(card_id=card_code)
    save_path = os.path.join(folder, f"{card_code}_{filename}.jpg")

    # Set initial success flag to False
    download_success = False
    
    try:
        # 1. Download the image data
        image_response = requests.get(image_url, timeout=10)
        # 2. Check for HTTP errors (4xx/5xx)
        image_response.raise_for_status() 

        # 3. Check if any content was received
        if not image_response.content:
            print(f"  Warning: Received empty content for {filename} ({card_code}). URL: {image_url}")
            return
            
        # 4. Save the image content directly
        with open(save_path, 'wb') as f:
            f.write(image_response.content)
            
        # 5. Check if the file was written and has a reasonable size
        if os.path.getsize(save_path) > 1000: # Images should be > 1KB
            download_success = True
        else:
            print(f"  Warning: File written for {filename} is too small ({os.path.getsize(save_path)} bytes). Deleting.")
            os.remove(save_path) # Delete the empty/corrupt file
        
    except requests.exceptions.RequestException as e:
        # If we fail, print the specific URL used
        print(f"  Failed to download {filename} ({card_code}): {e} for URL: {image_url}")
    except Exception as e:
        print(f"  Unexpected error during file write for {filename}: {e}")
        
    finally:
        if download_success:
            print(f"  Downloaded: {filename} ({card_code})")
            
    # Be polite to the server
    sleep(0.1)

def find_core_set_code(original_card_info):
    """
    Searches for the functionally identical Core Set printing of a card.
    Uses subname and pack code for differentiation.
    """
    card_name = original_card_info['name']
    original_subname = original_card_info.get('subname')
    original_type = original_card_info.get('type_code') # <-- USE THIS FIELD
    
    # 1. Prepare search URL and fetch results (unchanged)
    search_name = requests.utils.quote(card_name)
    search_url = f"{API_CARDS_ENDPOINT}?name={search_name}"
    
    print(f"  Searching for Core Set printing of '{card_name}'...")
    search_results = get_json_data(search_url, f"search for {card_name}")
    
    if not search_results:
        return None 

    # 2. STRICT FILTERING: Use a strict set of criteria
    def is_functionally_identical(candidate_card):
        # A. Must be from the Core Set
        if candidate_card.get('pack_code') != 'core':
            return False
            
        # B. Must have the exact main name
        if candidate_card.get('name') != card_name:
            return False
            
        # C. Must match the type code (e.g., 'resource' must match 'resource')
        # This prevents matching a 'Hero' with an 'Ally'
        if candidate_card.get('type_code') != original_type:
             return False
        
        # D. Subname Check: If *both* cards have a subname, they must match.
        # This catches cards like "Spider-Man (Peter Parker)" vs "Spider-Man (Miles Morales)"
        candidate_subname = candidate_card.get('subname')
        if original_subname or candidate_subname:
            if original_subname != candidate_subname:
                return False
                
        # If all checks pass, it's the Core Set equivalent
        return True
        
    core_card = next((
        card for card in search_results 
        if is_functionally_identical(card)
    ), None)
    
    if core_card:
        subname = core_card.get('subname', 'N/A')
        print(f"  --> Core Set match found: {core_card.get('name')} ({subname}) Type: {core_card.get('type_code')}")
        return core_card.get('code')
    else:
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
                core_code = find_core_set_code(original_card_info)
                
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