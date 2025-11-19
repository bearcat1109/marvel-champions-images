# Image processing script for HoH cards.

from PIL import Image, ImageFilter, ImageDraw, ImageOps
import os
import math

def detect_card_rotation(img):
    """
    Detect rotation angle of the card by analyzing edges.
    Returns angle in degrees (negative = clockwise, positive = counter-clockwise).
    """
    # Convert to grayscale and detect edges
    gray = img.convert('L')
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # Enhance edges
    edges = ImageOps.autocontrast(edges)
    
    width, height = edges.size
    pixels = edges.load()
    
    # Find edge points along the card border
    edge_points = []
    threshold = 100  # Edge intensity threshold
    
    # Sample top portion to find top edge angle
    for y in range(height // 4):
        for x in range(width):
            if pixels[x, y] > threshold:
                edge_points.append((x, y))
    
    if len(edge_points) < 10:
        return 0  # Not enough edge points, assume no rotation
    
    # Calculate approximate angle using top edge points
    # Group points by x-coordinate and find average y
    x_groups = {}
    for x, y in edge_points:
        x_bucket = x // 10
        if x_bucket not in x_groups:
            x_groups[x_bucket] = []
        x_groups[x_bucket].append(y)
    
    # Get average y for each x group
    line_points = []
    for x_bucket, y_values in x_groups.items():
        avg_y = sum(y_values) / len(y_values)
        line_points.append((x_bucket * 10, avg_y))
    
    if len(line_points) < 2:
        return 0
    
    # Calculate slope using first and last points
    line_points.sort()
    x1, y1 = line_points[0]
    x2, y2 = line_points[-1]
    
    if x2 - x1 == 0:
        return 0
    
    slope = (y2 - y1) / (x2 - x1)
    angle = math.degrees(math.atan(slope))
    
    # Limit rotation to small angles (cards shouldn't be wildly rotated)
    angle = max(-5, min(5, angle))
    
    return angle

# Add this function outside of your existing functions
def create_centered_crop_box(card_bounds, target_aspect_ratio, image_size):
    """
    Calculates a new crop box (left, top, right, bottom) centered on the 
    card bounds, matching the target aspect ratio, and constrained by 
    the original image size.
    
    Args:
        card_bounds (tuple): (left, top, right, bottom) of the detected card.
        target_aspect_ratio (float): target_width / target_height.
        image_size (tuple): (width, height) of the original image.
        
    Returns:
        tuple: (left, top, right, bottom) for the final crop.
    """
    left, top, right, bottom = card_bounds
    img_width, img_height = image_size
    
    # 1. Find the center of the detected card content
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    
    # 2. Determine the size of the *actual* card content
    card_w = right - left
    card_h = bottom - top
    
    # 3. Calculate the new crop size (width and height)
    # The new crop box must be large enough to contain the detected card,
    # but also maintain the target aspect ratio.
    current_aspect = card_w / card_h
    
    if current_aspect > target_aspect_ratio:
        # Card content is too wide (relative to height). Height is the limiting factor.
        # Use card_h and calculate the required width to match the aspect ratio.
        new_crop_h = card_h
        new_crop_w = new_crop_h * target_aspect_ratio
    else:
        # Card content is too tall (relative to width). Width is the limiting factor.
        # Use card_w and calculate the required height to match the aspect ratio.
        new_crop_w = card_w
        new_crop_h = new_crop_w / target_aspect_ratio
        
    # Add a small buffer/margin to the calculated size
    buffer_scale = 1.01  # 1% buffer on size
    new_crop_w *= buffer_scale
    new_crop_h *= buffer_scale
    
    # 4. Calculate the final, centered crop box coordinates
    final_left = int(center_x - new_crop_w / 2)
    final_top = int(center_y - new_crop_h / 2)
    final_right = int(center_x + new_crop_w / 2)
    final_bottom = int(center_y + new_crop_h / 2)
    
    # 5. Clamp the box to the original image dimensions
    final_left = max(0, final_left)
    final_top = max(0, final_top)
    final_right = min(img_width, final_right)
    final_bottom = min(img_height, final_bottom)
    
    # Re-adjust the box in case clamping made it off-center again (common near edges)
    # This step is complex but important for robustness. A simpler approach is to
    # just stick to the original image boundaries and accept a slightly smaller final crop
    # if the card was detected near the edge.
    
    return (final_left, final_top, final_right, final_bottom)


def find_card_bounds(img, sensitivity=30):
    """
    Find card boundaries by detecting the dark border of the card.
    Returns (left, top, right, bottom) coordinates.
    """
    # Convert to grayscale
    gray = img.convert('L')
    width, height = gray.size
    pixels = gray.load()
    
    # Scan from edges inward to find where card starts
    # Card border is darker than background
    
    # Find top edge
    top = 0
    for y in range(height // 2):
        dark_count = 0
        for x in range(width // 4, 3 * width // 4, 5):
            if pixels[x, y] < 200:
                dark_count += 1
        if dark_count > sensitivity:
            top = y
            break
    
    # Find bottom edge
    bottom = height - 1
    for y in range(height - 1, height // 2, -1):
        dark_count = 0
        for x in range(width // 4, 3 * width // 4, 5):
            if pixels[x, y] < 200:
                dark_count += 1
        if dark_count > sensitivity:
            bottom = y
            break
    
    # Find left edge
    left = 0
    for x in range(width // 2):
        dark_count = 0
        for y in range(height // 4, 3 * height // 4, 5):
            if pixels[x, y] < 200:
                dark_count += 1
        if dark_count > sensitivity:
            left = x
            break
    
    # Find right edge
    right = width - 1
    for x in range(width - 1, width // 2, -1):
        dark_count = 0
        for y in range(height // 4, 3 * height // 4, 5):
            if pixels[x, y] < 200:
                dark_count += 1
        if dark_count > sensitivity:
            right = x
            break
    
    return (left, top, right, bottom)


def process_card_image(input_path, output_path, target_size=(750, 1050), 
                       auto_detect=True, fix_rotation=True, manual_crop_percent=0.03):
    """
    Remove borders, straighten, and resize card image to uniform dimensions, 
    ensuring the final crop is centered on the detected card content.
    """
    # Open image
    img = Image.open(input_path)
    
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Fix rotation if enabled (Your existing code)
    if fix_rotation:
        angle = detect_card_rotation(img)
        if abs(angle) > 0.1:
            # Note: The rotation function expands the canvas, which is fine
            # because the centering logic will re-find the card edges.
            img = img.rotate(-angle, expand=True, fillcolor='white', resample=Image.BICUBIC)
            print(f"Rotated by {-angle:.2f} degrees")
    
    width, height = img.size
    
    if auto_detect:
        # Detect card boundaries (Your existing code)
        card_left, card_top, card_right, card_bottom = find_card_bounds(img)
        
        # --- NEW CENTERING LOGIC ---
        target_aspect_ratio = target_size[0] / target_size[1]
        
        # Calculate the final, centered crop box
        left, top, right, bottom = create_centered_crop_box(
            (card_left, card_top, card_right, card_bottom), 
            target_aspect_ratio, 
            (width, height)
        )
        
        print(f"Card bounds: ({card_left}, {card_top}, {card_right}, {card_bottom})")
        print(f"Centered crop box: ({left}, {top}, {right}, {bottom})")
        # --- END NEW CENTERING LOGIC ---

    else:
        # Simple percentage crop (Your existing code for manual crop)
        crop_w = int(width * manual_crop_percent)
        crop_h = int(height * manual_crop_percent)
        left, top = crop_w, crop_h
        right, bottom = width - crop_w, height - crop_h
        print(f"Manual crop: {crop_w}px from each edge")
    
    # Crop to boundaries (now the centered boundaries)
    cropped = img.crop((left, top, right, bottom))
    
    # Resize to target dimensions
    # Resize the perfectly centered, aspect-ratio-corrected crop to the final size
    resized = cropped.resize(target_size, Image.LANCZOS)
    
    # Save with high quality
    resized.save(output_path, quality=95, dpi=(300, 300))
    
    print(f"Processed: {os.path.basename(input_path)}\n")
    return resized


def batch_process_cards(input_folder, output_folder, target_size=(750, 1050), 
                       auto_detect=True, fix_rotation=True, manual_crop_percent=0.03):
    """
    Process all card images in a folder.
    
    Args:
        input_folder: Folder containing original images
        output_folder: Folder to save processed images
        target_size: Final dimensions (width, height) in pixels
        auto_detect: Use automatic border detection
        fix_rotation: Automatically detect and fix card rotation
        manual_crop_percent: Percentage to crop if not auto-detecting
    """
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Supported image formats
    extensions = ('.jpg', '.jpeg', '.png', '.webp')
    
    # Process each image
    processed = 0
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(extensions):
            input_path = os.path.join(input_folder, filename)
            
            # Keep original filename but ensure .jpg extension
            name, _ = os.path.splitext(filename)
            output_path = os.path.join(output_folder, f"{name}.jpg")
            
            try:
                process_card_image(input_path, output_path, target_size, 
                                 auto_detect, fix_rotation, manual_crop_percent)
                processed += 1
            except Exception as e:
                print(f"Error processing {filename}: {e}\n")
    
    print(f"Processed {processed} images successfully!")


# Example usage:
if __name__ == "__main__":
    # Single image with auto-detection and rotation fix
    # process_card_image('ghost_spider.jpg', 'ghost_spider_processed.jpg', 
    #                   auto_detect=True, fix_rotation=True)
    
    # Single image without rotation fix
    # process_card_image('ghost_spider.jpg', 'ghost_spider_processed.jpg', 
    #                   auto_detect=True, fix_rotation=False)
    
    # Batch process with auto-detection and rotation fix
    batch_process_cards(
        input_folder='sinister_motives_fullres',
        output_folder='processed_cards',
        target_size=(750, 1050),
        auto_detect=True,
        fix_rotation=True
    )