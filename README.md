# *Welcome!*

## This repo contains a few different scripts for different purposes.

**marvelcdb-script.py**: This generates a folder of images from the cards contained in a Marvel CDB decklist. Use the decklist ID found in the URL
  in the script on line 11. 
  - There are a few checks in the script to make sure it gets the right version of a card, mainly based on traits and color.
  - The script also gets core images when available, since the images on these are generally better centered and more consistent than other printings,
  and also sometimes the box printings just do not have images.

**scrape-hoh.py**: This scrapes all images from a Hall of Heroes page for use as card images. This can be less consistent but Hall of Heroes
  has high quality images. Replace the URL a the top of the script with the page you want to scrape and then the TARGET_SECTIONS with what parts of
  the page you want to scrape.

**processor.py**: This script takes all the images in a folder, and does its best work to fix any alignment issues or off centering. It's not perfect, 
  but can help significantly especially with how inconsistent centering is on HoH.

**generate-pdf.py**: This script takes all images in a given folder (Named after the deck ID) and places them the amount of times they are in the deck
  onto a PDF page so that they can be printed! The cards are resized to a height of 3.49 inches (Standard height), in a 3x3 layout by default. 
  Happy proxy-ing!
