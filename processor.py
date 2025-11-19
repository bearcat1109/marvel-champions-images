# Image processing script for HoH cards.

from PIL import Image, ImageFilter, ImageDraw, ImageOps
import os
import math

def detect_card_rotation(img, threshold=200):
    """
    Detects the rotation angle of a card image by analyzing the top edge.

    Args:
        img (PIL.Image): The input image (expected to be cropped to the card).
        threshold (int): Pixel intensity threshold for identifying an edge point.

    Returns:
        float: The detected angle of rotation in degrees (positive is counter-clockwise).
    """
    width, height = img.size
    
    # 1. Image Preprocessing for Edge Detection
    # Convert to grayscale ('L') for simplicity
    gray = img.convert('L') 
    
    # Apply a slight Gaussian blur to smooth out noise and fine details (card art), 
    # ensuring the coarse card border is the dominant feature.
    # Radius of 1.5 is generally good for minor smoothing.
    gray = gray.filter(ImageFilter.GaussianBlur(radius=1.5)) 
    
    # Apply an edge detection filter
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # Get pixel data for analysis
    pixels = edges.load()
    
    # 2. Sample Edge Points from the Top Half of the Image
    # We only look at the top part since we assume the top border is visible 
    # and straight across the whole image.
    edge_points = []
    
    max_y_sample = height // 7
    # Sample the top 1/3 to 1/2 of the image height for a good sample size (height // 2).
    # We iterate across all columns (x) and the top rows (y).
    for y in range(max_y_sample): 
        for x in range(width):
            # Check if the pixel intensity is above the threshold (i.e., it's an edge)
            if pixels[x, y] > threshold:
                edge_points.append((x, y))

    # 3. Calculate Slope (Linear Regression Approximation)
    if not edge_points or len(edge_points) < 5:
        # Not enough data to calculate a reliable angle
        return 0.0

    # Calculate the average x and y values
    avg_x = sum(p[0] for p in edge_points) / len(edge_points)
    avg_y = sum(p[1] for p in edge_points) / len(edge_points)

    # Perform a simple slope calculation (M = Sum[(x_i - avg_x) * (y_i - avg_y)] / Sum[(x_i - avg_x)^2])
    # This finds the line of best fit for the detected edge points.
    numerator = 0.0
    denominator = 0.0
    
    for x, y in edge_points:
        dx = x - avg_x
        dy = y - avg_y
        numerator += dx * dy
        denominator += dx * dx

    # Avoid division by zero (e.g., if all points are perfectly vertical)
    if denominator == 0:
        return 0.0

    slope = numerator / denominator

    # 4. Convert Slope to Angle in Degrees
    # Angle (radians) = atan(slope)
    angle_rad = math.atan(slope)
    angle_deg = math.degrees(angle_rad)

    # Note: If the slope calculation is slightly off, the angle can be large. 
    # We generally expect card skew to be less than +/- 5 degrees.
    angle_deg = max(-5.0, min(5.0, angle_deg))
    
    return angle_deg

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
    # Batch process with auto-detection and rotation fix
    batch_process_cards(
        input_folder='deck_38353_cards',
        output_folder='processed_cards',
        target_size=(750, 1050),
        auto_detect=True,
        fix_rotation=True
    )