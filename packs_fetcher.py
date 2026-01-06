# Script to fetch all available pack codes from MarvelCDB
# This will help you identify which pack code to use for downloading images

import requests
import json

BASE_URL = "https://marvelcdb.com"
PACKS_ENDPOINT = f"{BASE_URL}/api/public/packs"

def get_all_pack_codes():
    """
    Fetches all available packs and their codes from the MarvelCDB API.
    """
    print("Fetching all pack codes from MarvelCDB...")
    
    try:
        response = requests.get(PACKS_ENDPOINT, timeout=10)
        response.raise_for_status()
        packs = response.json()
        
        if not isinstance(packs, list):
            print("Error: Unexpected response format")
            return
        
        print(f"\nFound {len(packs)} packs:")
        print("\n" + "="*80)
        print(f"{'Pack Code':<20} {'Pack Name':<40} {'Cycle':<20}")
        print("="*80)
        
        # Sort by cycle position and then by position within cycle
        sorted_packs = sorted(packs, key=lambda x: (x.get('cycle_position', 0), x.get('position', 0)))
        
        for pack in sorted_packs:
            code = pack.get('code', 'N/A')
            name = pack.get('name', 'Unknown')
            cycle = pack.get('cycle_code', 'N/A')
            
            print(f"{code:<20} {name:<40} {cycle:<20}")
        
        print("="*80)
        print("\nUsage: Change PACK_CODE in your download script to any of the codes above.")
        print("Example: PACK_CODE = 'core' for Core Set")
        print("Example: PACK_CODE = 'cap' for Captain America Hero Pack")
        
        # Save to JSON file for reference
        with open('pack_codes_reference.json', 'w') as f:
            json.dump(sorted_packs, f, indent=2)
        print("\nPack information saved to 'pack_codes_reference.json'")
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching packs: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    get_all_pack_codes()