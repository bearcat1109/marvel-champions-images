# Script to get all card images from a MarvelCDB pack.
# Modified from deck downloader to pack downloader.

import requests
import os
import json
from time import sleep
from PIL import Image
from io import BytesIO

# --- CONFIGURATION ---
BASE_URL = "https://marvelcdb.com"
PACK_CODE = "sm"  # Change this to your desired pack code (e.g., 'core', 'trors', 'got', etc.)
PACK_ENDPOINT = f"{BASE_URL}/api/public/cards/{PACK_CODE}.json"
IMAGE_URL_TEMPLATE = f"{BASE_URL}/bundles/cards/{{card_id}}.png"

# Set to True to download only villain/encounter cards, False for all cards
VILLAIN_ONLY = True

OUTPUT_FOLDER = f"pack_{PACK_CODE}_cards{'_villain_only' if VILLAIN_ONLY else ''}"

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

def download_card_image(card_code, filename, folder):
    """Downloads a single card image, rotates if horizontal, and saves it."""
    
    image_url = IMAGE_URL_TEMPLATE.format(card_id=card_code)
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
        
        # 4. Open image with PIL to check orientation
        img = Image.open(BytesIO(image_response.content))
        width, height = img.size
        
        # 5. If image is horizontal (width > height), rotate it 90 degrees clockwise
        if width > height:
            print(f"  Rotating horizontal card: {filename}")
            img = img.rotate(-90, expand=True)  # -90 for clockwise, expand=True adjusts size
        
        # 6. Save the image (rotated if necessary)
        img.save(save_path, 'JPEG', quality=95)
        
        # 7. Check if the file was written and has a reasonable size
        if os.path.getsize(save_path) > 1000:
            download_success = True
        else:
            print(f"  Warning: File written for {filename} is too small ({os.path.getsize(save_path)} bytes). Deleting.")
            os.remove(save_path)
        
    except requests.exceptions.RequestException as e:
        # If fail, print the specific URL used
        print(f"  Failed to download {filename} ({card_code}): {e} for URL: {image_url}")
    except Exception as e:
        print(f"  Unexpected error during image processing for {filename}: {e}")
        
    finally:
        if download_success:
            print(f"  Downloaded: {filename} ({card_code})")
            
    # Naptime
    sleep(0.1)

def pull_card_images_by_pack(pack_code, output_folder, villain_only=False):
    """
    Fetches all cards from a pack and downloads their images.
    If villain_only is True, only downloads encounter/villain cards.
    """
    print(f"--- Starting Download for Pack '{pack_code}' ---")
    if villain_only:
        print("    (Villain/Encounter cards only)")
    os.makedirs(output_folder, exist_ok=True)
    
    # 1. Fetch the Pack's Cards
    pack_cards = get_json_data(PACK_ENDPOINT, f"cards for pack '{pack_code}'")
    if not pack_cards:
        print(f"Error: Could not fetch cards for pack '{pack_code}'.")
        print(f"Make sure the pack code is correct. Common pack codes include:")
        print("  - 'core' (Core Set)")
        print("  - 'trors' (The Rise of Red Skull)")
        print("  - 'got' (Galaxy's Most Wanted)")
        print("  - 'mts' (The Mad Titan's Shadow)")
        return

    if not isinstance(pack_cards, list):
        print(f"Error: Unexpected response format. Expected a list of cards.")
        return

    # 2. Filter for villain/encounter cards if requested
    if villain_only:
        pack_cards = [card for card in pack_cards if card.get('faction_code') == 'encounter']
        print(f"Found {len(pack_cards)} villain/encounter cards in pack '{pack_code}'.")
    else:
        print(f"Found {len(pack_cards)} total cards in pack '{pack_code}'.")
    
    # 3. Download Images for each card in the pack
    print(f"\nStarting download...")
    downloaded_count = 0
    
    for card_info in pack_cards:
        card_code = card_info.get('code')
        card_name = card_info.get('name', 'Unknown')
        card_type = card_info.get('type_code', 'unknown')
        
        if not card_code:
            print(f"Warning: Card without code found, skipping: {card_name}")
            continue
        
        # Use a sanitized version of the card name for the filename
        # Include type for better organization (e.g., villain, minion, treachery)
        sanitized_name = card_name.replace(' ', '_').replace('/', '').replace(':', '')
        if villain_only:
            sanitized_name = f"{card_type}_{sanitized_name}"
        
        download_card_image(
            card_code=card_code, 
            filename=sanitized_name, 
            folder=output_folder
        )
        downloaded_count += 1
            
    print(f"\nSuccessfully downloaded {downloaded_count} card images from pack '{pack_code}'.")
    print("--- Download Complete ---")


if __name__ == "__main__":
    pull_card_images_by_pack(PACK_CODE, OUTPUT_FOLDER, villain_only=VILLAIN_ONLY)